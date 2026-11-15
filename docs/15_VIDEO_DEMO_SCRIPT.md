# 15 · Video Demonstration Script

You record the video yourself. This script is a starting point. Edit the wording so it sounds like you.

**Length.** No portal limit has been confirmed (Q16). This script targets **4 minutes 50 seconds**, inside a 3–5 minute window. If the portal sets a shorter limit, shorten segments 5 and 8 first. Do not cut the Bob story (segment 6): it is the core participation requirement.

**Honesty rules for the voice-over.** These keep the video consistent with the documents.
- Say "simulation" whenever you give the 38 → 0 numbers. Do not call them measured field results.
- Say the Orchestrate agent **recommends** and a human **approves**. Never say it closes roads.
- Say "one watsonx Orchestrate agent". The other three modules are rule-based Python.
- Describe Bob's role only as far as your evidence supports. Segment 6 has bracketed parts for you to complete.

Companion files: [recording checklist](../submission/demo/VIDEO_RECORDING_CHECKLIST.md) · [screenshots needed](SCREENSHOT_REQUIREMENTS.md) · [judging alignment](13_JUDGING_CRITERIA_ALIGNMENT.md)

---

## Structure at a glance

| # | Segment | Time | Cumulative |
|---|---|---|---|
| 1 | Opening | 0:15 | 0:15 |
| 2 | The problem | 0:25 | 0:40 |
| 3 | The solution | 0:20 | 1:00 |
| 4 | Live demo: citizen, admin, responder | 1:05 | 2:05 |
| 5 | Ripple Engine and measurable outcome | 0:20 | 2:25 |
| 6 | **The Bob story** | **1:15** | 3:40 |
| 7 | watsonx Orchestrate demo | 0:45 | 4:25 |
| 8 | Impact and honest limits | 0:15 | 4:40 |
| 9 | Closing | 0:10 | 4:50 |

The four required items are covered in this order: problem (2), prototype (3, 4, 7), **Bob story (6)**, impact (5, 8). Privacy and human review are said in segments 3 and 7. See [00 Participation requirements](00_PARTICIPATION_REQUIREMENTS.md).

Total 4:50.

---

## Before you record

1. Start the app with demo mode on and a clean database.
2. Check the Orchestrate panel shows **Connected**, and that the tool callback URL is reachable. The tunnel was offline during the audit.
3. Run one incident through the agent yourself first, so you know it works on the day.
4. Hide or crop the tunnel URL, personal emails and any API key.
5. Use a browser window at 1280×720 or larger, zoom 100 %.

---

## Segment 1 · Opening (0:15)

**Show on screen:** Title slide, then the login page (SS01).

**Say:**
> "Hi, I'm **[TEAM INPUT REQUIRED: name]**, and this is **MaleMitra**. *Male* is Kannada for rain, and *Mitra* means friend. It's a monsoon mobility and civic-response platform for Bengaluru, built for the *Smarter Streets, Better Living* track, with IBM Bob and IBM watsonx Orchestrate."

**Audience takeaway:** Project name, track, and that both IBM products are involved.

---

## Segment 2 · The problem (0:25)

**Show on screen:** A slide with three icons or labels: *Commuters*, *Control room*, *Field crews*. No invented statistics. You may show the Bengaluru rainfall context from doc 01 with its source.

**Say:**
> "When heavy rain hits Bengaluru, a low-lying road or underpass can become dangerous within minutes. The commuter who sees the water, the control room that can act, and the driver who is about to enter that road are usually on different channels. So drivers still get routed into flooded roads, and crews work without a shared picture. Bengaluru's monsoon runs from June to September, and the city has lost most of its lakes to built-up land, which is why this keeps happening."

**Audience takeaway:** Three groups, one broken information loop, and why it matters in Bengaluru.

> Check the lake and built-up-land facts against [01](01_EXECUTIVE_SUMMARY.md) before saying them. They come from Wikipedia pages, not primary sources.

---

## Segment 3 · The solution (0:20)

**Show on screen:** Architecture diagram `submission/assets/diagrams/01_high_level_architecture.png`, then the one-loop line from doc 01.

**Say:**
> "MaleMitra closes that loop. A citizen reports a hazard. The control room triages and dispatches a team. A responder verifies on site. Only then does an administrator close the road. The moment it closes, every route re-plans around it. And an IBM watsonx Orchestrate agent helps the control room decide what to do next, but a human always makes the final call."

**Audience takeaway:** One closed loop, human-gated, with an AI advisor.

---

## Segment 4 · Live demo (1:05)

Rehearse this segment. Use the one-click demo accounts on the login page.

### 4a. Citizen (0:20)
**Show:** Sign in as **Citizen (Pooja)** (SS02). Open **Find Routes**, pick two points in Koramangala and Indiranagar, compare the route cards (SS11). Click the map and submit a hazard report.

**Say:**
> "As a citizen I can compare a direct route against MaleMitra's risk-aware route. Here it explains why it picks a different road. I'll report a flooded underpass by clicking the map. The system snaps it to the nearest road segment and merges it with any report within ten metres."

### 4b. Control room (0:20)
**Show:** Sign out. Sign in as **Control Room Admin** (SS03). Open the incident, click **Review**, assign **Team Alpha**.

**Say:**
> "The control room sees the queue with confidence and duplicate counts. I review the report and dispatch Team Alpha. A single unverified report can only add a small routing penalty. It cannot close a road."

### 4c. Responder (0:25)
**Show:** Sign in as **Inspector Ramesh**. **Team queue** → **Claim** → record depth and *impassable* → submit (SS09). Switch back to admin and click the authorise-block action.

**Say:**
> "The responder claims the task, measures the water depth, and marks the road impassable. Only now can the administrator authorise the closure. Every step is role-gated and written to an audit trail."

**Audience takeaway:** A working, role-based loop from report to verified closure.

> Reality check: the responder screen in SS09 was an empty state. If you do the loop live, your queue will be populated.

---

## Segment 5 · Ripple Engine and measurable outcome (0:20)

**Show on screen:** After the closure, open the Ripple view (SS07). Then a terminal running `python backend/eval_benchmark.py`, with the three numbers highlighted.

**Say:**
> "Once the road is closed, the Ripple Engine re-routes 150 simulated trips and shows where traffic piles up. In our benchmark on a 20-node model of five Bengaluru neighbourhoods, a router that ignores the closure sends 38 trips, about 25 percent, over the closed road. MaleMitra sends none, for about 14 extra seconds per trip on average. This is a simulation with synthetic trips, not field data, and anyone can reproduce it with one command."

**Audience takeaway:** A measurable, reproducible result, honestly labelled.

> Use only the **command-line** figures (38 → 0, +14.2 s, +3.9 %). The Benchmark page in the app shows different time figures because it uses live graph state. Do not read those aloud.
> After the demo, restore tracked files: `git checkout -- backend/app/data/benchmark_results.json backend/app/data/benchmark_results.csv`.

---

## Segment 6 · The Bob story (1:15)

**This is the core participation requirement. Give it real, specific moments from your own Bob history.** A judge should leave knowing what Bob did, how you steered and checked it, and that it ran through the whole build.

Three beats, about 25 seconds each. Fill the brackets only with things that actually happened.

### 6a. Start (0:25)
**Show on screen:** BOB-1, your first Bob task with its date, then the same idea in the code (for example the schemas or the state machine).

**Say:**
> "We built MaleMitra with IBM Bob from the first day. We started by asking Bob to **[TEAM INPUT REQUIRED: real first task and what came back]**. **[TEAM INPUT REQUIRED: one sentence on how Bob shaped the architecture or the incident workflow.]**"

### 6b. Build and fix (0:25)
**Show on screen:** BOB-2 (Bob fixing a failing test) and BOB-3 (Bob applying a diff to a real file). If you can, a live 15-second screen recording of Bob making one small change.

**Say:**
> "Bob works in small, reviewable diffs. When **[TEAM INPUT REQUIRED: a real failure]** broke, Bob read the failing test, proposed a focused change, and we re-ran the suite. Here it is editing **[a real file, for example `agent_service.py`]**. In this repository you can see 95 recorded Bob edits across the map, the routing module and the responder workspace."

### 6c. Review and trust (0:25)
**Show on screen:** terminal with `git notes --ref=bob list | wc -l`, then `pytest backend/tests` ending in `242 passed`. If you have it, BOB-4: Bob history from the earlier system showing dates.

**Say:**
> "We didn't accept Bob's output blindly. **[TEAM INPUT REQUIRED: who reviewed the diffs, and how.]** Every change was checked by our automated suite: 242 tests, all passing, plus a benchmark that gives the same answer on every run. **[Optional, only if you can show it: Bob was also used on an earlier machine for our earlier commits; here is that history.]**"

**Audience takeaway:** Bob was used throughout development, its changes were reviewed, and the result is tested.

> Do not claim more than your evidence shows. The 95 notes cover the evening of 15 Nov only. Earlier-machine use and "all commits on every branch" are your statements. Show BOB-4 or leave the claim out.
> Do not show any personal or confidential data that you sent to Bob (rule 8.6).

---

## Segment 7 · watsonx Orchestrate demo (0:45)

**Show on screen, in this order:**
1. Orchestrate console: agent page and the 8 tools (ORCH-1, ORCH-2). Crop out anything secret.
2. MaleMitra Admin → **watsonx Orchestrate Agent** tab showing **Connected** (ORCH-3).
3. Open an incident → click **Ask agent** (or **Ask the agent** in the Orchestrate panel). Show the reply and the recommendation card (ORCH-4).
4. **Agent Decision Timeline** with `LLM agent` rows and `tool:*` actions (ORCH-5, SS04).
5. Click **Approve & dispatch team** and show the status change and audit row (ORCH-6).

**Say:**
> "Here's the IBM watsonx Orchestrate agent. It has eight tools that call MaleMitra's own API. When I ask it to analyse this incident, it decides which tools to call: first the incident context, then the available responders, and for a verified incident, a ripple what-if. It ends with one structured recommendation. The tools can only read, simulate, or *submit a recommendation*. The agent cannot change an incident's status or close a road. If it proposes something invalid for the current stage, the system rejects it and the agent has to re-plan. The recommendation waits for me. When I approve it, the normal workflow action runs with the same checks and the same audit trail."

**If asked why this is agentic and not a chatbot, say:**
> "It chooses tools, acts on real data, and writes into the system of record. It is bounded by schema, state gates and human approval."

**Audience takeaway:** Real tool use, real guardrails, human in control.

> **Critical:** this segment depends on your live evidence. If the tool URL is unreachable on the day, the agent will not be able to call tools. Test it first. If it fails, fall back to the Timeline from an earlier real run, and say so on camera.
> Do not say the agent runs autonomously, runs continuously or coordinates with other agents. It does none of these.

---

## Segment 8 · Impact and honest limits (0:15)

**Show on screen:** The KPI table from doc 10 (K1 and K2), then a short "Limits" slide.

**Say:**
> "Our headline measures are closed-road exposure and detour cost. Both are demonstrated in simulation today. Real-world time savings still need a pilot, so we haven't claimed any. The model covers five neighbourhoods, the agent's accuracy hasn't been formally evaluated, and the next steps are rainfall data, more agents, and a Kannada interface."

**Audience takeaway:** Clear KPIs, an honest boundary between simulation and reality, and a credible roadmap.

---

## Segment 9 · Closing (0:10)

**Show on screen:** Closing slide with the repository URL and the hosted demo URL **[TEAM INPUT REQUIRED: final URLs, Q10]**.

**Say:**
> "MaleMitra gives Bengaluru a shared picture during the monsoon: citizens, control room and responders on one loop, with an IBM watsonx Orchestrate agent that advises and a human who decides. It was built with IBM Bob, it runs today, and it's ready for a real pilot. Thank you."

**Audience takeaway:** Why the project deserves recognition.

---

## Optional shorter cut (about 3 minutes)

Keep segments 1, 3, 4 (one pass, no sign-outs between roles, use the walkthrough modal), 7 and 9. Drop 5 and 8. Fold the Bob story into one sentence.

## Backup plan

| Problem on the day | What to do |
|---|---|
| Orchestrate tool callbacks fail | Show the console, the tests and an earlier real timeline. Say clearly it is a previous run. |
| Hosted site sleeping | Use the local run and show the hosted `/api/v1/health` separately. |
| Map tiles blank | Check the internet connection. Tiles come from OpenStreetMap. |
| OSRM offline | Routes show "Graph fallback (OSRM unavailable)". Mention it as designed degradation. |
| Benchmark numbers differ in app | Use the CLI numbers. |
