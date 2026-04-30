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
    """Load road_edges.geojson and build Graph."""
    graph = Graph()
    road_file = GEOJSON_PATHS['road_edges']
    
    if not os.path.exists(road_file):
        print(f"      ERROR: {road_file} not found!")
        return graph

    with open(road_file, encoding='utf-8') as f:
        road_geojson = json.load(f)
    features = road_geojson.get('features', [])
    
    node_counter = 0
    node_map: Dict[Tuple, Any] = {}  # (lon_r, lat_r) -> node_id

    max_edge_length_found = 0.0

    for feat in features:
        geom = feat.get('geometry', {})
        coords_raw = geom.get('coordinates', [])
        props = feat.get('properties', {})

        # Flatten MultiLineString → longest LineString
        if geom.get('type') == 'MultiLineString':
            if not coords_raw:
                continue
            coords_raw = max(coords_raw, key=lambda c: len(c))
        elif geom.get('type') != 'LineString':
            continue

        if len(coords_raw) < 2:
            continue

        # Round to 6 dp for stable node deduplication
        start = (round(coords_raw[0][0], 6), round(coords_raw[0][1], 6))
        end   = (round(coords_raw[-1][0], 6), round(coords_raw[-1][1], 6))

        if start == end:  # skip self-loops
            continue

        for pt in (start, end):
            if pt not in node_map:
                node_map[pt] = node_counter
                graph.add_node(node_counter, lat=pt[1], lon=pt[0])
                node_counter += 1

        u = node_map[start]
        v = node_map[end]

        name = props.get('name', 'Unnamed Road')
        if isinstance(name, float) and math.isnan(name):
            name = 'Unnamed Road'

        l_val = float(props.get('length', 0.0) or 0.0)
        if l_val <= 0:
            l_val = (len(coords_raw) - 1) * 10.0

        if l_val > max_edge_length_found:
            max_edge_length_found = l_val

        graph.add_edge(u, v, {
            'osmid': props.get('osmid', ''),
            'name': str(name),
            'highway': props.get('highway', 'unclassified'),
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
    
    # Store the max edge length in the graph object or as a module variable if needed
    # For now, we'll just return the graph and let the caller handle global MAX_EDGE_LENGTH
    graph.max_edge_length = max_edge_length_found
    return graph
