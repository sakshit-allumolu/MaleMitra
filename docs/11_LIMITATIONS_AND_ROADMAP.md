# 11 · Limitations and Roadmap

Everything under "Implemented" in the rest of the documentation is real; this document lists what it does **not** do, what is broken, and what a realistic next step is. Fixes that touch application code are **proposals** — none were applied during the documentation work (tracked as Q17 in [`INFORMATION_REQUIRED_FROM_TEAM.md`](INFORMATION_REQUIRED_FROM_TEAM.md)).

## 1. Known issues (verified 15 Nov 2026)

| ID | Issue | Evidence | Severity | Proposed fix (not applied) |
|---|---|---|---|---|
| KI-1 | **CI lint fails:** `F821 Undefined name 'Set'` | `ruff check backend --select E9,F` → `agent_service.py:206` | High for CI/judges who look at the badge | Add `Set` to the `typing` import, or use `set[...]` |
| KI-2 | **Benchmark artefacts are inconsistent.** Committed `benchmark_results.json` shows +289.6 %; CLI gives +3.9 %; in-app page depends on graph state | §2 of [08](08_TESTING_AND_VALIDATION.md) | High (a judge may quote the wrong number) | Run the in-app benchmark on a clean graph copy and regenerate the committed file; or remove the JSON/CSV from version control |
| KI-3 | **Running tests/benchmark rewrites tracked files** (`benchmark_results.json/.csv`) | `git status` after `pytest` | Medium | Write results to an ignored path or a temp dir during tests |
| KI-4 | **Other citizens' names/ids visible in `evidence_list`** via the API | [09 §4.1](09_SECURITY_PRIVACY_AND_RESPONSIBLE_AI.md) | Medium (privacy) | Mask for citizen callers + regression test |
| KI-5 | **Docs contradict each other on Orchestrate verification:** `DEMO.md:59` says "not verified"; `orchestrate/malemitra_incident_agent.yaml` header says "UNVERIFIED"; `README.md:83`/`orchestrate/README.md:22` say verified | grep | Medium (credibility) | Update the stale lines after the team confirms the end-to-end evidence |
| KI-6 | **README claims that do not match the repo:** "130+ tests" (actual 242; DEMO.md says 234); `backend/e2e_smoke.py` ("59 checks") does not exist but is referenced by README and CI; README says Tailwind but `package.json` has none | grep / `ls` | Medium | Correct the README; add or remove the smoke script |
| KI-7 | **Default branch is `main`** (an older prototype with unrelated history); the submission code is on `feature-demo` | `git log` | High for reproducibility | Decide which branch is the submission; merge or make it default |
| KI-8 | **No LICENSE file**; hackathon terms say MIT | `ls` | High (compliance) | Team decision; see [12](12_REPOSITORY_AND_LICENSE.md) |
| KI-9 | **Orchestrate tool callbacks need a public URL**; the team's tunnel host was unreachable at audit time and changes on restart | `/agents/status`, curl | High for live demo | Use the IBM Code Engine deployment script for a stable URL; verify before recording |
| KI-10 | Frontend bundle is 586 kB (single chunk), build warns | `npm run build` | Low | Code-splitting |
| KI-11 | `render.yaml` + hosted instance run `DEMO_MODE=true` (demo accounts, public password) | `render.yaml` | Medium | Keep for judging, but verify `ALLOW_LEGACY_TOKENS=false` and `EXPOSE_RESET_TOKEN=false` on the live host |
| KI-12 | `/simulations/{run_id}/impact` ignores `run_id` and always runs seed 42 | `simulations.py:55-59` | Low | Persist runs and look up by id, or remove the parameter |
| KI-13 | `acceptance` test IDs are non-contiguous (T03, T07, T10, T12–T14 missing) | test names | Cosmetic | Renumber or note |

## 2. Limitations by area

### Technical
- **Tiny modelled network:** 20 nodes / 56 edges for five localities; hazard and ripple results do not generalise beyond them. City-wide routing depends on OSRM.
- **Synthetic mobility:** 150 trips with seed 42. No origin–destination survey data.
- **Per-process graph in memory** synchronised through a DB epoch; closures reach other workers on their next request or SSE tick (≈ 2.5 s), not instantly.
- **SQLite is single-host**; PostgreSQL is a single node in the shipped Compose file.
- **No metrics/alerting** (no Prometheus, no error tracker).
- **Not load-tested; not penetration-tested; no dependency vulnerability scan.**

### Data
- No real BBMP/BTP/KSNDMC feeds, no rainfall or sensor ingestion, no historic flood layer.
- Crowd reports come only from app users; coverage bias is likely and unmeasured.
- Photos are stored but **not analysed** and not virus-scanned; they are viewable by anyone holding the random id.

### AI reliability
- Only **one** LLM agent; reasoning quality is **unevaluated** (no labelled set, no accuracy/precision figure).
- Citizen free text reaches the LLM without sanitisation (prompt-injection exposure, mitigated only by the recommend-only design and human approval).
- The model name (`granite-3-8b-instruct`) comes from the agent YAML; the model actually running in the team's instance is unconfirmed [TEAM INPUT REQUIRED].
- The agent is invoked on admin request; it is **not** autonomous or continuous, and there is no agent-to-agent coordination.

### External dependencies
IBM watsonx Orchestrate + IBM IAM (AI layer only) · OpenStreetMap tiles, Nominatim (map, search) · unpkg (Leaflet CSS) · optional TomTom, OSRM, SMTP/SMS relay. Each has a fallback except the map tiles (blank map offline).

### Product / UX
English only (the name is Kannada); responder side is simulated with demo accounts; accessibility not audited; no mobile app; no push notifications.

## 3. Features not implemented

Image analysis · Kannada/Hindi UI · mobile app / PWA install · push notifications · rainfall forecast ingestion · real municipal integrations · HttpOnly-cookie sessions · account deletion/export · data-retention jobs · multi-agent orchestration · autonomous (scheduled) agent runs · metrics and alerting · frontend automated tests.

## 4. Roadmap (realistic, ordered by value for a hackathon submission and then for a pilot)

### Immediate — before submission (hours; needs your approval where code changes)
1. Fix KI-1 (one import) so CI is green.
2. Reconcile KI-2/KI-5/KI-6 text so every document states the same numbers and verification status.
3. Decide the submission branch (KI-7) and add a `LICENSE` (KI-8) after the ownership checks in [12](12_REPOSITORY_AND_LICENSE.md).
4. Capture the Orchestrate and Bob evidence screenshots listed in [SCREENSHOT_REQUIREMENTS](SCREENSHOT_REQUIREMENTS.md); verify the tool URL is reachable before recording the video.
5. Push the Bob git notes if you want them public (`git push origin refs/notes/bob`).

### Short term (1–4 weeks)
- Mask reporter identities in `evidence_list` (KI-4); citizen-text sanitisation for the LLM; prompt-injection tests.
- Add `pip-audit`/`npm audit` and a frontend smoke test (Playwright) to CI; restore or replace `e2e_smoke.py`.
- Stable public deployment on IBM Code Engine with PostgreSQL; run the suite against PostgreSQL in CI and keep the badge green.
- Per-route on-screen safety disclaimer; keyboard and screen-reader pass; Kannada UI strings.
- Evaluate the Orchestrate agent on a labelled set of ≥ 50 incidents; publish acceptance and error rates.

### Medium term (1–3 months)
- Build the road graph for the whole city from OpenStreetMap; replace synthetic trips with an aggregated OD matrix if a data-sharing agreement is obtained.
- Pilot with one ward and one control-room team to measure K3–K6.
- Notification delivery against a real SMS gateway; push notifications / PWA.
- Image analysis suggesting severity to the **human reviewer** (never auto-closing).
- Second Orchestrate agent (citizen-advisory drafter) and a scheduled analysis flow for new critical incidents (see [04 Part C](04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md)).

### Long term (3–12 months)
- Integration with municipal and traffic-police systems and rainfall/flood-sensor feeds.
- Multi-city configuration packages (Mumbai, Chennai, Hyderabad, Pune).
- Governance: data-protection impact assessment, retention policy, role-based access with SSO, independent security assessment.

All roadmap items are **plans**, not commitments, and none has started.
