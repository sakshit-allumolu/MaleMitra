import logging
import json
import itertools
import math
import ssl
import threading
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from backend.app.config import in_graph_area, settings
from backend.app.models.database import get_db_connection
from backend.app.services.graph_service import road_graph, RoadEdge, haversine_distance
from backend.app.services import tomtom_routing_service

log = logging.getLogger("malemitra.agent")

# ── OSRM routing server ────────────────────────────────────────────────────────
# Driving profile, returns full geometry + turn-by-turn steps. The public demo server is for
# demos only (no SLA, usage policy); set OSRM_BASE_URL to a self-hosted OSRM in production.
OSRM_BASE = settings.OSRM_BASE_URL.rstrip("/")

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

def _live_traffic_label(factor: float) -> str:
    """Human label for a measured live/free-flow travel-time ratio."""
    if factor < 1.15:
        return "Live — free flow"
    if factor < 1.4:
        return "Live — light congestion"
    if factor < 1.8:
        return "Live — heavy congestion"
    return "Live — severe congestion"


def _geojson_coords_to_latlon(geojson_coords: List[List[float]]) -> List[List[float]]:
    """
    Converts GeoJSON coordinate pairs [[lon, lat], ...] to Leaflet [[lat, lon], ...].
    OSRM GeoJSON geometry uses [longitude, latitude] order per the GeoJSON spec.
    """
    return [[c[1], c[0]] for c in geojson_coords if len(c) >= 2]


def _make_ssl_ctx() -> "ssl.SSLContext":
    """TLS context for the routing server. Verified unless OSRM_VERIFY_TLS=false."""
    ctx = ssl.create_default_context()
    if not settings.OSRM_VERIFY_TLS:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


# Per-process response cache + circuit breaker. Routing is a best-effort enhancement: when the
# routing server is slow or down we fail fast and fall back to graph geometry instead of
# tying up request threads on 8s timeouts.
_osrm_cache: Dict[str, Tuple[float, Dict]] = {}
_osrm_lock = threading.Lock()
_osrm_failures = 0
_osrm_open_until = 0.0
_OSRM_CACHE_MAX = 512


def _osrm_reset() -> None:
    global _osrm_failures, _osrm_open_until
    with _osrm_lock:
        _osrm_cache.clear()
        _osrm_failures = 0
        _osrm_open_until = 0.0


def _osrm_request(url: str, timeout: Optional[float] = None) -> Optional[Dict]:
    """OSRM HTTP call with TTL cache, short timeout and a circuit breaker."""
    global _osrm_failures, _osrm_open_until
    if not settings.OSRM_ENABLED:
        return None
    now = time.monotonic()
    with _osrm_lock:
        hit = _osrm_cache.get(url)
        if hit and hit[0] > now:
            return hit[1]
        if _osrm_open_until > now:
            return None  # breaker open: skip the network entirely
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MaleMitra/1.0"})
        with urllib.request.urlopen(
            req, timeout=timeout or settings.OSRM_TIMEOUT_SECONDS, context=_make_ssl_ctx()
        ) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        with _osrm_lock:
            _osrm_failures += 1
            if _osrm_failures >= settings.OSRM_BREAKER_THRESHOLD:
                _osrm_open_until = time.monotonic() + settings.OSRM_BREAKER_COOLDOWN_SECONDS
                _osrm_failures = 0
                log.warning("[OSRM] circuit open for %ss after repeated failures (%s)",
                            settings.OSRM_BREAKER_COOLDOWN_SECONDS, e)
            else:
                log.warning("[OSRM] request failed: %s", e)
        return None
    with _osrm_lock:
        _osrm_failures = 0
        if data.get("code") == "Ok":
            if len(_osrm_cache) >= _OSRM_CACHE_MAX:
                _osrm_cache.clear()
            _osrm_cache[url] = (time.monotonic() + settings.OSRM_CACHE_TTL_SECONDS, data)
    return data


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
        log.warning(f"[Bypass] DB query failed: {e}")
        return []


# Open incidents nobody has closed the road for yet: citizen reports waiting for review, dispatch or field
# verification. Closing a road takes time, so routes steer around these as well (softer than a closure).
_REPORTED_STATUSES = ("reported", "under_review", "assigned", "field_verified", "clearance_proposed")


def _get_reported_incident_locations() -> List[Tuple[float, float]]:
    """Lat/lon of open incidents whose road is not (yet) closed."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        marks = ",".join("?" * len(_REPORTED_STATUSES))
        cursor.execute(f"SELECT lat, lon FROM incidents WHERE status IN ({marks}) AND is_blocked = 0",
                       _REPORTED_STATUSES)
        rows = cursor.fetchall()
        conn.close()
        return [(float(r["lat"]), float(r["lon"])) for r in rows]
    except Exception as e:
        log.warning(f"[Bypass] DB query failed: {e}")
        return []


_CLEARANCE_M = 60.0      # a route "passes" an incident when it comes this close
_ENDPOINT_SKIP_M = 150.0  # an incident at the start or destination itself cannot be avoided
_DISTINCT_M = 150.0      # two routes count as different when this much of one is off the other


def _incidents_near_trip(o_lat: float, o_lon: float, d_lat: float, d_lon: float
                         ) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
    """(closed, reported) incident points that matter for this trip."""
    straight = haversine_distance(o_lat, o_lon, d_lat, d_lon)
    limit = straight * 1.5 + 600

    def relevant(pts):
        return [(la, lo) for la, lo in pts
                if haversine_distance(o_lat, o_lon, la, lo) + haversine_distance(d_lat, d_lon, la, lo) <= limit
                and haversine_distance(o_lat, o_lon, la, lo) > _ENDPOINT_SKIP_M
                and haversine_distance(d_lat, d_lon, la, lo) > _ENDPOINT_SKIP_M]

    return relevant(_get_blocked_incident_locations()), relevant(_get_reported_incident_locations())


def _path_xy(route: Dict, lat0: float) -> List[Tuple[float, float]]:
    kx = 111_000.0 * math.cos(math.radians(lat0))
    return [(lon * kx, lat * 111_000.0) for lon, lat in route.get("geometry", {}).get("coordinates", [])]


def _dist_to_path_m(px: float, py: float, path: List[Tuple[float, float]]) -> float:
    best = float("inf")
    for (x1, y1), (x2, y2) in zip(path, path[1:] or path):
        dx, dy = x2 - x1, y2 - y1
        seg = dx * dx + dy * dy
        t = 0.0 if seg == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / seg))
        best = min(best, math.hypot(x1 + t * dx - px, y1 + t * dy - py))
    return best


def _clearance_m(route: Dict, locs: List[Tuple[float, float]]) -> float:
    """Smallest distance (m) from any of the points to an OSRM route's geometry."""
    best = float("inf")
    for blat, blon in locs:
        path = _path_xy(route, blat)
        best = min(best, _dist_to_path_m(blon * 111_000.0 * math.cos(math.radians(blat)), blat * 111_000.0, path))
    return best


def _hits(route: Dict, locs: List[Tuple[float, float]]) -> int:
    """How many of the points the route passes within _CLEARANCE_M."""
    return sum(1 for p in locs if _clearance_m(route, [p]) < _CLEARANCE_M)


def _unique_length_m(route: Dict, other: Dict) -> float:
    """Length (m) of `route` that is more than _CLEARANCE_M away from `other` (0 = same road)."""
    pts = route.get("geometry", {}).get("coordinates", [])
    if len(pts) < 2:
        return 0.0
    lat0 = pts[0][1]
    a, b = _path_xy(route, lat0), _path_xy(other, lat0)
    if not b:
        return 0.0
    step = max(1, len(a) // 120)
    total = 0.0
    for i in range(0, len(a) - step, step):
        (x1, y1), (x2, y2) = a[i], a[i + step]
        if _dist_to_path_m((x1 + x2) / 2, (y1 + y2) / 2, b) > _CLEARANCE_M:
            total += math.hypot(x2 - x1, y2 - y1)
    return total


_MAX_DETOUR_FACTOR = 1.8  # a detour longer than this many times the direct route is not worth offering
_MAX_DETOUR_QUERIES = 24  # cap on forced via-point OSRM calls per trip


def _detour_routes(
    direct: Dict, osrm_alts: List[Dict], o_lat: float, o_lon: float, d_lat: float, d_lon: float,
    closed: List[Tuple[float, float]], reported: List[Tuple[float, float]],
    direct_closed: bool, direct_reported: bool,
) -> Dict[str, Optional[Dict]]:
    """
    Detours for a direct route that runs into a closed road and/or a reported incident. Nothing is built (and
    OSRM is not called) when the direct route is clean.

      "safe"        shortest route that stays _CLEARANCE_M clear of every closed road AND every reported incident;
      "closed_only" shortest route that avoids the closed roads but still passes a reported incident. Only
                    returned when the direct route meets both kinds (a middle option), or when no safe route exists.

    A route within _CLEARANCE_M of a closed road is never returned. Candidates are OSRM's own alternatives plus
    routes forced through via-points beside each incident the direct route meets (300 m to 1.5 km, either side).
    """
    out: Dict[str, Optional[Dict]] = {"safe": None, "closed_only": None}
    if not (direct_closed or direct_reported):
        return out
    direct_len = direct.get("distance", 0.0) or 1.0
    pool: List[Dict] = []

    def add(route: Dict) -> None:
        if closed and _clearance_m(route, closed) < _CLEARANCE_M:
            return
        if route.get("distance", 0.0) > _MAX_DETOUR_FACTOR * direct_len:
            return
        if _unique_length_m(route, direct) < _DISTINCT_M:
            return  # same road as the direct route
        if any(_unique_length_m(route, q) < _DISTINCT_M and _unique_length_m(q, route) < _DISTINCT_M for q in pool):
            return
        pool.append(route)

    def classify() -> None:
        clean = [r for r in pool if not reported or _clearance_m(r, reported) >= _CLEARANCE_M]
        rest = [r for r in pool if r not in clean]
        out["safe"] = min(clean, key=lambda r: r.get("distance", 0.0)) if clean else None
        want_closed_only = direct_closed and (direct_reported or out["safe"] is None)
        out["closed_only"] = min(rest, key=lambda r: r.get("distance", 0.0)) if rest and want_closed_only else None

    def done() -> bool:
        return out["safe"] is not None and (not (direct_closed and direct_reported) or out["closed_only"] is not None)

    for r in osrm_alts:
        add(r)
    classify()

    ky = 111_000.0
    kx = 111_000.0 * math.cos(math.radians(o_lat))
    ex, ny = (d_lon - o_lon) * kx, (d_lat - o_lat) * ky
    norm = math.hypot(ex, ny)
    if not done() and norm >= 1.0:
        perp_e, perp_n = -ny / norm, ex / norm
        meets = sorted((p for p in closed + reported if _clearance_m(direct, [p]) < _CLEARANCE_M),
                       key=lambda p: haversine_distance(o_lat, o_lon, p[0], p[1]))
        meets = meets[:3]
        # Same-side combinations first, then mixed ones (a closure and a report can need opposite sides).
        sides = sorted(itertools.product((1, -1), repeat=len(meets)), key=lambda c: len(set(c)))
        budget = _MAX_DETOUR_QUERIES
        for offset in (300.0, 600.0, 1000.0, 1500.0):
            for combo in sides:
                if budget <= 0:
                    return out
                budget -= 1
                vias = [(lo + sd * offset * perp_e / kx, la + sd * offset * perp_n / ky)
                        for (la, lo), sd in zip(meets, combo)]
                data = _fetch_osrm_route_waypoints([(o_lon, o_lat)] + vias + [(d_lon, d_lat)])
                if data and data.get("code") == "Ok" and data.get("routes"):
                    add(data["routes"][0])
                classify()
                if done():
                    return out
    return out


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
                "decision": r["decision"],
                "decided_at": r["decided_at"],
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
        # The graph covers a few neighbourhoods. For trips that start or end elsewhere in the city it would attach
        # unrelated junction names and penalties to the route, so those trips use OSRM + live traffic only.
        if not (in_graph_area(origin_lat, origin_lon) and in_graph_area(dest_lat, dest_lon)):
            return {}
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
                "node_ids": nodes_f,
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
                "node_ids": nodes_r,
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

        # ── Step 2: Routes around incidents ────────────────────────────────
        # Cards: the direct route always; plus detours only when the direct route runs into something.
        #   closed roads only   -> direct + a detour around the closed roads
        #   reported only       -> direct + a recommended route that clears every reported incident
        #   both                -> direct + closed-roads-only detour + recommended route that clears both
        # Nothing on the path -> the direct route alone (no filler "backup" routes).
        closed_pts: List[Tuple[float, float]] = []
        reported_pts: List[Tuple[float, float]] = []
        direct_closed = direct_reported = False
        detours: Dict[str, Optional[Dict]] = {"safe": None, "closed_only": None}
        if osrm_data and osrm_data.get("code") == "Ok" and osrm_data.get("routes"):
            direct_osrm = osrm_data["routes"][0]
            closed_pts, reported_pts = _incidents_near_trip(origin_lat, origin_lon, dest_lat, dest_lon)
            direct_closed = bool(closed_pts) and _clearance_m(direct_osrm, closed_pts) < _CLEARANCE_M
            direct_reported = bool(reported_pts) and _clearance_m(direct_osrm, reported_pts) < _CLEARANCE_M
            detours = _detour_routes(
                direct_osrm, osrm_data["routes"][1:], origin_lat, origin_lon, dest_lat, dest_lon,
                closed_pts, reported_pts, direct_closed, direct_reported)

        # ── Step 3: Compute internal risk scores ───────────────────────────
        risk_scores = AgentOrchestrator._graph_risk_scores(
            origin_lat, origin_lon, dest_lat, dest_lon)

        # ── Step 4: Traffic factor ─────────────────────────────────────────
        # Preferred: TomTom live-traffic ETA (real, per-route). Fallback: Bengaluru time-of-day profile.
        tod_factor, tod_label = _get_traffic_factor()
        live_routes = tomtom_routing_service.get_live_routes(origin_lat, origin_lon, dest_lat, dest_lon)
        if live_routes:
            traffic_factor = round(tomtom_routing_service.live_factor(live_routes[0]), 3)
            traffic_label = _live_traffic_label(traffic_factor)
            traffic_source = "tomtom_live"
        else:
            traffic_factor, traffic_label = tod_factor, tod_label
            traffic_source = "time_of_day_model"

        routes_output = []

        if osrm_data and osrm_data.get("code") == "Ok":
            direct_label = "Direct Route"
            direct_note = "OSRM road routing + live traffic scaling + MaleMitra incident scoring."
            if (direct_closed or direct_reported) and detours["safe"] is None:
                what = "the closed roads and reported incidents" if direct_closed and direct_reported else (
                    "the closed road" if direct_closed else "the reported incidents")
                direct_note = f"No route that stays clear of {what} could be found, so none is recommended."
            # (type, label, osrm route, uncertainty, recommended)
            cards = [("fastest", direct_label, osrm_data["routes"][0], direct_note, False)]
            if detours["safe"]:
                if direct_closed and direct_reported:
                    note = "Avoids the closed roads and every reported incident. Reports are unverified and may not be real."
                elif direct_closed:
                    note = "Avoids the closed road(s) on the direct route."
                else:
                    note = "Avoids the reported incidents on the direct route. Reports are unverified and may not be real."
                cards.append(("risk_aware", "Recommended Detour", detours["safe"], note, True))
            if detours["closed_only"]:
                cards.append(("alternative", "Avoids Closed Roads Only", detours["closed_only"],
                              "Avoids the closed roads but may pass reported incidents, which are unverified.", False))

            for r_type, r_label, active_route, r_uncertainty, r_recommended in cards:
                # Extract real road geometry from GeoJSON
                geom = active_route.get("geometry", {})
                raw_coords = geom.get("coordinates", []) if isinstance(geom, dict) else []
                coords = _geojson_coords_to_latlon(raw_coords) if raw_coords else [
                    [origin_lat, origin_lon], [dest_lat, dest_lon]]

                # Real distance from OSRM; base duration scaled by the traffic factor. With TomTom, the
                # factor comes from the TomTom route that follows this same road (else its best route).
                route_factor, route_source = traffic_factor, traffic_source
                if live_routes:
                    matched, exact = tomtom_routing_service.match_route(coords, live_routes)
                    route_factor = round(tomtom_routing_service.live_factor(matched), 3)
                    route_source = "tomtom_live" if exact else "tomtom_corridor"
                real_distance_m = active_route.get("distance", 0.0)
                osrm_duration_s = active_route.get("duration", 0.0)
                traffic_delay_s = round(osrm_duration_s * (route_factor - 1.0), 1)
                traffic_adjusted_s = round(osrm_duration_s * route_factor, 1)

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
                    "traffic_factor": route_factor,
                    "traffic_source": route_source,
                    "hazard_penalty_s": hazard_penalty_s,
                    "congestion_delay_s": congestion_delay_s,
                    "distance_m": round(real_distance_m, 1),
                    "blocked_edges_crossed": blocked_crossed,
                    "risk_score": risk_score,
                    "uncertainty": r_uncertainty,
                    "geometry_source": "osrm",
                    "closed_incidents_passed": _hits(active_route, closed_pts) if closed_pts else 0,
                    "reported_incidents_passed": _hits(active_route, reported_pts) if reported_pts else 0,
                    "recommended": r_recommended,
                })

        else:
            # ── OSRM unavailable: graceful fallback to graph straight-lines ──
            log.warning("[OSRM] Unavailable, falling back to graph geometry.")
            start_node = road_graph.find_nearest_node(origin_lat, origin_lon)
            end_node = road_graph.find_nearest_node(dest_lat, dest_lon)
            if not start_node or not end_node or start_node == end_node:
                start_node, end_node = "N1", "N7"

            for mode, r_type, r_label, r_uncertainty in [
                ("fastest",    "fastest",    "Direct Route", "Graph fallback (OSRM unavailable) + live traffic."),
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
                    "traffic_source": traffic_source,
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
            "traffic_source": traffic_source,
            "message": (
                f"Routes calculated with {'live traffic' if traffic_source == 'tomtom_live' else 'typical-hours traffic model'} "
                f"({traffic_label}, ×{traffic_factor}) + MaleMitra incident intelligence."
            ) if routes_output else "No feasible route found.",
        }


agent_orchestrator = AgentOrchestrator()
