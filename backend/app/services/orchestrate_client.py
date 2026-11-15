"""
Client for IBM watsonx Orchestrate.

Flow: IBM Cloud API key -> IAM bearer token (cached) -> POST to the agent's chat endpoint.

What is verified vs. configurable:
* IAM token exchange (grant_type=urn:ibm:params:oauth:grant-type:apikey) follows IBM Cloud IAM docs.
* The agent chat path differs by Orchestrate edition/version, so it is read from
  settings.ORCHESTRATE_CHAT_PATH ({agent_id} is substituted). Confirm it against your
  instance's API reference. The request body is OpenAI-style chat messages and the
  reply parser accepts several common response shapes.
When credentials are missing the client reports `configured: False` and never makes a network call.
"""
import time
from typing import Any, Dict, List, Optional

import httpx

from backend.app.config import settings

IAM_GRANT = "urn:ibm:params:oauth:grant-type:apikey"
TOKEN_SAFETY_MARGIN_S = 60


class OrchestrateError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class OrchestrateClient:
    def __init__(self) -> None:
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0
        self.last_error: Optional[str] = None
        self.last_ok_at: Optional[float] = None

    # ── configuration ──────────────────────────────────────────────────────
    @staticmethod
    def missing_settings() -> List[str]:
        missing = []
        if not settings.ORCHESTRATE_API_KEY:
            missing.append("ORCHESTRATE_API_KEY")
        if not settings.ORCHESTRATE_INSTANCE_URL:
            missing.append("ORCHESTRATE_INSTANCE_URL")
        if not settings.ORCHESTRATE_AGENT_ID:
            missing.append("ORCHESTRATE_AGENT_ID")
        return missing

    def is_configured(self) -> bool:
        return not self.missing_settings()

    def status(self) -> Dict[str, Any]:
        missing = self.missing_settings()
        return {
            "configured": not missing,
            "missing_settings": missing,
            "tools_enabled": bool(settings.AGENT_TOOL_API_KEY),
            "agent_id": settings.ORCHESTRATE_AGENT_ID or None,
            "instance_url": settings.ORCHESTRATE_INSTANCE_URL or None,
            "tools_public_url": settings.PUBLIC_BASE_URL,
            "last_error": self.last_error,
            "last_ok_at": self.last_ok_at,
        }

    # ── auth ───────────────────────────────────────────────────────────────
    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expiry:
            return self._token
        # Orchestrate SaaS (api.<region>.watson-orchestrate.ibm.com) issues tokens from the
        # platform identity service: JSON body, token returned as "token". Classic IBM Cloud IAM
        # uses a form body and returns "access_token".
        platform_iam = "/apikeys/token" in settings.ORCHESTRATE_IAM_URL
        if platform_iam:
            request_kwargs = {"json": {"apikey": settings.ORCHESTRATE_API_KEY},
                              "headers": {"Accept": "application/json"}}
        else:
            request_kwargs = {"data": {"grant_type": IAM_GRANT, "apikey": settings.ORCHESTRATE_API_KEY},
                              "headers": {"Accept": "application/json",
                                          "Content-Type": "application/x-www-form-urlencoded"}}
        try:
            resp = httpx.post(settings.ORCHESTRATE_IAM_URL, timeout=settings.ORCHESTRATE_TIMEOUT_SECONDS,
                              **request_kwargs)
        except httpx.HTTPError as e:
            raise OrchestrateError(f"IAM token request failed: {e}")
        if resp.status_code != 200:
            raise OrchestrateError(f"IAM token request rejected ({resp.status_code}). Check ORCHESTRATE_API_KEY.", 401)
        body = resp.json()
        self._token = body["token"] if platform_iam else body["access_token"]
        self._token_expiry = time.time() + float(body.get("expires_in", 3600)) - TOKEN_SAFETY_MARGIN_S
        return self._token

    # ── chat ───────────────────────────────────────────────────────────────
    def chat(self, message: str) -> Dict[str, Any]:
        if not self.is_configured():
            raise OrchestrateError(
                f"watsonx Orchestrate is not configured (missing: {', '.join(self.missing_settings())}).", 503)
        try:
            token = self._get_token()
            url = settings.ORCHESTRATE_INSTANCE_URL + settings.ORCHESTRATE_CHAT_PATH.format(
                agent_id=settings.ORCHESTRATE_AGENT_ID)
            try:
                resp = httpx.post(
                    url,
                    json={"messages": [{"role": "user", "content": message}], "stream": False},
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                    timeout=settings.ORCHESTRATE_TIMEOUT_SECONDS,
                )
            except httpx.HTTPError as e:
                raise OrchestrateError(f"Orchestrate request failed: {e}")
            if resp.status_code == 401:
                self._token = None  # force a refresh next time
                raise OrchestrateError("Orchestrate rejected the access token (401).", 401)
            if resp.status_code >= 400:
                raise OrchestrateError(f"Orchestrate returned {resp.status_code}: {resp.text[:300]}")
            try:
                payload = resp.json()
            except ValueError:
                raise OrchestrateError("Orchestrate returned a non-JSON response.")
        except OrchestrateError as e:
            self.last_error = e.message
            raise
        self.last_error = None
        self.last_ok_at = time.time()
        return {"reply": self._extract_reply(payload), "raw": payload}

    @staticmethod
    def _extract_reply(payload: Any) -> str:
        """Pull the assistant text out of the response shapes Orchestrate-style APIs return."""
        if isinstance(payload, dict):
            choices = payload.get("choices")
            if choices and isinstance(choices, list):
                msg = choices[0].get("message") or {}
                if msg.get("content"):
                    return str(msg["content"])
            for key in ("output", "response", "reply", "message", "text", "content"):
                val = payload.get(key)
                if isinstance(val, str) and val:
                    return val
            if isinstance(payload.get("messages"), list) and payload["messages"]:
                last = payload["messages"][-1]
                if isinstance(last, dict) and last.get("content"):
                    return str(last["content"])
        return ""


orchestrate_client = OrchestrateClient()
