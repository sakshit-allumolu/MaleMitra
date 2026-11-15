import os
import struct
import zlib

import pytest
from fastapi.testclient import TestClient

from backend.app import ratelimit
from backend.app.config import settings
from backend.app.main import app
from backend.app.models.database import get_db_connection
from backend.app.services import reputation_service as rep
from backend.app.services import upload_service
from backend.app.services.graph_service import road_graph
from backend.app.services.incident_service import incident_service

client = TestClient(app)
ADMIN = {"Authorization": "Bearer usr-admin-1"}
CITIZEN = {"Authorization": "Bearer usr-citizen-1"}
CITIZEN2 = {"Authorization": "Bearer usr-citizen-2"}
RESP1 = {"Authorization": "Bearer usr-resp-1"}
SPOT = {"lat": 12.9420, "lon": 77.6090, "type": "waterlogging", "severity": "high", "description": "Flooded underpass"}


# ── tiny image builders (no imaging library is installed) ──────────────────────

def make_png(extra_chunks=()):
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\x00\x00")
    out = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
    for t, d in extra_chunks:
        out += chunk(t, d)
    return out + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def make_jpeg(with_exif=True, trailing=b""):
    def seg(marker, payload):
        return b"\xff" + bytes([marker]) + struct.pack(">H", len(payload) + 2) + payload
    out = b"\xff\xd8" + seg(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
    if with_exif:
        out += seg(0xE1, b"Exif\x00\x00GPS-LAT-12.94-LON-77.60-SECRET")
    out += seg(0xDB, b"\x00" + bytes(64))
    out += seg(0xC0, b"\x08\x00\x01\x00\x01\x01\x01\x11\x00")
    out += seg(0xC4, b"\x00" + bytes(16) + b"\x00")
    out += seg(0xDA, b"\x01\x01\x00\x00\x3f\x00") + b"\x12\x34\x56" + b"\xff\xd9"
    return out + trailing


@pytest.fixture(autouse=True)
def _tmp_uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    yield
    for e in road_graph.edges.values():
        e.is_blocked = False


def _upload(data, headers=CITIZEN):
    return client.post("/api/v1/uploads", content=data, headers={**headers, "Content-Type": "application/octet-stream"})


# ── C1: uploads ────────────────────────────────────────────────────────────────

def test_png_upload_roundtrip_and_served_safely():
    r = _upload(make_png())
    assert r.status_code == 201, r.text
    body = r.json()
    got = client.get(body["url"])
    assert got.status_code == 200 and got.headers["content-type"] == "image/png"
    assert got.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in got.headers["content-security-policy"]
    assert got.content.startswith(b"\x89PNG")


def test_exif_gps_is_stripped_from_jpegs():
    raw = make_jpeg(with_exif=True)
    assert b"GPS-LAT" in raw
    r = _upload(raw)
    assert r.status_code == 201, r.text
    stored = client.get(r.json()["url"]).content
    assert b"GPS-LAT" not in stored and b"Exif" not in stored
    assert stored.startswith(b"\xff\xd8") and stored.endswith(b"\xff\xd9")


def test_png_text_and_exif_chunks_are_stripped():
    raw = make_png([(b"tEXt", b"Comment\x00phone-gps-12.94"), (b"eXIf", b"GPSDATA")])
    stored = client.get(_upload(raw).json()["url"]).content
    assert b"phone-gps" not in stored and b"GPSDATA" not in stored


@pytest.mark.parametrize("payload,why", [
    (b"GIF89a" + bytes(50), "gif"),
    (b"<html><script>alert(1)</script></html>", "html"),
    (b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", "svg"),
    (b"%PDF-1.4 " + bytes(50), "pdf"),
    (b"MZ\x90\x00" + bytes(80), "exe"),
    (make_jpeg(trailing=b"<?php system($_GET['c']); ?>"), "jpeg with appended payload"),
    (make_png() + b"<script>alert(1)</script>", "png with appended payload"),
    (make_jpeg()[:40], "truncated jpeg"),
    (b"\x89PNG\r\n\x1a\n" + bytes(30), "png without chunks"),
])
def test_non_images_and_polyglots_are_rejected(payload, why):
    r = _upload(payload)
    assert r.status_code == 415, (why, r.status_code, r.text)


def test_content_type_and_filename_cannot_disguise_a_file():
    r = client.post("/api/v1/uploads", content=b"<html>x</html>",
                    headers={**CITIZEN, "Content-Type": "image/png", "X-Filename": "a.png"})
    assert r.status_code == 415


def test_empty_and_oversized_uploads_are_rejected(monkeypatch):
    assert _upload(b"").status_code == 400
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 200)
    assert _upload(make_jpeg() + bytes(500)).status_code == 413


def test_oversize_is_enforced_even_without_content_length(monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 1000)

    def gen():
        for _ in range(50):
            yield bytes(100)
    r = client.post("/api/v1/uploads", content=gen(), headers={**CITIZEN, "Content-Type": "application/octet-stream"})
    assert r.status_code == 413


def test_upload_requires_login():
    assert client.post("/api/v1/uploads", content=make_png()).status_code == 401


def test_uploads_are_rate_limited(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_UPLOADS_PER_HOUR", 2)
    ratelimit.reset()
    assert [_upload(make_png()).status_code for _ in range(3)] == [201, 201, 429]
    ratelimit.reset()


@pytest.mark.parametrize("bad", ["../../etc/passwd", "..%2f..%2fetc%2fpasswd", "0" * 32, "x" * 40, "%00"])
def test_photo_ids_cannot_traverse_or_guess(bad):
    assert client.get(f"/api/v1/uploads/{bad}").status_code == 404


def test_photo_id_on_a_report_must_belong_to_the_reporter():
    pid = _upload(make_png(), CITIZEN).json()["id"]
    stolen = client.post("/api/v1/reports", json={**SPOT, "photo_id": pid}, headers=CITIZEN2)
    assert stolen.status_code == 422
    assert client.post("/api/v1/reports", json={**SPOT, "photo_id": "f" * 32}, headers=CITIZEN).status_code == 422
    assert client.post("/api/v1/reports", json={**SPOT, "photo_id": "../x"}, headers=CITIZEN).status_code == 422
    ok = client.post("/api/v1/reports", json={**SPOT, "photo_id": pid}, headers=CITIZEN)
    assert ok.status_code == 200, ok.text
    conn = get_db_connection()
    row = conn.execute("SELECT photo_url FROM incident_reports WHERE incident_id = ?", (ok.json()["id"],)).fetchone()
    attached = conn.execute("SELECT attached FROM uploads WHERE id = ?", (pid,)).fetchone()["attached"]
    conn.close()
    assert row["photo_url"] == f"/api/v1/uploads/{pid}" and attached == 1


def test_unattached_uploads_are_purged_after_a_day():
    old = _upload(make_png()).json()["id"]
    path = upload_service.locate(old)[0]
    conn = get_db_connection()
    conn.execute("UPDATE uploads SET created_ts = created_ts - 200000 WHERE id = ?", (old,))
    conn.commit()
    conn.close()
    _upload(make_png())                       # any new upload triggers the sweep
    assert upload_service.locate(old) is None and not os.path.exists(path)


def test_attached_uploads_are_kept():
    pid = _upload(make_png()).json()["id"]
    client.post("/api/v1/reports", json={**SPOT, "photo_id": pid}, headers=CITIZEN)
    conn = get_db_connection()
    conn.execute("UPDATE uploads SET created_ts = created_ts - 200000 WHERE id = ?", (pid,))
    conn.commit()
    conn.close()
    _upload(make_png())
    assert upload_service.locate(pid) is not None


# ── C2: reputation ─────────────────────────────────────────────────────────────

def _clean_slate():
    """Other tests leave open incidents on the same road; the edge weight is the max over all of them."""
    conn = get_db_connection()
    conn.execute("DELETE FROM incident_reports")
    conn.execute("DELETE FROM incidents")
    conn.commit()
    conn.close()
    incident_service.restore_graph_state()


def _fresh_user(uid):
    conn = get_db_connection()
    conn.execute("DELETE FROM incident_reports WHERE reporter_id = ?", (uid,))
    conn.execute("DELETE FROM users WHERE id = ?", (uid,))
    conn.execute("INSERT INTO users (id, name, email, role, password_hash, team_id, active, created_at) "
                 "VALUES (?, ?, ?, 'citizen', 'x', NULL, 1, '2026-01-01T00:00:00')", (uid, uid, f"{uid}@t.in"))
    conn.commit()
    conn.close()
    return {"Authorization": f"Bearer {uid}"}


def _incident_for(uid, status, lat=12.9420, lon=77.6090, note=None):
    """Insert a historical incident + report for `uid` directly."""
    conn = get_db_connection()
    iid = f"inc-h{abs(hash((uid, status, lat, note))) % 10**7}"
    conn.execute("DELETE FROM incidents WHERE id = ?", (iid,))
    conn.execute("INSERT INTO incidents (id, road_edge_id, road_name, lat, lon, type, severity, status, confidence, "
                 "reported_by_id, reported_by_name, reports_count, restriction_notes, created_at, updated_at) "
                 "VALUES (?, NULL, 'x', ?, ?, 'waterlogging', 'low', ?, 0.8, ?, ?, 1, ?, '2026-01-01', '2026-01-01')",
                 (iid, lat, lon, status, uid, uid, note))
    conn.execute("INSERT INTO incident_reports (id, incident_id, reporter_id, reporter_name, lat, lon, description, created_at)"
                 " VALUES (?, ?, ?, ?, ?, ?, 'x', '2026-01-01')", (f"rep-{iid}", iid, uid, uid, lat, lon))
    conn.commit()
    conn.close()
    return iid


def test_new_accounts_start_in_the_middle_and_staff_are_fully_trusted():
    _fresh_user("usr-rep-new")
    assert rep.reputation("usr-rep-new") == pytest.approx(0.5)
    assert rep.reputation("usr-admin-1") == 1.0 and rep.reputation("usr-resp-1") == 1.0


def test_reputation_rises_with_confirmed_reports_and_falls_with_rejected_ones():
    _fresh_user("usr-rep-good")
    _fresh_user("usr-rep-bad")
    for i in range(4):
        _incident_for("usr-rep-good", "cleared", lat=12.90 + i / 100)
        _incident_for("usr-rep-bad", "rejected", lat=12.90 + i / 100, note="Rejected by control room")
    assert rep.reputation("usr-rep-good") == pytest.approx(5.5 / 7)     # (4 + 1.5) / (4 + 0 + 3)
    assert rep.reputation("usr-rep-bad") == pytest.approx(1.5 / 7)      # 1.5 / (0 + 4 + 3)


def test_withdrawn_reports_do_not_hurt_reputation():
    _fresh_user("usr-rep-wd")
    _incident_for("usr-rep-wd", "rejected", note="Withdrawn by reporter")
    assert rep.reputation("usr-rep-wd") == pytest.approx(0.5)


def _edge_of(report):
    return report["road_edge_id"]


def test_low_reputation_reporter_barely_moves_risk_aware_routing_but_a_trusted_one_does():
    _clean_slate()
    h_bad = _fresh_user("usr-rep-spam")
    for i in range(6):
        _incident_for("usr-rep-spam", "rejected", lat=12.90 + i / 100, note="Rejected by control room")
    r = client.post("/api/v1/reports", json=SPOT, headers=h_bad)
    assert r.status_code == 200, r.text
    edge = road_graph.edges[_edge_of(r.json())]
    low = road_graph.get_edge_weight(edge, "risk_aware") - edge.travel_time_s
    assert edge.hazard_weight < 0.3

    # The same spot reported by a respected citizen carries real weight.
    client.post(f"/api/v1/incidents/{r.json()['id']}/restriction", json={"action": "reject"}, headers=ADMIN)
    h_good = _fresh_user("usr-rep-solid")
    for i in range(6):
        _incident_for("usr-rep-solid", "cleared", lat=12.90 + i / 100)
    r2 = client.post("/api/v1/reports", json=SPOT, headers=h_good)
    edge2 = road_graph.edges[_edge_of(r2.json())]
    high = road_graph.get_edge_weight(edge2, "risk_aware") - edge2.travel_time_s
    assert edge2.hazard_weight > 0.8 and high > 3 * low


def test_corroboration_by_independent_reporters_adds_up_but_stays_below_verified():
    _clean_slate()
    uids = [f"usr-rep-c{i}" for i in range(6)]
    hs = [_fresh_user(u) for u in uids]
    first = client.post("/api/v1/reports", json=SPOT, headers=hs[0]).json()
    edge_id = first["road_edge_id"]
    w1 = rep.edge_weight(edge_id)
    settings.DUPLICATE_RADIUS_M = 50.0
    try:
        for h in hs[1:]:
            client.post("/api/v1/reports", json=SPOT, headers=h)
    finally:
        settings.DUPLICATE_RADIUS_M = 0.0
    w6 = rep.edge_weight(edge_id)
    assert w1 == pytest.approx(0.5) and w6 > 0.9 - 1e-9 and w6 <= rep.MAX_UNVERIFIED_WEIGHT


def test_a_photo_raises_trust_and_responder_verification_gives_full_weight():
    _clean_slate()
    h = _fresh_user("usr-rep-photo")
    no_photo = client.post("/api/v1/reports", json=SPOT, headers=h).json()
    plain = rep.edge_weight(no_photo["road_edge_id"])
    client.post(f"/api/v1/incidents/{no_photo['id']}/restriction", json={"action": "reject", "notes": "dup"}, headers=ADMIN)
    pid = _upload(make_png(), h).json()["id"]
    with_photo = client.post("/api/v1/reports", json={**SPOT, "photo_id": pid}, headers=h).json()
    assert rep.edge_weight(with_photo["road_edge_id"]) > plain - 1e-9  # reputation dropped a bit after rejection, photo compensates
    iid = with_photo["id"]
    client.post(f"/api/v1/incidents/{iid}/review", json={}, headers=ADMIN)
    client.post(f"/api/v1/incidents/{iid}/assign", json={"team_id": "team-alpha", "responder_id": "usr-resp-1"}, headers=ADMIN)
    assert rep.edge_weight(with_photo["road_edge_id"]) >= rep.TRIAGED_FLOOR
    client.post(f"/api/v1/incidents/{iid}/verify", json={"findings": "50cm water", "water_depth_cm": 50}, headers=RESP1)
    assert rep.edge_weight(with_photo["road_edge_id"]) == 1.0


def test_weights_survive_a_restart_of_the_in_memory_graph():
    _clean_slate()
    h = _fresh_user("usr-rep-restart")
    for i in range(6):
        _incident_for("usr-rep-restart", "rejected", lat=12.90 + i / 100, note="Rejected by control room")
    r = client.post("/api/v1/reports", json=SPOT, headers=h).json()
    edge = road_graph.edges[r["road_edge_id"]]
    before = edge.hazard_weight
    edge.hazard_weight = 1.0
    incident_service.restore_graph_state()
    assert edge.hazard_weight == pytest.approx(before) and before < 0.3


def test_network_endpoint_exposes_the_hazard_weight():
    edges = client.get("/api/v1/routes/network").json()["edges"]
    assert all("hazard_weight" in e for e in edges)
