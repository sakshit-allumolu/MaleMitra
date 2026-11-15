"""
Traffic-aware routing via the TomTom Routing API.

OSRM supplies the road geometry and turn-by-turn steps; TomTom supplies what OSRM cannot: the *live*
travel time on the same corridor. For each OSRM route we find the TomTom route that follows the same
roads and scale the OSRM duration by TomTom's live/free-flow ratio.

Disabled (no network calls) unless TOMTOM_API_KEY is set and TOMTOM_ROUTING_ENABLED=true. It is a metered
API, so: responses are cached briefly, a rolling 24h request budget is enforced across all workers via the
`rate_hits` table, and a circuit breaker stops hammering TomTom when it is failing. Any failure returns
None and the caller falls back to the time-of-day model. The API key is never logged.
"""
import json
import logging
import math
import threading
import time
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple

from backend.app.config import settings
from backend.app.models.database import get_db_connection

log = logging.getLogger("malemitra.tomtom_routing")

TOMTOM_ROUTING_URL = "https://api.tomtom.com/routing/1/calculateRoute"
BUDGET_BUCKET, BUDGET_KEY, BUDGET_WINDOW_S = "tomtom_routing", "global", 86400
MAX_ALTERNATIVES = 2
MAX_FACTOR = 4.0       # sanity clamp on live/free-flow
MATCH_RADIUS_M = 60.0  # an OSRM point "lies on" a TomTom route when it is this close to it
MATCH_MIN_SHARE = 0.6  # share of OSRM points that must lie on a TomTom route to call them the same route

# fetcher(url) -> parsed TomTom JSON or None. Injectable for tests.
Fetcher = Callable[[str], Optional[Dict]]

_cache: Dict[Tuple, Tuple[float, List[Dict]]] = {}
_lock = threading.Lock()
_CACHE_MAX = 256
_failures = 0
_open_until = 0.0
_BREAKER_THRESHOLD = 3
_BREAKER_COOLDOWN_S = 60


def enabled() -> bool:
    return bool(settings.TOMTOM_API_KEY) and settings.TOMTOM_ROUTING_ENABLED and settings.TOMTOM_ROUTING_DAILY_BUDGET > 0


def reset() -> None:
    global _failures, _open_until
    with _lock:
        _cache.clear()
        _failures = 0
        _open_until = 0.0


# ── budget ────────────────────────────────────────────────────────────────────

def budget_used() -> int:
    conn = get_db_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM rate_hits WHERE bucket = ? AND key = ? AND ts > ?",
                            (BUDGET_BUCKET, BUDGET_KEY, time.time() - BUDGET_WINDOW_S)).fetchone()[0]
    finally:
        conn.close()


def _take_budget() -> bool:
    """Atomically reserve one request from the rolling 24h budget. Fails closed: a metered API call is
    never made when the budget can't be checked."""
    now = time.time()
    try:
        conn = get_db_connection()
        try:
            conn.begin_write(f"rate:{BUDGET_BUCKET}:{BUDGET_KEY}")
            n = conn.execute("SELECT COUNT(*) FROM rate_hits WHERE bucket = ? AND key = ? AND ts > ?",
                             (BUDGET_BUCKET, BUDGET_KEY, now - BUDGET_WINDOW_S)).fetchone()[0]
            if n >= settings.TOMTOM_ROUTING_DAILY_BUDGET:
                conn.rollback()
                return False
            conn.execute("INSERT INTO rate_hits (bucket, key, ts) VALUES (?, ?, ?)", (BUDGET_BUCKET, BUDGET_KEY, now))
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception as e:
        log.warning("TomTom routing budget check failed, skipping call: %s", type(e).__name__)
        return False


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _http_get(url: str) -> Optional[Dict]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MaleMitra/1.0"})
        with urllib.request.urlopen(req, timeout=settings.TOMTOM_ROUTING_TIMEOUT_SECONDS) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        # Never log the URL or the exception text: the URL contains the API key.
        log.warning("[TomTomRouting] request failed: %s", type(e).__name__)
        return None


def _build_url(o_lat: float, o_lon: float, d_lat: float, d_lon: float) -> str:
    params = urllib.parse.urlencode({
        "key": settings.TOMTOM_API_KEY,
        "traffic": "true",
        "travelMode": "car",
        "routeType": "fastest",
        "computeTravelTimeFor": "all",  # adds noTrafficTravelTimeInSeconds next to the live figure
        "maxAlternatives": MAX_ALTERNATIVES,
    })
    return f"{TOMTOM_ROUTING_URL}/{o_lat:.6f},{o_lon:.6f}:{d_lat:.6f},{d_lon:.6f}/json?{params}"


def _parse(data: Optional[Dict]) -> List[Dict[str, Any]]:
    """TomTom response -> [{travel_s, no_traffic_s, delay_s, length_m, points[[lat,lon]]}], skipping malformed routes."""
    out: List[Dict[str, Any]] = []
    for r in (data or {}).get("routes", []) or []:
        try:
            s = r["summary"]
            travel = float(s["travelTimeInSeconds"])
            free = float(s.get("noTrafficTravelTimeInSeconds") or 0.0)
            if travel <= 0 or free <= 0:
                continue
            pts = [[p["latitude"], p["longitude"]] for leg in r.get("legs", []) for p in leg.get("points", [])]
            out.append({
                "travel_s": travel,
                "no_traffic_s": free,
                "delay_s": float(s.get("trafficDelayInSeconds") or max(0.0, travel - free)),
                "length_m": float(s.get("lengthInMeters") or 0.0),
                "points": pts,
            })
        except (KeyError, TypeError, ValueError):
            continue
    return out


def get_live_routes(o_lat: float, o_lon: float, d_lat: float, d_lon: float,
                    fetcher: Optional[Fetcher] = None) -> Optional[List[Dict[str, Any]]]:
    """Live-traffic routes between two points, or None when disabled / over budget / failing."""
    global _failures, _open_until
    if not enabled():
        return None
    ck = (round(o_lat, 4), round(o_lon, 4), round(d_lat, 4), round(d_lon, 4))
    now = time.monotonic()
    with _lock:
        hit = _cache.get(ck)
        if hit and hit[0] > now:
            return hit[1]
        if _open_until > now:
            return None
    if not _take_budget():
        log.warning("[TomTomRouting] daily budget (%s) exhausted - using time-of-day model",
                    settings.TOMTOM_ROUTING_DAILY_BUDGET)
        return None
    routes = _parse((fetcher or _http_get)(_build_url(o_lat, o_lon, d_lat, d_lon)))
    with _lock:
        if not routes:
            _failures += 1
            if _failures >= _BREAKER_THRESHOLD:
                _open_until = time.monotonic() + _BREAKER_COOLDOWN_S
                _failures = 0
                log.warning("[TomTomRouting] circuit open for %ss after repeated failures", _BREAKER_COOLDOWN_S)
            return None
        _failures = 0
        if len(_cache) >= _CACHE_MAX:
            _cache.clear()
        _cache[ck] = (time.monotonic() + settings.TOMTOM_ROUTING_CACHE_TTL_SECONDS, routes)
    return routes


# ── matching OSRM routes to TomTom routes ─────────────────────────────────────

def live_factor(route: Dict[str, Any]) -> float:
    """Live travel time / free-flow travel time, >= 1.0."""
    return min(MAX_FACTOR, max(1.0, route["travel_s"] / route["no_traffic_s"]))


def _near(p: List[float], pts: List[List[float]], radius_m: float) -> bool:
    cos_lat = math.cos(math.radians(p[0]))
    for q in pts:
        dy = (q[0] - p[0]) * 111_320.0
        if abs(dy) > radius_m:
            continue
        dx = (q[1] - p[1]) * 111_320.0 * cos_lat
        if dx * dx + dy * dy <= radius_m * radius_m:
            return True
    return False


def _overlap(coords: List[List[float]], pts: List[List[float]], samples: int = 40) -> float:
    if not coords or not pts:
        return 0.0
    step = max(1, len(coords) // samples)
    sampled = coords[::step]
    return sum(1 for c in sampled if _near(c, pts, MATCH_RADIUS_M)) / len(sampled)


def match_route(coords: List[List[float]], live_routes: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], bool]:
    """TomTom route that follows `coords` ([[lat, lon], ...]). Returns (route, exact). When none overlaps
    enough (e.g. a bypass detour TomTom wouldn't pick), falls back to TomTom's best route as a corridor-level
    estimate and reports exact=False."""
    best, best_share = live_routes[0], 0.0
    for r in live_routes:
        share = _overlap(coords, r["points"])
        if share > best_share:
            best, best_share = r, share
    if best_share >= MATCH_MIN_SHARE:
        return best, True
    return live_routes[0], False


def status() -> Dict[str, Any]:
    on = enabled()
    try:
        used = budget_used() if on else 0
    except Exception:
        used = -1
    return {
        "enabled": on,
        "key_configured": bool(settings.TOMTOM_API_KEY),
        "daily_budget": settings.TOMTOM_ROUTING_DAILY_BUDGET,
        "used_last_24h": used,
        "breaker_open": _open_until > time.monotonic(),
    }
