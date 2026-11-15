"""
Notifications: a transactional outbox plus a background dispatcher.

* `enqueue()` writes rows to the `notifications` table using the *caller's* open transaction, so a
  notification exists if and only if the change that caused it was committed.
* A daemon thread claims due rows (with a lease, so several workers never double-send), delivers them
  and retries failures with exponential backoff until NOTIFY_MAX_ATTEMPTS, then marks them `failed`.
* Channels:
    email    - SMTP (SMTP_HOST ...). Needs the user's email.
    sms      - POST of signed JSON to NOTIFY_WEBHOOK_URL (relay to your SMS gateway). Needs a phone number.
    log      - logged only; used when nothing is configured in DEMO_MODE or NOTIFY_LOG_ONLY=true.
  A message is queued on every channel the user can be reached on.
Message bodies never contain passwords. Password-reset messages contain the one-time token (that is their purpose).
"""
import hashlib
import hmac
import json
import logging
import smtplib
import socket
import ssl
import threading
import urllib.error
import urllib.request
import uuid
from datetime import timedelta
from email.message import EmailMessage
from typing import Any, Callable, Dict, List, Optional

from backend.app.config import settings
from backend.app.models.database import get_db_connection
from backend.app.timeutil import utcnow

log = logging.getLogger("malemitra.notify")

LEASE_SECONDS = 60
BACKOFF_BASE_SECONDS = 30
BACKOFF_MAX_SECONDS = 3600

# sender(row) raises on failure. Replaceable in tests.
Sender = Callable[[Dict[str, Any]], None]


# ── channels ──────────────────────────────────────────────────────────────────

def channels_available() -> Dict[str, bool]:
    return {
        "email": bool(settings.SMTP_HOST),
        "sms": bool(settings.NOTIFY_WEBHOOK_URL),
        "log": bool(settings.NOTIFY_LOG_ONLY or settings.DEMO_MODE),
    }


def _channels_for(user: Dict[str, Any]) -> List[tuple]:
    """(channel, recipient) pairs this user can be reached on, given what is configured."""
    avail = channels_available()
    out = []
    if avail["email"] and user.get("email"):
        out.append(("email", user["email"]))
    if avail["sms"] and user.get("phone"):
        out.append(("sms", user["phone"]))
    if not out and avail["log"]:
        out.append(("log", user.get("email") or user.get("phone") or user["id"]))
    return out


def send_email(row: Dict[str, Any]) -> None:
    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = row["recipient"]
    msg["Subject"] = row["subject"]
    msg["X-MaleMitra-Notification"] = row["id"]
    msg.set_content(row["body"])
    timeout = settings.NOTIFY_TIMEOUT_SECONDS
    if settings.SMTP_SSL:
        client = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout,
                                  context=ssl.create_default_context())
    else:
        client = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout)
    with client:
        if not settings.SMTP_SSL and settings.SMTP_STARTTLS:
            client.starttls(context=ssl.create_default_context())
        if settings.SMTP_USER:
            client.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        client.send_message(msg)


def send_webhook(row: Dict[str, Any]) -> None:
    payload = json.dumps({
        "id": row["id"], "channel": row["channel"], "to": row["recipient"], "kind": row["kind"],
        "subject": row["subject"], "message": row["body"],
    }).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "MaleMitra/1.0", "X-Notification-Id": row["id"]}
    if settings.NOTIFY_WEBHOOK_SECRET:
        sig = hmac.new(settings.NOTIFY_WEBHOOK_SECRET.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        headers["X-MaleMitra-Signature"] = f"sha256={sig}"
    req = urllib.request.Request(settings.NOTIFY_WEBHOOK_URL, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=settings.NOTIFY_TIMEOUT_SECONDS) as resp:
        if resp.status >= 300:
            raise RuntimeError(f"webhook returned HTTP {resp.status}")


def send_log(row: Dict[str, Any]) -> None:
    # Reset tokens are secrets: never write the body of a password_reset message to the log.
    shown = "[redacted]" if row["kind"] == "password_reset" else row["body"]
    log.info("NOTIFY(%s) to=%s kind=%s subject=%r body=%s", row["channel"], row["recipient"], row["kind"],
             row["subject"], shown)


DEFAULT_SENDERS: Dict[str, Sender] = {"email": send_email, "sms": send_webhook, "log": send_log}


# ── outbox ────────────────────────────────────────────────────────────────────

def enqueue(cursor, user_id: Optional[str], kind: str, subject: str, body: str,
            dedupe_key: Optional[str] = None) -> int:
    """Queue `subject/body` for a user on every reachable channel. Uses the caller's transaction."""
    if not settings.NOTIFY_ENABLED or not user_id:
        return 0
    cursor.execute("SELECT id, email, phone, active FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if not row or not row["active"]:
        return 0
    now = utcnow().isoformat()
    queued = 0
    for channel, recipient in _channels_for(dict(row)):
        cursor.execute("""
        INSERT INTO notifications
            (id, user_id, channel, recipient, kind, subject, body, status, attempts, next_attempt_at, dedupe_key, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', 0, ?, ?, ?)
        ON CONFLICT DO NOTHING
        """, (f"ntf-{uuid.uuid4().hex[:12]}", user_id, channel, recipient, kind, subject, body, now, dedupe_key, now))
        queued += cursor.rowcount
    return queued


def enqueue_for_team(cursor, team_id: Optional[str], kind: str, subject: str, body: str,
                     dedupe_key: Optional[str] = None) -> int:
    """Notify every active responder on a team (used for the team queue)."""
    if not team_id:
        return 0
    cursor.execute("SELECT id FROM users WHERE role = 'responder' AND team_id = ? AND active = 1", (team_id,))
    return sum(enqueue(cursor, r["id"], kind, subject, body,
                       f"{dedupe_key}:{r['id']}" if dedupe_key else None) for r in cursor.fetchall())


def _backoff(attempts: int) -> timedelta:
    return timedelta(seconds=min(BACKOFF_MAX_SECONDS, BACKOFF_BASE_SECONDS * (2 ** max(0, attempts - 1))))


def _claim_due(worker_id: str, limit: int) -> List[Dict[str, Any]]:
    """Atomically lease up to `limit` due messages (safe with several workers)."""
    conn = get_db_connection()
    try:
        conn.begin_write("notifications-claim")
        now = utcnow()
        rows = conn.execute("""
            SELECT * FROM notifications
            WHERE status = 'pending' AND next_attempt_at <= ? AND (lease_until IS NULL OR lease_until <= ?)
            ORDER BY next_attempt_at LIMIT ?
        """, (now.isoformat(), now.isoformat(), limit)).fetchall()
        lease = (now + timedelta(seconds=LEASE_SECONDS)).isoformat()
        for r in rows:
            conn.execute("UPDATE notifications SET lease_until = ?, claimed_by = ? WHERE id = ?",
                         (lease, worker_id, r["id"]))
        conn.commit()
        return [dict(r) for r in rows]
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _finish(row: Dict[str, Any], error: Optional[str]) -> None:
    conn = get_db_connection()
    try:
        attempts = row["attempts"] + 1
        now = utcnow()
        if error is None:
            conn.execute("UPDATE notifications SET status='sent', attempts=?, sent_at=?, lease_until=NULL, last_error=NULL "
                         "WHERE id=?", (attempts, now.isoformat(), row["id"]))
        elif attempts >= settings.NOTIFY_MAX_ATTEMPTS:
            conn.execute("UPDATE notifications SET status='failed', attempts=?, lease_until=NULL, last_error=? WHERE id=?",
                         (attempts, error[:500], row["id"]))
            log.error("Notification %s (%s to %s) failed permanently: %s", row["id"], row["channel"],
                      row["recipient"], error)
        else:
            conn.execute("UPDATE notifications SET attempts=?, next_attempt_at=?, lease_until=NULL, last_error=? WHERE id=?",
                         (attempts, (now + _backoff(attempts)).isoformat(), error[:500], row["id"]))
        conn.commit()
    finally:
        conn.close()


def dispatch_due(senders: Optional[Dict[str, Sender]] = None, limit: int = 20,
                 worker_id: Optional[str] = None) -> Dict[str, int]:
    """Deliver due messages once. Returns counts; used by the background loop and by tests."""
    senders = senders or DEFAULT_SENDERS
    worker_id = worker_id or f"{socket.gethostname()}-{threading.get_ident()}"
    sent = failed = 0
    for row in _claim_due(worker_id, limit):
        sender = senders.get(row["channel"])
        try:
            if sender is None:
                raise RuntimeError(f"no sender for channel '{row['channel']}'")
            sender(row)
            _finish(row, None)
            sent += 1
        except Exception as e:  # delivery errors must never crash the dispatcher
            _finish(row, f"{type(e).__name__}: {e}")
            failed += 1
    return {"sent": sent, "failed": failed}


def stats() -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        counts = {r["status"]: r["n"] for r in conn.execute("SELECT status, COUNT(*) n FROM notifications GROUP BY status")}
    finally:
        conn.close()
    return {"channels": channels_available(), "counts": counts, "dispatcher_running": dispatcher.running}


class Dispatcher:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _loop(self):
        while not self._stop.is_set():
            try:
                dispatch_due()
            except Exception as e:
                log.warning("Notification dispatcher error: %s: %s", type(e).__name__, e)
            self._stop.wait(settings.NOTIFY_POLL_SECONDS)

    def start(self):
        if not settings.NOTIFY_ENABLED or self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="notifications", daemon=True)
        self._thread.start()
        log.info("Notification dispatcher started (channels: %s)", channels_available())

    def stop(self):
        self._stop.set()


dispatcher = Dispatcher()
