# 01 · Executive Summary

**MaleMitra (ಮಳೆ ಮಿತ್ರ – "Rain Friend")** — *When the rain comes, the road you are sent down should already know it is flooded.*

Track: **Smarter Streets, Better Living** · Event: IBM Bobathon – Build for Bengaluru 2026 · Repo: <https://github.com/sakshit-allumolu/MaleMitra>

> Status legend used across the package: **[VERIFIED]** checked in code or by running it · **[USER-STATED]** told to us, not provable from the repo · **[TEAM INPUT REQUIRED]** see [`INFORMATION_REQUIRED_FROM_TEAM.md`](INFORMATION_REQUIRED_FROM_TEAM.md).

---

## The four required items at a glance

| Required item | Our answer |
|---|---|
| The problem | Commuters, control-room staff and field responders get flood information through different, slow channels. The improvement needed is one verified picture that routes react to. |
| The prototype | Working FastAPI + React platform with an IBM watsonx Orchestrate agent that recommends and a human approves. |
| The Bob story | Built with IBM Bob. 95 Bob edits are recorded in the repo **[VERIFIED]**; wider history **[USER-STATED]**, evidence pending. See [04 Part A](04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md). |
| The impact | 38 of 150 simulated trips cross a closed road when it is ignored; MaleMitra sends 0, for +14.2 s (+3.9 %) per trip. Simulation, not field data. |
| Privacy and human review | Agent recommends only; a human approves every closure. |

## 30-second pitch

> In a Bengaluru monsoon, one flooded underpass can trap cars while the next navigation app still routes drivers into it, because the citizen who saw the water, the control room that can act, and the commuter who needs a safe route are not on the same page. **MaleMitra connects them.** A citizen reports a flood. The control room triages, dispatches a field team, and only after on-site verification does an administrator close the road. The moment the road closes, every commuter's route re-plans around it, and a ripple engine shows where the displaced traffic will pile up. An **IBM watsonx Orchestrate agent** reads each incident, calls our tools, and recommends the next step. It never acts alone: a human approves every closure.

## The problem in plain language

Heavy rain turns low-lying roads and underpasses into hazards within minutes. Today the people who *see* the problem (commuters), the people who can *fix or close* it (the municipal control room and field crews), and the people who need to *avoid* it (everyone else on the road) usually get information through different, slow channels. The result is drivers entering water they cannot see the depth of, and response crews working without a shared picture.

## Why it matters in Bengaluru

External context, with sources (we cite what we could verify and do not invent statistics):

- Bengaluru's monsoon runs June–September ([Wikipedia: Bengaluru](https://en.wikipedia.org/wiki/Bengaluru), climate section). 2022 was its wettest year, with over 1,700 mm of rain, against a mean of about 860 mm ([Wikipedia: Lakes in Bengaluru](https://en.wikipedia.org/wiki/Lakes_in_Bengaluru)).
- Built-up land rose from about 8 % of the city area in 1973 to 87.6 % by 2025, while open water and permeable surfaces fell ([Wikipedia: Infrastructure in Bengaluru](https://en.wikipedia.org/wiki/Infrastructure_in_Bengaluru)). The city historically had over 1,400 lakes and tanks; fewer than 200 survive (same page).
- Urban flood causes in Bengaluru are discussed in: Palanichamy, R. B., *"Overpopulation, concrete jungle, altered landscape: Decoding Bengaluru's urban flood woes"*, India Today, 7 Sept 2022 (listed as a reference on the Wikipedia page above; **we have not independently opened it** — please verify before quoting).

We make **no claim** about casualty counts, economic loss or response-time statistics, because we have not verified any.

## Who experiences it

| Group | Experience |
|---|---|
| Commuters, delivery riders, cab/auto drivers | Do not know which road is flooded or how deep; navigation ignores local hazards. |
| Municipal control-room staff (modelled on BBMP) | Receive scattered reports with no way to tell duplicates from new events or judge credibility. |
| Field responders (stormwater / traffic units) | Dispatched without a shared, up-to-date incident record. |

## What we built **[VERIFIED]**

A working modular monolith (FastAPI + React) with three role-based workspaces:

1. **Citizen** — report a geotagged hazard (optional photo); compare **Direct vs MaleMitra risk-aware vs alternative** routes with turn-by-turn directions and optional voice.
2. **Control room (admin)** — triage queue, dispatch a team or named responder, and the *only* authority to close or reopen a road.
3. **Field responder** — verify on site (water depth in cm, impassable yes/no) and propose clearance.
4. **Ripple Engine** — shows how one closure shifts 150 simulated trips across the road network and where congestion builds.
5. **watsonx Orchestrate agent** — analyses an incident with 8 tools and *recommends* the next action for an admin to approve or dismiss.

## How it works (one loop)

`Report → map to road segment → merge duplicates → admin triage → team dispatch → field verification → admin authorises closure → graph version increments → all routes re-plan → ripple simulation → clearance proposed → admin reopens`.

Every step is gated by role and recorded in an audit trail.

## What makes it different

- **Closed loop, not a map.** Reports, human verification, closure and rerouting live in one system.
- **Trust-weighted crowd data.** An unverified report only adds a routing *penalty* scaled by reporter reputation and corroboration; **only an admin can close a road.**
- **Ripple Engine** estimates second-order effects of a closure (where do the displaced trips go?).
- **Agentic but governed.** The Orchestrate agent chooses which tools to call and reasons over results, but can only *recommend*; recommendations are limited to actions valid for the incident's current state, and every tool call is logged.
- **Honest degradation.** Without IBM credentials, TomTom or OSRM, the app still works and says what it fell back to.

## How IBM technologies contribute

| Technology | Contribution | Evidence |
|---|---|---|
| **IBM Bob** | Used to build and refactor the codebase. | 7 local git notes recording 95 Bob edit operations (15 Nov); further Bob use on an earlier machine is **[USER-STATED]** — evidence pending. See [04](04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md). |
| **IBM watsonx Orchestrate** | LLM agent that calls MaleMitra's tools and recommends next steps. | 37 passing tests; live token exchange and chat call verified 15 Nov; end-to-end run **[USER-STATED]**, screenshots pending. |
| IBM Cloud Code Engine | Optional deployment target (script provided). | `scripts/deploy_code_engine.sh` |

## Impact (honest framing)

| Level | Statement |
|---|---|
| **Demonstrated (simulation, not field data)** | On a 20-node model of five Bengaluru neighbourhoods (Koramangala, Indiranagar, Domlur, HSR, Ejipura) with 150 seeded synthetic trips and one closure, a closure-blind shortest path sends **38 trips (25.3 %)** over the closed road; MaleMitra sends **0**, at an average **+14.2 s (+3.9 %)** per trip. Reproduce: `python backend/eval_benchmark.py`. |
| Estimated | Needs real baselines (time from first report to verified closure; drivers re-routed). **Requires measurement.** |
| Projected | See [10](10_IMPACT_AND_SCALABILITY.md). |

## Scalability and potential

PostgreSQL + multi-worker state sharing (tested with separate server processes), self-hostable OSRM, containerised deployment. **Not load-tested.** Next steps: ingest rainfall forecasts, larger modelled network, Kannada UI, real municipal integration. See [11](11_LIMITATIONS_AND_ROADMAP.md).

## Read next

[02 Problem & Solution](02_PROBLEM_STATEMENT_AND_SOLUTION.md) · [03 Architecture](03_TECHNICAL_ARCHITECTURE.md) · [04 IBM Bob & Orchestrate](04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md) · [13 Judging alignment](13_JUDGING_CRITERIA_ALIGNMENT.md) · [Compliance gaps](14_FINAL_SUBMISSION_CHECKLIST.md)
