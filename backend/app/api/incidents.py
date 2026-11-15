from fastapi import APIRouter, HTTPException, Depends, Query, Response
from backend.app.models.schemas import (
    ReportCreateRequest, ReviewRequest, AssignRequest, VerifyRequest,
    ProposeClearanceRequest, RestrictionRequest, UserRole, UserProfile
)
from backend.app.api.auth import get_current_user, require_role
from backend.app.services.incident_service import incident_service
from backend.app.config import settings
from backend.app.ratelimit import hit
from backend.app.services import upload_service

router = APIRouter(tags=["incidents"])

@router.post("/reports")
def create_report(req: ReportCreateRequest, user: UserProfile = Depends(get_current_user)):
    """FR-01: Citizen submits geotagged incident report (rate limited per account)."""
    hit("reports", user.id, settings.RATE_LIMIT_REPORTS_PER_HOUR, 3600)
    return incident_service.create_report(
        user_id=user.id,
        user_name=user.name,
        lat=req.lat,
        lon=req.lon,
        inc_type=req.type,
        severity=req.severity,
        description=req.description,
        evidence_note=req.evidence_note,
        photo_url=upload_service.claim(req.photo_id, user.id) or req.photo_url
    )

@router.get("/incidents")
def list_incidents(
    response: Response,
    limit: int = Query(1000, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: UserProfile = Depends(get_current_user),
):
    """Role-filtered incident list, newest first. Page with limit/offset; X-Total-Count has the total."""
    response.headers["X-Total-Count"] = str(incident_service.count_incidents())
    return incident_service.get_all_incidents(role=user.role, user_id=user.id, limit=limit, offset=offset)

@router.get("/incidents/{incident_id}")
def get_incident_detail(incident_id: str, user: UserProfile = Depends(get_current_user)):
    inc = incident_service.get_incident_by_id(incident_id, role=user.role)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc

@router.post("/incidents/{incident_id}/review")
def review_incident(
    incident_id: str, 
    req: ReviewRequest, 
    user: UserProfile = Depends(require_role([UserRole.ADMIN]))
):
    """Admin reviews and triages incident."""
    return incident_service.admin_review(
        incident_id=incident_id,
        admin_id=user.id,
        admin_name=user.name,
        notes=req.notes or "Reviewed by control room.",
        severity=req.initial_severity
    )

@router.post("/incidents/{incident_id}/assign")
def assign_team(
    incident_id: str, 
    req: AssignRequest, 
    user: UserProfile = Depends(require_role([UserRole.ADMIN]))
):
    """Admin assigns a response team, optionally a specific responder on it (else the team queue)."""
    return incident_service.admin_assign_team(
        incident_id=incident_id,
        admin_id=user.id,
        admin_name=user.name,
        team_id=req.team_id,
        notes=req.notes or "Dispatched field responder",
        responder_id=req.responder_id
    )

@router.post("/incidents/{incident_id}/claim")
def claim_incident(
    incident_id: str,
    user: UserProfile = Depends(require_role([UserRole.RESPONDER]))
):
    """A free responder takes an unclaimed incident from their team's queue."""
    return incident_service.claim_incident(
        incident_id=incident_id,
        responder_id=user.id,
        responder_name=user.name
    )

@router.post("/incidents/{incident_id}/verify")
def verify_incident(
    incident_id: str, 
    req: VerifyRequest, 
    user: UserProfile = Depends(require_role([UserRole.RESPONDER, UserRole.ADMIN]))
):
    """Responder verifies incident on-site with field findings."""
    return incident_service.responder_verify(
        incident_id=incident_id,
        responder_id=user.id,
        responder_name=user.name,
        findings=req.findings,
        water_depth_cm=req.water_depth_cm,
        is_impassable=req.is_impassable,
        recommended_action=req.recommended_action,
        evidence_note=req.evidence_note,
        photo_url=upload_service.claim(req.photo_id, user.id) or req.photo_url
    )

@router.post("/incidents/{incident_id}/clearance")
def propose_clearance(
    incident_id: str, 
    req: ProposeClearanceRequest, 
    user: UserProfile = Depends(require_role([UserRole.RESPONDER, UserRole.ADMIN]))
):
    """Responder recommends reopening and submits clearance evidence."""
    return incident_service.responder_propose_clearance(
        incident_id=incident_id,
        responder_id=user.id,
        responder_name=user.name,
        findings=req.clearance_findings,
        evidence_note=req.evidence_note
    )

@router.post("/incidents/{incident_id}/restriction")
def authorize_restriction(
    incident_id: str,
    req: RestrictionRequest,
    user: UserProfile = Depends(require_role([UserRole.ADMIN]))
):
    """Admin confirms road blockage or authorizes reopening. Increments graph_version."""
    return incident_service.admin_authorize_restriction(
        incident_id=incident_id,
        admin_id=user.id,
        admin_name=user.name,
        action=req.action,
        notes=req.notes
    )

@router.post("/incidents/{incident_id}/withdraw")
def withdraw_report(
    incident_id: str,
    user: UserProfile = Depends(get_current_user)
):
    """FR-01b: Citizen withdraws their own report (only while reported/under_review)."""
    return incident_service.withdraw_report(
        incident_id=incident_id,
        user_id=user.id
    )
