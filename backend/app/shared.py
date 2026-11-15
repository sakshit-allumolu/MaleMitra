"""
State shared between worker processes / replicas, kept in the database.

The road graph lives in each process's memory (it is a small, hot structure), so every worker has to learn
about changes the others made. The scheme:

* Triggers in `init_db()` bump the ``graph`` epoch in `shared_state` inside the same transaction as any
  incident change that can affect roads (so a write can never be missed).
* `sync_graph()` compares the worker's epoch with the database and, when it is stale, rebuilds closures and
  hazards from the incidents table and recomputes the ripple flows. It is called on every API request and on
  every SSE tick, so a closure authorised on one worker is honoured by routing on all of them.
* The latest ripple result and TomTom readings are stored in `shared_state` for the same reason.
* `acquire_lease()` elects the single worker that polls TomTom (a lease expires if its holder dies).
"""
import json
import logging
import os
import threading
import time
import uuid
from typing import Any, Dict, Optional

from backend.app.models.database import get_db_connection
from backend.app.timeutil import utcnow

log = logging.getLogger("malemitra.shared")

WORKER_ID = f"{os.getpid()}-{uuid.uuid4().hex[:6]}"

GRAPH, LIVE, RIPPLE = "graph", "live", "ripple"

_sync_lock = threading.Lock()
_synced: Dict[str, int] = {GRAPH: -1, LIVE: -1}


# ── key/value with a version counter ──────────────────────────────────────────

def versions() -> Dict[str, int]:
    conn = get_db_connection()
    try:
        return {r["key"]: r["version"] for r in conn.execute("SELECT key, version FROM shared_state")}
    finally:
        conn.close()


def put(key: str, value: Any) -> None:
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO shared_state (key, version, value, updated_at) VALUES (?, 1, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET version = shared_state.version + 1, value = excluded.value, "
            "updated_at = excluded.updated_at",
            (key, json.dumps(value), utcnow().isoformat()))
        conn.commit()
    finally:
        conn.close()


def get(key: str) -> Optional[Any]:
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT value FROM shared_state WHERE key = ?", (key,)).fetchone()
    finally:
        conn.close()
    return json.loads(row["value"]) if row and row["value"] else None


# ── leases ────────────────────────────────────────────────────────────────────

def acquire_lease(name: str, ttl_s: float, holder: str = WORKER_ID) -> bool:
    """Take (or renew) the named lease. True if this holder owns it afterwards."""
    now = time.time()
    conn = get_db_connection()
    try:
        conn.begin_write(f"lease:{name}")
        row = conn.execute("SELECT holder, until FROM leases WHERE name = ?", (name,)).fetchone()
        if row is None or row["until"] <= now or row["holder"] == holder:
            conn.execute("INSERT INTO leases (name, holder, until) VALUES (?, ?, ?) "
                         "ON CONFLICT(name) DO UPDATE SET holder = excluded.holder, until = excluded.until",
                         (name, holder, now + ttl_s))
            conn.commit()
            return True
        conn.rollback()
        return False
    finally:
        conn.close()


# ── graph synchronisation ─────────────────────────────────────────────────────

def mark_synced() -> None:
    """Record the current epochs as already applied (used right before a deliberate full restore)."""
    _synced.update({k: v for k, v in versions().items() if k in _synced})


def is_stale() -> bool:
    v = versions()
    return any(v.get(k, 0) != _synced[k] for k in (GRAPH, LIVE))


def sync_graph(force: bool = False) -> bool:
    """Bring this process's road graph up to date with the database. Returns True if anything changed."""
    from backend.app.services.graph_service import road_graph
    from backend.app.services.incident_service import IncidentService
    from backend.app.services.live_traffic_service import live_traffic
    from backend.app.services.ripple_service import ripple_engine

    v = versions()
    if not force and all(v.get(k, 0) == _synced[k] for k in (GRAPH, LIVE)):
        return False
    with _sync_lock:
        v = versions()  # re-read: another thread may have synced while we waited
        if not force and all(v.get(k, 0) == _synced[k] for k in (GRAPH, LIVE)):
            return False
        changed = False
        if force or v.get(GRAPH, 0) != _synced[GRAPH]:
            before = {e_id for e_id, e in road_graph.edges.items() if e.is_blocked}
            IncidentService.restore_graph_state()
            after = {e_id for e_id, e in road_graph.edges.items() if e.is_blocked}
            # Flows depend on which roads are closed; recompute only when that set moved (or on first sync).
            if before != after or (_synced[GRAPH] < 0 and after):
                try:
                    ripple_engine.run_for_current_state(persist=False)
                except Exception as e:  # a failed recompute must not block serving
                    log.warning("ripple recompute after sync failed: %s", e)
            changed = True
        if force or v.get(LIVE, 0) != _synced[LIVE]:
            live_traffic.load_shared()
            changed = True
        _synced[GRAPH], _synced[LIVE] = v.get(GRAPH, 0), v.get(LIVE, 0)
        if changed:
            # Same number on every worker, so a client that reconnects to a different one sees a consistent
            # version; strictly greater than any local bump made since the previous sync.
            road_graph.graph_version = max(road_graph.graph_version + 1, _synced[GRAPH] + _synced[LIVE] + 1)
            log.info("graph synced to shared epoch graph=%s live=%s", _synced[GRAPH], _synced[LIVE])
        return changed
