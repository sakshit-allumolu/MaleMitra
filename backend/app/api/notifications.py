from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.app.api.auth import require_role
from backend.app.models.database import get_db_connection
from backend.app.models.schemas import UserProfile, UserRole
from backend.app.services import notification_service
from backend.app.timeutil import utcnow

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/status")
def notification_status(user: UserProfile = Depends(require_role([UserRole.ADMIN]))):
    """Configured channels, dispatcher state and queue counts (control room only)."""
    return notification_service.stats()


@router.get("")
def list_notifications(status: Optional[str] = None, limit: int = 50,
                       user: UserProfile = Depends(require_role([UserRole.ADMIN]))):
    """Recent notifications (bodies omitted: password-reset messages contain one-time codes)."""
    limit = max(1, min(200, limit))
    conn = get_db_connection()
    q = ("SELECT id, user_id, channel, recipient, kind, subject, status, attempts, last_error, created_at, sent_at "
         "FROM notifications")
    args = []
    if status:
        q += " WHERE status = ?"
        args.append(status)
    rows = conn.execute(q + " ORDER BY created_at DESC LIMIT ?", (*args, limit)).fetchall()
    conn.close()
    return {"notifications": [dict(r) for r in rows]}


@router.post("/{notification_id}/retry")
def retry_notification(notification_id: str, user: UserProfile = Depends(require_role([UserRole.ADMIN]))):
    """Put a permanently failed notification back in the queue."""
    conn = get_db_connection()
    cur = conn.execute(
        "UPDATE notifications SET status = 'pending', attempts = 0, next_attempt_at = ?, "
        "lease_until = NULL, last_error = NULL WHERE id = ? AND status = 'failed'",
        (utcnow().isoformat(), notification_id))
    conn.commit()
    changed = cur.rowcount
    conn.close()
    if not changed:
        raise HTTPException(status_code=404, detail="No failed notification with that id.")
    return {"id": notification_id, "status": "pending"}
