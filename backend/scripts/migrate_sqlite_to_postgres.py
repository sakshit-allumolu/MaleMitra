"""One-off copy of an existing SQLite database into PostgreSQL.

    DATABASE_URL=postgresql://user:pass@host:5432/malemitra \\
        python -m backend.scripts.migrate_sqlite_to_postgres [path/to/malemitra.db] [--replace]

* Stop the application first (writes made to SQLite after the copy would be lost).
* The schema is created with the application's own migration code, then every table is copied in one transaction.
* Refuses to run into a database that already holds users/incidents unless --replace is given (which empties
  the copied tables first). Ephemeral tables (rate limits, leases, shared_state) are not copied.
* Uploaded photos live on disk, not in the database: copy the uploads folder separately if it moves.
"""
import os
import sqlite3
import sys

from backend.app.config import settings

from backend.scripts.backup import PG_TABLES as TABLES  # parents before children


def migrate(sqlite_path: str, replace: bool = False) -> dict:
    from backend.app.models import database

    if not database.is_postgres():
        raise SystemExit("Set DATABASE_URL to a postgresql:// URL first.")
    if not os.path.exists(sqlite_path):
        raise SystemExit(f"SQLite file not found: {sqlite_path}")

    database.init_db(seed=False)          # tables, indexes and the graph-epoch triggers
    src = sqlite3.connect(sqlite_path)
    src.row_factory = sqlite3.Row
    dst = database.get_db_connection()
    copied = {}
    try:
        existing = {t: dst.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("users", "incidents")}
        if any(existing.values()) and not replace:
            raise SystemExit(f"PostgreSQL already has data ({existing}). Re-run with --replace to overwrite it.")
        if replace:
            for t in reversed(TABLES):
                dst.execute(f"DELETE FROM {t}")
        for table in TABLES:
            src_cols = [r["name"] for r in src.execute(f"PRAGMA table_info({table})")]
            if not src_cols:
                continue                   # table does not exist in an older database
            dst_cols = database.table_columns(dst, table)
            cols = [c for c in src_cols if c in dst_cols]
            rows = [tuple(r[c] for c in cols) for r in src.execute(f"SELECT {', '.join(cols)} FROM {table}")]
            if rows:
                dst.executemany(
                    f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", rows)
            copied[table] = len(rows)
        dst.commit()
    except BaseException:
        dst.rollback()
        raise
    finally:
        dst.close()
        src.close()

    # Row counts must match before anyone points the app at the new database.
    check = database.get_db_connection()
    src = sqlite3.connect(sqlite_path)
    try:
        for table, n in copied.items():
            got = check.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if got != n:
                raise SystemExit(f"verification failed for {table}: copied {n}, PostgreSQL has {got}")
    finally:
        check.close()
        src.close()
    # Seeds anything still missing (teams/demo users are only inserted into empty tables).
    database.init_db()
    return copied


def main(argv: list) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    path = args[0] if args else settings.DATABASE_PATH
    result = migrate(path, replace="--replace" in argv)
    for table, n in result.items():
        print(f"{table:24s} {n}")
    print("done - start the application with DATABASE_URL set")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
