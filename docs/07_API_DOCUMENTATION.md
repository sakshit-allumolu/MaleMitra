# 07 · API Documentation

All paths below are relative to the API prefix **`/api/v1`**. Source: the FastAPI routers in `backend/app/api/` and the Pydantic models in `backend/app/models/schemas.py`. The operation list and the role guards were extracted from the running application's route table (`app.routes` dependency introspection) on 15 Nov 2026 and cross-checked against the code; the **example responses were captured by the auditor from a throwaway `DEMO_MODE` database** (offline, no OSRM/TomTom/Orchestrate). Live interactive documentation is served by the app at `/docs` (Swagger UI) and `/openapi.json`.

**Total: 53 documented operations** — auth 9 · reports 1 · incidents 9 · routes 2 · simulations 5 (incl. `GET /simulations/latest`) · teams 4 · events 3 · health 1 · traffic 1 · agents 5 · agent-tools 8 · notifications 3 · uploads 2. One further route, `GET /agent-tools/spec`, serves the tools' OpenAPI document and is hidden from `/docs` (`include_in_schema=False`).

## Conventions

| Item | Detail |
|---|---|
| Auth header | `Authorization: Bearer <access_token>` (token from `POST /auth/login`). Token format: `<user_id>.<token_version>.<expiry>.<hmac>`; 8 h lifetime; revoked on logout/password change. Bare user ids are accepted **only** when `ALLOW_LEGACY_TOKENS=true` (default in `DEMO_MODE`). |
| Agent-tool auth | `X-API-Key: <AGENT_TOOL_API_KEY>`; `401` if unset or wrong. |
| Content type | `application/json`, except `POST /uploads` (raw image bytes). |
| Errors | `{"detail": "<message>"}`; validation errors `422` with Pydantic's `detail: [{type, loc, msg, input, ctx}]`; agent-tool rejections `422 {"detail": {"error": "<code>", "message": "…"}}`. |
| Common errors | `401` missing/invalid session · `403` role not allowed · `422` validation · `429` rate-limited (`Retry-After` header) · `503` dependency unavailable |
| Service area | Report and route coordinates must lie inside the Bengaluru bounding box (`ROUTE_AREA_BBOX` default `77.42,12.82,77.78,13.13`); outside → `422`. Schema-level bounds are lat 12.0–14.0, lon 77.0–78.5. |

## Role matrix

`A` admin · `R` responder · `C` citizen · `—` not allowed · `*` any signed-in user · `Public` no auth · `Key` agent API key. Derived from `require_role(...)` / `get_current_user` in the code.

| Operation | Public | C | R | A | Notes |
|---|---|---|---|---|---|
| `POST /auth/login`, `/auth/register`, `/auth/forgot-password`, `/auth/reset-password` | ✔ | | | | per-IP rate limit; register creates citizens only outside `DEMO_MODE` |
| `POST /auth/users` | | — | — | ✔ | admin creates responder/admin/citizen |
| `GET /auth/me`, `PUT /auth/me/phone`, `POST /auth/logout`, `POST /auth/change-password` | | ✔ | ✔ | ✔ | |
| `POST /reports` | | ✔ | ✔ | ✔ | 30/h per account |
| `GET /incidents`, `GET /incidents/{id}` | | ✔ | ✔ | ✔ | response is role-filtered (citizens see public fields, `is_mine`) |
| `POST /incidents/{id}/withdraw` | | ✔ (own) | ✔ (own) | ✔ (own) | only `reported`/`under_review` |
| `POST /incidents/{id}/review`, `/assign`, `/restriction` | | — | — | ✔ | |
| `POST /incidents/{id}/claim` | | — | ✔ | — | **responder only** (admin gets 403) |
| `POST /incidents/{id}/verify`, `/clearance` | | — | ✔ | ✔ | |
| `POST /routes/compare` | | ✔ | ✔ | ✔ | |
| `GET /routes/network` | ✔ | | | | public graph data |
| `POST /simulations`, `GET /simulations/{run_id}/impact` | | ✔ | ✔ | ✔ | read-only; 10/min per account |
| `POST /simulations/{run_id}/inject`, `GET /simulations/benchmark/run` | | — | — | ✔ | |
| `GET /simulations/latest`, `GET /traffic/live`, `GET /health` | ✔ | | | | |
| `GET /teams` | | ✔ | ✔ | ✔ | |
| `GET /teams/responders` | | — | — | ✔ | |
| `GET /teams/me/tasks` | | — | ✔ | ✔ | |
| `POST /teams/{team_id}/status` | | — | ✔ (own team) | ✔ | |
| `GET /events/agent`, `GET /events/audit` | | — | — | ✔ | |
| `GET /events/stream` | ✔ | | | | **Unauthenticated SSE**: only graph version and blocked edge ids (same data as `/routes/network`); max 100 clients |
| `GET /agents/status` | | ✔ | ✔ | ✔ | no secrets in the response |
| `POST /agents/chat`, `/agents/analyze/{id}`, `GET /agents/recommendation/{id}`, `POST /agents/recommendations/{event_id}/decision` | | — | — | ✔ | |
| `POST /agent-tools/*` (8 tools) | | | | | **Key** (`X-API-Key`) |
| `GET /agent-tools/spec` | ✔ | | | | OpenAPI doc of the tools; contains the public base URL, no secret |
| `GET /notifications/status`, `GET /notifications`, `POST /notifications/{id}/retry` | | — | — | ✔ | |
| `POST /uploads` | | ✔ | ✔ | ✔ | 20/h per account |
| `GET /uploads/{id}` | ✔ | | | | capability URL (128-bit random id); EXIF/GPS stripped |

Verified during the audit: no token → `401`; citizen on `/events/audit` → `403`; citizen on `/incidents/{id}/review` → `403`; responder updating another team's status → `403`; unconfigured `agents/chat` → `503`.

---

## 1. Authentication

| Method | URL | Purpose | Request body | Success | Errors |
|---|---|---|---|---|---|
| POST | `/auth/login` | Exchange email/password for a session token | `{email, password}` | `200 TokenResponse` | `401 Invalid email or password.`, `429` lock-out after 5 failures (`Retry-After: 900`), `422` |
| POST | `/auth/register` | Public sign-up (citizen) | `{name, email, password, role?, phone?, team_id?, admin_code?}` | `200 TokenResponse` | `422` weak password/too long, `409` email exists, `403` non-citizen role outside `DEMO_MODE` or bad admin code, `400` missing fields |
| POST | `/auth/users` | Admin creates an account | `{name, email, password, role, team_id?, phone?}` | `200 UserProfile` | `422` role/password/team, `409`, `403` |
| GET | `/auth/me` | Current user | — | `200 UserProfile` | `401` |
| PUT | `/auth/me/phone` | Set/clear SMS number | `{phone}` | `200 {"phone": "+919876543210"}` | `422` |
| POST | `/auth/logout` | Revoke all this user's tokens | — | `200 {"message":"Signed out."}` | `401` |
| POST | `/auth/change-password` | Change password; returns a fresh token | `{current_password, new_password}` | `200 TokenResponse` | `403` wrong current, `422` policy |
| POST | `/auth/forgot-password` | Start reset; same reply whether or not the email exists | `{email}` | `200 {"message":"If that email exists, a reset link has been sent.","debug_token":null}` (`debug_token` only when `DEMO_MODE` and `EXPOSE_RESET_TOKEN`) | `429` |
| POST | `/auth/reset-password` | Finish reset | `{token, new_password}` | `200` | `400` invalid/used/expired token, `422` |

Password policy: ≥ 8 chars with an uppercase letter, a lowercase letter, a digit and a special character.

**Example — login**

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"citizen@malemitra.in","password":"demo123"}'
```
```json
{"access_token":"usr-citizen-1.0.1794796960.<hmac>","token_type":"bearer","user_id":"usr-citizen-1","name":"Citizen Commuter (Pooja)","role":"citizen","team_id":null}
```
Wrong password: `401 {"detail":"Invalid email or password."}`. Missing field: `422 {"detail":[{"type":"missing","loc":["body","password"],"msg":"Field required",…}]}`.

**`UserProfile`**: `{id, name, email, role, team_id, active}` (captured: `{"id":"usr-citizen-1","name":"Citizen Commuter (Pooja)","email":"citizen@malemitra.in","role":"citizen","team_id":null,"active":true}`).

## 2. Reports and incidents

### `POST /reports` — submit a hazard report
Purpose: create an incident or merge into one within 10 m. Auth: any signed-in user. Rate limit: 30/h/account.

| Field | Type | Rules |
|---|---|---|
| `lat`, `lon` | float | within the service area |
| `type` | enum | `waterlogging` (default), `drain_overflow`, `fallen_tree_water`, `manhole_hazard`, `road_submerged` |
| `severity` | enum | `low`, `medium` (default), `high`, `critical` |
| `description` | string | 3–2000 chars, required |
| `evidence_note` | string? | ≤ 2000 |
| `photo_id` | string? | 32 hex chars from `POST /uploads` (preferred) |
| `photo_url` | string? | `http(s)://…`, ≤ 500; reference only, counts for nothing in credibility |

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/reports \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"lat":12.9610,"lon":77.6387,"type":"drain_overflow","severity":"medium","description":"Drain overflowing onto the carriageway"}'
```
Captured response (trimmed): `200 {"id":"inc-5bb8e9c9","road_edge_id":"edge-33","road_name":"Domlur Flyover / Old Airport Road (North/Eastbound)","lat":12.961,"lon":77.6387,"type":"drain_overflow","severity":"medium","status":"reported","confidence":0.85,"reports_count":1,"assigned_team_id":null,"is_blocked":false,"evidence_list":[{"evidence_type":"citizen_report","text_notes":"Drain overflowing onto the carriageway",…}],"agent_summary":{"edge_mapped":"edge-33","distance_to_edge_m":7.0,"is_ambiguous":false,"confidence":0.85,"recommendation":"Eligible for priority inspection","duplicate_cluster":false,"duplicate_of":null}}`

Errors: `422` outside Bengaluru / bad enum / short description (Delhi test point 28.6, 77.2 → `422 … "Input should be less than or equal to 14"`), `401`, `429`.

**`IncidentDetail`**: `id, road_edge_id, road_name, lat, lon, type, severity, status, confidence, reported_by_id, reported_by_name, reports_count, assigned_team_id/label, assigned_responder_id/name, verification_notes, water_depth_cm, restriction_notes, is_blocked, created_at, updated_at, evidence_list[], agent_summary`. Citizens receive a filtered view (adds `is_mine`).

### Other incident operations

| Method | URL | Role | Body | Purpose | Notable errors |
|---|---|---|---|---|---|
| GET | `/incidents?limit=&offset=` | * | — | Newest first; `limit` 1–1000 (default 1000); header `X-Total-Count` | `401` |
| GET | `/incidents/{id}` | * | — | One incident | `404` |
| POST | `/incidents/{id}/review` | A | `{notes?, initial_severity?}` | → `under_review` (also valid from `under_review`) | `409 Cannot review incident in state …` |
| POST | `/incidents/{id}/assign` | A | `{team_id, responder_id?, priority?, notes?}` | → `assigned` (team queue if no `responder_id`) | `409` triage not confirmed, `404` unknown team, `422` responder not on that team |
| POST | `/incidents/{id}/claim` | R | — | Free responder takes a queue item | `409`/`403` not assigned, taken, other team |
| POST | `/incidents/{id}/verify` | R, A | `{findings (3–2000), water_depth_cm (0–500, default 45), is_impassable (default true), recommended_action: authorize_closure\|monitor\|clear, evidence_note?, photo_id?, photo_url?}` | → `field_verified` | `409 … Must be assigned first.`, `403` other responder/team |
| POST | `/incidents/{id}/clearance` | R, A | `{clearance_findings?, evidence_note?}` | → `clearance_proposed` | `409` |
| POST | `/incidents/{id}/restriction` | A | `{action: authorize_block\|authorize_reopen\|reject, restriction_type?, notes?}` | `authorize_block` (needs `field_verified`) → `blocked`, bumps `graph_version`; `authorize_reopen` (needs `clearance_proposed`) → `cleared`; `reject` (needs `reported`/`under_review`) → `rejected` | `409` e.g. "Cannot authorize blockage on incident in status 'assigned'. A responder must field-verify it first." |
| POST | `/incidents/{id}/withdraw` | * (own report) | — | → `rejected` ("Withdrawn by reporter") | `403` not yours, `409` "Only reports that are 'reported' or 'under_review' can be withdrawn." |

## 3. Routing

### `POST /routes/compare`
Body (note the nested objects):

```json
{"origin":{"lat":12.9352,"lon":77.6245},"destination":{"lat":12.9784,"lon":77.6408},"scenario_id":null}
```
Response `RouteCompareResponse`: `{graph_version, data_mode, routes:[RoutePathItem], active_restrictions_count, reported_hazards_count, traffic_factor, traffic_label, traffic_source, message}`. Each `RoutePathItem`: `type` (`fastest`/`risk_aware`/`alternative`), `label`, `edge_ids`, `path_nodes`, `node_names`, `coordinates [[lat,lon]…]`, `osrm_steps`, `estimated_duration_s`, `base_duration_s`, `traffic_delay_s`, `traffic_factor`, `traffic_source` (`tomtom_live`/`tomtom_corridor`/`time_of_day_model`), `hazard_penalty_s`, `congestion_delay_s`, `distance_m`, `blocked_edges_crossed`, `risk_score`, `uncertainty`, `geometry_source`.

Captured (offline): `200`, `data_mode: "hybrid_osrm_malemitra"`, routes `fastest` 1148.2 s / risk 0.18 and `risk_aware` 1316.2 s / risk 0.08, `traffic_source: "time_of_day_model"`, message "Routes calculated with typical-hours traffic model (Night — free flow, ×1.0) + MaleMitra incident intelligence."
Errors: `422` "The start point is outside the Bengaluru area MaleMitra can route in. Pick a point inside the city."

### `GET /routes/network` (public)
`{graph_version, nodes:[{id,name,lat,lon}], edges:[…]}` — 20 nodes, 56 edges in the audited build.

## 4. Simulations

| Method | URL | Role | Body | Notes |
|---|---|---|---|---|
| POST | `/simulations` | * | `{seed=42, iterations 1–5 (2), custom_blocked_edge_ids? (≤20), trip_count? (10–500), scenario_label?}` | Read-only what-if. `422 Unknown edge ids: [...]`. 10/min per account |
| GET | `/simulations/{run_id}/impact` | * | — | Runs seed 42/2 iterations (the `run_id` is not used for lookup) |
| POST | `/simulations/{run_id}/inject` | A | `{edge_ids: [1–20]}` | Ripple for the listed edges (seed 42) |
| GET | `/simulations/benchmark/run` | A | — | Baseline vs MaleMitra benchmark |
| GET | `/simulations/latest` | Public | — | Last automatic ripple result or `{"detail":"No automatic ripple run yet."}` |

`RippleImpactResponse`: `{run_id, graph_version, seed, total_trips, affected_trips, mean_baseline_duration_s, mean_disrupted_duration_s, mean_detour_s, pct_travel_time_increase, top_affected_edges[], blocked_edges[], edge_metrics[], timestamp}`; `EdgeMetric`: `{edge_id, road_name, source_node, target_node, baseline_load, disrupted_load, delta_load, capacity_proxy, base_travel_time_s, disrupted_travel_time_s, congestion_ratio, status}`.
Captured after one closure on the audit DB: `total_trips 150, affected_trips 25, mean_baseline_duration_s 366.7`, top edge `edge-43` Δload +25.

Benchmark response (`BenchmarkResult`): `{scenario_name, total_trips, blocked_corridor, baseline_trips_crossing_blocked, baseline_pct_blocked, malemitra_trips_crossing_blocked, malemitra_pct_blocked, blocked_traversal_reduction_pct, baseline_mean_trip_time_s, malemitra_mean_trip_time_s, mean_detour_s, detour_tradeoff_pct, network_total_travel_time_increase_pct, no_route_trips_count, evaluation_runtime_ms, timestamp}`. Captured: `38 → 0` trips, `100 %` reduction on a clean graph; time-trade-off values depend on live graph state — see [08](08_TESTING_AND_VALIDATION.md).

## 5. Teams, events, health, notifications, uploads

| Method | URL | Role | Response (captured where noted) |
|---|---|---|---|
| GET | `/teams` | * | `{"teams":[{"id":"team-alpha","label":"Team Alpha - Stormwater Response","status":"dispatched","current_incident_id":"inc-…","demo_flag":1}, …]}` |
| GET | `/teams/responders` | A | `{"responders":[{id,name,team_id,team_label,is_free,active_incident_ids}]}` |
| GET | `/teams/me/tasks` | R, A | `{"team_id","tasks":[…],"queue":[…],"is_free":bool}` |
| POST | `/teams/{team_id}/status?status=available\|dispatched\|offline` | A; R own team | `{"team_id","status"}`; `403 Responders can only update their own team.`; `404` |
| GET | `/events/agent` | A | `{"events":[{event_id, incident_id, agent, action, input_refs, result, data_mode, requires_approval, decision, decided_at, timestamp}]}` (last 50) |
| GET | `/events/audit` | A | `{"audits":[{id, actor_id, actor_name, action, entity_type, entity_id, before_state, after_state, timestamp}]}` (last 50) |
| GET | `/events/stream` | Public | SSE; every ≈ 2.5 s: `data: {"graph_version":N,"version_changed":bool,"active_blocked_edges":["edge-7",…]}`; `503` over 100 clients |
| GET | `/health` | Public | `200 {"status":"healthy","service":"MaleMitra API","checks":{"database":true,"road_graph":true},"graph_version":8,"nodes_count":20,"edges_count":56,"mode":"modular_monolith"}`; `503` if a check fails |
| GET | `/traffic/live` | Public | `{"enabled":false,"provider":"tomtom","poll_interval_s":1020,…,"routing":{"enabled":false,"key_configured":false,"daily_budget":800,…}}` |
| GET | `/notifications/status` | A | `{"channels":{"email":false,"sms":false,"log":true},"counts":{"pending":7,"sent":1},"dispatcher_running":true}` |
| GET | `/notifications?status=&limit=` | A | `{"notifications":[{id,user_id,channel,recipient,kind,subject,status,attempts,last_error,created_at,sent_at}]}` — bodies omitted on purpose (reset messages hold one-time codes); `limit` clamped 1–200 |
| POST | `/notifications/{id}/retry` | A | `{"id","status":"pending"}`; `404 No failed notification with that id.` |
| POST | `/uploads` | * | Raw JPEG/PNG bytes as body → `201 {"id":"<32 hex>","url":"…","mime":"image/jpeg","size":N}`; `415 Rejected image: only JPEG and PNG images are accepted.` (captured), `413` over 5 MB, `400` empty, `429` |
| GET | `/uploads/{id}` | Public | The image; `404 Photo not found`; headers `X-Content-Type-Options: nosniff`, `Content-Security-Policy: default-src 'none'; sandbox` |

## 6. Agents (watsonx Orchestrate) — admin only

| Method | URL | Body | Response |
|---|---|---|---|
| GET | `/agents/status` (any signed-in user) | — | `{configured, missing_settings[], tools_enabled, agent_id, instance_url, tools_public_url, last_error, last_ok_at, tools:[8 names]}`. Captured unconfigured: `"configured": false, "missing_settings": ["ORCHESTRATE_API_KEY","ORCHESTRATE_INSTANCE_URL","ORCHESTRATE_AGENT_ID"]` |
| POST | `/agents/chat` | `{message (1–2000)}` | `200 {"reply": "…"}`; `503 watsonx Orchestrate is not configured (missing: …)` (captured); other `OrchestrateError` status codes pass through (e.g. 502) |
| POST | `/agents/analyze/{incident_id}` | — | `{"reply": "…", "recommendation": {…} \| null}`; `404 Incident not found.` |
| GET | `/agents/recommendation/{incident_id}` | — | `{"recommendation": {…} \| null}` |
| POST | `/agents/recommendations/{event_id}/decision` | `{decision: "approve"\|"dismiss", notes?, team_id?, responder_id?}` | `{"recommendation": {…}, "incident": {…}}`. Errors: `404 Recommendation not found.` (captured), `409` already decided, `409` "Incident is now '…' but this was recommended at '…'. Re-analyse before approving." (stale), `422` "Choose a response team to approve this recommendation." |

Approving a state-changing recommendation (`request_triage`, `assign_team`, `reject_duplicate`, `propose_block`, `propose_reopen`) runs the corresponding incident-service action with its usual gates and writes an `AGENT_RECOMMENDATION_APPROVED` audit row; `monitor`, `escalate`, `request_field_verification` are advisory and are only acknowledged.

## 7. Agent tools (called by watsonx Orchestrate) — `X-API-Key`

OpenAPI for these eight operations: `GET /agent-tools/spec`, also committed as `orchestrate/malemitra_tools_openapi.json`. `operationId` equals the tool name.

| Tool | Request body | Response (captured on audit DB) |
|---|---|---|
| `map_to_edge` | `{lat, lon}` | `{"edge_id":"edge-1","road_name":"80ft Road Koramangala (North/Eastbound)","distance_m":0.0,"is_ambiguous":false,"is_blocked":false,"hazard_severity":"critical"}` |
| `list_open_incidents` | `{status?}` (body optional) | `{"count":2,"incidents":[{id, road_edge_id, road_name, type, severity, status, confidence, reports_count, duplicate_of, is_ambiguous, assigned_team_id, assigned_responder_id, is_blocked, created_at}]}` (≤ 25) |
| `list_responder_availability` | `{team_id?}` (body optional) | `{"count":2,"free_count":2,"responders":[{id, name, team_id, team_label, is_free, active_incident_ids}],"note":"…"}` — no email/phone |
| `get_incident_context` | `{incident_id}` | `{incident:{…slim…}, verification_notes, water_depth_cm, evidence:[{type,notes,at}], edge:{…}, other_open_incidents_on_edge:[], previous_recommendation}` — citizen notes appear in `evidence[].notes`; no reporter identity |
| `compute_route` | `{origin_lat, origin_lon, dest_lat, dest_lon}` | `{"routes":{"fastest":{node_names, duration_s, distance_m, blocked_crossed, risk_score, hazard_penalty_s, congestion_delay_s}, "risk_aware":{…}, …}}` |
| `estimate_bpr_load` | `{edge_id}` | `{"edge_id","road_name","volume_capacity_ratio":0.0,"source":"ripple_simulation","free_flow_s":108.8,"bpr_travel_time_s":108.8,"delay_s":0.0,"is_blocked":false}` |
| `run_ripple_what_if` | `{edge_ids:[≤5]}` | `{"simulated_blocked_edges":["edge-35"],"total_trips":150,"affected_trips":16,"mean_detour_s":110.1,"pct_travel_time_increase":3.2,"top_affected_edges":[{edge_id, road_name, delta_load, congestion_ratio, status}]}` — live state not changed |
| `submit_recommendation` | `{incident_id, action, rationale (≥10 chars), confidence (0–1), team_id?, responder_id?}` | `action ∈ request_triage, assign_team, reject_duplicate, request_field_verification, propose_block, propose_reopen, monitor, escalate`. Success stores the recommendation with `requires_approval`. Rejections (captured): `422 {"detail":{"error":"workflow_gate","message":"'propose_block' is only valid when status is ['field_verified']; incident is 'reported'."}}`; unknown incident → `422 {"error":"not_found","message":"Incident inc-none not found."}` |

Without the key: `401 {"detail":"Invalid or missing X-API-Key."}` (captured); with `AGENT_TOOL_API_KEY` unset: `401 "Agent tools are disabled: AGENT_TOOL_API_KEY is not configured."`

## 8. Not exposed / out of scope

- There is no public API for other developers, no API versioning beyond `/api/v1`, and no pagination except `GET /incidents`.
- No WebSocket API; live updates use SSE only.
- Example tokens above are shortened; never paste a real token or `AGENT_TOOL_API_KEY` into documentation or screenshots.
