from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from backend.app.models.schemas import UserProfile, UserRole
from backend.app.api.auth import get_current_user, require_role
from backend.app.models.database import get_db_connection
from backend.app.services.incident_service import incident_service

router = APIRouter(prefix="/teams", tags=["teams"])

@router.get("")
def list_teams():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM response_teams")
    teams = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"teams": teams}

@router.get("/me/tasks")
def get_my_tasks(user: UserProfile = Depends(require_role([UserRole.RESPONDER, UserRole.ADMIN]))):
    """Responder views assigned tasks/incidents."""
    team_id = user.team_id or "team-alpha"
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM incidents WHERE assigned_team_id = ? AND status NOT IN ('cleared', 'rejected')", (team_id,))
    rows = cursor.fetchall()
    conn.close()
    
    tasks = []
    for r in rows:
        inc = incident_service.get_incident_by_id(r["id"], role=user.role)
        if inc:
            tasks.append(inc)
            
    return {"team_id": team_id, "tasks": tasks}

@router.post("/{team_id}/status")
def update_team_status(team_id: str, status: str, user: UserProfile = Depends(require_role([UserRole.ADMIN, UserRole.RESPONDER]))):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE response_teams SET status = ? WHERE id = ?", (status, team_id))
    conn.commit()
    conn.close()
    return {"team_id": team_id, "status": status}
