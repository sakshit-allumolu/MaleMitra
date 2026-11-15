from fastapi import APIRouter
from fastapi.responses import JSONResponse
from backend.app.models.database import get_db_connection
from backend.app.services.graph_service import road_graph
from backend.app.services import tomtom_routing_service
from backend.app.services.live_traffic_service import live_traffic
from backend.app.services.ripple_service import ripple_engine

router = APIRouter(tags=["health"])

@router.get("/health")
def health_check():
    """Liveness + readiness: verifies the database answers and the road graph is loaded."""
    checks = {"database": False, "road_graph": bool(road_graph.edges)}
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        checks["database"] = True
    except Exception:
        pass
    healthy = all(checks.values())
    body = {
        "status": "healthy" if healthy else "unhealthy",
        "service": "MaleMitra API",
        "checks": checks,
        "graph_version": road_graph.graph_version,
        "nodes_count": len(road_graph.nodes),
        "edges_count": len(road_graph.edges),
        "mode": "modular_monolith"
    }
    return JSONResponse(body, status_code=200 if healthy else 503)

@router.get("/traffic/live")
def live_traffic_status():
    """Status of the TomTom live-traffic feed that drives BPR edge congestion."""
    return {**live_traffic.status(), "routing": tomtom_routing_service.status()}

@router.get("/simulations/latest")
def latest_ripple_result():
    """Most recent ripple result produced automatically when a road restriction changed."""
    return ripple_engine.latest() or {"detail": "No automatic ripple run yet."}
