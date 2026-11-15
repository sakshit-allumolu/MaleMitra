"""A report within a few metres of an open incident is counted on it instead of opening a new one."""
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.config import settings
from backend.app.models.database import get_db_connection
from backend.app.services.graph_service import road_graph

client = TestClient(app)
ADMIN = {"Authorization": "Bearer usr-admin-1"}
CITIZENS = [{"Authorization": f"Bearer {u}"} for u in ("usr-citizen-1", "usr-citizen-2")]

# 1e-5 degrees of latitude is about 1.1 m.
M = 1.1e-5


@pytest.fixture(autouse=True)
def _merge_on(monkeypatch):
    monkeypatch.setattr(settings, "DUPLICATE_RADIUS_M", 10.0)
    yield
    for e in road_graph.edges.values():
        e.is_blocked = False


@pytest.fixture
def spot():
    """A location no other test uses, with any leftover open incident there closed first."""
    lat, lon = 12.9505, 77.6005
    conn = get_db_connection()
    conn.execute("UPDATE incidents SET status = 'rejected' WHERE abs(lat - ?) < 0.001 AND abs(lon - ?) < 0.001",
                 (lat, lon))
    conn.commit()
    conn.close()
    return lat, lon


def _report(lat, lon, who=0, severity="medium", desc="Standing water."):
    r = client.post("/api/v1/reports", json={"lat": lat, "lon": lon, "type": "waterlogging",
                                             "severity": severity, "description": desc}, headers=CITIZENS[who])
    assert r.status_code == 200, r.text
    return r.json()


def _incident(iid):
    return client.get(f"/api/v1/incidents/{iid}", headers=ADMIN).json()


def _open_count_near(lat, lon):
    conn = get_db_connection()
    n = conn.execute("SELECT COUNT(*) FROM incidents WHERE abs(lat - ?) < 0.0005 AND abs(lon - ?) < 0.0005 "
                     "AND status NOT IN ('rejected', 'cleared')", (lat, lon)).fetchone()[0]
    conn.close()
    return n


def test_nearby_report_is_counted_on_the_older_incident(spot):
    lat, lon = spot
    first = _report(lat, lon, who=0)
    second = _report(lat + 5 * M, lon, who=1, desc="Same flooding, seen from the other side.")
    assert second["id"] == first["id"] and second["merged"] is True
    assert _open_count_near(lat, lon) == 1
    inc = _incident(first["id"])
    assert inc["reports_count"] == 2
    texts = [e["text_notes"] for e in inc["evidence_list"]]
    assert any("Same flooding" in t for t in texts)  # the new report's evidence is kept


def test_report_outside_the_radius_opens_a_new_incident(spot):
    lat, lon = spot
    first = _report(lat, lon, who=0)
    far = _report(lat + 30 * M, lon, who=1)
    assert far["id"] != first["id"] and not far.get("merged")


def test_same_citizen_reporting_twice_is_not_double_counted(spot):
    lat, lon = spot
    first = _report(lat, lon, who=0)
    again = _report(lat + 2 * M, lon, who=0)
    assert again["id"] == first["id"] and again["already_reported"] is True
    assert _incident(first["id"])["reports_count"] == 1


def test_enough_independent_reports_escalate_severity(spot):
    lat, lon = spot
    first = _report(lat, lon, who=0, severity="low")
    assert _incident(first["id"])["severity"] == "low"
    _report(lat + 1 * M, lon, who=1, severity="low")
    assert _incident(first["id"])["severity"] == "low"          # two reports: not yet
    # a third and fourth distinct reporter
    conn = get_db_connection()
    for uid in ("usr-test-merge-c", "usr-test-merge-d"):
        conn.execute("INSERT INTO users (id, name, email, role, password_hash, active, created_at) "
                     "VALUES (?, ?, ?, 'citizen', 'x', 1, '2026-01-01') ON CONFLICT DO NOTHING",
                     (uid, uid, f"{uid}@t.in"))
    conn.commit()
    conn.close()
    h = lambda u: {"Authorization": f"Bearer {u}"}
    for n, uid in enumerate(("usr-test-merge-c", "usr-test-merge-d"), start=2):
        r = client.post("/api/v1/reports", json={"lat": lat + n * M, "lon": lon, "type": "waterlogging",
                                                 "severity": "low", "description": "Water again."}, headers=h(uid))
        assert r.status_code == 200
        if n == 2:
            assert _incident(first["id"])["severity"] == "high"  # three reports -> at least high
    assert _incident(first["id"])["reports_count"] == 4
    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE id LIKE 'usr-test-merge-%'")
    conn.commit()
    conn.close()


def test_reporter_cannot_inflate_severity_alone(spot):
    lat, lon = spot
    first = _report(lat, lon, who=0, severity="low")
    _report(lat + M, lon, who=1, severity="critical")   # a single other reporter claims "critical"
    assert _incident(first["id"])["severity"] == "low"


def test_closed_incident_does_not_absorb_new_reports(spot):
    lat, lon = spot
    first = _report(lat, lon, who=0)
    assert client.post(f"/api/v1/incidents/{first['id']}/restriction", json={"action": "reject"},
                       headers=ADMIN).status_code == 200
    fresh = _report(lat, lon, who=1)
    assert fresh["id"] != first["id"]


def test_merge_is_audited_and_visible_on_the_timeline(spot):
    lat, lon = spot
    first = _report(lat, lon, who=0)
    _report(lat + M, lon, who=1)
    audit = client.get("/api/v1/events/audit", headers=ADMIN).json()["audits"]
    assert any(a["action"] == "MERGE_REPORT" and a["entity_id"] == first["id"] for a in audit)
    events = client.get("/api/v1/events/agent", headers=ADMIN).json()["events"]
    assert any(e.get("incident_id") == first["id"] and "merge" in str(e).lower() for e in events)


def test_a_merged_incident_cannot_be_withdrawn_by_its_first_reporter(spot):
    lat, lon = spot
    first = _report(lat, lon, who=0)
    _report(lat + M, lon, who=1)
    r = client.post(f"/api/v1/incidents/{first['id']}/withdraw", headers=CITIZENS[0])
    assert r.status_code == 409 and "also reported" in r.json()["detail"]


def test_merging_can_be_disabled(spot, monkeypatch):
    monkeypatch.setattr(settings, "DUPLICATE_RADIUS_M", 0.0)
    lat, lon = spot
    first = _report(lat, lon, who=0)
    second = _report(lat, lon, who=1)
    assert second["id"] != first["id"]
