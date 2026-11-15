# Screenshot Requirements

This file lists every screenshot the submission uses or still needs.

- **Captured** means the file exists in `submission/assets/screenshots/` and was taken from the running application during the audit on 15 Nov 2026.
- **To capture** means you need to take it. We do not create mock screenshots or fake IBM dashboards.

Rules for every capture:
1. Never show an API key, bearer token, `.env` contents or password field contents.
2. **Crop or blur the Cloudflare tunnel host** (the `PUBLIC_BASE_URL` value). The Orchestrate panel shows it. One earlier screenshot (SS05) was deleted for this reason.
3. Do not show personal email addresses. The demo accounts (`*@malemitra.in`) are fine.
4. Use a window of at least 1280×720, browser zoom 100 %.
5. Save as PNG, using the filenames below.

---

## 1. Captured screenshots

| ID | File | Page or workflow | What it shows | Used in | Caption note |
|---|---|---|---|---|---|
| SS01 | `SS01_login_page.png` | Login | Sign-in with one-click demo roles | Deck slide 7, [06](06_SETUP_AND_INSTALLATION.md) | |
| SS02 | `SS02_citizen_workspace.png` | Citizen workspace | Map, hazard reporting, route search | Deck slide 7, [05](05_FEATURES_AND_USER_FLOWS.md) | |
| SS03 | `SS03_admin_control_room.png` | Admin → Road Map & Overlay | Triage queue and map | Deck slide 7, [02](02_PROBLEM_STATEMENT_AND_SOLUTION.md) | |
| SS04 | `SS04_admin_agent_timeline.png` | Admin → Agent Decision Timeline | Agent actions tagged `rule-based` or `LLM agent` | Deck slide 9, [02](02_PROBLEM_STATEMENT_AND_SOLUTION.md) | Rows visible are **rule-based**. LLM rows need ORCH-5. |
| SS06 | `SS06_admin_audit_log.png` | Admin → System Audit Trail | Append-only audit rows | Deck slide 7, [02](02_PROBLEM_STATEMENT_AND_SOLUTION.md), [09](09_SECURITY_PRIVACY_AND_RESPONSIBLE_AI.md) | |
| SS07 | `SS07_ripple_engine.png` | Ripple view after a closure | Trips re-routed and load shift on the graph | Deck slides 7 and 12, [10](10_IMPACT_AND_SCALABILITY.md) | Synthetic trips, not field data. |
| SS08 | `SS08_benchmark_view.png` | Benchmark view | In-app benchmark page | Optional | **Caption with the CLI figures only** (38 → 0, +14.2 s, +3.9 %). The in-app time figures differ because they use live graph state. |
| SS09 | `SS09_responder_field_tasks.png` | Responder → My tasks | Field task screen | Deck slide 7, [05](05_FEATURES_AND_USER_FLOWS.md) | Empty-state capture. Retake with a populated queue if you can. |
| SS11 | `SS11_citizen_route_compare.png` | Citizen → Find Routes | Direct vs risk-aware vs alternative route cards | Deck slides 6 and 7, [02](02_PROBLEM_STATEMENT_AND_SOLUTION.md) | Caption: "Graph fallback (OSRM unavailable)". |

SS05 and SS10 do not exist. They were captured and deliberately deleted (SS05 exposed the tunnel URL).

---

## 2. IBM watsonx Orchestrate evidence — **critical, to capture**

You told us the end-to-end run works. We could not re-run the tool-callback loop because the tunnel was unreachable, so these screenshots are the proof judges will look for.

| ID | Suggested filename | Page or workflow | What it must demonstrate | Used in |
|---|---|---|---|---|
| ORCH-1 | `ORCH1_console_agent.png` | Orchestrate console → agent `malemitra_incident_agent` | Agent name, model and instructions. Confirms the real model (Q20). | Deck slide 10, [04 §B.9](04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md) |
| ORCH-2 | `ORCH2_console_tools.png` | Orchestrate console → tools | The 8 tools imported from the OpenAPI spec | Deck slide 10, [04](04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md) |
| ORCH-3 | `ORCH3_panel_connected.png` | MaleMitra → Admin → *watsonx Orchestrate Agent* | **Connected** status and tool-call counts above 0. Crop the tunnel URL. | Deck slide 10, video segment 7 |
| ORCH-4 | `ORCH4_ask_agent_result.png` | Incident card → **Ask agent**, or panel → **Ask the agent** | The agent's reply and the stored recommendation card | Deck slides 9 and 10, video segment 7 |
| ORCH-5 | `ORCH5_timeline_llm_rows.png` | Admin → Agent Decision Timeline | Rows tagged **LLM agent** with `tool:*` actions | Deck slide 9, video segment 7 |
| ORCH-6 | `ORCH6_approve_and_audit.png` | Recommendation card → **Approve & dispatch team** (or **Approve & close road**) | Human approval, resulting status change and audit row | Deck slide 9, video segment 7 |
| ORCH-7 | `ORCH7_run_trace.png` | Orchestrate run trace (optional) | Thread or run id proving a live run | Optional |

Capture order that works: ORCH-1 → ORCH-2 → ORCH-3 → create a fresh `reported` incident → ORCH-4 → ORCH-5 → ORCH-6.

## 3. IBM Bob evidence — **critical, to capture**

| ID | Suggested filename | What it must demonstrate | Used in |
|---|---|---|---|
| BOB-1 | `BOB1_initial_prompt.png` | Bob task showing the first scaffolding prompt, with a date | Deck slide 4, [04 §A.4](04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md) |
| BOB-2 | `BOB2_fix_failing_test.png` | Bob fixing a failing test, before and after | Deck slide 4 |
| BOB-3 | `BOB3_apply_diff.png` | Bob applying a diff to a real file such as `agent_service.py` | Deck slide 4, video segment 6 |
| BOB-4 | `BOB4_history_earlier_system.png` | Bob task history from the **earlier system** with dates | Deck slide 5, [`INFORMATION_REQUIRED_FROM_TEAM.md`](INFORMATION_REQUIRED_FROM_TEAM.md) Q3 |
| BOB-5 | `BOB5_git_notes.png` | Terminal: `git notes --ref=bob list \| wc -l` (expected 7 in this clone) | Deck slide 5, video segment 6 |

## 4. Other captures that would strengthen the submission

| ID | Suggested filename | What it shows | Used in |
|---|---|---|---|
| EXT-1 | `EXT1_render_hosted_app.png` | The hosted instance (`malemitra.onrender.com`) working in a browser | [06 §9](06_SETUP_AND_INSTALLATION.md), deck slide 13 |
| EXT-2 | `EXT2_pytest_242_passed.png` | Terminal with `pytest backend/tests` ending in `242 passed` | [08](08_TESTING_AND_VALIDATION.md), deck slide 13 |
| EXT-3 | `EXT3_benchmark_cli.png` | Terminal: `python backend/eval_benchmark.py` output with 38 → 0 | [10](10_IMPACT_AND_SCALABILITY.md), deck slide 12 |
| EXT-4 | `EXT4_ci_green.png` | GitHub Actions green run (only after the lint fix is approved and applied) | Checklist, deck slide 13 |
| EXT-5 | `EXT5_populated_responder.png` | Responder queue with real tasks, to replace SS09 | Deck slide 7 |
| EXT-6 | `EXT6_recommendation_card.png` | Recommendation card with confidence and approve / dismiss buttons | [05](05_FEATURES_AND_USER_FLOWS.md) |

---

## 5. Manual capture checklist

- [ ] Start the app with a clean demo database (see [06](06_SETUP_AND_INSTALLATION.md)).
- [ ] Confirm Orchestrate shows **Connected** and the tool URL answers.
- [ ] Run one incident through the whole loop as citizen → admin → responder → admin.
- [ ] Capture ORCH-1…7 in the order given above, then BOB-1…5.
- [ ] Capture EXT-1…6.
- [ ] Crop or blur the tunnel host in every Orchestrate panel capture.
- [ ] Check each file for tokens, keys, personal emails and password fields.
- [ ] Save PNGs into `submission/assets/screenshots/` with the filenames above.
- [ ] Insert them into the marked placeholder boxes in `submission/IBM_Bobathon_Presentation.pptx`.
- [ ] If you ran the benchmark or tests, restore tracked files:
  `git checkout -- backend/app/data/benchmark_results.json backend/app/data/benchmark_results.csv`
- [ ] Tick the matching items in [14](14_FINAL_SUBMISSION_CHECKLIST.md).
