from fastapi import APIRouter, Depends
from backend.app.models.schemas import RouteCompareRequest, RouteCompareResponse, UserProfile
from backend.app.api.auth import get_current_user
from backend.app.services.agent_service import agent_orchestrator
from backend.app.services.graph_service import road_graph

router = APIRouter(prefix="/routes", tags=["routes"])

@router.post("/compare", response_model=RouteCompareResponse)
def compare_routes(req: RouteCompareRequest, user: UserProfile = Depends(get_current_user)):
    """FR-06: Fastest and risk-aware route comparison."""
    res = agent_orchestrator.compare_routes(
        origin_lat=req.origin.lat,
        origin_lon=req.origin.lon,
        dest_lat=req.destination.lat,
        dest_lon=req.destination.lon,
        user_id=user.id
    )
    return res

@router.get("/network")
def get_road_network():
    """Returns nodes and road segment edges for map rendering."""
    nodes_list = list(road_graph.nodes.values())
    edges_list = [e.to_dict() for e in road_graph.edges.values()]
    return {
        "graph_version": road_graph.graph_version,
        "nodes": nodes_list,
        "edges": edges_list
    }
