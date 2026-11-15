"""
Admin decision on a watsonx Orchestrate recommendation.

The agent only recommends. An admin either:
* approves  -> the matching human workflow action runs (same gates and audit trail as the
               manual buttons), then the recommendation is marked approved; or
* dismisses -> nothing changes except the recommendation being marked dismissed.

Recommendations that were made at an earlier workflow step ("stale") cannot be approved.
"""
import json
import uuid
from typing import Any, Dict, Optional

from fastapi import HTTPException

from backend.app.timeutil import utcnow
from backend.app.models.database import get_db_connection
from backend.app.services import agent_tools_service as tools
from backend.app.services.incident_service import IncidentService

# Actions that map to a workflow step. Others (monitor, escalate, request_field_verification)
# have no admin state change: approving them just acknowledges the advice.
STATE_CHANGING = {"request_triage", "assign_team", "reject_duplicate", "propose_block", "propose_reopen"}


def _load_event(event_id: str) -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT id, incident_id, result, decision FROM agent_events WHERE id = ? AND action = 'recommendation'",
            (event_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Recommendation not found.")
    return {"id": row["id"], "incident_id": row["incident_id"], "decision": row["decision"],
            "rec": json.loads(row["result"])}


def _execute(action: str, incident_id: str, admin_id: str, admin_name: str,
             notes: str, team_id: Optional[str], responder_id: Optional[str] = None) -> None:
    if action == "request_triage":
        IncidentService.admin_review(incident_id, admin_id, admin_name, notes)
    elif action == "assign_team":
        if not team_id:
            raise HTTPException(status_code=422, detail="Choose a response team to approve this recommendation.")
        IncidentService.admin_assign_team(incident_id, admin_id, admin_name, team_id, notes, responder_id)
    elif action == "reject_duplicate":
        IncidentService.admin_authorize_restriction(incident_id, admin_id, admin_name, "reject", notes)
    elif action == "propose_block":
        IncidentService.admin_authorize_restriction(incident_id, admin_id, admin_name, "authorize_block", notes)
    elif action == "propose_reopen":
        IncidentService.admin_authorize_restriction(incident_id, admin_id, admin_name, "authorize_reopen", notes)


def decide(event_id: str, decision: str, admin_id: str, admin_name: str,
           notes: Optional[str] = None, team_id: Optional[str] = None,
           responder_id: Optional[str] = None) -> Dict[str, Any]:
    if decision not in ("approve", "dismiss"):
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'dismiss'.")
    ev = _load_event(event_id)
    if ev["decision"]:
        raise HTTPException(status_code=409, detail=f"This recommendation was already {ev['decision']}.")

    rec, incident_id = ev["rec"], ev["incident_id"]
    inc = IncidentService.get_incident_by_id(incident_id, role="admin")
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found.")

    outcome = "approved" if decision == "approve" else "dismissed"
    if decision == "approve":
        if inc["status"] != rec.get("status_at_recommendation"):
            raise HTTPException(
                status_code=409,
                detail=f"Incident is now '{inc['status']}' but this was recommended at '{rec.get('status_at_recommendation')}'. "
                       "Re-analyse before approving.")
        if rec["action"] in STATE_CHANGING:
            text = (notes or "").strip() or f"Approved agent recommendation: {rec['rationale']}"[:400]
            if not team_id:  # nothing chosen by the admin: use what the agent recommended
                team_id, responder_id = rec.get("team_id"), rec.get("responder_id")
            _execute(rec["action"], incident_id, admin_id, admin_name, text, team_id, responder_id)

    now = utcnow().isoformat()
    conn = get_db_connection()
    try:
        conn.execute("UPDATE agent_events SET decision = ?, decided_by = ?, decided_at = ? WHERE id = ?",
                     (outcome, admin_id, now, event_id))
        conn.execute(
            "INSERT INTO audit_events (id, actor_id, actor_name, action, entity_type, entity_id, before_state, after_state, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), admin_id, admin_name, f"AGENT_RECOMMENDATION_{outcome.upper()}",
             "agent_recommendation", event_id,
             json.dumps({"action": rec["action"], "status_at_recommendation": rec.get("status_at_recommendation")}),
             json.dumps({"decision": outcome, "incident_id": incident_id,
                         "state_changed": decision == "approve" and rec["action"] in STATE_CHANGING}), now))
        conn.commit()
    finally:
        conn.close()
    return {
        "recommendation": tools.latest_recommendation(incident_id),
        "incident": IncidentService.get_incident_by_id(incident_id, role="admin"),
    }
