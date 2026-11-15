# 13 · Judging Criteria Alignment

The hackathon scores four criteria, 5 points each (20 in total). This document maps each criterion to the evidence in the repository and gives a critical view of the gaps.

**Core participation requirement: "Built with IBM Bob".** Each team submits (1) the problem, (2) the prototype, (3) the Bob story, a short demo of how the team used Bob throughout development, and (4) one measurable outcome. Safety-focused projects must include privacy and human review in the design. Where each item lives: [00 Participation requirements](00_PARTICIPATION_REQUIREMENTS.md). Because the Bob story is a core requirement, its evidence also feeds criterion 1 (use of required IBM technology) and criterion 2 (use of AI and IBM technology), and it is currently our thinnest evidence.

### Official criteria wording (from the event brief)

| Criterion | What judges evaluate |
|---|---|
| (a) Completeness and Feasibility | Feasibility of the solution, completeness of the concept and implementation, quality of the proof-of-concept, and effectiveness of the participant's use of the required IBM technology |
| (b) Creativity and Innovation | Originality, uniqueness of approach, degree of innovation, and effectiveness of the use of AI and IBM technology in addressing the challenge |
| (c) Design and Usability | Quality of the user experience, accessibility, usability, ease of adoption, and effectiveness of the proposed design in real-world scenarios |
| (d) Effectiveness and Efficiency | How effectively the submission addresses the challenge, potential real-world impact, scalability, efficiency, and ability to solve meaningful user problems |

**We do not assign ourselves points.** Scoring is the judges' call. For each criterion we give an *evidence strength* rating (Strong / Moderate / Weak / Pending) based only on what can be verified today. A rating can improve once the pending items are done.

| Marker | Meaning |
|---|---|
| ✅ | Verified in code or by a run on 15 Nov 2026 |
| 🟦 | User-stated, not provable from the repo |
| 📸 | Evidence pending (screenshot or export needed) |
| ⚠️ | Gap that could cost points |

Related: [01 Executive Summary](01_EXECUTIVE_SUMMARY.md) · [14 Checklist](14_FINAL_SUBMISSION_CHECKLIST.md) · [15 Video script](15_VIDEO_DEMO_SCRIPT.md)

---

## Overview

| Criterion | Max | Evidence strength today | Main reason |
|---|---|---|---|
| 1. Completeness and Feasibility | 5 | **Moderate to Strong**, held back by compliance gaps and thin Bob evidence | Working prototype and 242 passing tests. The Orchestrate end-to-end proof, the Fresh Code position and the missing LICENSE are open. |
| 2. Creativity and Innovation | 5 | **Moderate** | Closed-loop design, trust-weighted crowd data, ripple engine and a governed agent. Several parts (Dijkstra routing, BPR) are standard techniques. |
| 3. Design and Usability | 5 | **Moderate** | Three role-based workspaces and an in-app demo walkthrough. No accessibility audit, no frontend tests, no user testing. |
| 4. Effectiveness and Efficiency | 5 | **Weak to Moderate** | One reproducible simulation result (38 of 150 trips → 0). No real-world baseline. The agent's quality has not been evaluated. |

---

## 1. Completeness and Feasibility (5 points)

### What judges are looking for
A clearly stated problem, a working prototype, an implementation that matches the claims, technical feasibility, real use of IBM technology, and a result a judge can reproduce.

### Evidence in our implementation

| Aspect | Evidence | Status |
|---|---|---|
| Problem clarity | Monsoon flooding of roads: reporters, responders and commuters are not on one page. [02](02_PROBLEM_STATEMENT_AND_SOLUTION.md) | ✅ |
| Working prototype | Three role workspaces, 53 API operations, 14 tables. Backend started in a fresh Python 3.12 venv: `/api/v1/health` = healthy (20 nodes, 56 edges), `/docs` = 200. [06](06_SETUP_AND_INSTALLATION.md) | ✅ |
| Implementation completeness | Full incident loop: report → triage → dispatch → verify → authorise closure → reroute → clearance → reopen. State guards in `incident_service.py`. [05](05_FEATURES_AND_USER_FLOWS.md) | ✅ |
| Automated tests | `pytest backend/tests`: **242 passed**. `npm run build` passes. [08](08_TESTING_AND_VALIDATION.md) | ✅ |
| Feasibility | Modular monolith, SQLite or PostgreSQL, Docker and Render config present, optional OSRM and TomTom with fallbacks. [03](03_TECHNICAL_ARCHITECTURE.md) | ✅ (Docker and PostgreSQL runs not executed) |
| IBM Bob | 7 local git notes recording 95 Bob edits on 15 Nov. Earlier use on another machine and "all commits" are user-stated. [04 Part A](04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md) | ✅ partial · 🟦 · 📸 |
| IBM watsonx Orchestrate | Agent YAML, 8-tool OpenAPI spec, 37 tests, live IAM token exchange and live chat on 15 Nov. End-to-end tool loop is user-stated. [04 Part B](04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md) | ✅ partial · 🟦 · 📸 |
| Reproducibility | Deterministic benchmark: identical result on three CLI runs. Setup guide with exact commands. | ✅ |

### Relevant documentation
[02](02_PROBLEM_STATEMENT_AND_SOLUTION.md), [03](03_TECHNICAL_ARCHITECTURE.md), [04](04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md), [06](06_SETUP_AND_INSTALLATION.md), [08](08_TESTING_AND_VALIDATION.md)

### Demonstration points
0. Lead with the Bob story (video segment 6, [15](15_VIDEO_DEMO_SCRIPT.md)): first prompt, a fix, review, and 242 passing tests.
1. Start from login with the demo accounts, then show one full incident loop across the three roles.
2. Show the closure changing a route in the citizen view.
3. Show the Orchestrate panel connected, then **Ask the agent** and the recommendation card (needs your live capture).
4. Run `python backend/eval_benchmark.py` and `pytest backend/tests` on screen.

### Gaps that could reduce the score
- ⚠️ **Orchestrate end-to-end evidence is not in the repo.** Only your statement. A judge who cannot see it may treat the mandatory IBM product as unproven. This is the single biggest risk.
- ⚠️ **Fresh Code Rule.** Every `feature-demo` commit is dated 15 Nov, after the published 14 Nov period end. The extension to 16 Nov is user-stated. See [Q1, Q2](INFORMATION_REQUIRED_FROM_TEAM.md).
- ⚠️ **Bob provenance is thin.** 95 edit notes, local only, one evening.
- ⚠️ CI lint step fails today (`F821 Undefined name 'Set'`, `agent_service.py:206`). A judge looking at the Actions tab sees red.
- ⚠️ No `LICENSE` file, although the event terms refer to the MIT licence.
- ⚠️ `main` holds an older prototype with unrelated history. A judge who opens the default branch sees the wrong code.
- ⚠️ README, `DEMO.md` and the agent YAML contain stale claims (130+ tests, `e2e_smoke.py`, Tailwind, "unverified" lines).
- ⚠️ PostgreSQL suite and Docker Compose were not run.

### Recommended improvements
1. Capture ORCH-1…7 with timestamps and keep the tunnel up during the demo ([SCREENSHOT_REQUIREMENTS](SCREENSHOT_REQUIREMENTS.md)).
2. Approve the small fixes in Q17 (Set import, stale text). They are not made yet.
3. Add the LICENSE after all contributors agree (Q12).
4. Align the default branch with the submission branch (Q11).
5. Push the Bob notes (`git push origin refs/notes/bob`) and add Bob task-history exports.
6. Run the Docker and PostgreSQL paths once and record the result in doc 08.

---

## 2. Creativity and Innovation (5 points)

### What judges are looking for
Originality, a fresh way of solving the problem, meaningful agentic AI, a clear difference from conventional solutions, and non-superficial use of IBM technology.

### Evidence in our implementation

| Aspect | What is distinctive | Honest caveat |
|---|---|---|
| Closed loop | Report, verification, closure and rerouting live in one system with role gates and an audit trail. | The individual parts (reporting, maps, routing) are familiar. The integration is the novelty. |
| Trust-weighted crowd data | An unverified report adds only a routing penalty scaled by reporter reputation and corroboration. Only an admin can close a road. 33 tests. | Weights are design choices and have not been calibrated on real data. |
| Ripple Engine | Re-routes 150 seeded trips on a closure and shows where load shifts. | Synthetic trips on a 20-node graph. Not field data. |
| Governed agent | The Orchestrate agent picks tools per incident (ReAct), writes a schema-checked, state-gated recommendation, and cannot change status. 37 tests. | One agent, invoked on admin request. No agent-to-agent coordination, no autonomous runs. |
| Honest degradation | Without IBM, TomTom or OSRM credentials the app still works and says what it fell back to. | Common good practice, but it helps a judge run the project. |
| Bob usage | Small surgical diffs rather than regenerated files. | Evidence is limited (see criterion 1). |

### Relevant documentation
[01](01_EXECUTIVE_SUMMARY.md), [02](02_PROBLEM_STATEMENT_AND_SOLUTION.md) (differentiation), [04 §B.10](04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md) (why agentic, not a chatbot)

### Demonstration points
- Show the Agent Decision Timeline with `LLM agent` rows next to `rule-based` rows. This makes the split between deterministic and LLM logic visible.
- Try an invalid action and show the 422 `workflow_gate` the agent must re-plan around.
- Show the ripple view after a closure.

### Gaps that could reduce the score
- ⚠️ Only one of the four "agents" is an LLM. The other three are rule-based Python. Do not call them AI agents in the video.
- ⚠️ No evaluation of agent quality (no labelled set, no comparison with a human or a baseline).
- ⚠️ Prompt-injection exposure: citizen free text reaches the LLM. The mitigation is human approval, with no text sanitisation.
- ⚠️ Orchestrate is used as a single advisor. A judge may expect more orchestration (several agents, flows, schedules).

### Recommended improvements
Choose only what is realistic before submission. All of these are **proposed**, not built:
1. A second agent, or an Orchestrate flow that auto-analyses `critical` incidents ([04 Part C](04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md)).
2. Sanitise and length-limit citizen notes before they reach the agent.
3. A small labelled evaluation of recommendations (even 20 hand-made incidents) to turn "agent quality unevaluated" into a number.

---

## 3. Design and Usability (5 points)

### What judges are looking for
A clear, usable interface, sensible user workflows, accessibility, ease of first use, and adoption potential.

### Evidence in our implementation

| Aspect | Evidence | Status |
|---|---|---|
| Role-based workspaces | Citizen ("Find Routes", "Withdraw"), Admin (Road Map & Overlay, Agent Decision Timeline, System Audit Trail, watsonx Orchestrate Agent, Manage Accounts), Responder ("My tasks", "Team queue", "Claim", "Find Route (Avoid Blockages)"). Screenshots SS02, SS03, SS09. | ✅ |
| Route comparison | Direct vs risk-aware vs alternative cards with turn-by-turn directions and optional voice. SS11. | ✅ |
| Transparency | Every agent action tagged `LLM agent` or `rule-based`, visible audit trail. SS04, SS06. | ✅ |
| First-use help | In-app demo walkthrough (`DemoWalkthroughModal.tsx`) and one-click demo logins. | ✅ |
| Map | Leaflet map with OSM attribution (`InteractiveMap.tsx:225`). | ✅ |
| Error and offline states | UI says "Not connected" for Orchestrate and "Graph fallback (OSRM unavailable)" for routing. | ✅ |
| Adoption potential | Web app, no install. Self-hostable. | Plausible, unproven |

### Relevant documentation
[05](05_FEATURES_AND_USER_FLOWS.md), [09](09_SECURITY_PRIVACY_AND_RESPONSIBLE_AI.md), [SCREENSHOT_REQUIREMENTS](SCREENSHOT_REQUIREMENTS.md)

### Demonstration points
Citizen view first, because it is the simplest. Then the admin queue, then the responder. Keep each role to under a minute. Show the walkthrough modal as proof of first-use support.

### Gaps that could reduce the score
- ⚠️ **No accessibility audit.** No claim of WCAG conformance is made. Styling is inline, and keyboard and screen-reader behaviour is untested.
- ⚠️ **English-only UI.** A Kannada interface is on the roadmap only. The project name is bilingual, but the interface is not.
- ⚠️ **No frontend tests** and no user testing. All usability statements are the team's design intent, not measured results.
- ⚠️ Single 586 kB JavaScript chunk. This may matter on mobile networks in the rain.
- ⚠️ Public demo password (`demo123`) is acceptable for a demo but must not be presented as a security feature.
- ⚠️ The responder screenshot (SS09) shows an empty state. A populated one would show more.

### Recommended improvements
1. Run a quick Lighthouse or axe check and report the result honestly in doc 08.
2. Retake SS09 with a populated queue.
3. Test with 3–5 people and record what happened. Then, and only then, quote it.
4. Code-split the frontend bundle (proposed).

---

## 4. Effectiveness and Efficiency (5 points)

### What judges are looking for
Does it solve the problem, with a measurable and believable impact, efficiently, with a path to scale.

### Evidence in our implementation

| Aspect | Evidence | Class |
|---|---|---|
| Closed-road exposure | **38 of 150 trips (25.3 %) cross the closed road when it is ignored; MaleMitra sends 0.** Identical on three CLI runs. | Demonstrated (simulation) |
| Detour cost | Mean trip time 366.7 s → 381.0 s (**+14.2 s, +3.9 %**). 0 trips stranded. | Demonstrated (simulation) |
| Efficiency of the engine | About 4–5 ms for the benchmark. | Demonstrated |
| Process safety | Unverified reports cannot close a road; agent cannot change status (tests). | Demonstrated (tests) |
| Time saved, fewer drivers in flood water, faster triage | Not measured. | Estimated or projected only |
| Scalability | PostgreSQL, multi-worker state sharing (tested with separate server processes), OSRM, Docker. | Design evidence. Not load-tested. |
| KPIs | K1–K6 defined with method, baseline, target, frequency, source. | Plan, with K1 and K2 demonstrated in simulation |

### Relevant documentation
[10](10_IMPACT_AND_SCALABILITY.md), [08](08_TESTING_AND_VALIDATION.md), [11](11_LIMITATIONS_AND_ROADMAP.md)

### Demonstration points
Run the CLI benchmark live and read the three numbers (38 → 0, +14.2 s, 0 stranded). Say clearly that it is a simulation on a 20-node model of five neighbourhoods. Do not describe it as measured field impact.

### Gaps that could reduce the score
- ⚠️ **Impact is simulated.** There is no pilot, no real baseline and no user data. K3–K6 have no baseline (marked "requires measurement").
- ⚠️ **Number consistency.** The in-app benchmark page shows different time figures (+20.9 s to +38.6 s) because it uses live graph state. The committed JSON shows +289.6 %. Quote only the CLI figures. A judge who compares the app to the deck will see a mismatch unless it is explained.
- ⚠️ The modelled network is five neighbourhoods and 20 nodes, small against a city of this size. City-wide routing depends on OSRM and a bounding box, but the **risk model** covers only the small graph.
- ⚠️ No load test, so "scalable" is a design claim.
- ⚠️ Agent effectiveness (accuracy of recommendations) is unevaluated.
- ⚠️ A known privacy gap: `evidence_list[].submitted_by` and `submitter_name` expose other citizens' ids and names to signed-in citizens (doc 09 §4.1, KI-4). Unfixed.

### Recommended improvements
1. Explain the benchmark figures in one slide note and in the video: "CLI figures are canonical".
2. Fix the evidence-list masking (needs your approval, Q17).
3. Measure one real number, even a small one, such as time from report to verified closure in a staged run with teammates. Label it as a staged run.
4. Run a basic load test (for example 50 concurrent route requests) and report it as is.
5. Regenerate the committed benchmark JSON so it matches the CLI result, or remove it from the repo.

---

## Cross-cutting risks a judge may raise

| Question a judge may ask | Short honest answer | Where |
|---|---|---|
| Was this built inside the hackathon window? | Commit dates for the submitted branch are all 15 Nov. The extension is user-stated. Needs organiser confirmation. | [Q1, Q2](INFORMATION_REQUIRED_FROM_TEAM.md) |
| Show me Bob in action. | 95 local edit notes and your screenshots (pending). | [04 Part A](04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md) |
| Show me Orchestrate in action. | Live capture (pending). Tests, YAML and OpenAPI spec are in the repo. | [04 Part B](04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md) |
| Is the impact real? | It is a simulation. Real baselines are not yet measured. | [10](10_IMPACT_AND_SCALABILITY.md) |
| Is it safe if the AI is wrong? | The agent can only recommend. A human approves. The recommendation is state-gated. | [09](09_SECURITY_PRIVACY_AND_RESPONSIBLE_AI.md) |
| Is it open source under MIT? | No LICENSE file yet. Pending team agreement. LGPL (psycopg) and MPL (certifi) dependencies are noted. | [12](12_REPOSITORY_AND_LICENSE.md) |

## Priority order for the remaining time

1. 🔴 Orchestrate screenshots and a reachable tool URL (criteria 1 and 2).
2. 🔴 Confirm the deadline and the Fresh Code position with the organisers (criterion 1).
3. 🔴 Add the LICENSE, fix the default branch, make the repo public (criterion 1).
4. 🟠 Fix the lint error and stale claims (criterion 1, after approval).
5. 🟠 Bob evidence exports (criteria 1 and 2).
6. 🟡 Accessibility check, populated responder screenshot, small user test (criterion 3).
7. 🟡 Staged measurement and a basic load test (criterion 4).
