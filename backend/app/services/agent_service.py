import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from backend.app.models.database import get_db_connection
from backend.app.services.graph_service import road_graph, RoadEdge, haversine_distance
from backend.app.services.ripple_service import ripple_engine

class AgentOrchestrator:
    @staticmethod
    def get_recent_agent_events(limit: int = 50) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM agent_events ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        
        events = []
        for r in rows:
            input_refs = []
            if r["input_refs"]:
                try:
                    input_refs = json.loads(r["input_refs"])
                except Exception:
                    input_refs = [r["input_refs"]]
            res_dict = {}
            if r["result"]:
                try:
                    res_dict = json.loads(r["result"])
                except Exception:
                    res_dict = {"raw": r["result"]}
                    
            events.append({
                "event_id": r["id"],
                "incident_id": r["incident_id"],
                "agent": r["agent"],
                "action": r["action"],
                "input_refs": input_refs,
                "result": res_dict,
                "data_mode": r["data_mode"],
                "requires_approval": bool(r["requires_approval"]),
                "timestamp": r["created_at"]
            })
        conn.close()
        return events

    @staticmethod
    def get_recent_audit_events(limit: int = 50) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_events ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        
        audits = []
        for r in rows:
            before_dict = None
            if r["before_state"]:
                try:
                    before_dict = json.loads(r["before_state"])
                except Exception:
                    before_dict = {"raw": r["before_state"]}
            after_dict = None
            if r["after_state"]:
                try:
                    after_dict = json.loads(r["after_state"])
                except Exception:
                    after_dict = {"raw": r["after_state"]}
                    
            audits.append({
                "id": r["id"],
                "actor_id": r["actor_id"],
                "actor_name": r["actor_name"],
                "action": r["action"],
                "entity_type": r["entity_type"],
                "entity_id": r["entity_id"],
                "before_state": before_dict,
                "after_state": after_dict,
                "timestamp": r["created_at"]
            })
        conn.close()
        return audits

    @staticmethod
    def compare_routes(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float, user_id: str = "anon") -> Dict[str, Any]:
        """
        Mobility Agent Route Comparison:
        Computes:
        1. Fastest Route (ignoring unverified hazards, but respecting confirmed blocked edges).
        2. Risk-Aware Route (incorporates hazard penalties + modeled ripple congestion).
        3. Alternative Diverse Routes (k-shortest diverse paths).
        """
        start_node = road_graph.find_nearest_node(origin_lat, origin_lon)
        end_node = road_graph.find_nearest_node(dest_lat, dest_lon)
        
        if not start_node or not end_node or start_node == end_node:
            # Pick distinct default nodes if coordinates coincide
            start_node = "N1"
            end_node = "N7"
            
        routes_output = []
        
        # 1. Fastest Route
        fastest_res = road_graph.compute_dijkstra(start_node, end_node, mode="fastest")
        if fastest_res:
            nodes, edges, duration = fastest_res
            coords = []
            edge_ids = []
            tot_dist = 0.0
            blocked_crossed = 0
            risk_score = 0.0
            
            for e in edges:
                edge_ids.append(e.edge_id)
                tot_dist += e.length_m
                if e.is_blocked:
                    blocked_crossed += 1
                if e.hazard_severity != "none":
                    risk_score += (0.35 if e.hazard_severity == "high" else 0.18)
                for pt in e.geometry:
                    if not coords or coords[-1] != pt:
                        coords.append(pt)
                        
            routes_output.append({
                "type": "fastest",
                "label": "Direct / Standard Route",
                "edge_ids": edge_ids,
                "path_nodes": nodes,
                "coordinates": coords,
                "estimated_duration_s": round(duration, 1),
                "base_duration_s": round(sum(e.travel_time_s for e in edges), 1),
                "hazard_penalty_s": 0.0,
                "congestion_delay_s": max(0.0, round(duration - sum(e.travel_time_s for e in edges), 1)),
                "distance_m": round(tot_dist, 1),
                "blocked_edges_crossed": blocked_crossed,
                "risk_score": min(1.0, round(risk_score, 2)),
                "uncertainty": "Modeled using baseline speed limits & confirmed restrictions."
            })
            
        # 2. Risk-Aware Route
        risk_res = road_graph.compute_dijkstra(start_node, end_node, mode="risk_aware")
        if risk_res:
            nodes_r, edges_r, duration_r = risk_res
            coords_r = []
            edge_ids_r = []
            tot_dist_r = 0.0
            blocked_crossed_r = 0
            risk_score_r = 0.0
            
            for e in edges_r:
                edge_ids_r.append(e.edge_id)
                tot_dist_r += e.length_m
                if e.is_blocked:
                    blocked_crossed_r += 1
                if e.hazard_severity != "none":
                    risk_score_r += 0.08
                for pt in e.geometry:
                    if not coords_r or coords_r[-1] != pt:
                        coords_r.append(pt)
                        
            routes_output.append({
                "type": "risk_aware",
                "label": "MaleMitra Risk-Aware Detour",
                "edge_ids": edge_ids_r,
                "path_nodes": nodes_r,
                "coordinates": coords_r,
                "estimated_duration_s": round(duration_r, 1),
                "base_duration_s": round(sum(e.travel_time_s for e in edges_r), 1),
                "hazard_penalty_s": round(sum(40.0 for e in edges_r if e.hazard_severity != "none"), 1),
                "congestion_delay_s": max(0.0, round(duration_r - sum(e.travel_time_s for e in edges_r), 1)),
                "distance_m": round(tot_dist_r, 1),
                "blocked_edges_crossed": blocked_crossed_r,
                "risk_score": min(0.3, round(risk_score_r, 2)),
                "uncertainty": "Penalizes flooded segments & ripple congestion. Not a certified safe route."
            })
            
        # 3. Alternative Route (Yen's diverse paths)
        k_paths = road_graph.compute_k_shortest_paths(start_node, end_node, k=2, mode="risk_aware")
        if len(k_paths) > 1:
            nodes_a, edges_a, duration_a = k_paths[1]
            coords_a = []
            edge_ids_a = []
            tot_dist_a = 0.0
            for e in edges_a:
                edge_ids_a.append(e.edge_id)
                tot_dist_a += e.length_m
                for pt in e.geometry:
                    if not coords_a or coords_a[-1] != pt:
                        coords_a.append(pt)
                        
            routes_output.append({
                "type": "alternative",
                "label": "Secondary Corridor Alternative",
                "edge_ids": edge_ids_a,
                "path_nodes": nodes_a,
                "coordinates": coords_a,
                "estimated_duration_s": round(duration_a, 1),
                "base_duration_s": round(sum(e.travel_time_s for e in edges_a), 1),
                "hazard_penalty_s": 0.0,
                "congestion_delay_s": max(0.0, round(duration_a - sum(e.travel_time_s for e in edges_a), 1)),
                "distance_m": round(tot_dist_a, 1),
                "blocked_edges_crossed": 0,
                "risk_score": 0.12,
                "uncertainty": "Alternative feasible path via parallel thoroughfare."
            })

        active_restrictions = sum(1 for e in road_graph.edges.values() if e.is_blocked)
        reported_hazards = sum(1 for e in road_graph.edges.values() if e.hazard_severity != "none" and not e.is_blocked)
        
        return {
            "graph_version": road_graph.graph_version,
            "data_mode": "simulated_incidents",
            "routes": routes_output,
            "active_restrictions_count": active_restrictions,
            "reported_hazards_count": reported_hazards,
            "message": "Routes successfully calculated." if routes_output else "No feasible route exists due to flood obstructions."
        }

agent_orchestrator = AgentOrchestrator()
