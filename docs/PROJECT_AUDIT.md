# MaleMitra – Project Audit

**Audit date:** 15 Nov 2026 · **Audited commit:** `cdafc7d` (branch `feature-demo`) · **Auditor:** IBM Bob (automated repository inspection)

Legend used throughout the documentation set:

| Tag | Meaning |
|---|---|
| **[VERIFIED]** | Observed directly in code, or by running a command/test during this audit. |
| **[USER-STATED]** | Told to the auditor by the team; not provable from the repository. Needs evidence before submission. |
| **[ASSUMPTION]** | Reasonable inference, not confirmed. |
| **[TEAM INPUT REQUIRED]** | Missing information. Tracked in [`INFORMATION_REQUIRED_FROM_TEAM.md`](INFORMATION_REQUIRED_FROM_TEAM.md). |

---

## 1. Identity

| Item | Value |
|---|---|
| Project name | **MaleMitra (ಮಳೆ ಮಿತ್ರ – "Rain Friend")** [VERIFIED: `README.md`, `backend/app/config.py`] |
| One-line description | A connected monsoon mobility and civic-response platform: a citizen flood report becomes a verified road closure, and every commuter's route re-plans around it. |
| Repository | `https://github.com/sakshit-allumolu/MaleMitra` [VERIFIED: `git remote -v`] |
| Version | 1.0.0 |
| Branch audited | `feature-demo` (HEAD `cdafc7d`) |

## 2. Problem, users, use cases

- **Problem [VERIFIED from README/code intent]:** During heavy Bengaluru monsoon rain, information on waterlogged roads is fragmented. Citizen reports, control-room review and field verification are disconnected, so commuters can be routed into submerged underpasses and response dispatch is uncoordinated.
- **Target users [VERIFIED: 3 roles in code]:** Citizens/commuters; municipal control-room administrators (modelled on BBMP); field responders (Teams Alpha/Beta).
- **Primary use cases [VERIFIED]:** (1) geotagged hazard report with optional photo; (2) risk-aware route comparison; (3) triage → dispatch → field verification → admin-authorised closure → clearance → reopening; (4) "what if this road closes?" ripple simulation; (5) AI-assisted incident analysis by a watsonx Orchestrate agent with human approval.

## 3. Hackathon track

**Selected track: "Smarter Streets, Better Living"** — the official track text lists "Traffic congestion and commute planning" and "neighbourhood flood alerts" as potential solutions, which this project directly addresses. The UI footer and README already state this track. No stretch is required. Student category: **[TEAM INPUT REQUIRED]** (eligibility unknown).

## 4. Feature inventory

### 4.1 Implemented and verified

| # | Feature | Evidence |
|---|---|---|
| F1 | Role-based auth (citizen / admin / responder), scrypt-hashed passwords, signed expiring sessions, logout revocation, login lockout | `api/auth.py`, `security.py`; tests `test_session_tokens.py`, `test_hardening.py`; smoke test |
| F2 | Geotagged incident reporting (5 hazard types, 4 severities), service-area bounds validation, rate limits | `api/incidents.py`, `schemas.py`; smoke test (Delhi coords → 422) |
| F3 | Photo upload (JPEG/PNG by magic bytes, EXIF/GPS stripped, 5 MB cap, 24 h purge of unattached) | `services/upload_service.py` |
| F4 | Report merging: reports within 10 m of an open incident are counted on it instead of duplicating | `test_report_merging.py` |
| F5 | Crowd-trust weighting: reporter reputation × corroboration × photo × triage floor; unverified reports never close a road | `services/reputation_service.py`, `test_crowd_trust.py` (33 tests) |
| F6 | Spatial snap of report to road edge (Haversine, ambiguity flag) with rule-based confidence | `incident_service.py`, `graph_service.py` |
| F7 | 8-state incident workflow with role gates and audit trail | `incident_service.py`; `test_acceptance.py`, `test_admin_workflow.py` |
| F8 | Responder assignment: team queue / named responder, availability, atomic claim | `test_responder_assignment.py` |
| F9 | Road closure authorised **only** by admin; closures persisted and restored at startup; graph version counter | `incident_service.admin_authorize_restriction`, `restore_graph_state` |
| F10 | Risk-aware routing (Dijkstra/Yen, hazard + BPR congestion costs) and "Direct vs risk-aware vs alternative" comparison | `graph_service.py`, `agent_service.compare_routes`; smoke test; screenshot SS11 |
| F11 | Ripple Engine: 150 seeded synthetic trips re-routed on closure, BPR delay, per-edge Δtrips | `ripple_service.py`; `test_ripple_engine.py`; screenshot SS07 |
| F12 | Reproducible benchmark harness (CLI + admin endpoint) | `eval_benchmark.py`, `eval_service.py`; run 3×, deterministic |
| F13 | Optional live traffic: TomTom flow polling and routing ETAs, budgets, cache, circuit breaker | `live_traffic_service.py`, `tomtom_routing_service.py`; tests use recorded-shape responses only |
| F14 | Optional OSRM road geometry with circuit breaker and graph fallback | `agent_service.py` (fallback visible in SS11) |
| F15 | Notification outbox (email via SMTP, SMS via signed webhook), retry/backoff | `notification_service.py`; `test_notifications.py` (20) |
| F16 | Multi-worker consistency through DB epoch/leases; SQLite or PostgreSQL | `shared.py`; `test_multi_worker.py` |
| F17 | Live updates via Server-Sent Events | `api/events.py`, `IncidentContext.tsx` |
| F18 | **watsonx Orchestrate agent integration** — 8 REST tools, agent chat client, recommendations with human approve/dismiss | `agent_tools.py`, `agent_tools_service.py`, `orchestrate_client.py`, `recommendation_service.py`, `orchestrate/`; 37 tests; smoke test; live connectivity check (see §8) |
| F19 | Agent Decision Timeline and Audit Trail (admin) | `AgentTimeline.tsx`, `AuditLogViewer.tsx`; SS04 |
| F20 | Voice narration and turn-by-turn directions (browser `speechSynthesis`) | `CitizenWorkspace.tsx` |
| F21 | Guided demo (Demo Guide, onboarding tour), one-click demo logins | `DemoWalkthroughModal.tsx`, `OnboardingTour.tsx`, `LoginPage.tsx` |
| F22 | Backups, SQLite→PostgreSQL migration, demo reset scripts | `backend/scripts/` |
| F23 | Deployment assets: Dockerfile (non-root), docker-compose (app + PostgreSQL + OSRM), Render blueprint, IBM Code Engine script, CI workflow | root files |

### 4.2 Partial, simulated or limited — do not over-claim

| Item | Reality [VERIFIED] |
|---|---|
| "AI" in incident intelligence / mobility / response-coordinator agents | **Rule-based Python**, not LLM. The Timeline tags them `rule-based` (SS04). Only the watsonx Orchestrate agent is an LLM. |
| Road network | A **hand-built 20-node / 56-edge graph** covering Koramangala, Indiranagar, Domlur, HSR, Ejipura (`bengaluru_graph.json`). City-wide routing relies on OSRM geometry and a ~city bounding box, not on the graph. |
| Trips in ripple/benchmark | **150 synthetic** trips (seed 42). No real mobility data. |
| Benchmark impact figures | Simulation on the 20-node model; not field data (README says so). |
| Photos | Counted as "a file was attached"; **not analysed** by any model. |
| SMS/email delivery | Verified only against a local SMTP server and test webhook, not a real carrier. |
| TomTom live traffic | Code and tests exist; tests use recorded-shape responses. Live key present in local `.env` [VERIFIED set], not exercised in this audit. |
| Load / performance | **Not load-tested** (DEMO.md says so). |
| Responder workspace | "Simulated Emergency Responder" — accounts are demo accounts; no real municipal integration. |
| `WatsonxSkillCatalog.tsx` | Exists only on `origin/main` (earlier prototype). Not present on `feature-demo`; replaced by `OrchestratePanel.tsx`. |

### 4.3 Not implemented

Mobile app; Kannada UI; push notifications; image analysis; Prometheus metrics/alerting; HttpOnly-cookie sessions; real BBMP/BTP data feeds; rainfall-forecast ingestion; accessibility audit (only 2 `aria-` usages found in `frontend/src`).

## 5. Technology stack [VERIFIED]

| Layer | Technology |
|---|---|
| Frontend | React 19.3, TypeScript 5.9, Vite 6.4, Leaflet 1.9, lucide-react. **Inline styles** — the README's mention of Tailwind is not supported by `package.json` (no Tailwind dependency). |
| Backend | Python (CI 3.11; audited on 3.12), FastAPI 0.128.8, Starlette 0.49.3, Pydantic 2.13.5, Uvicorn 0.39, httpx 0.28.1 |
| Storage | SQLite (WAL) by default; PostgreSQL 16 via `DATABASE_URL` (psycopg 3 + pool) |
| Routing/maps | Own Dijkstra/Yen on modelled graph; OSRM (self-hosted via compose, or public demo server); OpenStreetMap tiles; Nominatim search; TomTom (optional) |
| AI | IBM watsonx Orchestrate agent (`llm: watsonx/ibm/granite-3-8b-instruct` in the agent YAML) |
| Dev/ops | Docker, docker-compose, GitHub Actions CI, Render, IBM Code Engine |

## 6. Architecture summary

A **modular monolith**: one FastAPI process serves the REST API (`/api/v1`) and the built React SPA. In-memory road graph + engines per worker; shared state (closures, hazards, ripple result, rate limits, leases) in the database, synchronised through an epoch checked on each request. Full detail and diagrams: [`03_TECHNICAL_ARCHITECTURE.md`](03_TECHNICAL_ARCHITECTURE.md).

- **Backend layout:** `api/` (11 routers) · `services/` (13 modules) · `models/` (DB DDL + Pydantic schemas) · `data/` (graph, trips, benchmark output) · `scripts/`.
- **Frontend layout:** `views/` (Citizen, Admin, Responder, Evaluation) · `components/` (map, ripple, agent panel, timeline, tours) · `context/` (auth, incidents) · `services/api.ts`.
- **Tables (14 + `schema_info`):** users, password_reset_tokens, response_teams, incidents, incident_reports, incident_evidence, agent_events, notifications, rate_hits, shared_state, leases, uploads, audit_events, simulation_runs.
- **API surface:** 53 operations (list in [`07_API_DOCUMENTATION.md`](07_API_DOCUMENTATION.md)).

## 7. IBM Bob usage — evidence available

| Evidence | Finding |
|---|---|
| `refs/notes/bob` git notes | **[VERIFIED]** 7 notes covering 95 recorded edit operations (94 `apply_diff`, 1 `insert_content`) on `agent_service.py` (27), `InteractiveMap.tsx` (32), `ResponderWorkspace.tsx` (22), `DemoWalkthroughModal.tsx` (10), `incident_service.py` (3), `test_responder_assignment.py` (1). Attached to commits `a8eb4a9`…`cdafc7d` (15 Nov, 22:38–23:36 IST). Notes are **local only** — `git ls-remote origin 'refs/notes/*'` returned none, so GitHub has no Bob provenance unless pushed. |
| README §8 "Authentic IBM Bob Story" | Claims Bob generated the Pydantic schemas, state machine, ripple engine, benchmark harness, and fixed acceptance-test failures. **[USER-STATED / README-stated]** — no prompts, transcripts or notes in the repo corroborate these specific claims. |
| User statement | Bob was also used in earlier work "on a different system", and **all commits on `main` and every other branch were made with Bob**. **[USER-STATED]** — git metadata alone cannot show this; authors are the human accounts (see §10). |
| `.vscode/sessions/history`, `.vscode/notes` | Empty directories. |

Action: attach Bob task-history exports/screenshots for the earlier system (see [`INFORMATION_REQUIRED_FROM_TEAM.md`](INFORMATION_REQUIRED_FROM_TEAM.md) Q3–Q5).

## 8. IBM watsonx Orchestrate usage — evidence

| Check | Result |
|---|---|
| Code: tool REST layer (8 tools, API-key guarded, closed by default) | **[VERIFIED]** `agent_tools.py` |
| Code: Orchestrate client (IAM token exchange → chat) | **[VERIFIED]** `orchestrate_client.py` |
| Code: agent definition and OpenAPI tool spec | **[VERIFIED]** `orchestrate/malemitra_incident_agent.yaml`, `malemitra_tools_openapi.json` |
| Tests | **[VERIFIED RUN]** `test_orchestrate_agent.py` — 37 passed |
| Live IAM token exchange against the team's IBM account | **[VERIFIED RUN, 15 Nov 2026]** succeeded |
| Live chat call to the team's agent (`ap-south-1`) | **[VERIFIED RUN]** replied "OK"; response had `thread_id`, `run_id`, `trace_id` |
| Historic tool-call log in dev DB (`agent_events`) | **[VERIFIED]** 531 `watsonx_orchestrate` rows, all 14 Nov: 62 `run_ripple_what_if`, 53 `get_incident_context`, 109 `submit_recommendation`, 144 stored recommendations; 2 with long, evidence-citing rationales. Many rows are short/generic, so some may come from test scripts. |
| End-to-end run (Ask agent → tools called over public URL → recommendation stored) | **[USER-STATED: working]**. Not re-run in this audit because the public tunnel (`trycloudflare.com`) was unreachable. **Screenshot placeholders provided** in [`SCREENSHOT_REQUIREMENTS.md`](SCREENSHOT_REQUIREMENTS.md). |
| Local offline smoke (tools + guardrails + human approval) | **[VERIFIED RUN]** 6/6 — agent cannot change status; admin approval runs the workflow step |

**Documentation inconsistency to fix:** `DEMO.md:59` says the live Orchestrate connection "has not been verified"; `orchestrate/malemitra_incident_agent.yaml:3-8` still says the file is "UNVERIFIED"; `README.md:83` and `orchestrate/README.md:22` say verified. This audit treats it as verified (evidence above) but the stale lines should be edited by the team.

## 9. External integrations

| Service | Required? | Purpose |
|---|---|---|
| IBM watsonx Orchestrate (+ IBM IAM) | For AI layer; app runs without | Agent reasoning over tools |
| TomTom Flow/Routing | Optional | Live-traffic ETAs and congestion |
| OSRM | Optional (falls back) | Road geometry, turn-by-turn |
| OpenStreetMap tiles, Nominatim | Browser-side | Map and geocoding |
| unpkg (Leaflet CSS, SRI-pinned) | Browser-side | Styles |
| SMTP / SMS webhook | Optional | Notifications |
| Cloudflare tunnel / ngrok | Dev only | Expose tools to Orchestrate cloud |

## 10. Authorship and the Fresh Code Rule — **critical flag**

| Fact [VERIFIED] | Detail |
|---|---|
| Hackathon Period (official rules §1.1, fetched from TechGig 15 Nov 2026) | 5 Oct 2026 00:00 – **14 Nov 2026 23:59 IST** |
| `origin/main` history | 6 commits, **10–13 Nov 2026** (authors: Sai Sri Sakshit Allumolu ×4, `venu019` ×2). Contains the first prototype (graph, ripple engine, UI, watsonx *skill catalogue* UI). |
| `feature-demo`/`feat-prod`/`feat-deploy` | 32/26/14 commits, **all dated 15 Nov 2026 15:15–23:36 IST** — **after** the Period ended per the page fetched. |
| `feature-demo` root commit `a3ca2a6` | Unrelated history to `main` (no merge base). Its first commit already adds ~all of the backend, tests, Docker, CI and README in one commit. |
| Working-tree file mtimes | 9 files 13 Nov, 19 files 14 Nov, 60 files 15 Nov. |
| Other contributor | `venu019 <venu30062004@gmail.com>` — 2 commits on `main`/`feat-2`. Must be credited (rules §6.6) and counted as a team member (≤5). |
| Deadline | **[USER-STATED]** extended to **16 Nov 2026**. The TechGig page still shows 14 Nov for the Hackathon Period and a "Register by Nov 16" banner. Needs portal confirmation. |
| "Bob did it all, on another system" | **[USER-STATED]** |

**Assessment.** Under rule 7.1.2 all submitted code must be *written during* the Hackathon Period. Commit timestamps are consistent with the period only for work dated before 15 Nov; the large 15 Nov body of work is after the published end. If the extension to 16 Nov is real and the 15 Nov work was done within the extended window, it is compliant — but only the organiser's confirmation settles that. Git timestamps are author-controlled and are neither proof nor disproof. **The team must supply: (a) the organiser's written extension notice, and (b) Bob task history showing when the code was produced.** No timestamps or logs were altered or invented by this audit.

## 11. Testing status [VERIFIED RUN, 15 Nov 2026]

| Check | Result |
|---|---|
| `pytest backend/tests` (Python 3.12, SQLite) | **242 passed**, 1 deprecation warning, 18.6 s |
| Test count by collection | 242 across 17 files |
| PostgreSQL run of the suite | **Not run** (needs `TEST_DATABASE_URL`); CI config claims both |
| `ruff check backend --select E9,F` (CI lint) | **1 error**: `F821 Undefined name 'Set'` at `backend/app/services/agent_service.py:206` → CI lint step would fail. Not fixed (audit is read-only for app code). |
| `npm run build` (tsc + vite) | **Pass**; one >500 kB chunk-size warning (586 kB) |
| Benchmark CLI ×3 | Deterministic: 38→0 blocked-road crossings; mean 366.7 s → 381.0 s (+14.2 s, +3.9 %) |
| Live HTTP smoke on throwaway DB | 20 checks, 3 initially failed due to **my wrong payloads**, re-run corrected: all behaviours passed (see doc 08) |
| Frontend unit/e2e tests | **None exist** |
| `backend/e2e_smoke.py` | Referenced in README and CI, **file does not exist** in the repo |

## 12. Known limitations / technical risks

1. **Fresh Code / authorship evidence** (§10) — highest risk.
2. **Benchmark results depend on graph state:** the committed `benchmark_results.json` shows `malemitra_mean_trip_time_s` 1428.9 s (+289.6 %). A clean CLI run (`python backend/eval_benchmark.py`, three repeats) gives 381.0 s (+14.2 s, +3.9 %). The in-app Benchmark page on a fresh demo database showed 387.7 s (+20.9 s, +5.7 %), because the endpoint runs against live graph state (hazard penalties from seeded incidents). Other runs gave 1477 s and 1523 s. The "38 → 0 trips crossing the blocked road" result was identical in every run. **Quote only the CLI figures and state the conditions.**
3. Running the benchmark/smoke tests **overwrites tracked files** (`benchmark_results.json/.csv`). This audit restored them with `git checkout`.
4. Modelled graph is tiny; claims about "city-wide" refer to OSRM routing, not the risk model.
5. Demo defaults are insecure by design (`demo123`, public admin code `bbmp2026`, legacy bare-id tokens) — acceptable only with `DEMO_MODE=true`; `render.yaml` and Code Engine script close these.
6. `.env` is git-ignored; scanning 50 revisions and the working tree found **no leak** of its four secret values.
7. No LICENSE file; hackathon terms say submissions are governed by the MIT licence (see doc 12).
8. psycopg is LGPL-3.0 (dynamic dependency) — compatible with MIT distribution as a separately-installed library, but flag for review.
9. Orchestrate tool URL depends on a temporary tunnel; if it is down at judging time the AI layer cannot call back.
10. `README.md` mentions Tailwind and `backend/e2e_smoke.py`, neither of which exist.

## 13. Missing information

See [`INFORMATION_REQUIRED_FROM_TEAM.md`](INFORMATION_REQUIRED_FROM_TEAM.md).
