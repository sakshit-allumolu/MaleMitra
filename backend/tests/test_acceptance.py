import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.graph_service import road_graph
from backend.app.services.ripple_service import ripple_engine
from backend.app.services.eval_service import eval_harness

client = TestClient(app)

def test_t01_citizen_report_in_bounded_region():
    """T01: Citizen report in bounded region: Persisted and mapped to candidate road edge."""
    payload = {
        "lat": 12.9352,
        "lon": 77.6245,
        "type": "waterlogging",
        "severity": "high",
        "description": "Sony World Junction deep water puddle.",
        "evidence_note": "Near junction signal"
    }
    resp = client.post("/api/v1/reports", json=payload, headers={"Authorization": "Bearer usr-citizen-1"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"].startswith("inc-")
    assert data["road_edge_id"] is not None
    assert data["status"] == "reported"
    assert "road_name" in data
    assert data["reports_count"] >= 1

def test_t02_ambiguous_location_flagged():
    """T02: Ambiguous location between two roads flagged for review, does not silently restrict."""
    # Coordinate midway between ST Bed and Koramangala 80ft road
    payload = {
        "lat": 12.9295,
        "lon": 77.6280,
        "type": "drain_overflow",
        "severity": "medium",
        "description": "Drain overflowing across layout road."
    }
    resp = client.post("/api/v1/reports", json=payload, headers={"Authorization": "Bearer usr-citizen-1"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "reported"
    assert data["is_blocked"] is False
    assert data["confidence"] <= 0.85

def test_t04_unverified_report_does_not_close_road():
    """T04: Unverified report creates warning penalty; no hard road closure."""
    payload = {
        "lat": 12.9600,
        "lon": 77.6490,
        "type": "waterlogging",
        "severity": "medium",
        "description": "Domlur signal water accumulation."
    }
    resp = client.post("/api/v1/reports", json=payload, headers={"Authorization": "Bearer usr-citizen-1"})
    assert resp.status_code == 200
    data = resp.json()
    edge_id = data["road_edge_id"]
    if edge_id and edge_id in road_graph.edges:
        assert road_graph.edges[edge_id].is_blocked is False

def test_t05_responder_verifies_and_admin_approves_blockage():
    """T05: Responder verifies blockage -> Admin can approve -> Graph version increments."""
    # Create report
    report_resp = client.post("/api/v1/reports", json={
        "lat": 12.9425,
        "lon": 77.6250,
        "type": "road_submerged",
        "severity": "critical",
        "description": "Ejipura main link road fully submerged."
    }, headers={"Authorization": "Bearer usr-citizen-1"})
    inc_id = report_resp.json()["id"]
    
    # Admin Review
    rev_resp = client.post(f"/api/v1/incidents/{inc_id}/review", json={"notes": "Triage verified"}, headers={"Authorization": "Bearer usr-admin-1"})
    assert rev_resp.status_code == 200
    assert rev_resp.json()["status"] == "under_review"
    
    # Admin Assign
    assign_resp = client.post(f"/api/v1/incidents/{inc_id}/assign", json={"team_id": "team-alpha", "priority": "critical"}, headers={"Authorization": "Bearer usr-admin-1"})
    assert assign_resp.status_code == 200
    assert assign_resp.json()["status"] == "assigned"
    
    # Responder Verify
    verify_resp = client.post(f"/api/v1/incidents/{inc_id}/verify", json={
        "findings": "Water depth 55cm. Inundation across both lanes. Vehicles cannot pass.",
        "water_depth_cm": 55.0,
        "is_impassable": True,
        "recommended_action": "authorize_closure"
    }, headers={"Authorization": "Bearer usr-resp-1"})
    assert verify_resp.status_code == 200
    assert verify_resp.json()["status"] == "field_verified"
    
    # Admin Authorize Restriction
    prev_version = road_graph.graph_version
    block_resp = client.post(f"/api/v1/incidents/{inc_id}/restriction", json={
        "action": "authorize_block",
        "notes": "Authorized emergency road closure."
    }, headers={"Authorization": "Bearer usr-admin-1"})
    assert block_resp.status_code == 200
    assert block_resp.json()["status"] == "blocked"
    assert block_resp.json()["is_blocked"] is True
    assert road_graph.graph_version > prev_version

def test_t06_blocked_edge_excluded_from_recomputed_routes():
    """T06: Blocked edge in route: Recompute excludes blocked edge."""
    # Query route through Sony World / Ejipura corridor
    route_resp = client.post("/api/v1/routes/compare", json={
        "origin": {"lat": 12.9352, "lon": 77.6245},
        "destination": {"lat": 12.9780, "lon": 77.6410}
    }, headers={"Authorization": "Bearer usr-citizen-1"})
    assert route_resp.status_code == 200
    data = route_resp.json()
    assert "routes" in data
    assert len(data["routes"]) >= 1
    
    for r in data["routes"]:
        assert r["blocked_edges_crossed"] == 0

def test_t08_responder_propose_clearance_and_admin_reopening():
    """T08: Responder recommends reopening -> Admin approval required."""
    # Find an existing incident or create one
    report_resp = client.post("/api/v1/reports", json={
        "lat": 12.9340,
        "lon": 77.6320,
        "type": "waterlogging",
        "severity": "high",
        "description": "Koramangala 4th Block water receded."
    }, headers={"Authorization": "Bearer usr-citizen-1"})
    inc_id = report_resp.json()["id"]
    
    client.post(f"/api/v1/incidents/{inc_id}/assign", json={"team_id": "team-alpha"}, headers={"Authorization": "Bearer usr-admin-1"})
    client.post(f"/api/v1/incidents/{inc_id}/verify", json={"findings": "Impassable", "water_depth_cm": 40.0, "is_impassable": True, "recommended_action": "authorize_closure"}, headers={"Authorization": "Bearer usr-resp-1"})
    client.post(f"/api/v1/incidents/{inc_id}/restriction", json={"action": "authorize_block"}, headers={"Authorization": "Bearer usr-admin-1"})
    
    # Responder proposes clearance
    clear_prop_resp = client.post(f"/api/v1/incidents/{inc_id}/clearance", json={
        "clearance_findings": "Pumps operated for 2 hours. Water level below 5cm. Road clear."
    }, headers={"Authorization": "Bearer usr-resp-1"})
    assert clear_prop_resp.status_code == 200
    assert clear_prop_resp.json()["status"] == "clearance_proposed"
    
    # Admin Reopening Authorization
    reopen_resp = client.post(f"/api/v1/incidents/{inc_id}/restriction", json={
        "action": "authorize_reopen",
        "notes": "Reopening confirmed by Control Room."
    }, headers={"Authorization": "Bearer usr-admin-1"})
    assert reopen_resp.status_code == 200
    assert reopen_resp.json()["status"] == "cleared"
    assert reopen_resp.json()["is_blocked"] is False

def test_t09_citizen_forbidden_from_admin_endpoints():
    """T09: Citizen calls admin endpoint -> 403 Forbidden; no state mutation."""
    resp = client.post("/api/v1/incidents/inc-dummy/review", json={"notes": "Hacked review"}, headers={"Authorization": "Bearer usr-citizen-1"})
    assert resp.status_code == 403

def test_t11_ripple_run_deterministic_reproducibility():
    """T11: Ripple run same seed -> Identical modeled outputs."""
    run1 = ripple_engine.run_simulation(seed=42, iterations=2, custom_blocked_edge_ids=["edge-7"])
    run2 = ripple_engine.run_simulation(seed=42, iterations=2, custom_blocked_edge_ids=["edge-7"])
    
    assert run1["affected_trips"] == run2["affected_trips"]
    assert run1["mean_baseline_duration_s"] == run2["mean_baseline_duration_s"]
    assert run1["mean_disrupted_duration_s"] == run2["mean_disrupted_duration_s"]
    assert run1["mean_detour_s"] == run2["mean_detour_s"]

def test_t15_full_e2e_journey():
    """T15: Full E2E journey: Report -> Review -> Assign -> Verify -> Block -> Reroute -> Clear -> Reopen."""
    # 1. Report
    rep = client.post("/api/v1/reports", json={
        "lat": 12.9175,
        "lon": 77.6225,
        "type": "waterlogging",
        "severity": "critical",
        "description": "Silk Board junction underpass flooded."
    }, headers={"Authorization": "Bearer usr-citizen-1"}).json()
    inc_id = rep["id"]
    
    # 2. Review
    rev = client.post(f"/api/v1/incidents/{inc_id}/review", json={"notes": "Urgent triage"}, headers={"Authorization": "Bearer usr-admin-1"}).json()
    assert rev["status"] == "under_review"
    
    # 3. Assign
    ass = client.post(f"/api/v1/incidents/{inc_id}/assign", json={"team_id": "team-beta"}, headers={"Authorization": "Bearer usr-admin-1"}).json()
    assert ass["status"] == "assigned"
    
    # 4. Verify
    ver = client.post(f"/api/v1/incidents/{inc_id}/verify", json={"findings": "Water 50cm deep", "water_depth_cm": 50.0, "is_impassable": True, "recommended_action": "authorize_closure"}, headers={"Authorization": "Bearer usr-resp-2"}).json()
    assert ver["status"] == "field_verified"
    
    # 5. Block
    blk = client.post(f"/api/v1/incidents/{inc_id}/restriction", json={"action": "authorize_block"}, headers={"Authorization": "Bearer usr-admin-1"}).json()
    assert blk["status"] == "blocked"
    
    # 6. Reroute
    rt = client.post("/api/v1/routes/compare", json={"origin": {"lat": 12.9150, "lon": 77.6350}, "destination": {"lat": 12.9345, "lon": 77.6110}}).json()
    assert len(rt["routes"]) > 0
    
    # 7. Propose Clearance
    prop = client.post(f"/api/v1/incidents/{inc_id}/clearance", json={"clearance_findings": "Water drained."}, headers={"Authorization": "Bearer usr-resp-2"}).json()
    assert prop["status"] == "clearance_proposed"
    
    # 8. Reopen
    clr = client.post(f"/api/v1/incidents/{inc_id}/restriction", json={"action": "authorize_reopen"}, headers={"Authorization": "Bearer usr-admin-1"}).json()
    assert clr["status"] == "cleared"
    assert clr["is_blocked"] is False
