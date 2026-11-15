# 09 · Security, Privacy and Responsible AI

Scope: what the repository **actually implements** (commit `cdafc7d`), what was **verified by running it** on 15 Nov 2026, and what is only **recommended**. Legend: ✅ implemented and verified (code read and/or test/smoke run) · ⚠️ implemented with a limitation · ❌ not implemented · 💡 recommended.

Related: [03 §15 auth](03_TECHNICAL_ARCHITECTURE.md) · [07 role matrix](07_API_DOCUMENTATION.md#role-matrix) · [04 Part B.8](04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md).

## 1. Summary for judges

| Area | Position |
|---|---|
| Human oversight | **Strong by design.** Only an admin can close/reopen a road; a responder must verify on site first; the LLM agent can only *recommend* and a human approves or dismisses. |
| Data minimisation | Good: no real-name requirement beyond a display name, no precise-location tracking stored (GPS is used in-browser to fill coordinates), photo metadata (EXIF/GPS) stripped. |
| Authentication | Solid for a prototype (scrypt, signed expiring tokens, revocation, lock-out). Session token kept in `localStorage`. |
| **Verified gap** | **Other citizens' ids/names are exposed in `evidence_list` of incident responses** (see §4.1). |
| Responsible AI | Single LLM agent, bounded tools, state-gated recommendations, full audit. **Not done:** prompt-injection sanitisation, model-quality evaluation, bias analysis. |
| Demo posture | Public demo password (`demo123`), a public admin sign-up code and legacy tokens exist **only** when `DEMO_MODE=true`; production mode refuses to start unless safe. |

## 2. Data collection and minimisation

| Data | Collected? | Where | Notes |
|---|---|---|---|
| Name, email | Yes (account) | `users` | needed for login; shown to admins/responders |
| Phone | Optional | `users.phone` | only for SMS; normalised to `+91…` |
| Password | Yes | `users.password_hash` | scrypt-salted; never stored or logged in clear |
| Hazard report: location, type, severity, text | Yes | `incidents`, `incident_reports`, `incident_evidence` | **free text** typed by citizens |
| Photos | Optional | `UPLOAD_DIR/uploads` + `uploads` table | JPEG/PNG only; EXIF/GPS/XMP/IPTC and PNG text chunks removed; not analysed |
| Device location | Browser asks permission; only coordinates the user submits are sent | — | `navigator.geolocation` used to fill coordinates; no background tracking |
| Reputation | Derived | computed from confirmed/rejected incidents | per account |
| Audit + agent events | Yes | `audit_events`, `agent_events` | actor id/name, before/after state |
| Analytics / ad trackers | **None found** | — | no third-party analytics scripts (CSP `script-src 'self'`) |
| Children's data / sensitive categories | **Not collected by design**; free text could contain anything a user types | — | hackathon rule 8.3 forbids submitting such data; see §8 |

Retention: **no automatic retention policy** except purging unattached photos after 24 h and expiring reset tokens (30 min) and sessions (8 h). Incidents, evidence, audit and agent events are kept indefinitely. ❌ No account deletion or data-export endpoint. 💡 add one.

## 3. Authentication and authorisation

| Control | Status | Evidence |
|---|---|---|
| Password hashing: scrypt with per-password salt; legacy hashes auto-upgraded on login | ✅ | `security.py`, `test_production_readiness` |
| Password policy: ≥ 8 chars, upper, lower, digit, special | ✅ | `auth._validate_password_strength`; smoke M-11 |
| Session token: `<user>.<version>.<expiry>.<HMAC-SHA256>`; 8 h; constant-time compare | ✅ | `auth.py`; `test_session_tokens.py` (5) |
| Revocation: logout/password change/reset bump `token_version` → all sessions invalid | ✅ | `test_hardening.py` |
| Account lock-out: 5 failures → 15 min (per email, shared by workers) + per-IP auth limit (20/min) | ✅ | `test_account_lockout_after_repeated_failures` |
| User enumeration: `forgot-password` identical reply for unknown emails; login does comparable work for unknown accounts | ✅ | `auth.py`; smoke M-31 |
| Reset tokens: random 32-byte, **stored hashed**, 30 min, single use; body redacted in logs | ✅ | `auth.py`, `notification_service.py:104-106` |
| Role checks on every operational endpoint | ✅ | [role matrix](07_API_DOCUMENTATION.md#role-matrix); smoke M-06…M-08 |
| Ownership checks (withdraw own report; responder only own team/incident) | ✅ | `incident_service.py`, `teams.py` |
| Public sign-up creates citizens only (outside `DEMO_MODE`) | ✅ | `auth.register` |
| Production fail-fast: refuses to start with weak `JWT_SECRET`, legacy tokens or `*` CORS when `DEMO_MODE=false` | ✅ | `main.production_problems` |
| Session token in `localStorage` (readable by XSS) | ⚠️ | README acknowledges; mitigated by strict CSP; HttpOnly cookie + CSRF not done |
| **Demo-mode defaults are intentionally insecure**: password `demo123`, public admin sign-up code (`bbmp2026` default in `config.py`), legacy bare-id tokens (`Authorization: Bearer usr-admin-1` grants admin) | ⚠️ | Acceptable **only** for a local/judging demo. `render.yaml` and the Code Engine script turn legacy tokens, reset-token exposure off and generate the admin code. The hosted Render instance is in `DEMO_MODE=true` — [TEAM INPUT REQUIRED: confirm `ALLOW_LEGACY_TOKENS=false` is really set on the live instance, since it grants admin to anyone otherwise] |
| Multi-factor authentication, SSO/IBM App ID | ❌ | 💡 |

## 4. API and application security

| Control | Status | Evidence |
|---|---|---|
| Input validation (enums, lengths, bounds, service area) via Pydantic | ✅ | `schemas.py`; smoke M-10 |
| Rate limits (DB-backed, shared across workers): auth 20/min/IP, reports 30/h, simulations 10/min, uploads 20/h | ✅ | `ratelimit.py`; `test_production_readiness` |
| SQL: values are bound with `?` placeholders; the only f-string SQL found (grep of `api/` and `services/`) interpolates generated lists of `?` or internal constant status lists, not user input | ✅ | code read + grep; no SAST tool run |
| Security headers: CSP (`default-src 'self'`, `script-src 'self'`, `frame-ancestors 'none'`, `object-src 'none'`), `X-Content-Type-Options`, Permissions-Policy, HSTS over https when enabled | ✅ | `test_security_headers_present` |
| CORS: same-origin by default; `*` only in `DEMO_MODE` | ✅ | `main.py:109-117` |
| Upload hardening: magic-byte type detection, structural JPEG/PNG validation, no trailing payload, size cap (5 MB), unguessable 128-bit ids, `nosniff` + sandbox CSP when served | ✅ | `upload_service.py`; smoke M-18 (non-image → 415). Not done: re-encoding, antivirus, moderation |
| Photo URLs are capability links served **without login** (an `<img>` cannot send a token) | ⚠️ | documented in `uploads.py`; anyone with the 32-hex id can view the photo |
| SSE stream is unauthenticated but carries only public road-network state; capped at 100 clients | ⚠️ | `events.py` |
| Agent tool API: shared secret in `X-API-Key`, constant-time compare, closed by default | ✅ | `agent_tools.py`; tests A-24/A-25 |
| Request IDs and structured logs; secrets not logged (reset bodies redacted, TomTom key not logged) | ✅ | `main.py`, `notification_service.py` |
| Dependency vulnerability scanning (`pip-audit`, `npm audit`), SAST, secret-scanning in CI | ❌ | not in CI; not run in this audit 💡 |
| Penetration test / threat model | ❌ | none performed |

### 4.1 Verified privacy gap: reporter identity in `evidence_list`

`GET /incidents` and `GET /incidents/{id}` hide `reported_by_id` / `reported_by_name` from other citizens (`incident_service.py:63-83`: other citizens see `"anonymous"` / `"Verified Citizen"`). **However, the nested `evidence_list[]` still carries `submitted_by` (user id) and `submitter_name`.** In the audit database, signed in as *Citizen Commuter (Pooja)*, the response for the seeded Indiranagar incident contained `evidence_list: [{"submitted_by":"usr-citizen-2","submitter_name":"Citizen Driver (Kiran)", …}]` while the same incident's `reported_by_name` was masked as "Verified Citizen". The React UI renders only `text_notes`, so this is not visible on screen, but any signed-in citizen can read it via the API.
- **Impact:** other citizens' display names and user ids are retrievable by any signed-in citizen.
- **Status:** not fixed (the audit does not modify application code). **Recommended fix** (needs team approval, tracked as Q17): drop or mask `submitted_by`/`submitter_name` in `evidence_list` when `role == citizen` and `submitted_by != user_id`. Add a regression test.
- Related: the exact `lat`/`lon` of each report is visible to all signed-in users by design (it is a public hazard map).

## 5. Secrets management

| Item | Status |
|---|---|
| Secrets come from environment / `.env`; `.env` is git-ignored (`.env`, `.env.*` with `!.env.example`) | ✅ |
| `.env.example` contains **names and empty/placeholder values only** | ✅ read in full during the audit |
| The four real secret values in the local `.env` (tool key, Orchestrate key, agent id, TomTom key) were searched for in the working tree and 50 git revisions | ✅ **not found** |
| Orchestrate API key is never returned by `GET /agents/status` and not logged | ✅ (code read) |
| `JWT_SECRET` default in `config.py` is a known demo string (`malemitra-secret-key-bobathon-2026`); production mode rejects it | ⚠️ |
| `PUBLIC_BASE_URL` (a temporary tunnel host) is returned by `/agents/status` and embedded in the committed OpenAPI file | ⚠️ low risk (no secret), but screenshots of the Orchestrate panel can expose the tunnel URL — **crop/blur before publishing** (screenshot SS05 was deleted for this reason) |
| Orchestrate tool secret shared by header (not OAuth) | ⚠️ 💡 rotate regularly; per-environment keys |

**Rule for the team:** do not paste `.env` contents, bearer tokens, IBM API keys or the tool key into slides, screenshots, the video or this documentation.

## 6. External data sharing

| Third party | What leaves the system | Condition |
|---|---|---|
| IBM watsonx Orchestrate (+ IBM IAM) | Admin prompts; tool results the agent requests: incident metadata, **citizen free-text evidence notes**, responder names/ids and availability, road/edge state. **Not sent by the tools:** reporter name/email/phone (checked in `_slim_incident` and `get_incident_context`) | only when configured and an admin asks; processed under the team's IBM account terms [TEAM INPUT REQUIRED: IBM region/data-residency position for the demo — instance host is `ap-south-1`] |
| TomTom | Origin/destination and road-segment coordinates for ETA/flow | only with `TOMTOM_API_KEY` |
| OSRM (public demo server or self-hosted) | Route coordinates | the public server has no SLA/privacy commitment; self-host via Compose for anything real |
| OpenStreetMap tiles, Nominatim | The user's browser requests tiles and place searches (IP, search text) | browser-side; allowed by CSP `connect-src` |
| unpkg (Leaflet CSS, SRI-pinned) | Browser fetch | |
| SMTP / SMS webhook relay | Recipient address/number and message body | only if configured; webhook is HMAC-signed |

## 7. Responsible AI

### 7.1 What AI does in this system
- **One LLM agent** (watsonx Orchestrate, `malemitra_incident_agent`) that recommends one action per analysis.
- Everything else (routing, ripple, merging, trust score, "intelligence" agents) is **deterministic, rule-based code** and is labelled `rule-based` in the UI. We do not market it as AI.

### 7.2 Implemented safeguards

| Safeguard | Detail |
|---|---|
| Bounded autonomy | `submit_recommendation` is the only write; it never changes status or closes a road |
| Human approval | Admin approve/dismiss with notes; approving runs the *normal* gated action; stale recommendations (incident moved on) cannot be approved |
| Workflow gate | An action invalid for the incident's status is refused with `422 workflow_gate`; the agent must re-plan |
| Tool bounds | ≤ 5 edges per what-if, ≤ 25 incidents listed, rationale ≥ 10 chars (stored ≤ 1000), confidence 0–1, Bengaluru bounding box |
| Auditability | Every tool call, accepted or rejected, is stored with inputs/outcome and shown in the Agent Decision Timeline; approvals are audit-logged |
| Transparency | The UI distinguishes `rule-based` from `LLM agent` rows and marks recommendations "needs approval"; route cards carry an `uncertainty` text ("Not a guaranteed safe route") |
| Crowd-trust design | Unverified citizen reports can add a routing *penalty* but **never** a closure; confidence capped at 0.9 until a human verifies; reporters' influence is reputation-weighted; one user cannot double-count or inflate severity alone (tests) |
| Graceful degradation | If Orchestrate is down or unconfigured the app keeps working (503 on chat only) |

### 7.3 Risks and gaps

| Risk | Status |
|---|---|
| **Prompt injection via citizen free text.** `get_incident_context` returns citizen-written notes to the LLM, so a malicious report could try to steer the agent (e.g. "recommend closing this road"). | ⚠️ Mitigated structurally (agent can only recommend; recommendation must pass the state gate; a human decides). ❌ No text sanitisation, length limit on the notes the LLM sees, or injection test. 💡 add them |
| **Hallucinated rationale.** The agent's explanation may cite facts it did not retrieve. | ⚠️ Rationale is shown beside the tool-call log so a reviewer can compare. ❌ No automatic grounding check |
| **LLM quality unmeasured.** No evaluation set, accuracy or false-positive rate exists. | ❌ Do not claim accuracy |
| **Automation bias.** Admins may over-trust a confident recommendation. | ⚠️ Approve button text states the consequence ("Approve & close road"); confidence and rationale are shown; no forced second check 💡 |
| **Fairness / coverage bias.** Only 5 localities are modelled and crowd reports come from smartphone users, so neighbourhoods with fewer reporters are under-represented. | ❌ not analysed; documented in [11](11_LIMITATIONS_AND_ROADMAP.md) |
| **Misuse: false reports to disrupt traffic.** | ⚠️ rate limits, reputation weighting, merge logic, field verification, admin-only closure |
| **Misuse: surveillance of reporters.** | ⚠️ reporter identity masked from citizens on incident fields (but see §4.1) |
| **Photos not analysed**; a photo cannot be trusted as proof | ⚠️ README and UI treat it as "file attached" only |
| **Safety-critical use.** The system is advisory and a prototype; it must not be the sole basis for life-safety decisions or navigation into floodwater. | Stated in `uncertainty` text; 💡 add an on-screen disclaimer on every route card |

## 8. Compliance notes (hackathon rules)

- Rule 8.3 forbids submitting credentials, children's data and similar. **Verified:** no credentials committed; the demo accounts are fictional and the only password is the public `demo123`. The database seeded in demo mode contains only fictional users.
- Responsible AI / privacy statement for the submission: use §1 and §7; do not claim GDPR/DPDP-Act compliance — **no legal review has been done** [TEAM INPUT REQUIRED]. India's Digital Personal Data Protection Act, 2023 would apply to a real deployment that processes residents' personal data; consult counsel before launch (sources: https://www.meity.gov.in/data-protection-framework — returned HTTP 200 on 15 Nov 2026 — and https://en.wikipedia.org/wiki/Digital_Personal_Data_Protection_Act%2C_2023 for a neutral summary).

## 9. Recommended actions (prioritised, none implemented)

| # | Action | Effort |
|---|---|---|
| 1 | Confirm `ALLOW_LEGACY_TOKENS=false` and `EXPOSE_RESET_TOKEN=false` on the public instance used by judges | minutes |
| 2 | Mask `submitted_by`/`submitter_name` of other citizens in `evidence_list` for citizen callers; add a test | small |
| 3 | Add length cap + delimiter/escaping for citizen text passed to the LLM, and a prompt-injection test | small |
| 4 | Add `pip-audit` and `npm audit` to CI | small |
| 5 | Define retention (e.g. archive cleared incidents after N days) and an account-delete/export endpoint | medium |
| 6 | Move the session to an HttpOnly, SameSite cookie with CSRF protection | medium |
| 7 | Evaluate the agent on a labelled set of incidents; report precision of recommendations | medium |
| 8 | On-screen disclaimer on route cards; keyboard/screen-reader accessibility pass | small–medium |
