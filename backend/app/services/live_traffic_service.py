"""
Live traffic ingestion (Priority 2).

Polls TomTom Traffic Flow Segment Data for each road in the graph, converts the
observed speed ratio into a volume/capacity estimate by inverting the BPR curve,
and stores it on the edge (`live_vc`). `RoadGraph.get_edge_weight` then prefers
that fresh value over the synthetic ripple flow.

    ratio = current_speed / free_flow_speed = 1 / (1 + alpha * vc^beta)
    =>  vc = ((1/ratio - 1) / alpha) ** (1/beta)

Disabled (no network calls) unless TOMTOM_API_KEY is set.
"""
import json
import logging
import threading
import time
import urllib.parse
import urllib.request
from typing import Callable, Dict, List, Optional, Tuple

from backend.app import shared
from backend.app.config import settings
from backend.app.services.graph_service import RoadGraph, road_graph

log = logging.getLogger("malemitra.live_traffic")

TOMTOM_FLOW_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"

# fetcher(lat, lon) -> flowSegmentData dict or None
Fetcher = Callable[[float, float], Optional[Dict]]


def speed_ratio_to_vc(ratio: float) -> float:
    """Invert the BPR delay function: observed speed ratio -> volume/capacity."""
    if ratio >= 1.0:
        return 0.0
    ratio = max(ratio, 1e-3)
    vc = ((1.0 / ratio - 1.0) / settings.BPR_ALPHA) ** (1.0 / settings.BPR_BETA)
    return min(vc, settings.LIVE_TRAFFIC_MAX_VC)


def fetch_tomtom_segment(lat: float, lon: float, timeout: int = 8) -> Optional[Dict]:
    params = urllib.parse.urlencode({"key": settings.TOMTOM_API_KEY, "point": f"{lat},{lon}"})
    try:
        req = urllib.request.Request(f"{TOMTOM_FLOW_URL}?{params}", headers={"User-Agent": "MaleMitra/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8")).get("flowSegmentData")
    except Exception as e:
        # Never log the URL: it contains the API key.
        log.warning(f"[LiveTraffic] TomTom request failed: {type(e).__name__}")
        return None


class LiveTrafficService:
    def __init__(self, graph: RoadGraph):
        self.graph = graph
        self.last_poll_at: Optional[float] = None
        self.last_poll_updated: int = 0
        self.last_poll_requested: int = 0
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    @property
    def enabled(self) -> bool:
        return bool(settings.TOMTOM_API_KEY)

    def _query_points(self) -> List[Tuple[Tuple[float, float], List[str]]]:
        """One query point per physical road (both directions share a TomTom segment)."""
        groups: Dict[frozenset, List[str]] = {}
        for edge in self.graph.edges.values():
            groups.setdefault(frozenset((edge.u, edge.v)), []).append(edge.edge_id)
        points = []
        for edge_ids in groups.values():
            (lat1, lon1), (lat2, lon2) = [tuple(p) for p in self.graph.edges[edge_ids[0]].geometry[:2]]
            points.append((((lat1 + lat2) / 2.0, (lon1 + lon2) / 2.0), edge_ids))
        return points

    def effective_interval_s(self) -> int:
        """Poll interval, stretched if needed so the daily request budget is never exceeded."""
        n = max(1, len(self._query_points()))
        min_for_budget = int(86400 * n / max(1, settings.LIVE_TRAFFIC_DAILY_REQUEST_BUDGET)) + 1
        return max(settings.LIVE_TRAFFIC_POLL_SECONDS, min_for_budget)

    def poll_once(self, fetcher: Optional[Fetcher] = None) -> int:
        """Fetch live flow for every road and update edges. Returns number of edges updated."""
        fetch = fetcher or fetch_tomtom_segment
        now = time.time()
        updated = 0
        requested = 0
        for (lat, lon), edge_ids in self._query_points():
            requested += 1
            seg = fetch(lat, lon)
            if not seg:
                continue
            free = float(seg.get("freeFlowSpeed") or 0.0)
            cur = float(seg.get("currentSpeed") or 0.0)
            if free <= 0 or float(seg.get("confidence", 1.0)) < settings.LIVE_TRAFFIC_MIN_CONFIDENCE:
                continue
            ratio = min(1.0, cur / free)
            vc = settings.LIVE_TRAFFIC_MAX_VC if seg.get("roadClosure") else speed_ratio_to_vc(ratio)
            for e_id in edge_ids:
                edge = self.graph.edges[e_id]
                edge.live_vc = vc
                edge.live_speed_ratio = ratio
                edge.live_updated_at = now
                updated += 1
        self.last_poll_at = now
        self.last_poll_updated = updated
        self.last_poll_requested = requested
        if updated:
            # Notify SSE clients / invalidate cached routes.
            self.graph.graph_version += 1
            self._publish()
        return updated

    def _publish(self) -> None:
        """Share the readings so workers that are not polling see them too."""
        readings = {e.edge_id: [e.live_vc, e.live_speed_ratio, e.live_updated_at]
                    for e in self.graph.edges.values() if e.live_vc is not None}
        try:
            shared.put(shared.LIVE, readings)
        except Exception as e:
            log.warning("[LiveTraffic] could not share readings: %s", e)

    def load_shared(self) -> None:
        """Apply readings fetched by whichever worker currently holds the polling lease."""
        readings = shared.get(shared.LIVE) or {}
        with self.graph.lock:
            for e_id, (vc, ratio, ts) in readings.items():
                edge = self.graph.edges.get(e_id)
                if edge is not None:
                    edge.live_vc, edge.live_speed_ratio, edge.live_updated_at = vc, ratio, ts

    LEASE_NAME = "live-traffic"
    TICK_S = 30

    def _loop(self):
        # Only one worker/replica may poll TomTom (it is a paid, rate-limited API). The lease is renewed
        # every tick and expires if the holder dies, so another worker takes over within ~2 ticks.
        last_poll = 0.0
        while not self._stop.is_set():
            interval = self.effective_interval_s()
            try:
                if shared.acquire_lease(self.LEASE_NAME, ttl_s=self.TICK_S * 3):
                    if time.time() - last_poll >= interval:
                        self.poll_once()
                        last_poll = time.time()
                else:
                    last_poll = 0.0  # lost/never had it: poll immediately if we take over
            except Exception as e:
                log.warning(f"[LiveTraffic] Poll failed: {type(e).__name__}: {e}")
            self._stop.wait(self.TICK_S)

    def start(self):
        if not self.enabled:
            log.info("[LiveTraffic] TOMTOM_API_KEY not set - live traffic disabled (using synthetic flows).")
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="live-traffic", daemon=True)
        self._thread.start()
        log.warning(f"[LiveTraffic] Polling TomTom every {self.effective_interval_s()}s.")

    def stop(self):
        self._stop.set()

    def status(self) -> Dict:
        fresh = sum(1 for e in self.graph.edges.values() if e.has_fresh_live_data())
        return {
            "enabled": self.enabled,
            "provider": "tomtom",
            "poll_interval_s": self.effective_interval_s(),
            "last_poll_at": self.last_poll_at,
            "last_poll_requests": self.last_poll_requested,
            "edges_with_fresh_live_data": fresh,
            "total_edges": len(self.graph.edges),
        }


live_traffic = LiveTrafficService(road_graph)
