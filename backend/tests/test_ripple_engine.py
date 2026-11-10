import pytest
from backend.app.services.graph_service import road_graph
from backend.app.services.ripple_service import ripple_engine
from backend.app.services.eval_service import eval_harness

def test_ripple_engine_flow_assignment():
    sim = ripple_engine.run_simulation(seed=42, iterations=2, custom_blocked_edge_ids=["edge-7", "edge-8"])
    assert sim["total_trips"] == 150
    assert sim["affected_trips"] > 0
    assert len(sim["top_affected_edges"]) > 0
    assert sim["mean_detour_s"] >= 0.0
    assert sim["pct_travel_time_increase"] >= 0.0

def test_bpr_congestion_delay_function():
    # Base travel time 100s, flow 0 -> 100s
    t0 = 100.0
    t_zero = ripple_engine.calculate_bpr_travel_time(t0, flow=0, capacity=50)
    assert t_zero == 100.0
    
    # Over capacity (flow 100 vs capacity 50) -> delay increases
    t_over = ripple_engine.calculate_bpr_travel_time(t0, flow=100, capacity=50)
    assert t_over > 100.0

def test_evaluation_benchmark_harness():
    bench = eval_harness.run_benchmark(seed=42, blocked_edges=["edge-7", "edge-8"])
    assert bench["total_trips"] == 150
    assert bench["baseline_trips_crossing_blocked"] > 0
    assert bench["malemitra_trips_crossing_blocked"] == 0
    assert bench["blocked_traversal_reduction_pct"] == 100.0
    assert bench["detour_tradeoff_pct"] > 0.0
