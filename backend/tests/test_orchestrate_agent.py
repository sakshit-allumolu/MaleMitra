import json
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.config import settings
from backend.app.models.database import get_db_connection
from backend.app.services.graph_service import road_graph
from backend.app.services import orchestrate_client as oc
from backend.app.services.orchestrate_client import OrchestrateClient

client = TestClient(app)
ADMIN = {"Authorization": "Bearer usr-admin-1"}
RESP = {"Authorization": "Bearer usr-resp-1"}
CITIZEN = {"Authorization": "Bearer usr-citizen-1"}
KEY = "test-agent-key"
TOOL = {"X-API-Key": KEY}
T = "/api/v1/agent-tools"

# A road no other test reports on.
LOC = (12.9420, 77.6090)


@pytest.fixture(autouse=True)
def _agent_settings(monkeypatch):
    monkeypatch.setattr(settings, "AGENT_TOOL_API_KEY", KEY)
    yield
    for e in road_graph.edges.values():
        e.is_blocked = False


def _report():
    r = client.post("/api/v1/reports", json={
        "lat": LOC[0], "lon": LOC[1], "type": "waterlogging",
        "severity": "high", "description": "Standing water on the road."
    }, headers=CITIZEN)
    assert r.status_code == 200
    return r.json()


def _events(tool_action_prefix, incident_id=None):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM agent_events WHERE agent = 'watsonx_orchestrate' AND action LIKE ?",
        (tool_action_prefix + "%",)).fetchall()
    conn.close()
    return [dict(r) for r in rows if incident_id is None or r["incident_id"] == incident_id]


# ── Auth ───────────────────────────────────────────────────────────────────

def test_tools_closed_when_no_key_configured(monkeypatch):
    monkeypatch.setattr(settings, "AGENT_TOOL_API_KEY", "")
    r = client.post(f"{T}/list_open_incidents", json={}, headers=TOOL)
    assert r.status_code == 401


def test_list_open_incidents_accepts_request_without_body():
    # Orchestrate sends no body when the agent has no filter to pass.
    r = client.post(f"{T}/list_open_incidents", headers=TOOL)
    assert r.status_code == 200 and "incidents" in r.json()


def test_tools_reject_missing_and_wrong_key():
    assert client.post(f"{T}/list_open_incidents", json={}).status_code == 401
    assert client.post(f"{T}/list_open_incidents", json={}, headers={"X-API-Key": "nope"}).status_code == 401
    # A user bearer token is not an agent credential
    assert client.post(f"{T}/list_open_incidents", json={}, headers=ADMIN).status_code == 401


# ── Read tools ─────────────────────────────────────────────────────────────

def test_map_to_edge_and_bounds():
    r = client.post(f"{T}/map_to_edge", json={"lat": 12.935, "lon": 77.624}, headers=TOOL)
    assert r.status_code == 200
    assert r.json()["edge_id"] in road_graph.edges
    far = client.post(f"{T}/map_to_edge", json={"lat": 13.5, "lon": 77.6}, headers=TOOL)
    assert far.status_code == 422
    assert far.json()["detail"]["error"] == "out_of_bounds"


def test_list_and_context_tools():
    inc = _report()
    lst = client.post(f"{T}/list_open_incidents", json={}, headers=TOOL).json()
    assert any(i["id"] == inc["id"] for i in lst["incidents"])
    assert client.post(f"{T}/list_open_incidents", json={"status": "bogus"}, headers=TOOL).status_code == 422

    ctx = client.post(f"{T}/get_incident_context", json={"incident_id": inc["id"]}, headers=TOOL)
    assert ctx.status_code == 200
    body = ctx.json()
    assert body["incident"]["id"] == inc["id"]
    assert body["edge"]["edge_id"] == inc["road_edge_id"]
    assert "geometry" in body["edge"] and body["edge"]["geometry"] is None
    missing = client.post(f"{T}/get_incident_context", json={"incident_id": "inc-nope"}, headers=TOOL)
    assert missing.status_code == 422 and missing.json()["detail"]["error"] == "not_found"


def test_estimate_bpr_and_route():
    edge_id = next(iter(road_graph.edges))
    r = client.post(f"{T}/estimate_bpr_load", json={"edge_id": edge_id}, headers=TOOL).json()
    assert r["edge_id"] == edge_id and r["delay_s"] >= 0
    assert client.post(f"{T}/estimate_bpr_load", json={"edge_id": "edge-zzz"}, headers=TOOL).status_code == 422
    route = client.post(f"{T}/compute_route", json={
        "origin_lat": 12.93, "origin_lon": 77.62, "dest_lat": 12.97, "dest_lon": 77.64}, headers=TOOL)
    assert route.status_code == 200
    assert "fastest" in route.json()["routes"]
    assert "node_ids" not in route.json()["routes"]["fastest"]


# ── What-if is sandboxed and bounded ───────────────────────────────────────

def test_what_if_does_not_change_live_state_and_is_bounded():
    edge_id = next(iter(road_graph.edges))
    version = road_graph.graph_version
    r = client.post(f"{T}/run_ripple_what_if", json={"edge_ids": [edge_id]}, headers=TOOL)
    assert r.status_code == 200
    assert r.json()["simulated_blocked_edges"] == [edge_id]
    assert road_graph.edges[edge_id].is_blocked is False
    assert road_graph.graph_version == version

    too_many = list(road_graph.edges)[:6]
    assert client.post(f"{T}/run_ripple_what_if", json={"edge_ids": too_many}, headers=TOOL).status_code == 422
    assert client.post(f"{T}/run_ripple_what_if", json={"edge_ids": []}, headers=TOOL).status_code == 422
    assert client.post(f"{T}/run_ripple_what_if", json={"edge_ids": ["edge-zzz"]}, headers=TOOL).status_code == 422


# ── Recommendation guardrails ──────────────────────────────────────────────

def test_recommendation_respects_workflow_gates_and_never_changes_state():
    inc = _report()
    iid = inc["id"]
    rec = {"incident_id": iid, "action": "propose_block", "confidence": 0.9,
           "rationale": "Water depth is above 40cm on this road."}
    # propose_block needs field_verified; incident is only 'reported'
    gate = client.post(f"{T}/submit_recommendation", json=rec, headers=TOOL)
    assert gate.status_code == 422 and gate.json()["detail"]["error"] == "workflow_gate"

    ok = client.post(f"{T}/submit_recommendation",
                     json={**rec, "action": "request_triage"}, headers=TOOL)
    assert ok.status_code == 200 and ok.json()["recorded"] is True

    # Nothing about the incident or the road changed
    after = client.get("/api/v1/incidents", headers=ADMIN).json()
    mine = next(i for i in after if i["id"] == iid)
    assert mine["status"] == "reported" and mine["is_blocked"] is False
    assert road_graph.edges[inc["road_edge_id"]].is_blocked is False

    stored = _events("recommendation", iid)
    assert len(stored) == 1 and stored[0]["requires_approval"] == 1
    assert json.loads(stored[0]["result"])["action"] == "request_triage"

    got = client.get(f"/api/v1/agents/recommendation/{iid}", headers=ADMIN).json()
    assert got["recommendation"]["action"] == "request_triage"


def test_recommendation_input_validation():
    inc = _report()
    base = {"incident_id": inc["id"], "action": "monitor", "confidence": 0.5, "rationale": "Watching the situation."}
    assert client.post(f"{T}/submit_recommendation", json={**base, "action": "close_road_now"}, headers=TOOL).status_code == 422
    assert client.post(f"{T}/submit_recommendation", json={**base, "rationale": "short"}, headers=TOOL).status_code == 422
    assert client.post(f"{T}/submit_recommendation", json={**base, "confidence": 1.5}, headers=TOOL).status_code == 422
    assert client.post(f"{T}/submit_recommendation", json={**base, "incident_id": "inc-nope"}, headers=TOOL).status_code == 422


def test_closed_incident_gets_no_recommendations():
    inc = _report()
    rej = client.post(f"/api/v1/incidents/{inc['id']}/restriction", json={"action": "reject", "notes": "test"}, headers=ADMIN)
    assert rej.status_code == 200
    r = client.post(f"{T}/submit_recommendation", json={
        "incident_id": inc["id"], "action": "monitor", "confidence": 0.5,
        "rationale": "Watching the situation."}, headers=TOOL)
    assert r.status_code == 422 and r.json()["detail"]["error"] == "incident_closed"


# ── Audit logging ──────────────────────────────────────────────────────────

def test_every_tool_call_is_logged_including_rejections():
    inc = _report()
    iid = inc["id"]
    client.post(f"{T}/get_incident_context", json={"incident_id": iid}, headers=TOOL)
    client.post(f"{T}/submit_recommendation", json={
        "incident_id": iid, "action": "propose_reopen", "confidence": 0.4,
        "rationale": "Trying a gated action."}, headers=TOOL)
    ok = _events("tool:get_incident_context", iid)
    rejected = _events("tool:submit_recommendation", iid)
    assert ok and json.loads(ok[-1]["result"])["outcome"] == "ok"
    assert rejected and json.loads(rejected[-1]["result"])["outcome"] == "rejected"
    assert all(e["data_mode"] == "orchestrate" for e in ok + rejected)
    # surfaced through the existing timeline endpoint
    timeline = client.get("/api/v1/events/agent", headers=ADMIN).json()["events"]
    assert any(e["agent"] == "watsonx_orchestrate" for e in timeline)


# ── OpenAPI export ─────────────────────────────────────────────────────────

def test_openapi_spec_contains_only_agent_tools(monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://example.ngrok.app/")
    spec = client.get(f"{T}/spec").json()
    ops = {op["operationId"] for item in spec["paths"].values() for op in item.values()}
    assert ops == {"map_to_edge", "list_open_incidents", "list_responder_availability", "get_incident_context",
                   "compute_route", "estimate_bpr_load", "run_ripple_what_if", "submit_recommendation"}
    assert all(p.startswith(f"{T}/") for p in spec["paths"])
    assert spec["servers"][0]["url"] == "https://example.ngrok.app"
    assert spec["components"]["securitySchemes"]["ApiKeyAuth"]["name"] == "X-API-Key"


# ── Agents API + Orchestrate client ────────────────────────────────────────

@pytest.fixture
def unconfigured(monkeypatch):
    for k in ("ORCHESTRATE_API_KEY", "ORCHESTRATE_INSTANCE_URL", "ORCHESTRATE_AGENT_ID"):
        monkeypatch.setattr(settings, k, "")


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(settings, "ORCHESTRATE_API_KEY", "ibm-key")
    monkeypatch.setattr(settings, "ORCHESTRATE_INSTANCE_URL", "https://orch.example")
    monkeypatch.setattr(settings, "ORCHESTRATE_AGENT_ID", "agent-1")
    monkeypatch.setattr(settings, "ORCHESTRATE_IAM_URL", "https://iam.cloud.ibm.com/identity/token")
    monkeypatch.setattr(oc.orchestrate_client, "_token", None)
    monkeypatch.setattr(oc.orchestrate_client, "_token_expiry", 0.0)


def test_status_and_chat_degrade_gracefully_when_unconfigured(unconfigured):
    s = client.get("/api/v1/agents/status", headers=CITIZEN).json()
    assert s["configured"] is False
    assert set(s["missing_settings"]) == {"ORCHESTRATE_API_KEY", "ORCHESTRATE_INSTANCE_URL", "ORCHESTRATE_AGENT_ID"}
    assert client.get("/api/v1/agents/status").status_code == 401
    r = client.post("/api/v1/agents/chat", json={"message": "hi"}, headers=ADMIN)
    assert r.status_code == 503 and "not configured" in r.json()["detail"]


def test_chat_and_analyze_are_admin_only(unconfigured):
    assert client.post("/api/v1/agents/chat", json={"message": "hi"}, headers=CITIZEN).status_code == 403
    assert client.post("/api/v1/agents/chat", json={"message": "hi"}, headers=RESP).status_code == 403
    assert client.post("/api/v1/agents/analyze/inc-x", headers=RESP).status_code == 403
    assert client.get("/api/v1/agents/recommendation/inc-x", headers=CITIZEN).status_code == 403
    assert client.post("/api/v1/agents/analyze/inc-nope", headers=ADMIN).status_code == 404


class _Resp:
    def __init__(self, status, payload):
        self.status_code, self._p, self.text = status, payload, json.dumps(payload)

    def json(self):
        return self._p


def test_client_uses_platform_token_service_by_default(configured, monkeypatch):
    seen = {}

    def fake_post(url, **kw):
        if "/apikeys/token" in url:
            seen["token_body"] = kw["json"]
            return _Resp(200, {"token": "plat-tok", "expires_in": 7200})
        assert kw["headers"]["Authorization"] == "Bearer plat-tok"
        return _Resp(200, {"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(oc.settings, "ORCHESTRATE_IAM_URL",
                        "https://account-iam.platform.saas.ibm.com/api/2.0/apikeys/token")
    monkeypatch.setattr(oc.httpx, "post", fake_post)
    assert oc.orchestrate_client.chat("hello")["reply"] == "ok"
    assert seen["token_body"] == {"apikey": "ibm-key"}


def test_client_exchanges_token_caches_it_and_parses_reply(configured, monkeypatch):
    calls = []

    def fake_post(url, **kw):
        calls.append((url, kw))
        if "identity/token" in url:
            assert kw["data"]["grant_type"] == "urn:ibm:params:oauth:grant-type:apikey"
            assert kw["data"]["apikey"] == "ibm-key"
            return _Resp(200, {"access_token": "tok-1", "expires_in": 3600})
        assert url == "https://orch.example/v1/orchestrate/agent-1/chat/completions"
        assert kw["headers"]["Authorization"] == "Bearer tok-1"
        return _Resp(200, {"choices": [{"message": {"content": "Recommend request_triage."}}]})

    monkeypatch.setattr(oc.httpx, "post", fake_post)
    assert oc.orchestrate_client.chat("hello")["reply"] == "Recommend request_triage."
    oc.orchestrate_client.chat("again")
    assert sum(1 for u, _ in calls if "identity/token" in u) == 1   # token cached
    assert oc.orchestrate_client.status()["last_error"] is None
    assert "ibm-key" not in json.dumps(oc.orchestrate_client.status())   # status never echoes the API key


def test_analyze_returns_reply_and_stored_recommendation(configured, monkeypatch):
    inc = _report()

    def fake_post(url, **kw):
        if "identity/token" in url:
            return _Resp(200, {"access_token": "t", "expires_in": 3600})
        assert inc["id"] in kw["json"]["messages"][0]["content"]
        # Simulate the agent calling our tool during its run
        client.post(f"{T}/submit_recommendation", json={
            "incident_id": inc["id"], "action": "request_triage", "confidence": 0.8,
            "rationale": "Fresh report with high severity."}, headers=TOOL)
        return _Resp(200, {"output": "Triage first."})

    monkeypatch.setattr(oc.httpx, "post", fake_post)
    r = client.post(f"/api/v1/agents/analyze/{inc['id']}", headers=ADMIN)
    assert r.status_code == 200
    assert r.json()["reply"] == "Triage first."
    assert r.json()["recommendation"]["action"] == "request_triage"


def test_client_surfaces_iam_and_upstream_failures(configured, monkeypatch):
    monkeypatch.setattr(oc.httpx, "post", lambda url, **kw: _Resp(400, {"errorMessage": "bad key"}))
    r = client.post("/api/v1/agents/chat", json={"message": "hi"}, headers=ADMIN)
    assert r.status_code == 401 and "ORCHESTRATE_API_KEY" in r.json()["detail"]
    assert "rejected" in oc.orchestrate_client.status()["last_error"]

    def upstream_500(url, **kw):
        if "identity/token" in url:
            return _Resp(200, {"access_token": "t", "expires_in": 3600})
        return _Resp(500, {"error": "boom"})

    monkeypatch.setattr(oc.httpx, "post", upstream_500)
    r = client.post("/api/v1/agents/chat", json={"message": "hi"}, headers=ADMIN)
    assert r.status_code == 502


def test_extract_reply_shapes():
    ex = OrchestrateClient._extract_reply
    assert ex({"choices": [{"message": {"content": "a"}}]}) == "a"
    assert ex({"output": "b"}) == "b"
    assert ex({"messages": [{"role": "assistant", "content": "c"}]}) == "c"
    assert ex({"unknown": 1}) == ""


# ── Approve / dismiss a recommendation ─────────────────────────────────────

def _recommend(iid, action, rationale="Evidence-based reasoning for the admin."):
    r = client.post(f"{T}/submit_recommendation", json={
        "incident_id": iid, "action": action, "confidence": 0.9, "rationale": rationale}, headers=TOOL)
    assert r.status_code == 200, r.text
    return client.get(f"/api/v1/agents/recommendation/{iid}", headers=ADMIN).json()["recommendation"]


def _decide(event_id, body, headers=ADMIN):
    return client.post(f"/api/v1/agents/recommendations/{event_id}/decision", json=body, headers=headers)


def _status(iid):
    return next(i for i in client.get("/api/v1/incidents", headers=ADMIN).json() if i["id"] == iid)["status"]


def test_recommendation_starts_undecided():
    rec = _recommend(_report()["id"], "request_triage")
    assert rec["decision"] is None and rec["event_id"]


def test_approve_runs_the_workflow_action_and_records_decision():
    iid = _report()["id"]
    rec = _recommend(iid, "request_triage")
    r = _decide(rec["event_id"], {"decision": "approve"})
    assert r.status_code == 200
    assert _status(iid) == "under_review"
    assert r.json()["recommendation"]["decision"] == "approved"
    assert r.json()["recommendation"]["decided_by"] == "usr-admin-1"
    audit = client.get("/api/v1/events/audit", headers=ADMIN).json()
    assert any(a["action"] == "AGENT_RECOMMENDATION_APPROVED" and a["entity_id"] == rec["event_id"]
               for a in audit["audits"])
    # surfaced on the timeline too
    tl = client.get("/api/v1/events/agent", headers=ADMIN).json()["events"]
    assert any(e["event_id"] == rec["event_id"] and e["decision"] == "approved" for e in tl)


def test_dismiss_changes_nothing_but_the_record():
    iid = _report()["id"]
    rec = _recommend(iid, "request_triage")
    r = _decide(rec["event_id"], {"decision": "dismiss"})
    assert r.status_code == 200
    assert _status(iid) == "reported"
    assert r.json()["recommendation"]["decision"] == "dismissed"


def test_a_recommendation_can_only_be_decided_once():
    rec = _recommend(_report()["id"], "request_triage")
    assert _decide(rec["event_id"], {"decision": "dismiss"}).status_code == 200
    again = _decide(rec["event_id"], {"decision": "approve"})
    assert again.status_code == 409 and "already dismissed" in again.json()["detail"]


def test_stale_recommendation_cannot_be_approved_but_can_be_dismissed():
    iid = _report()["id"]
    rec = _recommend(iid, "request_triage")
    assert client.post(f"/api/v1/incidents/{iid}/review", json={"notes": "manual"}, headers=ADMIN).status_code == 200
    stale = _decide(rec["event_id"], {"decision": "approve"})
    assert stale.status_code == 409 and "Re-analyse" in stale.json()["detail"]
    assert _decide(rec["event_id"], {"decision": "dismiss"}).status_code == 200


def test_approving_reject_duplicate_rejects_the_incident():
    iid = _report()["id"]
    rec = _recommend(iid, "reject_duplicate", "Ten other reports on the same edge already cover this.")
    assert _decide(rec["event_id"], {"decision": "approve", "notes": "Duplicate of existing case"}).status_code == 200
    assert _status(iid) == "rejected"


def test_assign_team_approval_needs_a_team():
    iid = _report()["id"]
    client.post(f"/api/v1/incidents/{iid}/review", json={"notes": "triage"}, headers=ADMIN)
    rec = _recommend(iid, "assign_team")
    no_team = _decide(rec["event_id"], {"decision": "approve"})
    assert no_team.status_code == 422 and "team" in no_team.json()["detail"].lower()
    assert _status(iid) == "under_review"            # nothing happened, and it is still undecided
    ok = _decide(rec["event_id"], {"decision": "approve", "team_id": "team-alpha"})
    assert ok.status_code == 200 and _status(iid) == "assigned"


def test_advisory_actions_are_acknowledged_without_changing_state():
    iid = _report()["id"]
    rec = _recommend(iid, "monitor", "Low severity; keep watching the road.")
    assert _decide(rec["event_id"], {"decision": "approve"}).status_code == 200
    assert _status(iid) == "reported"


def test_only_admins_can_decide_and_input_is_validated():
    rec = _recommend(_report()["id"], "request_triage")
    assert _decide(rec["event_id"], {"decision": "approve"}, headers=CITIZEN).status_code == 403
    assert _decide(rec["event_id"], {"decision": "approve"}, headers=RESP).status_code == 403
    assert client.post(f"/api/v1/agents/recommendations/{rec['event_id']}/decision",
                       json={"decision": "approve"}).status_code == 401
    assert _decide(rec["event_id"], {"decision": "maybe"}).status_code == 422
    assert _decide("no-such-event", {"decision": "approve"}).status_code == 404



@pytest.mark.parametrize("value", ["", "open", "OPEN", "all", "active", " Reported "])
def test_list_open_incidents_tolerates_what_an_llm_sends_for_no_filter(value):
    r = client.post("/api/v1/agent-tools/list_open_incidents", json={"status": value}, headers=TOOL)
    assert r.status_code == 200, (value, r.text)


def test_list_open_incidents_still_rejects_a_real_typo():
    r = client.post("/api/v1/agent-tools/list_open_incidents", json={"status": "flooded"}, headers=TOOL)
    assert r.status_code == 422


def test_rejected_agent_tool_bodies_are_logged_with_the_reason(caplog):
    import logging
    with caplog.at_level(logging.WARNING, logger="malemitra"):
        r = client.post("/api/v1/agent-tools/get_incident_context", json={"wrong": 1}, headers=TOOL)
    assert r.status_code == 422
    assert any("agent tool call rejected" in m and "incident_id" in m and "wrong" in m for m in caplog.messages)


def test_tool_summaries_equal_operation_ids_so_orchestrate_names_match_the_agent_instructions():
    spec = client.get("/api/v1/agent-tools/spec").json()
    ops = [op for item in spec["paths"].values() for op in item.values()]
    assert len(ops) == 8
    assert all(op["summary"] == op["operationId"] for op in ops), [(o["operationId"], o["summary"]) for o in ops]
