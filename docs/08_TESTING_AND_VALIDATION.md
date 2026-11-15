# 08 · Testing and Validation

**Run date:** 15 Nov 2026 · **Commit:** `cdafc7d` (branch `feature-demo`) · **Environment:** macOS (Apple Silicon), Python 3.12.16 virtual environment, Node 22.22.1, SQLite, no network services other than the live IBM calls named below.
Status vocabulary: **PASS** = executed during this audit and succeeded · **FAIL** = executed and failed · **NOT RUN** = exists but not executed here · **NOT TESTED** = no test exists · **USER-STATED** = reported by the team, not reproduced.

## 1. Summary

| Check | Result |
|---|---|
| `python -m pytest backend/tests -q` | **242 passed**, 1 warning (anyio deprecation inside Starlette's test client), 19.07 s (re-run twice; earlier run 18.6 s) |
| Same suite on PostgreSQL (`TEST_DATABASE_URL`) | **NOT RUN** — no PostgreSQL instance was started. CI is configured to run SQLite and PostgreSQL; [TEAM INPUT REQUIRED: link a green CI run if one exists] |
| `ruff check backend --select E9,F` (the CI lint command) | **FAIL — 1 error:** `F821 Undefined name 'Set'` at `backend/app/services/agent_service.py:206` (`locs: Set[Tuple[float, float]] = set()`). The CI `backend` job would fail at this step. Left unfixed because the audit does not modify application code; a one-line import fix is suggested in [11](11_LIMITATIONS_AND_ROADMAP.md) for the team to approve |
| `npm run build` (`tsc && vite build`) | **PASS**; one chunk-size warning (586 kB > 500 kB) |
| Frontend unit / component / e2e tests | **NOT TESTED** — none exist |
| `backend/e2e_smoke.py` | **Does not exist.** README and CI reference it ("59 checks"); the CI command excludes it from lint but it is absent from the repository |
| Benchmark CLI (`python backend/eval_benchmark.py`) ×3 | **PASS** and deterministic: 38 of 150 trips cross the closed road in the baseline → 0 with MaleMitra; mean 366.7 s → 381.0 s (+14.2 s, +3.9 %) |
| Live HTTP smoke on a throwaway database | 20 checks: 17 passed; the 3 failures were wrong test payloads written by the auditor (not product defects) and the corrected re-run passed 6/6; a second scripted pass (§4) all behaved as designed |
| Orchestrate: live IAM token exchange and live chat round-trip | **PASS** on 15 Nov 2026 (reply "OK"; thread/run/trace ids returned). Secret values were never printed |
| Orchestrate: full tool-callback loop through the public tool URL | **NOT RE-RUN** — the team's public tunnel was unreachable during the audit. **USER-STATED:** works end-to-end. Evidence screenshots pending (ORCH-1…7) |
| Secret scan | The four secret values in the local `.env` were searched for in the working tree and in 50 revisions of git history: **not found**. `.env` is git-ignored |
| Deployed instance | `https://malemitra.onrender.com/api/v1/health` → HTTP 200 on 15 Nov 2026 |

**Side effect found:** running the test suite or the benchmark rewrites the tracked files `backend/app/data/benchmark_results.json/.csv`. They were restored with `git checkout` each time; the working tree for application files is unchanged.

## 2. Testing strategy (as implemented in the repository)

| Layer | What exists | Where |
|---|---|---|
| Unit | Graph maths (Haversine, point-to-segment, Dijkstra, k-shortest paths), BPR function, reputation formula, token signing, phone/password helpers, upload sanitiser | `test_graph_routing`, `test_ripple_engine`, `test_crowd_trust`, `test_session_tokens`, `test_production_readiness` |
| Integration (API + DB via Starlette `TestClient` on a throwaway DB) | Workflow, role gates, merging, assignment, notifications, backup, reset, auto-ripple, TomTom routing, multi-worker | the other files |
| Acceptance | "T01…T15" scenarios incl. a full end-to-end journey | `test_acceptance.py` (9 tests; numbering is non-contiguous: T03, T07, T10, T12–T14 are absent) |
| API / security | 401/403 role checks, lock-out, revocation, security headers, rate limits, upload validation | `test_hardening`, `test_production_readiness`, `test_acceptance` |
| AI-agent behaviour | Tool auth, bounds, workflow gates, logging of rejected calls, approve/dismiss, stale recommendations, OpenAPI spec = only tools, IAM client with a mocked transport | `test_orchestrate_agent.py` (37) |
| Multi-process | Real separate server processes sharing the DB | `test_multi_worker.py` (6) |
| Frontend | **None** (type-check via `tsc` during build only) | — |
| Load / performance | **None** (DEMO.md says "not load-tested"); only the 4–5 ms benchmark runtime | — |
| Accessibility | **None**; two `aria-` attributes exist in `frontend/src` | — |
| LLM quality / evaluation | **None.** The Orchestrate agent's reasoning quality has not been measured; tests use a mocked client | — |

Test counts per file (collected and run): acceptance 9 · admin_workflow 7 · backup 4 · crowd_trust 33 · graph_routing 5 · hardening 11 · live_traffic_and_auto_ripple 11 · multi_worker 6 · notifications 20 · orchestrate_agent 37 · production_readiness 38 · report_merging 10 · reset_demo 2 · responder_assignment 19 · ripple_engine 3 · session_tokens 5 · tomtom_routing 22 = **242**.

> **Limitation to state to judges:** the TomTom and SMTP/SMS tests use recorded-shape or local stand-ins; the Orchestrate client tests use a mocked HTTP transport. They prove the code handles those shapes, not that every third-party service behaves that way today.

## 3. Test-case table — automated suite

All rows below are **PASS** because the whole suite ran green on 15 Nov 2026; the name is the real pytest function. Rows are a representative selection mapped to features, not all 242.

| ID | Feature | Scenario (pytest function) | Input | Expected | Actual | Status |
|---|---|---|---|---|---|---|
| A-01 | Reporting | `test_acceptance::test_t01_citizen_report_in_bounded_region` | Report inside the region | Incident created and mapped to an edge | As expected | PASS |
| A-02 | Reporting | `test_t02_ambiguous_location_flagged` | Point midway between two roads (12.9295, 77.6280) | Report accepted as `reported`, **not blocked**, `confidence ≤ 0.85` (the test does not assert the `is_ambiguous` field) | As expected | PASS |
| A-03 | Trust | `test_t04_unverified_report_does_not_close_road` | Unverified report at Domlur | Mapped edge is not blocked | As expected | PASS |
| A-04 | Workflow | `test_t05_responder_verifies_and_admin_approves_blockage` | Verify then admin block | Edge blocked, graph version bumps | As expected | PASS |
| A-05 | Routing | `test_t06_blocked_edge_excluded_from_recomputed_routes` | Closure then route compare | Blocked edge absent | As expected | PASS |
| A-06 | Workflow | `test_t08_responder_propose_clearance_and_admin_reopening` | Clearance then reopen | Road reopened | As expected | PASS |
| A-07 | AuthZ | `test_t09_citizen_forbidden_from_admin_endpoints` | Citizen calls admin API | 403 | As expected | PASS |
| A-08 | Ripple | `test_t11_ripple_run_deterministic_reproducibility` | Same seed twice | Identical result | As expected | PASS |
| A-09 | End-to-end | `test_t15_full_e2e_journey` | Report → … → reopen | Whole loop succeeds | As expected | PASS |
| A-10 | Workflow gates | `test_admin_workflow::test_cannot_close_road_without_field_verification` | Block an unverified incident | 409 | As expected | PASS |
| A-11 | Workflow gates | `test_cannot_reopen_before_clearance_is_proposed` | Reopen early | 409 | As expected | PASS |
| A-12 | Workflow gates | `test_cannot_dispatch_before_triage_review` | Assign before review | 409 | As expected | PASS |
| A-13 | Merging | `test_report_merging::test_nearby_report_is_counted_on_the_older_incident` | Two reports ≤ 10 m | One incident, count 2 | As expected | PASS |
| A-14 | Merging | `test_same_citizen_reporting_twice_is_not_double_counted` | Same user twice | Count unchanged | As expected | PASS |
| A-15 | Trust | `test_reporter_cannot_inflate_severity_alone` | A second reporter claims `critical` on a `low` incident | Severity stays `low` | As expected | PASS |
| A-16 | Crowd trust | `test_crowd_trust.py` (33 tests) | Reputation, corroboration, photo, cap 0.9 | Per formula | As expected | PASS |
| A-17 | Assignment | `test_responder_assignment.py` (19 tests) | Team queue, named responder, atomic claim | Rules respected | As expected | PASS |
| A-18 | Sessions | `test_session_tokens::test_tampered_signature_and_swapped_user_are_rejected` | Tampered token | 401 | As expected | PASS |
| A-19 | Sessions | `test_hardening::test_logout_revokes_all_sessions` | Logout then reuse token | 401 | As expected | PASS |
| A-20 | Lock-out | `test_account_lockout_after_repeated_failures` | 5 wrong passwords | 429 | As expected | PASS |
| A-21 | Headers | `test_security_headers_present` | `GET /health` | CSP contains `default-src 'self'` and `frame-ancestors 'none'`; `permissions-policy` present; HSTS only over https when enabled | As expected | PASS |
| A-22 | Resilience | `test_osrm_circuit_breaker_stops_hitting_network`, `test_compare_routes_falls_back_when_osrm_down` | OSRM failing | Breaker opens, graph fallback | As expected | PASS |
| A-23 | Password reset | `test_production_readiness::test_reset_token_is_hidden_outside_demo_mode_and_stored_hashed` | `DEMO_MODE=false` | No token in response; stored hashed | As expected | PASS |
| A-24 | Agent tools | `test_orchestrate_agent::test_tools_closed_when_no_key_configured` | No key set | 401 | As expected | PASS |
| A-25 | Agent tools | `test_tools_reject_missing_and_wrong_key` | Bad key | 401 | As expected | PASS |
| A-26 | Agent guard-rails | `test_recommendation_respects_workflow_gates_and_never_changes_state` | Invalid action for status | 422 gate; status unchanged | As expected | PASS |
| A-27 | Agent guard-rails | `test_what_if_does_not_change_live_state_and_is_bounded` | 1 edge, then 6 edges, empty list, unknown edge | 1 edge → 200 with edge still unblocked and graph version unchanged; the other three → 422 | As expected | PASS |
| A-28 | Agent audit | `test_every_tool_call_is_logged_including_rejections` | Accepted + rejected calls | Rows in `agent_events` | As expected | PASS |
| A-29 | Human approval | `test_approve_runs_the_workflow_action_and_records_decision`, `test_dismiss_changes_nothing_but_the_record`, `test_stale_recommendation_cannot_be_approved_but_can_be_dismissed` | Approve / dismiss / stale | Gated action only on approve | As expected | PASS |
| A-30 | Agent roles | `test_chat_and_analyze_are_admin_only`, `test_only_admins_can_decide_and_input_is_validated` | Non-admin calls | 403 | As expected | PASS |
| A-31 | Orchestrate client | `test_client_exchanges_token_caches_it_and_parses_reply`, `test_client_surfaces_iam_and_upstream_failures` | Mocked IAM + chat | Token cached; errors surfaced | As expected | PASS |
| A-32 | Spec | `test_openapi_spec_contains_only_agent_tools`, `test_tool_summaries_equal_operation_ids_…` | Export spec | Only the 8 tools; names match | As expected | PASS |
| A-33 | Notifications | `test_notifications.py` (20) | Outbox, retry, back-off, signing | Per design | As expected | PASS |
| A-34 | Multi-worker | `test_multi_worker.py` (6) | Separate processes | Shared closures/ripple visible | As expected | PASS |
| A-35 | TomTom | `test_tomtom_routing.py` (22) | Recorded-shape responses, budgets, breaker | Per design | As expected | PASS (mocked) |
| A-36 | Ops | `test_backup.py` (4), `test_reset_demo.py` (2) | Backup/restore; reset refuses outside demo | Per design | As expected | PASS |
| A-37 | Benchmark | `test_ripple_engine::test_evaluation_benchmark_harness` | Run harness on `edge-7`,`edge-8`, seed 42 | 150 trips; baseline crossings > 0; MaleMitra crossings = 0; reduction = 100 %; detour trade-off > 0 | As expected | PASS |

## 4. Test-case table — manual API smoke executed by the auditor

Run against a throwaway database (`DEMO_MODE=true`, offline) through the FastAPI `TestClient` with the application lifespan active; no production data was touched.

| ID | Feature | Scenario | Input | Expected | Actual | Status |
|---|---|---|---|---|---|---|
| M-01 | Health | Readiness | `GET /health` | 200 healthy | 200, 20 nodes / 56 edges | PASS |
| M-02 | Auth | Valid login | citizen demo creds | 200 + token | 200 | PASS |
| M-03 | Auth | Wrong password | bad password | 401 | 401 "Invalid email or password." | PASS |
| M-04 | Auth | Missing field | no password | 422 | 422 "Field required" | PASS |
| M-05 | AuthN | No token | `GET /incidents` | 401 | 401 "Not authenticated. Please log in." | PASS |
| M-06 | AuthZ | Citizen reads audit | `GET /events/audit` | 403 | 403 | PASS |
| M-07 | AuthZ | Citizen reviews incident | `POST …/review` | 403 | 403 | PASS |
| M-08 | AuthZ | Responder edits other team | `POST /teams/team-beta/status` as Alpha | 403 | 403 "Responders can only update their own team." | PASS |
| M-09 | Reporting | Valid report | Domlur point | 200 + edge mapping | 200, `edge-33`, 7 m, confidence 0.85 | PASS |
| M-10 | Validation | Delhi coordinates | lat 28.6 / lon 77.2 | 422 | 422 | PASS |
| M-11 | Validation | Weak password on register | `weak` | 422 | 422 "at least 8 characters" | PASS |
| M-12 | Workflow | Full path | review → assign → claim → verify → block | each 200 | each 200; status `blocked` | PASS |
| M-13 | Workflow gate | Block before verification | `authorize_block` on `assigned` | 409 | 409 "A responder must field-verify it first." | PASS |
| M-14 | Workflow gate | Withdraw a blocked incident | `…/withdraw` | 409 | 409 | PASS |
| M-15 | Routing | Compare routes | Koramangala → Indiranagar | fastest + risk-aware | 200; 1148 s/risk 0.18 vs 1316 s/risk 0.08 (`time_of_day_model`) | PASS |
| M-16 | Ripple | Simulation after closure | seed 42 | 150 trips | 150 trips, 25 affected | PASS |
| M-17 | Benchmark | Admin benchmark | `GET /simulations/benchmark/run` | result object | 38 → 0 crossings; time metrics differ from the CLI (live graph state) | PASS (caveat) |
| M-18 | Upload | Non-image body | `notanimage` | 415 | 415 "only JPEG and PNG images are accepted." | PASS |
| M-19 | Upload | Valid JPEG/PNG with EXIF | — | EXIF/GPS stripped | **NOT RUN manually** (covered by unit tests only) | NOT RUN |
| M-20 | Agent tools | Correct key | `map_to_edge` | 200 | 200 | PASS |
| M-21 | Agent tools | No key | same | 401 | 401 "Invalid or missing X-API-Key." | PASS |
| M-22 | Agent tools | Wrong-state action | `propose_block` on a `reported` incident | 422 `workflow_gate` | 422 `workflow_gate` | PASS |
| M-23 | Agent tools | Valid recommendation | `request_triage` on `reported` | accepted; status unchanged | accepted; status unchanged | PASS |
| M-24 | Human approval | Admin approves it | decision `approve` | incident → `under_review`, audit row | as expected (earlier run) | PASS |
| M-25 | Agent | Chat when unconfigured | `POST /agents/chat` as admin | 503 | 503 "watsonx Orchestrate is not configured (missing: …)" | PASS |
| M-26 | Agent | Chat as citizen | — | 403 | 403 | PASS |
| M-27 | Agent | Unknown recommendation id | `…/decision` | 404 | 404 | PASS |
| M-28 | Notifications | Status | `GET /notifications/status` | counts | `{"channels":{"email":false,"sms":false,"log":true},"counts":{"pending":7,"sent":1}}` | PASS |
| M-29 | Account | Admin creates responder | `POST /auth/users` | 200 | 200 | PASS |
| M-30 | Phone | Normalisation | `98765 43210` | `+919876543210` | `+919876543210` | PASS |
| M-31 | Reset | Unknown email | `forgot-password` | generic reply | generic reply, `debug_token: null` | PASS |

## 5. Live IBM verification (15 Nov 2026)

| ID | Check | Result | Status |
|---|---|---|---|
| L-01 | All five Orchestrate/tool settings present in `.env` (names only inspected) | all SET | PASS |
| L-02 | IBM IAM API-key → bearer-token exchange | succeeded | PASS |
| L-03 | `POST` to the team's agent chat endpoint (`ap-south-1` host) with a one-word prompt | HTTP success, reply "OK", `thread_id`, `run_id`, `trace_id` present | PASS |
| L-04 | Public tool URL (`PUBLIC_BASE_URL`, temporary tunnel) reachable from the internet | **Unreachable** at audit time | FAIL (environmental) |
| L-05 | Full ReAct loop: agent → tools → `submit_recommendation` → timeline → approval | Not re-run | **USER-STATED works** |
| L-06 | Historic evidence | Dev database holds 531 `watsonx_orchestrate` rows dated 14 Nov 2026 (62 `run_ripple_what_if`, 53 `get_incident_context`, 109 `submit_recommendation`, 144 stored recommendations). A minority are generic/short and may come from scripted tests, so the table is supporting but not conclusive evidence | Supporting |

## 6. Performance and scale (limited)

| Measurement | Result | Caveat |
|---|---|---|
| Benchmark engine runtime | ≈ 4–5 ms for 150 trips on a 56-edge graph | tiny graph |
| Test suite | 242 tests in ≈ 19 s | |
| Load / concurrency | **NOT TESTED** | Multi-worker consistency is tested, throughput is not |

## 7. Untested or unverified areas (be explicit with judges)

1. **PostgreSQL** path (suite not run here).
2. **Docker Compose** stack (not started).
3. **Frontend** behaviour beyond type-check/build — no automated UI tests; manual screenshots only.
4. **Accessibility** and screen-reader behaviour; mobile layouts.
5. **LLM quality** of the Orchestrate agent (no evaluation set, no accuracy figure exists).
6. **TomTom live** requests and **real SMTP/SMS carriers**.
7. **Photo upload happy path through the browser** (unit-tested only).
8. **Load testing**, **penetration testing**, **dependency vulnerability scan** (`pip-audit`/`npm audit` not run).
9. **User acceptance testing**: **none performed**, and no user feedback exists. [TEAM INPUT REQUIRED: if any pilot or peer feedback exists, add it with source and date.]

## 8. How to reproduce

```bash
python -m pytest backend/tests -q
ruff check backend --select E9,F
python backend/eval_benchmark.py
cd frontend && npm ci && npm run build
git checkout -- backend/app/data/benchmark_results.json backend/app/data/benchmark_results.csv   # undo test side effects
```
