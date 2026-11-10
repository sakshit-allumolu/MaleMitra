#!/usr/bin/env python3
"""
MaleMitra (ಮಳೆ ಮಿತ್ರ) - Reproducible Benchmark & Evaluation Harness
Executes seeded comparative simulation comparing Baseline Blind Shortest Path vs MaleMitra Risk & Ripple-Aware Routing.
"""
import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.eval_service import eval_harness

def main():
    print("=" * 70)
    print("MALEMITRA (ಮಳೆ ಮಿತ್ರ) | BOBATHON 2026 BENCHMARK EVALUATION")
    print("Bounded Bengaluru Road Network: Koramangala / Indiranagar / Domlur Corridor")
    print("=" * 70)
    
    result = eval_harness.run_benchmark(seed=42)
    
    print(f"\nScenario: {result['scenario_name']}")
    print(f"Total Modeled Trips: {result['total_trips']}")
    print(f"Blocked Disruption Corridor: {', '.join(result['blocked_corridor'])}\n")
    
    print("-" * 70)
    print(f"{'Metric':<40} | {'Baseline':<12} | {'MaleMitra':<12}")
    print("-" * 70)
    print(f"{'Trips crossing blocked road':<40} | {result['baseline_trips_crossing_blocked']:<12} | {result['malemitra_trips_crossing_blocked']:<12}")
    print(f"{'Blocked edge exposure rate':<40} | {str(result['baseline_pct_blocked'])+'%':<12} | {str(result['malemitra_pct_blocked'])+'%':<12}")
    print(f"{'Mean journey time':<40} | {str(result['baseline_mean_trip_time_s'])+'s':<12} | {str(result['malemitra_mean_trip_time_s'])+'s':<12}")
    print(f"{'Mean detour cost':<40} | {'0.0s':<12} | {str(result['mean_detour_s'])+'s':<12}")
    print("-" * 70)
    print(f"\n★ Primary Metric Result:")
    print(f"  -> Reduction in modeled journeys crossing blocked segment: {result['blocked_traversal_reduction_pct']}%")
    print(f"  -> Detour trade-off: +{result['mean_detour_s']}s (+{result['detour_tradeoff_pct']}%)")
    print(f"  -> Evaluation Runtime: {result['evaluation_runtime_ms']} ms")
    print("\nBenchmark results written to:")
    print("  - backend/app/data/benchmark_results.json")
    print("  - backend/app/data/benchmark_results.csv")
    print("=" * 70)

if __name__ == "__main__":
    main()
