"""
Two real server processes sharing one database, to prove state stays consistent across workers/replicas.
(The in-process tests cannot show this: they share a single road graph object.)
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ADMIN = {"Authorization": "Bearer usr-admin-1"}
CITIZEN = {"Authorization": "Bearer usr-citizen-1"}
RESP1 = {"Authorization": "Bearer usr-resp-1"}


def _db_env(tmp: str, name: str) -> dict:
    """Database settings for a child server: its own SQLite file, or its own schema on TEST_DATABASE_URL."""
    url = os.environ.get("TEST_DATABASE_URL", "")
    if url:
        return {"DATABASE_URL": url, "DATABASE_SCHEMA": f"mm_{name}_{os.urandom(4).hex()}",
                "DATABASE_PATH": os.path.join(tmp, f"{name}.db")}
    return {"DATABASE_URL": "", "DATABASE_SCHEMA": "", "DATABASE_PATH": os.path.join(tmp, f"{name}.db")}


def _drop_schema(env: dict) -> None:
    if env.get("DATABASE_URL"):
        import psycopg
        with psycopg.connect(env["DATABASE_URL"], autocommit=True) as c:
            c.execute(f'DROP SCHEMA IF EXISTS "{env["DATABASE_SCHEMA"]}" CASCADE')


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Node:
    def __init__(self, env):
        self.port = _free_port()
        self.base = f"http://127.0.0.1:{self.port}/api/v1"
        self.log = tempfile.TemporaryFile()
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", str(self.port),
             "--log-level", "warning"],
            cwd=ROOT, env=env, stdout=self.log, stderr=subprocess.STDOUT)
        deadline = time.time() + 40
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"server exited early:\n{self.output()}")
            try:
                self.call("GET", "/health")
                return
            except Exception:
                time.sleep(0.3)
        raise RuntimeError(f"server did not start:\n{self.output()}")

    def output(self) -> str:
        self.log.seek(0)
        return self.log.read().decode("utf-8", "replace")

    def call(self, method, path, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"null")

    def blocked(self):
        return {e["edge_id"] for e in self.call("GET", "/routes/network")[1]["edges"] if e["is_blocked"]}

    def hazard(self, edge_id):
        return next(e["hazard_severity"] for e in self.call("GET", "/routes/network")[1]["edges"] if e["edge_id"] == edge_id)

    def stop(self):
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


@pytest.fixture(scope="module")
def cluster():
    tmp = tempfile.mkdtemp(prefix="malemitra-mw-")
    env = {**os.environ, **_db_env(tmp, "mw"), "DEMO_MODE": "true",
           "RATE_LIMIT_ENABLED": "true", "RATE_LIMIT_AUTH_PER_MIN": "6", "NOTIFY_POLL_SECONDS": "3600",
           "TOMTOM_API_KEY": "", "PYTHONPATH": ROOT}
    a = Node(env)   # first start creates and seeds the database
    b = Node(env)
    yield a, b
    a.stop()
    b.stop()
    _drop_schema(env)


def _drive_to_block(node):
    body = {"lat": 12.9420, "lon": 77.6090, "type": "waterlogging", "severity": "high", "description": "Underpass flooded"}
    code, inc = node.call("POST", "/reports", body, CITIZEN)
    assert code in (200, 201), inc
    iid = inc["id"]
    assert node.call("POST", f"/incidents/{iid}/review", {}, ADMIN)[0] == 200
    assert node.call("POST", f"/incidents/{iid}/assign", {"team_id": "team-alpha", "responder_id": "usr-resp-1"}, ADMIN)[0] == 200
    assert node.call("POST", f"/incidents/{iid}/verify", {"findings": "55cm water", "water_depth_cm": 55}, RESP1)[0] == 200
    return iid, inc["road_edge_id"]


def _until(fn, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        v = fn()
        if v:
            return v
        time.sleep(0.2)
    return fn()


def test_closure_authorised_on_one_worker_is_enforced_on_the_other(cluster):
    a, b = cluster
    iid, edge = _drive_to_block(a)
    assert edge and edge not in b.blocked()
    assert a.call("POST", f"/incidents/{iid}/restriction", {"action": "authorize_block"}, ADMIN)[0] == 200
    assert edge in a.blocked()
    assert edge in b.blocked(), "worker B still routes over a road worker A closed"
    # Routing on B must actually avoid it, not just report it: a route that crosses the closed edge
    # is flagged as such, and the recommended one must not cross it.
    code, res = b.call("POST", "/routes/compare", {"origin": {"lat": 12.9352, "lon": 77.6245},
                                                   "destination": {"lat": 12.9150, "lon": 77.6350}}, CITIZEN)
    assert code == 200, res
    assert res["active_restrictions_count"] >= 1
    assert all(r["blocked_edges_crossed"] == 0 for r in res["routes"] if r["type"] != "fastest"), res["routes"]
    a.call("POST", f"/incidents/{iid}/clearance", {"clearance_findings": "drained"}, RESP1)
    assert a.call("POST", f"/incidents/{iid}/restriction", {"action": "authorize_reopen"}, ADMIN)[0] == 200
    assert edge not in b.blocked(), "worker B kept a road closed after A reopened it"


def test_the_latest_ripple_result_is_visible_from_every_worker(cluster):
    a, b = cluster
    iid, edge = _drive_to_block(a)
    a.call("POST", f"/incidents/{iid}/restriction", {"action": "authorize_block"}, ADMIN)
    ra, rb = a.call("GET", "/simulations/latest")[1], b.call("GET", "/simulations/latest")[1]
    assert ra.get("run_id") and ra["run_id"] == rb.get("run_id")
    assert edge in rb["blocked_edges"]
    a.call("POST", f"/incidents/{iid}/clearance", {"clearance_findings": "drained"}, RESP1)
    a.call("POST", f"/incidents/{iid}/restriction", {"action": "authorize_reopen"}, ADMIN)


def test_a_hazard_reported_on_one_worker_reaches_the_other(cluster):
    a, b = cluster
    body = {"lat": 12.9510, "lon": 77.6160, "type": "waterlogging", "severity": "medium", "description": "Standing water"}
    code, inc = b.call("POST", "/reports", body, CITIZEN)
    assert code in (200, 201), inc
    edge = inc["road_edge_id"]
    assert edge and _until(lambda: a.hazard(edge) != "none")
    b.call("POST", f"/incidents/{inc['id']}/restriction", {"action": "reject"}, ADMIN)
    assert _until(lambda: a.hazard(edge) == "none")


def test_rate_limits_are_shared_between_workers(cluster):
    a, b = cluster
    codes = []
    for i in range(10):  # a different email each time, so this exercises the per-IP limit, not the account lockout
        creds = {"email": f"nobody{i}@example.org", "password": "wrong-password"}
        codes.append((a if i % 2 == 0 else b).call("POST", "/auth/login", creds)[0])
    assert codes[:6] == [401] * 6          # the 6 allowed attempts are spread over both workers
    assert 429 in codes[6:], f"limit ignored when attempts alternate between workers: {codes}"
    assert codes.count(401) == 6


def test_only_one_worker_holds_the_traffic_polling_lease(cluster):
    from backend.app import shared
    assert shared.acquire_lease("t-lease", 30, holder="w1") is True
    assert shared.acquire_lease("t-lease", 30, holder="w2") is False
    assert shared.acquire_lease("t-lease", 30, holder="w1") is True      # holder renews
    assert shared.acquire_lease("t-lease", -1, holder="w1") is True      # let it expire
    assert shared.acquire_lease("t-lease", 30, holder="w2") is True      # failover


def test_workers_starting_together_seed_the_database_exactly_once():
    tmp = tempfile.mkdtemp(prefix="malemitra-race-")
    env = {**os.environ, **_db_env(tmp, "race"), "DEMO_MODE": "true",
           "RATE_LIMIT_ENABLED": "false", "NOTIFY_POLL_SECONDS": "3600", "TOMTOM_API_KEY": "", "PYTHONPATH": ROOT}
    code = "import backend.app.main as m, asyncio\nasync def go():\n  async with m.lifespan(m.app): pass\nasyncio.run(go())"
    procs = [subprocess.Popen([sys.executable, "-c", code], cwd=ROOT, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT) for _ in range(4)]
    outs = [p.communicate(timeout=90)[0].decode() for p in procs]
    assert all(p.returncode == 0 for p in procs), outs
    if env["DATABASE_URL"]:
        import psycopg
        conn = psycopg.connect(env["DATABASE_URL"], options=f"-c search_path={env['DATABASE_SCHEMA']}")
    else:
        import sqlite3
        conn = sqlite3.connect(env["DATABASE_PATH"])
    try:
        assert conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 5
    finally:
        conn.close()
        _drop_schema(env)

