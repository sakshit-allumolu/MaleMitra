from fastapi import APIRouter, Depends, HTTPException
from typing import Literal
from backend.app.models.schemas import UserProfile, UserRole
from backend.app.api.auth import get_current_user, require_role
from backend.app.models.database import get_db_connection
from backend.app.services.incident_service import incident_service

router = APIRouter(prefix="/teams", tags=["teams"])

@router.get("")
def list_teams(user: UserProfile = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM response_teams")
    teams = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"teams": teams}

@router.get("/responders")
def list_responders(user: UserProfile = Depends(require_role([UserRole.ADMIN]))):
    """Admin view: every responder, their team and whether they are free right now."""
    return {"responders": incident_service.get_responder_availability()}

@router.get("/me/tasks")
def get_my_tasks(user: UserProfile = Depends(require_role([UserRole.RESPONDER, UserRole.ADMIN]))):
    """Responder views their own tasks and their team's unclaimed queue."""
    team_id = user.team_id or "team-alpha"
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, assigned_responder_id FROM incidents WHERE assigned_team_id = ? AND status NOT IN ('cleared', 'rejected')", (team_id,))
    rows = cursor.fetchall()
    conn.close()
    
    tasks, queue = [], []
    for r in rows:
        inc = incident_service.get_incident_by_id(r["id"], role=user.role)
        if not inc:
            continue
        if r["assigned_responder_id"] is None:
            queue.append(inc)
        elif r["assigned_responder_id"] == user.id:
            tasks.append(inc)

    me = next((r for r in incident_service.get_responder_availability(team_id) if r["id"] == user.id), None)
    return {"team_id": team_id, "tasks": tasks, "queue": queue, "is_free": me["is_free"] if me else False}

@router.post("/{team_id}/status")
def update_team_status(
    team_id: str,
    status: Literal["available", "dispatched", "offline"],
    user: UserProfile = Depends(require_role([UserRole.ADMIN, UserRole.RESPONDER]))
):
    """Admins may update any team; a responder only their own."""
    if user.role == UserRole.RESPONDER and user.team_id != team_id:
        raise HTTPException(status_code=403, detail="Responders can only update their own team.")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE response_teams SET status = ? WHERE id = ?", (status, team_id))
    updated = cursor.rowcount
    conn.commit()
    conn.close()
    if not updated:
        raise HTTPException(status_code=404, detail="Team not found.")
    return {"team_id": team_id, "status": status}
