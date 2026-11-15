# MaleMitra (ಮಳೆ ಮಿತ್ರ)
### A Connected Monsoon Mobility and Civic Response Platform
**IBM Bobathon 2026 Submission • Theme: Smarter Streets, Better Living**

---

## 1. Executive Summary & Value Proposition

During heavy Bengaluru monsoon rainfall, commuters receive fragmented information about waterlogged roads, while citizen hazard reports, municipal control room review, and field verification are disconnected. This causes dangerous vehicle entrapment in submerged underpasses and uncoordinated response dispatch.

**MaleMitra (ಮಳೆ ಮಿತ್ರ)** connects the complete incident-to-response loop into a single deployable modular monolith:
1. **Citizen Workspace**: Submit geotagged waterlogging reports, view map hazards with verified provenance, and compare **Direct vs. MaleMitra Risk-Aware Detour vs. Alternative Corridor** routes.
2. **Administrator Workspace**: Control room triage queue, spatial road edge association, response team dispatch, and emergency road restriction/reopening authorization.
3. **Simulated Emergency Responder Workspace**: Mobile-optimized field view for on-site inspection, water depth measurement (cm), impassability verification, and dewatering clearance proposals.
4. **Signature Innovation — Graph-Based Ripple Engine**: Models how one verified road closure dynamically redirects 150 synthetic monsoon trips across bounded Bengaluru corridors (Koramangala, Indiranagar, Domlur, Ejipura, HSR, Silk Board), calculating cascading traffic migration ($\Delta v$) and Bureau of Public Roads (BPR) congestion delays.

```
Citizen Report ──► Spatial Edge Mapping ──► IncidentAgent Evidence Summary
      ▲                                                   │
      │                                                   ▼
Rerouted Citizen Route ◄── Graph Version++ ◄── Admin Closure Authorization
      │                                                   │
      ▼                                                   ▼
Ripple Engine Recomputes 150 Trips              Responder Field Inspection
(Cascade Congestion Deltas)                     (55cm Depth & Impassable Verified)
```

---

## 2. Benchmark Results (Simulated)

> **These figures come from a simulation, not field data.** They are measured on a ~20-node model of six Bengaluru neighbourhoods with 150 *synthetic* trips and a single hypothetical closure (Sony World corridor). They demonstrate that the routing logic avoids a closed road and what detour it costs in that model; they are not evidence of real-world outcomes.

MaleMitra includes a standalone, reproducible evaluation harness ([`backend/eval_benchmark.py`](backend/eval_benchmark.py:1)) running 150 seeded Origin-Destination trips on the bounded Bengaluru road graph:

| Metric | Baseline (Blind Shortest Path) | MaleMitra (Risk & Ripple Aware) | Demonstrated Impact |
| :--- | :---: | :---: | :---: |
| **Trips Crossing Blocked Road** | **38 trips (25.3%)** | **0 trips (0.0%)** | Closed road avoided by all simulated trips |
| **Mean Trip Duration** | 366.7 seconds | 381.0 seconds | +14.2s (+3.9%) Detour Trade-off |
| **Stranded / No Route Rate** | 0.0% | 0.0% | Full Network Reachability Preserved |
| **Evaluation Harness Runtime** | — | **8.8 ms** | Deterministic pure-Python engine (on the small modelled graph) |

*Benchmark outputs are persisted to [`backend/app/data/benchmark_results.json`](backend/app/data/benchmark_results.json) and [`backend/app/data/benchmark_results.csv`](backend/app/data/benchmark_results.csv).*

---

## 3. Pre-Seeded Demo Accounts (DEMO_MODE only)

With `DEMO_MODE=true` (the default) these accounts are seeded with the public password **`demo123`**. With `DEMO_MODE=false` they are **not created** (and are deactivated if a demo database is reused); see section 7.

| Role | Name | Email | Default Team / Authority |
| :--- | :--- | :--- | :--- |
| **Citizen** | Pooja (Citizen Commuter) | `citizen@malemitra.in` | Submit reports, compare routes, track hazards |
| **Administrator** | BBMP Monsoon Control Room Admin | `admin@malemitra.in` | Review triage, dispatch teams, authorize road closures/reopenings |
| **Responder 1** | Inspector Ramesh | `responder1@malemitra.in` | Team Alpha (Stormwater & Dewatering Pump Unit) |
| **Responder 2** | Officer Kavitha | `responder2@malemitra.in` | Team Beta (Traffic & Debris Unit) |

---

## 4. Agentic AI with IBM watsonx Orchestrate

MaleMitra has two layers, and the README is explicit about which is which:

**Deterministic engine (rule-based, no LLM)** - the pieces that must be predictable and auditable:
- Spatial edge mapping + rule-based confidence ([`incident_service.py`](backend/app/services/incident_service.py:1)), Dijkstra / Yen routing with hazard and BPR congestion costs ([`graph_service.py`](backend/app/services/graph_service.py:1), [`agent_service.py`](backend/app/services/agent_service.py:1)), the Ripple Engine ([`ripple_service.py`](backend/app/services/ripple_service.py:1)) and optional TomTom live traffic ([`live_traffic_service.py`](backend/app/services/live_traffic_service.py:1)).
- These rows in the Agent Timeline are tagged **rule-based**.

**Agentic layer (LLM, watsonx Orchestrate)** - an Orchestrate agent that reasons over an incident, calls MaleMitra's tools and recommends the next step:

```
Admin: "Ask agent" ──▶ /agents/analyze/{id} ──▶ watsonx Orchestrate agent (LLM)
                                                   │  calls tools over REST (X-API-Key)
   get_incident_context · estimate_bpr_load · run_ripple_what_if · compute_route · map_to_edge ...
                                                   ▼
                              submit_recommendation  ──▶  admin sees it, approves or ignores
```

- **Human in the loop**: the agent can only *recommend*. It cannot change an incident's status or close a road; admins keep that authority. Recommendations are stored with `requires_approval`.
- **Guardrails**: tools are closed unless `AGENT_TOOL_API_KEY` is set; recommended actions must be valid for the incident's current workflow state; what-if runs are sandboxed and capped; every tool call, accepted or rejected, is logged to the Agent Timeline (**LLM agent** badge).
- **Graceful degradation**: without Orchestrate credentials the app works fully; the panel shows "Not connected" and the Ask buttons are disabled.
- **Setup**: see [`orchestrate/README.md`](orchestrate/README.md) (tool import, agent definition, env vars). Includes what is verified versus what needs checking against your Orchestrate instance.

Tool and guardrail logic is covered by [`test_orchestrate_agent.py`](backend/tests/test_orchestrate_agent.py:1). A live Orchestrate round-trip requires your instance and a public tool URL and is not part of the automated tests.

---

## 5. Technology Stack

- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS / Custom Civic Design System (`#123047` navy, `#0B8B95` teal, `#3576B8` rain blue, `#C78420` amber, `#B53A3A` red), Leaflet Map with custom SVG pins, Lucide Icons.
- **Backend**: Python 3.11+, FastAPI, Pydantic v2, Starlette. Storage is SQLite (WAL mode, default, one host) or PostgreSQL 16 (set `DATABASE_URL`; several workers/hosts). A self-hosted OSRM supplies road geometry and turn-by-turn steps and falls back to the modelled graph when unreachable. With a TomTom key, the TomTom Routing API supplies live-traffic ETAs; without one the app uses a typical-hours model.
- **Algorithms**: Pure Python Graph Engine (`RoadGraph`), Dijkstra shortest path, Yen's k-shortest paths, Haversine spatial indexing, BPR congestion delay function.
- **Testing & QA**: 130+ pytest tests (acceptance, workflow, report merging, responder assignment, agent guardrails, production-readiness), run on a throwaway database; `backend/e2e_smoke.py` runs 59 checks against a live server. CI (`.github/workflows/ci.yml`) runs the backend tests, the frontend type-check + build and the Docker build.

---

## 6. How to Run Locally

> Presenting this? See [`DEMO.md`](DEMO.md) for the 5-minute script, the pre-demo checklist, likely questions and the demo-data reset command.

### Quick Start (Python + Node.js)

1. **Start Backend API Server**:
   ```bash
   ./venv/bin/python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   *Backend API & Swagger Docs will be available at `http://localhost:8000/docs`.*

2. **Start Frontend Development Server**:
   ```bash
   cd frontend
   npm run dev
   ```
   *Open `http://localhost:5173` in your browser.*

3. **Run Evaluation Benchmark CLI**:
   ```bash
   ./venv/bin/python3 backend/eval_benchmark.py
   ```

4. **Run Pytest Acceptance Test Suite**:
   ```bash
   pip install -r backend/requirements-dev.txt
   python3 -m pytest backend/tests/
   ```

---

## 7. Docker Deployment & Production Notes

**Demo** (seeded accounts, demo passwords):

```bash
docker compose up --build        # http://localhost:8000
```

**Public demo URL (free: Render)**: [`render.yaml`](render.yaml) is a Blueprint for one free Docker web service with the public-URL hardening already set (`ALLOW_LEGACY_TOKENS=false`, generated `JWT_SECRET` and `ADMIN_SIGNUP_CODE`, `EXPOSE_RESET_TOKEN=false`). Push the repo to GitHub, then in Render: New -> Blueprint -> select the repo, and paste `TOMTOM_API_KEY` when asked. The free plan sleeps after ~15 minutes idle (first request then takes 30-60 s; open the URL just before presenting) and restarts with fresh demo data. Hugging Face Docker Spaces need a paid PRO plan, so they are not used.

**Public demo URL (IBM Code Engine)**: one app, SQLite, the public OSRM server and live TomTom traffic, with demo logins kept but the public-URL holes closed (`ALLOW_LEGACY_TOKENS=false`, random `JWT_SECRET` and `ADMIN_SIGNUP_CODE`, `EXPOSE_RESET_TOKEN=false`, `CORS_ORIGINS` = the app URL):

```bash
ibmcloud login --sso && ibmcloud target -r jp-tok -g <resource_group>
./scripts/deploy_code_engine.sh      # reads secrets from .env, builds from the Dockerfile, prints the URL
```

Limits of this setup: data resets on redeploy or restart (demo incidents are re-seeded), uploaded photos are not kept, and road geometry comes from the public OSRM server (no SLA; the app falls back to graph lines if it is down). Use PostgreSQL plus a self-hosted OSRM for anything beyond a demo.

**Production** (`DEMO_MODE=false`). The app *refuses to start* unless `JWT_SECRET` (>= 32 chars) is set, legacy tokens are off and `CORS_ORIGINS` has no `*`:

```bash
export DEMO_MODE=false
export JWT_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
export CORS_ORIGINS=https://malemitra.example.org
export BOOTSTRAP_ADMIN_EMAIL=ops@example.org BOOTSTRAP_ADMIN_PASSWORD='<strong password>'
docker compose up -d --build
```

`docker compose up` starts the app, **PostgreSQL** (all application data) and a **self-hosted OSRM**: `osrm-download` fetches the Karnataka OpenStreetMap extract and crops it to Bengaluru, `osrm-prepare` builds the routing data once, `osrm` serves it. The first start downloads the map and takes a few minutes; later starts reuse it (`osrm-data` volume). To refresh the map: `docker compose rm -sf osrm && docker volume rm <project>_osrm-data && docker compose up -d`.

**Live-traffic routing (TomTom).** Put your key in the environment or `.env` (`TOMTOM_API_KEY=...`) and restart. That turns on two things: flow polling (real road speeds feed congestion costs; status at `GET /api/v1/traffic/live`) and the Routing API, which gives `/routes/compare` a measured live-vs-free-flow ETA per route instead of the time-of-day multiplier. Each route reports `traffic_source`: `tomtom_live` (matched a TomTom route on the same roads), `tomtom_corridor` (a detour TomTom would not choose, so TomTom's best route is used as an estimate) or `time_of_day_model` (no key, budget used up, or TomTom failing). Both share TomTom's free tier of about 2,500 requests/day: split it with `LIVE_TRAFFIC_DAILY_REQUEST_BUDGET` (1500) and `TOMTOM_ROUTING_DAILY_BUDGET` (800). The routing budget is a rolling 24 h cap across all workers, results are cached 2 min per origin/destination, and a circuit breaker stops calls while TomTom is failing. The key is never logged.

**Moving existing SQLite data to PostgreSQL** (stop the app first):

```bash
docker compose up -d postgres
docker compose run --rm --no-deps malemitra python -m backend.scripts.migrate_sqlite_to_postgres /app/data/malemitra.db
docker compose up -d
```

It refuses to write into a database that already has users/incidents unless you add `--replace`. `python -m backend.scripts.backup create` works on either database (PostgreSQL snapshots are taken in one consistent transaction).


See [`.env.example`](.env.example) for every setting. What `DEMO_MODE=false` changes: no demo users or seeded incidents; the demo password is rejected; public sign-up creates **citizens only** (admins create responders/admins via `POST /api/v1/auth/users`); password-reset tokens are never returned by the API (they are stored hashed); legacy bare-id tokens are rejected; CORS is same-origin unless configured.

What is built in regardless of mode: scrypt-salted passwords (legacy hashes upgrade on login), signed expiring sessions, role checks on every operational endpoint (timeline/audit/benchmark are admin-only), request validation (enums, length limits, service-area bounds), database-backed rate limits (shared by all workers), request IDs + structured logs, a `/api/v1/health` that checks the database and returns 503 when unhealthy, non-root container, and road closures that are **restored from the database on startup**.

**Known limits - read before deploying for real use:**

- **Shared state lives in the database.** Road closures/hazards, the latest ripple result, TomTom readings and rate-limit counters are shared between worker processes through the database: every request checks a shared epoch (bumped by DB triggers in the same transaction as any incident change) and rebuilds its in-memory graph when another worker changed it; one worker at a time holds a lease to poll TomTom; the notification outbox uses leases too. This is tested with real separate server processes (`backend/tests/test_multi_worker.py`), and the whole test-suite passes on both SQLite and PostgreSQL (`TEST_DATABASE_URL=postgresql://... pytest backend/tests`; CI runs both). Closures reach other workers on their next request (or SSE tick, ~2.5 s), not instantly.
- **SQLite is one host only.** Its file locking is unreliable on network filesystems, so use PostgreSQL (`DATABASE_URL`, the compose default) for several hosts or HA. On PostgreSQL the schema is created by the app on startup under an advisory lock. Foreign keys are not declared (the SQLite schema never enforced them either); the pool is per process, so keep `WEB_CONCURRENCY x DB_POOL_MAX` below PostgreSQL's `max_connections`. Not covered: PostgreSQL itself is a single node here - replication/failover is yours to run.
- **Notifications need a provider you configure.** Responders, reporters and admins are notified on assignment, field verification, clearance proposals, block/reopen/reject and new high/critical reports; password resets are delivered the same way. Messages go through a database-backed outbox (queued in the same transaction as the change, retried with exponential backoff, de-duplicated). Email needs `SMTP_HOST`; SMS needs `NOTIFY_WEBHOOK_URL` pointing at a relay to your SMS gateway (signed with `NOTIFY_WEBHOOK_SECRET`). Without either, messages are only logged. Admins can inspect and retry deliveries at `/api/v1/notifications`. Verified against a local SMTP server and webhook in tests, not against a real carrier.
- **Modelled network.** Routing and the ripple engine run on a small graph of six neighbourhoods with synthetic trips; reports outside that area are rejected. It is not a city-wide routing product.
- **Crowd reports are weighted, not trusted.** An unverified report only adds a routing *penalty* (never a closure; only an admin closes a road). That penalty is scaled by the reporter's reputation (incidents a responder later confirmed vs. ones the control room rejected; withdrawn reports are neutral; new accounts start at 0.5; staff are 1.0), by corroboration from independent reporters (capped at 0.9, below a verified hazard), and by whether a stored photo is attached. Triage by an admin raises it to at least 0.7, a responder's field verification to full strength (see `reputation_service.py`). Photos go through `POST /api/v1/uploads`: JPEG/PNG only (decided from the file's bytes), structurally validated, EXIF/GPS and text metadata stripped, 5 MB cap, rate limited, served `nosniff` with a sandboxing CSP, unattached files purged after 24 h. **Not done:** images are not analysed (a photo means "a file was attached", not "this shows a flood"), no virus scanning or moderation, and reputation is per account, so a patient attacker with several aged accounts can still skew it. Photos live in `UPLOAD_DIR` (default: next to the database, on the same volume), are served by unguessable id without a login (an `<img>` tag cannot send a token), and are not covered by the database backup unless you back up that folder too.
- **Routing geometry depends on an OSRM server.** `docker compose` runs one (self-hosted, Bengaluru only). Outside compose the default `OSRM_BASE_URL` is the public demo server, which has no SLA and a fair-use policy. The map is cropped to a bounding box (`OSRM_BBOX`) with the low-memory `simple` strategy, so roads that cross the box edge are cut there and routes near the border or outside it will not work. Responses are cached for 10 min, calls time out after 4 s, and after 3 consecutive failures a circuit breaker skips the network for 60 s and the API serves graph geometry instead (tested). TLS to the routing server is verified outside `DEMO_MODE`. The cache and breaker are per process. OSRM itself has no live traffic; that comes from TomTom (above), whose ETA scales OSRM's free-flow duration - it does not change which roads OSRM picks. Not verified against a live TomTom account in this repository's tests (they use recorded-shape responses).
- **Sessions.** Tokens are HMAC-signed with an expiry and a per-account version: `POST /auth/logout` and a password change/reset revoke every outstanding token, and 5 wrong passwords lock that account's login for 15 min (shared across workers, in addition to the per-IP limit). The SPA keeps the token in `localStorage`, which an XSS bug could read; the strict CSP (no inline/remote scripts) is the mitigation, and moving to an HttpOnly cookie would need CSRF protection - not done.
- **Behind a proxy**, set `FORWARDED_ALLOW_IPS` to the proxy address, or per-IP limits see only the proxy. Terminate TLS at the proxy; HSTS is sent on https responses.
- **Backups.** `python -m backend.scripts.backup create [dir]` takes a consistent online snapshot of the database plus the uploads folder (safe while running); `restore <archive>` (stop the app first) and `prune` are in the same script. Schedule it (cron) and copy archives off the host. The database carries a schema version and refuses to start if it is newer than the build.
- **No metrics/alerting yet.** There are structured logs with request ids and a `/health` endpoint, but no Prometheus metrics or error tracker; add one before a real launch.
- The Orchestrate agent definition and chat path are **not verified against a live instance** (see `orchestrate/README.md`).

---

## 8. Authentic IBM Bob Story

Throughout the implementation of MaleMitra, **IBM Bob** was used to scaffold typed contracts, implement routing logic, debug failing regression tests, and evaluate network impact:

1. **Typed Scaffolding**: IBM Bob generated the complete Pydantic v2 schema contract ([`backend/app/models/schemas.py`](backend/app/models/schemas.py:1)) and the 8-state incident machine (`reported` $\rightarrow$ `under_review` $\rightarrow$ `assigned` $\rightarrow$ `field_verified` $\rightarrow$ `blocked` $\rightarrow$ `clearance_proposed` $\rightarrow$ `cleared`).
2. **Graph-Based Ripple Engine Implementation**: Bob authored the pure-Python Dijkstra and Bureau of Public Roads (BPR) delay curves in [`backend/app/services/ripple_service.py`](backend/app/services/ripple_service.py:1) to ensure deterministic execution without bulky external GIS overhead.
3. **Test-Driven Debugging**: When initial acceptance tests failed due to asynchronous Starlette testclient table initialization, Bob applied surgical diffs to [`backend/app/models/database.py`](backend/app/models/database.py:1), resolving the acceptance-test failures at the time.
4. **Reproducible Benchmark Generation**: Bob generated the evaluation harness ([`backend/eval_benchmark.py`](backend/eval_benchmark.py:1)) providing empirical proof of the 100% reduction in blocked segment traversal.

---
*Made with IBM Bob for Bobathon 2026*
