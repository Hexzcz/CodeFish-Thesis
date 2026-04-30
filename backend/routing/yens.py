from typing import List, Dict
from backend.graph.builder import Graph
from backend.routing.dijkstra import dijkstra
from backend.routing.weights import compute_wsm_weight

def yens_k_shortest_paths(
    g: Graph,
    source,
    target,
    K: int,
    scenario: str,
    weights: Dict[str, float],
    max_edge_length: float
) -> List[Dict]:
    """
    Refactored Iterative Penalized Dijkstra (Dynamic Edge-Weight Penalty).
    Generates alternative paths by penalizing edges of previously found paths,
    ensuring spatial diversity instead of simple detours.
    """
    PENALTY_FACTOR = 2.5  # Significant jump to push for different corridors
    
    # 1. Find Initial Optimal Path (P1)
    cost1, path1 = dijkstra(g, source, target, scenario, weights, max_edge_length)
    if not path1:
        return []
        
    p1_edges = set()
    for i in range(len(path1) - 1):
        # We use sorted tuple to treat undirected edges consistently
        p1_edges.add(tuple(sorted((path1[i], path1[i + 1]))))
        
    A = [{'path': path1, 'cost': cost1, 'similarity_score': 100.0, 'rank': 1}]
    
    # 2. Cumulative Edge Penalties
    # Key: (u, v) -> multiplier
    edge_penalties = {}
    
    for k in range(2, K + 1):
        # Apply penalties for EVERY edge used in ANY previous path in A
        latest_path = A[-1]['path']
        for i in range(len(latest_path) - 1):
            u, v = latest_path[i], latest_path[i + 1]
            edge_penalties[(u, v)] = edge_penalties.get((u, v), 1.0) * PENALTY_FACTOR
            edge_penalties[(v, u)] = edge_penalties.get((v, u), 1.0) * PENALTY_FACTOR
            
        # Run Dijkstra on the penalized graph
        p_cost, p_path = dijkstra(g, source, target, scenario, weights, max_edge_length, edge_penalties=edge_penalties)
        
        if not p_path:
            break
            
        pk_edges = set()
        for i in range(len(p_path) - 1):
            pk_edges.add(tuple(sorted((p_path[i], p_path[i + 1]))))
            
        shared_count = len(pk_edges.intersection(p1_edges))
        similarity = (shared_count / len(p1_edges) * 100.0) if p1_edges else 0.0
        
        real_cost = 0.0
        for i in range(len(p_path) - 1):
            edge = g.get_edge(p_path[i], p_path[i + 1])
            real_cost += compute_wsm_weight(edge, scenario, weights, max_edge_length)
            
        A.append({
            'path': p_path,
            'cost': real_cost,
            'similarity_score': round(similarity, 1),
            'rank': k
        })
        
    return A
