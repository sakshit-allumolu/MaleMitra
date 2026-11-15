# 02 · Problem Statement and Detailed Solution

## 1. Problem title

**Fragmented flood information during Bengaluru's monsoon: no shared, verified, real-time picture connecting citizens, the control room, field crews and commuters' routes.**

## 2. Background and context

Bengaluru receives most of its rain between June and September ([Wikipedia: Bengaluru](https://en.wikipedia.org/wiki/Bengaluru)). Over five decades, built-up area grew from roughly 8 % (1973) to 87.6 % (2025) of the city's land, while lakes and permeable ground shrank; the city once had more than 1,400 lakes and tanks and fewer than 200 survive ([Wikipedia: Infrastructure in Bengaluru](https://en.wikipedia.org/wiki/Infrastructure_in_Bengaluru)). The stormwater drain network is about 842 km and is described as impacted by urbanisation ([Wikipedia: Lakes in Bengaluru](https://en.wikipedia.org/wiki/Lakes_in_Bengaluru)). 2022 recorded over 1,700 mm of rain, about twice the mean annual figure (same page).

These sources describe the *environmental* setting. We did **not** find, and therefore do not cite, verified statistics on flood-related traffic incidents or response times. **[TEAM INPUT REQUIRED]** — if you hold news reports or municipal data on named underpass flooding events, add them here with URLs.

## 3. Problem description

When rain intensifies, a road segment (often an underpass or low junction) can become impassable within minutes. Three information gaps follow:

1. **Observation gap.** The people who see the water (commuters) have no structured channel that is weighed for credibility and tied to a specific road segment.
2. **Action gap.** The control room that can dispatch crews and close roads gets unstructured, duplicate and unverifiable reports.
3. **Routing gap.** Even after a road is closed, commuters' route choices don't change automatically, and nobody can see where the diverted traffic will concentrate.

## 4. People affected

| Group | Pain | What MaleMitra gives them |
|---|---|---|
| Commuters, riders, drivers | Entering flooded roads; unpredictable detours | Risk-aware route compare, closure-aware routing, report channel |
| Control-room staff | Duplicate/low-quality reports; no triage aid | Duplicate merge, confidence, reputation-weighted evidence, AI recommendation, single authority for closure |
| Field responders | Unclear tasking | Team queue / named assignment, field-verification form, clearance proposal |
| City planners (secondary) | No view of closure side-effects | Ripple Engine |

## 5. Current challenges and existing approaches

| Approach (general categories) | Limitation relevant here |
|---|---|
| Consumer navigation apps with live traffic | Optimise travel time; do not know a municipal-verified flood closure unless it appears in their data. We do not claim anything about any specific vendor's internals. |
| Social-media reporting / helplines | Unstructured, duplicated, hard to verify, not tied to the road graph. |
| Manual control-room coordination | Slow and does not show second-order traffic effects. |

*Caveat:* the above is a general characterisation; we have not benchmarked named products. **[TEAM INPUT REQUIRED]** if you want a named comparison with sources.

## 6. Why existing solutions are insufficient

None of the categories above closes the loop *report → verify → authorise → re-route → simulate effect* under role-based human control. That loop is MaleMitra's contribution.

## 7. Bengaluru-specific relevance

- Hazard types match local failure modes: `waterlogging`, `drain_overflow`, `fallen_tree_water`, `manhole_hazard`, `road_submerged` (`schemas.py`).
- Seeded scenario: Sony World Junction underpass (Koramangala), Indiranagar 100 ft Road drain overflow; geography covered by the modelled graph: Koramangala, Indiranagar, Domlur, HSR, Ejipura.
- Authority modelling: BBMP-style control room, teams "Stormwater Response" and "Traffic & Debris".
- City-wide route/report acceptance bounded by `ROUTE_AREA_BBOX` (77.42,12.82 – 77.78,13.13); outside it the app refuses rather than returning a wrong route **[VERIFIED]**.
- Local language: product name in Kannada; UI text is English only (Kannada UI is roadmap).

## 8. Proposed solution

MaleMitra is a closed-loop platform in which **people report, people verify, an administrator authorises, and software re-plans** — with an LLM agent assisting triage but never deciding.

### Objectives

1. Convert scattered citizen observations into **one verified record per hazard**.
2. Keep **humans in charge** of closures.
3. Make every commuter's route **reflect verified closures and weighted hazards** immediately.
4. Show decision-makers the **ripple effect** of a closure.
5. Provide an **auditable** record of every action (human and agent).

## 9. Problem → feature traceability

| Problem | Implemented feature | Code / evidence |
|---|---|---|
| Unstructured, duplicate reports | Typed geotagged reports; **merge within 10 m**; map to nearest road edge with ambiguity flag | `incident_service.create_report`; `test_report_merging.py` (10 tests) |
| Can't judge credibility | **Reputation × corroboration × photo × triage** weighting; max 0.9 until human-verified | `reputation_service.py`; `test_crowd_trust.py` (33) |
| Fake/mistaken reports closing roads | **Only admin** can authorise closure; field verification precedes it | `admin_authorize_restriction`; state gates tested |
| Commuters routed into hazards | **Risk-aware routing** (hazard penalties + BPR congestion) with Direct vs risk-aware vs alternative cards | `graph_service.py`, SS11 |
| Unknown side-effects of closures | **Ripple Engine** on 150 synthetic trips | `ripple_service.py`, SS07 |
| Slow, inconsistent triage | **Orchestrate agent** recommendation with evidence and confidence; admin approve/dismiss | `agent_tools_service.py`, `recommendation_service.py` |
| No accountability | **Audit trail** + **Agent Decision Timeline** | SS04, SS06 |
| Crews unavailable / unclear | Responder availability, team queue, atomic claim | `test_responder_assignment.py` (19) |
| Response lag | Server-sent events push updates; notification outbox (email/SMS webhook) | `events.py`, `notification_service.py` |
| Privacy of photos | EXIF/GPS stripped, validated JPEG/PNG, size cap | `upload_service.py` |

## 10. Core features

Detailed in [05_FEATURES_AND_USER_FLOWS.md](05_FEATURES_AND_USER_FLOWS.md). Summary: citizen reporting; risk-aware route comparison with directions and voice; control-room queue; field verification; road closure/reopen; Ripple Engine; benchmark harness; watsonx Orchestrate analyst; agent timeline and audit; role-based auth; optional live traffic.

## 11. User journeys

**Citizen (Pooja).** Opens MaleMitra → searches "Sony World Junction" → sees Direct 22 min vs MaleMitra detour 25 min with "incident penalty" and "ripple congestion" lines (SS11) → reports a flooded underpass with a photo → receives status updates as the incident moves through the workflow.

**Control-room admin.** Sees queue (SS03) → opens a report → reads confidence, duplicate count and the **agent's recommendation** → approves "request triage" → assigns Team Alpha or a free responder → after the responder's verification, authorises the closure → runs a ripple simulation → later authorises reopening.

**Responder (Inspector Ramesh).** Opens Field Tasks (SS09) → claims an incident from the team queue → records water depth (cm), impassable yes/no and a recommended action → later proposes clearance once pumped.

## 12. Example scenario (reproducible with seeded demo data)

1. Citizen reports a critical waterlogging at 12.9352, 77.6245 (Sony World Junction).
2. Admin reviews → assigns Team Alpha (seeded state already has this incident *assigned*).
3. Responder submits field verification: depth 55 cm, impassable.
4. Admin authorises closure: graph version increments (visible in the top bar, "Graph v8" in the screenshots).
5. Citizen searches Silk Board → Indiranagar: risk-aware route avoids the closed segment.
6. Ripple Engine shows added load on parallel corridors.
7. Clearance proposed → admin reopens → routes return to normal.

These are the steps in the in-app **Demo Guide** and `DEMO.md`.

## 13. Expected outcomes

- Fewer drivers routed through verified-closed roads (demonstrated in simulation).
- Fewer duplicate incidents for staff to process (merging exists; **magnitude requires measurement**).
- A complete, queryable record of who did what and when.

## 14. Measurable impact indicators

Primary (demonstrated in simulation): *share of modelled trips traversing a closed road* — **25.3 % → 0 %**, at a mean detour cost of **+14.2 s (+3.9 %)** (clean CLI run, seed 42). Further KPIs with measurement plans: [10_IMPACT_AND_SCALABILITY.md](10_IMPACT_AND_SCALABILITY.md).

> These figures come from a simulation on a 20-node model with synthetic trips, not field data.

## 15. Why it is practical

- Runs today: one container (+ optional PostgreSQL/OSRM); 242 automated tests pass.
- Works without paid services; every external dependency has a fallback.
- Role model and gates mirror how a control room actually works (report → triage → verify → authorise).
- Privacy and abuse controls are in place (see [09](09_SECURITY_PRIVACY_AND_RESPONSIBLE_AI.md)).

## 16. Why it is innovative

1. **Closed-loop flood response + routing** in a single deployable system.
2. **Trust-weighted crowdsourcing** that can influence routing *without* ever being able to close a road.
3. **Ripple Engine** for second-order closure impact.
4. **Governed agentic AI**: an Orchestrate agent whose only write is an approvable recommendation, constrained by workflow gates and fully logged.

## 17. Honest limits

Modelled graph is small (20 nodes / 56 edges); trips are synthetic; photos are not analysed; not load-tested; responder side is simulated; no real municipal integration. Full list: [11](11_LIMITATIONS_AND_ROADMAP.md).
