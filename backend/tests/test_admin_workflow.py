import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.graph_service import road_graph

client = TestClient(app)
ADMIN = {"Authorization": "Bearer usr-admin-1"}
RESP = {"Authorization": "Bearer usr-resp-1"}
CITIZEN = {"Authorization": "Bearer usr-citizen-1"}

# Two roads that no other test reports on, so these incidents start with no duplicates.
LOC_A = (12.9680, 77.6530)   # HAL 2nd Stage
LOC_B = (12.9150, 77.6350)   # HSR Layout


@pytest.fixture(autouse=True)
def _reset_graph():
    yield
    for e in road_graph.edges.values():
        e.is_blocked = False


def _report(loc, headers=CITIZEN):
    r = client.post("/api/v1/reports", json={
        "lat": loc[0], "lon": loc[1], "type": "waterlogging",
        "severity": "high", "description": "Standing water."
    }, headers=headers)
    assert r.status_code == 200
    return r.json()


def _post(inc_id, path, body, headers=ADMIN):
    return client.post(f"/api/v1/incidents/{inc_id}/{path}", json=body, headers=headers)


def test_cannot_close_road_without_field_verification():
    inc = _report(LOC_A)
    _post(inc["id"], "review", {"notes": "ok"})
    _post(inc["id"], "assign", {"team_id": "team-alpha"})
    r = _post(inc["id"], "restriction", {"action": "authorize_block"})
    assert r.status_code == 409
    assert "field-verify" in r.json()["detail"]
    assert road_graph.edges[inc["road_edge_id"]].is_blocked is False


def test_cannot_reopen_before_clearance_is_proposed():
    inc = _report(LOC_A)
    iid = inc["id"]
    _post(iid, "review", {"notes": "ok"})
    _post(iid, "assign", {"team_id": "team-alpha"})
    _post(iid, "verify", {"findings": "deep", "water_depth_cm": 50.0, "is_impassable": True,
                          "recommended_action": "authorize_closure"}, RESP)
    assert _post(iid, "restriction", {"action": "authorize_block"}).status_code == 200
    r = _post(iid, "restriction", {"action": "authorize_reopen"})
    assert r.status_code == 409
    assert road_graph.edges[inc["road_edge_id"]].is_blocked is True
    _post(iid, "clearance", {"clearance_findings": "drained"}, RESP)
    assert _post(iid, "restriction", {"action": "authorize_reopen"}).status_code == 200
    assert road_graph.edges[inc["road_edge_id"]].is_blocked is False


def test_cannot_dispatch_before_triage_review():
    inc = _report(LOC_B)
    r = _post(inc["id"], "assign", {"team_id": "team-alpha"})
    assert r.status_code == 409
    assert "Triage" in r.json()["detail"]


def test_reject_only_for_reported_or_under_review():
    inc = _report(LOC_B)
    iid = inc["id"]
    _post(iid, "review", {"notes": "ok"})
    _post(iid, "assign", {"team_id": "team-alpha"})
    assert _post(iid, "restriction", {"action": "reject"}).status_code == 409


def test_reject_marks_incident_rejected_with_reason():
    inc = _report(LOC_B)
    r = _post(inc["id"], "restriction", {"action": "reject", "notes": "Spam"})
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"
    assert r.json()["restriction_notes"] == "Spam"


def test_second_report_on_same_road_is_flagged_as_duplicate_and_counted():
    # The DB persists between runs/tests, so don't assume the road is clean:
    # after this call at least one open incident is guaranteed on the road.
    _report(LOC_A)
    second = _report(LOC_A, {"Authorization": "Bearer usr-citizen-2"})
    summary = second["agent_summary"]
    assert summary["duplicate_cluster"] is True
    assert "duplicate" in summary["recommendation"].lower()

    original = client.get(f"/api/v1/incidents/{summary['duplicate_of']}", headers=ADMIN).json()
    assert original["road_edge_id"] == second["road_edge_id"]
    assert original["status"] in ("reported", "under_review", "assigned", "field_verified", "blocked", "clearance_proposed")
    # The corroborating report was counted on the original
    before = original["reports_count"]
    third = _report(LOC_A, {"Authorization": "Bearer usr-citizen-2"})
    after = client.get(f"/api/v1/incidents/{third['agent_summary']['duplicate_of']}", headers=ADMIN).json()
    assert after["reports_count"] >= before + 1


def test_rejecting_duplicate_keeps_hazard_while_original_is_open():
    first = _report(LOC_B)
    second = _report(LOC_B, {"Authorization": "Bearer usr-citizen-2"})
    edge = road_graph.edges[first["road_edge_id"]]
    assert edge.hazard_severity != "none"
    _post(second["id"], "restriction", {"action": "reject"})
    assert edge.hazard_severity != "none"  # original still open
