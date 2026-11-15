# 12 · Repository, Open Source and Licensing

**Repository:** https://github.com/sakshit-allumolu/MaleMitra · **Submission branch:** `feature-demo` (HEAD `cdafc7d` at audit time) · **Tracked files on that branch:** 104.
**Licensing status: UNRESOLVED — action needed before submission.** The repository has **no `LICENSE` file**, while the hackathon terms say submissions are governed by the MIT Open Source Licence. See §6.

## 1. Repository overview

MaleMitra (ಮಳೆ ಮಿತ್ರ) is a **modular monolith**: one FastAPI service (`backend/`) that also serves the built React single-page app (`frontend/`). Optional watsonx Orchestrate agent assets live in `orchestrate/`. Deployment assets: `Dockerfile`, `docker-compose.yml`, `render.yaml`, `scripts/deploy_code_engine.sh`, `.github/workflows/ci.yml`.

## 2. Directory structure (tracked files only)

```
MaleMitra/
├── README.md                      project README (see accuracy notes in §9)
├── DEMO.md                        presenter script and checklist
├── .env.example                   variable names with empty/placeholder values
├── Dockerfile, docker-compose.yml, render.yaml
├── .github/workflows/ci.yml       backend (ruff+pytest, SQLite+PostgreSQL), frontend build, docker build
├── scripts/deploy_code_engine.sh  IBM Code Engine deployment
├── orchestrate/                   watsonx Orchestrate integration
│   ├── malemitra_incident_agent.yaml      agent definition (ReAct, 8 tools, 9 rules)
│   ├── malemitra_tools_openapi.json       tool spec exported from the API
│   └── README.md
├── backend/
│   ├── requirements.txt, requirements-dev.txt
│   ├── eval_benchmark.py          benchmark CLI
│   ├── app/
│   │   ├── main.py, config.py, shared.py, security.py, ratelimit.py, timeutil.py
│   │   ├── api/        11 routers: auth, incidents, routes, simulations, teams, events, health,
│   │   │               agents, agent_tools, notifications, uploads
│   │   ├── services/   13 modules: incident, graph, ripple, agent (rule-based), agent_tools,
│   │   │               orchestrate_client, recommendation, reputation, eval, live_traffic,
│   │   │               tomtom_routing, notification, upload
│   │   ├── models/     database.py (DDL, 14 tables + schema_info), schemas.py (Pydantic)
│   │   └── data/       bengaluru_graph.json (20 nodes/56 edges), synthetic_trips.json (150 trips),
│   │                   benchmark_results.json/.csv
│   ├── scripts/        backup.py, migrate_sqlite_to_postgres.py, reset_demo.py
│   └── tests/          17 test files, 242 tests
└── frontend/
    ├── package.json, package-lock.json, vite.config.ts, tsconfig*.json, index.html
    └── src/  App.tsx, main.tsx, views/ (Citizen, Admin, Responder, Evaluation),
              components/ (InteractiveMap, RippleVisualizer, OrchestratePanel, AgentTimeline,
              AuditLogViewer, AgentRecommendationCard, LoginPage, DemoWalkthroughModal,
              OnboardingTour, …), context/ (Auth, Incident), services/api.ts, types/
```

Not tracked (git-ignored): `.env`, `.venv`/`venv*`, `node_modules`, `frontend/dist`, `backend/app/data/*.db`, uploads, `.vscode/`, `.bob/`, `*.log`.

## 3. Important source files (where to look first)

| Judge's question | File |
|---|---|
| How is the incident workflow enforced? | `backend/app/services/incident_service.py` |
| How are risk-aware routes computed? | `backend/app/services/graph_service.py`, `agent_service.py::compare_routes` |
| What is the Ripple Engine? | `backend/app/services/ripple_service.py`, `eval_service.py`, `backend/eval_benchmark.py` |
| How is crowd trust computed? | `backend/app/services/reputation_service.py` |
| Where does watsonx Orchestrate connect? | `orchestrate_client.py`, `api/agent_tools.py`, `agent_tools_service.py`, `recommendation_service.py`, `api/agents.py`, `orchestrate/*` |
| Where are security controls? | `backend/app/security.py`, `api/auth.py`, `ratelimit.py`, `main.py` (headers/CSP), `upload_service.py` |
| What do the screens look like in code? | `frontend/src/views/*.tsx`, `frontend/src/components/InteractiveMap.tsx` |
| What is tested? | `backend/tests/` |

## 4. Development workflow (as evidenced)

| Item | Finding |
|---|---|
| Branches on `origin` | `main`, `feat-2`, `feature-branch`, `feat-prod`, `feat-deploy`, `feature-demo` |
| `main` | 6 commits, 10–13 Nov 2026 — an earlier prototype whose history is **unrelated** to `feature-demo` (no merge base) |
| `feature-demo`, `feat-prod`, `feat-deploy` | 32 / 26 / 14 commits, all dated 15 Nov 2026 (15:15–23:36 IST) |
| Commit authors (all branches, 50 commits) | Sai Sri Sakshit Allumolu — 48 (45 with a personal address, **3 with an `@target.com` address**) · `venu019` — 2 |
| CI | GitHub Actions: backend job (ruff + pytest on SQLite and PostgreSQL), frontend job (`npm ci`, `npm run build`), docker job. **Lint step currently fails** (`F821`, see [08](08_TESTING_AND_VALIDATION.md)). Whether a CI run has actually executed on GitHub is [TEAM INPUT REQUIRED] |
| IBM Bob provenance | 7 git notes in `refs/notes/bob` (95 recorded edit operations on 6 files, 15 Nov 22:38–23:36 IST) exist **only locally**; none are on GitHub. Details and the user's statement about earlier Bob use: [04 Part A](04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md), [PROJECT_AUDIT §7, §10](PROJECT_AUDIT.md) |

Contribution process: there is no `CONTRIBUTING.md`; pull requests are not documented. For the hackathon the team's workflow is branch-per-stage commits to GitHub.

## 5. Dependencies and licences

Licences below were read from the installed package metadata (`importlib.metadata`) and from `frontend/package-lock.json` / each package's `package.json` on 15 Nov 2026. They are **self-reported package metadata, not a legal opinion.**

### 5.1 Backend (runtime — `backend/requirements.txt`)

| Package | Version | Licence |
|---|---|---|
| fastapi | 0.128.8 | MIT |
| starlette | 0.49.3 | BSD-3-Clause |
| uvicorn | 0.39.0 | BSD-3-Clause |
| pydantic / pydantic_core | 2.13.5 / 2.46.5 | MIT |
| httpx (→ httpcore, h11, anyio, idna, certifi) | 0.28.1 | BSD-3-Clause (httpx, httpcore, idna), MIT (h11, anyio), **MPL-2.0 (certifi)** |
| python-dotenv | 1.2.1 | BSD-3-Clause |
| **psycopg, psycopg-binary, psycopg-pool** | 3.3.9 / 3.3.9 / 3.3.3 | **LGPL-3.0-only** |
| click, annotated-types, typing-extensions, typing-inspection, annotated-doc | various | BSD-3-Clause / MIT / PSF-2.0 |

Development only (`requirements-dev.txt`): pytest 8.4.2 (MIT), ruff 0.17.5 (MIT), pluggy, iniconfig, packaging (Apache-2.0 OR BSD-2-Clause), Pygments (BSD-2-Clause).

### 5.2 Frontend (runtime — from `package-lock.json`)

| Package | Version | Licence |
|---|---|---|
| react, react-dom | 19.3.1 | MIT |
| leaflet | 1.9.4 | BSD-2-Clause |
| lucide-react | 1.70.0 | ISC |
| scheduler, csstype, @types/react | — | MIT |

Build tooling (dev): vite 6.4.5 (MIT), typescript 5.9.3 (Apache-2.0), `@vitejs/plugin-react` (MIT; not re-checked). **Tailwind is not a dependency** (the README mentions it by mistake).

### 5.3 Third-party services and data

| Item | Terms to respect |
|---|---|
| OpenStreetMap map tiles and data | ODbL data licence + attribution. The map shows "© OpenStreetMap contributors" (`InteractiveMap.tsx:225`). The public tile server and public OSRM/Nominatim servers have fair-use policies — fine for a demo, not for production traffic |
| Nominatim search | OSM usage policy (browser calls with a limited result count) |
| OSRM routing | public demo server (no SLA); self-hosted option in Compose; routing data from an OSM extract (`download.openstreetmap.fr`) |
| TomTom Flow/Routing APIs | Terms of the team's TomTom account; free tier ≈ 2,500 req/day; **do not redistribute the key** |
| unpkg | Leaflet CSS loaded with an SRI hash |
| IBM watsonx Orchestrate, IBM Cloud IAM | IBM account terms; hackathon-provided access [TEAM INPUT REQUIRED: confirm the instance is the hackathon-provided one] |
| `bengaluru_graph.json` (20 nodes/56 edges) and `synthetic_trips.json` (150 trips) | Created for the project; **how the graph coordinates/road names were derived is not documented.** If they came from OSM, ODbL attribution applies [TEAM INPUT REQUIRED] |

No copied third-party source files or vendored libraries were found in the tracked tree (listing of `backend/` and `frontend/src`).

## 6. Licence analysis (MIT requirement) — for your decision

**What the hackathon says (official page, fetched 15–16 Nov 2026):** rule 9.1 — IP in a submission remains with the team; 9.2 — participants grant IBM/TechGig a non-exclusive, royalty-free licence to review/evaluate/display/promote; 9.3 — participants must **disclose all material open-source components**; 6.6 — must credit contributors and comply with third-party licences; 6.2 — source code must be available "free of charge and without technical restrictions"; and the page states *"All submitted solutions will be governed by the applicable intellectual property and licensing terms, including the MIT Open Source License, as specified in the … Terms & Conditions."* The T&C document itself was not separately retrievable; its precise MIT wording must be read by the team [TEAM INPUT REQUIRED].

**Findings**
1. **No `LICENSE` file exists.** Without one, a public GitHub repository is "all rights reserved" by default, which is in tension with rule 6.2 and the MIT statement.
2. **Copyright holders:** at least two authors appear in history (Sai Sri Sakshit Allumolu and `venu019`). An MIT file needs a copyright line naming the holder(s); **all contributors should agree** [TEAM INPUT REQUIRED].
3. **Employer address:** three commits use an `@target.com` email. If any of that code was written under an employment agreement or on employer equipment/time, the employer might hold rights; rule 2.4 puts the duty to obtain approval on the participant. **Not assumed either way** — see Q19 in [`INFORMATION_REQUIRED_FROM_TEAM.md`](INFORMATION_REQUIRED_FROM_TEAM.md).
4. **LGPL-3.0 dependency (psycopg).** It is *used as a separately installed Python package* (not copied into the repo) and only imported when `DATABASE_URL` is set. Distributing an MIT-licensed application that depends on an LGPL library is commonly done, and the Docker image installs the library as an unmodified wheel; the LGPL asks that users can replace the library and that its licence text/notice accompany distribution. This is **not legal advice**; list it in the disclosure (rule 9.3) and have someone with licensing knowledge confirm. If in doubt, the app works without PostgreSQL (SQLite).
5. **MPL-2.0 (certifi)** is file-level copyleft on certifi's own files; unmodified use is fine; mention it in attributions.
6. All other runtime dependencies are MIT/BSD/ISC/PSF — compatible with an MIT-licensed project.
7. **IBM assets:** the agent YAML targets IBM's platform; no IBM source code is copied into the repo (none found).
8. **Generated content:** code produced with IBM Bob is part of the submission; rule 8.6 allows AI tools provided no personal/confidential data is submitted to them [TEAM INPUT REQUIRED: confirm none was].

**Recommended steps (not performed — the existing licence situation was deliberately not changed):**
1. Confirm ownership and agreement of all contributors (and the employer position, Q19).
2. Add a standard MIT `LICENSE` file at the repo root with the agreed copyright line, e.g. `Copyright (c) 2026 <names of the copyright holders>`; the template text is at https://opensource.org/license/mit.
3. Add a short `THIRD_PARTY_NOTICES.md` generated from §5 (plus the OSM attribution).
4. Mention the LGPL note above in the README.
5. Make the submission branch the one judges see (default branch or an explicit link).

## 7. Repository access requirements

| Requirement | Status |
|---|---|
| Source available free of charge, without technical restrictions (rule 6.2) | Remote `origin` is on GitHub; **whether the repository is public is not verified** — no unauthenticated fetch was attempted. [TEAM INPUT REQUIRED: confirm Public, or add the judges as collaborators; open `https://github.com/sakshit-allumolu/MaleMitra` in a private window to verify] |
| Default branch | `main` is the old prototype; judges cloning the default will not get this code [TEAM INPUT REQUIRED: choose] |
| No secrets in the repo | Verified by scanning the working tree and 50 revisions for the four secret values in the local `.env` |
| Reproducible build | Backend path verified in a fresh virtualenv; see [06](06_SETUP_AND_INSTALLATION.md) |
| Large/binary assets | none tracked beyond JSON data |
| Judges can run without IBM access | Yes — the AI layer is optional ([06 §5](06_SETUP_AND_INSTALLATION.md)); the hosted instance `https://malemitra.onrender.com` is an alternative |

## 8. Attribution and credits (rule 6.6)

| Contributor | Evidence | Credit |
|---|---|---|
| Sai Sri Sakshit Allumolu | 48 commits (git author) | repository owner |
| `venu019` (`venu30062004@gmail.com`) | 2 commits (`1e2fca1`, `95535a2` on `main`/`feat-2`) | **must be credited** — real name and team membership [TEAM INPUT REQUIRED] |
| Any other helper (mentors, design, data) | unknown | [TEAM INPUT REQUIRED] |
| IBM Bob | development assistant (see doc 04) | state as a tool, not a contributor of record |
| Open-source libraries | §5 | listed above |
| OpenStreetMap contributors | map/routing data | on-screen attribution present |

## 9. Documentation accuracy notes about the repository itself

The repository's own `README.md` and CI file contain statements that do not match the repository (full list in [11 §1](11_LIMITATIONS_AND_ROADMAP.md)): "130+ tests" (actual 242), `backend/e2e_smoke.py` referenced but missing, Tailwind mentioned but not installed, and conflicting Orchestrate "verified/unverified" notes. They were **not edited** by this documentation work.
