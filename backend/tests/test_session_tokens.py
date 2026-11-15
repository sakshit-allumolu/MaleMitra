from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.config import settings
from backend.app.api import auth

client = TestClient(app)


def _login(email="admin@malemitra.in"):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return r.json()


def _me(token):
    return client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})


def test_login_returns_signed_token_not_bare_user_id():
    body = _login()
    assert body["access_token"] != body["user_id"]
    assert body["access_token"].startswith(body["user_id"] + ".")
    me = _me(body["access_token"])
    assert me.status_code == 200 and me.json()["role"] == "admin"


def test_tampered_signature_and_swapped_user_are_rejected():
    tok = _login("citizen@malemitra.in")["access_token"]
    assert _me(tok[:-1] + ("0" if tok[-1] != "0" else "1")).status_code == 401
    # Re-use a citizen signature on the admin id
    _, version, expiry, sig = tok.rsplit(".", 3)
    assert _me(f"usr-admin-1.{version}.{expiry}.{sig}").status_code == 401


def test_expired_token_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "SESSION_TTL_SECONDS", -10)
    tok = auth.create_session_token("usr-admin-1")
    assert _me(tok).status_code == 401


def test_bare_user_id_rejected_when_legacy_tokens_disabled(monkeypatch):
    assert _me("usr-admin-1").status_code == 200   # default keeps local dev / existing tests working
    monkeypatch.setattr(settings, "ALLOW_LEGACY_TOKENS", False)
    assert _me("usr-admin-1").status_code == 401
    # signed tokens still work
    assert _me(auth.create_session_token("usr-admin-1")).status_code == 200


def test_signed_token_works_for_role_protected_endpoint(monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_LEGACY_TOKENS", False)
    for k in ("ORCHESTRATE_API_KEY", "ORCHESTRATE_INSTANCE_URL", "ORCHESTRATE_AGENT_ID"):
        monkeypatch.setattr(settings, k, "")   # independent of the developer's .env
    cit = _login("citizen@malemitra.in")["access_token"]
    adm = _login("admin@malemitra.in")["access_token"]
    assert client.post("/api/v1/agents/chat", json={"message": "hi"},
                       headers={"Authorization": f"Bearer {cit}"}).status_code == 403
    # admin passes auth + role check and reaches the handler (503 = Orchestrate not configured)
    r = client.post("/api/v1/agents/chat", json={"message": "hi"}, headers={"Authorization": f"Bearer {adm}"})
    assert r.status_code == 503
