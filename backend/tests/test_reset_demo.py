"""reset_demo: only works in DEMO_MODE, restores the seeded demo state, keeps users and the TomTom counter."""
import pytest
from fastapi.testclient import TestClient

from backend.app import ratelimit
from backend.app.config import settings
from backend.app.main import app
from backend.app.models.database import get_db_connection
from backend.scripts import reset_demo

client = TestClient(app)
H = {"Authorization": "Bearer usr-citizen-1"}


def _count(sql, *args):
    conn = get_db_connection()
    try:
        return conn.execute(sql, args).fetchone()[0]
    finally:
        conn.close()


def test_reset_refuses_outside_demo_mode(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    with pytest.raises(SystemExit):
        reset_demo.reset()


def test_reset_restores_the_seeded_demo_state():
    # make a mess: an extra report, a login-lockout style counter, and a routing-budget hit
    r = client.post("/api/v1/reports", headers=H, json={
        "lat": 12.9610, "lon": 77.6000, "type": "waterlogging", "severity": "high",
        "description": "Water over the road near the junction"})
    assert r.status_code in (200, 201), r.text
    ratelimit.record("login_fail", "someone@example.org")
    ratelimit.record("tomtom_routing", "global")
    users_before = _count("SELECT COUNT(*) FROM users")

    out = reset_demo.reset()

    assert out["incidents_seeded"] == 2
    assert _count("SELECT COUNT(*) FROM incidents") == 2
    # the seeded Sony World incident is assigned to Team Alpha; nothing else may be left busy
    assert _count("SELECT COUNT(*) FROM response_teams WHERE status != 'available' AND id != 'team-alpha'") == 0
    assert _count("SELECT COUNT(*) FROM rate_hits WHERE bucket = 'login_fail'") == 0
    assert _count("SELECT COUNT(*) FROM rate_hits WHERE bucket = 'tomtom_routing'") == 1  # real quota is kept
    assert _count("SELECT COUNT(*) FROM users") == users_before
    ratelimit.reset()
