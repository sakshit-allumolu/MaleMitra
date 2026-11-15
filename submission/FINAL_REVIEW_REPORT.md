# Final Review Report

**Project:** MaleMitra (ಮಳೆ ಮಿತ್ರ) · **Event:** IBM Bobathon: Build for Bengaluru 2026 · **Track:** Smarter Streets, Better Living
**Audited commit:** `cdafc7d` on `feature-demo` · **Audit date:** 15–16 Nov 2026

## 0. The four required items

"Built with IBM Bob" is the core participation requirement. Full map: [`docs/00_PARTICIPATION_REQUIREMENTS.md`](../docs/00_PARTICIPATION_REQUIREMENTS.md).

| Required item | Status |
|---|---|
| 1. The problem (who, what must improve) | Done, sourced, no invented statistics |
| 2. The prototype (working, built with Bob, agentic AI where useful) | Done. 242 tests pass. Orchestrate full loop is team-stated, screenshots pending |
| 3. **The Bob story** (short demo of Bob used throughout development) | **Script and deck slides ready. Real examples and screenshots missing. Repo proves 95 edits from one evening only.** This is the weakest item and the core requirement |
| 4. One measurable outcome | Done: 38 → 0 trips on the closed road, +14.2 s (+3.9 %), simulation |
| Safety: privacy and human review | Designed in and documented. Two known gaps listed in section 6 |

## 1. Readiness assessment

**The package is complete as far as the repository can support. The submission itself is not ready to upload until the six critical items in section 5 are resolved by you.**

| Area | Assessment |
|---|---|
| Documentation (docs 01–15, audit, questions, screenshots list) | Complete. Placeholders remain where only you know the answer. |
| Deck (15 slides, Bob story on slides 4–5) and video support | Generated. Needs your evidence screenshots and team details. |
| Prototype | Working and tested on the backend (242 passed). Frontend builds. No frontend tests. |
| IBM Bob evidence and Bob story (core requirement) | **Weak in the repo** (95 local edit notes). Rest is your statement. Deck slides 4–5 and video segment 6 (1:15) are built around it and wait for your real examples. |
| IBM watsonx Orchestrate evidence | **Code, tests and live chat verified. End-to-end run is your statement, no screenshots yet.** |
| Compliance (dates, Fresh Code, licence, employer) | **Open. Needs your decisions.** |

We do not estimate a score. Scoring is the judges' decision. See [doc 13](../docs/13_JUDGING_CRITERIA_ALIGNMENT.md) for an evidence-by-criterion view.

## 2. Deliverables generated

| Deliverable | Location |
|---|---|
| Project audit | [`docs/PROJECT_AUDIT.md`](../docs/PROJECT_AUDIT.md) |
| Questions for the team (Q1–Q21) | [`docs/INFORMATION_REQUIRED_FROM_TEAM.md`](../docs/INFORMATION_REQUIRED_FROM_TEAM.md) |
| Documents 01–15 | [`docs/`](../docs/) |
| Screenshot requirements and capture checklist | [`docs/SCREENSHOT_REQUIREMENTS.md`](../docs/SCREENSHOT_REQUIREMENTS.md) |
| Submission folder: README, executive summary, checklist pointer | [`submission/`](.) |
| Pointer files for documents 01–13 | [`presentation_source/documents/`](presentation_source/documents/) |
| Video script pointer and recording checklist | [`demo/`](demo/) |
| Presentation deck (15 slides, speaker notes) | [`IBM_Bobathon_Presentation.pptx`](IBM_Bobathon_Presentation.pptx) |
| Deck source: builder script and Markdown | [`presentation_source/build_deck.py`](presentation_source/build_deck.py), [`SLIDES.md`](presentation_source/SLIDES.md) |
| 9 real screenshots | [`assets/screenshots/`](assets/screenshots/) |
| 6 diagram PNGs (from Mermaid) | [`assets/diagrams/`](assets/diagrams/) |
| Link checker | [`presentation_source/check_links.py`](presentation_source/check_links.py) |
| This report | you are here |

`.env.example` already exists in the repository root and was not changed.

## 3. Deliverables pending (yours to do)

| Item | Why it is pending |
|---|---|
| Demo video | You are recording it. Script and checklist are ready. |
| ORCH-1…7 screenshots | Need your live Orchestrate run. We could not re-run the tool loop (tunnel offline). |
| BOB-1…5 screenshots and task-history exports | Exist only on your machines. |
| Team name, members, contact, final URLs | Not in the repo (Q6, Q10, Q18). |
| `LICENSE` file | Needs contributor agreement (Q12). |
| Populated responder screenshot, hosted-app screenshot, test and benchmark terminal captures | Optional strengthening (EXT-1…6). |
| Commit of `docs/` and `submission/` | Nothing was committed or pushed. |
| Deck check in PowerPoint | No PowerPoint or LibreOffice renderer was available here. |

## 4. Verification and test execution results

All run on 15 Nov 2026 unless stated. Details: [doc 08](../docs/08_TESTING_AND_VALIDATION.md).

| Check | Result |
|---|---|
| `pytest backend/tests` (Python 3.12, SQLite) | **242 passed**, 1 warning, about 19 s. Run twice. |
| `ruff check backend --select E9,F` | **1 error**: `F821 Undefined name 'Set'` at `agent_service.py:206`. This fails the CI lint step. **Not fixed** (awaiting Q17). |
| `npm run build` | Passes, with a 586 kB chunk-size warning. |
| Fresh virtual environment (`pip install -r backend/requirements-dev.txt`, uvicorn) | Health = healthy (20 nodes, 56 edges). `/` = 200. `/docs` = 200. |
| Benchmark CLI, three runs | Identical: 38 of 150 trips cross the closed road, MaleMitra sends 0. Mean +14.2 s (+3.9 %). 0 stranded. |
| Hosted instance health | `https://malemitra.onrender.com/api/v1/health` returned 200. |
| Live Orchestrate | IAM token exchange OK. Live chat OK. **Tool-callback loop not re-run.** |
| **Not run** | PostgreSQL suite, Docker Compose, a clean `npm ci`, frontend tests (none exist), accessibility audit, load test, penetration test. |

**Documentation QA run on this package (16 Nov):**

| Check | Result |
|---|---|
| Relative Markdown links in `docs/` and `submission/` (37 files) | All resolve. The five links to this report were the only ones missing until it was written. |
| Heading anchors referenced across files | 0 broken |
| Mermaid diagrams in `docs/` (8 blocks) | All 8 render with `mmdc`, including doc 04 §B.6 and the doc 05 state diagram that were unvalidated before |
| Secret scan: the three secret-looking values in `.env` against `docs/` and `submission/` | 0 matches |
| Token patterns (`sk-…`, `Bearer …`) | 0 matches |
| Tunnel host | Only the generic name `trycloudflare.com` appears, in the audit. No tunnel URL anywhere. |
| PPTX file | OpenXML validation passed. Text-fit estimate found one overflow (slide 2 title), fixed. |
| Application files modified | **None.** `git status` shows only `docs/` and `submission/` as untracked. The benchmark result files were restored after each run. |

## 5. Critical compliance gaps

| # | Gap | What you must do |
|---|---|---|
| 1 | **Deadline and Fresh Code Rule (7.1.2).** TechGig shows the Hackathon Period ending 14 Nov 2026 23:59 IST. All 32 `feature-demo` commits are dated 15 Nov. `main` has 6 commits (10–13 Nov) with unrelated history. The extension to 16 Nov is your statement and the portal may not be accepting uploads. | Get written organiser confirmation. Prepare a statement of what was written when. Verify the portal now. (Q1, Q2) |
| 2 | **IBM Bob provenance.** 7 notes, 95 edits, local only, one evening. Earlier-machine use and "all commits on all branches" are your statements. Git authors are human accounts. | Capture BOB-1…5, export history. Optionally `git push origin refs/notes/bob`. (Q3, Q4, Q5) |
| 3 | **watsonx Orchestrate end-to-end proof.** No screenshot in the repo. Tunnel was unreachable at audit time. | Capture ORCH-1…7 and have the tool URL reachable while you record. (Q8, Q9, Q20) |
| 4 | **MIT licence.** No `LICENSE`, `NOTICE` or `CONTRIBUTING` file. psycopg is LGPL-3.0-only and certifi is MPL-2.0. Graph and trip data provenance is undocumented. | Contributors agree, then add `LICENSE`. Get a legal view. This report is not legal advice. (Q12, Q21) |
| 5 | **Employer approval and AI-tool data (rules 2.4, 8.6).** Three commits use an `@target.com` author email. | Confirm approval and that no personal or confidential data went to Bob or other AI tools. (Q19) |
| 6 | **Default branch.** `main` is the old prototype. A judge opening the repo sees the wrong code. Also confirm the repo is public (rule 6.2) and that contributor `venu019` is credited (rule 6.6). | Decide the submission branch, set visibility, credit contributors. (Q6, Q11, Q13) |

## 6. Documentation quality issues

| # | Issue | Handling |
|---|---|---|
| 1 | The repo's own `README.md`, `DEMO.md`, the agent YAML and CI file contain stale claims: "130+ tests" (actual 242), `e2e_smoke.py` (missing but referenced), Tailwind (not installed), and conflicting Orchestrate "verified/unverified" lines. | Documented in [doc 11 KI-5, KI-6](../docs/11_LIMITATIONS_AND_ROADMAP.md). **Not edited**, awaiting Q17. A judge who reads the README first will see these. |
| 2 | **Three different benchmark time figures exist** (CLI +3.9 %, in-app +5.7 % to +10.5 %, committed JSON +289.6 %). | All our documents quote the CLI only and say why. Do not quote the others. |
| 3 | The Wikipedia-sourced facts (rainfall, built-up land, lakes) were read from Wikipedia, not from primary sources. The India Today article was **not opened**. | Flagged in doc 01 and the checklist. Verify before quoting from the stage. |
| 4 | Known privacy gap: `evidence_list` exposes other citizens' names and ids to signed-in citizens through the API. | Documented ([doc 09 §4.1](../docs/09_SECURITY_PRIVACY_AND_RESPONSIBLE_AI.md), KI-4). Unfixed. |
| 5 | The responder screenshot (SS09) is an empty state. The timeline screenshot (SS04) shows rule-based rows only. | Captioned. Retake with real data (EXT-5, ORCH-5). |
| 6 | The Orchestrate model name (`granite-3-8b-instruct`) comes from the YAML and is not confirmed in the running instance. | Marked as configured, not confirmed (Q20). |
| 7 | The deck was not opened in PowerPoint. Layout was checked by script only. | Open and check each slide, especially the amber placeholder boxes. |
| 8 | `docs/SCREENSHOT_REQUIREMENTS.md` was referenced from several documents before it existed. | Now exists. Links verified. |

## 7. Consistency and accuracy checks

- **Numbers match across the package:** 242 tests, 53 API operations, 14 tables, 20 nodes / 56 edges, 150 trips, 38 → 0, +14.2 s / +3.9 %, 95 Bob edits in 7 notes, 8 Orchestrate tools, 37 Orchestrate tests.
- **Agent description is the same everywhere:** one LLM agent, recommend-only, human approval, no agent-to-agent coordination. The three other agents are rule-based.
- **Impact is labelled simulation everywhere.** No real-world time savings are claimed.
- **No invented** commits, timestamps, users, partners, feedback or statistics.
- **All four judging criteria** are covered in doc 13 with gaps stated.
- **Deck and documents describe the same architecture.** Slides 7, 8 and 10 use PNGs exported from the Mermaid diagrams in doc 03.

## 8. Recommended final improvements (in priority order)

1. Resolve the six critical gaps above.
2. Approve the small fixes in Q17: one import to turn CI green, and the stale README/`DEMO.md`/YAML lines.
3. Mask `evidence_list` reporter identities (KI-4) with a regression test.
4. Run the Docker Compose and PostgreSQL paths once and record the result in doc 08.
5. Run a quick accessibility check (Lighthouse or axe) and a basic load test, and report honestly.
6. Test with 3–5 people. Quote the outcome only if it happens.
7. Regenerate or remove the committed `benchmark_results.json/.csv`, and stop tests rewriting them (KI-2, KI-3).
8. Consider a small labelled evaluation of agent recommendations (even 20 hand-made incidents).

## 9. Manual actions required from you

1. Answer [`INFORMATION_REQUIRED_FROM_TEAM.md`](../docs/INFORMATION_REQUIRED_FROM_TEAM.md) (Q1–Q21). 🔴 items first: Q1, Q2, Q3, Q4, Q6, Q8, Q12, Q19.
2. Capture the screenshots in [`SCREENSHOT_REQUIREMENTS.md`](../docs/SCREENSHOT_REQUIREMENTS.md) and drop them into the deck's placeholder boxes.
3. Replace every `[TEAM INPUT REQUIRED]` marker. Search for it: `grep -rn "TEAM INPUT REQUIRED" docs submission`.
4. Open the PPTX, check the layout and add team details.
5. Record the video using [`docs/15_VIDEO_DEMO_SCRIPT.md`](../docs/15_VIDEO_DEMO_SCRIPT.md) and [the recording checklist](demo/VIDEO_RECORDING_CHECKLIST.md).
6. Make the repository public, set the default branch, add the `LICENSE`, then commit `docs/` and `submission/`.
7. Before pushing, re-run a secret scan and restore tracked benchmark files: `git checkout -- backend/app/data/benchmark_results.json backend/app/data/benchmark_results.csv`.
8. Check the TechGig portal for the live deadline, file formats and size limits, then upload and keep the confirmation.
9. After uploading, open the submitted links in a private browser window.
