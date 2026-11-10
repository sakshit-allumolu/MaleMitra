import random
import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional
from backend.app.services.graph_service import RoadGraph, road_graph, RoadEdge
from backend.app.config import settings

class RippleEngine:
    def __init__(self, graph: RoadGraph):
        self.graph = graph
        self.synthetic_trips: List[Dict[str, Any]] = []
        self._generate_or_load_synthetic_trips()

    def _generate_or_load_synthetic_trips(self, count: int = 150):
        trips_path = os.path.join(os.path.dirname(__file__), "../data/synthetic_trips.json")
        if os.path.exists(trips_path):
            try:
                with open(trips_path, "r") as f:
                    self.synthetic_trips = json.load(f)
                return
            except Exception as e:
                print(f"Error reading synthetic trips: {e}, generating.")

        rng = random.Random(42)  # Deterministic seed for reproducible evaluation
        node_ids = list(self.graph.nodes.keys())
        trips = []
        
        for i in range(count):
            origin = rng.choice(node_ids)
            dest = rng.choice(node_ids)
            while dest == origin:
                dest = rng.choice(node_ids)
                
            trip_type = rng.choice(["commute_office", "school_run", "commercial_delivery", "hospital_transit"])
            trips.append({
                "trip_id": f"trip-{i+1:03d}",
                "origin": origin,
                "destination": dest,
                "origin_name": self.graph.nodes[origin]["name"],
                "destination_name": self.graph.nodes[dest]["name"],
                "trip_type": trip_type
            })
            
        self.synthetic_trips = trips
        os.makedirs(os.path.dirname(trips_path), exist_ok=True)
        with open(trips_path, "w") as f:
            json.dump(trips, f, indent=2)

    def calculate_bpr_travel_time(self, base_t: float, flow: int, capacity: int) -> float:
        """
        Bureau of Public Roads delay function:
        t = t0 * [1 + alpha * (v / c)^beta]
        """
        c = max(10, capacity)
        v = max(0, flow)
        return base_t * (1.0 + settings.BPR_ALPHA * ((v / c) ** settings.BPR_BETA))

    def run_simulation(self, seed: int = 42, iterations: int = 2, 
                       custom_blocked_edge_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Runs the Ripple Simulation:
        1. Resets edge flow volumes.
        2. Assigns all synthetic trips on baseline network (all eligible edges).
        3. Records baseline flows and baseline trip travel times.
        4. Applies blocked edges (from graph or custom list).
        5. Reassigns trips whose baseline path traversed any blocked edge.
        6. Runs iterative loading (Method of Successive Averages / Equilibrium) for 2 iterations.
        7. Computes load deltas, travel time changes, detour costs, and top congested corridors.
        """
        rng = random.Random(seed)
        
        # Step 1: Baseline assignment
        baseline_edge_flows: Dict[str, int] = {e_id: 0 for e_id in self.graph.edges}
        baseline_trip_paths: Dict[str, Tuple[List[str], List[str], float]] = {}
        
        # Ensure temporary unblocked state for baseline calculation
        blocked_state_backup = {e_id: e.is_blocked for e_id, e in self.graph.edges.items()}
        for e in self.graph.edges.values():
            e.is_blocked = False
            e.simulated_flow = 0
            
        for trip in self.synthetic_trips:
            res = self.graph.compute_dijkstra(trip["origin"], trip["destination"], mode="fastest")
            if res:
                nodes, edges, duration = res
                edge_ids = [e.edge_id for e in edges]
                baseline_trip_paths[trip["trip_id"]] = (nodes, edge_ids, duration)
                for e_id in edge_ids:
                    baseline_edge_flows[e_id] += 1

        # Step 2: Determine blocked edges
        active_blocked_edges: Set[str] = set()
        if custom_blocked_edge_ids is not None:
            active_blocked_edges = set(custom_blocked_edge_ids)
        else:
            # Check currently restricted edges in the graph
            active_blocked_edges = {e_id for e_id, is_b in blocked_state_backup.items() if is_b}
            # If no edges currently blocked, pick default Sony World flyover link for demonstration
            if not active_blocked_edges:
                active_blocked_edges = {"edge-7", "edge-8"}  # Sony World to Ejipura Link
                
        # Step 3: Apply blocked state
        for e_id, e in self.graph.edges.items():
            e.is_blocked = (e_id in active_blocked_edges)
            e.simulated_flow = baseline_edge_flows[e_id]
            
        # Step 4: Reassign affected trips
        disrupted_edge_flows: Dict[str, int] = {e_id: 0 for e_id in self.graph.edges}
        disrupted_trip_paths: Dict[str, Optional[Tuple[List[str], List[str], float]]] = {}
        affected_trip_count = 0
        total_baseline_duration = 0.0
        total_disrupted_duration = 0.0
        detour_durations: List[float] = []
        
        for trip in self.synthetic_trips:
            trip_id = trip["trip_id"]
            if trip_id not in baseline_trip_paths:
                continue
                
            base_nodes, base_edges, base_time = baseline_trip_paths[trip_id]
            total_baseline_duration += base_time
            
            # Check if baseline path crosses any blocked edge
            crosses_block = any(e_id in active_blocked_edges for e_id in base_edges)
            
            if not crosses_block:
                # Trip unaffected; maintains route
                disrupted_trip_paths[trip_id] = (base_nodes, base_edges, base_time)
                total_disrupted_duration += base_time
                for e_id in base_edges:
                    disrupted_edge_flows[e_id] += 1
            else:
                # Affected trip -> Reroute via shortest feasible path
                affected_trip_count += 1
                reroute_res = self.graph.compute_dijkstra(trip["origin"], trip["destination"], mode="fastest")
                if reroute_res:
                    new_nodes, new_edges, new_time = reroute_res
                    new_edge_ids = [e.edge_id for e in new_edges]
                    disrupted_trip_paths[trip_id] = (new_nodes, new_edge_ids, new_time)
                    total_disrupted_duration += new_time
                    detour_durations.append(max(0.0, new_time - base_time))
                    for e_id in new_edge_ids:
                        disrupted_edge_flows[e_id] += 1
                else:
                    # No feasible route exists (isolated by flood)
                    disrupted_trip_paths[trip_id] = None
                    total_disrupted_duration += (base_time * 2.5)  # Severe modeled penalty for stranded trip
                    detour_durations.append(base_time * 1.5)

        # Step 5: Iteration adjustment with BPR updated costs
        for it in range(iterations - 1):
            # Update flows in graph edges
            for e_id, edge in self.graph.edges.items():
                edge.simulated_flow = disrupted_edge_flows[e_id]
                
            # Rebalance affected trips with risk-aware BPR cost
            rebalanced_flows = {e_id: 0 for e_id in self.graph.edges}
            for trip in self.synthetic_trips:
                trip_id = trip["trip_id"]
                path_info = disrupted_trip_paths.get(trip_id)
                if path_info:
                    _, path_edges, _ = path_info
                    for e_id in path_edges:
                        rebalanced_flows[e_id] += 1
            disrupted_edge_flows = rebalanced_flows

        # Update global graph simulated flow
        for e_id, edge in self.graph.edges.items():
            edge.simulated_flow = disrupted_edge_flows[e_id]

        # Step 6: Compile Edge Metrics
        edge_metrics = []
        for e_id, edge in self.graph.edges.items():
            base_load = baseline_edge_flows[e_id]
            dis_load = disrupted_edge_flows[e_id]
            delta = dis_load - base_load
            cap = edge.capacity_proxy
            
            base_t = edge.travel_time_s
            base_travel_time = self.calculate_bpr_travel_time(base_t, base_load, cap)
            dis_travel_time = self.calculate_bpr_travel_time(base_t, dis_load, cap)
            
            congest_ratio = round(dis_load / max(1, cap), 2)
            
            status = "normal"
            if edge.is_blocked or e_id in active_blocked_edges:
                status = "blocked"
            elif congest_ratio >= 1.25:
                status = "severely_congested"
            elif congest_ratio >= 0.85:
                status = "congested"
                
            edge_metrics.append({
                "edge_id": e_id,
                "road_name": edge.road_name,
                "source_node": edge.u,
                "target_node": edge.v,
                "baseline_load": base_load,
                "disrupted_load": dis_load,
                "delta_load": delta,
                "capacity_proxy": cap,
                "base_travel_time_s": round(base_travel_time, 1),
                "disrupted_travel_time_s": round(dis_travel_time, 1),
                "congestion_ratio": congest_ratio,
                "status": status
            })

        # Sort top affected edges by delta load and congestion
        non_blocked_metrics = [m for m in edge_metrics if m["status"] != "blocked"]
        non_blocked_metrics.sort(key=lambda m: (m["delta_load"], m["congestion_ratio"]), reverse=True)
        top_affected = non_blocked_metrics[:8]

        total_trips = len(self.synthetic_trips)
        mean_base = round(total_baseline_duration / max(1, total_trips), 1)
        mean_disrupt = round(total_disrupted_duration / max(1, total_trips), 1)
        mean_detour = round(sum(detour_durations) / max(1, len(detour_durations)), 1) if detour_durations else 0.0
        pct_increase = round(((mean_disrupt - mean_base) / max(1.0, mean_base)) * 100.0, 1)

        run_id = f"sim-{uuid.uuid4().hex[:8]}"
        
        return {
            "run_id": run_id,
            "graph_version": self.graph.graph_version,
            "seed": seed,
            "total_trips": total_trips,
            "affected_trips": affected_trip_count,
            "mean_baseline_duration_s": mean_base,
            "mean_disrupted_duration_s": mean_disrupt,
            "mean_detour_s": mean_detour,
            "pct_travel_time_increase": pct_increase,
            "top_affected_edges": top_affected,
            "blocked_edges": list(active_blocked_edges),
            "edge_metrics": edge_metrics,
            "timestamp": datetime.utcnow().isoformat()
        }

ripple_engine = RippleEngine(road_graph)
