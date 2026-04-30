import heapq
from typing import Optional, Set, Dict, List, Tuple, Any
from backend.graph.builder import Graph
from backend.routing.weights import compute_wsm_weight

def dijkstra(
    g: Graph,
    source,
    target,
    scenario: str,
    weights: Dict[str, float],
    max_edge_length: float,
    forbidden_nodes: Optional[Set] = None,
    forbidden_edges: Optional[Set] = None,
    edge_penalties: Optional[Dict[Tuple, float]] = None,
) -> Tuple[float, List]:
    """
    Single-source shortest path with binary min-heap.
    Supports forbidden nodes/edges and dynamic edge penalties.

    Returns (total_weighted_cost, path_node_list).
    Returns (inf, []) if no path exists.
    """
    if forbidden_nodes is None:
        forbidden_nodes = set()
    if forbidden_edges is None:
        forbidden_edges = set()
    if edge_penalties is None:
        edge_penalties = {}

    if not g.has_node(source) or not g.has_node(target):
        return float('inf'), []
    if source == target:
        return 0.0, [source]
    if source in forbidden_nodes or target in forbidden_nodes:
        return float('inf'), []

    dist: Dict = {source: 0.0}
    prev: Dict = {source: None}
    heap = [(0.0, source)]
    visited: Set = set()

    while heap:
        current_dist, u = heapq.heappop(heap)

        if u in visited:
            continue
        visited.add(u)

        if u == target:
            break

        for v, edge_data in g.get_neighbors(u):
            if v in forbidden_nodes:
                continue
            if (u, v) in forbidden_edges or (v, u) in forbidden_edges:
                continue
            if v in visited:
                continue

            base_weight = compute_wsm_weight(edge_data, scenario, weights, max_edge_length)
            penalty = edge_penalties.get((u, v), 1.0)
            weight = base_weight * penalty
            
            new_dist = current_dist + weight

            if v not in dist or new_dist < dist[v]:
                dist[v] = new_dist
                prev[v] = u
                heapq.heappush(heap, (new_dist, v))

    if target not in visited:
        return float('inf'), []

    # Reconstruct path
    path = []
    cur = target
    while cur is not None:
        path.append(cur)
        cur = prev.get(cur)
    path.reverse()

    if not path or path[0] != source:
        return float('inf'), []

    return dist[target], path
