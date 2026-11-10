from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from backend.app.models.schemas import SimulationRunCreate, RippleImpactResponse, UserRole, UserProfile
from backend.app.api.auth import require_role, get_current_user
from backend.app.services.ripple_service import ripple_engine
from backend.app.services.eval_service import eval_harness

router = APIRouter(prefix="/simulations", tags=["simulations"])

@router.post("", response_model=RippleImpactResponse)
def create_simulation_run(
    req: SimulationRunCreate,
    user: UserProfile = Depends(get_current_user)
):
    """All authenticated users can run read-only what-if simulations.
    Only admins/responders can apply real graph blockages via the incidents workflow."""
    res = ripple_engine.run_simulation(
        seed=req.seed,
        iterations=req.iterations,
        custom_blocked_edge_ids=req.custom_blocked_edge_ids,
        trip_count=req.trip_count
    )
    return res

@router.post("/{run_id}/inject")
def inject_disruption(
    run_id: str,
    edge_ids: List[str],
    user: UserProfile = Depends(require_role([UserRole.ADMIN]))
):
    """Admin injects simulated disruption into road network and returns ripple impact."""
    res = ripple_engine.run_simulation(
        seed=42,
        iterations=2,
        custom_blocked_edge_ids=edge_ids
    )
    return res

@router.get("/{run_id}/impact")
def get_ripple_impact(run_id: str):
    """Retrieve current ripple impact metrics."""
    return ripple_engine.run_simulation(seed=42, iterations=2)

@router.get("/benchmark/run")
def run_evaluation_benchmark():
    """FR-10: Reproducible evaluation harness comparing Baseline vs MaleMitra."""
    return eval_harness.run_benchmark(seed=42)
