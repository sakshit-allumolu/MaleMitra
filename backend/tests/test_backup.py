import os
import sqlite3
import tarfile

from backend.app.config import settings
from backend.app.models.database import get_db_connection, is_postgres
from backend.scripts import backup


def _count():
    c = get_db_connection()
    try:
        return c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        c.close()


def test_backup_roundtrip_restores_deleted_data(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    os.makedirs(settings.UPLOAD_DIR)
    with open(os.path.join(settings.UPLOAD_DIR, "x.png"), "wb") as f:
        f.write(b"png-bytes")
    before = _count()
    archive = backup.create(str(tmp_path / "bk"))
    assert os.path.exists(archive)

    c = get_db_connection()
    c.execute("INSERT INTO users (id,name,email,role,password_hash,active,created_at) "
              "VALUES ('usr-tmp-bk','Tmp','tmp-bk@example.com','citizen','x',1,'2026-01-01')")
    c.commit(); c.close()
    os.remove(os.path.join(settings.UPLOAD_DIR, "x.png"))
    assert _count() == before + 1

    backup.restore(archive)
    assert _count() == before
    assert open(os.path.join(settings.UPLOAD_DIR, "x.png"), "rb").read() == b"png-bytes"
    if not is_postgres():
        chk = sqlite3.connect(settings.DATABASE_PATH)
        assert chk.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        chk.close()


def test_restore_rejects_path_traversal(tmp_path):
    evil = tmp_path / "evil.tar.gz"
    payload = tmp_path / "p"
    payload.write_text("x")
    with tarfile.open(evil, "w:gz") as t:
        t.add(payload, arcname="../escape.txt")
    try:
        backup.restore(str(evil))
        assert False, "should have refused"
    except RuntimeError as e:
        assert "unsafe" in str(e)


def test_prune_keeps_newest(tmp_path):
    for i in range(5):
        (tmp_path / f"malemitra-2026010{i}T000000Z.tar.gz").write_text("x")
    removed = backup.prune(str(tmp_path), 2)
    assert len(removed) == 3
    assert sorted(os.listdir(tmp_path)) == ["malemitra-20260103T000000Z.tar.gz", "malemitra-20260104T000000Z.tar.gz"]


def test_refuses_database_from_a_newer_release(tmp_path, monkeypatch):
    import pytest
    from backend.app.models import database
    if database.is_postgres():
        shared_schema = settings.DATABASE_SCHEMA
        future_schema = f"{shared_schema}_future"
        monkeypatch.setattr(settings, "DATABASE_SCHEMA", future_schema)
        try:
            database.init_db()
            c = database.get_db_connection()
            c.execute("UPDATE schema_info SET version = ? WHERE id = 1", (database.SCHEMA_VERSION + 1,))
            c.commit(); c.close()
            with pytest.raises(RuntimeError, match="newer"):
                database.init_db()
        finally:
            import psycopg
            monkeypatch.setattr(settings, "DATABASE_SCHEMA", shared_schema)  # later tests use the shared schema
            database.close_pools()
            with psycopg.connect(settings.DATABASE_URL, autocommit=True) as pg:
                pg.execute(f'DROP SCHEMA IF EXISTS "{future_schema}" CASCADE')
        return
    path = tmp_path / "future.db"
    monkeypatch.setattr(settings, "DATABASE_PATH", str(path))
    database.init_db()
    c = sqlite3.connect(path)
    assert c.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
    c.execute(f"PRAGMA user_version = {database.SCHEMA_VERSION + 1}")
    c.commit(); c.close()
    with pytest.raises(RuntimeError, match="newer"):
        database.init_db()
