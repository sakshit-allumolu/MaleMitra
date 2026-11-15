"""Auth revocation/lockout, security headers, routing resilience and incident pagination."""
import urllib.error

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.config import settings
from backend.app.services import agent_service

client = TestClient(app)
STRONG = "Str0ng!Pass"


def _register(email):
    r = client.post("/api/v1/auth/register", json={"name": "T User", "email": email, "password": STRONG})
    assert r.status_code == 200, r.text
    return r.json()


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def _login(email, pw=STRONG):
    return client.post("/api/v1/auth/login", json={"email": email, "password": pw})


# ── sessions ───────────────────────────────────────────────────────────────────

def test_logout_revokes_all_sessions():
    _register("logout@example.com")
    t1 = _login("logout@example.com").json()["access_token"]
    t2 = _login("logout@example.com").json()["access_token"]
    assert client.get("/api/v1/auth/me", headers=_auth(t1)).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=_auth(t1)).status_code == 200
    assert client.get("/api/v1/auth/me", headers=_auth(t1)).status_code == 401
    assert client.get("/api/v1/auth/me", headers=_auth(t2)).status_code == 401  # other device too
    assert _login("logout@example.com").status_code == 200  # can sign in again
    t3 = _login("logout@example.com").json()["access_token"]
    assert client.get("/api/v1/auth/me", headers=_auth(t3)).status_code == 200


def test_change_password_revokes_old_sessions_and_issues_new_token():
    _register("chg@example.com")
    old = _login("chg@example.com").json()["access_token"]
    bad = client.post("/api/v1/auth/change-password", headers=_auth(old),
                      json={"current_password": "wrong", "new_password": "N3w!Passw0rd"})
    assert bad.status_code == 403
    weak = client.post("/api/v1/auth/change-password", headers=_auth(old),
                       json={"current_password": STRONG, "new_password": "short"})
    assert weak.status_code == 422
    ok = client.post("/api/v1/auth/change-password", headers=_auth(old),
                     json={"current_password": STRONG, "new_password": "N3w!Passw0rd"})
    assert ok.status_code == 200
    assert client.get("/api/v1/auth/me", headers=_auth(old)).status_code == 401
    assert client.get("/api/v1/auth/me", headers=_auth(ok.json()["access_token"])).status_code == 200
    assert _login("chg@example.com").status_code == 401
    assert _login("chg@example.com", "N3w!Passw0rd").status_code == 200


def test_reset_password_revokes_existing_sessions():
    _register("rst@example.com")
    tok = _login("rst@example.com").json()["access_token"]
    dbg = client.post("/api/v1/auth/forgot-password", json={"email": "rst@example.com"}).json()["debug_token"]
    assert client.post("/api/v1/auth/reset-password",
                       json={"token": dbg, "new_password": "R3set!Passw0rd"}).status_code == 200
    assert client.get("/api/v1/auth/me", headers=_auth(tok)).status_code == 401


def test_account_lockout_after_repeated_failures(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_PER_MIN", 1000)
    monkeypatch.setattr(settings, "LOGIN_MAX_FAILURES", 3)
    _register("lock@example.com")
    for _ in range(3):
        assert _login("lock@example.com", "nope").status_code == 401
    r = _login("lock@example.com")  # correct password, but locked
    assert r.status_code == 429 and "Retry-After" in r.headers
    # a different account is unaffected
    assert _login("citizen@malemitra.in", "demo123").status_code == 200


def test_successful_login_resets_failure_counter(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_PER_MIN", 1000)
    monkeypatch.setattr(settings, "LOGIN_MAX_FAILURES", 3)
    _register("reset-count@example.com")
    for _ in range(2):
        _login("reset-count@example.com", "nope")
    assert _login("reset-count@example.com").status_code == 200
    for _ in range(2):
        assert _login("reset-count@example.com", "nope").status_code == 401
    assert _login("reset-count@example.com").status_code == 200


# ── headers ────────────────────────────────────────────────────────────────────

def test_security_headers_present(monkeypatch):
    r = client.get("/api/v1/health")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert "permissions-policy" in r.headers
    assert "strict-transport-security" not in r.headers  # plain http
    monkeypatch.setattr(settings, "HSTS_ENABLED", True)
    r = TestClient(app, base_url="https://testserver").get("/api/v1/health")
    assert "max-age=" in r.headers["strict-transport-security"]


# ── pagination ─────────────────────────────────────────────────────────────────

def test_incident_list_pagination_and_total_header():
    h = _auth("usr-admin-1")
    full = client.get("/api/v1/incidents", headers=h)
    total = int(full.headers["x-total-count"])
    assert total == len(full.json()) and total >= 3
    page = client.get("/api/v1/incidents?limit=2&offset=1", headers=h)
    assert [i["id"] for i in page.json()] == [i["id"] for i in full.json()[1:3]]
    assert int(page.headers["x-total-count"]) == total
    assert client.get("/api/v1/incidents?limit=0", headers=h).status_code == 422
    assert client.get("/api/v1/incidents?limit=100000", headers=h).status_code == 422


# ── routing resilience ─────────────────────────────────────────────────────────

def _fail(monkeypatch, calls):
    def boom(*a, **k):
        calls.append(1)
        raise urllib.error.URLError("down")
    monkeypatch.setattr(agent_service.urllib.request, "urlopen", boom)


def test_osrm_circuit_breaker_stops_hitting_network(monkeypatch):
    agent_service._osrm_reset()
    calls = []
    _fail(monkeypatch, calls)
    for i in range(10):
        assert agent_service._osrm_request(f"http://osrm.invalid/{i}") is None
    assert len(calls) == settings.OSRM_BREAKER_THRESHOLD  # then the breaker opens
    agent_service._osrm_reset()


def test_osrm_responses_are_cached(monkeypatch):
    agent_service._osrm_reset()
    calls = []

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"code": "Ok", "routes": []}'

    def fake(*a, **k):
        calls.append(1)
        return Resp()
    monkeypatch.setattr(agent_service.urllib.request, "urlopen", fake)
    for _ in range(5):
        assert agent_service._osrm_request("http://osrm.invalid/x")["code"] == "Ok"
    assert len(calls) == 1
    agent_service._osrm_reset()


def test_compare_routes_falls_back_when_osrm_down(monkeypatch):
    agent_service._osrm_reset()
    _fail(monkeypatch, [])
    r = client.post("/api/v1/routes/compare", headers=_auth("usr-citizen-1"), json={
        "origin": {"lat": 12.9716, "lon": 77.5946}, "destination": {"lat": 12.9352, "lon": 77.6245}})
    assert r.status_code == 200, r.text
    assert r.json()["routes"], "graph fallback must still return routes"
    agent_service._osrm_reset()


def test_osrm_tls_verified_by_default_in_production(monkeypatch):
    monkeypatch.setattr(settings, "OSRM_VERIFY_TLS", True)
    ctx = agent_service._make_ssl_ctx()
    assert ctx.check_hostname is True
