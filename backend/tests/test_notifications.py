"""Notification tests. Delivery is exercised against REAL local servers (a minimal SMTP server and an
HTTP webhook server on loopback), not mocks, so smtplib / urllib really do network I/O."""
import hashlib
import hmac
import json
import socketserver
import threading
from email import message_from_bytes
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.main import app
from backend.app.models.database import get_db_connection
from backend.app.services import notification_service as ns
from backend.app.services.graph_service import road_graph
from backend.app.timeutil import utcnow

client = TestClient(app)
ADMIN = {"Authorization": "Bearer usr-admin-1"}
CITIZEN = {"Authorization": "Bearer usr-citizen-1"}
RESP1 = {"Authorization": "Bearer usr-resp-1"}


# ── local servers ───────────────────────────────────────────────────────────

class _SMTPHandler(socketserver.StreamRequestHandler):
    def handle(self):
        w = lambda line: (self.wfile.write((line + "\r\n").encode()), self.wfile.flush())
        w("220 test ESMTP")
        mail_from, rcpts, data = None, [], b""
        while True:
            line = self.rfile.readline()
            if not line:
                return
            cmd = line.decode(errors="replace").strip()
            up = cmd.upper()
            if up.startswith(("EHLO", "HELO")):
                w("250 test")
            elif up.startswith("MAIL FROM"):
                if self.server.fail_next:
                    self.server.fail_next -= 1
                    w("451 temporary failure, try later")
                    continue
                mail_from = cmd[10:]
                w("250 ok")
            elif up.startswith("RCPT TO"):
                rcpts.append(cmd[8:].strip("<> "))
                w("250 ok")
            elif up == "DATA":
                w("354 end with <CRLF>.<CRLF>")
                buf = []
                while True:
                    l = self.rfile.readline()
                    if l in (b".\r\n", b".\n", b""):
                        break
                    buf.append(l)
                data = b"".join(buf)
                self.server.messages.append({"from": mail_from, "to": list(rcpts), "msg": message_from_bytes(data)})
                mail_from, rcpts = None, []
                w("250 queued")
            elif up == "QUIT":
                w("221 bye")
                return
            else:
                w("250 ok")


class _SMTPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _SMTPHandler)
        self.messages, self.fail_next = [], 0


@pytest.fixture()
def smtp(monkeypatch):
    srv = _SMTPServer()
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(settings, "SMTP_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "SMTP_PORT", srv.server_address[1])
    monkeypatch.setattr(settings, "SMTP_STARTTLS", False)
    monkeypatch.setattr(settings, "SMTP_USER", "")
    yield srv
    srv.shutdown()
    srv.server_close()


class _Hook(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        self.server.requests.append({"body": body, "headers": {k.lower(): v for k, v in self.headers.items()}})
        code = 200
        if self.server.fail_next:
            self.server.fail_next -= 1
            code = 500
        self.send_response(code)
        self.end_headers()

    def log_message(self, *a):
        pass


@pytest.fixture()
def webhook(monkeypatch):
    srv = HTTPServer(("127.0.0.1", 0), _Hook)
    srv.requests, srv.fail_next = [], 0
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(settings, "NOTIFY_WEBHOOK_URL", f"http://127.0.0.1:{srv.server_address[1]}/sms")
    monkeypatch.setattr(settings, "NOTIFY_WEBHOOK_SECRET", "s3cret")
    yield srv
    srv.shutdown()
    srv.server_close()


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    # The background dispatcher must not race the tests; they call dispatch_due() themselves.
    monkeypatch.setattr(settings, "NOTIFY_POLL_SECONDS", 3600)
    conn = get_db_connection()
    conn.execute("DELETE FROM notifications")
    conn.execute("UPDATE users SET phone = NULL")
    conn.commit()
    conn.close()
    yield
    for e in road_graph.edges.values():
        e.is_blocked = False


def _rows(**where):
    conn = get_db_connection()
    q = "SELECT * FROM notifications"
    if where:
        q += " WHERE " + " AND ".join(f"{k} = ?" for k in where)
    rows = [dict(r) for r in conn.execute(q + " ORDER BY created_at", tuple(where.values()))]
    conn.close()
    return rows


def _set_phone(uid, phone):
    conn = get_db_connection()
    conn.execute("UPDATE users SET phone = ? WHERE id = ?", (phone, uid))
    conn.commit()
    conn.close()


def _drive_incident(upto="assign", responder=None):
    body = {"lat": 12.9420, "lon": 77.6090, "type": "waterlogging", "severity": "high", "description": "Flooded underpass"}
    iid = client.post("/api/v1/reports", json=body, headers=CITIZEN).json()["id"]
    client.post(f"/api/v1/incidents/{iid}/review", json={}, headers=ADMIN)
    payload = {"team_id": "team-alpha"}
    if responder:
        payload["responder_id"] = responder
    r = client.post(f"/api/v1/incidents/{iid}/assign", json=payload, headers=ADMIN)
    assert r.status_code == 200, r.text
    return iid


# ── real SMTP / webhook delivery ───────────────────────────────────────────────

def test_email_is_delivered_over_real_smtp(smtp):
    r = client.post("/api/v1/auth/forgot-password", json={"email": "citizen@malemitra.in"})
    token = r.json()["debug_token"]
    out = ns.dispatch_due()
    assert out == {"sent": 1, "failed": 0}
    assert len(smtp.messages) == 1
    m = smtp.messages[0]
    assert m["to"] == ["citizen@malemitra.in"]
    assert "Reset your MaleMitra password" in m["msg"]["Subject"]
    assert token in m["msg"].get_payload()
    assert _rows(channel="email")[0]["status"] == "sent"


def test_sms_goes_to_the_webhook_with_a_valid_hmac_signature(webhook):
    _set_phone("usr-citizen-1", "+919800000001")
    client.post("/api/v1/auth/forgot-password", json={"email": "citizen@malemitra.in"})
    assert ns.dispatch_due() == {"sent": 1, "failed": 0}
    req = webhook.requests[0]
    sent = json.loads(req["body"])
    assert sent["channel"] == "sms" and sent["to"] == "+919800000001" and sent["kind"] == "password_reset"
    expected = "sha256=" + hmac.new(b"s3cret", req["body"], hashlib.sha256).hexdigest()
    assert req["headers"]["x-malemitra-signature"] == expected


def test_user_with_email_and_phone_is_reached_on_both_channels(smtp, webhook):
    _set_phone("usr-citizen-1", "+919800000001")
    client.post("/api/v1/auth/forgot-password", json={"email": "citizen@malemitra.in"})
    assert {r["channel"] for r in _rows()} == {"email", "sms"}
    assert ns.dispatch_due()["sent"] == 2
    assert len(smtp.messages) == 1 and len(webhook.requests) == 1


# ── retry / failure handling ─────────────────────────────────────────────────

def test_failed_delivery_is_retried_with_backoff_then_succeeds(smtp):
    smtp.fail_next = 1                      # first attempt gets "451 try later"
    client.post("/api/v1/auth/forgot-password", json={"email": "citizen@malemitra.in"})
    assert ns.dispatch_due() == {"sent": 0, "failed": 1}
    row = _rows()[0]
    assert row["status"] == "pending" and row["attempts"] == 1 and "451" in row["last_error"]
    assert row["next_attempt_at"] > utcnow().isoformat()          # backed off into the future
    assert ns.dispatch_due() == {"sent": 0, "failed": 0}          # not due yet
    conn = get_db_connection()
    conn.execute("UPDATE notifications SET next_attempt_at = '2000-01-01T00:00:00'")
    conn.commit()
    conn.close()
    assert ns.dispatch_due() == {"sent": 1, "failed": 0}
    assert _rows()[0]["status"] == "sent" and len(smtp.messages) == 1


def test_gives_up_after_max_attempts_and_admin_can_retry(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "SMTP_PORT", 1)                  # nothing listens here
    monkeypatch.setattr(settings, "NOTIFY_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(settings, "NOTIFY_TIMEOUT_SECONDS", 2)
    client.post("/api/v1/auth/forgot-password", json={"email": "citizen@malemitra.in"})
    for _ in range(2):
        ns.dispatch_due()
        conn = get_db_connection()
        conn.execute("UPDATE notifications SET next_attempt_at = '2000-01-01T00:00:00' WHERE status = 'pending'")
        conn.commit()
        conn.close()
    row = _rows()[0]
    assert row["status"] == "failed" and row["attempts"] == 2 and row["last_error"]
    assert ns.dispatch_due() == {"sent": 0, "failed": 0}           # no more attempts
    assert client.post(f"/api/v1/notifications/{row['id']}/retry", headers=CITIZEN).status_code == 403
    assert client.post(f"/api/v1/notifications/{row['id']}/retry", headers=ADMIN).status_code == 200
    assert _rows()[0]["status"] == "pending"
    assert client.post(f"/api/v1/notifications/{row['id']}/retry", headers=ADMIN).status_code == 404


def test_two_dispatchers_never_send_the_same_message_twice(smtp):
    for i in range(6):
        conn = get_db_connection()
        ns.enqueue(conn.cursor(), "usr-citizen-1", "t", f"s{i}", "b", dedupe_key=f"k{i}")
        conn.commit()
        conn.close()
    results = []
    ts = [threading.Thread(target=lambda n=n: results.append(ns.dispatch_due(worker_id=f"w{n}"))) for n in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sum(r["sent"] for r in results) == 6
    assert len(smtp.messages) == 6


# ── outbox semantics ─────────────────────────────────────────────────────────

def test_notification_is_not_queued_when_the_transaction_rolls_back():
    conn = get_db_connection()
    ns.enqueue(conn.cursor(), "usr-citizen-1", "t", "s", "b")
    conn.rollback()
    conn.close()
    assert _rows() == []


def test_dedupe_key_prevents_duplicates():
    conn = get_db_connection()
    c = conn.cursor()
    assert ns.enqueue(c, "usr-citizen-1", "t", "s", "b", dedupe_key="same") == 1
    assert ns.enqueue(c, "usr-citizen-1", "t", "s", "b", dedupe_key="same") == 0
    conn.commit()
    conn.close()
    assert len(_rows()) == 1


def test_inactive_unknown_and_disabled_are_skipped(monkeypatch):
    conn = get_db_connection()
    c = conn.cursor()
    assert ns.enqueue(c, "no-such-user", "t", "s", "b") == 0
    assert ns.enqueue(c, None, "t", "s", "b") == 0
    monkeypatch.setattr(settings, "NOTIFY_ENABLED", False)
    assert ns.enqueue(c, "usr-citizen-1", "t", "s", "b") == 0
    conn.close()


def test_no_channel_configured_outside_demo_means_nothing_queued(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "NOTIFY_LOG_ONLY", False)
    conn = get_db_connection()
    assert ns.enqueue(conn.cursor(), "usr-citizen-1", "t", "s", "b") == 0
    conn.close()


def test_log_channel_never_writes_reset_codes_to_the_log(caplog):
    caplog.set_level("INFO", logger="malemitra.notify")
    token = client.post("/api/v1/auth/forgot-password", json={"email": "citizen@malemitra.in"}).json()["debug_token"]
    ns.dispatch_due()
    assert "password_reset" in caplog.text and token not in caplog.text


# ── event hooks ──────────────────────────────────────────────────────────────

def test_assigning_to_a_responder_notifies_them_and_the_reporter():
    _drive_incident(responder="usr-resp-1")
    kinds = {(r["user_id"], r["kind"]) for r in _rows()}
    assert ("usr-resp-1", "task_assigned") in kinds
    assert ("usr-citizen-1", "report_assigned") in kinds
    assert ("usr-admin-1", "new_incident") in kinds                  # high severity alerts the control room


def test_assigning_to_the_team_queue_notifies_every_teammate():
    conn = get_db_connection()
    conn.execute("INSERT INTO users (id, name, email, role, password_hash, team_id, active, created_at) "
                 "VALUES ('usr-ntf-mate', 'Mate', 'mate@t.in', 'responder', 'x', 'team-alpha', 1, '2026-01-01') "
                 "ON CONFLICT DO NOTHING")
    conn.commit()
    conn.close()
    try:
        _drive_incident()
        queued = {r["user_id"] for r in _rows(kind="task_queued")}
        assert {"usr-resp-1", "usr-ntf-mate"} <= queued
        assert "usr-resp-2" not in queued                              # other team is not disturbed
    finally:
        conn = get_db_connection()
        conn.execute("DELETE FROM users WHERE id = 'usr-ntf-mate'")
        conn.commit()
        conn.close()


def test_full_lifecycle_tells_the_reporter_and_the_control_room():
    iid = _drive_incident(responder="usr-resp-1")
    client.post(f"/api/v1/incidents/{iid}/verify", json={"findings": "55cm water", "water_depth_cm": 55}, headers=RESP1)
    assert any(r["kind"] == "field_verified" and r["user_id"] == "usr-admin-1" for r in _rows())
    client.post(f"/api/v1/incidents/{iid}/restriction", json={"action": "authorize_block"}, headers=ADMIN)
    assert any(r["kind"] == "road_closed" and r["user_id"] == "usr-citizen-1" for r in _rows())
    assert any(r["kind"] == "closure_authorized" and r["user_id"] == "usr-resp-1" for r in _rows())
    client.post(f"/api/v1/incidents/{iid}/clearance", json={"clearance_findings": "drained"}, headers=RESP1)
    assert any(r["kind"] == "clearance_proposed" and r["user_id"] == "usr-admin-1" for r in _rows())
    client.post(f"/api/v1/incidents/{iid}/restriction", json={"action": "authorize_reopen"}, headers=ADMIN)
    assert any(r["kind"] == "road_reopened" and r["user_id"] == "usr-citizen-1" for r in _rows())


def test_rejecting_a_report_tells_the_reporter():
    body = {"lat": 12.9420, "lon": 77.6090, "description": "maybe flooded"}
    iid = client.post("/api/v1/reports", json=body, headers=CITIZEN).json()["id"]
    client.post(f"/api/v1/incidents/{iid}/restriction", json={"action": "reject"}, headers=ADMIN)
    assert any(r["kind"] == "report_rejected" and r["user_id"] == "usr-citizen-1" for r in _rows())


def test_merged_reporters_are_all_notified(monkeypatch):
    monkeypatch.setattr(settings, "DUPLICATE_RADIUS_M", 10.0)
    body = {"lat": 12.9610, "lon": 77.6010, "severity": "low", "description": "water"}
    first = client.post("/api/v1/reports", json=body, headers=CITIZEN).json()
    second = client.post("/api/v1/reports", json=body, headers={"Authorization": "Bearer usr-citizen-2"}).json()
    if second["id"] != first["id"]:
        pytest.skip("location was not merged in this database state")
    client.post(f"/api/v1/incidents/{first['id']}/restriction", json={"action": "reject"}, headers=ADMIN)
    who = {r["user_id"] for r in _rows(kind="report_rejected")}
    assert {"usr-citizen-1", "usr-citizen-2"} <= who


# ── phone handling & admin API ───────────────────────────────────────────────

def test_phone_is_normalised_validated_and_stored_at_signup():
    body = {"name": "Phone User", "email": "ph1@t.in", "password": "Str0ng-pass!", "phone": "98765 43210"}
    tok = client.post("/api/v1/auth/register", json=body).json()
    conn = get_db_connection()
    stored = conn.execute("SELECT phone FROM users WHERE id = ?", (tok["user_id"],)).fetchone()[0]
    conn.close()
    assert stored == "+919876543210"
    bad = client.post("/api/v1/auth/register", json={**body, "email": "ph2@t.in", "phone": "abc"})
    assert bad.status_code == 422


def test_user_can_set_and_clear_their_phone():
    h = CITIZEN
    assert client.put("/api/v1/auth/me/phone", json={"phone": "+14155550100"}, headers=h).json() == {"phone": "+14155550100"}
    assert client.put("/api/v1/auth/me/phone", json={"phone": None}, headers=h).json() == {"phone": None}
    assert client.put("/api/v1/auth/me/phone", json={"phone": "12"}, headers=h).status_code == 422
    assert client.put("/api/v1/auth/me/phone", json={"phone": "+14155550100"}).status_code == 401


def test_notification_admin_endpoints_are_admin_only_and_hide_bodies():
    client.post("/api/v1/auth/forgot-password", json={"email": "citizen@malemitra.in"})
    assert client.get("/api/v1/notifications/status", headers=CITIZEN).status_code == 403
    assert client.get("/api/v1/notifications").status_code == 401
    st = client.get("/api/v1/notifications/status", headers=ADMIN).json()
    assert st["counts"].get("pending", 0) >= 1 and "channels" in st
    listing = client.get("/api/v1/notifications", headers=ADMIN).json()["notifications"]
    assert listing and all("body" not in n for n in listing)


def test_background_dispatcher_delivers_without_being_called(smtp, monkeypatch):
    monkeypatch.setattr(settings, "NOTIFY_POLL_SECONDS", 0.1)
    disp = ns.Dispatcher()
    client.post("/api/v1/auth/forgot-password", json={"email": "citizen@malemitra.in"})
    disp.start()
    try:
        for _ in range(50):
            if smtp.messages:
                break
            threading.Event().wait(0.1)
    finally:
        disp.stop()
    assert len(smtp.messages) == 1
