"""Sliding-window rate limiter backed by the database, so every worker/replica shares the same counters."""
import logging
import time

from fastapi import HTTPException, Request

from backend.app.config import settings
from backend.app.models.database import get_db_connection

log = logging.getLogger("malemitra.ratelimit")

_PURGE_EVERY_S = 600
_MAX_WINDOW_S = 86400
_last_purge = 0.0


def reset() -> None:
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM rate_hits")
        conn.commit()
    finally:
        conn.close()


def _purge(conn, now: float) -> None:
    """Drop hits older than any window we use, so keys that never come back don't accumulate."""
    global _last_purge
    if now - _last_purge < _PURGE_EVERY_S:
        return
    _last_purge = now
    conn.execute("DELETE FROM rate_hits WHERE ts < ?", (now - _MAX_WINDOW_S,))


def hit(bucket: str, key: str, limit: int, window_s: int) -> None:
    """Record one event; raise 429 when `key` exceeded `limit` events in the last `window_s` seconds."""
    if not settings.RATE_LIMIT_ENABLED or limit <= 0:
        return
    now = time.time()
    try:
        conn = get_db_connection()
        try:
            # Takes the write lock up front, so check-then-insert is atomic across processes. PostgreSQL locks
            # per bucket+key (unrelated clients don't queue behind each other); SQLite has one writer anyway.
            conn.begin_write(f"rate:{bucket}:{key}")
            _purge(conn, now)
            row = conn.execute("SELECT COUNT(*) AS n, MIN(ts) AS oldest FROM rate_hits "
                               "WHERE bucket = ? AND key = ? AND ts > ?", (bucket, key, now - window_s)).fetchone()
            if row["n"] >= limit:
                conn.rollback()
                retry = max(1, int(window_s - (now - row["oldest"])) + 1)
                raise HTTPException(status_code=429,
                                    detail="Too many requests. Please slow down and try again shortly.",
                                    headers={"Retry-After": str(retry)})
            conn.execute("INSERT INTO rate_hits (bucket, key, ts) VALUES (?, ?, ?)", (bucket, key, now))
            conn.commit()
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as e:  # a limiter outage must not take the API down with it
        log.warning("rate limiter unavailable, allowing request: %s: %s", type(e).__name__, e)


def count(bucket: str, key: str, window_s: int) -> int:
    """Events recorded for `key` in the window (no side effects)."""
    conn = get_db_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM rate_hits WHERE bucket = ? AND key = ? AND ts > ?",
                            (bucket, key, time.time() - window_s)).fetchone()[0]
    finally:
        conn.close()


def record(bucket: str, key: str) -> None:
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO rate_hits (bucket, key, ts) VALUES (?, ?, ?)", (bucket, key, time.time()))
        conn.commit()
    finally:
        conn.close()


def clear(bucket: str, key: str) -> None:
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM rate_hits WHERE bucket = ? AND key = ?", (bucket, key))
        conn.commit()
    finally:
        conn.close()


def rate_limit_ip(bucket: str, limit_attr: str, window_s: int):
    """FastAPI dependency limiting by client IP. `limit_attr` is read from settings at call time."""
    def dependency(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        hit(bucket, ip, getattr(settings, limit_attr), window_s)
    return dependency
