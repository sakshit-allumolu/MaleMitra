"""Put a DEMO_MODE database back to its freshly-seeded state (for rehearsing / re-running a live demo).

    docker compose exec malemitra python -m backend.scripts.reset_demo        # inside the running container
    python -m backend.scripts.reset_demo                                      # local, same env as the app

* Refuses to run unless DEMO_MODE=true, so it can never wipe a real deployment.
* Deletes all incidents, reports, evidence, agent/audit events, notifications, simulation runs, upload rows and
  password-reset tokens; frees the response teams; clears login lockouts and rate-limit counters; then re-creates
  the two sample incidents (Sony World critical + assigned, Indiranagar drain overflow).
* Keeps user accounts and the TomTom routing request counter (that one mirrors your real API quota).
* A running app notices on its next request: the delete triggers bump the shared graph epoch, which re-opens
  every road closure the demo had made.
"""
import sys

from backend.app.config import settings

# Children before parents.
_CLEAR = [
    "incident_evidence", "incident_reports", "agent_events", "notifications", "audit_events",
    "simulation_runs", "uploads", "password_reset_tokens", "incidents",
]


def reset() -> dict:
    if not settings.DEMO_MODE:
        raise SystemExit("Refusing to reset: DEMO_MODE is not true. This script only touches demo databases.")

    from backend.app.models.database import get_db_connection, init_db
    from backend.app.main import seed_demo_incidents
    from backend.app.services.tomtom_routing_service import BUDGET_BUCKET

    init_db()
    conn = get_db_connection()
    try:
        removed = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in _CLEAR}
        for t in _CLEAR:
            conn.execute(f"DELETE FROM {t}")
        conn.execute("UPDATE response_teams SET status = 'available', current_incident_id = NULL")
        conn.execute("DELETE FROM rate_hits WHERE bucket != ?", (BUDGET_BUCKET,))
        conn.commit()
    finally:
        conn.close()

    seed_demo_incidents()

    conn = get_db_connection()
    try:
        seeded = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
    finally:
        conn.close()
    return {"removed": removed, "incidents_seeded": seeded}


if __name__ == "__main__":
    result = reset()
    for table, n in result["removed"].items():
        print(f"{table:24s} cleared {n}")
    print(f"demo incidents re-created: {result['incidents_seeded']}")
    sys.exit(0 if result["incidents_seeded"] else 1)
