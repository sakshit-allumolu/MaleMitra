import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from backend.app import shared
from backend.app.api.auth import require_role
from backend.app.config import settings
from backend.app.models.schemas import UserRole, UserProfile
from backend.app.services.agent_service import agent_orchestrator
from backend.app.services.graph_service import road_graph

router = APIRouter(prefix="/events", tags=["events"])

_sse_clients = 0

@router.get("/agent")
def get_agent_events(user: UserProfile = Depends(require_role([UserRole.ADMIN]))):
    """FR-09: Agent event timeline with structured tool decisions (control room only)."""
    return {"events": agent_orchestrator.get_recent_agent_events(limit=50)}

@router.get("/audit")
def get_audit_events(user: UserProfile = Depends(require_role([UserRole.ADMIN]))):
    """Audit trail of status changes, verifications and restrictions (control room only)."""
    return {"audits": agent_orchestrator.get_recent_audit_events(limit=50)}

@router.get("/stream")
async def event_stream(request: Request):
    """
    FR-08: Server-Sent Events live updates. Browsers cannot send auth headers on EventSource, so this
    stream carries only public road-network state (the same data as GET /routes/network) and does no
    database work. Concurrent clients are capped and disconnects free their slot.
    """
    global _sse_clients
    if _sse_clients >= settings.MAX_SSE_CLIENTS:
        raise HTTPException(status_code=503, detail="Too many live-update connections.")

    async def event_generator():
        global _sse_clients
        _sse_clients += 1
        try:
            last_version = road_graph.graph_version
            while True:
                if await request.is_disconnected():
                    break
                if settings.SHARED_SYNC_ENABLED:
                    try:
                        await run_in_threadpool(shared.sync_graph)
                    except Exception:
                        pass  # keep streaming the last known state
                current_version = road_graph.graph_version
                payload = {
                    "graph_version": current_version,
                    "version_changed": (current_version != last_version),
                    "active_blocked_edges": [e.edge_id for e in road_graph.edges.values() if e.is_blocked]
                }
                last_version = current_version
                yield f"data: {json.dumps(payload)}\n\n"
                await asyncio.sleep(2.5)
        finally:
            _sse_clients -= 1

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
