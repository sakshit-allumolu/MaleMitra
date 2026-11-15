# 06 · Setup and Installation Guide

Written for a judge or developer who has never seen the repository. Every command below was derived from the repository files (`README.md`, `Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml`, `backend/requirements*.txt`, `frontend/package.json`) and the backend part of §3 was executed on macOS (Apple Silicon) on 15 Nov 2026 in a brand-new Python 3.12 virtual environment (`pip install -r backend/requirements-dev.txt`, then `uvicorn` → `/api/v1/health` = healthy, `/` = 200, `/docs` = 200). The frontend build (`npm run build`) passed on the existing install, but a clean `npm ci` was **not** repeated. The Docker path in §2 follows the repository's own compose file and was **not** run during this audit.

**Repository:** `https://github.com/sakshit-allumolu/MaleMitra` — the working branch for this submission is **`feature-demo`** (the default branch `main` holds an earlier, unrelated prototype history; see [12](12_REPOSITORY_AND_LICENSE.md)). [TEAM INPUT REQUIRED: confirm which branch judges should clone — Q-list in [`INFORMATION_REQUIRED_FROM_TEAM.md`](INFORMATION_REQUIRED_FROM_TEAM.md).]

> The fastest ways to see the product without installing anything: the hosted instance `https://malemitra.onrender.com` (returned HTTP 200 on `/api/v1/health` on 15 Nov 2026; the free plan sleeps when idle, so the first request can take 30–60 s) and the screenshots in `submission/assets/screenshots/`.

## 1. Prerequisites

| Need | Version | Why | Verified with |
|---|---|---|---|
| Git | any recent | clone | — |
| Python | **3.11 or 3.12** (CI uses 3.11, Docker image uses 3.11-slim; audited on 3.12.16) | backend | 3.12.16 |
| Node.js + npm | **22** (CI and Dockerfile use 22) | frontend build | v22.22.1 |
| Docker + Compose v2 | optional | one-command run with PostgreSQL + OSRM | Docker 29.5.3 present; compose path not re-run |
| Chrome/Firefox/Edge | current | the SPA, Leaflet map | Chrome |
| IBM Cloud account with watsonx Orchestrate | **only** for the AI agent layer | optional; the app runs without it | team's own instance |

Not required: any paid API key. TomTom, OSRM-hosted, SMTP and Orchestrate are optional and the app degrades gracefully (see [03 §14](03_TECHNICAL_ARCHITECTURE.md)). The default Python is `python3`; on macOS system Python 3.9 is too old — use `python3.11` or `python3.12`.

## 2. Option A — Docker (demo, with PostgreSQL and self-hosted OSRM)

```bash
git clone https://github.com/sakshit-allumolu/MaleMitra.git
cd MaleMitra
git checkout feature-demo
cp .env.example .env            # optional; compose has safe demo defaults
docker compose up --build       # http://localhost:8000
```

`docker compose` starts the app, **PostgreSQL 16** and a **self-hosted OSRM**; on first start `osrm-download` fetches the Karnataka OpenStreetMap extract and crops it to Bengaluru (a few minutes; reused afterwards). Open `http://localhost:8000`. If the OSRM download is a problem, run `OSRM_ENABLED=false docker compose up --build` — the app falls back to graph geometry.

Reset the demo data to a known state: `docker compose exec malemitra python -m backend.scripts.reset_demo`.

## 3. Option B — From scratch without Docker (SQLite)

### 3.1 Backend

```bash
git clone https://github.com/sakshit-allumolu/MaleMitra.git
cd MaleMitra
git checkout feature-demo

python3.12 -m venv .venv                    # python3.11 also works
source .venv/bin/activate                   # Windows: .venv\Scripts\activate
pip install -r backend/requirements-dev.txt # includes runtime requirements + pytest + ruff
cp .env.example .env
```

Edit `.env` only if you need to; for a local demo the defaults work (`DEMO_MODE=true`, SQLite at `backend/app/data/malemitra.db`). Then:

```bash
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

- Health: `curl http://127.0.0.1:8000/api/v1/health` → `{"status":"healthy", … "nodes_count":20,"edges_count":56}`
- Interactive API docs: `http://127.0.0.1:8000/docs`
- Tables are created and demo data seeded automatically at start-up (`init_db`, `seed_demo_incidents`). **Only when `DEMO_MODE=true`.**

Run it from the **repository root** (module path `backend.app.main`). The database file is created under `backend/app/data/` and is git-ignored.

### 3.2 Frontend

Two ways:

**(i) Production build served by the backend (simplest, one port).**

```bash
cd frontend
npm ci
npm run build          # runs tsc then vite build -> frontend/dist
cd ..
# restart/start uvicorn from the repo root; the app now serves the SPA at http://127.0.0.1:8000/
```

The build prints a 500 kB chunk-size warning (586 kB); it is a warning only.

**(ii) Vite dev server with hot reload (second terminal).**

```bash
cd frontend
npm ci
npm run dev            # http://localhost:5173, proxies /api -> http://127.0.0.1:8000
```

### 3.3 Demo accounts (`DEMO_MODE=true` only)

| Role | Email | Password |
|---|---|---|
| Citizen | `citizen@malemitra.in` | `demo123` |
| Admin / control room | `admin@malemitra.in` | `demo123` |
| Responder (Team Alpha) | `responder1@malemitra.in` | `demo123` |
| Responder (Team Beta) | `responder2@malemitra.in` | `demo123` |

`demo123` is a **public, intentionally weak demo password**. The login page also has one-click buttons (*Citizen (Pooja)*, *Control Room Admin*, *Inspector Ramesh*). With `DEMO_MODE=false` these accounts do not exist (see §6).

### 3.4 Suggested 5-minute walkthrough

1. Sign in as **Citizen** → *Find Routes* between two Koramangala/Indiranagar points → compare routes.
2. Click the map → submit a hazard report.
3. Sign out → sign in as **Admin** → review → assign a team.
4. Sign in as **Responder** → claim → verify (impassable) → sign out.
5. Admin → **Authorise Block** → open *Ripple* and *Benchmark* views; open *Agent Decision Timeline* and *System Audit Trail*.
6. Admin → *watsonx Orchestrate Agent* tab (see §5).

`DEMO.md` in the repository root has the team's own presenter script and checklist.

## 4. Configuration reference

The repository already contains **[`.env.example`](../.env.example)** with variable names and **placeholders only** (no secrets). Real environment variables override `.env`. The table lists everything the app reads that matters for a first run; the full list is in `backend/app/config.py`.

| Variable | Default | Meaning |
|---|---|---|
| `DEMO_MODE` | `true` | `true` seeds demo users/incidents; `false` = production rules (see §6) |
| `DATABASE_PATH` | `backend/app/data/malemitra.db` | SQLite file (also locates the `uploads` folder) |
| `DATABASE_URL` | empty | `postgresql://…` → use PostgreSQL instead of SQLite |
| `WEB_CONCURRENCY` | `2` (Docker) | worker processes; state is shared through the DB |
| `JWT_SECRET` | demo value | **must** be set (≥ 32 chars) when `DEMO_MODE=false` |
| `CORS_ORIGINS` | empty | comma-separated allowed origins |
| `RATE_LIMIT_*`, `LOGIN_MAX_FAILURES`, `LOGIN_LOCKOUT_SECONDS` | see `.env.example` | abuse limits |
| `MAX_UPLOAD_BYTES` | `5242880` | photo cap |
| `OSRM_ENABLED`, `OSRM_BASE_URL` | `true`, public demo server | road geometry; failures fall back to graph |
| `TOMTOM_API_KEY` | empty | enables live traffic/ETAs (optional) |
| `SMTP_*`, `NOTIFY_WEBHOOK_URL`, `NOTIFY_LOG_ONLY` | empty/false | notifications (optional) |
| `AGENT_TOOL_API_KEY` | empty | shared secret the Orchestrate agent sends in `X-API-Key`; tools return 401 until set |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | URL Orchestrate calls for tools |
| `ORCHESTRATE_API_KEY`, `ORCHESTRATE_INSTANCE_URL`, `ORCHESTRATE_AGENT_ID` | empty | connect the Orchestrate agent |

Variables read by the code but **not listed in `.env.example`**: `ORCHESTRATE_CHAT_PATH`, `ORCHESTRATE_IAM_URL`, `ORCHESTRATE_TIMEOUT_SECONDS`, `ROUTE_AREA_BBOX`, `DUPLICATE_RADIUS_M`, `SESSION_TTL_SECONDS`, `ALLOW_LEGACY_TOKENS`, `ADMIN_SIGNUP_CODE`, `SHARED_SYNC_ENABLED`, `MAX_SSE_CLIENTS`, `HSTS_ENABLED`, `OSRM_VERIFY_TLS`, `OSRM_TIMEOUT_SECONDS`, `OSRM_BREAKER_*`. (Documentation gap only; defaults work.)

**Secrets:** never commit `.env` (it is in `.gitignore`). Generate a secret with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.

## 5. IBM service configuration (watsonx Orchestrate) — optional for running, required for the AI feature

Everything here is from `orchestrate/README.md` and the code; it needs **your own** IBM Cloud account and Orchestrate instance. Without it the Admin panel shows *Not connected* and `POST /agents/chat` returns `503`; the rest of the product works.

1. Choose a tool secret and start the backend with a **publicly reachable** URL (Orchestrate's cloud cannot call `localhost`):
   ```bash
   export AGENT_TOOL_API_KEY="$(openssl rand -hex 24)"
   export PUBLIC_BASE_URL="https://<your-public-url>"     # ngrok / Cloudflare tunnel / Code Engine URL
   python -m uvicorn backend.app.main:app --port 8000
   ```
2. Get the tool spec: `curl "$PUBLIC_BASE_URL/api/v1/agent-tools/spec" > orchestrate/malemitra_tools_openapi.json` (the repo already has a copy).
3. In watsonx Orchestrate import `malemitra_tools_openapi.json` as tools (*Add tool → Import from OpenAPI*), authentication **API key**, header `X-API-Key`, value = `AGENT_TOOL_API_KEY`.
4. Create the agent from `orchestrate/malemitra_incident_agent.yaml` (or paste its instructions into the agent builder) and attach the eight tools. Note the agent id.
5. Put the connection settings in `.env` (placeholders shown):
   ```
   ORCHESTRATE_API_KEY=<your IBM Cloud API key>
   ORCHESTRATE_INSTANCE_URL=https://<your-orchestrate-instance-url>
   ORCHESTRATE_AGENT_ID=<agent id>
   ```
6. Restart the backend. Sign in as admin → *watsonx Orchestrate Agent* tab shows **Connected**; incidents get an **Ask agent** button.

Verification without an LLM (works offline): the 37 tests in `backend/tests/test_orchestrate_agent.py` (see §7). **Known operational fragility:** if you use a temporary tunnel the URL changes each time — update `PUBLIC_BASE_URL` and re-import the spec.

## 6. Production-style run (optional)

`DEMO_MODE=false` makes the app refuse to start unless `JWT_SECRET` ≥ 32 chars is set, legacy tokens are off and `CORS_ORIGINS` has no `*`:

```bash
export DEMO_MODE=false
export JWT_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
export CORS_ORIGINS=https://malemitra.example.org
export BOOTSTRAP_ADMIN_EMAIL=ops@example.org
export BOOTSTRAP_ADMIN_PASSWORD='<choose a strong password>'
docker compose up -d --build
```

No demo users or seeded incidents exist in this mode; the first admin is created from `BOOTSTRAP_ADMIN_*`.

Other deployment assets: `render.yaml` (Render Blueprint), `scripts/deploy_code_engine.sh` (IBM Code Engine). PostgreSQL migration and backups: `python -m backend.scripts.migrate_sqlite_to_postgres --help`, `python -m backend.scripts.backup create`.

## 7. Running the tests

```bash
source .venv/bin/activate
python -m pytest backend/tests -q                        # SQLite; ~19 s; 242 tests
TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/malemitra_test python -m pytest backend/tests -q   # PostgreSQL
ruff check backend --select E9,F                          # CI lint
python backend/eval_benchmark.py                          # benchmark CLI
cd frontend && npm run build                              # type-check + production build
```

Expected on 15 Nov 2026 (`cdafc7d`): **242 passed**, 1 deprecation warning. `ruff` reports **1 error** (`F821 Undefined name 'Set'`, `backend/app/services/agent_service.py:206`) which fails the CI lint step; this is recorded in [08](08_TESTING_AND_VALIDATION.md) and not fixed by the documentation work. There are no frontend tests.

> **Side effect to know about:** running the benchmark CLI **overwrites the tracked files** `backend/app/data/benchmark_results.json` and `.csv`. Restore them with `git checkout -- backend/app/data/benchmark_results.json backend/app/data/benchmark_results.csv` if you do not want a dirty working tree. The test suite uses a throwaway database.

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: backend` | uvicorn started inside `backend/` | run from the repo root: `python -m uvicorn backend.app.main:app` |
| `pip` fails to build or `ModuleNotFoundError: psycopg` | very old Python / no wheel | use Python 3.11/3.12 on a 64-bit platform; psycopg binary wheels are in `requirements.txt` |
| Blank page at `http://localhost:8000/` | frontend not built | `cd frontend && npm ci && npm run build`, restart backend (the API and `/docs` still work) |
| Page shows old UI | stale process on port 8000 | `lsof -nP -iTCP:8000 -sTCP:LISTEN`, stop old process, hard refresh |
| Login fails with `429` | 5 failed attempts lock an email for 15 min | wait, or `python -m backend.scripts.reset_demo` (demo mode only) |
| Login says invalid credentials | `DEMO_MODE=false` | demo users only exist when `DEMO_MODE=true` |
| `RuntimeError: Refusing to start with DEMO_MODE=false…` | insecure production settings | set `JWT_SECRET`, `CORS_ORIGINS` as in §6 |
| Orchestrate panel "Not connected" / `503` on chat | missing `ORCHESTRATE_*` | fill the three variables (§5) |
| Agent calls fail with 401 | `AGENT_TOOL_API_KEY` unset or differs from the Orchestrate tool connection | set both to the same value |
| Agent cannot reach tools | `PUBLIC_BASE_URL` not public / tunnel changed | restart tunnel, update `PUBLIC_BASE_URL`, re-import the spec |
| Routes show "Graph fallback (OSRM unavailable)" | OSRM unreachable (offline, or compose OSRM still preparing) | expected fallback; start `docker compose up -d osrm` or set `OSRM_ENABLED=false` |
| Report rejected `422 … outside the Bengaluru area` | coordinates outside service bounding box | pick a point inside Bengaluru |
| Map tiles blank | no internet (OpenStreetMap tiles) | connect, or demo with screenshots |
| `tsc` errors during `npm run build` | wrong Node version | use Node 22 |
| Docker first start very slow | OSRM map download/prepare | wait for `osrm-prepare` to finish, or disable OSRM |
| `sqlite3.OperationalError: no such table` in a script | app never started (tables are created at start-up) | start the app once, or run via `with TestClient(app)` |

## 9. Quick verification checklist for judges

- [ ] `curl http://127.0.0.1:8000/api/v1/health` → HTTP 200, `"status":"healthy"`, 20 nodes, 56 edges
- [ ] Login as `citizen@malemitra.in` / `demo123` in the browser
- [ ] `python -m pytest backend/tests -q` → 242 passed
- [ ] `python backend/eval_benchmark.py` → baseline 38 of 150 trips cross the closed road, MaleMitra 0
- [ ] (needs IBM account) Admin → watsonx Orchestrate Agent → Connected
