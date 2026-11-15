# MaleMitra (ಮಳೆ ಮಿತ್ರ) — IBM Bobathon: Build for Bengaluru 2026

**Track:** Smarter Streets, Better Living
**Repository:** <https://github.com/sakshit-allumolu/MaleMitra> (submission branch: `feature-demo`)
**Hosted demo:** <https://malemitra.onrender.com> (health endpoint returned 200 on 15 Nov 2026; confirm the final URL, Q10)
**Team:** [TEAM INPUT REQUIRED: names, roles, contact]

MaleMitra is a monsoon mobility and civic-response platform. Citizens report flooded roads, the control room triages and dispatches, responders verify on site, and only then does an administrator close the road. Every route re-plans around the closure. An IBM watsonx Orchestrate agent recommends the next step. A human approves every action.

## The four required items ("Built with IBM Bob" is the core requirement)

| # | Item | Where |
|---|---|---|
| 1 | **The problem:** who experiences it, what must improve | [`02`](../docs/02_PROBLEM_STATEMENT_AND_SOLUTION.md) |
| 2 | **The prototype:** working, built with Bob, agentic AI where useful | [`05`](../docs/05_FEATURES_AND_USER_FLOWS.md), [`06` run it](../docs/06_SETUP_AND_INSTALLATION.md), [`04` Part B Orchestrate](../docs/04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md) |
| 3 | **The Bob story:** short demo of how Bob was used throughout development | [`04` Part A](../docs/04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md), [video script segment 6](../docs/15_VIDEO_DEMO_SCRIPT.md) |
| 4 | **The impact:** one measurable outcome | [`10`](../docs/10_IMPACT_AND_SCALABILITY.md): 38 → 0 trips on a closed road in simulation |
| + | **Safety:** privacy and human review in the design | [`09`](../docs/09_SECURITY_PRIVACY_AND_RESPONSIBLE_AI.md) |

Full mapping, with evidence status: [`docs/00_PARTICIPATION_REQUIREMENTS.md`](../docs/00_PARTICIPATION_REQUIREMENTS.md).

## Start here (10-minute judge path)

| Step | Read | Time |
|---|---|---|
| 1 | [`EXECUTIVE_SUMMARY.md`](EXECUTIVE_SUMMARY.md) | 3 min |
| 2 | [Participation requirements](../docs/00_PARTICIPATION_REQUIREMENTS.md): the four items and the Bob story | 3 min |
| 3 | [`FINAL_REVIEW_REPORT.md`](FINAL_REVIEW_REPORT.md): honest status, gaps and what is still pending | 3 min |
| 4 | [IBM Bob and watsonx Orchestrate usage](../docs/04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md) | 4 min |
| 5 | [Judging criteria alignment](../docs/13_JUDGING_CRITERIA_ALIGNMENT.md) | optional |

## What is in this folder

| Item | Purpose |
|---|---|
| [`EXECUTIVE_SUMMARY.md`](EXECUTIVE_SUMMARY.md) | One-page summary and 30-second pitch |
| [`IBM_Bobathon_Presentation.pptx`](IBM_Bobathon_Presentation.pptx) | Presentation deck |
| [`presentation_source/`](presentation_source/) | Editable Markdown source of the deck, and pointers to each canonical document |
| [`demo/VIDEO_DEMO_SCRIPT.md`](demo/VIDEO_DEMO_SCRIPT.md) | Script for the demo video (recorded by the team) |
| [`demo/VIDEO_RECORDING_CHECKLIST.md`](demo/VIDEO_RECORDING_CHECKLIST.md) | Pre-recording and post-recording checks |
| [`assets/screenshots/`](assets/screenshots/) | Real screenshots of the running app |
| [`assets/diagrams/`](assets/diagrams/) | PNG exports of the Mermaid architecture diagrams |
| [`FINAL_SUBMISSION_CHECKLIST.md`](FINAL_SUBMISSION_CHECKLIST.md) | Checklist with open items |
| [`FINAL_REVIEW_REPORT.md`](FINAL_REVIEW_REPORT.md) | Final quality audit and readiness assessment |

## Canonical documents (in `docs/`)

The full documents live in [`../docs/`](../docs/). They are not duplicated here.

| # | Document |
|---|---|
| Audit | [`PROJECT_AUDIT.md`](../docs/PROJECT_AUDIT.md) |
| 00 | [Participation requirements](../docs/00_PARTICIPATION_REQUIREMENTS.md) |
| 01 | [Executive summary](../docs/01_EXECUTIVE_SUMMARY.md) |
| 02 | [Problem statement and solution](../docs/02_PROBLEM_STATEMENT_AND_SOLUTION.md) |
| 03 | [Technical architecture](../docs/03_TECHNICAL_ARCHITECTURE.md) |
| 04 | [IBM Bob and watsonx Orchestrate](../docs/04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md) |
| 05 | [Features and user flows](../docs/05_FEATURES_AND_USER_FLOWS.md) |
| 06 | [Setup and installation](../docs/06_SETUP_AND_INSTALLATION.md) |
| 07 | [API documentation](../docs/07_API_DOCUMENTATION.md) |
| 08 | [Testing and validation](../docs/08_TESTING_AND_VALIDATION.md) |
| 09 | [Security, privacy and responsible AI](../docs/09_SECURITY_PRIVACY_AND_RESPONSIBLE_AI.md) |
| 10 | [Impact and scalability](../docs/10_IMPACT_AND_SCALABILITY.md) |
| 11 | [Limitations and roadmap](../docs/11_LIMITATIONS_AND_ROADMAP.md) |
| 12 | [Repository and licence](../docs/12_REPOSITORY_AND_LICENSE.md) |
| 13 | [Judging criteria alignment](../docs/13_JUDGING_CRITERIA_ALIGNMENT.md) |
| 14 | [Final submission checklist](../docs/14_FINAL_SUBMISSION_CHECKLIST.md) |
| 15 | [Video demo script](../docs/15_VIDEO_DEMO_SCRIPT.md) |
| — | [Screenshot requirements](../docs/SCREENSHOT_REQUIREMENTS.md) |
| — | [Information required from the team](../docs/INFORMATION_REQUIRED_FROM_TEAM.md) |

## Run it in five commands

Full guide: [`06_SETUP_AND_INSTALLATION.md`](../docs/06_SETUP_AND_INSTALLATION.md).

```bash
git clone https://github.com/sakshit-allumolu/MaleMitra.git && cd MaleMitra
git checkout feature-demo
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements-dev.txt
pytest backend/tests          # 242 passed on 15 Nov 2026
```

To start the app and see the demo accounts, follow section 3 of the setup guide.

## Status at a glance (15 Nov 2026)

| Area | Status |
|---|---|
| Working prototype, backend tests, frontend build | Verified: 242 passed, build passes |
| Benchmark | Verified: 38 of 150 simulated trips cross the closed road when it is ignored; MaleMitra sends 0 (simulation, not field data) |
| IBM Bob | Partly evidenced (95 local edit notes). Wider use is team-stated. **Screenshots pending.** |
| IBM watsonx Orchestrate | Code, 37 tests, live token and chat verified. End-to-end loop is team-stated. **Screenshots pending.** |
| Fresh Code Rule, deadline | **Needs your confirmation** with the organisers |
| MIT `LICENSE` file | **Missing**, needs contributor agreement |
| CI lint | 1 known error (`Set` import), fix awaiting approval |

Details and every open item: [`FINAL_REVIEW_REPORT.md`](FINAL_REVIEW_REPORT.md).
