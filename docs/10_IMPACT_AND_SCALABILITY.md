# 10 · Impact Assessment and Scalability

**Reading guide.** Every claim in this document is placed in exactly one of three classes. Do not merge them in slides or in the video.

| Class | Meaning | Allowed wording |
|---|---|---|
| **D — Demonstrated** | Produced by running the code in this repository (simulation or test) | "In our simulation …" |
| **E — Estimated** | Reasoned from the design or from cited public facts; not measured on MaleMitra | "We expect … / could …" |
| **P — Projected** | Future value that depends on work or data we do not yet have | "Target … / if deployed …" |

No field pilot, user study, partnership or municipal data exists. Nothing here is a measured real-world saving.

## 1. Beneficiaries

| Group | Direct benefit | Indirect benefit |
|---|---|---|
| Commuters, riders, delivery and cab drivers | Route comparison that accounts for reported and closed hazards; a reporting channel | Fewer stalled vehicles and less congestion on the affected corridor |
| Municipal control-room staff | One verified record per hazard (merging), confidence, audit trail, agent triage recommendation | Time to decision; defensible records |
| Field responders | One queue, atomic claim, structured verification and clearance forms | Less duplicated dispatch |
| City planners (secondary) | Ripple view of what a closure does to neighbouring roads | Evidence for diversion planning |

## 2. Demonstrated impact (D)

All values come from the deterministic benchmark CLI (`python backend/eval_benchmark.py`, seed 42, repeated three times with identical output) and automated tests, on the **20-node / 56-edge modelled graph with 150 synthetic trips**.

| Metric | Baseline (closed road ignored) | MaleMitra | Source |
|---|---|---|---|
| Trips crossing the closed Sony World corridor (`edge-7`, `edge-8`) | **38 of 150 (25.3 %)** | **0 (0 %)** | benchmark CLI ×3 |
| Mean trip time | 366.7 s | 381.0 s (**+14.2 s, +3.9 %** averaged over all 150 trips) | benchmark CLI ×3 |
| Trips stranded (no route) | — | 0 | benchmark CLI |
| Trips re-routed per closure in the Ripple view | — | 38 (25 %), +56.2 s per re-routed trip | screenshot SS07 (consistent with 14.2 s × 150 / 38) |
| Engine runtime | — | ≈ 4–5 ms | benchmark CLI |

What this shows: given a verified closure, the routing layer removes every modelled trip from the closed road for a small average time cost. What it does **not** show: real-world driver behaviour, real flood frequency, or real time saved.

**Do not quote** the committed `backend/app/data/benchmark_results.json` (it records +289.6 %) or the in-app Benchmark page's time figures, which depend on live graph state (+20.9 s/+5.7 % on a fresh DB; +38.6 s/+10.5 % after another closure in the audit run). The "38 → 0" count was identical in every run.

**Demonstrated process properties (tests):** unverified reports can never close a road; only an admin can; reports within 10 m merge (10 tests); crowd-trust formula behaves as designed (33 tests); agent recommendations are state-gated and cannot change status (37 tests).

**Observed in the development database (not a usage study):** of 144 stored Orchestrate recommendations, 61 were approved, 30 dismissed and 53 undecided. These rows were created during development and testing, some by scripts, so they show the approve/dismiss mechanism working, not the quality of the agent or any user preference.

## 3. Estimated impact (E)

| Benefit | Reasoning | Confidence | What would make it measurable |
|---|---|---|---|
| Less control-room time spent on duplicates | Merging collapses repeated reports of one spot into one incident with a count | Medium (mechanism proven, magnitude unknown) | Count raw reports vs incidents in a pilot |
| Faster triage | The agent gathers context from 8 tools and proposes a next action in one step | Low–medium (agent quality unevaluated) | Time-to-first-action with vs without the agent |
| Fewer cars entering flooded roads | Routes avoid verified closures and weighted hazards | Medium in principle, unknown in practice (depends on adoption and on closures being published quickly) | Pilot with app-originated trips |
| Better diversion planning | Ripple shows which neighbouring roads absorb diverted trips | Medium | Compare predicted vs observed load after real closures |

Context supporting the **problem** (not the product's effect): Bengaluru's monsoon runs June–September (https://en.wikipedia.org/wiki/Bengaluru); mean annual rainfall is about 860 mm with over 1,700 mm in 2022, the wettest year recorded there (https://en.wikipedia.org/wiki/Lakes_in_Bengaluru); built-up area rose from about 8 % in 1973 to 87.6 % in 2025 and fewer than 200 of over 1,400 lakes survive (https://en.wikipedia.org/wiki/Infrastructure_in_Bengaluru). We found **no verified source in this audit for flood casualties, response times or per-incident costs, so none are claimed.** Suggested primary sources to obtain them: BBMP/BTP/KSNDMC releases and the Karnataka State Disaster Management Authority reports [TEAM INPUT REQUIRED].

## 4. KPI plan (≥ 3 measurable KPIs)

| # | Metric | Measurement method | Baseline | Target | Frequency | Data source |
|---|---|---|---|---|---|---|
| K1 | **Closed-road exposure:** share of modelled/real app-planned trips whose chosen route crosses a verified-closed segment | Benchmark CLI for simulation; in a pilot, count planned routes returned by `/routes/compare` with `blocked_edges_crossed > 0` over all calls | **Simulation: 25.3 % (38/150).** Real-world: requires measurement | **0 %** (simulation achieved); pilot target 0 % of returned *risk-aware* routes | Every code change (CI) / daily in a pilot | `eval_benchmark.py`; `/routes/compare` logs |
| K2 | **Detour cost:** mean extra travel time of MaleMitra vs ignoring the closure, over all trips | Same benchmark; in pilot, `estimated_duration_s` of risk-aware minus fastest | **+14.2 s (+3.9 %)** in simulation | ≤ +5 % in simulation; pilot target to be set after first data | Per release / daily | benchmark CLI; route responses |
| K3 | **Report-to-verified-closure time:** minutes from first citizen report to `blocked` | Timestamps `incident.created_at` → audit event `AUTHORIZE_AUTHORIZE_BLOCK` | **Requires measurement** (no real incidents) | Set after pilot; compare with agent-assisted vs not | Per incident, weekly summary | `incidents`, `audit_events` |
| K4 | **Duplicate reduction ratio:** raw reports ÷ open incidents | `SUM(reports_count)` / `COUNT(incidents)` | Dev DB: 1166 reports over 587 incidents (≈ 2.0) is **test data, not a baseline** | Higher ratio with stable precision | Weekly | `incidents.reports_count` |
| K5 | **Agent recommendation acceptance rate:** approved ÷ (approved + dismissed) | `agent_events.decision` | Dev DB 61 / 91 (67 %) — **development data, not a baseline** | Track; investigate low or very high rates (automation bias) | Weekly | `agent_events` |
| K6 | **False-closure rate:** closures later found unnecessary by a responder | Count `blocked` incidents whose clearance finds < 10 cm on arrival | **Requires measurement** | Near 0 (design should make it rare because closure needs verification) | Per closure | `incident_evidence` |

K1 and K2 are the headline KPIs for the submission (D-class today). K3–K6 are instrumentation-ready from existing tables but have no real data (E/P-class).

## 5. Social, environmental, accessibility

- **Social:** gives residents a structured channel and visible follow-through; supports transparent, auditable municipal action. No claim of reduced harm is made without data.
- **Environmental (E):** fewer stalled/idling vehicles and shorter detours *could* reduce emissions locally; **no measurement or estimate was made.**
- **Accessibility (current):** voice narration of directions through the browser; English-only UI; only two `aria-` attributes in the frontend; no formal accessibility audit. Not a strength today (see [13](13_JUDGING_CRITERIA_ALIGNMENT.md)).
- **Inclusion gap:** crowd reports depend on smartphone owners; neighbourhoods with fewer reporters will be under-represented.

## 6. Bengaluru applicability

The 20-node graph covers Koramangala, Indiranagar, Domlur, HSR Layout and Ejipura — localities named in the code and seeded data. Routing and report acceptance work city-wide inside the bounding box `77.42,12.82 – 77.78,13.13`, but **the hazard/ripple model is only calibrated on those five localities**. Hazard types and the BBMP-style role model are tailored to Bengaluru's monsoon failure modes (underpass waterlogging, drain overflow, fallen trees, open manholes).

## 7. Scalability

| Dimension | Today (verified) | Constraint | Path |
|---|---|---|---|
| Application | One FastAPI process or `WEB_CONCURRENCY` workers; replicas on PostgreSQL share state through DB epoch/leases (6 multi-process tests) | Not load-tested | Load test, then horizontal scaling behind a proxy |
| Database | SQLite (one host) or PostgreSQL 16 | Single PostgreSQL node; no replication set-up in repo | Managed PostgreSQL with HA |
| Road graph | 20 nodes / 56 edges hand-built JSON, held in memory | **Biggest scaling blocker** | Build the graph from OpenStreetMap for the whole city; store/partition per ward |
| Routing geometry | OSRM (self-hosted via Compose or public) with breaker + cache | Public server has no SLA | Self-host OSRM per city extract |
| Traffic data | Optional TomTom within free-tier budgets | Quota (≈ 2,500 req/day) | Paid tier or city feeds |
| Real-time updates | SSE every 2.5 s, 100 client cap | Cap is a safeguard, not a capacity test | Pub/sub broker, CDN for the public map |
| Agent layer | One Orchestrate agent, on-demand | Tunnel/public URL for callbacks; each analysis is an LLM run | Stable hosted URL (Code Engine script exists), queueing, batching |
| Other cities | `ROUTE_AREA_BBOX`, graph JSON, trips JSON, team seeds are data/config | Needs a graph and local teams per city | Config-per-city package; Mumbai, Chennai, Hyderabad, Pune are plausible next candidates as they face monsoon flooding (E-class, no study done) |

## 8. Future expansion (P-class, not built)

Rainfall/forecast ingestion; automated closure *proposals* from sensor feeds (still human-approved); Kannada and other languages; push notifications and a mobile app; image analysis of photos with human review; integration with BBMP/BTP systems; multi-agent Orchestrate flows (see [04 Part C](04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md)). Detailed, dated roadmap: [11](11_LIMITATIONS_AND_ROADMAP.md).
