import os
import tempfile
import uuid

# Must happen before any backend module is imported: settings are read at import time.
# The suite runs against a throwaway database so it never touches (or depends on) local dev data.
_TMP = tempfile.mkdtemp(prefix="malemitra-tests-")
os.environ["DATABASE_PATH"] = os.path.join(_TMP, "test.db")
os.environ["DEMO_MODE"] = "true"
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
# Run the whole suite on PostgreSQL with  TEST_DATABASE_URL=postgresql://user:pass@host:5432/db pytest ...
# Every run gets its own schema (dropped at the end), so a shared server is never polluted.
_PG_URL = os.environ.get("TEST_DATABASE_URL", "")
_PG_SCHEMA = f"mm_test_{uuid.uuid4().hex[:10]}" if _PG_URL else ""
os.environ["DATABASE_URL"] = _PG_URL
os.environ["DATABASE_SCHEMA"] = _PG_SCHEMA

import pytest
from backend.app.config import settings
from backend.app.models.database import init_db

init_db()


def pytest_sessionfinish(session, exitstatus):
    if not _PG_URL:
        return
    import psycopg
    from backend.app.models.database import close_pools
    close_pools()
    with psycopg.connect(_PG_URL, autocommit=True) as c:
        c.execute(f'DROP SCHEMA IF EXISTS "{_PG_SCHEMA}" CASCADE')


@pytest.fixture(autouse=True)
def _no_proximity_merge(monkeypatch):
    """
    Most tests report at fixed coordinates over and over and expect a fresh incident each time.
    Proximity merging is switched off for them; test_report_merging.py turns it back on.
    """
    monkeypatch.setattr(settings, "DUPLICATE_RADIUS_M", 0.0)


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    from backend.app import ratelimit
    ratelimit.reset()
    yield
    ratelimit.reset()
