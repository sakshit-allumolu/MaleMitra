# Executive Summary — MaleMitra (ಮಳೆ ಮಿತ್ರ)

*When the rain comes, the road you are sent down should already know it is flooded.*

**Track:** Smarter Streets, Better Living · **Event:** IBM Bobathon – Build for Bengaluru 2026 · **Repo:** <https://github.com/sakshit-allumolu/MaleMitra>

The full version, with sources, is [`docs/01_EXECUTIVE_SUMMARY.md`](../docs/01_EXECUTIVE_SUMMARY.md). Markers: **[VERIFIED]** checked in code or by running it; **[USER-STATED]** told to us, not provable from the repo.

## The four required items

| Item | Answer |
|---|---|
| The problem | Commuters, control room and responders get flood information through different, slow channels. Needed: one verified picture that routes react to. |
| The prototype | Working FastAPI + React platform, three role workspaces, one watsonx Orchestrate agent that recommends and a human approves. |
| The Bob story | Built with IBM Bob. 95 Bob edits recorded in 7 local git notes **[VERIFIED]**; earlier and wider use **[USER-STATED]**, evidence pending. Story outline: [`docs/00`](../docs/00_PARTICIPATION_REQUIREMENTS.md). |
| The impact | 38 of 150 simulated trips cross a closed road when it is ignored; MaleMitra sends 0, for +14.2 s (+3.9 %). Simulation, not field data. |
| Privacy and human review | Agent recommends only. A human approves every closure. |

## 30-second pitch

In a Bengaluru monsoon, one flooded underpass can trap cars while navigation still routes drivers into it. The citizen who saw the water, the control room that can act, and the commuter who needs a safe route are not on the same page. **MaleMitra connects them.** A citizen reports a flood. The control room triages and dispatches a field team. Only after on-site verification does an administrator close the road. The moment the road closes, routes re-plan around it, and a ripple engine shows where displaced traffic will pile up. An **IBM watsonx Orchestrate agent** reads each incident, calls our tools and recommends the next step. It never acts alone: a human approves every closure.

## What was built [VERIFIED]

| Part | What it does |
|---|---|
| Citizen workspace | Geotagged hazard reports with optional photo. Direct vs risk-aware vs alternative routes. |
| Control room (admin) | Triage queue, dispatch, and the only authority to close or reopen a road. |
| Field responder | Claims tasks, records water depth and impassable yes/no, proposes clearance. |
| Ripple Engine | Re-routes 150 simulated trips after a closure and shows where load shifts. |
| watsonx Orchestrate agent | 8 tools. Recommends one next action with evidence. Cannot change an incident's status. |
| Audit and timeline | Every action and every tool call is recorded. |

Stack: FastAPI, SQLite or PostgreSQL, React + TypeScript + Vite, Leaflet. 53 API operations, 14 tables.

## How IBM technology contributes

| Technology | Contribution | Evidence status |
|---|---|---|
| IBM Bob | Used to build and refactor the codebase. | 7 local git notes, 95 edits (15 Nov). Earlier use on another machine is **[USER-STATED]**. Screenshots pending. |
| IBM watsonx Orchestrate | LLM agent that chooses tools and recommends actions for admin approval. | 37 passing tests. Live token exchange and chat verified 15 Nov. Full tool loop is **[USER-STATED]**. Screenshots pending. |

## Impact (simulation, not field data)

On a 20-node model of five Bengaluru neighbourhoods with 150 seeded synthetic trips and one closure: a closure-blind router sends **38 trips (25.3 %)** over the closed road. MaleMitra sends **0**, for an average **+14.2 s (+3.9 %)** per trip. Reproduce with `python backend/eval_benchmark.py`. Real-world baselines are not yet measured. See [`docs/10_IMPACT_AND_SCALABILITY.md`](../docs/10_IMPACT_AND_SCALABILITY.md).

## Verified status

242 backend tests pass; the frontend builds; the backend starts from a fresh virtual environment. Not yet run: PostgreSQL suite, Docker Compose, frontend tests (none exist), accessibility audit, load test.

## Responsible AI

The agent recommends only. Recommendations are limited to actions valid for the incident's current state and wait for human approval. Every call is logged. Known exposure: citizen free text reaches the LLM without sanitisation. See [`docs/09_SECURITY_PRIVACY_AND_RESPONSIBLE_AI.md`](../docs/09_SECURITY_PRIVACY_AND_RESPONSIBLE_AI.md).

## Open items before submitting

Deadline and Fresh Code confirmation, Orchestrate and Bob screenshots, `LICENSE` file, team details. All are listed in [`FINAL_REVIEW_REPORT.md`](FINAL_REVIEW_REPORT.md).
