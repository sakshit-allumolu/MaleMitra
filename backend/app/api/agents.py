from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.api.auth import get_current_user, require_role
from backend.app.models.schemas import UserProfile, UserRole
from backend.app.services import agent_tools_service as tools
from backend.app.services import recommendation_service
from backend.app.services.incident_service import IncidentService
from backend.app.services.orchestrate_client import OrchestrateError, orchestrate_client

router = APIRouter(prefix="/agents", tags=["agents"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class DecisionRequest(BaseModel):
    decision: Literal["approve", "dismiss"]
    notes: Optional[str] = Field(None, max_length=500)
    team_id: Optional[str] = Field(None, description="assign_team: team to dispatch. Defaults to the recommended team.")
    responder_id: Optional[str] = Field(
        None, description="assign_team: responder on that team. Omit for the team queue. "
                          "Only used when team_id is sent; otherwise the recommended responder is used.")


@router.get("/status")
def agents_status(user: UserProfile = Depends(get_current_user)):
    """Connection state of the watsonx Orchestrate agent and its tools (no secrets)."""
    return {**orchestrate_client.status(), "tools": sorted(tools.TOOLS)}


@router.post("/chat")
def agents_chat(req: ChatRequest, user: UserProfile = Depends(require_role([UserRole.ADMIN]))):
    """Free-form question to the Orchestrate agent (admin only)."""
    try:
        res = orchestrate_client.chat(req.message)
    except OrchestrateError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return {"reply": res["reply"]}


@router.post("/analyze/{incident_id}")
def agents_analyze(incident_id: str, user: UserProfile = Depends(require_role([UserRole.ADMIN]))):
    """
    Ask the Orchestrate agent to analyse one incident. The agent calls our tools
    (get_incident_context, run_ripple_what_if, ...) and ends with submit_recommendation,
    which is stored for the admin to approve or ignore.
    """
    if not IncidentService.get_incident_by_id(incident_id, role="admin"):
        raise HTTPException(status_code=404, detail="Incident not found.")
    prompt = (
        f"Analyse MaleMitra incident {incident_id}. Use get_incident_context first, then any other tools you need "
        f"(for example run_ripple_what_if or estimate_bpr_load). If the incident is under_review and needs a team, call "
        f"list_responder_availability and recommend assign_team with a free responder's responder_id, or with only a "
        f"team_id (team queue) when nobody is free. Finish by calling submit_recommendation with a single "
        f"action that is valid for the incident's current status. You only recommend; a human admin decides."
    )
    try:
        res = orchestrate_client.chat(prompt)
    except OrchestrateError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return {
        "reply": res["reply"],
        "recommendation": tools.latest_recommendation(incident_id),
    }


@router.get("/recommendation/{incident_id}")
def agents_recommendation(incident_id: str, user: UserProfile = Depends(require_role([UserRole.ADMIN]))):
    """Most recent agent recommendation for an incident (null if none)."""
    return {"recommendation": tools.latest_recommendation(incident_id)}


@router.post("/recommendations/{event_id}/decision")
def agents_recommendation_decision(
    event_id: str, req: DecisionRequest, user: UserProfile = Depends(require_role([UserRole.ADMIN]))
):
    """
    Admin approves or dismisses an agent recommendation. Approving runs the matching workflow
    action (with its normal gates and audit trail); dismissing changes nothing but the record.
    """
    return recommendation_service.decide(
        event_id, req.decision, admin_id=user.id, admin_name=user.name, notes=req.notes,
        team_id=req.team_id, responder_id=req.responder_id)
