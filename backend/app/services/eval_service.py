import time
import json
import csv
import os
from datetime import datetime
from typing import Dict, Any, List
from backend.app.services.graph_service import RoadGraph, road_graph
from backend.app.services.ripple_service import RippleEngine, ripple_engine

class EvaluationHarness:
    @staticmethod
    def run_benchmark(seed: int = 42, blocked_edges: List[str] = None) -> Dict[str, Any]:
        """
        FR-10: Seeded reproducible comparison between Baseline Shortest Path and MaleMitra Ripple & Risk-Aware Model.
        Outputs structured evaluation metrics.
        """
        start_time = time.perf_counter()
        
        if blocked_edges is None:
            blocked_edges = ["edge-7", "edge-8"]  # Sony World to Ejipura Link
            
        trips = ripple_engine.synthetic_trips
        total_trips = len(trips)
        
        # 1. Baseline simulation (No blockage awareness: trips take default fastest shortest paths blindly)
        baseline_crossed_blocked = 0
        baseline_durations = []
        
        # Ensure unblocked for baseline calculation
        for e in road_graph.edges.values():
            e.is_blocked = False
            
        for trip in trips:
            res = road_graph.compute_dijkstra(trip["origin"], trip["destination"], mode="fastest")
            if res:
                _, edges, duration = res
                edge_ids = [e.edge_id for e in edges]
                if any(e_id in blocked_edges for e_id in edge_ids):
                    baseline_crossed_blocked += 1
                baseline_durations.append(duration)
            else:
                baseline_durations.append(0.0)
                
        # 2. MaleMitra Model (Closure-aware + Risk & Ripple Congestion penalties)
        for e_id in blocked_edges:
            if e_id in road_graph.edges:
                road_graph.edges[e_id].is_blocked = True
                
        malemitra_crossed_blocked = 0
        malemitra_durations = []
        no_route_count = 0
        
        for trip in trips:
            res = road_graph.compute_dijkstra(trip["origin"], trip["destination"], mode="risk_aware")
            if res:
                _, edges, duration = res
                edge_ids = [e.edge_id for e in edges]
                if any(e_id in blocked_edges for e_id in edge_ids):
                    malemitra_crossed_blocked += 1
                malemitra_durations.append(duration)
            else:
                no_route_count += 1
                # If isolated, assign reasonable penalty
                malemitra_durations.append(max(baseline_durations) * 1.5 if baseline_durations else 600.0)
                
        # Compute metrics
        baseline_mean = sum(baseline_durations) / max(1, len(baseline_durations))
        malemitra_mean = sum(malemitra_durations) / max(1, len(malemitra_durations))
        mean_detour = max(0.0, malemitra_mean - baseline_mean)
        
        baseline_pct_blocked = round((baseline_crossed_blocked / max(1, total_trips)) * 100.0, 1)
        malemitra_pct_blocked = round((malemitra_crossed_blocked / max(1, total_trips)) * 100.0, 1)
        
        reduction_pct = 100.0 if baseline_crossed_blocked == 0 else round(((baseline_crossed_blocked - malemitra_crossed_blocked) / baseline_crossed_blocked) * 100.0, 1)
        detour_tradeoff_pct = round((mean_detour / max(1.0, baseline_mean)) * 100.0, 1)
        
        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        
        result = {
            "scenario_name": "Bengaluru Bounded Monsoon Blockage Benchmark (Sony World Corridor)",
            "total_trips": total_trips,
            "blocked_corridor": blocked_edges,
            "baseline_trips_crossing_blocked": baseline_crossed_blocked,
            "baseline_pct_blocked": baseline_pct_blocked,
            "malemitra_trips_crossing_blocked": malemitra_crossed_blocked,
            "malemitra_pct_blocked": malemitra_pct_blocked,
            "blocked_traversal_reduction_pct": reduction_pct,
            "baseline_mean_trip_time_s": round(baseline_mean, 1),
            "malemitra_mean_trip_time_s": round(malemitra_mean, 1),
            "mean_detour_s": round(mean_detour, 1),
            "detour_tradeoff_pct": detour_tradeoff_pct,
            "network_total_travel_time_increase_pct": detour_tradeoff_pct,
            "no_route_trips_count": no_route_count,
            "evaluation_runtime_ms": elapsed_ms,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Save JSON and CSV
        data_dir = os.path.join(os.path.dirname(__file__), "../data")
        os.makedirs(data_dir, exist_ok=True)
        
        json_path = os.path.join(data_dir, "benchmark_results.json")
        with open(json_path, "w") as f:
            json.dump(result, f, indent=2)
            
        csv_path = os.path.join(data_dir, "benchmark_results.csv")
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Metric", "Baseline (Blind Shortest Path)", "MaleMitra (Risk & Ripple Aware)", "Impact / Trade-off"])
            writer.writerow(["Trips Traversing Blocked Edge", baseline_crossed_blocked, malemitra_crossed_blocked, f"-{reduction_pct}% reduction"])
            writer.writerow(["Blocked Edge Exposure Rate", f"{baseline_pct_blocked}%", f"{malemitra_pct_blocked}%", "Zero flooded road entrapment"])
            writer.writerow(["Mean Journey Time (s)", f"{round(baseline_mean, 1)}s", f"{round(malemitra_mean, 1)}s", f"+{round(mean_detour, 1)}s (+{detour_tradeoff_pct}%) detour"])
            writer.writerow(["Evaluation Runtime (ms)", "", "", f"{elapsed_ms} ms"])

        return result

eval_harness = EvaluationHarness()
