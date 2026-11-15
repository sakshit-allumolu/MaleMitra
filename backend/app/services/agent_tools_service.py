"""
Tool layer exposed to the watsonx Orchestrate agent.

Orchestrate's LLM decides *which* tool to call; these functions are the
deterministic, auditable actions it can take. Design rules:

* Read tools never mutate state.
* run_ripple_what_if is a sandboxed simulation (run_simulation restores real edge state).
* submit_recommendation is the only write, and it only appends a recommendation
  (requires_approval=1). It never changes an incident's status or blocks a road:
  admins keep the authorization gate.
* Every call, accepted or rejected, is appended to agent_events.
"""
import json
import uuid
from typing import Any, Dict, List, Optional

from backend.app.timeutil import utcnow
from backend.app.config import settings
from backend.app.models.database import get_db_connection
from backend.app.models.schemas import IncidentStatus
from backend.app.services.graph_service import road_graph
from backend.app.services.incident_service import IncidentService
from backend.app.services.ripple_service import ripple_engine

AGENT_NAME = "watsonx_orchestrate"
DATA_MODE = "orchestrate"

MAX_WHAT_IF_EDGES = 5
MAX_LIST_RESULTS = 25

# Action -> incident statuses in which the recommendation is allowed. Mirrors the
# human workflow gates in IncidentService so the agent cannot suggest a skipped step.
ALLOWED_ACTIONS: Dict[str, Optional[tuple]] = {
    "request_triage": (IncidentStatus.REPORTED,),
    "assign_team": (IncidentStatus.UNDER_REVIEW,),
    "reject_duplicate": (IncidentStatus.REPORTED, IncidentStatus.UNDER_REVIEW),
    "request_field_verification": (IncidentStatus.ASSIGNED,),
    "propose_block": (IncidentStatus.FIELD_VERIFIED,),
    "propose_reopen": (IncidentStatus.CLEARANCE_PROPOSED,),
    "monitor": None,   # allowed for any open incident
    "escalate": None,
}


class ToolError(Exception):
    """Validation / guardrail failure. Surfaced to the agent as a structured error."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _now() -> str:
    return utcnow().isoformat()


def log_tool_call(tool: str, args: Dict[str, Any], outcome: str, result: Dict[str, Any],
                  incident_id: Optional[str] = None, requires_approval: bool = False) -> None:
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO agent_events (id, incident_id, agent, action, input_refs, result, data_mode, requires_approval, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()), incident_id, AGENT_NAME, f"tool:{tool}",
                json.dumps([f"{k}={v}" for k, v in args.items()], default=str),
                json.dumps({"outcome": outcome, **result}, default=str),
                DATA_MODE, 1 if requires_approval else 0, _now(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def list_responder_availability(team_id: Optional[str] = None) -> Dict[str, Any]:
    responders = IncidentService.get_responder_availability(team_id)
    return {
        "count": len(responders),
        "free_count": sum(1 for r in responders if r["is_free"]),
        "responders": responders,
        "note": "A responder is free when they have no incident in assigned, field_verified, blocked or clearance_proposed.",
    }


def _slim_incident(inc: Dict[str, Any]) -> Dict[str, Any]:
    summary = inc.get("agent_summary") or {}
    return {
        "id": inc["id"],
        "road_edge_id": inc["road_edge_id"],
        "road_name": inc["road_name"],
        "type": inc["type"],
        "severity": inc["severity"],
        "status": inc["status"],
        "confidence": inc["confidence"],
        "reports_count": inc["reports_count"],
        "duplicate_of": summary.get("duplicate_of"),
        "is_ambiguous": summary.get("is_ambiguous"),
        "assigned_team_id": inc["assigned_team_id"],
        "assigned_responder_id": inc.get("assigned_responder_id"),
        "is_blocked": inc["is_blocked"],
        "created_at": inc["created_at"],
    }


# ── Tools ──────────────────────────────────────────────────────────────────

def map_to_edge(lat: float, lon: float) -> Dict[str, Any]:
    if not (settings.MIN_LAT <= lat <= settings.MAX_LAT and settings.MIN_LON <= lon <= settings.MAX_LON):
        raise ToolError("out_of_bounds", "Coordinates are outside the supported Bengaluru service area.")
    edge, dist_m, ambiguous = road_graph.find_nearest_edge(lat, lon)
    if not edge:
        raise ToolError("no_edge", "No road segment found near these coordinates.")
    return {
        "edge_id": edge.edge_id,
        "road_name": edge.road_name,
        "distance_m": round(dist_m, 1),
        "is_ambiguous": ambiguous,
        "is_blocked": edge.is_blocked,
        "hazard_severity": edge.hazard_severity,
    }


# An LLM filling in "status" often sends one of these to mean "no filter" (every incident listed is open).
_NO_FILTER = {"", "open", "all", "any", "active", "none", "null", "*"}


def list_open_incidents(status: Optional[str] = None) -> Dict[str, Any]:
    if status is not None:
        status = status.strip().lower().replace(" ", "_").replace("-", "_")
        if status in _NO_FILTER:
            status = None
    if status is not None and status not in IncidentService.ACTIVE_STATUSES:
        raise ToolError("invalid_status", f"status must be one of {sorted(IncidentService.ACTIVE_STATUSES)}")
    incidents = [
        i for i in IncidentService.get_all_incidents(role="admin")
        if i["status"] in IncidentService.ACTIVE_STATUSES and (status is None or i["status"] == status)
    ]
    return {
        "count": len(incidents),
        "incidents": [_slim_incident(i) for i in incidents[:MAX_LIST_RESULTS]],
        "truncated": len(incidents) > MAX_LIST_RESULTS,
    }


def latest_recommendation(incident_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT id, result, created_at, decision, decided_by, decided_at FROM agent_events "
            "WHERE incident_id = ? AND action = 'recommendation' ORDER BY created_at DESC LIMIT 1", (incident_id,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    data = json.loads(row["result"])
    data["created_at"] = row["created_at"]
    data["event_id"] = row["id"]
    data["decision"] = row["decision"]          # None until an admin approves or dismisses it
    data["decided_by"] = row["decided_by"]
    data["decided_at"] = row["decided_at"]
    return data


def get_incident_context(incident_id: str) -> Dict[str, Any]:
    inc = IncidentService.get_incident_by_id(incident_id, role="admin")
    if not inc:
        raise ToolError("not_found", f"Incident {incident_id} not found.")
    edge = road_graph.edges.get(inc["road_edge_id"]) if inc["road_edge_id"] else None
    same_edge = [
        _slim_incident(i) for i in IncidentService.get_all_incidents(role="admin")
        if i["road_edge_id"] == inc["road_edge_id"] and i["id"] != incident_id
        and i["status"] in IncidentService.ACTIVE_STATUSES
    ]
    return {
        "incident": _slim_incident(inc),
        "verification_notes": inc["verification_notes"],
        "water_depth_cm": inc["water_depth_cm"],
        "evidence": [
            {"type": e["evidence_type"], "notes": e["text_notes"], "at": e["created_at"]}
            for e in inc["evidence_list"][-5:]
        ],
        "edge": edge.to_dict() | {"geometry": None} if edge else None,
        "other_open_incidents_on_edge": same_edge,
        "previous_recommendation": latest_recommendation(incident_id),
    }


def compute_route(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float) -> Dict[str, Any]:
    from backend.app.services.agent_service import AgentOrchestrator  # local import: avoids cycle at module load
    for lat, lon in ((origin_lat, origin_lon), (dest_lat, dest_lon)):
        if not (settings.MIN_LAT <= lat <= settings.MAX_LAT and settings.MIN_LON <= lon <= settings.MAX_LON):
            raise ToolError("out_of_bounds", "Coordinates are outside the supported Bengaluru service area.")
    scores = AgentOrchestrator._graph_risk_scores(origin_lat, origin_lon, dest_lat, dest_lon)
    if not scores:
        raise ToolError("no_route", "No route found between these points on the modelled network.")
    trimmed = {}
    for name, s in scores.items():
        trimmed[name] = {k: v for k, v in s.items() if k != "node_ids"}
    return {"routes": trimmed}


def estimate_bpr_load(edge_id: str) -> Dict[str, Any]:
    edge = road_graph.edges.get(edge_id)
    if not edge:
        raise ToolError("not_found", f"Edge {edge_id} not found.")
    live = edge.has_fresh_live_data()
    if live:
        vc = float(edge.live_vc)
        source = "live_traffic"
    else:
        vc = edge.simulated_flow / max(10, edge.capacity_proxy)
        source = "ripple_simulation"
    bpr_s = edge.travel_time_s * (1 + settings.BPR_ALPHA * (vc ** settings.BPR_BETA))
    return {
        "edge_id": edge.edge_id,
        "road_name": edge.road_name,
        "volume_capacity_ratio": round(vc, 2),
        "source": source,
        "free_flow_s": round(edge.travel_time_s, 1),
        "bpr_travel_time_s": round(bpr_s, 1),
        "delay_s": round(bpr_s - edge.travel_time_s, 1),
        "is_blocked": edge.is_blocked,
    }


def run_ripple_what_if(edge_ids: List[str]) -> Dict[str, Any]:
    if not edge_ids:
        raise ToolError("invalid_input", "edge_ids must contain at least one edge.")
    if len(edge_ids) > MAX_WHAT_IF_EDGES:
        raise ToolError("too_many_edges", f"At most {MAX_WHAT_IF_EDGES} edges per what-if run.")
    unknown = [e for e in edge_ids if e not in road_graph.edges]
    if unknown:
        raise ToolError("not_found", f"Unknown edge ids: {unknown}")
    result = ripple_engine.run_simulation(custom_blocked_edge_ids=list(edge_ids))
    return {
        "simulated_blocked_edges": result["blocked_edges"],
        "total_trips": result["total_trips"],
        "affected_trips": result["affected_trips"],
        "mean_detour_s": result["mean_detour_s"],
        "pct_travel_time_increase": result["pct_travel_time_increase"],
        "top_affected_edges": [
            {"edge_id": m["edge_id"], "road_name": m["road_name"], "delta_load": m["delta_load"],
             "congestion_ratio": m["congestion_ratio"], "status": m["status"]}
            for m in result["top_affected_edges"][:5]
        ],
        "note": "Sandboxed what-if; live road state was not modified.",
    }


def submit_recommendation(incident_id: str, action: str, rationale: str, confidence: float,
                          team_id: Optional[str] = None, responder_id: Optional[str] = None) -> Dict[str, Any]:
    if action not in ALLOWED_ACTIONS:
        raise ToolError("invalid_action", f"action must be one of {sorted(ALLOWED_ACTIONS)}")
    rationale = (rationale or "").strip()
    if len(rationale) < 10:
        raise ToolError("invalid_input", "rationale must explain the recommendation (min 10 characters).")
    if not (0.0 <= confidence <= 1.0):
        raise ToolError("invalid_input", "confidence must be between 0 and 1.")
    inc = IncidentService.get_incident_by_id(incident_id, role="admin")
    if not inc:
        raise ToolError("not_found", f"Incident {incident_id} not found.")
    if inc["status"] not in IncidentService.ACTIVE_STATUSES:
        raise ToolError("incident_closed", f"Incident is {inc['status']}; no further recommendations.")
    allowed = ALLOWED_ACTIONS[action]
    if allowed is not None and inc["status"] not in allowed:
        raise ToolError(
            "workflow_gate",
            f"'{action}' is only valid when status is {[str(s) for s in allowed]}; incident is '{inc['status']}'.",
        )
    if (team_id or responder_id) and action != "assign_team":
        raise ToolError("invalid_input", "team_id / responder_id only apply to the assign_team action.")
    if responder_id:
        match = next((r for r in IncidentService.get_responder_availability() if r["id"] == responder_id), None)
        if not match:
            raise ToolError("not_found", f"Responder {responder_id} not found.")
        if team_id and team_id != match["team_id"]:
            raise ToolError("invalid_input", f"Responder {responder_id} is on {match['team_id']}, not {team_id}.")
        if not match["is_free"]:
            raise ToolError("responder_busy", f"Responder {responder_id} is not free. Pick a free responder, or recommend the team queue.")
        team_id = match["team_id"]
    rec = {
        "incident_id": incident_id,
        "action": action,
        "rationale": rationale[:1000],
        "confidence": round(confidence, 2),
        "status_at_recommendation": inc["status"],
        "requires_human_approval": True,
    }
    if action == "assign_team":
        rec["team_id"] = team_id            # None until the admin chooses a team
        rec["responder_id"] = responder_id  # None = leave in the team queue
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO agent_events (id, incident_id, agent, action, input_refs, result, data_mode, requires_approval, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), incident_id, AGENT_NAME, "recommendation",
             json.dumps([f"incident:{incident_id}"]), json.dumps(rec), DATA_MODE, 1, _now()),
        )
        conn.commit()
    finally:
        conn.close()
    return {**rec, "recorded": True, "note": "Recommendation recorded for admin review. No state was changed."}


TOOLS = {
    "map_to_edge": map_to_edge,
    "list_open_incidents": list_open_incidents,
    "list_responder_availability": list_responder_availability,
    "get_incident_context": get_incident_context,
    "compute_route": compute_route,
    "estimate_bpr_load": estimate_bpr_load,
    "run_ripple_what_if": run_ripple_what_if,
    "submit_recommendation": submit_recommendation,
}


def invoke(tool: str, **kwargs) -> Dict[str, Any]:
    """Run a tool with guardrails; every call (success or failure) is logged."""
    fn = TOOLS[tool]
    incident_id = kwargs.get("incident_id")
    try:
        result = fn(**kwargs)
    except ToolError as e:
        log_tool_call(tool, kwargs, "rejected", {"error": e.code, "message": e.message}, incident_id)
        raise
    # submit_recommendation already wrote its own 'recommendation' event; don't double-log it.
    if tool != "submit_recommendation":
        log_tool_call(tool, kwargs, "ok", {"summary": _summarize(tool, result)}, incident_id)
    return result


def _summarize(tool: str, result: Dict[str, Any]) -> str:
    if tool == "list_open_incidents":
        return f"{result['count']} open incidents"
    if tool == "list_responder_availability":
        return f"{result['free_count']}/{result['count']} responders free"
    if tool == "map_to_edge":
        return f"{result['edge_id']} ({result['road_name']}, {result['distance_m']}m)"
    if tool == "get_incident_context":
        return f"context for {result['incident']['id']} on {result['incident']['road_name']}"
    if tool == "compute_route":
        return f"routes: {', '.join(result['routes'])}"
    if tool == "estimate_bpr_load":
        return f"{result['edge_id']} v/c={result['volume_capacity_ratio']} delay={result['delay_s']}s"
    if tool == "run_ripple_what_if":
        return f"{result['affected_trips']}/{result['total_trips']} trips affected, +{result['pct_travel_time_increase']}%"
    if tool == "submit_recommendation":
        return f"{result['action']} (conf {result['confidence']})"
    return "ok"
