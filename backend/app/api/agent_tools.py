"""
REST surface that watsonx Orchestrate calls as agent tools.

Auth: a shared secret in the `X-API-Key` header (settings.AGENT_TOOL_API_KEY).
Tools are closed by default - with no key configured every call is rejected.
The OpenAPI document served at /agent-tools/spec contains only these
operations (operationId == tool name) so it can be imported into Orchestrate.
"""
import logging
import secrets
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from backend.app.config import settings
from backend.app.services import agent_tools_service as tools

router = APIRouter(prefix="/agent-tools", tags=["agent-tools"])
log = logging.getLogger("malemitra.agent_tools")


def require_agent_key(x_api_key: Optional[str] = Header(None)) -> None:
    configured = settings.AGENT_TOOL_API_KEY
    if not configured:
        raise HTTPException(status_code=401, detail="Agent tools are disabled: AGENT_TOOL_API_KEY is not configured.")
    if not x_api_key or not secrets.compare_digest(x_api_key, configured):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key.")


def _run(tool: str, **kwargs):
    try:
        return tools.invoke(tool, **kwargs)
    except tools.ToolError as e:
        # Orchestrate shows any non-2xx to the user as a generic tool failure; keep the real reason in our log.
        log.warning("tool %s rejected: %s (%s) args=%r", tool, e.code, e.message, {k: str(v)[:80] for k, v in kwargs.items()})
        raise HTTPException(status_code=422, detail={"error": e.code, "message": e.message})


class MapToEdgeRequest(BaseModel):
    lat: float = Field(..., description="Latitude of the reported location (Bengaluru service area).")
    lon: float = Field(..., description="Longitude of the reported location (Bengaluru service area).")


class ListIncidentsRequest(BaseModel):
    status: Optional[str] = Field(
        None, description="Optional filter: reported, under_review, assigned, field_verified, blocked or clearance_proposed.")


class IncidentRequest(BaseModel):
    incident_id: str = Field(..., description="Incident id, e.g. inc-1a2b3c4d.")


class RouteRequest(BaseModel):
    origin_lat: float
    origin_lon: float
    dest_lat: float
    dest_lon: float


class EdgeRequest(BaseModel):
    edge_id: str = Field(..., description="Road segment id, e.g. edge-7.")


class WhatIfRequest(BaseModel):
    edge_ids: List[str] = Field(..., description="Road segment ids to simulate as closed (max 5).")


class ResponderAvailabilityRequest(BaseModel):
    team_id: Optional[str] = Field(None, description="Optional: only responders on this team, e.g. team-alpha.")


class RecommendationRequest(BaseModel):
    incident_id: str
    action: str = Field(
        ..., description="One of: request_triage, assign_team, reject_duplicate, request_field_verification, "
                         "propose_block, propose_reopen, monitor, escalate. Must be valid for the incident's current status.")
    rationale: str = Field(..., description="Evidence-based reasoning for a human admin (min 10 chars).")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Your confidence in this recommendation, 0 to 1.")
    team_id: Optional[str] = Field(None, description="assign_team only: the team to dispatch.")
    responder_id: Optional[str] = Field(
        None, description="assign_team only: a FREE responder from list_responder_availability. "
                          "Omit it when nobody is free so the incident goes to the team queue.")


@router.post("/map_to_edge", operation_id="map_to_edge", dependencies=[Depends(require_agent_key)],
             summary="map_to_edge")
def map_to_edge(req: MapToEdgeRequest):
    """Snap a latitude/longitude to the nearest modelled road segment. Read-only."""
    return _run("map_to_edge", lat=req.lat, lon=req.lon)


@router.post("/list_open_incidents", operation_id="list_open_incidents", dependencies=[Depends(require_agent_key)],
             summary="list_open_incidents")
def list_open_incidents(req: Optional[ListIncidentsRequest] = None):
    """List incidents that are not yet cleared or rejected, optionally filtered by status. Read-only."""
    # The agent sends no body when it has no filter, so the body is optional.
    return _run("list_open_incidents", status=req.status if req else None)


@router.post("/list_responder_availability", operation_id="list_responder_availability",
             dependencies=[Depends(require_agent_key)], summary="list_responder_availability")
def list_responder_availability(req: Optional[ResponderAvailabilityRequest] = None):
    """Every active responder with team and is_free flag, to choose who should take an incident. Read-only."""
    return _run("list_responder_availability", team_id=req.team_id if req else None)


@router.post("/get_incident_context", operation_id="get_incident_context", dependencies=[Depends(require_agent_key)],
             summary="get_incident_context")
def get_incident_context(req: IncidentRequest):
    """Incident details, evidence, road segment state, other open incidents on the same segment and any previous recommendation. Read-only."""
    return _run("get_incident_context", incident_id=req.incident_id)


@router.post("/compute_route", operation_id="compute_route", dependencies=[Depends(require_agent_key)],
             summary="compute_route")
def compute_route(req: RouteRequest):
    """Risk scores, duration and blocked-road crossings for fastest / risk-aware / alternative routes. Read-only."""
    return _run("compute_route", origin_lat=req.origin_lat, origin_lon=req.origin_lon,
                dest_lat=req.dest_lat, dest_lon=req.dest_lon)


@router.post("/estimate_bpr_load", operation_id="estimate_bpr_load", dependencies=[Depends(require_agent_key)],
             summary="estimate_bpr_load")
def estimate_bpr_load(req: EdgeRequest):
    """Volume/capacity and BPR travel-time delay for a segment, from live traffic when fresh else the ripple simulation. Read-only."""
    return _run("estimate_bpr_load", edge_id=req.edge_id)


@router.post("/run_ripple_what_if", operation_id="run_ripple_what_if", dependencies=[Depends(require_agent_key)],
             summary="run_ripple_what_if")
def run_ripple_what_if(req: WhatIfRequest):
    """Sandboxed what-if: how many trips are affected and which neighbouring roads absorb the traffic. Does not change live road state."""
    return _run("run_ripple_what_if", edge_ids=req.edge_ids)


@router.post("/submit_recommendation", operation_id="submit_recommendation", dependencies=[Depends(require_agent_key)],
             summary="submit_recommendation")
def submit_recommendation(req: RecommendationRequest):
    """Record a recommended next action for an incident. It never changes incident status or closes a road; a human admin must act on it."""
    return _run("submit_recommendation", incident_id=req.incident_id, action=req.action,
                rationale=req.rationale, confidence=req.confidence,
                team_id=req.team_id, responder_id=req.responder_id)


def build_agent_openapi(full: dict) -> dict:
    """Filter the app's OpenAPI document down to the agent tools only."""
    prefix = f"{settings.API_PREFIX}/agent-tools/"
    paths = {p: item for p, item in full.get("paths", {}).items() if p.startswith(prefix)}
    return {
        "openapi": full.get("openapi", "3.1.0"),
        "info": {
            "title": "MaleMitra Agent Tools",
            "version": settings.VERSION,
            "description": "Tools for the MaleMitra monsoon incident-response agent. All calls require the X-API-Key header.",
        },
        "servers": [{"url": settings.PUBLIC_BASE_URL.rstrip("/")}],
        "paths": paths,
        "components": {
            "schemas": full.get("components", {}).get("schemas", {}),
            "securitySchemes": {"ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"}},
        },
        "security": [{"ApiKeyAuth": []}],
    }


@router.get("/spec", include_in_schema=False)
def agent_tools_spec(request: Request):
    """OpenAPI document containing only the agent tools, ready to import into Orchestrate."""
    return build_agent_openapi(request.app.openapi())
