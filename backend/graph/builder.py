from collections import defaultdict
from typing import Optional, Dict, List, Tuple, Any
import json
import math
import os
from backend.core.config import GEOJSON_PATHS

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

def build_graph() -> Graph:
    """Load road_nodes and road_edges from Supabase and build Graph."""
    from backend.core.database import get_db_connection
    from sqlalchemy import text
    import json
    
    graph = Graph()
    max_edge_length_found = 0.0
    
    try:
        with get_db_connection() as conn:
            # 1. Load Nodes
            print("Fetching nodes from Supabase...")
            nodes_result = conn.execute(text("SELECT osmid, lat, lon FROM road_nodes"))
            for row in nodes_result:
                osmid_str = str(row[0])
                graph.add_node(osmid_str, lat=row[1], lon=row[2])
                
            # 2. Load Edges
            print("Fetching edges from Supabase...")
            edges_result = conn.execute(text("SELECT u, v, osmid, name, highway, length, ST_AsGeoJSON(geom) as geom_json FROM road_edges"))
            for row in edges_result:
                u = str(row[0])
                v = str(row[1])
                
                # If nodes don't exist, we can't create the edge
                if not graph.has_node(u) or not graph.has_node(v):
                    continue
                    
                l_val = float(row[5] or 0.0)
                if l_val > max_edge_length_found:
                    max_edge_length_found = l_val
                    
                geom_json = json.loads(row[6])
                coords_raw = geom_json.get('coordinates', [])
                
                graph.add_edge(u, v, {
                    'osmid': str(row[2]),
                    'name': str(row[3] or 'Unnamed Road'),
                    'highway': str(row[4] or 'unclassified'),
                    'length': l_val,
                    'geometry': coords_raw,
                    'flood_class_5yr':   None,
                    'flood_class_25yr':  None,
                    'flood_class_100yr': None,
                    'flood_proba_5yr':   None,
                    'flood_proba_25yr':  None,
                    'flood_proba_100yr': None,
                    'elevation': None,
                    'features': None,
                })
                
        print(f"Graph built with {graph.node_count()} nodes and {graph.edge_count()} edges.")
    except Exception as e:
        print(f"Error building graph from DB: {e}")
        
    graph.max_edge_length = max_edge_length_found
    return graph
