import pytest
from backend.app.services.graph_service import RoadGraph, haversine_distance, point_to_segment_distance

def test_haversine_accuracy():
    # Sony World Junction to Ejipura (~800-1000m)
    dist = haversine_distance(12.9352, 77.6245, 12.9425, 77.6250)
    assert 700.0 < dist < 1200.0

def test_point_to_segment_distance():
    # Point perpendicular to segment
    dist, px, py = point_to_segment_distance(12.9352, 77.6240, 12.9300, 77.6240, 12.9400, 77.6240)
    assert dist < 1.0  # directly on the line

def test_dijkstra_shortest_path():
    graph = RoadGraph()
    res = graph.compute_dijkstra("N1", "N7", mode="fastest")
    assert res is not None
    nodes, edges, cost = res
    assert nodes[0] == "N1"
    assert nodes[-1] == "N7"
    assert len(edges) >= 2
    assert cost > 0

def test_dijkstra_blocked_exclusion():
    graph = RoadGraph()
    # Find initial path
    initial_res = graph.compute_dijkstra("N1", "N7", mode="fastest")
    assert initial_res is not None
    _, initial_edges, _ = initial_res
    
    # Block first edge
    first_edge = initial_edges[0]
    first_edge.is_blocked = True
    
    new_res = graph.compute_dijkstra("N1", "N7", mode="fastest")
    assert new_res is not None
    _, new_edges, _ = new_res
    assert first_edge.edge_id not in [e.edge_id for e in new_edges]
    
    # Restore
    first_edge.is_blocked = False

def test_k_shortest_paths_diversity():
    graph = RoadGraph()
    k_paths = graph.compute_k_shortest_paths("N1", "N7", k=3, mode="risk_aware")
    assert len(k_paths) >= 2
    path1_nodes = k_paths[0][0]
    path2_nodes = k_paths[1][0]
    assert path1_nodes != path2_nodes
