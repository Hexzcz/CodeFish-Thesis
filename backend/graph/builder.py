from collections import defaultdict
from typing import Optional, Dict, List, Tuple, Any
import copy
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


def _blank_edge_data(osmid, name, highway, length, coords) -> Dict:
    return {
        'osmid': str(osmid),
        'name': str(name or 'Unnamed Road'),
        'highway': str(highway or 'unclassified'),
        'length': length,
        'geometry': coords,
        'flood_class_5yr':   None,
        'flood_class_25yr':  None,
        'flood_class_100yr': None,
        'flood_proba_5yr':   None,
        'flood_proba_25yr':  None,
        'flood_proba_100yr': None,
        'elevation': None,
        'features': None,
    }

def build_graph_from_files() -> Graph:
    """Build the Graph from the bundled road_nodes/road_edges GeoJSON (offline)."""
    graph = Graph()
    max_edge_length_found = 0.0

    print("Loading nodes from local GeoJSON...")
    with open(GEOJSON_PATHS['road_nodes'], 'r') as f:
        nodes_geojson = json.load(f)
    for feature in nodes_geojson.get('features', []):
        props = feature.get('properties', {})
        coords = feature.get('geometry', {}).get('coordinates', [None, None])
        lat = props.get('lat', coords[1])
        lon = props.get('lon', coords[0])
        if lat is None or lon is None:
            continue
        graph.add_node(str(props.get('osmid')), lat=float(lat), lon=float(lon))

    print("Loading edges from local GeoJSON...")
    with open(GEOJSON_PATHS['road_edges'], 'r') as f:
        edges_geojson = json.load(f)
    for feature in edges_geojson.get('features', []):
        props = feature.get('properties', {})
        u = str(props.get('u'))
        v = str(props.get('v'))

        # If nodes don't exist, we can't create the edge
        if not graph.has_node(u) or not graph.has_node(v):
            continue

        l_val = float(props.get('length') or 0.0)
        if l_val > max_edge_length_found:
            max_edge_length_found = l_val

        coords_raw = feature.get('geometry', {}).get('coordinates', [])

        graph.add_edge(u, v, _blank_edge_data(
            props.get('osmid'), props.get('name'), props.get('highway'), l_val, coords_raw
        ))

    graph.max_edge_length = max_edge_length_found
    print(f"Graph built with {graph.node_count()} nodes and {graph.edge_count()} edges.")
    return graph

def build_graph() -> Graph:
    """Load road_nodes and road_edges from Supabase, falling back to local GeoJSON."""
    from backend.core.config import USE_LOCAL_DATA
    from backend.core.database import get_db_connection
    from sqlalchemy import text
    import json

    if USE_LOCAL_DATA:
        return build_graph_from_files()

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

                graph.add_edge(u, v, _blank_edge_data(
                    row[2], row[3], row[4], l_val, coords_raw
                ))

        print(f"Graph built with {graph.node_count()} nodes and {graph.edge_count()} edges.")
    except Exception as e:
        print(f"Error building graph from DB: {e}")

    if graph.edge_count() == 0:
        print("  Falling back to local GeoJSON road network.")
        return build_graph_from_files()

    graph.max_edge_length = max_edge_length_found
    return graph
