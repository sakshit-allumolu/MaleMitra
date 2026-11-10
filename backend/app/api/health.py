from fastapi import APIRouter
from backend.app.services.graph_service import road_graph

router = APIRouter(tags=["health"])

@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "MaleMitra API",
        "graph_version": road_graph.graph_version,
        "nodes_count": len(road_graph.nodes),
        "edges_count": len(road_graph.edges),
        "mode": "modular_monolith"
    }
