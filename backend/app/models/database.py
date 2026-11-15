"""
Database access for both supported back-ends.

* SQLite (default, ``DATABASE_PATH``): one host, WAL mode.
* PostgreSQL (``DATABASE_URL=postgresql://...``): pooled connections, safe for several workers and replicas.

The rest of the application is written once against a small common surface: ``?`` placeholders,
``conn.execute(...)``/``conn.cursor()``, rows addressable by name *and* index, ``commit/rollback/close``, and
``conn.begin_write(name)`` for "check then write" sections that must not interleave. PostgreSQL connections are
wrapped to provide exactly that (see `PgConnection`); SQLite connections get the same ``begin_write``.
"""
import atexit
import contextlib
import functools
import os
import re
import sqlite3
import threading
import uuid
import zlib
from typing import Any, Dict, Set

from backend.app.config import settings
from backend.app.security import hash_password
from backend.app.timeutil import utcnow

# 1 = baseline; 2 = users.token_version (session revocation).
SCHEMA_VERSION = 2


def is_postgres() -> bool:
    """True when DATABASE_URL points at PostgreSQL (read on every call so tests can switch databases)."""
    return settings.DATABASE_URL.startswith(("postgres://", "postgresql://"))


# ── PostgreSQL adapter ────────────────────────────────────────────────────────────────────────────────

class Row(tuple):
    """A result row addressable by column name or position (the behaviour of `sqlite3.Row`)."""

    def __new__(cls, values, keys):
        self = super().__new__(cls, values)
        self._keys = tuple(keys)
        return self

    def keys(self):
        return list(self._keys)

    def __getitem__(self, item):
        if isinstance(item, str):
            try:
                return super().__getitem__(self._keys.index(item))
            except ValueError:
                raise IndexError("No item with that key") from None
        return super().__getitem__(item)


def _row_factory(cursor):
    names = [c.name for c in cursor.description] if cursor.description else []
    return lambda values: Row(values, names)


@functools.lru_cache(maxsize=1024)
def _translate(sql: str, has_params: bool) -> str:
    """SQLite-style ``?`` placeholders -> psycopg ``%s`` (and escape literal ``%`` when parameters are bound)."""
    if not has_params:
        return sql
    out, in_quote = [], False
    for ch in sql:
        if ch == "'":
            in_quote = not in_quote
            out.append(ch)
        elif ch == "%":
            out.append("%%")
        elif ch == "?" and not in_quote:
            out.append("%s")
        else:
            out.append(ch)
    return "".join(out)


def _adapt(params):
    # Flag columns are INTEGER 0/1; psycopg would send a Python bool as boolean and PostgreSQL refuses to store it.
    if not params:
        return None
    return tuple(int(p) if isinstance(p, bool) else p for p in params)


class PgCursor:
    def __init__(self, cur):
        self._cur = cur

    def execute(self, sql, params=()):
        bound = _adapt(params)
        self._cur.execute(_translate(sql, bound is not None), bound)
        return self

    def executemany(self, sql, seq):
        rows = [_adapt(p) or () for p in seq]
        self._cur.executemany(_translate(sql, True), rows)
        return self

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def fetchmany(self, size=None):
        return self._cur.fetchmany(size) if size else self._cur.fetchmany()

    def __iter__(self):
        return iter(self._cur)

    def close(self):
        self._cur.close()

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def description(self):
        return self._cur.description


class PgConnection:
    """A pooled PostgreSQL connection with the sqlite3-style surface the application uses."""

    def __init__(self, pool, raw):
        self._pool = pool
        self._raw = raw

    def cursor(self) -> PgCursor:
        return PgCursor(self._raw.cursor(row_factory=_row_factory))

    def execute(self, sql, params=()) -> PgCursor:
        return self.cursor().execute(sql, params)

    def executemany(self, sql, seq) -> PgCursor:
        return self.cursor().executemany(sql, seq)

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def begin_write(self, name: str = "global") -> None:
        """Serialise a check-then-write section on `name` until commit/rollback (SQLite: BEGIN IMMEDIATE)."""
        self._raw.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (name,))

    def close(self):
        raw, self._raw = self._raw, None
        if raw is None:
            return
        try:
            if not raw.closed:
                raw.rollback()
        except Exception:
            pass
        finally:
            self._pool.putconn(raw)

    def __del__(self):  # a code path that forgot close() must not starve the pool
        try:
            self.close()
        except Exception:
            pass


_pools: Dict[tuple, Any] = {}
_pools_lock = threading.Lock()


def _pool():
    from psycopg_pool import ConnectionPool

    key = (settings.DATABASE_URL, settings.DATABASE_SCHEMA, os.getpid())
    pool = _pools.get(key)
    if pool is None:
        with _pools_lock:
            pool = _pools.get(key)
            if pool is None:
                kwargs: Dict[str, Any] = {}
                if settings.DATABASE_SCHEMA:
                    kwargs["options"] = f"-c search_path={settings.DATABASE_SCHEMA}"
                pool = ConnectionPool(
                    settings.DATABASE_URL, min_size=settings.DB_POOL_MIN, max_size=settings.DB_POOL_MAX,
                    timeout=settings.DB_POOL_TIMEOUT_SECONDS, kwargs=kwargs, check=ConnectionPool.check_connection,
                    open=True, name=f"malemitra-{len(_pools)}")
                _pools[key] = pool
    return pool


def close_pools() -> None:
    with _pools_lock:
        pools = [p for (_, _, pid), p in _pools.items() if pid == os.getpid()]
        _pools.clear()
    for p in pools:
        try:
            p.close()
        except Exception:
            pass


atexit.register(close_pools)


# ── SQLite ────────────────────────────────────────────────────────────────────────────────────────────

class SqliteConnection(sqlite3.Connection):
    def begin_write(self, name: str = "global") -> None:
        self.execute("BEGIN IMMEDIATE")


def get_db_connection():
    if is_postgres():
        pool = _pool()
        return PgConnection(pool, pool.getconn())
    os.makedirs(os.path.dirname(settings.DATABASE_PATH) or ".", exist_ok=True)
    # timeout: wait for a competing writer instead of failing at once with "database is locked".
    conn = sqlite3.connect(settings.DATABASE_PATH, timeout=15, factory=SqliteConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 15000")
    conn.execute("PRAGMA foreign_keys = OFF")  # legacy rows may reference removed incidents
    return conn


def table_columns(conn, table: str) -> Set[str]:
    if is_postgres():
        rows = conn.execute("SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema = current_schema() AND table_name = ?", (table,)).fetchall()
        return {r[0] for r in rows}
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


@contextlib.contextmanager
def startup_lock(name: str = "init"):
    """Cross-process lock so workers starting together don't race on migrations / first-run seeding."""
    if is_postgres():
        import psycopg
        # Advisory locks are database-wide, so the schema is part of the key. The lock lives on its own
        # connection (session level) and is released when that connection closes.
        key = zlib.crc32(f"{settings.DATABASE_SCHEMA}:{name}".encode())
        with psycopg.connect(settings.DATABASE_URL, autocommit=True) as lock_conn:
            lock_conn.execute("SELECT pg_advisory_lock(%s)", (key,))
            if settings.DATABASE_SCHEMA:
                lock_conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{settings.DATABASE_SCHEMA}"')
            yield
        return
    try:
        import fcntl
    except ImportError:  # non-POSIX: single-process development only
        yield
        return
    os.makedirs(os.path.dirname(settings.DATABASE_PATH) or ".", exist_ok=True)
    with open(f"{settings.DATABASE_PATH}.{name}.lock", "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def init_db(seed: bool = True):
    with startup_lock("init"):
        _init_db(seed)


_PG_GRAPH_EPOCH_FN = """
CREATE OR REPLACE FUNCTION malemitra_bump_graph_epoch() RETURNS trigger AS $$
BEGIN
    UPDATE shared_state SET version = version + 1 WHERE key = 'graph';
    RETURN NULL;
END
$$ LANGUAGE plpgsql
"""


def _init_db(seed: bool = True):
    conn = get_db_connection()
    cursor = conn.cursor()
    pg = is_postgres()

    def ddl(sql: str) -> None:
        # The schema is written once. SQLite's REAL/INTEGER are 8 bytes; PostgreSQL's are 4 (GPS coordinates
        # and large simulation seeds would be mangled or rejected), so widen them there.
        if pg:
            sql = re.sub(r"\bINTEGER\b", "BIGINT", re.sub(r"\bREAL\b", "DOUBLE PRECISION", sql))
            # SQLite ran with foreign_keys=OFF (legacy rows may point at removed incidents); keep that behaviour
            # so existing data migrates as-is instead of being rejected.
            sql = re.sub(r",\s*FOREIGN KEY \([^)]*\) REFERENCES \w+\([^)]*\)", "", sql)
        cursor.execute(sql)

    if not pg:
        # WAL lets readers and the single writer proceed concurrently (persisted in the DB file).
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")

    # Users table
    ddl("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        role TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        team_id TEXT,
        active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    )
    """)

    # Password reset tokens
    ddl("""
    CREATE TABLE IF NOT EXISTS password_reset_tokens (
        token TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        email TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        used INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """)
    
    # Response Teams
    ddl("""
    CREATE TABLE IF NOT EXISTS response_teams (
        id TEXT PRIMARY KEY,
        label TEXT NOT NULL,
        status TEXT NOT NULL,
        current_incident_id TEXT,
        demo_flag INTEGER DEFAULT 1
    )
    """)
    
    # Incidents table
    ddl("""
    CREATE TABLE IF NOT EXISTS incidents (
        id TEXT PRIMARY KEY,
        road_edge_id TEXT,
        road_name TEXT,
        lat REAL NOT NULL,
        lon REAL NOT NULL,
        type TEXT NOT NULL,
        severity TEXT NOT NULL,
        status TEXT NOT NULL,
        confidence REAL DEFAULT 0.85,
        reported_by_id TEXT NOT NULL,
        reported_by_name TEXT NOT NULL,
        reports_count INTEGER DEFAULT 1,
        assigned_team_id TEXT,
        verification_notes TEXT,
        water_depth_cm REAL,
        restriction_notes TEXT,
        is_blocked INTEGER DEFAULT 0,
        agent_summary TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)
    
    # Incident Reports (individual submissions that can aggregate into incidents)
    ddl("""
    CREATE TABLE IF NOT EXISTS incident_reports (
        id TEXT PRIMARY KEY,
        incident_id TEXT NOT NULL,
        reporter_id TEXT NOT NULL,
        reporter_name TEXT NOT NULL,
        lat REAL NOT NULL,
        lon REAL NOT NULL,
        description TEXT NOT NULL,
        evidence_note TEXT,
        photo_url TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (incident_id) REFERENCES incidents(id)
    )
    """)
    
    # Incident Evidence
    ddl("""
    CREATE TABLE IF NOT EXISTS incident_evidence (
        id TEXT PRIMARY KEY,
        incident_id TEXT NOT NULL,
        submitted_by TEXT NOT NULL,
        submitter_name TEXT NOT NULL,
        evidence_type TEXT NOT NULL,
        text_notes TEXT NOT NULL,
        water_depth_cm REAL,
        is_impassable INTEGER,
        photo_url TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (incident_id) REFERENCES incidents(id)
    )
    """)
    
    # Agent Events log
    ddl("""
    CREATE TABLE IF NOT EXISTS agent_events (
        id TEXT PRIMARY KEY,
        incident_id TEXT,
        agent TEXT NOT NULL,
        action TEXT NOT NULL,
        input_refs TEXT,
        result TEXT NOT NULL,
        data_mode TEXT DEFAULT 'simulated',
        requires_approval INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """)

    # Admin decision on an agent recommendation (approve / dismiss). Added after the first
    # release, so existing databases are migrated in place.
    existing_cols = table_columns(conn, "agent_events")
    for col in ("decision", "decided_by", "decided_at"):
        if col not in existing_cols:
            ddl(f"ALTER TABLE agent_events ADD COLUMN {col} TEXT")

    # Contact number for SMS/push notifications (optional).
    user_cols = table_columns(conn, "users")
    if "phone" not in user_cols:
        ddl("ALTER TABLE users ADD COLUMN phone TEXT")
    # Bumped on logout / password change / reset; session tokens carry the version they were issued at.
    if "token_version" not in user_cols:
        ddl("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0")

    # Notification outbox: rows are written in the same transaction as the change that caused them
    # and delivered by the dispatcher (retry with backoff; leases make it safe with several workers).
    ddl("""
    CREATE TABLE IF NOT EXISTS notifications (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        channel TEXT NOT NULL,
        recipient TEXT NOT NULL,
        kind TEXT NOT NULL,
        subject TEXT NOT NULL,
        body TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0,
        next_attempt_at TEXT NOT NULL,
        lease_until TEXT,
        claimed_by TEXT,
        last_error TEXT,
        dedupe_key TEXT,
        created_at TEXT NOT NULL,
        sent_at TEXT
    )
    """)

    # Shared (cross-worker) state: sliding-window rate-limit hits, a versioned key/value store the workers
    # poll to stay consistent, and leases for singleton background jobs.
    ddl("""
    CREATE TABLE IF NOT EXISTS rate_hits (
        bucket TEXT NOT NULL,
        key TEXT NOT NULL,
        ts REAL NOT NULL
    )
    """)
    ddl("""
    CREATE TABLE IF NOT EXISTS shared_state (
        key TEXT PRIMARY KEY,
        version INTEGER NOT NULL DEFAULT 0,
        value TEXT,
        updated_at TEXT NOT NULL
    )
    """)
    ddl("""
    CREATE TABLE IF NOT EXISTS leases (
        name TEXT PRIMARY KEY,
        holder TEXT NOT NULL,
        until REAL NOT NULL
    )
    """)

    # Uploaded photos (files live on disk under UPLOAD_DIR; rows track owner, type and whether a report uses them).
    ddl("""
    CREATE TABLE IF NOT EXISTS uploads (
        id TEXT PRIMARY KEY,
        owner_id TEXT NOT NULL,
        filename TEXT NOT NULL,
        mime TEXT NOT NULL,
        size INTEGER NOT NULL,
        sha256 TEXT NOT NULL,
        created_at TEXT NOT NULL,
        created_ts REAL NOT NULL,
        attached INTEGER NOT NULL DEFAULT 0
    )
    """)

    # Every write that can change road closures/hazards bumps the 'graph' epoch inside the same transaction
    # (so workers never miss a change and no call site has to remember to). Workers poll it and rebuild.
    cursor.execute("INSERT INTO shared_state (key, version, value, updated_at) VALUES ('graph', 0, NULL, ?) "
                   "ON CONFLICT (key) DO NOTHING", (utcnow().isoformat(),))
    columns = "status, severity, is_blocked, road_edge_id, reports_count"
    if pg:
        # BEFORE ... FOR EACH STATEMENT: the shared_state row is locked before any incident row, so every
        # transaction that touches incidents queues on it first and two of them can never deadlock
        # (a row-level AFTER trigger would take the locks in the opposite order). The bump becomes visible
        # only on commit, together with the change itself.
        cursor.execute(_PG_GRAPH_EPOCH_FN)
        for name, event in (
            ("trg_graph_epoch_ins", "BEFORE INSERT ON incidents"),
            ("trg_graph_epoch_upd", f"BEFORE UPDATE OF {columns} ON incidents"),
            ("trg_graph_epoch_del", "BEFORE DELETE ON incidents"),
        ):
            cursor.execute("SELECT 1 FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
                           "WHERE t.tgname = ? AND c.relname = 'incidents' "
                           "AND c.relnamespace = current_schema()::regnamespace", (name,))
            if not cursor.fetchone():
                cursor.execute(f"CREATE TRIGGER {name} {event} FOR EACH STATEMENT "
                               "EXECUTE FUNCTION malemitra_bump_graph_epoch()")
    else:
        bump = "UPDATE shared_state SET version = version + 1 WHERE key = 'graph'"
        for name, event in (
            ("trg_graph_epoch_ins", "AFTER INSERT ON incidents"),
            ("trg_graph_epoch_upd", f"AFTER UPDATE OF {columns} ON incidents"),
            ("trg_graph_epoch_del", "AFTER DELETE ON incidents"),
        ):
            cursor.execute(f"CREATE TRIGGER IF NOT EXISTS {name} {event} BEGIN {bump}; END")

    # Individual responder an incident is assigned to (NULL = sitting in the team queue).
    if "assigned_responder_id" not in table_columns(conn, "incidents"):
        ddl("ALTER TABLE incidents ADD COLUMN assigned_responder_id TEXT")
    
    # Audit Events log
    ddl("""
    CREATE TABLE IF NOT EXISTS audit_events (
        id TEXT PRIMARY KEY,
        actor_id TEXT NOT NULL,
        actor_name TEXT NOT NULL,
        action TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        before_state TEXT,
        after_state TEXT,
        created_at TEXT NOT NULL
    )
    """)
    
    # Simulation Runs
    ddl("""
    CREATE TABLE IF NOT EXISTS simulation_runs (
        id TEXT PRIMARY KEY,
        seed INTEGER NOT NULL,
        graph_version INTEGER NOT NULL,
        blocked_edges TEXT NOT NULL,
        summary_metrics TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    # Indexes for the lookups the API does on every request / poll.
    for stmt in (
        "CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status)",
        "CREATE INDEX IF NOT EXISTS idx_incidents_edge ON incidents(road_edge_id)",
        "CREATE INDEX IF NOT EXISTS idx_incidents_team ON incidents(assigned_team_id)",
        "CREATE INDEX IF NOT EXISTS idx_incidents_responder ON incidents(assigned_responder_id)",
        "CREATE INDEX IF NOT EXISTS idx_reports_incident ON incident_reports(incident_id, reporter_id)",
        "CREATE INDEX IF NOT EXISTS idx_evidence_incident ON incident_evidence(incident_id)",
        "CREATE INDEX IF NOT EXISTS idx_agent_events_created ON agent_events(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_agent_events_incident ON agent_events(incident_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_events(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_reset_email ON password_reset_tokens(email)",
        "CREATE INDEX IF NOT EXISTS idx_uploads_orphans ON uploads(attached, created_ts)",
        "CREATE INDEX IF NOT EXISTS idx_reports_reporter ON incident_reports(reporter_id)",
        "CREATE INDEX IF NOT EXISTS idx_rate_hits ON rate_hits(bucket, key, ts)",
        "CREATE INDEX IF NOT EXISTS idx_notifications_due ON notifications(status, next_attempt_at)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_notifications_dedupe ON notifications(dedupe_key, channel, recipient) "
        "WHERE dedupe_key IS NOT NULL",
    ):
        cursor.execute(stmt)

    # Schema version. Bump SCHEMA_VERSION when adding a migration above.
    # An older build must not run against a database a newer build already migrated.
    if pg:
        cursor.execute("CREATE TABLE IF NOT EXISTS schema_info (id INTEGER PRIMARY KEY, version INTEGER NOT NULL)")
        cursor.execute("INSERT INTO schema_info (id, version) VALUES (1, 0) ON CONFLICT (id) DO NOTHING")
        current = cursor.execute("SELECT version FROM schema_info WHERE id = 1").fetchone()[0]
    else:
        current = cursor.execute("PRAGMA user_version").fetchone()[0]
    if current > SCHEMA_VERSION:
        conn.close()
        raise RuntimeError(
            f"Database schema version {current} is newer than this build supports ({SCHEMA_VERSION}). "
            "Deploy the newer release or restore a matching backup.")
    if current < SCHEMA_VERSION:
        if pg:
            cursor.execute("UPDATE schema_info SET version = ? WHERE id = 1", (SCHEMA_VERSION,))
        else:
            cursor.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    conn.commit()
    if seed:
        seed_initial_data(conn)
    conn.close()


def seed_initial_data(conn):
    cursor = conn.cursor()
    now = utcnow().isoformat()

    # Demo accounts exist only in DEMO_MODE (shared, publicly documented password).
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0 and settings.DEMO_MODE:
        demo_hash = hash_password("demo123")
        demo_users = [
            ("usr-citizen-1", "Citizen Commuter (Pooja)", "citizen@malemitra.in", "citizen", demo_hash, None, 1, now),
            ("usr-citizen-2", "Citizen Driver (Kiran)", "kiran@malemitra.in", "citizen", demo_hash, None, 1, now),
            ("usr-admin-1", "BBMP Monsoon Control Room Admin", "admin@malemitra.in", "admin", demo_hash, None, 1, now),
            ("usr-resp-1", "Inspector Ramesh (Stormwater Unit)", "responder1@malemitra.in", "responder", demo_hash, "team-alpha", 1, now),
            ("usr-resp-2", "Officer Kavitha (Traffic & Pump Unit)", "responder2@malemitra.in", "responder", demo_hash, "team-beta", 1, now),
        ]
        cursor.executemany(
            "INSERT INTO users (id, name, email, role, password_hash, team_id, active, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", demo_users)

    if not settings.DEMO_MODE:
        # A database that was first created in demo mode must not keep its public demo logins.
        cursor.execute("UPDATE users SET active = 0 WHERE id IN "
                       "('usr-citizen-1','usr-citizen-2','usr-admin-1','usr-resp-1','usr-resp-2')")
        if settings.BOOTSTRAP_ADMIN_EMAIL and settings.BOOTSTRAP_ADMIN_PASSWORD:
            email = settings.BOOTSTRAP_ADMIN_EMAIL.lower().strip()
            cursor.execute("SELECT 1 FROM users WHERE email = ?", (email,))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO users (id, name, email, role, password_hash, team_id, active, created_at) "
                    "VALUES (?, ?, ?, 'admin', ?, NULL, 1, ?)",
                    (f"usr-admin-{uuid.uuid4().hex[:6]}", "Administrator", email,
                     hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD), now))
    
    # Check if response teams already seeded
    cursor.execute("SELECT COUNT(*) FROM response_teams")
    if cursor.fetchone()[0] == 0:
        demo_teams = [
            ("team-alpha", "Team Alpha - Stormwater Response", "available", None, 1),
            ("team-beta", "Team Beta - Traffic & Debris Unit", "available", None, 1),
            ("team-gamma", "Team Gamma - Quick Drainage & Pump", "available", None, 1),
        ]
        cursor.executemany("INSERT INTO response_teams VALUES (?, ?, ?, ?, ?)", demo_teams)
    
    conn.commit()
