from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List
from backend.app.models.schemas import SimulationRunCreate, RippleImpactResponse, UserRole, UserProfile
from backend.app.api.auth import require_role, get_current_user
from backend.app.config import settings
from backend.app.ratelimit import hit
from backend.app.services.graph_service import road_graph
from backend.app.services.ripple_service import ripple_engine
from backend.app.services.eval_service import eval_harness

router = APIRouter(prefix="/simulations", tags=["simulations"])


class InjectRequest(BaseModel):
    edge_ids: List[str] = Field(..., min_length=1, max_length=20)


def _throttle(user: UserProfile) -> None:
    hit("simulation", user.id, settings.RATE_LIMIT_SIMULATIONS_PER_MIN, 60)


@router.post("", response_model=RippleImpactResponse)
def create_simulation_run(
    req: SimulationRunCreate,
    user: UserProfile = Depends(get_current_user)
):
    """All authenticated users can run read-only what-if simulations (rate limited).
    Only admins/responders can apply real graph blockages via the incidents workflow."""
    _throttle(user)
    if req.custom_blocked_edge_ids:
        unknown = [e for e in req.custom_blocked_edge_ids if e not in road_graph.edges]
        if unknown:
            raise HTTPException(status_code=422, detail=f"Unknown edge ids: {unknown}")
    return ripple_engine.run_simulation(
        seed=req.seed,
        iterations=req.iterations,
        custom_blocked_edge_ids=req.custom_blocked_edge_ids,
        trip_count=req.trip_count
    )

@router.post("/{run_id}/inject")
def inject_disruption(
    run_id: str,
    req: InjectRequest,
    user: UserProfile = Depends(require_role([UserRole.ADMIN]))
):
    """Admin injects simulated disruption into road network and returns ripple impact."""
    _throttle(user)
    unknown = [e for e in req.edge_ids if e not in road_graph.edges]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown edge ids: {unknown}")
    return ripple_engine.run_simulation(seed=42, iterations=2, custom_blocked_edge_ids=req.edge_ids)

@router.get("/{run_id}/impact")
def get_ripple_impact(run_id: str, user: UserProfile = Depends(get_current_user)):
    """Retrieve current ripple impact metrics."""
    _throttle(user)
    return ripple_engine.run_simulation(seed=42, iterations=2)

@router.get("/benchmark/run")
def run_evaluation_benchmark(user: UserProfile = Depends(require_role([UserRole.ADMIN]))):
    """FR-10: Reproducible evaluation harness comparing Baseline vs MaleMitra."""
    _throttle(user)
    return eval_harness.run_benchmark(seed=42)
