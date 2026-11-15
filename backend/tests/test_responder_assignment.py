"""Responder-level assignment: own tasks vs team queue, claiming, availability, agent recommendation."""
import uuid
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.config import settings
from backend.app.models.database import get_db_connection
from backend.app.services.graph_service import road_graph

client = TestClient(app)
ADMIN = {"Authorization": "Bearer usr-admin-1"}
CITIZEN = {"Authorization": "Bearer usr-citizen-1"}
TOOL = {"X-API-Key": "test-agent-key"}
T = "/api/v1/agent-tools"
TEAM = "team-gamma"
OTHER_TEAM = "team-beta"
LOC = (12.9420, 77.6090)


def _hdr(uid):
    return {"Authorization": f"Bearer {uid}"}


@pytest.fixture(autouse=True)
def _agent_key(monkeypatch):
    monkeypatch.setattr(settings, "AGENT_TOOL_API_KEY", "test-agent-key")
    yield
    for e in road_graph.edges.values():
        e.is_blocked = False


@pytest.fixture
def responders():
    """Two fresh responders on team-gamma, removed afterwards so other tests are unaffected."""
    tag = uuid.uuid4().hex[:6]
    ids = [f"usr-test-a-{tag}", f"usr-test-b-{tag}"]
    conn = get_db_connection()
    for i, uid in enumerate(ids):
        conn.execute(
            "INSERT INTO users (id, name, email, role, password_hash, team_id, active, created_at) "
            "VALUES (?, ?, ?, 'responder', 'x', ?, 1, '2026-01-01')",
            (uid, f"Test Responder {i}", f"{uid}@test.in", TEAM))
    conn.commit()
    conn.close()
    yield ids
    conn = get_db_connection()
    for uid in ids:
        conn.execute("UPDATE incidents SET assigned_responder_id = NULL WHERE assigned_responder_id = ?", (uid,))
        conn.execute("DELETE FROM users WHERE id = ?", (uid,))
    conn.commit()
    conn.close()


def _under_review():
    r = client.post("/api/v1/reports", json={
        "lat": LOC[0], "lon": LOC[1], "type": "waterlogging",
        "severity": "high", "description": "Standing water on the road."}, headers=CITIZEN)
    iid = r.json()["id"]
    assert client.post(f"/api/v1/incidents/{iid}/review", json={"notes": "t"}, headers=ADMIN).status_code == 200
    return iid


def _assign(iid, **body):
    return client.post(f"/api/v1/incidents/{iid}/assign", json={"team_id": TEAM, **body}, headers=ADMIN)


def _tasks(uid):
    return client.get("/api/v1/teams/me/tasks", headers=_hdr(uid)).json()


def _ids(items):
    return {i["id"] for i in items}


def test_assign_to_responder_shows_in_my_tasks_not_the_queue(responders):
    a, b = responders
    iid = _under_review()
    r = _assign(iid, responder_id=a)
    assert r.status_code == 200
    assert r.json()["assigned_responder_id"] == a and r.json()["assigned_responder_name"] == "Test Responder 0"
    assert iid in _ids(_tasks(a)["tasks"])
    other = _tasks(b)
    assert iid not in _ids(other["tasks"]) and iid not in _ids(other["queue"])


def test_assign_without_responder_goes_to_team_queue(responders):
    a, b = responders
    iid = _under_review()
    r = _assign(iid)
    assert r.status_code == 200 and r.json()["assigned_responder_id"] is None
    for uid in (a, b):
        t = _tasks(uid)
        assert iid in _ids(t["queue"]) and iid not in _ids(t["tasks"])


def test_assign_validates_team_and_responder(responders):
    a, _ = responders
    iid = _under_review()
    bad_team = client.post(f"/api/v1/incidents/{iid}/assign", json={"team_id": "team-nope"}, headers=ADMIN)
    assert bad_team.status_code == 404
    wrong_team = client.post(f"/api/v1/incidents/{iid}/assign",
                             json={"team_id": OTHER_TEAM, "responder_id": a}, headers=ADMIN)
    assert wrong_team.status_code == 422
    assert _assign(iid, responder_id="usr-citizen-1").status_code == 422


def test_free_responder_can_claim_from_queue(responders):
    a, b = responders
    iid = _under_review()
    _assign(iid)
    claim = client.post(f"/api/v1/incidents/{iid}/claim", headers=_hdr(a))
    assert claim.status_code == 200 and claim.json()["assigned_responder_id"] == a
    assert iid in _ids(_tasks(a)["tasks"])
    assert iid not in _ids(_tasks(b)["queue"])
    again = client.post(f"/api/v1/incidents/{iid}/claim", headers=_hdr(b))
    assert again.status_code == 409


def test_busy_responder_cannot_claim(responders):
    a, _ = responders
    first, second = _under_review(), _under_review()
    _assign(first, responder_id=a)
    _assign(second)
    assert _tasks(a)["is_free"] is False
    busy = client.post(f"/api/v1/incidents/{second}/claim", headers=_hdr(a))
    assert busy.status_code == 409 and "current task" in busy.json()["detail"]


def test_claim_rules_other_team_citizen_and_admin(responders):
    a, _ = responders
    iid = _under_review()
    client.post(f"/api/v1/incidents/{iid}/assign", json={"team_id": OTHER_TEAM}, headers=ADMIN)
    assert client.post(f"/api/v1/incidents/{iid}/claim", headers=_hdr(a)).status_code == 403
    assert client.post(f"/api/v1/incidents/{iid}/claim", headers=CITIZEN).status_code == 403
    assert client.post(f"/api/v1/incidents/{iid}/claim", headers=ADMIN).status_code == 403


def test_only_the_assigned_responder_can_work_the_incident(responders):
    a, b = responders
    iid = _under_review()
    _assign(iid, responder_id=a)
    body = {"findings": "Water 40cm", "water_depth_cm": 40, "is_impassable": True}
    assert client.post(f"/api/v1/incidents/{iid}/verify", json=body, headers=_hdr(b)).status_code == 403
    assert client.post(f"/api/v1/incidents/{iid}/verify", json=body, headers=_hdr(a)).status_code == 200
    assert client.post(f"/api/v1/incidents/{iid}/clearance", json={"clearance_findings": "dry"},
                       headers=_hdr(b)).status_code == 403
    # an admin is never locked out
    assert client.post(f"/api/v1/incidents/{iid}/clearance", json={"clearance_findings": "dry"},
                       headers=ADMIN).status_code == 200


def test_queue_incident_can_be_worked_by_a_teammate_but_not_another_team(responders):
    a, _ = responders
    iid = _under_review()
    _assign(iid)
    body = {"findings": "Water 20cm", "water_depth_cm": 20, "is_impassable": False}
    assert client.post(f"/api/v1/incidents/{iid}/verify", json=body, headers=_hdr("usr-resp-2")).status_code == 403
    assert client.post(f"/api/v1/incidents/{iid}/verify", json=body, headers=_hdr(a)).status_code == 200


def test_admin_can_reassign_a_queued_incident_to_a_responder(responders):
    a, _ = responders
    iid = _under_review()
    _assign(iid)
    assert _assign(iid, responder_id=a).json()["assigned_responder_id"] == a


def test_availability_lists_free_and_busy_responders(responders):
    a, b = responders
    iid = _under_review()
    _assign(iid, responder_id=a)
    listing = client.get("/api/v1/teams/responders", headers=ADMIN).json()["responders"]
    by_id = {r["id"]: r for r in listing}
    assert by_id[a]["is_free"] is False and by_id[a]["active_incident_ids"] == [iid]
    assert by_id[b]["is_free"] is True and by_id[b]["team_id"] == TEAM
    assert client.get("/api/v1/teams/responders", headers=_hdr(a)).status_code == 403


def test_team_stays_dispatched_until_its_last_incident_is_cleared(responders):
    a, b = responders
    one, two = _under_review(), _under_review()
    _assign(one, responder_id=a)
    _assign(two, responder_id=b)
    client.post(f"/api/v1/incidents/{one}/clearance", json={"clearance_findings": "dry"}, headers=_hdr(a))
    assert client.post(f"/api/v1/incidents/{one}/restriction", json={"action": "authorize_reopen"},
                       headers=ADMIN).status_code == 200

    def team_status():
        return next(t for t in client.get("/api/v1/teams", headers=ADMIN).json()["teams"] if t["id"] == TEAM)["status"]

    assert team_status() == "dispatched"        # incident `two` is still in the field
    client.post(f"/api/v1/incidents/{two}/clearance", json={"clearance_findings": "dry"}, headers=_hdr(b))
    client.post(f"/api/v1/incidents/{two}/restriction", json={"action": "authorize_reopen"}, headers=ADMIN)
    assert team_status() in ("available", "dispatched")  # other tests may leave unrelated gamma work open


def test_existing_database_is_migrated_with_the_new_column():
    from backend.app.models.database import table_columns
    conn = get_db_connection()
    cols = table_columns(conn, "incidents")
    conn.close()
    assert "assigned_responder_id" in cols


# ── Agent tool + recommendation ────────────────────────────────────────────

def test_agent_availability_tool_lists_responders(responders):
    a, b = responders
    _assign(_under_review(), responder_id=a)
    r = client.post(f"{T}/list_responder_availability", json={"team_id": TEAM}, headers=TOOL)
    assert r.status_code == 200
    by_id = {x["id"]: x for x in r.json()["responders"]}
    assert by_id[a]["is_free"] is False and by_id[b]["is_free"] is True
    assert client.post(f"{T}/list_responder_availability", headers=TOOL).status_code == 200  # body optional
    assert client.post(f"{T}/list_responder_availability", json={}).status_code == 401


def _recommend(iid, **extra):
    r = client.post(f"{T}/submit_recommendation", json={
        "incident_id": iid, "action": "assign_team", "confidence": 0.8,
        "rationale": "Nearest free responder on the team.", **extra}, headers=TOOL)
    return r


def _decide(iid, body):
    rec = client.get(f"/api/v1/agents/recommendation/{iid}", headers=ADMIN).json()["recommendation"]
    return rec, client.post(f"/api/v1/agents/recommendations/{rec['event_id']}/decision", json=body, headers=ADMIN)


def test_recommendation_rejects_a_busy_responder(responders):
    a, _ = responders
    _assign(_under_review(), responder_id=a)
    iid = _under_review()
    r = _recommend(iid, responder_id=a)
    assert r.status_code == 422 and r.json()["detail"]["error"] == "responder_busy"
    assert _recommend(iid, responder_id="usr-nobody").status_code == 422


def test_recommendation_responder_only_for_assign_team(responders):
    a, _ = responders
    iid = _under_review()
    r = client.post(f"{T}/submit_recommendation", json={
        "incident_id": iid, "action": "monitor", "confidence": 0.5,
        "rationale": "Keep watching this road.", "responder_id": a}, headers=TOOL)
    assert r.status_code == 422


def test_approving_uses_the_recommended_free_responder(responders):
    a, _ = responders
    iid = _under_review()
    assert _recommend(iid, responder_id=a).status_code == 200
    rec, res = _decide(iid, {"decision": "approve"})
    assert rec["team_id"] == TEAM and rec["responder_id"] == a
    assert res.status_code == 200 and res.json()["incident"]["assigned_responder_id"] == a


def test_approving_with_nobody_free_sends_incident_to_team_queue(responders):
    iid = _under_review()
    assert _recommend(iid, team_id=TEAM).status_code == 200
    _, res = _decide(iid, {"decision": "approve"})
    inc = res.json()["incident"]
    assert res.status_code == 200 and inc["assigned_team_id"] == TEAM and inc["assigned_responder_id"] is None


def test_admin_choice_overrides_the_recommendation(responders):
    a, b = responders
    iid = _under_review()
    _recommend(iid, responder_id=a)
    _, res = _decide(iid, {"decision": "approve", "team_id": TEAM, "responder_id": b})
    assert res.json()["incident"]["assigned_responder_id"] == b


def test_verified_responder_can_claim_next_incident_from_queue(responders):
    a, _ = responders
    first, second = _under_review(), _under_review()
    _assign(first, responder_id=a)
    _assign(second)  # in queue

    # Busy initially
    assert client.post(f"/api/v1/incidents/{second}/claim", headers=_hdr(a)).status_code == 409

    # Submit verification for first incident
    body = {"findings": "Water 40cm, flooded underpass", "water_depth_cm": 40, "is_impassable": True, "recommended_action": "authorize_closure"}
    v_res = client.post(f"/api/v1/incidents/{first}/verify", json=body, headers=_hdr(a))
    assert v_res.status_code == 200

    # Responder is now free to claim the second incident from queue
    claim_res = client.post(f"/api/v1/incidents/{second}/claim", headers=_hdr(a))
    assert claim_res.status_code == 200 and claim_res.json()["assigned_responder_id"] == a
