# Install: pip install fastapi uvicorn rio-tiler matplotlib shapely geopandas pillow joblib rasterio scikit-learn xgboost
# Run: uvicorn main_routing:app --reload --port 8000
# Open: http://localhost:8000

import heapq
import time
import json
import math
import os
import io
import copy
from collections import defaultdict
from typing import Optional, Set, Dict, List, Tuple, Any

import numpy as np
import geopandas as gpd
from shapely.geometry import box, mapping, Point, LineString, MultiLineString
from shapely.ops import linemerge
import rasterio
import matplotlib.pyplot as plt
import joblib
from PIL import Image, ImageDraw

from fastapi import FastAPI, Response, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ─────────────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────────────

app = FastAPI(title="CodeFish Flood-Aware Evacuation Routing")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# Pydantic Request Models
# ─────────────────────────────────────────────

class RouteRequest(BaseModel):
    origin_lat: float
    origin_lon: float
    scenario: str = "25yr"
    k: Optional[int] = 3
    # Weights for WSM (Edge Cost) and TOPSIS (Path Ranking)
    # Must sum to 1.0. Defaults if not provided.
    weights: Optional[Dict[str, float]] = {
        'flood': 0.5,
        'distance': 0.3,
        'road_class': 0.2
    }


# ─────────────────────────────────────────────
# Section 1: Custom Graph Class
# ─────────────────────────────────────────────

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


# ─────────────────────────────────────────────
# Global State
# ─────────────────────────────────────────────

graph = Graph()
evacuation_centers: List[Dict] = []
MODELS: Dict[str, Any] = {}
main_component: Set = set()   # nodes in the largest connected component

SCENARIOS = ['5yr', '25yr', '100yr']

# Raster files
RASTER_FILES = {
    'elevation':    'rasters_COP30/output_hh.tif',
    'slope':        'viz/viz.hh_slope.tif',
    'land_cover':   'land_cover_aligned.tif',
    'dist_waterway': 'distance_to_waterways.tif',
}
FLOOD_RASTERS = {
    '5yr':   'flood_hazard_fh5yr_aligned.tif',
    '25yr':  'flood_hazard_fh25yr_aligned.tif',
    '100yr': 'flood_hazard_fh100yr_aligned.tif',
}

DEFAULT_FEATURES = {
    'elevation': 20.0,
    'slope': 2.2,
    'land_cover': 50.0,
    'dist_waterway': 275.0,
}

# Tile-rendering configuration
LAYERS_MAP = {
    "flood_5yr":    ("flood_hazard_fh5yr_aligned.tif",   "flood",   255.0),
    "flood_25yr":   ("flood_hazard_fh25yr_aligned.tif",  "flood",   255.0),
    "flood_100yr":  ("flood_hazard_fh100yr_aligned.tif", "flood",   255.0),
    "land_cover":   ("land_cover_aligned.tif",            "tab20",   0.0),
    "dist_waterway":("distance_to_waterways.tif",         "Blues_r", None),
    "elevation":    ("rasters_COP30/output_hh.tif",       "terrain", None),
    "slope":        ("viz/viz.hh_slope.tif",              "YlOrRd",  None),
}
FLOOD_COLORMAP = {
    1: (255, 255,   0, 180),
    2: (255, 140,   0, 180),
    3: (255,   0,   0, 180),
}

# Boundary geometry for map clipping
BOUNDARY_FILE = "district1_boundary_strict.geojson"
STRICT_BOUNDARY_GEOM = None

if os.path.exists(BOUNDARY_FILE):
    try:
        _bdf = gpd.read_file(BOUNDARY_FILE)
        if not _bdf.empty:
            STRICT_BOUNDARY_GEOM = (
                _bdf.geometry.union_all()
                if hasattr(_bdf.geometry, 'union_all')
                else _bdf.geometry.unary_union
            )
            print(f"Loaded boundary clipping geom: {STRICT_BOUNDARY_GEOM.geom_type}")
    except Exception as _e:
        print(f"Error loading boundary for clipping: {_e}")

# Cached GeoJSON for pass-through API endpoints
ROAD_GEOJSON: Optional[Dict] = None
EVAC_GEOJSON: Optional[Dict] = None
ROAD_FILE = "road_edges.geojson"
EVAC_FILE = "evacuation_centers.geojson"


# ─────────────────────────────────────────────
# Section 2: Nearest Node Lookup
# ─────────────────────────────────────────────

LAT_TO_M = 111320.0         # metres per degree latitude
LON_TO_M = 107600.0         # metres per degree longitude at ~14.6° N


def get_nearest_node(g: Graph, lat: float, lon: float) -> Tuple[Any, float]:
    """
    Find the nearest graph node using an efficient linear scan.
    Returns (node_id, distance_m).
    Raises ValueError if no node is within 500 m.
    """
    if not g.nodes:
        raise ValueError("Road network graph is empty")

    min_dist = float('inf')
    nearest = None

    for node_id, node in g.nodes.items():
        dlat = (node['lat'] - lat) * LAT_TO_M
        dlon = (node['lon'] - lon) * LON_TO_M
        dist = math.sqrt(dlat ** 2 + dlon ** 2)
        if dist < min_dist:
            min_dist = dist
            nearest = node_id

    if min_dist > 500:
        raise ValueError(
            f"Origin is {min_dist:.0f} m from the nearest road node "
            "(max allowed: 500 m). Please place your pin closer to a road."
        )

    return nearest, min_dist


# ─────────────────────────────────────────────
# Section 3: Criteria & WSM Weight Function
# ─────────────────────────────────────────────

HIGHWAY_RANK = {
    'motorway': 1, 'motorway_link': 1,
    'trunk': 2, 'trunk_link': 2,
    'primary': 3, 'primary_link': 3,
    'secondary': 4, 'secondary_link': 4,
    'tertiary': 5, 'tertiary_link': 5,
    'residential': 6,
    'unclassified': 7,
    'service': 8,
    'living_street': 8,
    'pedestrian': 9,
    'footway': 9,
    'path': 9,
}
MAX_RANK = 10.0
MAX_EDGE_LENGTH = 1000.0 # Will be updated dynamically


def compute_wsm_weight(edge_data: Dict, scenario: str, weights: Dict[str, float]) -> float:
    """
    Weighted Sum Model (WSM) for edge cost.
    Cost = w1*norm(flood) + w2*norm(length) + w3*norm(road_class)
    Higher cost = less desirable edge.
    """
    # 1. Flood Probability (0 to 1)
    flood_proba = float(edge_data.get(f'flood_proba_{scenario}', 0.0) or 0.0)
    
    # 2. Road Length (Normalised by MAX_EDGE_LENGTH)
    length = float(edge_data.get('length', 100.0))
    norm_length = min(length / MAX_EDGE_LENGTH, 2.0) # Cap significantly long edges
    
    # 3. Road Class (Lower rank = better road = lower cost)
    hw = edge_data.get('highway', 'unclassified')
    if isinstance(hw, list): hw = hw[0]
    rank = HIGHWAY_RANK.get(hw, MAX_RANK)
    norm_rank = rank / MAX_RANK
    
    # WSM Calculation
    wf = weights.get('flood', 0.5)
    wd = weights.get('distance', 0.3)
    wr = weights.get('road_class', 0.2)
    
    # Scaling factor (e.g. 100) to keep costs as meaningful numbers for Dijkstra
    # Length is still the 'physical' unit base to keep path geometry realistic
    wsm_cost = (wf * flood_proba + wd * norm_length + wr * norm_rank) * 100.0
    
    # We must ensure we never return 0 as cost for Dijkstra to avoid loops
    return max(wsm_cost, 0.01)


# ─────────────────────────────────────────────
# Section 4: Dijkstra Algorithm
# ─────────────────────────────────────────────

def dijkstra(
    g: Graph,
    source,
    target,
    scenario: str,
    weights: Dict[str, float],
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

            base_weight = compute_wsm_weight(edge_data, scenario, weights)
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


# ─────────────────────────────────────────────
# Section 5: Yen's K-Shortest Paths
# ─────────────────────────────────────────────

def yens_k_shortest_paths(
    g: Graph,
    source,
    target,
    K: int,
    scenario: str,
    weights: Dict[str, float]
) -> List[Dict]:
    """
    Refactored Iterative Penalized Dijkstra (Dynamic Edge-Weight Penalty).
    Generates alternative paths by penalizing edges of previously found paths,
    ensuring spatial diversity instead of simple detours.
    """
    PENALTY_FACTOR = 4.0  # Significant jump to push for different corridors
    
    # 1. Find Initial Optimal Path (P1)
    cost1, path1 = dijkstra(g, source, target, scenario, weights)
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
        # This increases the cost of 'over-used' corridors
        latest_path = A[-1]['path']
        for i in range(len(latest_path) - 1):
            u, v = latest_path[i], latest_path[i + 1]
            edge_penalties[(u, v)] = edge_penalties.get((u, v), 1.0) * PENALTY_FACTOR
            edge_penalties[(v, u)] = edge_penalties.get((v, u), 1.0) * PENALTY_FACTOR
            
        # Run Dijkstra on the penalized graph
        p_cost, p_path = dijkstra(g, source, target, scenario, weights, edge_penalties=edge_penalties)
        
        if not p_path:
            break
            
        # Calculate Similarity to P1: (Shared Edges / P1 Edges) * 100
        pk_edges = set()
        for i in range(len(p_path) - 1):
            pk_edges.add(tuple(sorted((p_path[i], p_path[i + 1]))))
            
        shared_count = len(pk_edges.intersection(p1_edges))
        similarity = (shared_count / len(p1_edges) * 100.0) if p1_edges else 0.0
        
        # We calculate the REAL (unpenalized) WSM cost for ranking transparency
        real_cost = 0.0
        for i in range(len(p_path) - 1):
            edge = g.get_edge(p_path[i], p_path[i + 1])
            real_cost += compute_wsm_weight(edge, scenario, weights)
            
        A.append({
            'path': p_path,
            'cost': real_cost,
            'similarity_score': round(similarity, 1),
            'rank': k
        })
        
    return A


# ─────────────────────────────────────────────
# Section 6: Route Scoring
# ─────────────────────────────────────────────

def score_routes(routes: List[Dict], g: Graph, scenario: str, weights_map: Dict[str, float]) -> List[Dict]:
    """
    Score paths using WSM and TOPSIS ranking.
    """
    if not routes:
        return []

    scored = []

    for route_data in routes:
        path = route_data['path']

        total_length = 0.0
        total_flood_proba = 0.0
        max_flood_class = 0
        segment_count = 0
        flood_class_counts = {0: 0, 1: 0, 2: 0, 3: 0}
        segments = []

        for i in range(len(path) - 1):
            edge = g.get_edge(path[i], path[i + 1])
            if not edge:
                continue

            length = float(edge.get('length', 0.0))
            flood_class = int(edge.get(f'flood_class_{scenario}', 0) or 0)
            flood_proba = float(edge.get(f'flood_proba_{scenario}', 0.0) or 0.0)
            elevation = float(edge.get('elevation', 0.0) or 0.0)

            total_length += length
            total_flood_proba += flood_proba
            max_flood_class = max(max_flood_class, flood_class)
            flood_class_counts[min(flood_class, 3)] += 1
            segment_count += 1

            segments.append({
                'name': edge.get('name', 'Unnamed Road'),
                'highway': edge.get('highway', 'unclassified'),
                'length': round(length, 2),
                'flood_class': flood_class,
                'flood_proba': round(flood_proba, 4),
                'elevation': round(elevation, 2),
                'wsm_cost': round(compute_wsm_weight(edge, scenario, weights_map), 4)
            })

        avg_flood_proba = total_flood_proba / segment_count if segment_count > 0 else 0.0

        wsm_flood_total = sum(s['flood_proba'] * weights_map['flood'] for s in segments) * 100.0
        wsm_dist_total = sum((min(s['length'] / MAX_EDGE_LENGTH, 2.0)) * weights_map['distance'] for s in segments) * 100.0
        
        # Road class sum
        wsm_rank_total = 0.0
        for s in segments:
            hw = s['highway']
            if isinstance(hw, list): hw = hw[0]
            rank = HIGHWAY_RANK.get(hw, MAX_RANK)
            wsm_rank_total += (rank / MAX_RANK) * weights_map['road_class'] * 100.0

        r_final = {
            'path': path,
            'cost': route_data['cost'],
            'similarity_score': route_data.get('similarity_score', 0.0),
            'total_length_m': round(total_length, 2),
            'total_length_km': round(total_length / 1000, 3),
            'flood_exposure': round(avg_flood_proba, 4),
            'max_flood_class': max_flood_class,
            'flood_class_counts': flood_class_counts,
            'segment_count': segment_count,
            'segments': segments,
            'wsm_breakdown': {
                'flood': round(wsm_flood_total, 2),
                'distance': round(wsm_dist_total, 2),
                'road_class': round(wsm_rank_total, 2)
            },
            '_raw_flood': avg_flood_proba,
            '_raw_length': total_length,
            '_raw_rank': 1.0 
        }
        scored.append(r_final)
    
    # --- TOPSIS RANKING ---
    if len(scored) > 0:
        matrix = []
        for r in scored:
            avg_hw_rank = sum(HIGHWAY_RANK.get(s['highway'] if not isinstance(s['highway'], list) else s['highway'][0], MAX_RANK) for s in r['segments'])
            avg_hw_rank /= r['segment_count'] if r['segment_count'] > 0 else 1.0
            matrix.append([r['_raw_flood'], r['_raw_length'], avg_hw_rank])
        
        matrix = np.array(matrix)
        w = np.array([weights_map['flood'], weights_map['distance'], weights_map['road_class']])
        
        # 1. Norm
        norm_matrix = np.zeros_like(matrix)
        for j in range(matrix.shape[1]):
            col_sum_sq = np.sqrt(np.sum(matrix[:, j]**2)) + 1e-9
            norm_matrix[:, j] = matrix[:, j] / col_sum_sq
                
        # 2. Weighted
        weighted_matrix = norm_matrix * w
        
        # 3. Ideals (Cost criteria: best=min, worst=max)
        ideal_best = np.min(weighted_matrix, axis=0)
        ideal_worst = np.max(weighted_matrix, axis=0)
        
        # 4. Separation
        s_best = np.sqrt(np.sum((weighted_matrix - ideal_best)**2, axis=1))
        s_worst = np.sqrt(np.sum((weighted_matrix - ideal_worst)**2, axis=1))
        
        # 5. Closeness
        closeness = s_worst / (s_best + s_worst + 1e-9)
        
        for i, r in enumerate(scored):
            r['topsis_score'] = round(float(closeness[i]), 4)
            r['topsis_breakdown'] = {
                's_best': round(float(s_best[i]), 4),
                's_worst': round(float(s_worst[i]), 4)
            }
            r['wsm_path_cost'] = round(r['cost'], 2)

    scored.sort(key=lambda x: x.get('topsis_score', 0), reverse=True)

    for i, r in enumerate(scored):
        r['rank'] = i + 1
        r['recommended'] = (i == 0)
        fe = r['flood_exposure']
        if fe < 0.15: r['risk_label'] = 'Low'
        elif fe < 0.40: r['risk_label'] = 'Medium'
        else: r['risk_label'] = 'High'
        r['safety_score'] = round(r.get('topsis_score', 0) * 100, 1)
        if '_raw_flood' in r: del r['_raw_flood']
        if '_raw_length' in r: del r['_raw_length']
        if '_raw_rank' in r: del r['_raw_rank']

    return scored

# ─────────────────────────────────────────────
# Section 7: Nearest Evacuation Center
# ─────────────────────────────────────────────

def find_top_n_evacuation_centers(
    origin_lat: float,
    origin_lon: float,
    centers: List[Dict],
    n: int = 3
) -> List[Dict]:
    """Find the top N evacuation centers by straight-line distance."""
    if not centers:
        raise ValueError("No evacuation centers loaded")

    scored = []
    for center in centers:
        dlat = (center['lat'] - origin_lat) * LAT_TO_M
        dlon = (center['lon'] - origin_lon) * LON_TO_M
        dist = math.sqrt(dlat ** 2 + dlon ** 2)
        scored.append({**center, 'distance_m': round(dist, 1)})

    scored.sort(key=lambda x: x['distance_m'])
    return scored[:n]


# ─────────────────────────────────────────────
# Raster Helpers (Tile Serving)
# ─────────────────────────────────────────────

def tile_bounds_wgs84(tx, ty, tz):
    n = 2 ** tz
    west  =  tx / n * 360.0 - 180.0
    east  = (tx + 1) / n * 360.0 - 180.0
    north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * ty / n))))
    south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (ty + 1) / n))))
    return west, south, east, north


def build_clip_mask(tx, ty, tz, size=256):
    if STRICT_BOUNDARY_GEOM is None:
        return np.ones((size, size), dtype=bool)
    west, south, east, north = tile_bounds_wgs84(tx, ty, tz)
    tile_box = box(west, south, east, north)
    clipped = STRICT_BOUNDARY_GEOM.intersection(tile_box)
    if clipped.is_empty:
        return np.zeros((size, size), dtype=bool)

    tile_w = east - west
    tile_h = north - south

    def geo_to_pix(lon, lat):
        return (lon - west) / tile_w * size, (north - lat) / tile_h * size

    img_mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(img_mask)

    def draw_poly(poly):
        coords = [geo_to_pix(lon, lat) for lon, lat in poly.exterior.coords]
        if len(coords) >= 3:
            draw.polygon(coords, fill=255)
        for interior in poly.interiors:
            coords = [geo_to_pix(lon, lat) for lon, lat in interior.coords]
            if len(coords) >= 3:
                draw.polygon(coords, fill=0)

    if clipped.geom_type == "Polygon":
        draw_poly(clipped)
    elif clipped.geom_type in ("MultiPolygon", "GeometryCollection"):
        for g in clipped.geoms:
            if g.geom_type == "Polygon":
                draw_poly(g)

    return np.array(img_mask) > 0


def get_transparent_tile():
    buf = io.BytesIO()
    Image.fromarray(np.zeros((256, 256, 4), dtype=np.uint8)).save(buf, format="PNG")
    return buf.getvalue()


def render_flood(data, valid):
    rgba = np.zeros((256, 256, 4), dtype=np.uint8)
    for val, color in FLOOD_COLORMAP.items():
        idx = (data == val) & valid
        rgba[idx] = color
    buf = io.BytesIO()
    Image.fromarray(rgba).save(buf, format="PNG")
    return buf.getvalue()


def render_continuous(data, valid, cmap_name):
    if not np.any(valid):
        return get_transparent_tile()
    fdata = data.astype(float)
    vmin, vmax = float(fdata[valid].min()), float(fdata[valid].max())
    normed = np.zeros_like(fdata)
    if vmax > vmin:
        normed[valid] = (fdata[valid] - vmin) / (vmax - vmin)
    cmap = plt.get_cmap(cmap_name)
    rgba = (cmap(normed) * 255).astype(np.uint8)
    rgba[~valid] = 0
    buf = io.BytesIO()
    Image.fromarray(rgba).save(buf, format="PNG")
    return buf.getvalue()


# ─────────────────────────────────────────────
# Startup Data Loading
# ─────────────────────────────────────────────

def _load_road_graph():
    """[1/6] & [2/6] Load road_edges.geojson and build Graph."""
    global graph, ROAD_GEOJSON
    print("[1/6] Loading road network...")

    if not os.path.exists(ROAD_FILE):
        print("      ERROR: road_edges.geojson not found!")
        return

    ROAD_GEOJSON = json.load(open(ROAD_FILE, encoding='utf-8'))
    features = ROAD_GEOJSON.get('features', [])
    print(f"      Loaded {len(features)} edge features from GeoJSON")

    print("[2/6] Building graph...")
    node_counter = 0
    node_map: Dict[Tuple, Any] = {}  # (lon_r, lat_r) -> node_id

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

        global MAX_EDGE_LENGTH
        if l_val > MAX_EDGE_LENGTH:
            MAX_EDGE_LENGTH = l_val

        graph.add_edge(u, v, {
            'osmid': props.get('osmid', ''),
            'name': str(name),
            'highway': props.get('highway', 'unclassified'),
            'length': l_val,
            'geometry': coords_raw,       # raw [[lon,lat], ...] list
            'flood_class_5yr':   None,
            'flood_class_25yr':  None,
            'flood_class_100yr': None,
            'flood_proba_5yr':   None,
            'flood_proba_25yr':  None,
            'flood_proba_100yr': None,
            'elevation': None,
            'features': None,
        })

    print(f"      Graph (raw): {graph.node_count()} nodes, {graph.edge_count()} edges")
    
    # Prune isolated components — keep only the largest connected subgraph
    _prune_to_largest_component()
    
    print(f"      Graph (final): {graph.node_count()} nodes, {graph.edge_count()} edges")


def _get_connected_component(start_node) -> Set:
    """BFS from start_node. Returns set of reachable node IDs."""
    visited: Set = set()
    queue = [start_node]
    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)
        for neighbor, _ in graph.get_neighbors(node):
            if neighbor not in visited:
                queue.append(neighbor)
    return visited


def _prune_to_largest_component():
    """Find and keep only the largest connected component in graph."""
    global main_component
    
    all_nodes = set(graph.nodes.keys())
    if not all_nodes:
        return
    
    visited_global: Set = set()
    components: List[Set] = []
    
    for node in all_nodes:
        if node not in visited_global:
            comp = _get_connected_component(node)
            components.append(comp)
            visited_global.update(comp)
    
    if not components:
        main_component = all_nodes
        return
    
    largest = max(components, key=len)
    total = len(all_nodes)
    print(f"      Graph components found: {len(components)}")
    print(f"      Largest component: {len(largest)} nodes out of {total}")
    
    if len(components) > 1:
        removed_count = total - len(largest)
        print(f"      Removing {removed_count} nodes from {len(components) - 1} smaller component(s)")
        
        # Remove nodes not in largest component
        nodes_to_remove = [n for n in list(graph.nodes.keys()) if n not in largest]
        for node in nodes_to_remove:
            del graph.nodes[node]
            if node in graph.adj:
                del graph.adj[node]
        
        # Purge stale adjacency entries pointing to removed nodes
        for node in graph.adj:
            graph.adj[node] = [
                (nb, ed) for nb, ed in graph.adj[node]
                if nb in largest
            ]
        
        # Purge stale edge entries
        graph.edges = {
            (u, v): ed
            for (u, v), ed in graph.edges.items()
            if u in largest and v in largest
        }
    else:
        print("      Network is fully connected ✅")
    
    main_component = largest


def _sample_raster(path: str, lat: float, lon: float, default: float) -> float:
    """Sample a single raster value at (lat, lon). Returns default on error."""
    try:
        with rasterio.open(path) as src:
            row, col = src.index(lon, lat)
            if row < 0 or col < 0 or row >= src.height or col >= src.width:
                return default
            val = src.read(1, window=((row, row + 1), (col, col + 1)))
            if val.size > 0:
                v = float(val.flat[0])
                if not math.isnan(v):
                    return v
    except Exception:
        pass
    return default


def _extract_edge_features():
    """[3/6] Sample rasters at each edge centroid."""
    print("[3/6] Sampling rasters at road centroids...")

    available = {k: v for k, v in RASTER_FILES.items() if os.path.exists(v)}
    missing = set(RASTER_FILES) - set(available)
    if missing:
        print(f"      WARNING: rasters not found: {missing}")

    count = 0
    for (u, v), edge in list(graph.edges.items()):
        if v < u:  # process each edge once
            continue

        coords = edge.get('geometry', [])
        if not coords:
            for key in DEFAULT_FEATURES:
                edge[key] = DEFAULT_FEATURES[key]
            # sync reverse direction
            rev = graph.edges.get((v, u))
            if rev is not None:
                for key in DEFAULT_FEATURES:
                    rev[key] = edge[key]
            continue

        # Centroid of coordinate list
        mid = coords[len(coords) // 2]
        c_lon, c_lat = mid[0], mid[1]

        feats: Dict[str, float] = {}
        for key in DEFAULT_FEATURES:
            if key in available:
                feats[key] = _sample_raster(available[key], c_lat, c_lon, DEFAULT_FEATURES[key])
            else:
                feats[key] = DEFAULT_FEATURES[key]

        edge['features'] = feats
        edge['elevation'] = feats['elevation']

        rev = graph.edges.get((v, u))
        if rev is not None:
            rev['features'] = feats
            rev['elevation'] = feats['elevation']

        count += 1
        if count % 500 == 0:
            print(f"      Sampled {count} edges...")

    print(f"      Sampled {count} edges")


def _load_models():
    """[4/6] Load XGBoost models."""
    global MODELS
    print("[4/6] Loading XGBoost models...")
    loaded = []
    for scenario in SCENARIOS:
        path = f'model_{scenario}.pkl'
        if os.path.exists(path):
            try:
                MODELS[scenario] = joblib.load(path)
                loaded.append(scenario)
            except Exception as e:
                print(f"      WARNING: failed to load {path}: {e}")
        else:
            print(f"      WARNING: {path} not found")

    if loaded:
        print(f"      Models loaded: {', '.join(loaded)}")
    else:
        print("      No XGBoost models found — flood predictions unavailable")


def _precompute_flood():
    """[5/6] Pre-compute flood predictions for all edges × scenarios."""
    print("[5/6] Pre-computing flood predictions...")

    if not MODELS:
        print("      Skipped — no models available")
        return

    for scenario in SCENARIOS:
        model = MODELS.get(scenario)
        if model is None:
            continue

        count = 0
        for (u, v), edge in list(graph.edges.items()):
            if v < u:
                continue
            feats = edge.get('features')
            if feats is None:
                edge[f'flood_class_{scenario}'] = 0
                edge[f'flood_proba_{scenario}'] = 0.0
                rev = graph.edges.get((v, u))
                if rev:
                    rev[f'flood_class_{scenario}'] = 0
                    rev[f'flood_proba_{scenario}'] = 0.0
                continue

            try:
                X = np.array([[
                    feats['elevation'],
                    feats['slope'],
                    feats['land_cover'],
                    feats['dist_waterway'],
                ]])
                flood_class = int(model.predict(X)[0])
                proba = model.predict_proba(X)[0]
                # Use P(class 3) = high flood probability
                flood_proba = float(proba[3] if len(proba) > 3 else max(proba))
            except Exception:
                flood_class = 0
                flood_proba = 0.0

            edge[f'flood_class_{scenario}'] = flood_class
            edge[f'flood_proba_{scenario}'] = flood_proba
            rev = graph.edges.get((v, u))
            if rev:
                rev[f'flood_class_{scenario}'] = flood_class
                rev[f'flood_proba_{scenario}'] = flood_proba

            count += 1

        print(f"      {scenario}: {count} edges processed")


def _load_evac_centers():
    """[6/6] Load evacuation centers into memory."""
    global evacuation_centers, EVAC_GEOJSON
    print("[6/6] Loading evacuation centers...")

    if not os.path.exists(EVAC_FILE):
        print(f"      WARNING: {EVAC_FILE} not found")
        return

    with open(EVAC_FILE, encoding='utf-8') as f:
        EVAC_GEOJSON = json.load(f)

    for feat in EVAC_GEOJSON.get('features', []):
        coords = feat['geometry']['coordinates']
        props = feat.get('properties', {})
        evacuation_centers.append({
            'lat': float(coords[1]),
            'lon': float(coords[0]),
            'facility': props.get('facility', 'Unknown Center'),
            'barangay': props.get('barangay', ''),
            'type': props.get('type', 'Other'),
        })

    print(f"      {len(evacuation_centers)} centers loaded")


# ─────────────────────────────────────────────
# Section 8: Route Endpoint
# ─────────────────────────────────────────────

@app.post("/route")
async def find_route(request: RouteRequest):
    """
    Main flood-aware evacuation routing endpoint.

    Automatically routes to the nearest evacuation center.
    Returns K ranked routes with geometry and metrics.
    """
    t0 = time.time()

    # --- Input validation ---
    if not (-90 <= request.origin_lat <= 90):
        raise HTTPException(400, "Invalid latitude")
    if not (-180 <= request.origin_lon <= 180):
        raise HTTPException(400, "Invalid longitude")
    if request.scenario not in SCENARIOS:
        raise HTTPException(400, f"scenario must be one of: {SCENARIOS}")

    K = min(max(request.k or 3, 1), 5)

    if graph.node_count() == 0:
        raise HTTPException(503, "Road network not loaded — please wait for server startup")

    # --- Snap origin to nearest road node ---
    try:
        origin_node, origin_dist = get_nearest_node(graph, request.origin_lat, request.origin_lon)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # --- Find target centers ---
    # Focus on the Top 3 candidates that are within a reasonable 'Search Horizon'
    # We don't want to propose centers 10km away if one is 500m away, 
    # UNLESS the 500m one is unreachable or extremely risky.
    candidates = find_top_n_evacuation_centers(request.origin_lat, request.origin_lon, evacuation_centers, n=5)
    
    target_centers = []
    if candidates:
        d_min = candidates[0]['distance_m']
        for c in candidates:
            # Adaptive Threshold: Allow variety, but skip centers that are 
            # disproportionately far (e.g. > 2km and > 3x the d_min)
            if c['distance_m'] < 2000 or c['distance_m'] < d_min * 3.0:
                target_centers.append(c)
                if len(target_centers) >= 3: break
    
    w = request.weights or {'flood': 0.5, 'distance': 0.3, 'road_class': 0.2}
    raw_routes = []
    seen_paths = set()

    # 1. Find the BEST route to each of the valid target centers
    for center in target_centers:
        try:
            d_node, d_dist = get_nearest_node(graph, center['lat'], center['lon'])
            if d_node == origin_node: continue
            
            cost, path = dijkstra(graph, origin_node, d_node, request.scenario, w)
            if path:
                pt = tuple(path)
                if pt not in seen_paths:
                    seen_paths.add(pt)
                    raw_routes.append({
                        'path': path, 
                        'cost': cost, 
                        'rank': 1, 
                        'destination_info': center,
                        'dest_node': d_node
                    })
        except:
            continue

    # 2. If we need more routes (K > 3) or if some centers were unreachable, 
    # find alternatives to the very NEAREST center
    if len(raw_routes) < K and target_centers:
        main_center = target_centers[0]
        try:
            d_node, d_dist = get_nearest_node(graph, main_center['lat'], main_center['lon'])
            # Ask for more alternatives to this center
            alts = yens_k_shortest_paths(graph, origin_node, d_node, K, request.scenario, w)
            for alt in alts:
                pt = tuple(alt['path'])
                if pt not in seen_paths:
                    seen_paths.add(pt)
                    alt['destination_info'] = main_center
                    alt['dest_node'] = d_node
                    raw_routes.append(alt)
        except:
            pass

    if not raw_routes:
        raise HTTPException(404, "No evacuation route found to any nearby center.")

    # --- Score and rank across ALL candidates ---
    scored = score_routes(raw_routes[:K], graph, request.scenario, w)

    # --- Build GeoJSON features ---
    origin_node_data = graph.nodes.get(origin_node, {})
    
    # The 'primary' destination is whatever Rank 1 ends at
    primary_route = scored[0]
    primary_center = primary_route.get('destination_info', {})
    primary_d_node = primary_route.get('dest_node')
    primary_d_data = graph.nodes.get(primary_d_node, {})

    features = []
    for route in scored:
        coordinates = []
        for i in range(len(route['path']) - 1):
            u = route['path'][i]
            v = route['path'][i + 1]
            edge = graph.get_edge(u, v)
            if edge and edge.get('geometry'):
                coordinates.append(edge['geometry'])
            else:
                # Fallback: straight line between nodes
                nu = graph.nodes.get(u, {})
                nv = graph.nodes.get(v, {})
                coordinates.append([
                    [nu.get('lon', 0), nu.get('lat', 0)],
                    [nv.get('lon', 0), nv.get('lat', 0)],
                ])

        features.append({
            'type': 'Feature',
            'geometry': {'type': 'MultiLineString', 'coordinates': coordinates},
            'properties': {
                'rank': route['rank'],
                'recommended': route['recommended'],
                'scenario': request.scenario,
                'total_length_m': route['total_length_m'],
                'total_length_km': route['total_length_km'],
                'flood_exposure': route['flood_exposure'],
                'max_flood_class': route['max_flood_class'],
                'flood_class_counts': route['flood_class_counts'],
                'risk_label': route['risk_label'],
                'topsis_score': route.get('topsis_score', 0),
                'wsm_path_cost': route.get('wsm_path_cost', 0),
                'safety_score': route['safety_score'],
                'similarity_score': route.get('similarity_score', 0),
                'segment_count': route['segment_count'],
                'segments': route['segments'],
                'destination_name': route.get('destination_info', {}).get('facility', 'Unknown'),
                'destination_barangay': route.get('destination_info', {}).get('barangay', ''),
            },
        })

    elapsed_ms = round((time.time() - t0) * 1000, 2)

    return {
        'scenario': request.scenario,
        'k_requested': K,
        'k_found': len(features),
        'origin': {
            'lat': request.origin_lat,
            'lon': request.origin_lon,
            'nearest_node_id': str(origin_node),
            'nearest_node_lat': origin_node_data.get('lat'),
            'nearest_node_lon': origin_node_data.get('lon'),
            'snap_distance_m': round(origin_dist, 1),
        },
        'destination': {
            'name': primary_center.get('facility', 'Unknown'),
            'barangay': primary_center.get('barangay', ''),
            'lat': primary_center.get('lat'),
            'lon': primary_center.get('lon'),
            'nearest_node_id': str(primary_d_node),
            'nearest_node_lat': primary_d_data.get('lat'),
            'nearest_node_lon': primary_d_data.get('lon'),
            'snap_distance_m': 0, # Placeholder
            'straight_line_distance_m': primary_center.get('distance_m', 0),
        },
        'routes': features,
        'computation_time_ms': elapsed_ms,
    }


# ─────────────────────────────────────────────
# Tile & GeoJSON Passthrough Endpoints
# ─────────────────────────────────────────────

@app.get("/boundary")
async def get_boundary():
    path = "district1_boundary.geojson"
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    raise HTTPException(status_code=404, detail="Boundary not found")


@app.get("/roads")
async def get_roads():
    if ROAD_GEOJSON is None:
        raise HTTPException(404, "Road GeoJSON not loaded")
    return ROAD_GEOJSON


@app.get("/evacuation-centers")
async def get_evacuation_centers():
    if EVAC_GEOJSON is None:
        raise HTTPException(404, "Evacuation centers not loaded")
    return EVAC_GEOJSON


@app.get("/tiles/{layer_name}/{z}/{x}/{y}.png")
async def get_tile(layer_name: str, z: int, x: int, y: int, clip: bool = Query(True)):
    from rio_tiler.io import Reader
    from rio_tiler.errors import TileOutsideBounds

    info = LAYERS_MAP.get(layer_name)
    if not info:
        return Response(content=get_transparent_tile(), media_type="image/png")

    file_path, cmap_or_type, nodata_override = info
    if not os.path.exists(file_path):
        return Response(content=get_transparent_tile(), media_type="image/png")

    try:
        with Reader(file_path) as src:
            try:
                kwargs = {"tilesize": 256}
                if nodata_override is not None:
                    kwargs["nodata"] = nodata_override
                img = src.tile(x, y, z, **kwargs)
            except TileOutsideBounds:
                return Response(content=get_transparent_tile(), media_type="image/png")

        data = img.data[0]
        raw_mask = img.mask
        valid = (raw_mask == 255) if raw_mask.dtype == np.uint8 else (raw_mask > 0)

        if clip:
            valid = valid & build_clip_mask(x, y, z)

        if not np.any(valid):
            return Response(content=get_transparent_tile(), media_type="image/png")

        content = (
            render_flood(data, valid)
            if cmap_or_type == "flood"
            else render_continuous(data, valid, cmap_or_type)
        )
        return Response(content=content, media_type="image/png",
                        headers={"Cache-Control": "no-cache, no-store"})

    except Exception as e:
        print(f"Tile error {layer_name} {z}/{x}/{y}: {e}")
        return Response(content=get_transparent_tile(), media_type="image/png")


@app.get("/flood-segments")
async def get_flood_segments(scenario: str = Query("25yr")):
    """Return all road edges with flood predictions as GeoJSON."""
    if scenario not in SCENARIOS:
        raise HTTPException(400, f"scenario must be one of {SCENARIOS}")

    features = []
    seen = set()
    for (u, v), edge in graph.edges.items():
        key = (min(u, v), max(u, v))
        if key in seen:
            continue
        seen.add(key)

        coords = edge.get('geometry', [])
        if not coords:
            continue

        flood_class  = int(edge.get(f'flood_class_{scenario}', 0) or 0)
        flood_proba  = float(edge.get(f'flood_proba_{scenario}', 0.0) or 0.0)
        risk_label = 'Low' if flood_proba < 0.2 else ('Medium' if flood_proba < 0.5 else 'High')

        features.append({
            'type': 'Feature',
            'geometry': {'type': 'LineString', 'coordinates': coords},
            'properties': {
                'osmid': edge.get('osmid', ''),
                'name': edge.get('name', 'Unnamed Road'),
                'highway': edge.get('highway', 'unclassified'),
                'length': edge.get('length', 0.0),
                'flood_class': flood_class,
                'flood_proba': round(flood_proba, 4),
                'risk_label': risk_label,
            },
        })

    return {'type': 'FeatureCollection', 'features': features}


@app.get("/graph-stats")
async def get_graph_stats():
    lats = [n['lat'] for n in graph.nodes.values()]
    lons = [n['lon'] for n in graph.nodes.values()]
    return {
        'total_nodes': graph.node_count(),
        'total_edges': graph.edge_count(),
        'scenarios_precomputed': list(MODELS.keys()),
        'bounds': {
            'north': max(lats) if lats else 0,
            'south': min(lats) if lats else 0,
            'east': max(lons) if lons else 0,
            'west': min(lons) if lons else 0,
        },
    }


@app.get("/graph/diagnostics")
async def get_graph_diagnostics():
    """Detailed graph health check — use this to verify connectivity without QGIS."""
    if graph.node_count() == 0:
        return {"error": "Graph not loaded yet"}

    lats = [n['lat'] for n in graph.nodes.values()]
    lons = [n['lon'] for n in graph.nodes.values()]

    # Sample first 3 nodes
    sample_nodes = [
        {'id': str(nid), 'lat': n['lat'], 'lon': n['lon']}
        for nid, n in list(graph.nodes.items())[:3]
    ]

    # Road type counts
    highway_counts: Dict[str, int] = {}
    seen_edges: Set = set()
    for (u, v), edge in graph.edges.items():
        key = (min(u, v), max(u, v))
        if key in seen_edges:
            continue
        seen_edges.add(key)
        hw = str(edge.get('highway', 'other') or 'other')
        hw = hw if hw in ('primary', 'secondary', 'tertiary', 'residential', 'service') else 'other'
        highway_counts[hw] = highway_counts.get(hw, 0) + 1

    # Verify the graph actually has the main component set
    is_connected = len(main_component) == graph.node_count() and graph.node_count() > 0

    return {
        "total_nodes": graph.node_count(),
        "total_edges": graph.edge_count(),
        "is_connected": is_connected,
        "main_component_size": len(main_component),
        "evacuation_centers_loaded": len(evacuation_centers),
        "models_loaded": list(MODELS.keys()),
        "bounds": {
            "north": round(max(lats), 6),
            "south": round(min(lats), 6),
            "east": round(max(lons), 6),
            "west": round(min(lons), 6),
        },
        "sample_nodes": sample_nodes,
        "road_type_breakdown": {
            "primary":     highway_counts.get('primary', 0),
            "secondary":   highway_counts.get('secondary', 0),
            "tertiary":    highway_counts.get('tertiary', 0),
            "residential": highway_counts.get('residential', 0),
            "service":     highway_counts.get('service', 0),
            "other":       highway_counts.get('other', 0),
        },
    }



@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "graph_nodes": graph.node_count(),
        "graph_edges": graph.edge_count(),
        "evac_centers": len(evacuation_centers),
        "models_loaded": list(MODELS.keys()),
    }


# ─────────────────────────────────────────────
# Startup Event
# ─────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    print("=" * 52)
    print("  CodeFish Flood-Aware Routing — Starting Up  ")
    print("=" * 52)

    _load_road_graph()
    _extract_edge_features()
    _load_models()
    _precompute_flood()
    _load_evac_centers()

    print()
    print("Application ready.")
    print("POST /route — flood-aware routing active")
    print("=" * 52)


# ─────────────────────────────────────────────
# Static & Index
# ─────────────────────────────────────────────

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def read_index():
    return FileResponse("index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
