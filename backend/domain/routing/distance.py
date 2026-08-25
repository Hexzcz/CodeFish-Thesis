"""Plain shortest-distance routing — the baseline the flood-aware routes are
compared against.

`routes.py` used to carry two near-identical copies of this search: one that
returned a distance and one that returned a distance and a path. There is one
search here, and the distance-only call is a thin wrapper over it.
"""
import heapq
from typing import Any, List, Tuple

from backend.domain.graph import Graph


def shortest_distance_path(g: Graph, source, target) -> Tuple[float, List[Any]]:
    """Dijkstra over edge length in metres. Returns (distance_m, node path).

    An unreachable target yields (inf, []) rather than raising: callers route
    to several candidate centers and expect some of them to be unreachable.
    """
    if not g.has_node(source) or not g.has_node(target):
        return float('inf'), []
    if source == target:
        return 0.0, [source]

    dist = {source: 0.0}
    prev = {source: None}
    heap = [(0.0, source)]
    visited = set()

    while heap:
        cur_d, u = heapq.heappop(heap)
        if u in visited:
            continue
        visited.add(u)
        if u == target:
            break

        for v, edge_data in g.get_neighbors(u):
            if v in visited:
                continue
            length_m = float(edge_data.get('length', 0.0) or 0.0)
            nd = cur_d + max(length_m, 0.0)
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))

    if target not in visited:
        return float('inf'), []

    path = []
    cur = target
    while cur is not None:
        path.append(cur)
        cur = prev.get(cur)
    path.reverse()
    if not path or path[0] != source:
        return float('inf'), []
    return dist[target], path


def shortest_distance(g: Graph, source, target) -> float:
    """Distance in metres along the shortest path, or inf if unreachable."""
    return shortest_distance_path(g, source, target)[0]
