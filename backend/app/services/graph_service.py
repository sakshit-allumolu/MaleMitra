import json
import math
import heapq
import os
from typing import Dict, List, Tuple, Optional, Any, Set
from backend.app.config import settings

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Returns distance in meters between two lat/lon points."""
    R = 6371000  # meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def point_to_segment_distance(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> Tuple[float, float, float]:
    """
    Computes minimum distance in meters from point (px, py) to line segment (x1, y1) -> (x2, y2).
    Also returns the projected nearest point (proj_lat, proj_lon).
    """
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return haversine_distance(px, py, x1, y1), x1, y1
    
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    dist = haversine_distance(px, py, proj_x, proj_y)
    return dist, proj_x, proj_y

class RoadEdge:
    def __init__(self, edge_id: str, u: str, v: str, road_name: str, length_m: float, 
                 travel_time_s: float, capacity_proxy: int, geometry: List[List[float]],
                 flood_risk_base: float = 0.0):
        self.edge_id = edge_id
        self.u = u
        self.v = v
        self.road_name = road_name
        self.length_m = length_m
        self.travel_time_s = travel_time_s
        self.capacity_proxy = capacity_proxy
        self.geometry = geometry  # list of [lat, lon]
        self.flood_risk_base = flood_risk_base
        
        # Dynamic operational attributes
        self.is_blocked: bool = False
        self.hazard_severity: str = "none"  # "none", "low", "medium", "high", "critical"
        self.reported_hazards_count: int = 0
        self.water_depth_cm: float = 0.0
        self.simulated_flow: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source": self.u,
            "target": self.v,
            "road_name": self.road_name,
            "length_m": self.length_m,
            "travel_time_s": self.travel_time_s,
            "capacity_proxy": self.capacity_proxy,
            "geometry": self.geometry,
            "is_blocked": self.is_blocked,
            "hazard_severity": self.hazard_severity,
            "water_depth_cm": self.water_depth_cm,
            "simulated_flow": self.simulated_flow
        }

class RoadGraph:
    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: Dict[str, RoadEdge] = {}
        self.adj: Dict[str, List[RoadEdge]] = {}
        self.graph_version: int = 1
        self._load_or_generate_bengaluru_network()

    def _load_or_generate_bengaluru_network(self):
        graph_path = os.path.join(os.path.dirname(__file__), "../data/bengaluru_graph.json")
        if os.path.exists(graph_path):
            try:
                with open(graph_path, "r") as f:
                    data = json.load(f)
                self._parse_graph_data(data)
                return
            except Exception as e:
                print(f"Error loading graph from {graph_path}: {e}, regenerating.")
        
        # Generate bounded Bengaluru road graph (Koramangala, Indiranagar, Domlur, Ejipura, HSR corridor)
        raw_nodes = [
            {"id": "N1", "name": "Sony World Junction, Koramangala", "lat": 12.9352, "lon": 77.6245},
            {"id": "N2", "name": "Koramangala 80ft Rd / 1st Block", "lat": 12.9279, "lon": 77.6271},
            {"id": "N3", "name": "Koramangala 100ft Rd / 4th Block", "lat": 12.9340, "lon": 77.6320},
            {"id": "N4", "name": "Koramangala 5th Block Junction", "lat": 12.9355, "lon": 77.6180},
            {"id": "N5", "name": "Ejipura Main Signal", "lat": 12.9425, "lon": 77.6250},
            {"id": "N6", "name": "Intermediate Ring Road (IRR) / Domlur", "lat": 12.9610, "lon": 77.6380},
            {"id": "N7", "name": "Indiranagar 100ft Rd / CMH Rd", "lat": 12.9780, "lon": 77.6410},
            {"id": "N8", "name": "Indiranagar 12th Main / 100ft Rd", "lat": 12.9710, "lon": 77.6435},
            {"id": "N9", "name": "Old Airport Road / Domlur Signal", "lat": 12.9600, "lon": 77.6490},
            {"id": "N10", "name": "HAL 2nd Stage / Suranjandas Rd", "lat": 12.9680, "lon": 77.6530},
            {"id": "N11", "name": "HSR Layout Sector 1 / 5th Main", "lat": 12.9150, "lon": 77.6350},
            {"id": "N12", "name": "Central Silk Board Junction", "lat": 12.9175, "lon": 77.6225},
            {"id": "N13", "name": "Madiwala Market / Police Station", "lat": 12.9220, "lon": 77.6190},
            {"id": "N14", "name": "Hosur Road / Forum Mall", "lat": 12.9345, "lon": 77.6110},
            {"id": "N15", "name": "Dairy Circle / Bannerghatta Rd", "lat": 12.9410, "lon": 77.6010},
            {"id": "N16", "name": "National Games Village (NGV)", "lat": 12.9415, "lon": 77.6170},
            {"id": "N17", "name": "ST Bed Layout, Koramangala", "lat": 12.9310, "lon": 77.6290},
            {"id": "N18", "name": "Viveknagar / Austin Town", "lat": 12.9550, "lon": 77.6210},
            {"id": "N19", "name": "Ulsoor Lake South / Kensington Rd", "lat": 12.9740, "lon": 77.6220},
            {"id": "N20", "name": "Trinity Circle / MG Road", "lat": 12.9720, "lon": 77.6160},
        ]
        
        # Raw connections (bidirectional)
        connections = [
            ("N1", "N2", "80ft Road Koramangala", 45, 75),
            ("N1", "N3", "Koramangala 100ft Road West", 40, 80),
            ("N1", "N4", "Koramangala 5th Block Main Rd", 35, 60),
            ("N1", "N5", "Sony World to Ejipura Link (Koramangala Flyover)", 40, 70),
            ("N2", "N17", "80ft Rd to ST Bed Connector", 35, 50),
            ("N3", "N17", "100ft Rd to ST Bed Inner Rd", 30, 40),
            ("N2", "N11", "Sarjapur Road / HSR Link", 50, 90),
            ("N2", "N12", "Madiwala to Silk Board Connector", 45, 100),
            ("N12", "N13", "Silk Board to Madiwala Main", 40, 110),
            ("N13", "N14", "Hosur Road to Forum Mall", 45, 95),
            ("N14", "N4", "Forum Mall to Koramangala 5th Block", 35, 65),
            ("N14", "N15", "Hosur Road / Dairy Circle Cut", 45, 85),
            ("N4", "N16", "Koramangala 5th Block to NGV", 35, 55),
            ("N5", "N16", "Ejipura to NGV Link Road", 35, 50),
            ("N5", "N6", "Intermediate Ring Road (IRR) South", 50, 110),
            ("N6", "N18", "IRR to Viveknagar Link", 40, 60),
            ("N6", "N9", "Domlur Flyover / Old Airport Road", 50, 120),
            ("N9", "N8", "Old Airport Rd to 100ft Indiranagar", 45, 90),
            ("N8", "N7", "100ft Road Indiranagar", 40, 85),
            ("N7", "N10", "CMH Road to HAL 2nd Stage", 40, 70),
            ("N9", "N10", "Old Airport Road HAL Corridor", 50, 100),
            ("N18", "N19", "Austin Town to Ulsoor Road", 35, 55),
            ("N19", "N20", "Ulsoor to Trinity Circle", 40, 75),
            ("N18", "N20", "Viveknagar to MG Road Corridor", 40, 70),
            ("N16", "N18", "NGV to Viveknagar Inner Link", 30, 45),
            ("N3", "N5", "Koramangala 4th Block to Ejipura Bypass", 35, 55),
            ("N11", "N12", "HSR 5th Main to Silk Board Flyover", 45, 90),
            ("N7", "N19", "Indiranagar CMH to Ulsoor Connector", 35, 60)
        ]
        
        edges_data = []
        edge_counter = 1
        node_map = {n["id"]: n for n in raw_nodes}
        
        for u, v, road_name, speed_kmh, cap in connections:
            n_u = node_map[u]
            n_v = node_map[v]
            dist_m = round(haversine_distance(n_u["lat"], n_u["lon"], n_v["lat"], n_v["lon"]), 1)
            time_s = round(dist_m / (speed_kmh * 1000 / 3600), 1)
            
            # Forward edge
            e_id_fwd = f"edge-{edge_counter}"
            edge_counter += 1
            geom_fwd = [[n_u["lat"], n_u["lon"]], [n_v["lat"], n_v["lon"]]]
            edges_data.append({
                "edge_id": e_id_fwd,
                "u": u,
                "v": v,
                "road_name": road_name + " (North/Eastbound)",
                "length_m": dist_m,
                "travel_time_s": time_s,
                "capacity_proxy": cap,
                "geometry": geom_fwd
            })
            
            # Reverse edge
            e_id_rev = f"edge-{edge_counter}"
            edge_counter += 1
            geom_rev = [[n_v["lat"], n_v["lon"]], [n_u["lat"], n_u["lon"]]]
            edges_data.append({
                "edge_id": e_id_rev,
                "u": v,
                "v": u,
                "road_name": road_name + " (South/Westbound)",
                "length_m": dist_m,
                "travel_time_s": time_s,
                "capacity_proxy": cap,
                "geometry": geom_rev
            })
        
        graph_dict = {
            "nodes": raw_nodes,
            "edges": edges_data
        }
        
        os.makedirs(os.path.dirname(graph_path), exist_ok=True)
        with open(graph_path, "w") as f:
            json.dump(graph_dict, f, indent=2)
            
        self._parse_graph_data(graph_dict)

    def _parse_graph_data(self, data: Dict[str, Any]):
        self.nodes = {n["id"]: n for n in data["nodes"]}
        self.edges = {}
        self.adj = {n_id: [] for n_id in self.nodes}
        
        for e in data["edges"]:
            edge = RoadEdge(
                edge_id=e["edge_id"],
                u=e["u"],
                v=e["v"],
                road_name=e["road_name"],
                length_m=e["length_m"],
                travel_time_s=e["travel_time_s"],
                capacity_proxy=e["capacity_proxy"],
                geometry=e["geometry"]
            )
            self.edges[edge.edge_id] = edge
            if edge.u in self.adj:
                self.adj[edge.u].append(edge)

    def find_nearest_node(self, lat: float, lon: float) -> str:
        """Finds closest graph node ID to given lat/lon."""
        best_node = None
        min_dist = float('inf')
        for node_id, n in self.nodes.items():
            d = haversine_distance(lat, lon, n["lat"], n["lon"])
            if d < min_dist:
                min_dist = d
                best_node = node_id
        return best_node

    def find_nearest_edge(self, lat: float, lon: float, max_dist_m: float = 1200.0) -> Tuple[Optional[RoadEdge], float, bool]:
        """
        Maps a geotagged incident to the nearest candidate road edge.
        Returns: (nearest_edge, distance_in_meters, is_ambiguous)
        If another parallel edge is within 25m distance difference, is_ambiguous = True.
        """
        candidates: List[Tuple[float, RoadEdge]] = []
        for edge_id, edge in self.edges.items():
            pts = edge.geometry
            if len(pts) >= 2:
                dist, _, _ = point_to_segment_distance(lat, lon, pts[0][0], pts[0][1], pts[1][0], pts[1][1])
                if dist <= max_dist_m:
                    candidates.append((dist, edge))
        
        if not candidates:
            # Fallback to nearest node's outgoing edge
            near_node = self.find_nearest_node(lat, lon)
            if near_node and self.adj[near_node]:
                return self.adj[near_node][0], 150.0, False
            return None, float('inf'), False
            
        candidates.sort(key=lambda x: x[0])
        best_dist, best_edge = candidates[0]
        
        is_ambiguous = False
        if len(candidates) > 1:
            second_dist, second_edge = candidates[1]
            # If two distinct road names are within 30 meters of each other
            if (second_dist - best_dist < 30.0) and (best_edge.road_name.split('(')[0] != second_edge.road_name.split('(')[0]):
                is_ambiguous = True
                
        return best_edge, best_dist, is_ambiguous

    def set_edge_restriction(self, edge_id: str, is_blocked: bool, notes: Optional[str] = None):
        """Sets blocked or reopened status on an edge and increments graph_version."""
        if edge_id in self.edges:
            self.edges[edge_id].is_blocked = is_blocked
            self.graph_version += 1

    def set_edge_hazard(self, edge_id: str, severity: str, water_depth_cm: float = 0.0):
        """Updates unverified or reported hazard score on an edge."""
        if edge_id in self.edges:
            self.edges[edge_id].hazard_severity = severity
            self.edges[edge_id].water_depth_cm = water_depth_cm
            self.edges[edge_id].reported_hazards_count += 1
            self.graph_version += 1

    def clear_edge_hazard(self, edge_id: str):
        if edge_id in self.edges:
            self.edges[edge_id].hazard_severity = "none"
            self.edges[edge_id].water_depth_cm = 0.0
            self.edges[edge_id].reported_hazards_count = 0
            self.edges[edge_id].is_blocked = False
            self.graph_version += 1

    def get_edge_weight(self, edge: RoadEdge, mode: str = "fastest") -> float:
        """
        Generalized edge cost function:
        W(e) = T(e) + lambda * R(e) + mu * C(e)
        - If edge.is_blocked: infinite cost (excluded from eligible routing)
        - mode 'fastest': W(e) = T_base(e)
        - mode 'risk_aware': W(e) = T_base(e) + lambda * Hazard_Penalty + mu * Congestion_Penalty
        """
        if edge.is_blocked:
            return float('inf')
            
        base_t = edge.travel_time_s
        
        if mode == "fastest":
            # Baseline fastest ignores unverified warnings unless blocked
            return base_t
            
        # Risk-aware calculation
        hazard_penalty = 0.0
        if edge.hazard_severity == "critical":
            hazard_penalty = 400.0
        elif edge.hazard_severity == "high":
            hazard_penalty = 250.0
        elif edge.hazard_severity == "medium":
            hazard_penalty = 120.0
        elif edge.hazard_severity == "low":
            hazard_penalty = 40.0
            
        # Congestion delay from BPR formula: t = t0 * (1 + alpha * (v/c)^beta)
        v = edge.simulated_flow
        c = max(10, edge.capacity_proxy)
        congestion_delay = base_t * settings.BPR_ALPHA * ((v / c) ** settings.BPR_BETA)
        
        total_w = base_t + (settings.HAZARD_LAMBDA / 100.0) * hazard_penalty + settings.CONGESTION_MU * congestion_delay
        return total_w

    def compute_dijkstra(self, start_node: str, end_node: str, mode: str = "fastest") -> Optional[Tuple[List[str], List[RoadEdge], float]]:
        """
        Computes shortest path from start_node to end_node under the given cost mode.
        Returns: (node_path, edge_path, total_cost) or None if no feasible path.
        """
        if start_node not in self.nodes or end_node not in self.nodes:
            return None
            
        dist: Dict[str, float] = {node_id: float('inf') for node_id in self.nodes}
        prev_node: Dict[str, Optional[str]] = {node_id: None for node_id in self.nodes}
        prev_edge: Dict[str, Optional[RoadEdge]] = {node_id: None for node_id in self.nodes}
        
        dist[start_node] = 0.0
        pq: List[Tuple[float, str]] = [(0.0, start_node)]
        
        while pq:
            current_dist, u = heapq.heappop(pq)
            if current_dist > dist[u]:
                continue
            if u == end_node:
                break
                
            for edge in self.adj.get(u, []):
                weight = self.get_edge_weight(edge, mode=mode)
                if math.isinf(weight):
                    continue
                    
                new_dist = current_dist + weight
                v = edge.v
                if new_dist < dist[v]:
                    dist[v] = new_dist
                    prev_node[v] = u
                    prev_edge[v] = edge
                    heapq.heappush(pq, (new_dist, v))
                    
        if math.isinf(dist[end_node]):
            return None
            
        # Reconstruct path
        curr = end_node
        node_path: List[str] = []
        edge_path: List[RoadEdge] = []
        while curr is not None:
            node_path.append(curr)
            edge = prev_edge[curr]
            if edge:
                edge_path.append(edge)
            curr = prev_node[curr]
            
        node_path.reverse()
        edge_path.reverse()
        return node_path, edge_path, dist[end_node]

    def compute_k_shortest_paths(self, start_node: str, end_node: str, k: int = 3, mode: str = "risk_aware") -> List[Tuple[List[str], List[RoadEdge], float]]:
        """
        Computes up to k diverse feasible paths using Yen's algorithm.
        """
        shortest = self.compute_dijkstra(start_node, end_node, mode=mode)
        if not shortest:
            return []
            
        A = [shortest]
        B = []  # Candidate paths
        
        for i in range(1, k):
            prev_path_nodes, prev_path_edges, _ = A[i - 1]
            for spur_idx in range(len(prev_path_nodes) - 1):
                spur_node = prev_path_nodes[spur_idx]
                root_path_nodes = prev_path_nodes[:spur_idx + 1]
                root_path_edges = prev_path_edges[:spur_idx]
                
                # Temporarily disable edges part of previous paths that share root
                removed_edges: List[RoadEdge] = []
                for path_nodes, path_edges, _ in A:
                    if len(path_nodes) > spur_idx and path_nodes[:spur_idx + 1] == root_path_nodes:
                        edge_to_remove = path_edges[spur_idx]
                        if not edge_to_remove.is_blocked:
                            edge_to_remove.is_blocked = True
                            removed_edges.append(edge_to_remove)
                
                # Compute spur path
                spur_res = self.compute_dijkstra(spur_node, end_node, mode=mode)
                
                # Restore removed edges
                for edge in removed_edges:
                    edge.is_blocked = False
                    
                if spur_res:
                    spur_nodes, spur_edges, _ = spur_res
                    total_nodes = root_path_nodes[:-1] + spur_nodes
                    total_edges = root_path_edges + spur_edges
                    
                    # Compute total cost
                    total_cost = sum(self.get_edge_weight(e, mode=mode) for e in total_edges)
                    
                    # Avoid duplicate candidates
                    cand_tuple = (total_nodes, total_edges, total_cost)
                    if cand_tuple not in [c for _, c in B] and total_nodes not in [a[0] for a in A]:
                        heapq.heappush(B, (total_cost, cand_tuple))
                        
            if not B:
                break
            _, best_cand = heapq.heappop(B)
            A.append(best_cand)
            
        return A

# Global singleton road graph
road_graph = RoadGraph()
