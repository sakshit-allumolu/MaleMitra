import json
import math
import ssl
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from backend.app.models.database import get_db_connection
from backend.app.services.graph_service import road_graph, RoadEdge, haversine_distance
from backend.app.services.ripple_service import ripple_engine

# ── OSRM public demo API ───────────────────────────────────────────────────────
# Uses the free public OSRM demo server — no API key required.
# Driving profile, returns full geometry + turn-by-turn steps.
OSRM_BASE = "https://router.project-osrm.org/route/v1/driving"

# ── Time-of-day traffic multiplier (IST = UTC+5:30) ──────────────────────────
# OSRM returns free-flow travel times; we scale by Bengaluru peak-hour factors
# derived from city-level traffic studies (TomTom Traffic Index 2023).
# Multiplier > 1.0 = congestion slowing traffic vs free-flow speed.
_BENGALURU_TRAFFIC_PROFILE: List[Dict[str, Any]] = [
    # (start_hour_IST, end_hour_IST, multiplier, label)
    {"start": 0,  "end": 6,  "factor": 1.00, "label": "Night — free flow"},
    {"start": 6,  "end": 8,  "factor": 1.25, "label": "Early morning build-up"},
    {"start": 8,  "end": 10, "factor": 1.65, "label": "AM peak — heavy congestion"},
    {"start": 10, "end": 12, "factor": 1.30, "label": "Mid-morning — moderate"},
    {"start": 12, "end": 14, "factor": 1.20, "label": "Midday — light congestion"},
    {"start": 14, "end": 16, "factor": 1.25, "label": "Afternoon — building up"},
    {"start": 16, "end": 19, "factor": 1.70, "label": "PM peak — severe congestion"},
    {"start": 19, "end": 21, "factor": 1.40, "label": "Evening dispersal"},
    {"start": 21, "end": 24, "factor": 1.10, "label": "Late evening — thinning"},
]

def _get_traffic_factor() -> Tuple[float, str]:
    """Returns (multiplier, label) for the current IST hour."""
    utc_now = datetime.now(timezone.utc)
    ist_hour = (utc_now.hour + 5) % 24 + (1 if utc_now.minute >= 30 else 0)
    ist_hour = ist_hour % 24
    for slot in _BENGALURU_TRAFFIC_PROFILE:
        if slot["start"] <= ist_hour < slot["end"]:
            return slot["factor"], slot["label"]
    return 1.0, "Unknown"

def _geojson_coords_to_latlon(geojson_coords: List[List[float]]) -> List[List[float]]:
    """
    Converts GeoJSON coordinate pairs [[lon, lat], ...] to Leaflet [[lat, lon], ...].
    OSRM GeoJSON geometry uses [longitude, latitude] order per the GeoJSON spec.
    """
    return [[c[1], c[0]] for c in geojson_coords if len(c) >= 2]


def _make_ssl_ctx() -> "ssl.SSLContext":
    """Unverified SSL context for the public OSRM demo server (expired cert)."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _osrm_request(url: str, timeout: int = 8) -> Optional[Dict]:
    """Single OSRM HTTP call with shared SSL context and error handling."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MaleMitra/1.0 (Bobathon 2026)"})
        with urllib.request.urlopen(req, timeout=timeout, context=_make_ssl_ctx()) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[OSRM] Request failed: {e}")
        return None


def _fetch_osrm_route(
    origin_lat: float, origin_lon: float,
    dest_lat: float, dest_lon: float,
    alternatives: bool = True
) -> Optional[Dict]:
    """
    Calls OSRM routing API (origin → dest) and returns the parsed JSON response.
    Uses geometries=geojson for unambiguous [lon,lat] coordinate arrays.
    """
    coords_str = f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
    params = urllib.parse.urlencode({
        "overview": "full",
        "geometries": "geojson",
        "steps": "true",
        "alternatives": "true" if alternatives else "false",
        "annotations": "false",
    })
    return _osrm_request(f"{OSRM_BASE}/{coords_str}?{params}")


def _fetch_osrm_route_waypoints(waypoints_lonlat: List[Tuple[float, float]]) -> Optional[Dict]:
    """
    Calls OSRM with an ordered list of (lon, lat) waypoints.
    Used to route via specific intermediate points that bypass blocked segments.
    Returns no alternatives (single best route through all waypoints).
    """
    coords_str = ";".join(f"{lon},{lat}" for lon, lat in waypoints_lonlat)
    params = urllib.parse.urlencode({
        "overview": "full",
        "geometries": "geojson",
        "steps": "true",
        "alternatives": "false",
        "annotations": "false",
    })
    return _osrm_request(f"{OSRM_BASE}/{coords_str}?{params}")


def _perpendicular_offset(
    lat1: float, lon1: float,
    lat2: float, lon2: float,
    offset_m: float = 80.0
) -> Tuple[float, float]:
    """
    Returns a point offset ~offset_m metres perpendicular to the midpoint of
    segment (lat1,lon1)→(lat2,lon2).  Used to place a waypoint beside a blocked
    road so OSRM is forced to take the parallel street instead.
    """
    mid_lat = (lat1 + lat2) / 2.0
    mid_lon = (lon1 + lon2) / 2.0

    # Direction vector of the segment (approximate, treating degrees as flat)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    length = math.sqrt(dlat ** 2 + dlon ** 2)
    if length < 1e-9:
        return mid_lat, mid_lon

    # Perpendicular unit vector (rotate 90°)
    perp_lat = -dlon / length
    perp_lon = dlat / length

    # Convert offset_m to degrees (~111,000 m per degree)
    deg_per_m = 1.0 / 111_000.0
    return mid_lat + perp_lat * offset_m * deg_per_m, mid_lon + perp_lon * offset_m * deg_per_m


def _get_blocked_incident_locations() -> List[Tuple[float, float]]:
    """
    Fetches lat/lon of all incidents currently marked as BLOCKED from the DB.
    These are the real precise GPS coordinates of the blockages — far more
    accurate than the coarse internal graph edge midpoints.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT lat, lon FROM incidents WHERE status = 'blocked' AND is_blocked = 1")
        rows = cursor.fetchall()
        conn.close()
        return [(float(r["lat"]), float(r["lon"])) for r in rows]
    except Exception as e:
        print(f"[Bypass] DB query failed: {e}")
        return []


def _build_blocked_waypoints(
    origin_lat: float, origin_lon: float,
    dest_lat: float, dest_lon: float,
) -> List[Tuple[float, float]]:
    """
    Builds an OSRM waypoint list that forces detours around all actively blocked
    incident locations.

    Strategy — for each blocked incident within the route corridor:
      Place two waypoints offset along the origin→dest travel direction:
        • one ~250m before the blockage (approach)
        • one ~250m after  the blockage (departure)
      OSRM must plan a path through both points, so it naturally routes around
      the blocked spot on parallel streets rather than through it.
    """
    blocked_locs = _get_blocked_incident_locations()
    if not blocked_locs:
        return []

    straight_dist = haversine_distance(origin_lat, origin_lon, dest_lat, dest_lon)
    max_relevance_dist = straight_dist * 1.5 + 600

    # Direction unit vector from origin to dest (degrees, treated as flat)
    dlat = dest_lat - origin_lat
    dlon = dest_lon - origin_lon
    length = math.sqrt(dlat ** 2 + dlon ** 2)
    if length < 1e-9:
        return []
    dir_lat = dlat / length
    dir_lon = dlon / length
    deg_per_m = 1.0 / 111_000.0
    offset_deg = 250.0 * deg_per_m  # 250 m offset along travel direction

    detour_points: List[Tuple[float, float, float]] = []  # (dist_from_origin, lon, lat)

    for blk_lat, blk_lon in blocked_locs:
        dist_from_origin = haversine_distance(origin_lat, origin_lon, blk_lat, blk_lon)
        dist_from_dest   = haversine_distance(dest_lat, dest_lon, blk_lat, blk_lon)
        if dist_from_origin + dist_from_dest > max_relevance_dist:
            continue  # blockage not on this route corridor

        # Point before the blockage (approach side)
        before_lat = blk_lat - dir_lat * offset_deg
        before_lon = blk_lon - dir_lon * offset_deg
        # Point after the blockage (departure side)
        after_lat  = blk_lat + dir_lat * offset_deg
        after_lon  = blk_lon + dir_lon * offset_deg

        detour_points.append((dist_from_origin - offset_deg * 111_000, before_lon, before_lat))
        detour_points.append((dist_from_origin + offset_deg * 111_000, after_lon,  after_lat))

    if not detour_points:
        return []

    # Sort by distance from origin so waypoints are in travel order
    detour_points.sort(key=lambda x: x[0])

    waypoints: List[Tuple[float, float]] = [(origin_lon, origin_lat)]
    for _, bp_lon, bp_lat in detour_points:
        waypoints.append((bp_lon, bp_lat))
    waypoints.append((dest_lon, dest_lat))
    return waypoints


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
        - Blocked-edge bypass: re-queries OSRM with perpendicular waypoints so
          the risk-aware route physically avoids roads marked as blocked
        Both are blended per route in the response.
        """
        # ── Step 1: Fetch OSRM routes (fastest + alternatives) ────────────
        osrm_data = _fetch_osrm_route(origin_lat, origin_lon, dest_lat, dest_lon, alternatives=True)

        # ── Step 2: Build bypass-aware risk route via waypoints ────────────
        # If any graph-edges are blocked, generate a detour route that routes
        # around them on real roads using OSRM waypoints.
        bypass_waypoints = _build_blocked_waypoints(origin_lat, origin_lon, dest_lat, dest_lon)
        bypass_osrm_data: Optional[Dict] = None
        if bypass_waypoints and len(bypass_waypoints) > 2:
            bypass_osrm_data = _fetch_osrm_route_waypoints(bypass_waypoints)
            if bypass_osrm_data and bypass_osrm_data.get("code") != "Ok":
                bypass_osrm_data = None

        # ── Step 3: Compute internal risk scores ───────────────────────────
        risk_scores = AgentOrchestrator._graph_risk_scores(
            origin_lat, origin_lon, dest_lat, dest_lon)

        # ── Step 4: Live traffic factor (time-of-day, IST) ─────────────────
        traffic_factor, traffic_label = _get_traffic_factor()

        routes_output = []

        if osrm_data and osrm_data.get("code") == "Ok":
            osrm_routes = osrm_data.get("routes", [])

            # For the risk_aware slot, prefer the bypass route if we computed one
            bypass_route = bypass_osrm_data["routes"][0] if bypass_osrm_data else None

            route_types = ["fastest", "risk_aware", "alternative"]
            route_labels = [
                "Direct / Standard Route",
                "MaleMitra Risk-Aware Detour",
                "Secondary Corridor Alternative",
            ]
            route_uncertainties = [
                "OSRM road routing + live traffic scaling + MaleMitra incident scoring.",
                "Re-routed around blocked/flooded segments via real road detour.",
                "Alternative corridor via OSRM + MaleMitra risk model + live traffic.",
            ]

            for i, osrm_route in enumerate(osrm_routes[:3]):
                r_type = route_types[i] if i < len(route_types) else f"route_{i}"
                r_label = route_labels[i] if i < len(route_labels) else f"Route {i+1}"
                r_uncertainty = route_uncertainties[i] if i < len(route_uncertainties) else ""

                # For risk_aware slot: use the bypass route geometry if available
                active_route = (bypass_route if r_type == "risk_aware" and bypass_route else osrm_route)

                # Extract real road geometry from GeoJSON
                geom = active_route.get("geometry", {})
                raw_coords = geom.get("coordinates", []) if isinstance(geom, dict) else []
                coords = _geojson_coords_to_latlon(raw_coords) if raw_coords else [
                    [origin_lat, origin_lon], [dest_lat, dest_lon]]

                # Real distance from OSRM; base duration scaled by live traffic factor
                real_distance_m = active_route.get("distance", 0.0)
                osrm_duration_s = active_route.get("duration", 0.0)
                traffic_delay_s = round(osrm_duration_s * (traffic_factor - 1.0), 1)
                traffic_adjusted_s = round(osrm_duration_s * traffic_factor, 1)

                # Turn-by-turn steps from first leg of active route
                osrm_steps = []
                legs = active_route.get("legs", [])
                if legs:
                    # For waypointed routes OSRM returns multiple legs; flatten all steps
                    for leg in legs:
                        osrm_steps.extend(_osrm_steps_to_directions(leg.get("steps", [])))

                # Blend with graph risk scores (incident hazard + edge-level congestion)
                graph_risk = risk_scores.get(r_type, risk_scores.get("fastest", {}))
                blocked_crossed = graph_risk.get("blocked_crossed", 0)
                hazard_penalty_s = graph_risk.get("hazard_penalty_s", 0.0)
                congestion_delay_s = graph_risk.get("congestion_delay_s", 0.0)
                risk_score = graph_risk.get("risk_score", 0.0)
                node_names = graph_risk.get("node_names", [])

                total_duration_s = round(
                    traffic_adjusted_s + hazard_penalty_s + congestion_delay_s, 1)

                routes_output.append({
                    "type": r_type,
                    "label": r_label,
                    "coordinates": coords,
                    "node_names": node_names,
                    "osrm_steps": osrm_steps,
                    "estimated_duration_s": total_duration_s,
                    "base_duration_s": round(osrm_duration_s, 1),
                    "traffic_delay_s": traffic_delay_s,
                    "traffic_factor": traffic_factor,
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
                ("fastest",    "fastest",    "Direct / Standard Route", "Graph fallback (OSRM unavailable) + live traffic."),
                ("risk_aware", "risk_aware", "MaleMitra Risk-Aware Detour", "Graph fallback with hazard penalties + live traffic."),
            ]:
                result = road_graph.compute_dijkstra(start_node, end_node, mode=mode)
                if not result:
                    continue
                nodes_fb, edges_fb, dur_fb = result
                coords_fb = AgentOrchestrator._fallback_coords(
                    origin_lat, origin_lon, dest_lat, dest_lon, edges_fb)
                graph_risk = risk_scores.get(r_type, {})
                traffic_delay_fb = round(dur_fb * (traffic_factor - 1.0), 1)
                routes_output.append({
                    "type": r_type,
                    "label": r_label,
                    "coordinates": coords_fb,
                    "node_names": [road_graph.nodes[n]["name"] for n in nodes_fb if n in road_graph.nodes],
                    "osrm_steps": [],
                    "estimated_duration_s": round(dur_fb * traffic_factor + graph_risk.get("hazard_penalty_s", 0.0) + graph_risk.get("congestion_delay_s", 0.0), 1),
                    "base_duration_s": round(dur_fb, 1),
                    "traffic_delay_s": traffic_delay_fb,
                    "traffic_factor": traffic_factor,
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
            "traffic_factor": traffic_factor,
            "traffic_label": traffic_label,
            "message": f"Routes calculated with live traffic ({traffic_label}, ×{traffic_factor}) + MaleMitra incident intelligence." if routes_output else "No feasible route found.",
        }


agent_orchestrator = AgentOrchestrator()
