import asyncio
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from backend.app.services.agent_service import agent_orchestrator
from backend.app.services.graph_service import road_graph

router = APIRouter(prefix="/events", tags=["events"])

@router.get("/agent")
def get_agent_events():
    """FR-09: Agent event timeline with structured tool decisions."""
    return {"events": agent_orchestrator.get_recent_agent_events(limit=50)}

@router.get("/audit")
def get_audit_events():
    """Audit trail of status changes, verifications and restrictions."""
    return {"audits": agent_orchestrator.get_recent_audit_events(limit=50)}

@router.get("/stream")
async def event_stream():
    """FR-08: Server-Sent Events (SSE) live updates for all workspaces."""
    async def event_generator():
        last_version = road_graph.graph_version
        while True:
            current_version = road_graph.graph_version
            events = agent_orchestrator.get_recent_agent_events(limit=5)
            payload = {
                "graph_version": current_version,
                "version_changed": (current_version != last_version),
                "latest_agent_event": events[0] if events else None,
                "active_blocked_edges": [e.edge_id for e in road_graph.edges.values() if e.is_blocked]
            }
            last_version = current_version
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(2.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
