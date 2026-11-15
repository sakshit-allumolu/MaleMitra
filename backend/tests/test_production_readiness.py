"""Tests for the production-readiness fixes: graph restore, simulation safety, auth hardening,
endpoint lockdown, input validation, rate limiting and health."""
import threading

import pytest
from fastapi.testclient import TestClient

from backend.app import ratelimit
from backend.app.config import Settings, production_problems, settings
from backend.app.main import app
from backend.app.models.database import get_db_connection, init_db
from backend.app.security import hash_password, verify_password
from backend.app.services.graph_service import road_graph
from backend.app.services.incident_service import incident_service
from backend.app.services.ripple_service import ripple_engine

client = TestClient(app)
ADMIN = {"Authorization": "Bearer usr-admin-1"}
CITIZEN = {"Authorization": "Bearer usr-citizen-1"}
RESPONDER = {"Authorization": "Bearer usr-resp-1"}


@pytest.fixture(autouse=True)
def _clean_graph():
    yield
    for e in road_graph.edges.values():
        e.is_blocked = False
        e.hazard_severity = "none"
        e.reported_hazards_count = 0


def _blocked():
    return {e_id for e_id, e in road_graph.edges.items() if e.is_blocked}


# ── 1. closures survive a restart ──────────────────────────────────────────────

def _blocked_incident():
    inc = client.post("/api/v1/reports", json={
        "lat": 12.9420, "lon": 77.6090, "type": "waterlogging", "severity": "critical",
        "description": "Underpass flooded."}, headers=CITIZEN).json()
    iid = inc["id"]
    client.post(f"/api/v1/incidents/{iid}/review", json={}, headers=ADMIN)
    client.post(f"/api/v1/incidents/{iid}/assign", json={"team_id": "team-alpha"}, headers=ADMIN)
    client.post(f"/api/v1/incidents/{iid}/verify", json={"findings": "55cm, impassable"}, headers=RESPONDER)
    r = client.post(f"/api/v1/incidents/{iid}/restriction", json={"action": "authorize_block"}, headers=ADMIN)
    assert r.status_code == 200, r.text
    return iid, inc["road_edge_id"]


def test_blocked_roads_are_restored_from_the_database_after_a_restart():
    iid, edge_id = _blocked_incident()
    assert edge_id in _blocked()

    # Simulate a process restart: in-memory graph state is lost.
    for e in road_graph.edges.values():
        e.is_blocked = False
        e.hazard_severity = "none"
        e.reported_hazards_count = 0
    assert edge_id not in _blocked()

    version_before = road_graph.graph_version
    summary = incident_service.restore_graph_state()

    assert edge_id in _blocked()
    assert road_graph.edges[edge_id].hazard_severity != "none"
    assert summary["blocked_edges"] >= 1
    assert road_graph.graph_version > version_before
    client.post(f"/api/v1/incidents/{iid}/restriction", json={"action": "authorize_reopen"}, headers=ADMIN)


def test_restore_is_idempotent_and_drops_stale_in_memory_blocks():
    road_graph.edges["edge-9"].is_blocked = True   # not backed by any incident
    incident_service.restore_graph_state()
    first = _blocked()
    incident_service.restore_graph_state()
    assert _blocked() == first
    assert "edge-9" not in first or any(
        r["road_edge_id"] == "edge-9" for r in get_db_connection().execute(
            "SELECT road_edge_id FROM incidents WHERE status = 'blocked'"))


# ── 2. simulations are safe ────────────────────────────────────────────────────

def test_simulation_restores_live_state_even_when_it_raises(monkeypatch):
    road_graph.edges["edge-9"].is_blocked = True
    flows_before = {k: e.simulated_flow for k, e in road_graph.edges.items()}

    def boom(*a, **k):
        raise RuntimeError("simulated failure mid-run")

    monkeypatch.setattr(road_graph, "compute_dijkstra", boom)
    with pytest.raises(RuntimeError):
        ripple_engine.run_simulation(custom_blocked_edge_ids=["edge-3"])
    monkeypatch.undo()

    assert _blocked() == {"edge-9"}
    assert {k: e.simulated_flow for k, e in road_graph.edges.items()} == flows_before


def test_what_if_does_not_overwrite_live_flows_but_current_state_run_does():
    for e in road_graph.edges.values():
        e.simulated_flow = 0
    ripple_engine.run_simulation(custom_blocked_edge_ids=["edge-7"])
    assert all(e.simulated_flow == 0 for e in road_graph.edges.values())
    ripple_engine.run_for_current_state()
    assert any(e.simulated_flow > 0 for e in road_graph.edges.values())


def test_run_simulation_holds_the_graph_lock_while_it_mutates_state():
    """Direct proof of the locking contract: another thread cannot take the lock mid-simulation."""
    held_during_run = []
    original = ripple_engine._run_simulation

    def spy(*a, **k):
        got = []
        t = threading.Thread(target=lambda: got.append(road_graph.lock.acquire(blocking=False)))
        t.start()
        t.join()
        if got and got[0]:
            road_graph.lock.release()
        held_during_run.append(not got[0])
        return original(*a, **k)

    ripple_engine._run_simulation = spy
    try:
        ripple_engine.run_simulation(custom_blocked_edge_ids=["edge-3"])
    finally:
        ripple_engine._run_simulation = original
    assert held_during_run == [True]


def test_startup_restores_the_graph_from_the_database():
    iid, edge_id = _blocked_incident()
    for e in road_graph.edges.values():
        e.is_blocked = False
    with TestClient(app):          # entering the context runs the lifespan startup
        assert edge_id in _blocked()
    client.post(f"/api/v1/incidents/{iid}/restriction", json={"action": "authorize_reopen"}, headers=ADMIN)


# ── 3. passwords & production config ───────────────────────────────────────────

def test_passwords_are_salted_and_verify():
    a, b = hash_password("Sup3r-secret!"), hash_password("Sup3r-secret!")
    assert a != b and a.startswith("scrypt$")
    assert verify_password("Sup3r-secret!", a) == (True, False)
    assert verify_password("wrong", a)[0] is False


def test_legacy_hashes_verify_and_are_flagged_for_upgrade():
    import hashlib
    legacy = hashlib.sha256(b"Old-pass1!").hexdigest()
    assert verify_password("Old-pass1!", legacy) == (True, True)
    assert verify_password("nope", legacy)[0] is False


def test_legacy_plaintext_is_refused_outside_demo_mode(monkeypatch):
    assert verify_password("demo123", "demo123") == (True, True)
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    assert verify_password("demo123", "demo123")[0] is False


def test_login_upgrades_legacy_hash_to_scrypt():
    conn = get_db_connection()
    conn.execute("UPDATE users SET password_hash = 'demo123' WHERE id = 'usr-citizen-2'")
    conn.commit()
    conn.close()
    r = client.post("/api/v1/auth/login", json={"email": "kiran@malemitra.in", "password": "demo123"})
    assert r.status_code == 200
    conn = get_db_connection()
    stored = conn.execute("SELECT password_hash FROM users WHERE id = 'usr-citizen-2'").fetchone()[0]
    conn.close()
    assert stored.startswith("scrypt$")


def test_production_problems_flag_insecure_defaults():
    insecure = Settings(DEMO_MODE=False)
    assert len(production_problems(insecure)) >= 2
    safe = Settings(DEMO_MODE=False, JWT_SECRET="x" * 40, ALLOW_LEGACY_TOKENS=False, CORS_ORIGINS=["https://a.example"])
    assert production_problems(safe) == []


def test_app_refuses_to_start_insecurely_outside_demo_mode(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    with pytest.raises(RuntimeError, match="insecure"):
        with TestClient(app):
            pass


def test_admin_signup_requires_demo_code_and_is_closed_outside_demo_mode(monkeypatch):
    body = {"name": "New Admin", "email": "newadmin@t.in", "password": "Str0ng-pass!", "role": "admin"}
    assert client.post("/api/v1/auth/register", json={**body, "admin_code": "wrong"}).status_code == 403
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    assert client.post("/api/v1/auth/register", json={**body, "admin_code": "bbmp2026"}).status_code == 403
    r = client.post("/api/v1/auth/register", json={**body, "email": "newcit@t.in", "role": "citizen"})
    assert r.status_code == 200 and r.json()["role"] == "citizen"


def test_admin_can_create_responder_and_others_cannot():
    body = {"name": "Field Officer", "email": "field1@t.in", "password": "Str0ng-pass!",
            "role": "responder", "team_id": "team-beta"}
    assert client.post("/api/v1/auth/users", json=body, headers=CITIZEN).status_code == 403
    r = client.post("/api/v1/auth/users", json=body, headers=ADMIN)
    assert r.status_code == 200 and r.json()["team_id"] == "team-beta"
    assert client.post("/api/v1/auth/users", json={**body, "email": "field2@t.in", "team_id": "nope"},
                       headers=ADMIN).status_code == 422


def test_reset_token_is_hidden_outside_demo_mode_and_stored_hashed(monkeypatch):
    demo = client.post("/api/v1/auth/forgot-password", json={"email": "citizen@malemitra.in"}).json()
    token = demo["debug_token"]
    assert token
    conn = get_db_connection()
    stored = [r[0] for r in conn.execute("SELECT token FROM password_reset_tokens")]
    conn.close()
    assert token not in stored

    monkeypatch.setattr(settings, "DEMO_MODE", False)
    prod = client.post("/api/v1/auth/forgot-password", json={"email": "citizen@malemitra.in"}).json()
    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@t.in"}).json()
    assert prod["debug_token"] is None and prod["message"] == unknown["message"]

def test_reset_token_can_be_hidden_while_demo_mode_stays_on(monkeypatch):
    monkeypatch.setattr(settings, "EXPOSE_RESET_TOKEN", False)
    r = client.post("/api/v1/auth/forgot-password", json={"email": "citizen@malemitra.in"}).json()
    assert r["debug_token"] is None


def test_reset_password_flow_still_works():
    token = client.post("/api/v1/auth/forgot-password", json={"email": "kiran@malemitra.in"}).json()["debug_token"]
    r = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "Brand-new1!"})
    assert r.status_code == 200
    assert client.post("/api/v1/auth/login", json={"email": "kiran@malemitra.in", "password": "Brand-new1!"}).status_code == 200
    assert client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "Brand-new2!"}).status_code == 400
    # restore the demo password for other tests
    client.post("/api/v1/auth/forgot-password", json={"email": "kiran@malemitra.in"})
    conn = get_db_connection()
    conn.execute("UPDATE users SET password_hash = ? WHERE email = 'kiran@malemitra.in'", (hash_password("demo123"),))
    conn.commit()
    conn.close()


def test_deactivated_users_cannot_log_in_or_use_old_tokens():
    tok = client.post("/api/v1/auth/login", json={"email": "responder2@malemitra.in", "password": "demo123"}).json()["access_token"]
    conn = get_db_connection()
    conn.execute("UPDATE users SET active = 0 WHERE id = 'usr-resp-2'")
    conn.commit()
    conn.close()
    try:
        assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"}).status_code == 401
        assert client.post("/api/v1/auth/login", json={"email": "responder2@malemitra.in", "password": "demo123"}).status_code == 401
    finally:
        conn = get_db_connection()
        conn.execute("UPDATE users SET active = 1 WHERE id = 'usr-resp-2'")
        conn.commit()
        conn.close()


# ── 4. endpoint lockdown ───────────────────────────────────────────────────────

@pytest.mark.parametrize("path", ["/api/v1/events/agent", "/api/v1/events/audit", "/api/v1/teams"])
def test_operational_endpoints_require_login(path):
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("path", ["/api/v1/events/agent", "/api/v1/events/audit"])
def test_timeline_and_audit_are_admin_only(path):
    assert client.get(path, headers=CITIZEN).status_code == 403
    assert client.get(path, headers=RESPONDER).status_code == 403
    assert client.get(path, headers=ADMIN).status_code == 200


def test_benchmark_and_impact_require_auth():
    assert client.get("/api/v1/simulations/benchmark/run").status_code == 401
    assert client.get("/api/v1/simulations/benchmark/run", headers=CITIZEN).status_code == 403
    assert client.get("/api/v1/simulations/benchmark/run", headers=ADMIN).status_code == 200
    assert client.get("/api/v1/simulations/x/impact").status_code == 401


def test_team_status_is_validated_and_scoped():
    assert client.post("/api/v1/teams/team-alpha/status?status=hacked", headers=ADMIN).status_code == 422
    assert client.post("/api/v1/teams/team-beta/status?status=available", headers=RESPONDER).status_code == 403
    assert client.post("/api/v1/teams/team-alpha/status?status=available", headers=RESPONDER).status_code == 200
    assert client.post("/api/v1/teams/nope/status?status=available", headers=ADMIN).status_code == 404


def test_inject_takes_a_json_body_and_rejects_unknown_edges():
    assert client.post("/api/v1/simulations/r/inject", json={"edge_ids": ["edge-7"]}, headers=ADMIN).status_code == 200
    assert client.post("/api/v1/simulations/r/inject", json={"edge_ids": ["bogus"]}, headers=ADMIN).status_code == 422
    assert client.post("/api/v1/simulations/r/inject", json={"edge_ids": ["edge-7"]}, headers=CITIZEN).status_code == 403


def test_simulation_inputs_are_bounded():
    assert client.post("/api/v1/simulations", json={"trip_count": 100000}, headers=CITIZEN).status_code == 422
    assert client.post("/api/v1/simulations", json={"iterations": 999}, headers=CITIZEN).status_code == 422
    assert client.post("/api/v1/simulations", json={"custom_blocked_edge_ids": ["zzz"]}, headers=CITIZEN).status_code == 422


def test_sse_stream_does_not_leak_agent_events_and_unknown_api_paths_404():
    assert client.get("/api/v1/does-not-exist").status_code == 404


# ── input validation ───────────────────────────────────────────────────────────

def _report(**over):
    body = {"lat": 12.9420, "lon": 77.6090, "type": "waterlogging", "severity": "high", "description": "Water on road."}
    body.update(over)
    return client.post("/api/v1/reports", json=body, headers=CITIZEN)


def test_report_validation():
    assert _report(severity="apocalyptic").status_code == 422
    assert _report(type="ufo").status_code == 422
    assert _report(description="x" * 5000).status_code == 422
    assert _report(description="").status_code == 422
    assert _report(photo_url="javascript:alert(1)").status_code == 422
    assert _report(photo_url="https://example.com/p.jpg").status_code == 200
    assert _report(lat=13.5, lon=77.5).status_code == 422          # valid Karnataka, outside service area
    assert _report(lat=0.0).status_code == 422


def test_workflow_payload_validation():
    assert client.post("/api/v1/incidents/x/restriction", json={"action": "explode"}, headers=ADMIN).status_code == 422
    assert client.post("/api/v1/incidents/x/verify", json={"findings": "ok", "water_depth_cm": -5}, headers=RESPONDER).status_code == 422
    assert client.post("/api/v1/incidents/x/verify", json={"findings": "ok", "recommended_action": "nuke"}, headers=RESPONDER).status_code == 422


# ── rate limiting ──────────────────────────────────────────────────────────────

def test_login_is_rate_limited_per_ip(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_PER_MIN", 3)
    ratelimit.reset()
    codes = [client.post("/api/v1/auth/login", json={"email": "a@b.in", "password": "x"}).status_code for _ in range(5)]
    assert codes[:3] == [401, 401, 401] and codes[3:] == [429, 429]


def test_report_creation_is_rate_limited_per_account(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_REPORTS_PER_HOUR", 2)
    ratelimit.reset()
    codes = [_report().status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    assert client.post("/api/v1/reports", json={"lat": 12.94, "lon": 77.61, "description": "other user"},
                       headers=ADMIN).status_code == 200


def test_simulations_are_rate_limited(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_SIMULATIONS_PER_MIN", 2)
    ratelimit.reset()
    codes = [client.post("/api/v1/simulations", json={}, headers=CITIZEN).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


# ── 5. database & health ───────────────────────────────────────────────────────

def test_health_reports_database_and_graph_state():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy" and body["checks"] == {"database": True, "road_graph": True}


def test_health_is_503_when_database_is_unreachable(monkeypatch):
    from backend.app.api import health

    def broken():
        raise RuntimeError("db down")

    monkeypatch.setattr(health, "get_db_connection", broken)
    r = client.get("/api/v1/health")
    assert r.status_code == 503 and r.json()["status"] == "unhealthy"


def test_database_uses_wal_and_has_indexes():
    from backend.app.models.database import is_postgres
    conn = get_db_connection()
    if is_postgres():
        idx = {r[0] for r in conn.execute(
            "SELECT indexname FROM pg_indexes WHERE schemaname = current_schema() AND tablename = 'incidents'")}
    else:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        idx = {r[1] for r in conn.execute("PRAGMA index_list(incidents)")}
    conn.close()
    assert "idx_incidents_status" in idx and "idx_incidents_edge" in idx


def test_demo_users_are_not_seeded_outside_demo_mode(monkeypatch, tmp_path):
    from backend.app.models.database import close_pools, is_postgres
    monkeypatch.setattr(settings, "DATABASE_PATH", str(tmp_path / "fresh.db"))
    original_schema = settings.DATABASE_SCHEMA
    if is_postgres():  # a brand-new schema plays the part of the fresh database file
        monkeypatch.setattr(settings, "DATABASE_SCHEMA", f"{original_schema}_fresh")
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "BOOTSTRAP_ADMIN_EMAIL", "root@city.gov")
    monkeypatch.setattr(settings, "BOOTSTRAP_ADMIN_PASSWORD", "Str0ng-pass!")
    init_db()
    conn = get_db_connection()
    emails = [r[0] for r in conn.execute("SELECT email FROM users")]
    conn.close()
    if is_postgres():
        import psycopg
        fresh = settings.DATABASE_SCHEMA
        monkeypatch.setattr(settings, "DATABASE_SCHEMA", original_schema)  # later fixtures use the shared schema
        close_pools()
        with psycopg.connect(settings.DATABASE_URL, autocommit=True) as c:
            c.execute(f'DROP SCHEMA IF EXISTS "{fresh}" CASCADE')
    assert emails == ["root@city.gov"]


def test_demo_accounts_are_deactivated_when_a_demo_db_is_run_in_production_mode(monkeypatch):
    # The shared test DB has demo users; switching demo mode off must disable them.
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    init_db()
    conn = get_db_connection()
    active = conn.execute("SELECT active FROM users WHERE id = 'usr-admin-1'").fetchone()[0]
    conn.execute("UPDATE users SET active = 1 WHERE id IN "
                 "('usr-citizen-1','usr-citizen-2','usr-admin-1','usr-resp-1','usr-resp-2')")
    conn.commit()
    conn.close()
    assert active == 0
