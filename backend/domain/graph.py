"""The road network the router walks: nodes, edges and their attributes.

Pure data structure — it knows nothing about where the network came from.
Loading it from a database or from GeoJSON is an adapter's job
(`backend/adapters/road_network.py`).
"""
from collections import defaultdict
from typing import Optional, Dict, List, Tuple, Any
import copy


class Graph:
    """Adjacency list graph for efficient routing."""
    def __init__(self):
        # adjacency list: node_id -> [(neighbor_id, edge_data), ...]
        self.adj: Dict[Any, List[Tuple[Any, Dict]]] = defaultdict(list)
        # edge lookup: (u, v) -> edge_data  (stored both directions)
        self.edges: Dict[Tuple, Dict] = {}
        # node lookup: node_id -> {'id', 'lat', 'lon'}
        self.nodes: Dict[Any, Dict] = {}

    def add_node(self, node_id, lat: float, lon: float):
        self.nodes[node_id] = {'id': node_id, 'lat': lat, 'lon': lon}

    def add_edge(self, u, v, edge_data: Dict):
        """Add a bidirectional edge. Skips self-loops."""
        if u == v:
            return
        # Deduplicate: keep the shorter edge if one already exists
        existing = self.edges.get((u, v))
        if existing and existing.get('length', 0) <= edge_data.get('length', float('inf')):
            return
        self.adj[u].append((v, edge_data))
        self.adj[v].append((u, edge_data))
        self.edges[(u, v)] = edge_data
        self.edges[(v, u)] = edge_data

    def get_edge(self, u, v) -> Optional[Dict]:
        return self.edges.get((u, v))

    def get_neighbors(self, node_id) -> List[Tuple]:
        return self.adj.get(node_id, [])

    def has_node(self, node_id) -> bool:
        return node_id in self.nodes

    def node_count(self) -> int:
        return len(self.nodes)

    def edge_count(self) -> int:
        return len(self.edges) // 2

    def clone(self) -> "Graph":
        """Return an isolated copy safe for request-local graph mutations."""
        cloned = Graph()
        cloned.nodes = {node_id: dict(data) for node_id, data in self.nodes.items()}

        seen = set()
        for (u, v), edge_data in self.edges.items():
            key = frozenset((u, v))
            if key in seen:
                continue
            seen.add(key)
            cloned.add_edge(u, v, copy.deepcopy(edge_data))

        if hasattr(self, "max_edge_length"):
            cloned.max_edge_length = self.max_edge_length
        return cloned

