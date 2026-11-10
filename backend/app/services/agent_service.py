import json
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, List, Optional, Any, Tuple
from backend.app.models.database import get_db_connection
from backend.app.services.graph_service import road_graph, RoadEdge, haversine_distance
from backend.app.services.ripple_service import ripple_engine

# ── OSRM public demo API ───────────────────────────────────────────────────────
# Uses the free public OSRM demo server — no API key required.
# Driving profile, returns full geometry + turn-by-turn steps.
OSRM_BASE = "https://router.project-osrm.org/route/v1/driving"

def _decode_polyline6(encoded: str) -> List[List[float]]:
    """
    Decodes a Google/OSRM encoded polyline (precision 6) into [[lat,lon], ...].
    OSRM returns geometry as encoded polyline when overview=full&geometries=polyline6.
    """
    coords = []
    index, lat, lng = 0, 0, 0
    while index < len(encoded):
        for coord_idx, is_lat in enumerate([True, False]):
            result, shift, b = 0, 0, 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            value = ~(result >> 1) if (result & 1) else (result >> 1)
            if is_lat:
                lat += value
            else:
                lng += value
        coords.append([lat / 1e6, lng / 1e6])
    return coords


def _fetch_osrm_route(
    origin_lat: float, origin_lon: float,
    dest_lat: float, dest_lon: float,
    alternatives: bool = True
) -> Optional[Dict]:
    """
    Calls OSRM routing API and returns the parsed JSON response.
    Returns None on any network/parse failure (graceful degradation).
    """
    # OSRM expects lon,lat order
    coords_str = f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
    params = urllib.parse.urlencode({
        "overview": "full",
        "geometries": "polyline6",
        "steps": "true",
        "alternatives": "true" if alternatives else "false",
        "annotations": "false",
    })
    url = f"{OSRM_BASE}/{coords_str}?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MaleMitra/1.0 (Bobathon 2026)"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[OSRM] Request failed: {e}")
        return None


def _osrm_steps_to_directions(steps: List[Dict]) -> List[Dict]:
    """
    Converts OSRM step objects into a simplified directions list for the frontend.
    """
    MANEUVER_ICONS = {
        "turn": {"left": "↰", "right": "↱", "sharp left": "↺", "sharp right": "↻",
                 "slight left": "↖", "slight right": "↗", "uturn": "↩"},
        "new name": {"": "→"},
        "depart": {"": "🏁"},
        "arrive": {"": "🎯"},
        "roundabout": {"": "🔄"},
        "rotary": {"": "🔄"},
        "merge": {"": "⤵"},
        "fork": {"left": "↰", "right": "↱"},
        "end of road": {"left": "↰", "right": "↱"},
        "continue": {"": "↑"},
        "notification": {"": "ℹ️"},
    }
    result = []
    for s in steps:
        maneuver = s.get("maneuver", {})
        m_type = maneuver.get("type", "")
        m_mod = maneuver.get("modifier", "")
        icon = MANEUVER_ICONS.get(m_type, {}).get(m_mod) or MANEUVER_ICONS.get(m_type, {}).get("") or "→"
        name = s.get("name") or ""
        dist_m = round(s.get("distance", 0))
        dur_s = round(s.get("duration", 0))

        if m_type == "depart":
            instruction = f"Start on {name}" if name else "Depart"
        elif m_type == "arrive":
            instruction = "Arrive at your destination"
        elif m_type in ("turn", "end of road", "fork"):
            instruction = f"Turn {m_mod} onto {name}" if name else f"Turn {m_mod}"
        elif m_type == "new name":
            instruction = f"Continue onto {name}" if name else "Continue"
        elif m_type in ("roundabout", "rotary"):
            exit_n = maneuver.get("exit", "")
            instruction = f"Take exit {exit_n} at roundabout" + (f" onto {name}" if name else "")
        elif m_type == "merge":
            instruction = f"Merge onto {name}" if name else "Merge"
        else:
            instruction = f"Continue on {name}" if name else "Continue"

        result.append({
            "icon": icon,
            "instruction": instruction,
            "road": name,
            "distance_m": dist_m,
            "duration_s": dur_s,
            "dist": f"{dist_m}m" if dist_m < 1000 else f"{dist_m/1000:.1f}km",
        })
    return result


class AgentOrchestrator:

    @staticmethod
    def get_recent_agent_events(limit: int = 50) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM agent_events ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        events = []
        for r in rows:
            input_refs = []
            if r["input_refs"]:
                try:
                    input_refs = json.loads(r["input_refs"])
                except Exception:
                    input_refs = [r["input_refs"]]
            res_dict = {}
            if r["result"]:
                try:
                    res_dict = json.loads(r["result"])
                except Exception:
                    res_dict = {"raw": r["result"]}
            events.append({
                "event_id": r["id"],
                "incident_id": r["incident_id"],
                "agent": r["agent"],
                "action": r["action"],
                "input_refs": input_refs,
                "result": res_dict,
                "data_mode": r["data_mode"],
                "requires_approval": bool(r["requires_approval"]),
                "timestamp": r["created_at"]
            })
        conn.close()
        return events

    @staticmethod
    def get_recent_audit_events(limit: int = 50) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_events ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        audits = []
        for r in rows:
            before_dict = None
            if r["before_state"]:
                try:
                    before_dict = json.loads(r["before_state"])
                except Exception:
                    before_dict = {"raw": r["before_state"]}
            after_dict = None
            if r["after_state"]:
                try:
                    after_dict = json.loads(r["after_state"])
                except Exception:
                    after_dict = {"raw": r["after_state"]}
            audits.append({
                "id": r["id"],
                "actor_id": r["actor_id"],
                "actor_name": r["actor_name"],
                "action": r["action"],
                "entity_type": r["entity_type"],
                "entity_id": r["entity_id"],
                "before_state": before_dict,
                "after_state": after_dict,
                "timestamp": r["created_at"]
            })
        conn.close()
        return audits

    @staticmethod
    def _graph_risk_scores(
        origin_lat: float, origin_lon: float,
        dest_lat: float, dest_lon: float
    ) -> Dict[str, Any]:
        """
        Runs our internal Dijkstra to compute hazard/block risk scores.
        Returns a dict of risk metadata — does NOT produce display coordinates.
        """
        start_node = road_graph.find_nearest_node(origin_lat, origin_lon)
        end_node = road_graph.find_nearest_node(dest_lat, dest_lon)
        if not start_node or not end_node or start_node == end_node:
            start_node = "N1"
            end_node = "N7"

        results = {}

        # Fastest path risk
        fastest = road_graph.compute_dijkstra(start_node, end_node, mode="fastest")
        if fastest:
            nodes_f, edges_f, dur_f = fastest
            results["fastest"] = {
                "node_names": [road_graph.nodes[n]["name"] for n in nodes_f if n in road_graph.nodes],
                "duration_s": round(dur_f, 1),
                "distance_m": round(sum(e.length_m for e in edges_f), 1),
                "blocked_crossed": sum(1 for e in edges_f if e.is_blocked),
                "risk_score": min(1.0, round(sum(
                    0.35 if e.hazard_severity == "high" else 0.18
                    for e in edges_f if e.hazard_severity != "none"
                ), 2)),
                "hazard_penalty_s": 0.0,
                "congestion_delay_s": max(0.0, round(
                    dur_f - sum(e.travel_time_s for e in edges_f), 1)),
            }

        # Risk-aware path
        risk = road_graph.compute_dijkstra(start_node, end_node, mode="risk_aware")
        if risk:
            nodes_r, edges_r, dur_r = risk
            results["risk_aware"] = {
                "node_names": [road_graph.nodes[n]["name"] for n in nodes_r if n in road_graph.nodes],
                "duration_s": round(dur_r, 1),
                "distance_m": round(sum(e.length_m for e in edges_r), 1),
                "blocked_crossed": sum(1 for e in edges_r if e.is_blocked),
                "risk_score": min(0.3, round(sum(
                    0.08 for e in edges_r if e.hazard_severity != "none"), 2)),
                "hazard_penalty_s": round(sum(
                    40.0 for e in edges_r if e.hazard_severity != "none"), 1),
                "congestion_delay_s": max(0.0, round(
                    dur_r - sum(e.travel_time_s for e in edges_r), 1)),
            }

        # Alternative (Yen's)
        k_paths = road_graph.compute_k_shortest_paths(start_node, end_node, k=2, mode="risk_aware")
        if len(k_paths) > 1:
            nodes_a, edges_a, dur_a = k_paths[1]
            results["alternative"] = {
                "node_names": [road_graph.nodes[n]["name"] for n in nodes_a if n in road_graph.nodes],
                "duration_s": round(dur_a, 1),
                "distance_m": round(sum(e.length_m for e in edges_a), 1),
                "blocked_crossed": 0,
                "risk_score": 0.12,
                "hazard_penalty_s": 0.0,
                "congestion_delay_s": max(0.0, round(
                    dur_a - sum(e.travel_time_s for e in edges_a), 1)),
            }

        return results

    @staticmethod
    def _fallback_coords(
        origin_lat: float, origin_lon: float,
        dest_lat: float, dest_lon: float,
        edges: List[RoadEdge]
    ) -> List[List[float]]:
        """Straight-line fallback when OSRM is unavailable."""
        coords: List[List[float]] = [[origin_lat, origin_lon]]
        for e in edges:
            for pt in e.geometry:
                if coords[-1] != pt:
                    coords.append(pt)
        if coords[-1] != [dest_lat, dest_lon]:
            coords.append([dest_lat, dest_lon])
        return coords

    @staticmethod
    def compare_routes(
        origin_lat: float, origin_lon: float,
        dest_lat: float, dest_lon: float,
        user_id: str = "anon"
    ) -> Dict[str, Any]:
        """
        Hybrid routing:
        - OSRM for real road-following geometry and turn-by-turn steps
        - Internal RoadGraph Dijkstra for hazard/blocked risk scoring
        Both are blended per route in the response.
        """
        # ── Step 1: Fetch OSRM routes ──────────────────────────────────────
        osrm_data = _fetch_osrm_route(origin_lat, origin_lon, dest_lat, dest_lon, alternatives=True)

        # ── Step 2: Compute internal risk scores ───────────────────────────
        risk_scores = AgentOrchestrator._graph_risk_scores(
            origin_lat, origin_lon, dest_lat, dest_lon)

        routes_output = []

        if osrm_data and osrm_data.get("code") == "Ok":
            osrm_routes = osrm_data.get("routes", [])

            route_types = ["fastest", "risk_aware", "alternative"]
            route_labels = [
                "Direct / Standard Route",
                "MaleMitra Risk-Aware Detour",
                "Secondary Corridor Alternative",
            ]
            route_uncertainties = [
                "OSRM road routing with MaleMitra hazard scoring.",
                "Penalizes flooded segments & ripple congestion. Not a certified safe route.",
                "Alternative corridor via OSRM + MaleMitra risk model.",
            ]

            for i, osrm_route in enumerate(osrm_routes[:3]):
                r_type = route_types[i] if i < len(route_types) else f"route_{i}"
                r_label = route_labels[i] if i < len(route_labels) else f"Route {i+1}"
                r_uncertainty = route_uncertainties[i] if i < len(route_uncertainties) else ""

                # Decode real road geometry
                geom_encoded = osrm_route.get("geometry", "")
                coords = _decode_polyline6(geom_encoded) if geom_encoded else [
                    [origin_lat, origin_lon], [dest_lat, dest_lon]]

                # Real distance & duration from OSRM
                real_distance_m = osrm_route.get("distance", 0.0)
                real_duration_s = osrm_route.get("duration", 0.0)

                # Turn-by-turn steps from first leg
                osrm_steps = []
                legs = osrm_route.get("legs", [])
                if legs:
                    osrm_steps = _osrm_steps_to_directions(legs[0].get("steps", []))

                # Blend with graph risk scores
                graph_risk = risk_scores.get(r_type, risk_scores.get("fastest", {}))
                blocked_crossed = graph_risk.get("blocked_crossed", 0)
                hazard_penalty_s = graph_risk.get("hazard_penalty_s", 0.0)
                congestion_delay_s = graph_risk.get("congestion_delay_s", 0.0)
                risk_score = graph_risk.get("risk_score", 0.0)
                node_names = graph_risk.get("node_names", [])

                routes_output.append({
                    "type": r_type,
                    "label": r_label,
                    "coordinates": coords,
                    "node_names": node_names,
                    "osrm_steps": osrm_steps,
                    "estimated_duration_s": round(real_duration_s + hazard_penalty_s + congestion_delay_s, 1),
                    "base_duration_s": round(real_duration_s, 1),
                    "hazard_penalty_s": hazard_penalty_s,
                    "congestion_delay_s": congestion_delay_s,
                    "distance_m": round(real_distance_m, 1),
                    "blocked_edges_crossed": blocked_crossed,
                    "risk_score": risk_score,
                    "uncertainty": r_uncertainty,
                    "geometry_source": "osrm",
                })

        else:
            # ── OSRM unavailable: graceful fallback to graph straight-lines ──
            print("[OSRM] Unavailable, falling back to graph geometry.")
            start_node = road_graph.find_nearest_node(origin_lat, origin_lon)
            end_node = road_graph.find_nearest_node(dest_lat, dest_lon)
            if not start_node or not end_node or start_node == end_node:
                start_node, end_node = "N1", "N7"

            for mode, r_type, r_label, r_uncertainty in [
                ("fastest",    "fastest",    "Direct / Standard Route", "Graph fallback (OSRM unavailable)."),
                ("risk_aware", "risk_aware", "MaleMitra Risk-Aware Detour", "Graph fallback with hazard penalties."),
            ]:
                result = road_graph.compute_dijkstra(start_node, end_node, mode=mode)
                if not result:
                    continue
                nodes_fb, edges_fb, dur_fb = result
                coords_fb = AgentOrchestrator._fallback_coords(
                    origin_lat, origin_lon, dest_lat, dest_lon, edges_fb)
                graph_risk = risk_scores.get(r_type, {})
                routes_output.append({
                    "type": r_type,
                    "label": r_label,
                    "coordinates": coords_fb,
                    "node_names": [road_graph.nodes[n]["name"] for n in nodes_fb if n in road_graph.nodes],
                    "osrm_steps": [],
                    "estimated_duration_s": round(dur_fb, 1),
                    "base_duration_s": round(dur_fb, 1),
                    "hazard_penalty_s": graph_risk.get("hazard_penalty_s", 0.0),
                    "congestion_delay_s": graph_risk.get("congestion_delay_s", 0.0),
                    "distance_m": graph_risk.get("distance_m", 0.0),
                    "blocked_edges_crossed": graph_risk.get("blocked_crossed", 0),
                    "risk_score": graph_risk.get("risk_score", 0.0),
                    "uncertainty": r_uncertainty,
                    "geometry_source": "graph_fallback",
                })

        active_restrictions = sum(1 for e in road_graph.edges.values() if e.is_blocked)
        reported_hazards = sum(1 for e in road_graph.edges.values() if e.hazard_severity != "none" and not e.is_blocked)

        return {
            "graph_version": road_graph.graph_version,
            "data_mode": "hybrid_osrm_malemitra",
            "routes": routes_output,
            "active_restrictions_count": active_restrictions,
            "reported_hazards_count": reported_hazards,
            "message": "Routes calculated using real road geometry + MaleMitra hazard intelligence." if routes_output else "No feasible route found.",
        }


agent_orchestrator = AgentOrchestrator()
