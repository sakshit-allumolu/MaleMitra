"""TomTom traffic-aware routing: gating, budget, cache, breaker, route matching and /routes/compare integration."""
import pytest
from fastapi.testclient import TestClient

from backend.app import ratelimit
from backend.app.config import settings
from backend.app.main import app
from backend.app.services import agent_service, tomtom_routing_service as tt

client = TestClient(app)
O = (12.9716, 77.5946)
D = (12.9352, 77.6245)


def _payload(travel=900, free=600, points=None, n=1):
    pts = points or [(12.9716, 77.5946), (12.9600, 77.6000), (12.9352, 77.6245)]
    route = {
        "summary": {"travelTimeInSeconds": travel, "noTrafficTravelTimeInSeconds": free,
                    "trafficDelayInSeconds": travel - free, "lengthInMeters": 7000},
        "legs": [{"points": [{"latitude": a, "longitude": b} for a, b in pts]}],
    }
    return {"routes": [route] * n}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setattr(settings, "TOMTOM_API_KEY", "test-key")
    monkeypatch.setattr(settings, "TOMTOM_ROUTING_ENABLED", True)
    monkeypatch.setattr(settings, "TOMTOM_ROUTING_DAILY_BUDGET", 800)
    tt.reset()
    ratelimit.reset()
    agent_service._osrm_reset()
    yield
    tt.reset()
    ratelimit.reset()
    agent_service._osrm_reset()


def test_disabled_without_key_makes_no_calls(monkeypatch):
    monkeypatch.setattr(settings, "TOMTOM_API_KEY", "")
    calls = []
    assert tt.get_live_routes(*O, *D, fetcher=lambda u: calls.append(u)) is None
    assert calls == [] and tt.status()["enabled"] is False


def test_disabled_by_flag(monkeypatch):
    monkeypatch.setattr(settings, "TOMTOM_ROUTING_ENABLED", False)
    assert tt.get_live_routes(*O, *D, fetcher=lambda u: _payload()) is None


def test_parses_live_and_free_flow_times():
    routes = tt.get_live_routes(*O, *D, fetcher=lambda u: _payload(900, 600))
    assert routes[0]["travel_s"] == 900 and routes[0]["no_traffic_s"] == 600
    assert tt.live_factor(routes[0]) == pytest.approx(1.5)


def test_request_asks_for_live_traffic_and_alternatives():
    seen = []
    tt.get_live_routes(*O, *D, fetcher=lambda u: seen.append(u) or _payload())
    assert "traffic=true" in seen[0] and "computeTravelTimeFor=all" in seen[0]
    assert "maxAlternatives=2" in seen[0] and "12.971600,77.594600:12.935200,77.624500" in seen[0]


def test_responses_are_cached():
    calls = []
    for _ in range(4):
        assert tt.get_live_routes(*O, *D, fetcher=lambda u: calls.append(1) or _payload())
    assert len(calls) == 1 and tt.budget_used() == 1


def test_budget_is_enforced_and_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "TOMTOM_ROUTING_DAILY_BUDGET", 2)
    calls = []
    for i in range(5):
        tt.get_live_routes(O[0] + i * 0.01, O[1], *D, fetcher=lambda u: calls.append(1) or _payload())
    assert len(calls) == 2 and tt.budget_used() == 2
    assert tt.status()["used_last_24h"] == 2


def test_failures_open_the_breaker():
    calls = []
    for i in range(10):
        assert tt.get_live_routes(O[0] + i * 0.01, O[1], *D, fetcher=lambda u: calls.append(1)) is None
    assert len(calls) == 3  # breaker threshold, then no more network calls
    assert tt.status()["breaker_open"] is True


def test_http_errors_never_leak_the_api_key(monkeypatch, caplog):
    def boom(*a, **k):
        raise OSError("https://api.tomtom.com/...?key=test-key")
    monkeypatch.setattr(tt.urllib.request, "urlopen", boom)
    with caplog.at_level("DEBUG"):
        assert tt.get_live_routes(*O, *D) is None
    assert "test-key" not in caplog.text


def test_malformed_routes_are_skipped():
    bad = {"routes": [{"summary": {"travelTimeInSeconds": 100}}, {"nope": 1}, {"summary": {"travelTimeInSeconds": 0, "noTrafficTravelTimeInSeconds": 0}}]}
    assert tt.get_live_routes(*O, *D, fetcher=lambda u: bad) is None


def test_live_factor_is_clamped():
    assert tt.live_factor({"travel_s": 100, "no_traffic_s": 200}) == 1.0
    assert tt.live_factor({"travel_s": 9000, "no_traffic_s": 100}) == tt.MAX_FACTOR


def test_match_route_picks_overlapping_route_and_flags_detours():
    a = {"travel_s": 900, "no_traffic_s": 600, "points": [[12.97 + i * 0.001, 77.59] for i in range(40)]}
    b = {"travel_s": 700, "no_traffic_s": 650, "points": [[12.97 + i * 0.001, 77.65] for i in range(40)]}
    on_b = [[12.97 + i * 0.001, 77.6501] for i in range(40)]
    assert tt.match_route(on_b, [a, b]) == (b, True)
    far = [[12.97 + i * 0.001, 77.70] for i in range(40)]
    assert tt.match_route(far, [a, b]) == (a, False)  # no overlap: best TomTom route, flagged inexact


# ── /routes/compare integration ───────────────────────────────────────────────

def _osrm_ok(monkeypatch):
    route = {"distance": 7000.0, "duration": 600.0, "legs": [],
             "geometry": {"coordinates": [[77.5946, 12.9716], [77.6000, 12.9600], [77.6245, 12.9352]]}}
    monkeypatch.setattr(agent_service, "_fetch_osrm_route", lambda *a, **k: {"code": "Ok", "routes": [route]})
    monkeypatch.setattr(agent_service, "_fetch_osrm_route_waypoints", lambda *a, **k: None)


def _compare():
    r = client.post("/api/v1/routes/compare", headers={"Authorization": "Bearer usr-citizen-1"}, json={
        "origin": {"lat": O[0], "lon": O[1]}, "destination": {"lat": D[0], "lon": D[1]}})
    assert r.status_code == 200, r.text
    return r.json()


def test_compare_uses_tomtom_live_traffic(monkeypatch):
    _osrm_ok(monkeypatch)
    monkeypatch.setattr(tt, "_http_get", lambda url: _payload(900, 600))
    body = _compare()
    assert body["traffic_source"] == "tomtom_live"
    assert body["traffic_factor"] == pytest.approx(1.5)
    assert body["traffic_label"].startswith("Live") and "live traffic" in body["message"]
    assert "tomtom" not in (body["traffic_label"] + body["message"]).lower()  # provider name stays out of the UI
    first = body["routes"][0]
    assert first["traffic_source"] == "tomtom_live"
    assert first["traffic_factor"] == pytest.approx(1.5)
    assert first["traffic_delay_s"] == pytest.approx(300.0)  # 600s free-flow * 0.5
    assert first["base_duration_s"] == 600.0


def test_compare_falls_back_to_time_of_day_without_key(monkeypatch):
    _osrm_ok(monkeypatch)
    monkeypatch.setattr(settings, "TOMTOM_API_KEY", "")
    body = _compare()
    assert body["traffic_source"] == "time_of_day_model"
    assert body["routes"] and all(r["traffic_source"] == "time_of_day_model" for r in body["routes"])
    assert "typical-hours" in body["message"]


def test_compare_falls_back_when_tomtom_fails(monkeypatch):
    _osrm_ok(monkeypatch)
    monkeypatch.setattr(tt, "_http_get", lambda url: None)
    body = _compare()
    assert body["traffic_source"] == "time_of_day_model" and body["routes"]


def test_traffic_status_endpoint_reports_routing_budget():
    r = client.get("/api/v1/traffic/live")
    assert r.status_code == 200
    routing = r.json()["routing"]
    assert routing["enabled"] is True and routing["daily_budget"] == 800


# ── service-area guard ────────────────────────────────────────────────────────

def _compare_raw(o, d):
    return client.post("/api/v1/routes/compare", headers={"Authorization": "Bearer usr-citizen-1"},
                       json={"origin": {"lat": o[0], "lon": o[1]}, "destination": {"lat": d[0], "lon": d[1]}})


def test_compare_rejects_points_outside_the_routable_area(monkeypatch):
    called = []
    monkeypatch.setattr(agent_service, "_fetch_osrm_route", lambda *a, **k: called.append(1))
    far_north = (13.35, 77.55)  # inside the API's lat/lon limits, outside the OSRM map
    for o, d, who in ((far_north, D, "start"), (O, far_north, "destination")):
        r = _compare_raw(o, d)
        assert r.status_code == 422 and who in r.json()["detail"] and "outside" in r.json()["detail"]
    assert called == []  # never reached the routing server


def test_compare_accepts_points_inside_the_routable_area(monkeypatch):
    _osrm_ok(monkeypatch)
    assert _compare_raw(O, D).status_code == 200


def _geo(*pts):
    return {"distance": 7000.0, "duration": 600.0, "legs": [], "geometry": {"coordinates": [list(p) for p in pts]}}


def _closed_at(monkeypatch, lat, lon):
    monkeypatch.setattr(agent_service, "_get_blocked_incident_locations", lambda: [(lat, lon)])
    monkeypatch.setattr(tt, "_http_get", lambda url: None)


def test_detour_around_a_closed_road_is_shown_even_when_osrm_has_no_alternative(monkeypatch):
    direct = _geo((77.5946, 12.9716), (77.6000, 12.9600), (77.6245, 12.9352))
    detour = _geo((77.5946, 12.9716), (77.6100, 12.9700), (77.6245, 12.9352))
    detour["distance"] = 8200.0
    monkeypatch.setattr(agent_service, "_fetch_osrm_route", lambda *a, **k: {"code": "Ok", "routes": [direct]})
    monkeypatch.setattr(agent_service, "_fetch_osrm_route_waypoints", lambda *a, **k: {"code": "Ok", "routes": [detour]})
    _closed_at(monkeypatch, 12.9600, 77.6000)  # exactly on the direct route
    routes = _compare()["routes"]
    assert [r["type"] for r in routes] == ["fastest", "risk_aware"]
    assert routes[1]["distance_m"] == 8200.0 and routes[1]["coordinates"][1] == [12.97, 77.61]
    assert routes[1]["recommended"] is True and routes[0]["recommended"] is False


def test_a_detour_that_still_passes_through_the_closure_is_not_offered(monkeypatch):
    direct = _geo((77.5946, 12.9716), (77.6000, 12.9600), (77.6245, 12.9352))
    monkeypatch.setattr(agent_service, "_fetch_osrm_route", lambda *a, **k: {"code": "Ok", "routes": [direct]})
    monkeypatch.setattr(agent_service, "_fetch_osrm_route_waypoints", lambda *a, **k: {"code": "Ok", "routes": [direct]})
    _closed_at(monkeypatch, 12.9600, 77.6000)
    routes = _compare()["routes"]
    assert [r["type"] for r in routes] == ["fastest"] and not routes[0]["recommended"]
    assert "none is recommended" in routes[0]["uncertainty"]


def test_trip_outside_the_modelled_neighbourhoods_gets_no_graph_junction_names(monkeypatch):
    _osrm_ok(monkeypatch)
    monkeypatch.setattr(tt, "_http_get", lambda url: None)
    r = client.post("/api/v1/routes/compare", headers={"Authorization": "Bearer usr-citizen-1"}, json={
        "origin": {"lat": 13.0358, "lon": 77.5970}, "destination": {"lat": 13.0035, "lon": 77.5710}})  # Hebbal -> Malleshwaram
    assert r.status_code == 200, r.text
    first = r.json()["routes"][0]
    assert first["node_names"] == [] and first["blocked_edges_crossed"] == 0 and first["geometry_source"] == "osrm"


def test_graph_area_is_only_the_modelled_neighbourhoods():
    from backend.app.config import in_graph_area, in_service_area
    assert in_graph_area(12.9352, 77.6245) and in_service_area(12.9352, 77.6245)   # Sony World
    assert not in_graph_area(13.0035, 77.5710) and in_service_area(13.0035, 77.5710)  # Malleshwaram: city, not graph
    assert not in_service_area(13.35, 77.6)


# ── reported (not yet closed) incidents ───────────────────────────────────────

DIRECT = _geo((77.5946, 12.9716), (77.6000, 12.9600), (77.6245, 12.9352))
VIA_NORTH = _geo((77.5946, 12.9716), (77.6100, 12.9700), (77.6245, 12.9352))
VIA_SOUTH = _geo((77.5946, 12.9716), (77.5950, 12.9500), (77.6245, 12.9352))
for _r, _d in ((VIA_NORTH, 8200.0), (VIA_SOUTH, 9100.0)):
    _r["distance"] = _d


def _incidents(monkeypatch, closed=(), reported=(), alts=(), via=()):
    """OSRM returns DIRECT (+ alts); forced via-routes come from `via` in order; incidents are patched in."""
    monkeypatch.setattr(agent_service, "_get_blocked_incident_locations", lambda: list(closed))
    monkeypatch.setattr(agent_service, "_get_reported_incident_locations", lambda: list(reported))
    monkeypatch.setattr(agent_service, "_fetch_osrm_route",
                        lambda *a, **k: {"code": "Ok", "routes": [DIRECT, *alts]})
    queue = list(via)
    monkeypatch.setattr(agent_service, "_fetch_osrm_route_waypoints",
                        lambda *a, **k: {"code": "Ok", "routes": [queue.pop(0)]} if queue else None)
    monkeypatch.setattr(tt, "_http_get", lambda url: None)


REPORT = (12.9600, 77.6000)          # on the direct route
CLOSURE = (12.9600, 77.6000)         # same spot, used when it is closed rather than reported
MID_REPORT = (12.9476, 77.61225)     # middle of the direct route's second leg
CLOSED_ONLY = _geo((77.5946, 12.9716), (77.6100, 12.9700), (77.61225, 12.9476), (77.6245, 12.9352))
CLOSED_ONLY["distance"] = 8200.0     # skirts the closure but still passes MID_REPORT


def _spy_waypoints(monkeypatch):
    calls = []
    original = agent_service._fetch_osrm_route_waypoints

    def spy(*a, **k):
        calls.append(1)
        return original(*a, **k)
    monkeypatch.setattr(agent_service, "_fetch_osrm_route_waypoints", spy)
    return calls


def test_nothing_on_the_path_means_one_route_and_no_extra_osrm_calls(monkeypatch):
    _incidents(monkeypatch, via=[VIA_NORTH, VIA_SOUTH])
    calls = _spy_waypoints(monkeypatch)
    body = _compare()["routes"]
    assert [r["type"] for r in body] == ["fastest"] and not body[0]["recommended"]
    assert calls == []


def test_osrm_alternatives_are_not_shown_when_nothing_is_on_the_path(monkeypatch):
    _incidents(monkeypatch, alts=[VIA_NORTH, VIA_SOUTH])
    assert [r["type"] for r in _compare()["routes"]] == ["fastest"]


def test_a_closure_off_the_direct_route_means_one_route(monkeypatch):
    _incidents(monkeypatch, closed=[(12.9600, 77.6100)], via=[VIA_NORTH, VIA_SOUTH])  # ~1 km off the route
    body = _compare()["routes"]
    assert [r["type"] for r in body] == ["fastest"] and body[0]["closed_incidents_passed"] == 0


def test_incident_at_the_start_or_destination_is_ignored(monkeypatch):
    _incidents(monkeypatch, reported=[(12.9716, 77.5946)], via=[VIA_NORTH])  # exactly at the origin
    body = _compare()["routes"]
    assert [r["type"] for r in body] == ["fastest"] and body[0]["reported_incidents_passed"] == 0


def test_incident_far_from_the_trip_changes_nothing(monkeypatch):
    _incidents(monkeypatch, reported=[(13.05, 77.70)], via=[VIA_NORTH])
    body = _compare()["routes"]
    assert [r["type"] for r in body] == ["fastest"] and body[0]["reported_incidents_passed"] == 0


def test_reported_only_gives_two_routes_and_the_second_is_recommended_and_clean(monkeypatch):
    _incidents(monkeypatch, reported=[REPORT], via=[VIA_NORTH, VIA_SOUTH])
    routes = _compare()["routes"]
    assert [r["type"] for r in routes] == ["fastest", "risk_aware"]
    assert routes[0]["reported_incidents_passed"] == 1 and not routes[0]["recommended"]
    assert routes[1]["reported_incidents_passed"] == 0 and routes[1]["recommended"] is True
    assert routes[1]["distance_m"] == 8200.0                                 # the shorter of the clean detours


def test_a_route_that_still_passes_a_reported_incident_is_never_recommended(monkeypatch):
    _incidents(monkeypatch, reported=[REPORT], alts=[THROUGH], via=[])
    routes = _compare()["routes"]
    assert [r["type"] for r in routes] == ["fastest"] and not routes[0]["recommended"]
    assert "none is recommended" in routes[0]["uncertainty"]


def test_osrm_own_alternative_is_used_as_the_recommended_route_when_it_is_clean(monkeypatch):
    _incidents(monkeypatch, reported=[REPORT], alts=[VIA_SOUTH], via=[])
    routes = _compare()["routes"]
    assert [r["type"] for r in routes] == ["fastest", "risk_aware"] and routes[1]["distance_m"] == 9100.0


def test_closed_and_reported_gives_three_routes(monkeypatch):
    _incidents(monkeypatch, closed=[CLOSURE], reported=[MID_REPORT], alts=[CLOSED_ONLY, VIA_SOUTH])
    routes = _compare()["routes"]
    assert [r["type"] for r in routes] == ["fastest", "risk_aware", "alternative"]
    direct, safe, closed_only = routes
    assert direct["closed_incidents_passed"] == 1 and direct["reported_incidents_passed"] == 1
    assert safe["recommended"] and safe["closed_incidents_passed"] == 0 and safe["reported_incidents_passed"] == 0
    assert closed_only["closed_incidents_passed"] == 0 and closed_only["reported_incidents_passed"] == 1
    assert not closed_only["recommended"] and not direct["recommended"]


def test_closed_and_reported_with_no_clean_route_recommends_nothing(monkeypatch):
    _incidents(monkeypatch, closed=[CLOSURE], reported=[MID_REPORT], alts=[CLOSED_ONLY], via=[])
    routes = _compare()["routes"]
    assert [r["type"] for r in routes] == ["fastest", "alternative"]
    assert not any(r["recommended"] for r in routes) and routes[1]["closed_incidents_passed"] == 0


# A different road that still passes through the incident point (so it is no cleaner than the direct route).
THROUGH = _geo((77.5946, 12.9716), (77.6000, 12.9600), (77.6300, 12.9700), (77.6245, 12.9352))


def test_a_route_through_a_closed_road_is_never_offered(monkeypatch):
    _incidents(monkeypatch, closed=[CLOSURE], alts=[THROUGH], via=[])
    body = _compare()["routes"]
    assert [r["type"] for r in body] == ["fastest"] and body[0]["closed_incidents_passed"] == 1


def test_a_detour_far_longer_than_the_direct_route_is_not_offered(monkeypatch):
    long_route = _geo((77.5946, 12.9716), (77.7000, 12.9000), (77.6245, 12.9352))
    long_route["distance"] = 20000.0                                        # direct is 7000 m: 2.9x
    _incidents(monkeypatch, reported=[REPORT], via=[long_route] * 8)
    assert [r["type"] for r in _compare()["routes"]] == ["fastest"]


def test_reported_statuses_exclude_closed_and_finished_incidents():
    assert "blocked" not in agent_service._REPORTED_STATUSES
    assert "cleared" not in agent_service._REPORTED_STATUSES and "rejected" not in agent_service._REPORTED_STATUSES
    assert "reported" in agent_service._REPORTED_STATUSES
