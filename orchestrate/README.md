# watsonx Orchestrate integration

MaleMitra exposes eight deterministic tools over REST. An agent running in **watsonx Orchestrate**
decides which tools to call, reasons over the results and records a **recommendation**. A human
admin still approves every road closure or reopening.

```
Admin UI ──POST /agents/analyze/{id}──▶ MaleMitra backend ──chat──▶ watsonx Orchestrate agent (LLM)
                                              ▲                              │
                                              └──── X-API-Key tool calls ◀───┘
                                  (get_incident_context, run_ripple_what_if, … submit_recommendation)
```

## What is verified, what is not

| Part | Status |
|---|---|
| Tool endpoints, auth, guardrails, audit logging, OpenAPI export | Built and covered by the project's tests |
| IAM token exchange (API key → bearer token) | Follows IBM Cloud IAM documentation |
| Orchestrate chat REST path | **Unverified.** Configurable via `ORCHESTRATE_CHAT_PATH`; confirm in your instance's API reference |
| Agent YAML schema / `orchestrate` CLI commands | **Unverified.** The IBM docs available here did not cover the ADK. Use the agent builder UI if import fails |
| Real end-to-end run | Needs your Orchestrate instance and a public tool URL; not testable offline |

## Setup

1. **Pick secrets and start the backend**
   ```bash
   export AGENT_TOOL_API_KEY="$(openssl rand -hex 24)"
   export PUBLIC_BASE_URL="https://<your-public-url>"     # step 2
   ./venv/bin/uvicorn backend.app.main:app --port 8000
   ```
   With no `AGENT_TOOL_API_KEY` the tool endpoints return 401 (closed by default).

2. **Expose the backend publicly** (Orchestrate cloud cannot reach `localhost`), e.g.
   `ngrok http 8000`, and use the https URL as `PUBLIC_BASE_URL`.

3. **Get the OpenAPI spec for the tools**
   - Live: `GET $PUBLIC_BASE_URL/api/v1/agent-tools/spec` (its `servers[0].url` is `PUBLIC_BASE_URL`)
   - Or edit `servers[0].url` in [`malemitra_tools_openapi.json`](malemitra_tools_openapi.json).

4. **Import the tools into Orchestrate** (UI: *Add tool → Import from OpenAPI*, or the ADK CLI,
   e.g. `orchestrate tools import -k openapi -f malemitra_tools_openapi.json`; check
   `orchestrate tools import --help` for your version). When asked for authentication, choose
   **API key**, header name `X-API-Key`, value = your `AGENT_TOOL_API_KEY`.

5. **Create the agent** from [`malemitra_incident_agent.yaml`](malemitra_incident_agent.yaml)
   (or paste its description and instructions into the agent builder and attach the eight tools).
   Note the agent id.

6. **Point MaleMitra at Orchestrate**
   ```bash
   export ORCHESTRATE_API_KEY="<IBM Cloud API key>"
   export ORCHESTRATE_INSTANCE_URL="https://<your-orchestrate-instance-url>"
   export ORCHESTRATE_AGENT_ID="<agent id>"
   # only if your instance uses a different path:
   # export ORCHESTRATE_CHAT_PATH="/v1/orchestrate/{agent_id}/chat/completions"
   ```
   Restart the backend. Admin → *Agents* panel shows **Connected**, and each incident gets an
   **Ask Orchestrate agent** button.

## Tools

| Tool | Writes? | Purpose |
|---|---|---|
| `map_to_edge` | no | Snap lat/lon to the nearest road segment |
| `list_open_incidents` | no | Open incidents, optional status filter |
| `list_responder_availability` | no | Every responder, their team and whether they are free (no active field incident) |
| `get_incident_context` | no | Evidence, segment state, duplicates, previous recommendation |
| `compute_route` | no | Fastest vs risk-aware route scores |
| `estimate_bpr_load` | no | Volume/capacity and BPR delay (live TomTom if fresh) |
| `run_ripple_what_if` | no (sandboxed) | Trips affected if segments close (max 5) |
| `submit_recommendation` | appends one row | Records an action for admin review; never changes status. For `assign_team` it can carry `team_id` and a free `responder_id`; with no free responder it recommends the team queue |

## Guardrails

- Closed by default; constant-time `X-API-Key` comparison.
- `submit_recommendation` only accepts actions valid for the incident's current status (same gates as the human workflow).
- Input bounds: Bengaluru bounding box, ≤ 5 edges per what-if, rationale ≥ 10 characters, confidence 0–1.
- Every tool call, accepted or rejected, is written to `agent_events` (agent `watsonx_orchestrate`) and appears in the Agent Decision Timeline. Recommendations carry `requires_approval`.

## Deploying to IBM Code Engine (static URL)

The app URL `https://<app>.<uuid>.<region>.codeengine.appdomain.cloud` persists for the lifecycle of the
Code Engine **project** — do not delete the project. `app update` keeps the same URL.

```bash
ibmcloud login
ibmcloud target -r <region> -g <resource_group>
ibmcloud plugin install code-engine
ibmcloud ce project create --name malemitra          # also selects it

# Secrets (values from your local .env; the IBM key stays out of the image)
ibmcloud ce secret create --name malemitra-secrets \
  --from-literal AGENT_TOOL_API_KEY=<value> \
  --from-literal JWT_SECRET=<long random string> \
  --from-literal ORCHESTRATE_API_KEY=<IBM Cloud API key> \
  --from-literal ORCHESTRATE_INSTANCE_URL=<instance url> \
  --from-literal ORCHESTRATE_AGENT_ID=<agent id>

# Build (uses the Dockerfile) and deploy. Run from the project root.
ibmcloud ce app create --name malemitra --build-source . \
  --port 8000 --min-scale 1 --max-scale 1 \
  --env-from-secret malemitra-secrets \
  --env DEMO_MODE=true --env ALLOW_LEGACY_TOKENS=false

URL=$(ibmcloud ce app get --name malemitra --output url)
ibmcloud ce app update --name malemitra --env PUBLIC_BASE_URL=$URL
curl -s $URL/api/v1/agent-tools/spec > orchestrate/malemitra_tools_openapi.json   # re-import into Orchestrate
```

Notes:
- `--port 8000`: Code Engine assumes 8080 by default; this app listens on 8000.
- `--min-scale 1 --max-scale 1`: SQLite and the road-graph state are per-instance. Data resets on redeploy; demo incidents are re-seeded at startup.
- `ALLOW_LEGACY_TOKENS=false` is **required** on a public URL, otherwise `Authorization: Bearer usr-admin-1` grants admin.
- `.ceignore` keeps `.env`, `venv/`, `node_modules/` and the dev database out of the uploaded source.
- Redeploy after code changes: `ibmcloud ce app update --name malemitra --build-source .`
