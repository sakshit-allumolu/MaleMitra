# 00 · Participation Requirements Map

**"Built with IBM Bob" is the core participation requirement.** Each team submits four things. This page shows where each one is in the package, how strong the evidence is today, and what is still missing. For safety-focused projects, privacy and human review must be part of the design.

Status keys: ✅ verified in the repo or by a run on 15 Nov 2026 · 🟦 team-stated, not provable from the repo · 📸 your screenshot or export is pending.

| # | Required item | Our answer in one line | Evidence today | Where |
|---|---|---|---|---|
| 1 | **The problem:** who experiences it, and what needs to improve | Commuters, control-room staff and field responders are on different channels during monsoon flooding. What needs to improve: one shared, verified picture that routes react to. | ✅ written, sourced, no invented statistics | [02](02_PROBLEM_STATEMENT_AND_SOLUTION.md), [01](01_EXECUTIVE_SUMMARY.md) |
| 2 | **The prototype:** working, built with IBM Bob, agentic AI where useful | Three role-based workspaces plus a watsonx Orchestrate agent that recommends and a human approves | ✅ 242 tests pass, build passes, backend starts clean · Orchestrate: ✅ code, tests, live chat · 🟦📸 full tool loop | [05](05_FEATURES_AND_USER_FLOWS.md), [06](06_SETUP_AND_INSTALLATION.md), [08](08_TESTING_AND_VALIDATION.md), [04 Part B](04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md) |
| 3 | **The Bob story:** a short demo of how the team used Bob throughout development | See the outline below | ✅ 95 Bob edits recorded in 7 local git notes · 🟦📸 earlier history and "all commits" | [04 Part A](04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md), [video script](15_VIDEO_DEMO_SCRIPT.md) |
| 4 | **The impact:** one measurable outcome | **Closed-road exposure: 38 of 150 simulated trips → 0**, for +14.2 s (+3.9 %) mean trip time. Simulation, not field data. | ✅ identical on three CLI runs | [10](10_IMPACT_AND_SCALABILITY.md) |
| 5 | **Safety projects:** privacy and human review in the design | Agent only recommends. Human approves. Recommendations are state-gated. No reporter PII reaches the agent. | ✅ implemented · ⚠️ known gaps listed | [09](09_SECURITY_PRIVACY_AND_RESPONSIBLE_AI.md) |

## 1. The Bob story is the centre of the submission

Judges will look for Bob **throughout development**, not only at the end. Today the repository proves only one evening of it. The story has to be completed with your own evidence.

### What we can prove from the repository ✅

| Fact | Detail |
|---|---|
| Bob edited this codebase | `git notes --ref=bob`: 7 notes, 95 edit operations (94 `apply_diff`, 1 `insert_content`), 15 Nov 2026, 22:38–23:36 IST |
| Where | Map component (32), routing module (27), responder workspace (22), demo guide (10), incident service (3), one test (1) |
| How | Small, reviewable diffs rather than regenerated files |
| How the output was checked | 242 passing tests, a deterministic benchmark, type-check and build in CI |

Limitation: the notes are **local only** (`git ls-remote origin 'refs/notes/*'` returns nothing). To publish them: `git push origin refs/notes/bob`.

### What you told us 🟦 and must evidence 📸

- Bob was used on a different system for the earlier commits.
- All commits on `main` and every other branch were made with Bob.
- The README §8 claims: schemas, state machine, ripple engine, benchmark harness, test fixes.

### Suggested three-beat structure for the 60–90 second Bob demo

Fill the brackets with **real** moments from your Bob history. Do not invent them.

| Beat | Show on screen | Say (adapt) |
|---|---|---|
| **1. Start** | BOB-1: first prompt that scaffolded the project, with date | "We started by asking Bob to **[TEAM INPUT REQUIRED: real first task]**." |
| **2. Build and fix** | BOB-2: Bob fixing a failing test. BOB-3: Bob applying a diff to a real file | "When **[TEAM INPUT REQUIRED: real failure]** broke, Bob read the test, proposed a small diff and we re-ran the suite." |
| **3. Review and trust** | Terminal: `pytest backend/tests` (242 passed) and `git notes --ref=bob list \| wc -l` | "We reviewed every diff: **[TEAM INPUT REQUIRED: who and how]**. 95 Bob edits are recorded in the repo, and 242 tests check the result." |

Optional fourth beat if you have the history: BOB-4 (earlier system, with dates) to show Bob across the whole build.

## 2. Single measurable outcome

The headline outcome for the submission is:

> **Closed-road exposure.** In a deterministic simulation (20-node model of five Bengaluru neighbourhoods, 150 seeded synthetic trips, one verified closure), a router that ignores the closure sends **38 trips (25.3 %)** over the closed road. MaleMitra sends **0**, at an average cost of **+14.2 s (+3.9 %)** per trip.

Reproduce: `python backend/eval_benchmark.py` (identical on three runs). Label it as simulation every time. Real-world time saved is **not** measured. Other KPIs (K3–K6) have no baseline yet: [10 §4](10_IMPACT_AND_SCALABILITY.md#4-kpi-plan--3-measurable-kpis).

## 3. Safety, privacy and human review

| Design choice | Status |
|---|---|
| The agent cannot change status or close a road; only `submit_recommendation` writes, and it stores a recommendation awaiting approval | ✅ |
| Only an admin closes or reopens a road, and only after field verification | ✅ |
| Recommendations must fit the incident's current state; stale ones cannot be approved | ✅ |
| No reporter name, email or phone is returned to the agent | ✅ |
| Every action and tool call is logged and visible to admins | ✅ |
| Citizen free text reaches the LLM unsanitised (prompt-injection exposure) | ⚠️ mitigated by the above, not sanitised |
| Other reporters' names and ids appear in `evidence_list` for signed-in citizens | ⚠️ known privacy gap, unfixed ([09 §4.1](09_SECURITY_PRIVACY_AND_RESPONSIBLE_AI.md)) |

## 4. What to do next

1. Gather the Bob evidence (BOB-1…5) and decide the three beats above. See [SCREENSHOT_REQUIREMENTS](SCREENSHOT_REQUIREMENTS.md).
2. Answer Q3, Q4 and Q5 in [`INFORMATION_REQUIRED_FROM_TEAM.md`](INFORMATION_REQUIRED_FROM_TEAM.md).
3. Record the video using [15](15_VIDEO_DEMO_SCRIPT.md). The Bob segment now has the largest share after the live demo.
