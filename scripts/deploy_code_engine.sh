#!/usr/bin/env bash
# Deploy MaleMitra to IBM Code Engine as one public app (SQLite, public OSRM, live TomTom traffic).
# Idempotent: the first run creates the project, secret and app; later runs rebuild and update the app.
#
#   ibmcloud login --sso            # once
#   ibmcloud target -r jp-tok -g <resource_group>
#   ./scripts/deploy_code_engine.sh
#
# Secrets are read from ./.env and sent to a Code Engine secret. Nothing is printed except the URL.
set -euo pipefail
cd "$(dirname "$0")/.."

PROJECT="${CE_PROJECT:-malemitra}"
APP="${CE_APP:-malemitra}"
SECRET="${CE_SECRET:-malemitra-secrets}"

if ! ibmcloud target >/dev/null 2>&1 || ibmcloud target 2>&1 | grep -qi "not logged in"; then
  echo "Not logged in. Run: ibmcloud login --sso" >&2; exit 1
fi

envval() { grep -E "^$1=" .env 2>/dev/null | head -1 | cut -d= -f2- || true; }

ibmcloud ce project select --name "$PROJECT" >/dev/null 2>&1 || ibmcloud ce project create --name "$PROJECT" >/dev/null

if ! ibmcloud ce secret get --name "$SECRET" >/dev/null 2>&1; then
  JWT_SECRET="$(openssl rand -hex 32)"
  ADMIN_CODE="$(openssl rand -hex 5)"
  args=(--from-literal "JWT_SECRET=$JWT_SECRET" --from-literal "ADMIN_SIGNUP_CODE=$ADMIN_CODE")
  for k in TOMTOM_API_KEY AGENT_TOOL_API_KEY ORCHESTRATE_API_KEY ORCHESTRATE_INSTANCE_URL ORCHESTRATE_AGENT_ID; do
    v="$(envval "$k")"; [ -n "$v" ] && args+=(--from-literal "$k=$v")
  done
  ibmcloud ce secret create --name "$SECRET" "${args[@]}" >/dev/null
  echo "Created secret $SECRET. Admin sign-up code for this deployment: $ADMIN_CODE"
fi

# Demo mode on (one-click demo logins, seeded incidents) but with the public-URL hardening switched on.
COMMON=(--port 8000 --min-scale 1 --max-scale 1 --cpu 0.5 --memory 1G
        --env-from-secret "$SECRET"
        --env DEMO_MODE=true --env ALLOW_LEGACY_TOKENS=false --env EXPOSE_RESET_TOKEN=false
        --env WEB_CONCURRENCY=2 --env OSRM_VERIFY_TLS=true)

if ibmcloud ce app get --name "$APP" >/dev/null 2>&1; then
  ibmcloud ce app update --name "$APP" --build-source . --build-size medium "${COMMON[@]}"
else
  ibmcloud ce app create --name "$APP" --build-source . --build-size medium "${COMMON[@]}"
fi

URL="$(ibmcloud ce app get --name "$APP" --output url)"
ibmcloud ce app update --name "$APP" --env "PUBLIC_BASE_URL=$URL" --env "CORS_ORIGINS=$URL" >/dev/null
echo
echo "Deployed: $URL"
echo "Check:    curl -s $URL/api/v1/health"
