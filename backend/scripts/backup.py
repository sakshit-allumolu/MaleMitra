"""Consistent backup / restore of the database and the uploads folder.

    python -m backend.scripts.backup create  [DEST_DIR]        # default: ./backups
    python -m backend.scripts.backup restore ARCHIVE.tar.gz    # stop the app first
    python -m backend.scripts.backup prune   [DEST_DIR] [KEEP] # keep the newest KEEP archives (default 14)

SQLite: `create` uses SQLite's online backup API, so it is safe while the app is running (no torn pages,
unlike copying the .db file). PostgreSQL (DATABASE_URL set): every table is read inside one REPEATABLE READ
snapshot and stored as JSON, so the dump is consistent and does not depend on the pg_dump version.
An archive can only be restored into the kind of database it was taken from. Archives hold the database and
the uploads folder.
"""
import glob
import json
import os
import shutil
import sqlite3
import sys
import tarfile
import tempfile
from datetime import datetime, timezone

from backend.app.config import settings
from backend.app.models import database
from backend.app.services.upload_service import _dir as uploads_dir

DB_NAME = "malemitra.db"
PG_NAME = "database.json"
# Parents before children. Rate-limit hits, leases and shared_state are rebuilt by the running system.
PG_TABLES = [
    "users", "password_reset_tokens", "response_teams", "incidents", "incident_reports", "incident_evidence",
    "agent_events", "notifications", "uploads", "audit_events", "simulation_runs",
]


def _dump_postgres(path: str) -> None:
    conn = database.get_db_connection()
    try:
        conn._raw.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        data = {}
        for table in PG_TABLES:
            cur = conn.execute(f"SELECT * FROM {table}")
            cols = [d.name for d in cur.description]
            data[table] = {"columns": cols, "rows": [list(r) for r in cur.fetchall()]}
    finally:
        conn.close()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"schema_version": database.SCHEMA_VERSION, "tables": data}, fh)


def _load_postgres(path: str) -> None:
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    if payload.get("schema_version", 0) > database.SCHEMA_VERSION:
        raise RuntimeError("archive was taken by a newer release than this build supports")
    database.init_db(seed=False)
    conn = database.get_db_connection()
    try:
        for table in reversed(PG_TABLES):
            conn.execute(f"DELETE FROM {table}")
        known = {t: database.table_columns(conn, t) for t in PG_TABLES}
        for table in PG_TABLES:
            spec = payload["tables"].get(table)
            if not spec or not spec["rows"]:
                continue
            idx = [i for i, c in enumerate(spec["columns"]) if c in known[table]]
            cols = [spec["columns"][i] for i in idx]
            conn.executemany(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                             [tuple(r[i] for i in idx) for r in spec["rows"]])
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def create(dest_dir: str = "backups") -> str:
    os.makedirs(dest_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = os.path.join(dest_dir, f"malemitra-{stamp}.tar.gz")
    with tempfile.TemporaryDirectory() as tmp:
        if database.is_postgres():
            snap, arcname = os.path.join(tmp, PG_NAME), PG_NAME
            _dump_postgres(snap)
        else:
            snap, arcname = os.path.join(tmp, DB_NAME), DB_NAME
            src = sqlite3.connect(settings.DATABASE_PATH, timeout=30)
            dst = sqlite3.connect(snap)
            try:
                src.backup(dst)
            finally:
                dst.close()
                src.close()
            check = sqlite3.connect(snap)
            try:
                if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("backup failed the integrity check; not writing an archive")
            finally:
                check.close()
        with tarfile.open(out, "w:gz") as tar:
            tar.add(snap, arcname=arcname)
            up = uploads_dir()
            if os.path.isdir(up):
                tar.add(up, arcname="uploads")
    return out


def restore(archive: str) -> None:
    db_path = settings.DATABASE_PATH
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(archive, "r:gz") as tar:
            for m in tar.getmembers():  # refuse path traversal / links in a tampered archive
                if m.name.startswith(("/", "..")) or ".." in m.name.split("/") or not (m.isfile() or m.isdir()):
                    raise RuntimeError(f"unsafe member in archive: {m.name}")
            tar.extractall(tmp, filter="data")
        sqlite_snap, pg_snap = os.path.join(tmp, DB_NAME), os.path.join(tmp, PG_NAME)
        if not os.path.exists(sqlite_snap) and not os.path.exists(pg_snap):
            raise RuntimeError("archive has no database")
        if database.is_postgres():
            if not os.path.exists(pg_snap):
                raise RuntimeError("this archive holds a SQLite database; load it into PostgreSQL with "
                                   "python -m backend.scripts.migrate_sqlite_to_postgres")
            _load_postgres(pg_snap)
        else:
            if not os.path.exists(sqlite_snap):
                raise RuntimeError("this archive holds a PostgreSQL dump; unset DATABASE_URL only if you "
                                   "really want to restore it somewhere else (it cannot be loaded into SQLite)")
            check = sqlite3.connect(sqlite_snap)
            try:
                if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("archive database is corrupt")
            finally:
                check.close()
            os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
            if os.path.exists(db_path):  # keep what is being replaced
                shutil.copy2(db_path, f"{db_path}.pre-restore-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}")
            for suffix in ("-wal", "-shm"):  # stale journals would be replayed onto the restored file
                if os.path.exists(db_path + suffix):
                    os.remove(db_path + suffix)
            shutil.copy2(sqlite_snap, db_path)
        up_src = os.path.join(tmp, "uploads")
        if os.path.isdir(up_src):
            up = uploads_dir()
            os.makedirs(up, exist_ok=True)
            for f in os.listdir(up_src):
                shutil.copy2(os.path.join(up_src, f), os.path.join(up, f))


def prune(dest_dir: str = "backups", keep: int = 14) -> list:
    files = sorted(glob.glob(os.path.join(dest_dir, "malemitra-*.tar.gz")))
    old = files[:-keep] if keep > 0 else files
    for f in old:
        os.remove(f)
    return old


def main(argv: list) -> int:
    if len(argv) < 2 or argv[1] not in ("create", "restore", "prune"):
        print(__doc__)
        return 2
    cmd, args = argv[1], argv[2:]
    if cmd == "create":
        print(create(*args[:1]))
    elif cmd == "restore":
        if not args:
            print("restore needs an archive path")
            return 2
        restore(args[0])
        print(f"restored {args[0]} into {'PostgreSQL' if database.is_postgres() else settings.DATABASE_PATH}")
    else:
        removed = prune(args[0] if args else "backups", int(args[1]) if len(args) > 1 else 14)
        print(f"removed {len(removed)} old archive(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
