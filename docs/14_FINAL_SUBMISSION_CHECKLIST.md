# 14 · Final Submission Checklist

Status keys used on every line:

| Key | Meaning |
|---|---|
| ✅ **Done** | Completed and checked during this audit (15 Nov 2026) |
| ⏳ **Pending** | Work still to do, usually by you |
| ❓ **Confirm** | Needs your confirmation or a team decision |
| 🚨 **CRITICAL GAP** | Could cause disqualification or lose a mandatory requirement |

Open questions use the ids in [`INFORMATION_REQUIRED_FROM_TEAM.md`](INFORMATION_REQUIRED_FROM_TEAM.md). Nothing in this list was committed, pushed or submitted for you.

---

## 0. How to upload (portal: one `.zip` or `.ppt`, max 100 MB)

The zip has one folder per Phase 1 deliverable: 01 Problem statement and solution, 02 Working solution built with IBM Bob, 03 Source code, 04 Presentation deck, 05 Video demonstration.

- [ ] ⏳ Paste your video link into `submission/demo/VIDEO_LINK.txt`.
- [ ] ⏳ Fill the placeholders: deck slides 1, 4, 5, 10, 15 and every `[TEAM INPUT REQUIRED]`.
- [ ] ⏳ Commit `docs/` and `submission/` (the source folder in the zip comes from git).
- [ ] ⏳ Build: `/tmp/pptx_env/bin/python submission/build_submission_zip.py`. It refuses while placeholders or secrets remain.
- [ ] ⏳ Unzip it somewhere else and check the deck opens.
- [ ] ⏳ Upload `submission/MaleMitra_IBM_Bobathon_Submission.zip`, theme **Smarter Streets Better Living**, then **Save Answer**.

## 0a. The four required submission items (core: "Built with IBM Bob")

Map: [00 Participation requirements](00_PARTICIPATION_REQUIREMENTS.md).

- [x] ✅ **1. The problem:** who experiences it and what must improve. [02](02_PROBLEM_STATEMENT_AND_SOLUTION.md)
- [x] ✅ **2. The prototype:** working, role-based, with an agentic AI component. 242 tests pass. [05](05_FEATURES_AND_USER_FLOWS.md), [08](08_TESTING_AND_VALIDATION.md)
- [ ] 🚨 ⏳ **3. The Bob story:** a short demo of how Bob was used **throughout** development. Script ready (video segment 6). Needs your real examples and BOB-1…5. Only 95 edit notes from one evening are proven in the repo.
- [x] ✅ **4. The impact:** one measurable outcome, 38 → 0 trips on the closed road (+14.2 s, +3.9 %), labelled simulation. [10](10_IMPACT_AND_SCALABILITY.md)
- [x] ✅ **Safety projects:** privacy and human review designed in. [09](09_SECURITY_PRIVACY_AND_RESPONSIBLE_AI.md). ⚠️ Known gap: `evidence_list` identity exposure.

## 0. Critical items first

- [ ] 🚨 **Deadline and portal.** The TechGig page shows the Hackathon Period ending 14 Nov 2026 23:59 IST. You told us it was extended to 16 Nov. Confirm in writing and check that the portal is accepting uploads *now*. (Q1)
- [ ] 🚨 **Fresh Code Rule (rule 7.1.2).** All 32 commits on `feature-demo` are dated 15 Nov, after the published period end. `main` holds 6 commits from 10–13 Nov with unrelated history. Prepare a short written statement of what was written when. (Q2)
- [ ] 🚨 **watsonx Orchestrate end-to-end evidence.** The code, tests, live token exchange and live chat are verified. The full tool-callback run is user-stated, with no screenshots in the repo. Capture ORCH-1…7. (Q8)
- [ ] 🚨 **IBM Bob evidence and Bob story demo (the core requirement).** Only 7 local git notes (95 edits, 15 Nov). Earlier-machine use and "all commits made with Bob" are user-stated. Export task history and capture BOB-1…5. (Q3, Q4)
- [ ] 🚨 **MIT licence.** There is no `LICENSE` file. Event terms refer to the MIT licence. Needs agreement from all contributors. (Q12)
- [ ] 🚨 **Employer approval and AI-tool data (rules 2.4, 8.6).** Three commits carry an `@target.com` email. (Q19)

---

## 1. Project documentation

- [x] ✅ Project audit: [`PROJECT_AUDIT.md`](PROJECT_AUDIT.md)
- [x] ✅ Executive summary: [01](01_EXECUTIVE_SUMMARY.md)
- [x] ✅ Problem statement and solution: [02](02_PROBLEM_STATEMENT_AND_SOLUTION.md)
- [x] ✅ Technical architecture with six Mermaid diagrams: [03](03_TECHNICAL_ARCHITECTURE.md)
- [x] ✅ IBM Bob and watsonx Orchestrate: [04](04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md)
- [x] ✅ Features and user flows: [05](05_FEATURES_AND_USER_FLOWS.md)
- [x] ✅ Setup guide: [06](06_SETUP_AND_INSTALLATION.md)
- [x] ✅ API documentation (53 operations): [07](07_API_DOCUMENTATION.md)
- [x] ✅ Testing and validation: [08](08_TESTING_AND_VALIDATION.md)
- [x] ✅ Security, privacy and responsible AI: [09](09_SECURITY_PRIVACY_AND_RESPONSIBLE_AI.md)
- [x] ✅ Impact and scalability: [10](10_IMPACT_AND_SCALABILITY.md)
- [x] ✅ Limitations and roadmap: [11](11_LIMITATIONS_AND_ROADMAP.md)
- [x] ✅ Repository and licence: [12](12_REPOSITORY_AND_LICENSE.md)
- [x] ✅ Judging alignment: [13](13_JUDGING_CRITERIA_ALIGNMENT.md)
- [x] ✅ Video script, with the Bob story as its longest segment (1:15): [15](15_VIDEO_DEMO_SCRIPT.md)
- [ ] ⏳ Read every document once and replace each `[TEAM INPUT REQUIRED]` marker.
- [ ] ❓ Answer the questions in [`INFORMATION_REQUIRED_FROM_TEAM.md`](INFORMATION_REQUIRED_FROM_TEAM.md) (Q1–Q21).

## 2. Problem statement

- [x] ✅ Real-world problem, affected people and Bengaluru context written, with source URLs.
- [x] ✅ No invented statistics (casualty, cost and response-time figures are deliberately not claimed).
- [ ] ⏳ Open the India Today article cited in doc 01 and verify it before quoting. It was **not** opened during the audit.
- [ ] ❓ Add a primary source (BBMP, BTP, KSNDMC or KSDMA) if you want a harder local statistic.
- [x] ✅ Track chosen: **Smarter Streets, Better Living**.
- [ ] ❓ Student category? (Q7)

## 3. Solution description

- [x] ✅ Solution objectives, features, user journeys and scenarios documented.
- [x] ✅ Every claimed feature traced to code (see [05](05_FEATURES_AND_USER_FLOWS.md)).
- [x] ✅ Implemented, limited and proposed work kept separate.
- [ ] ❓ Check that [01](01_EXECUTIVE_SUMMARY.md) and the deck read the way you want to present the project.

## 4. IBM Bob evidence

- [x] ✅ Verified: 7 git notes, 95 edits, files touched listed in [04 §A.1–A.2](04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md).
- [ ] ⏳ 📸 BOB-1 initial scaffolding prompt with date.
- [ ] ⏳ 📸 BOB-2 Bob fixing a failing test.
- [ ] ⏳ 📸 BOB-3 Bob applying a diff to a real file.
- [ ] ⏳ 📸 BOB-4 Bob history from the **earlier system** showing dates.
- [ ] ⏳ 📸 BOB-5 Terminal: `git notes --ref=bob list | wc -l`.
- [ ] ❓ Publish the notes: `git push origin refs/notes/bob` (not done).
- [ ] ❓ Write who reviewed Bob's changes and how (placeholder in doc 04 §A.3).
- [ ] ❓ Confirm each README §8 claim about Bob (Q5).

## 5. watsonx Orchestrate evidence

- [x] ✅ Agent YAML, OpenAPI tool spec and `orchestrate/README.md` exist.
- [x] ✅ 37 Orchestrate tests pass; guardrail smoke test run (wrong-state action → 422, status unchanged).
- [x] ✅ Live IAM token exchange and live chat call worked on 15 Nov 2026.
- [ ] 🚨 ⏳ 📸 ORCH-1 Orchestrate console: agent page.
- [ ] 🚨 ⏳ 📸 ORCH-2 Orchestrate console: the 8 imported tools.
- [ ] 🚨 ⏳ 📸 ORCH-3 Admin panel showing **Connected** and tool-call counts.
- [ ] 🚨 ⏳ 📸 ORCH-4 **Ask the agent** result and recommendation card.
- [ ] 🚨 ⏳ 📸 ORCH-5 Agent Decision Timeline rows tagged `LLM agent`.
- [ ] 🚨 ⏳ 📸 ORCH-6 Admin approving the recommendation.
- [ ] ⏳ 📸 ORCH-7 Orchestrate run trace (optional).
- [ ] ⏳ Make sure the tool callback URL (`PUBLIC_BASE_URL`) is reachable *before* recording. The tunnel was offline at audit time.
- [ ] ❓ Confirm the model really running in the instance (YAML says `watsonx/ibm/granite-3-8b-instruct`). (Q20)
- [ ] ⏳ **Crop or blur the tunnel URL** in any screenshot you publish.

## 6. Working prototype

- [x] ✅ Backend starts in a fresh Python 3.12 venv; `/api/v1/health` healthy; `/docs` 200.
- [x] ✅ `pytest backend/tests`: 242 passed.
- [x] ✅ `npm run build` passes.
- [x] ✅ Deterministic benchmark: 38 of 150 trips → 0.
- [x] ✅ Hosted instance `https://malemitra.onrender.com/api/v1/health` returned 200 on 15 Nov.
- [ ] ❓ Which URL do judges use, and is it the latest `feature-demo`? Does it have Orchestrate configured? (Q10)
- [ ] ⏳ Check the hosted instance again right before submitting (free hosts can sleep).
- [ ] ⏳ Docker Compose and PostgreSQL were **not run**. Run them once, or say so plainly.

## 7. GitHub repository

- [ ] ❓ Repo public, or judge access arranged (rule 6.2). (Q13)
- [ ] ❓ Submission branch decided; default branch aligned (`main` is the older prototype). (Q11)
- [ ] ⏳ Commit the new `docs/` and `submission/` folders. **Nothing has been committed.**
- [ ] ❓ Approve the small code and doc fixes (Q17): `Set` import at `agent_service.py:206`, stale README / `DEMO.md` / YAML lines.
- [ ] ⏳ After the fix, confirm the GitHub Actions run is green. (Q21)
- [ ] ⏳ Add `.env.example` review: confirm it holds placeholders only (secret scan found none in the tree or in 50 revisions).
- [ ] ❓ Credit all contributors (rule 6.6), including `venu019`. (Q6)

## 8. Setup instructions

- [x] ✅ Exact commands in [06](06_SETUP_AND_INSTALLATION.md); backend path verified in a fresh venv.
- [ ] ⏳ Do one clean `npm ci && npm run build` from a fresh clone and note the result.
- [ ] ⏳ Check that the demo logins work on the hosted instance.

## 9. Presentation

- [x] ✅ `submission/IBM_Bobathon_Presentation.pptx` generated, with editable Markdown source.
- [ ] ⏳ Open the PPTX in PowerPoint or Keynote and check the layout.
- [ ] ⏳ Insert your ORCH and BOB screenshots into the marked placeholder boxes.
- [ ] ❓ Fill in team name, members and contact on the title slide. (Q6, Q18)
- [ ] ⏳ Check the portal's file-format and size limits. (Q16)

## 10. Video demonstration (you record it)

- [x] ✅ Script: [15](15_VIDEO_DEMO_SCRIPT.md) · recording checklist: [`submission/demo/VIDEO_RECORDING_CHECKLIST.md`](../submission/demo/VIDEO_RECORDING_CHECKLIST.md)
- [ ] ⏳ Rehearse once with a timer.
- [ ] ⏳ Reset the demo database so the queue is clean.
- [ ] ⏳ Record, then check there are no secrets, tunnel hosts or personal emails on screen.
- [ ] ❓ Confirm the portal's length and size limit. The script assumes 3–5 minutes. (Q16)

## 11. Testing

- [x] ✅ Results in [08](08_TESTING_AND_VALIDATION.md). Test cases are marked passed only when they ran.
- [ ] ⏳ Not tested: frontend (no tests exist), accessibility, load, PostgreSQL suite, Docker, live Orchestrate tool loop.
- [ ] ⏳ After running `pytest` or the benchmark, restore the tracked result files:
  `git checkout -- backend/app/data/benchmark_results.json backend/app/data/benchmark_results.csv`

## 12. Security and privacy

- [x] ✅ Documented in [09](09_SECURITY_PRIVACY_AND_RESPONSIBLE_AI.md), implemented and recommended safeguards separated.
- [x] ✅ No secrets in the working tree or in 50 git revisions (checked 15 Nov).
- [ ] ❓ Fix or consciously accept the `evidence_list` identity exposure (KI-4).
- [ ] ❓ Confirm `ALLOW_LEGACY_TOKENS=false` and `EXPOSE_RESET_TOKEN=false` on the live host. (Q20)
- [ ] ⏳ Confirm no personal or confidential data was sent to Bob or any AI tool. (Q19)
- [ ] ⏳ Re-scan for secrets just before you push.

## 13. Licensing

- [ ] 🚨 ❓ Add `LICENSE` (MIT) after all contributors agree. (Q12)
- [x] ✅ Dependency licences listed in [12](12_REPOSITORY_AND_LICENSE.md). Note: psycopg is LGPL-3.0-only and certifi is MPL-2.0.
- [ ] ❓ Legal view on LGPL/MPL dependencies under an MIT project. This is not legal advice.
- [ ] ❓ Provenance of the 20-node graph and 150 synthetic trips. (Q21)
- [x] ✅ OpenStreetMap attribution present in the map.
- [ ] ❓ Copyright holder names for the LICENSE line.

## 14. Team information

- [ ] ❓ Names, roles, team size (1–5) and representative. (Q6)
- [ ] ❓ Eligibility: Bengaluru residency, 18+, not an IBM employee, employer approval. (Q6, Q19)
- [ ] ❓ Student category claim, with proof. (Q7)
- [ ] ❓ Any user feedback, pilot or partnership. We assumed **none** and claim none. (Q15)

## 15. Final submission verification

- [ ] ⏳ Click every link in `submission/README.md` and `docs/`.
- [ ] ⏳ Check that numbers match everywhere: 242 tests, 53 operations, 38 → 0, +14.2 s / +3.9 %.
- [ ] ⏳ Check that no document says the agent can close a road. It cannot.
- [ ] ⏳ Check that no document calls the three rule-based modules "LLM agents".
- [ ] ⏳ Read [`submission/FINAL_REVIEW_REPORT.md`](../submission/FINAL_REVIEW_REPORT.md) one last time.
- [ ] ⏳ Upload everything the portal asks for and keep a copy of the confirmation.
- [ ] ⏳ After upload, open the submitted links in a private browser window.
