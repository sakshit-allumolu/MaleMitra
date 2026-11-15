import time
import pytest
from backend.app.config import settings
from backend.app.services.graph_service import road_graph
from backend.app.services.ripple_service import ripple_engine
from backend.app.services.live_traffic_service import LiveTrafficService, speed_ratio_to_vc


@pytest.fixture(autouse=True)
def _clean_graph():
    yield
    for e in road_graph.edges.values():
        e.is_blocked = False
        e.live_vc = e.live_speed_ratio = e.live_updated_at = None


# ── Priority 1: auto ripple ────────────────────────────────────────────────

def _blocked():
    return {e_id for e_id, e in road_graph.edges.items() if e.is_blocked}


def test_ripple_run_does_not_leak_blocked_state():
    for e in road_graph.edges.values():
        e.is_blocked = False
    road_graph.edges["edge-9"].is_blocked = True
    ripple_engine.run_simulation(custom_blocked_edge_ids=["edge-3"])
    assert _blocked() == {"edge-9"}
    ripple_engine.run_simulation()
    assert _blocked() == {"edge-9"}


def test_run_for_current_state_uses_real_blocks_and_caches():
    for e in road_graph.edges.values():
        e.is_blocked = False
    road_graph.edges["edge-5"].is_blocked = True
    res = ripple_engine.run_for_current_state()
    assert res["blocked_edges"] == ["edge-5"]
    assert ripple_engine.last_result is res
    assert _blocked() == {"edge-5"}


def test_run_for_current_state_with_nothing_blocked_has_no_demo_fallback():
    for e in road_graph.edges.values():
        e.is_blocked = False
    res = ripple_engine.run_for_current_state()
    assert res["blocked_edges"] == []


# ── Priority 2: speed ratio -> v/c ─────────────────────────────────────────

def test_speed_ratio_to_vc_inverts_bpr():
    assert speed_ratio_to_vc(1.0) == 0.0
    for vc in (0.5, 1.0, 1.5):
        ratio = 1.0 / (1.0 + settings.BPR_ALPHA * vc ** settings.BPR_BETA)
        assert speed_ratio_to_vc(ratio) == pytest.approx(vc, rel=1e-6)
    assert speed_ratio_to_vc(0.0) == settings.LIVE_TRAFFIC_MAX_VC


def test_poll_once_updates_edges_and_bumps_graph_version():
    svc = LiveTrafficService(road_graph)
    v0 = road_graph.graph_version
    n = svc.poll_once(fetcher=lambda lat, lon: {"currentSpeed": 10, "freeFlowSpeed": 40, "confidence": 0.9})
    assert n == len(road_graph.edges)
    assert all(e.has_fresh_live_data() and e.live_vc > 1.0 for e in road_graph.edges.values())
    assert road_graph.graph_version == v0 + 1


def test_poll_once_ignores_low_confidence_and_failures():
    svc = LiveTrafficService(road_graph)
    assert svc.poll_once(fetcher=lambda a, b: None) == 0
    assert svc.poll_once(fetcher=lambda a, b: {"currentSpeed": 5, "freeFlowSpeed": 40, "confidence": 0.1}) == 0
    assert not any(e.has_fresh_live_data() for e in road_graph.edges.values())


def test_stale_live_data_is_ignored():
    edge = road_graph.edges["edge-1"]
    edge.live_vc = 2.0
    edge.live_updated_at = time.time() - settings.LIVE_TRAFFIC_TTL_SECONDS - 1
    assert not edge.has_fresh_live_data()


def test_service_disabled_without_api_key():
    assert LiveTrafficService(road_graph).enabled == bool(settings.TOMTOM_API_KEY)


def test_poll_interval_respects_daily_budget():
    svc = LiveTrafficService(road_graph)
    n_roads = len(svc._query_points())
    assert 86400 / svc.effective_interval_s() * n_roads <= settings.LIVE_TRAFFIC_DAILY_REQUEST_BUDGET


# ── Priority 3: congestion-aware routing ───────────────────────────────────

def test_live_congestion_raises_risk_aware_cost_but_not_fastest():
    edge = road_graph.edges["edge-1"]
    fast_before = road_graph.get_edge_weight(edge, "fastest")
    risk_before = road_graph.get_edge_weight(edge, "risk_aware")
    edge.live_vc, edge.live_speed_ratio, edge.live_updated_at = 2.0, 0.3, time.time()
    assert road_graph.get_edge_weight(edge, "fastest") == fast_before
    assert road_graph.get_edge_weight(edge, "risk_aware") > risk_before


def test_risk_aware_route_avoids_live_congested_edges():
    res = road_graph.compute_dijkstra("N1", "N5", mode="risk_aware")
    direct = [e for e in res[1]]
    for e in direct:
        e.live_vc, e.live_speed_ratio, e.live_updated_at = 3.0, 0.1, time.time()
    rerouted = road_graph.compute_dijkstra("N1", "N5", mode="risk_aware")
    assert [e.edge_id for e in rerouted[1]] != [e.edge_id for e in direct]
