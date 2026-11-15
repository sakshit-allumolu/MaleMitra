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


def test_a_detour_that_still_passes_through_the_closure_is_not_offered(monkeypatch):
    direct = _geo((77.5946, 12.9716), (77.6000, 12.9600), (77.6245, 12.9352))
    monkeypatch.setattr(agent_service, "_fetch_osrm_route", lambda *a, **k: {"code": "Ok", "routes": [direct]})
    monkeypatch.setattr(agent_service, "_fetch_osrm_route_waypoints", lambda *a, **k: {"code": "Ok", "routes": [direct]})
    _closed_at(monkeypatch, 12.9600, 77.6000)
    assert [r["type"] for r in _compare()["routes"]] == ["fastest"]


def test_closure_off_the_direct_route_means_no_incident_detour_but_still_a_backup(monkeypatch):
    direct = _geo((77.5946, 12.9716), (77.6000, 12.9600), (77.6245, 12.9352))
    backup = _geo((77.5946, 12.9716), (77.6100, 12.9700), (77.6245, 12.9352))
    backup["distance"] = 8200.0
    monkeypatch.setattr(agent_service, "_fetch_osrm_route", lambda *a, **k: {"code": "Ok", "routes": [direct]})
    monkeypatch.setattr(agent_service, "_fetch_osrm_route_waypoints", lambda *a, **k: {"code": "Ok", "routes": [backup]})
    _closed_at(monkeypatch, 12.9600, 77.6100)  # ~1 km off the route: nothing to avoid
    body = _compare()["routes"]
    assert [r["type"] for r in body][0] == "fastest" and len(body) >= 2
    assert all(r["closed_incidents_passed"] == 0 and r["reported_incidents_passed"] == 0 for r in body)
    assert "Backup route" in body[1]["uncertainty"]  # honest label: nothing was being avoided


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


def test_a_reported_incident_gets_a_detour_and_a_third_route(monkeypatch):
    _incidents(monkeypatch, reported=[(12.9600, 77.6000)], via=[VIA_NORTH, VIA_SOUTH, VIA_NORTH, VIA_SOUTH])
    routes = _compare()["routes"]
    assert [r["type"] for r in routes] == ["fastest", "risk_aware", "alternative"]
    assert routes[0]["reported_incidents_passed"] == 1                      # direct route meets the report
    assert routes[1]["reported_incidents_passed"] == 0 and routes[2]["reported_incidents_passed"] == 0
    assert routes[1]["distance_m"] <= routes[2]["distance_m"]               # shortest clean detour first
    assert all(r["closed_incidents_passed"] == 0 for r in routes)


def test_osrm_own_alternative_is_used_as_the_third_route_when_it_avoids_the_incident(monkeypatch):
    _incidents(monkeypatch, reported=[(12.9600, 77.6000)], alts=[VIA_SOUTH], via=[VIA_NORTH])
    routes = _compare()["routes"]
    assert [r["type"] for r in routes] == ["fastest", "risk_aware", "alternative"]
    assert {routes[1]["distance_m"], routes[2]["distance_m"]} == {8200.0, 9100.0}


# A different road that still passes through the incident point (so it is no cleaner than the direct route).
THROUGH = _geo((77.5946, 12.9716), (77.6000, 12.9600), (77.6300, 12.9700), (77.6245, 12.9352))


def test_a_reported_incident_route_is_kept_as_a_last_resort_but_a_closed_one_never(monkeypatch):
    _incidents(monkeypatch, reported=[(12.9600, 77.6000)], alts=[THROUGH], via=[])
    routes = _compare()["routes"]
    assert [r["type"] for r in routes] == ["fastest", "risk_aware"]
    assert routes[1]["reported_incidents_passed"] == 1                     # shown, and it says so
    _incidents(monkeypatch, closed=[(12.9600, 77.6000)], alts=[THROUGH], via=[])
    body = _compare()["routes"]
    assert [r["type"] for r in body] == ["fastest"] and body[0]["closed_incidents_passed"] == 1


def test_incident_at_the_start_or_destination_is_ignored(monkeypatch):
    _incidents(monkeypatch, reported=[(12.9716, 77.5946)], via=[VIA_NORTH])  # exactly at the origin
    body = _compare()["routes"]
    assert all(r["reported_incidents_passed"] == 0 for r in body)           # not counted against any route
    assert all("Backup route" in r["uncertainty"] for r in body[1:])        # and not treated as something to avoid


def test_incident_far_from_the_trip_changes_nothing(monkeypatch):
    _incidents(monkeypatch, reported=[(13.05, 77.70)], via=[VIA_NORTH])
    body = _compare()["routes"]
    assert all(r["reported_incidents_passed"] == 0 for r in body)
    assert all("Backup route" in r["uncertainty"] for r in body[1:])


def test_a_backup_route_is_offered_even_when_nothing_is_reported(monkeypatch):
    _incidents(monkeypatch, via=[VIA_NORTH, VIA_SOUTH, VIA_NORTH, VIA_SOUTH])
    body = _compare()["routes"]
    assert [r["type"] for r in body] == ["fastest", "risk_aware", "alternative"]
    assert len({r["distance_m"] for r in body}) == 3                        # three different roads
    assert all("Backup route" in r["uncertainty"] for r in body[1:])


def test_a_backup_that_is_far_longer_than_the_direct_route_is_not_offered(monkeypatch):
    long_route = _geo((77.5946, 12.9716), (77.7000, 12.9000), (77.6245, 12.9352))
    long_route["distance"] = 20000.0                                        # direct is 7000 m: 2.9x
    _incidents(monkeypatch, via=[long_route, long_route, long_route, long_route])
    assert [r["type"] for r in _compare()["routes"]] == ["fastest"]


def test_reported_statuses_exclude_closed_and_finished_incidents():
    assert "blocked" not in agent_service._REPORTED_STATUSES
    assert "cleared" not in agent_service._REPORTED_STATUSES and "rejected" not in agent_service._REPORTED_STATUSES
    assert "reported" in agent_service._REPORTED_STATUSES
