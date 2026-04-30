# Install: pip install fastapi uvicorn rio-tiler matplotlib shapely geopandas pillow osmnx joblib rasterio networkx scikit-learn xgboost
# Run: uvicorn main:app --reload --port 8000
# Open: http://localhost:8000

from fastapi import FastAPI, Response, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rio_tiler.io import Reader
from rio_tiler.errors import TileOutsideBounds
import matplotlib.pyplot as plt
import numpy as np
import geopandas as gpd
from shapely.geometry import box, mapping, Point, LineString
import rasterio
import os
import io
import json
import math
import heapq
import time
import copy
from typing import List, Dict, Tuple, Optional
from PIL import Image, ImageDraw
import networkx as nx
import joblib
from shapely.ops import linemerge
import ftplib
import gzip
import datetime

app = FastAPI(title="CodeFish Flood-Aware Evacuation Routing")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# Boundary loading for raster clipping
# ─────────────────────────────────────────────
BOUNDARY_FILE = "district1_boundary_strict.geojson"
STRICT_BOUNDARY_GEOM = None

if os.path.exists(BOUNDARY_FILE):
    try:
        gdf = gpd.read_file(BOUNDARY_FILE)
        if not gdf.empty:
            STRICT_BOUNDARY_GEOM = gdf.geometry.union_all() if hasattr(gdf.geometry, 'union_all') else gdf.geometry.unary_union
            print(f"Loaded boundary: {STRICT_BOUNDARY_GEOM.geom_type}, bounds={STRICT_BOUNDARY_GEOM.bounds}")
    except Exception as e:
        print(f"Error loading boundary: {e}")

# ─────────────────────────────────────────────
# Road network - load or download on startup
# ─────────────────────────────────────────────
ROAD_FILE = "road_edges.geojson"
road_geojson = None


def load_or_download_roads():
    global road_geojson
    if os.path.exists(ROAD_FILE):
        print(f"Loading roads from {ROAD_FILE}...")
        with open(ROAD_FILE, "r", encoding="utf-8") as f:
            road_geojson = json.load(f)
        print(f"Roads loaded: {len(road_geojson.get('features', []))} features")
        return

    print("Downloading road network from OSMnx...")
    try:
        import osmnx as ox
        try:
            G = ox.graph_from_place(
                "District 1, Quezon City, Metro Manila, Philippines",
                network_type="drive",
            )
        except Exception:
            G = ox.graph_from_place(
                "Quezon City, Metro Manila, Philippines",
                network_type="drive",
            )
        edges = ox.graph_to_gdfs(G, nodes=False, edges=True).reset_index()

        def simplify_geom(geom):
            if geom.geom_type == "MultiLineString":
                from shapely.ops import linemerge

                merged = linemerge(geom)
                if merged.geom_type == "LineString":
                    return merged
                # fallback: longest segment
                return max(geom.geoms, key=lambda g: g.length)
            return geom

        edges["geometry"] = edges["geometry"].apply(simplify_geom)

        # Normalize fields
        def get_name(row):
            v = row.get("name", None)
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return "Unnamed Road"
            if isinstance(v, list):
                return v[0] if v else "Unnamed Road"
            return str(v)

        def get_highway(row):
            v = row.get("highway", "unclassified")
            if isinstance(v, list):
                v = v[0] if v else "unclassified"
            return str(v)

        def get_osmid(row):
            v = row.get("osmid", 0)
            if isinstance(v, list):
                v = v[0] if v else 0
            return int(v) if v else 0

        features = []
        for _, row in edges.iterrows():
            try:
                geom = row["geometry"]
                if geom is None or geom.is_empty:
                    continue
                length = round(float(row.get("length", 0)), 2)
                feature = {
                    "type": "Feature",
                    "geometry": mapping(geom),
                    "properties": {
                        "osmid": get_osmid(row),
                        "name": get_name(row),
                        "highway": get_highway(row),
                        "length": length,
                    },
                }
                features.append(feature)
            except Exception:
                continue

        road_geojson = {"type": "FeatureCollection", "features": features}
        with open(ROAD_FILE, "w", encoding="utf-8") as f:
            json.dump(road_geojson, f)
        print(f"Roads saved: {len(features)} features")

    except Exception as e:
        print(f"Error downloading roads: {e}")
        road_geojson = {"type": "FeatureCollection", "features": []}


# Load roads at startup
load_or_download_roads()


# ─────────────────────────────────────────────
# Road graph for routing
# ─────────────────────────────────────────────
ROAD_GRAPH_NODES = {}  # node_id -> (lon, lat)
ROAD_GRAPH_ADJ = {}  # node_id -> list[(neighbor_id, length)]
ROAD_GRAPH_BUILT = False


def _node_id_from_coord(lon: float, lat: float) -> str:
    # round to 6 decimal places to merge nearly-identical nodes
    return f"{lon:.6f},{lat:.6f}"


def build_road_graph():
    """Build a simple undirected graph from the road GeoJSON using segment endpoints."""
    global ROAD_GRAPH_NODES, ROAD_GRAPH_ADJ, ROAD_GRAPH_BUILT, road_geojson

    if ROAD_GRAPH_BUILT:
        return

    if road_geojson is None:
        # Try to load from disk
        if os.path.exists(ROAD_FILE):
            with open(ROAD_FILE, "r", encoding="utf-8") as f:
                road_geojson = json.load(f)
        else:
            load_or_download_roads()

    ROAD_GRAPH_NODES = {}
    ROAD_GRAPH_ADJ = {}

    if not road_geojson:
        print("build_road_graph: no road_geojson available")
        ROAD_GRAPH_BUILT = True
        return

    for feature in road_geojson.get("features", []):
        geom = feature.get("geometry", {})
        if geom.get("type") != "LineString":
            continue
        coords = geom.get("coordinates") or []
        if len(coords) < 2:
            continue

        (lon1, lat1) = coords[0]
        (lon2, lat2) = coords[-1]
        n1 = _node_id_from_coord(lon1, lat1)
        n2 = _node_id_from_coord(lon2, lat2)

        length = feature.get("properties", {}).get("length")
        try:
            edge_len = float(length) if length is not None else None
        except Exception:
            edge_len = None

        if edge_len is None:
            # simple planar distance in degrees (rough fallback)
            dx = lon2 - lon1
            dy = lat2 - lat1
            edge_len = float((dx * dx + dy * dy) ** 0.5)

        if n1 not in ROAD_GRAPH_NODES:
            ROAD_GRAPH_NODES[n1] = (lon1, lat1)
        if n2 not in ROAD_GRAPH_NODES:
            ROAD_GRAPH_NODES[n2] = (lon2, lat2)

        ROAD_GRAPH_ADJ.setdefault(n1, []).append((n2, edge_len))
        ROAD_GRAPH_ADJ.setdefault(n2, []).append((n1, edge_len))

    ROAD_GRAPH_BUILT = True
    print(f"Road graph built with {len(ROAD_GRAPH_NODES)} nodes.")


def _nearest_node(lon: float, lat: float):
    """Return node_id of graph node nearest to given lon/lat."""
    if not ROAD_GRAPH_BUILT:
        build_road_graph()
    best_id = None
    best_d2 = None
    for nid, (nlon, nlat) in ROAD_GRAPH_NODES.items():
        dx = nlon - lon
        dy = nlat - lat
        d2 = dx * dx + dy * dy
        if best_d2 is None or d2 < best_d2:
            best_d2 = d2
            best_id = nid
    return best_id


def _dijkstra(origin_id: str):
    """Dijkstra using a min-heap. Returns (dist, prev) maps."""
    import heapq

    dist = {origin_id: 0.0}
    prev = {}
    visited = set()
    heap = [(0.0, origin_id)]

    while heap:
        d, u = heapq.heappop(heap)
        if u in visited:
            continue
        visited.add(u)
        for v, w in ROAD_GRAPH_ADJ.get(u, []):
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))

    return dist, prev


def _reconstruct_path(prev, origin_id: str, dest_id: str):
    path = []
    cur = dest_id
    while True:
        path.append(cur)
        if cur == origin_id:
            break
        if cur not in prev:
            return []
        cur = prev[cur]
    path.reverse()
    return path


def _yen_k_shortest_paths(origin_id: str, dest_id: str, k: int):
    """
    Basic Yen's algorithm for k-shortest loopless paths between origin and dest.
    Returns a list of (path_nodes, total_length).
    """
    import copy
    import heapq

    if origin_id == dest_id:
        return []

    if not ROAD_GRAPH_BUILT:
        build_road_graph()

    # First shortest path
    dist0, prev0 = _dijkstra(origin_id)
    if dest_id not in dist0:
        return []
    base_path = _reconstruct_path(prev0, origin_id, dest_id)
    if not base_path:
        return []

    paths = [(base_path, dist0[dest_id])]
    candidates = []

    original_adj = ROAD_GRAPH_ADJ

    for k_i in range(1, k):
        last_path_nodes = paths[-1][0]
        for i in range(len(last_path_nodes) - 1):
            spur_node = last_path_nodes[i]
            root_path = last_path_nodes[: i + 1]

            # Clone adjacency for temporary modification
            adj_clone = copy.deepcopy(original_adj)

            # Remove edges that would recreate previously found paths
            for p, _plen in paths:
                if len(p) > i and p[: i + 1] == root_path:
                    u = p[i]
                    v = p[i + 1]
                    adj_clone[u] = [(n, w) for (n, w) in adj_clone.get(u, []) if n != v]

            # Temporarily remove all edges entering nodes in root_path except spur_node
            removed_nodes = set(root_path[:-1])
            for rn in removed_nodes:
                adj_clone[rn] = []

            # Run Dijkstra on modified graph from spur_node
            dist_spur, prev_spur = _dijkstra_on_adj(spur_node, adj_clone)
            if dest_id not in dist_spur:
                continue

            spur_path = _reconstruct_path(prev_spur, spur_node, dest_id)
            if not spur_path:
                continue

            total_path = root_path[:-1] + spur_path

            total_len = 0.0
            for u, v in zip(total_path[:-1], total_path[1:]):
                for nb, w in original_adj.get(u, []):
                    if nb == v:
                        total_len += w
                        break

            if all(existing[0] != total_path for existing in paths):
                heapq.heappush(candidates, (total_len, total_path))

        if not candidates:
            break

        length, new_path = heapq.heappop(candidates)
        paths.append((new_path, length))

    return paths


def _dijkstra_on_adj(origin_id: str, adj):
    """Dijkstra variant that operates on a provided adjacency dict."""
    import heapq

    dist = {origin_id: 0.0}
    prev = {}
    visited = set()
    heap = [(0.0, origin_id)]

    while heap:
        d, u = heapq.heappop(heap)
        if u in visited:
            continue
        visited.add(u)
        for v, w in adj.get(u, []):
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))

    return dist, prev


# ─────────────────────────────────────────────
# Evacuation centers - load or geocode
# ─────────────────────────────────────────────
EVAC_FILE = "evacuation_centers.geojson"
evac_geojson = None

EVAC_CENTERS = [
    # Alicia
    {"barangay": "Alicia", "facility": "Brgy Alicia Hall \u2013 3rd Floor"},
    {"barangay": "Alicia", "facility": "Bago bantay Elementary School"},
    # Bagong Pag-asa
    {"barangay": "Bagong Pag-asa", "facility": "Open Ground"},
    {"barangay": "Bagong Pag-asa", "facility": "Bagong Pag-asa Elementary School"},
    {"barangay": "Bagong Pag-asa", "facility": "Multipurpose Covered Court"},
    # Bahay Toro
    {"barangay": "Bahay Toro", "facility": "Bahay Toro Basketball Court"},
    {"barangay": "Bahay Toro", "facility": "Basketball Court"},
    {"barangay": "Bahay Toro", "facility": "Toro Hills Elementary School"},
    # Balingasa
    {"barangay": "Balingasa", "facility": "Barangay Hall Covered Court"},
    # Bungad
    {"barangay": "Bungad", "facility": "Barangay Bungad Covered Court"},
    {"barangay": "Bungad", "facility": "Bungad Elementary School"},
    # Damar
    {"barangay": "Damar", "facility": "Basketball Covered Court"},
    {"barangay": "Damar", "facility": "Multi-Purpose Hall"},
    {"barangay": "Damar", "facility": "Function Room"},
    # Damayan
    {"barangay": "Damayan", "facility": "Cong Calalay Elementary School (F. Bautista Street)"},
    {"barangay": "Damayan", "facility": "Minor Basilica of Saint Pedro Bautista"},
    # Del Monte
    {"barangay": "Del Monte", "facility": "Dalupan Elementary School"},
    {"barangay": "Del Monte", "facility": "San Francisco Elementary School"},
    # Katipunan
    {"barangay": "Katipunan", "facility": "San Antonio Elementary School"},
    # Lourdes
    {"barangay": "Lourdes", "facility": "Basketball Covered Court"},
    # Maharlika
    {"barangay": "Maharlika", "facility": "PureGold Kanlaon"},
    {"barangay": "Maharlika", "facility": "National Shrine of Our Lady of Lourdes"},
    # Manresa
    {"barangay": "Manresa", "facility": "Basketball Covered Court"},
    {"barangay": "Manresa", "facility": "Play Ground"},
    # Mariblo
    {"barangay": "Mariblo", "facility": "Barangay Hall (Mariblo)"},
    {"barangay": "Mariblo", "facility": "Day Care Center"},
    # Masambong
    {"barangay": "Masambong", "facility": "Tennis Court"},
    {"barangay": "Masambong", "facility": "Gazebo Hall"},
    {"barangay": "Masambong", "facility": "Parking Space"},
    # Nayong Kanluran
    {"barangay": "Nayong Kanluran", "facility": "Nayong Kanluran Barangay Hall"},
    {"barangay": "Nayong Kanluran", "facility": "Nayong Kanluran Covered Court"},
    # Paang Bundok
    {"barangay": "Paang Bundok", "facility": "Barangay Hall Paang Bundok"},
    {"barangay": "Paang Bundok", "facility": "Open Space"},
    # Pag-ibig sa Nayon
    {"barangay": "Pag-ibig sa Nayon", "facility": "Barangay Covered Court"},
    {"barangay": "Pag-ibig sa Nayon", "facility": "Yakap Day Care Center"},
    {
        "barangay": "Pag-ibig sa Nayon",
        "facility": "San Jose Elementary School (pag ibig sa nayon)",
    },
    # Paltok
    {"barangay": "Paltok", "facility": "Paltok Covered Court"},
    {"barangay": "Paltok", "facility": "Paltok Elementary School"},
    {"barangay": "Paltok", "facility": "Bayanihan Elementary School"},
    {"barangay": "Paltok", "facility": "Paltok Barangay Hall"},
    # Paraiso
    {"barangay": "Paraiso", "facility": "Residential House"},
    # Phil-am
    {"barangay": "Phil-am", "facility": "Phil-am Football Field"},
    # Project 6
    {"barangay": "Project 6", "facility": "Veterans Covered Court"},
    {"barangay": "Project 6", "facility": "Project 6 Elementary School"},
    {"barangay": "Project 6", "facility": "Project 6 Park"},
    {"barangay": "Project 6", "facility": "Multipurpose Hall \u2013 3rd Floor"},
    # Ramon Magsaysay
    {"barangay": "Ramon Magsaysay", "facility": "Parking Space & 3rd floor of Brgy."},
    {"barangay": "Ramon Magsaysay", "facility": "Covered Court"},
    # Salvacion
    {"barangay": "Salvacion", "facility": "Salvacion Barangay Hall"},
    # San Antonio
    {"barangay": "San Antonio", "facility": "San Antonio De Padua Parish Church"},
    {"barangay": "San Antonio", "facility": "San Jose Covered Court"},
    # San Isidro Labrador
    {"barangay": "San Isidro Labrador", "facility": "San Isidro Labrador Barangay Hall"},
    # San Jose
    {"barangay": "San Jose", "facility": "San Jose Elementary School"},
    {"barangay": "San Jose", "facility": "Basketball Covered Court"},
    # Siena
    {"barangay": "Siena", "facility": "Siena Barangay Hall (4th Floor)"},
    {"barangay": "Siena", "facility": "Siena College of Quezon City (Open Space)"},
    # St. Peter
    {"barangay": "St. Peter", "facility": "Barangay Multipurpose Hall"},
    # Sta. Cruz
    {"barangay": "Sta Cruz", "facility": "Barangay Multipurpose Hall"},
    {"barangay": "Sta Cruz", "facility": "Day Care Center (3rd Floor)"},
    # Sta. Teresita
    {"barangay": "Sta Teresita", "facility": "Sta. Teresita Covered Court"},
    # Sto Cristo
    {"barangay": "Sto Cristo", "facility": "Sto. Cristo Elementary School"},
    # Sto. Domingo
    {"barangay": "Sto Domingo", "facility": "The Santo Domingo Church and Convent"},
    # Talayan
    {"barangay": "Talayan", "facility": "Talayan Village Park"},
    # Vasra
    {"barangay": "Vasra", "facility": "Barangay hall (3rd Floor)"},
    {"barangay": "Vasra", "facility": "VMMC Hospital Open Space"},
    # Veterans Village
    {"barangay": "Veterans Village", "facility": "Esteban Abada Elementary School"},
    {"barangay": "Veterans Village", "facility": "Lucresia Kasilag High School"},
    {"barangay": "Veterans Village", "facility": "Covered Court"},
    # West Triangle
    {"barangay": "West Triangle", "facility": "Barangay Hall Multipurpose Hall"},
    {"barangay": "West Triangle", "facility": "Basketball Covered Court"},
    {"barangay": "West Triangle", "facility": "Open Space (JASMS compound)"},
]


def classify_evac_type(name: str) -> str:
    n = (name or "").lower()
    if "hall" in n or "barangay" in n:
        return "Barangay Hall"
    if any(k in n for k in ["elementary", "high school", "school", "college"]):
        return "School"
    if any(k in n for k in ["church", "parish", "basilica", "shrine", "santo", "san"]):
        return "Church"
    if any(k in n for k in ["court", "covered", "gymnasium", "gym"]):
        return "Court/Gymnasium"
    if any(k in n for k in ["open", "ground", "park", "parking", "playground", "field"]):
        return "Open Space"
    if "hospital" in n:
        return "Hospital"
    return "Other"


def load_or_generate_evac_centers():
    """
    Load evacuation_centers.geojson from disk if present.
    Otherwise geocode all facilities (with barangay centroid fallback)
    and write the GeoJSON file once.
    """
    global evac_geojson

    if os.path.exists(EVAC_FILE):
        print(f"Loading evacuation centers from {EVAC_FILE}...")
        try:
            with open(EVAC_FILE, "r", encoding="utf-8") as f:
                evac_geojson = json.load(f)
            existing_count = len(evac_geojson.get("features", []))
            target_count = len(EVAC_CENTERS)
            print(
                f"Evacuation centers loaded: {existing_count} features "
                f"(configured: {target_count})"
            )
            if existing_count == target_count:
                return
            else:
                print(
                    "Evacuation center count mismatch; regenerating "
                    "GeoJSON from configured list..."
                )
        except Exception as e:
            print(f"Error loading {EVAC_FILE}: {e}")
            evac_geojson = {"type": "FeatureCollection", "features": []}

    print("Generating evacuation centers GeoJSON...")
    try:
        import osmnx as ox
    except Exception as e:
        print(f"Error importing osmnx for geocoding: {e}")
        evac_geojson = {"type": "FeatureCollection", "features": []}
        return

    barangay_centroids = {}
    features = []
    total = len(EVAC_CENTERS)

    for idx, center in enumerate(EVAC_CENTERS, start=1):
        barangay = center["barangay"]
        facility = center["facility"]
        print(f"Geocoding {idx} of {total}: {facility}...")

        query = f"{facility}, {barangay}, Quezon City, Philippines"
        lat = lon = None
        geocoded = False

        try:
            lat, lon = ox.geocode(query)
            geocoded = True
        except Exception:
            # Fallback: barangay centroid
            if barangay not in barangay_centroids:
                try:
                    b_lat, b_lon = ox.geocode(
                        f"{barangay}, Quezon City, Philippines"
                    )
                    barangay_centroids[barangay] = (b_lat, b_lon)
                except Exception as e:
                    print(f"  Failed to geocode barangay {barangay}: {e}")
                    barangay_centroids[barangay] = (None, None)

            b_lat, b_lon = barangay_centroids.get(barangay, (None, None))
            lat, lon = b_lat, b_lon
            geocoded = False

        if lat is None or lon is None:
            print(f"  Skipping {facility}: no coordinates found")
            continue

        ftype = classify_evac_type(facility)
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(lon), float(lat)],
            },
            "properties": {
                "id": idx,
                "barangay": barangay,
                "facility": facility,
                "type": ftype,
                "geocoded": geocoded,
            },
        }
        features.append(feature)

    evac_geojson = {"type": "FeatureCollection", "features": features}
    try:
        with open(EVAC_FILE, "w", encoding="utf-8") as f:
            json.dump(evac_geojson, f, ensure_ascii=False, indent=2)
        print(f"Evacuation centers saved: {len(features)} features")
    except Exception as e:
        print(f"Error writing {EVAC_FILE}: {e}")


# ─────────────────────────────────────────────
# Raster layer configuration
# ─────────────────────────────────────────────
LAYERS_MAP = {
    "flood_5yr":    ("flood_hazard_fh5yr_aligned.tif",   "flood",   255.0),
    "flood_25yr":   ("flood_hazard_fh25yr_aligned.tif",  "flood",   255.0),
    "flood_100yr":  ("flood_hazard_fh100yr_aligned.tif", "flood",   255.0),
    "land_cover":   ("land_cover_aligned.tif",            "tab20",   0.0),
    "dist_waterway":("distance_to_waterways.tif",         "Blues_r", None),
    "elevation":    ("rasters_COP30/output_hh.tif",       "terrain", None),
    "slope":        ("viz/viz.hh_slope.tif",              "YlOrRd",  None),
}

FLOOD_RASTERS = {
    "5yr":   "flood_hazard_fh5yr_aligned.tif",
    "25yr":  "flood_hazard_fh25yr_aligned.tif",
    "100yr": "flood_hazard_fh100yr_aligned.tif",
}

FLOOD_MODELS = {
    "5yr":   "model_5yr.pkl",
    "25yr":  "model_25yr.pkl",
    "100yr": "model_100yr.pkl",
}

FLOOD_COLORMAP = {
    1: (255, 255,   0, 180),
    2: (255, 140,   0, 180),
    3: (255,   0,   0, 180),
}

# ─────────────────────────────────────────────
# Helpers
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


def sample_raster_at_point(raster_path, lon, lat):
    """Sample a raster at a given lon/lat coordinate. Returns float or None."""
    try:
        with rasterio.open(raster_path) as src:
            row, col = src.index(lon, lat)
            # bounds check
            if row < 0 or col < 0 or row >= src.height or col >= src.width:
                return None
            val = src.read(1)[row, col]
            return float(val)
    except Exception:
        return None


# ─────────────────────────────────────────────
# JAXA GSMaP Rainfall Fetcher
# ─────────────────────────────────────────────
JAXA_HOST = "hokusai.eorc.jaxa.jp"
JAXA_USER = "rainmap"
JAXA_PASS = "Niskur+1404"

def get_jaxa_rainfall(mode: str, target_time: Optional[datetime.datetime] = None, range_type: str = "short"):
    """
    Fetch rainfall intensity (mm/hr) from JAXA GSMaP FTP.
    mode: 'forecast' or 'historical'
    target_time: for historical mode (philippine time)
    range_type: 'short' (1-6h) or 'medium' (1-5d) for forecast
    """
    try:
        ftp = ftplib.FTP(JAXA_HOST)
        ftp.login(JAXA_USER, JAXA_PASS)
        
        # QC District 1 Coords
        lat, lon = 14.64, 121.02
        
        # JAXA Grid: 0.1 deg resolution
        # Lat: 60N to 60S (0 to 1200 rows)
        # Lon: 0E to 360E (0 to 3600 cols)
        lat_idx = int((60 - lat) / 0.1)
        lon_idx = int(lon / 0.1)
        pixel_offset = (lat_idx * 3600 + lon_idx) * 4
        
        filename = ""
        directory = ""
        
        if mode == "historical":
            # Convert PH time to UTC
            utc_time = target_time - datetime.timedelta(hours=8)
            # Use hour precision
            ts = utc_time.strftime("%Y%m%d.%H00")
            directory = f"/realtime/archive/{utc_time.strftime('%Y/%m/%d')}/"
            filename = f"gsmap_nrt.{ts}.dat.gz"
        else:
            # Forecast
            # Simplified: get the latest forecast file
            directory = "/forecast/archive/"
            # We'll need to list to find the latest
            ftp.cwd(directory)
            files = []
            ftp.retrlines('NLST', files.append)
            # Filter for forecast files
            fcst_files = [f for f in files if "gsmap_fcst" in f and f.endswith(".dat.gz")]
            if not fcst_files:
                return 0.0, "No forecast files found"
            filename = sorted(fcst_files)[-1] # Latest forecast
            
        print(f"JAXA: Fetching {directory}{filename}")
        ftp.cwd(directory)
        
        bio = io.BytesIO()
        ftp.retrbinary(f"RETR {filename}", bio.write)
        ftp.quit()
        
        bio.seek(0)
        with gzip.GzipFile(fileobj=bio) as gz:
            data = gz.read()
            # Extract the specific pixel
            import struct
            val = struct.unpack_from('<f', data, pixel_offset)[0]
            # GSMaP values < 0 are missing/invalid
            rainfall = max(0.0, float(val))
            return rainfall, f"Success from {filename}"
            
    except Exception as e:
        print(f"JAXA Error: {e}")
        return 0.0, str(e)

@app.get("/rainfall/jaxa")
async def get_jaxa_data(
    mode: str = Query("forecast"),
    timestamp: Optional[str] = None,
    range: str = "short"
):
    dt = None
    if timestamp:
        try:
            dt = datetime.datetime.fromisoformat(timestamp.replace('Z', ''))
        except:
            dt = datetime.datetime.now()
    else:
        dt = datetime.datetime.now()
        
    value, message = get_jaxa_rainfall(mode, dt, range)
    
    # Map to scenario
    # Thresholds (mm/hr):
    # < 10 -> 5yr (but maybe "No Flood" is better? User said map to 5,25,100)
    # 10 - 25 -> 5yr
    # 25 - 50 -> 25yr
    # > 50 -> 100yr
    
    mapping = "5yr"
    if value >= 50:
        mapping = "100yr"
    elif value >= 25:
        mapping = "25yr"
    else:
        mapping = "5yr"
        
    return {
        "intensity": round(value, 2),
        "mapping": mapping,
        "message": message,
        "mode": mode,
        "time_ph": dt.strftime("%Y-%m-%d %H:%M")
    }

# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────


@app.get("/evacuation-centers")
async def get_evacuation_centers():
    """
    Return evacuation_centers.geojson as JSON.
    If not yet generated, build it on first request.
    """
    global evac_geojson
    if evac_geojson is None:
        load_or_generate_evac_centers()

    if evac_geojson is None:
        raise HTTPException(
            status_code=503,
            detail="Evacuation center data is not available",
        )

    return JSONResponse(
        content=evac_geojson,
        headers={
            "Content-Type": "application/json",
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


@app.get("/routes/evacuation")
async def get_evacuation_routes(
    lat: float = Query(..., description="Origin latitude"),
    lon: float = Query(..., description="Origin longitude"),
    k: int = Query(3, ge=1, le=5, description="Number of alternative routes (Yen's k)"),
):
    """
    Compute up to k shortest routes from an origin point to the nearest
    evacuation center using Dijkstra + Yen's algorithm (length as cost).
    """
    if road_geojson is None:
        load_or_download_roads()
    if not ROAD_GRAPH_BUILT:
        build_road_graph()

    global evac_geojson
    if evac_geojson is None:
        load_or_generate_evac_centers()

    if not evac_geojson or not evac_geojson.get("features"):
        raise HTTPException(status_code=503, detail="No evacuation centers available")

    origin_node = _nearest_node(lon, lat)
    if origin_node is None:
        raise HTTPException(status_code=400, detail="Could not snap origin to road network")

    # Precompute distances from origin to all nodes
    dist_from_origin, _prev = _dijkstra(origin_node)

    # Find nearest evacuation center in network distance
    best_evac = None
    best_evac_node = None
    best_evac_dist = None

    for feat in evac_geojson.get("features", []):
        geom = feat.get("geometry", {})
        if geom.get("type") != "Point":
            continue
        coords = geom.get("coordinates") or []
        if len(coords) < 2:
            continue
        evac_lon, evac_lat = coords[0], coords[1]
        evac_node = _nearest_node(evac_lon, evac_lat)
        if evac_node is None:
            continue
        d = dist_from_origin.get(evac_node)
        if d is None:
            continue
        if best_evac_dist is None or d < best_evac_dist:
            best_evac = feat
            best_evac_node = evac_node
            best_evac_dist = d

    if best_evac is None or best_evac_node is None:
        raise HTTPException(
            status_code=404,
            detail="No reachable evacuation center found from this origin",
        )

    # Compute k-shortest routes to the chosen evacuation node
    paths = _yen_k_shortest_paths(origin_node, best_evac_node, k)
    if not paths:
        raise HTTPException(
            status_code=404,
            detail="No route could be computed to the nearest evacuation center",
        )

    route_items = []
    for rank, (nodes, total_len) in enumerate(paths, start=1):
        coords = []
        for nid in nodes:
            lon_i, lat_i = ROAD_GRAPH_NODES.get(nid, (None, None))
            if lon_i is None:
                continue
            # Keep as [lon, lat] (GeoJSON-style); frontend will convert for Leaflet
            coords.append([lon_i, lat_i])
        if len(coords) < 2:
            continue
        route_items.append(
            {
                "rank": rank,
                "length": total_len,
                "coordinates": coords,
            }
        )

    props = (best_evac.get("properties") or {}).copy()
    evac_coords = best_evac.get("geometry", {}).get("coordinates") or [None, None]

    return JSONResponse(
        content={
            "origin": {"lon": float(lon), "lat": float(lat)},
            "evacuation": {
                "lon": float(evac_coords[0]) if evac_coords[0] is not None else None,
                "lat": float(evac_coords[1]) if evac_coords[1] is not None else None,
                "properties": props,
            },
            "routes": route_items,
        },
        headers={
            "Content-Type": "application/json",
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


@app.get("/tiles/{layer_name}/{z}/{x}/{y}.png")
async def get_tile(layer_name: str, z: int, x: int, y: int, clip: bool = Query(True)):
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

        content = render_flood(data, valid) if cmap_or_type == "flood" else render_continuous(data, valid, cmap_or_type)

        return Response(content=content, media_type="image/png",
                        headers={"Cache-Control": "no-cache, no-store"})

    except Exception as e:
        print(f"Tile error {layer_name} {z}/{x}/{y}: {e}")
        return Response(content=get_transparent_tile(), media_type="image/png")


@app.get("/boundary")
async def get_boundary():
    path = "district1_boundary.geojson"
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    raise HTTPException(status_code=404, detail="Boundary not found")


@app.get("/roads")
async def get_roads():
    if road_geojson is None:
        raise HTTPException(status_code=503, detail="Road data not yet loaded")
    return JSONResponse(content=road_geojson, headers={"Content-Type": "application/json"})


@app.get("/roads/flood-risk")
async def get_roads_flood_risk(scenario: str = Query("25yr")):
    if scenario not in FLOOD_RASTERS:
        raise HTTPException(status_code=400, detail=f"Unknown scenario: {scenario}. Use 5yr, 25yr, or 100yr")

    if road_geojson is None:
        raise HTTPException(status_code=503, detail="Road data not yet loaded")

    raster_path = FLOOD_RASTERS[scenario]
    model_path = FLOOD_MODELS[scenario]

    # Load model once
    model = None
    if os.path.exists(model_path):
        try:
            import joblib
            model = joblib.load(model_path)
        except Exception as e:
            print(f"Error loading model {model_path}: {e}")

    # Open the raster for sampling
    raster_src = None
    if os.path.exists(raster_path):
        try:
            raster_src = rasterio.open(raster_path)
        except Exception as e:
            print(f"Error opening raster {raster_path}: {e}")

    risk_labels = {0: "None", 1: "Low", 2: "Medium", 3: "High"}
    enriched_features = []

    for feature in road_geojson.get("features", []):
        props = dict(feature.get("properties", {}))
        geom = feature.get("geometry", {})

        # Find centroid from geometry
        flood_class = 0
        flood_prob = 0.0

        try:
            if geom.get("type") == "LineString":
                coords = geom["coordinates"]
                mid_idx = len(coords) // 2
                lon, lat = coords[mid_idx][0], coords[mid_idx][1]
            else:
                # Fallback: first coordinate
                coords = geom.get("coordinates", [[0, 0]])
                lon, lat = coords[0][0], coords[0][1]

            # Sample flood class from raster
            if raster_src is not None:
                try:
                    row, col = raster_src.index(lon, lat)
                    if 0 <= row < raster_src.height and 0 <= col < raster_src.width:
                        val = int(raster_src.read(1)[row, col])
                        if val in (1, 2, 3):
                            flood_class = val
                except Exception:
                    pass

            # Get probability from model if available
            # Models expect [elevation, slope, dist_waterway, land_cover]
            # We use flood_class as a proxy for probability if model unavailable
            if model is not None:
                try:
                    # Simple proxy features: use available raster values
                    feat_vec = [[0, 0, 0, 0, flood_class]]
                    proba = model.predict_proba(feat_vec)
                    # Get probability of class 3 (highest risk)
                    classes = list(model.classes_)
                    if 3 in classes:
                        flood_prob = float(proba[0][classes.index(3)])
                    else:
                        flood_prob = flood_class / 3.0
                except Exception:
                    flood_prob = flood_class / 3.0
            else:
                flood_prob = flood_class / 3.0

        except Exception:
            pass

        props["flood_class"] = flood_class
        props["flood_probability"] = round(flood_prob, 4)
        props["risk_label"] = risk_labels.get(flood_class, "None")

        enriched_features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": props
        })

    if raster_src is not None:
        raster_src.close()

    result = {"type": "FeatureCollection", "features": enriched_features}
    return JSONResponse(content=result, headers={"Content-Type": "application/json"})


@app.get("/layers")
async def get_layers():
    return {
        "layers": [
            {"id": "flood_5yr",     "name": "Flood Hazard 5yr",     "group": "flood",   "color": "#ffff00"},
            {"id": "flood_25yr",    "name": "Flood Hazard 25yr",    "group": "flood",   "color": "#ff8c00"},
            {"id": "flood_100yr",   "name": "Flood Hazard 100yr",   "group": "flood",   "color": "#ff0000"},
            {"id": "land_cover",    "name": "Land Cover",           "group": "env",     "color": "#00d4ff"},
            {"id": "dist_waterway", "name": "Distance to Waterway", "group": "env",     "color": "#0000ff"},
            {"id": "elevation",     "name": "Elevation (DEM)",      "group": "terrain", "color": "#8b4513"},
            {"id": "slope",         "name": "Slope",                "group": "terrain", "color": "#ff4500"},
        ]
    }


# ─────────────────────────────────────────────
# Flood-Aware Routing: NetworkX + Yen's K-Shortest Paths
# ─────────────────────────────────────────────

class RoutingRequest(BaseModel):
    start_lat: float
    start_lng: float
    k: int = 3

class RouteRequest(BaseModel):
    origin_lat: float
    origin_lon: float
    destination_lat: Optional[float] = None
    destination_lon: Optional[float] = None
    scenario: str = "25yr"
    k: int = 3

# NetworkX graph for flood-aware routing
NX_GRAPH = None
NX_NODE_POSITIONS = {}  # node_id -> (lat, lon)
NX_MODELS = {}  # XGBoost models for each scenario

# Cache the road graph globally (for simple evacuation routing)
ROAD_GRAPH = None
NODE_COORDS = None
EDGE_GEOMETRIES = None

# Flood multipliers for edge weights
FLOOD_MULTIPLIERS = {0: 1.0, 1: 2.0, 2: 5.0, 3: 20.0}
SCENARIOS = ['5yr', '25yr', '100yr']


def build_road_graph():
    """Build a graph from road network GeoJSON for pathfinding."""
    global ROAD_GRAPH, NODE_COORDS, EDGE_GEOMETRIES
    
    if ROAD_GRAPH is not None and NODE_COORDS is not None:
        return ROAD_GRAPH, NODE_COORDS, EDGE_GEOMETRIES
    
    if not road_geojson or not road_geojson.get("features"):
        return {}, {}, {}
    
    print("Building road graph...")
    graph = {}  # node_id -> [(neighbor_id, distance), ...]
    node_coords = {}  # node_id -> (lat, lng)
    edge_geometries = {}  # (node1, node2) -> [[lat, lng], ...]
    
    for feature in road_geojson["features"]:
        geom = feature.get("geometry")
        if not geom or geom.get("type") != "LineString":
            continue
        
        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            continue
        
        length = feature["properties"].get("length", 0)
        if length <= 0:
            length = 1  # Avoid zero-length edges
        
        # Create nodes from endpoints
        start_node = tuple(coords[0])  # (lng, lat)
        end_node = tuple(coords[-1])
        
        # Store node coordinates (convert to lat, lng)
        node_coords[start_node] = (coords[0][1], coords[0][0])
        node_coords[end_node] = (coords[-1][1], coords[-1][0])
        
        # Store full geometry for this edge (convert to lat, lng)
        geometry = [[c[1], c[0]] for c in coords]  # [lat, lng]
        edge_geometries[(start_node, end_node)] = geometry
        edge_geometries[(end_node, start_node)] = list(reversed(geometry))
        
        # Add bidirectional edges
        if start_node not in graph:
            graph[start_node] = []
        if end_node not in graph:
            graph[end_node] = []
        
        graph[start_node].append((end_node, length))
        graph[end_node].append((start_node, length))
    
    ROAD_GRAPH = graph
    NODE_COORDS = node_coords
    EDGE_GEOMETRIES = edge_geometries
    print(f"Graph built: {len(graph)} nodes, {len(node_coords)} coordinates, {len(edge_geometries)} edge geometries")
    
    return graph, node_coords, edge_geometries


def load_nx_graph():
    """Load NetworkX graph from road_edges.geojson for flood-aware routing."""
    global NX_GRAPH, NX_NODE_POSITIONS
    
    if NX_GRAPH is not None:
        return
    
    if not road_geojson or not road_geojson.get("features"):
        print("Cannot load NX graph: road_geojson not available")
        return
    
    print("Building NetworkX graph for flood-aware routing...")
    NX_GRAPH = nx.Graph()
    node_counter = 0
    node_map = {}
    
    for feature in road_geojson["features"]:
        geom_dict = feature.get("geometry")
        if not geom_dict or geom_dict.get("type") != "LineString":
            continue
        
        coords = geom_dict.get("coordinates", [])
        if len(coords) < 2:
            continue
        
        # Create LineString from coordinates
        from shapely.geometry import LineString as SLineString
        geometry = SLineString(coords)
        
        # Start and end points
        start_point = (round(coords[0][0], 6), round(coords[0][1], 6))
        end_point = (round(coords[-1][0], 6), round(coords[-1][1], 6))
        
        # Create or get node IDs
        if start_point not in node_map:
            node_map[start_point] = node_counter
            NX_GRAPH.add_node(node_counter, lat=start_point[1], lon=start_point[0])
            NX_NODE_POSITIONS[node_counter] = (start_point[1], start_point[0])
            node_counter += 1
        
        if end_point not in node_map:
            node_map[end_point] = node_counter
            NX_GRAPH.add_node(node_counter, lat=end_point[1], lon=end_point[0])
            NX_NODE_POSITIONS[node_counter] = (end_point[1], end_point[0])
            node_counter += 1
        
        u = node_map[start_point]
        v = node_map[end_point]
        
        # Get edge attributes
        props = feature.get("properties", {})
        osmid = props.get("osmid", "")
        name = props.get("name", "Unnamed Road")
        if isinstance(name, float) and math.isnan(name):
            name = "Unnamed Road"
        highway = props.get("highway", "unclassified")
        length = props.get("length", 0.0)
        
        # Add edge
        NX_GRAPH.add_edge(u, v,
                         osmid=str(osmid),
                         name=str(name),
                         highway=highway,
                         length=length,
                         geometry=geometry)
    
    print(f"NetworkX graph created: {NX_GRAPH.number_of_nodes()} nodes, {NX_GRAPH.number_of_edges()} edges")


def extract_nx_features():
    """Extract raster features at edge centroids for flood prediction."""
    if NX_GRAPH is None:
        return
    
    print("Extracting features from rasters for NetworkX graph...")
    
    raster_files = {
        'elevation': 'rasters_COP30/output_hh.tif',
        'slope': 'viz/viz.hh_slope.tif',
        'land_cover': 'land_cover_aligned.tif',
        'dist_waterway': 'distance_to_waterways.tif'
    }
    
    default_features = {
        'elevation': 20.0,
        'slope': 2.2,
        'land_cover': 50,
        'dist_waterway': 275.0
    }
    
    count = 0
    for u, v, data in NX_GRAPH.edges(data=True):
        geom = data.get('geometry')
        if geom is None:
            continue
        
        # Get centroid
        centroid = geom.centroid
        lat, lon = centroid.y, centroid.x
        
        # Sample rasters
        features = {}
        for key, path in raster_files.items():
            if os.path.exists(path):
                val = sample_raster_at_point(path, lon, lat)
                features[key] = val if val is not None else default_features[key]
            else:
                features[key] = default_features[key]
        
        NX_GRAPH[u][v]['features'] = features
        count += 1
    
    print(f"Feature extraction complete: {count} edges")


def load_nx_models():
    """Load XGBoost models for flood prediction."""
    global NX_MODELS
    
    print("Loading XGBoost models...")
    for scenario in SCENARIOS:
        model_path = f'model_{scenario}.pkl'
        if os.path.exists(model_path):
            try:
                NX_MODELS[scenario] = joblib.load(model_path)
                print(f"  Loaded {model_path}")
            except Exception as e:
                print(f"  Error loading {model_path}: {e}")


def precompute_nx_flood():
    """Pre-compute flood predictions for all edges."""
    if NX_GRAPH is None or not NX_MODELS:
        return
    
    print("Pre-computing flood predictions...")
    
    for scenario in SCENARIOS:
        if scenario not in NX_MODELS:
            continue
        
        model = NX_MODELS[scenario]
        count = 0
        
        for u, v, data in NX_GRAPH.edges(data=True):
            features = data.get('features')
            if features is None:
                continue
            
            # Prepare feature vector
            X = np.array([[
                features['elevation'],
                features['slope'],
                features['land_cover'],
                features['dist_waterway']
            ]])
            
            # Predict
            flood_class = int(model.predict(X)[0])
            flood_proba = model.predict_proba(X)[0]
            
            # Store predictions
            NX_GRAPH[u][v][f'flood_class_{scenario}'] = flood_class
            NX_GRAPH[u][v][f'flood_proba_{scenario}'] = float(flood_proba[3] if len(flood_proba) > 3 else 0.0)
            count += 1
        
        print(f"  {scenario}: done ({count} edges)")


def get_nx_nearest_node(lat: float, lon: float) -> Optional[int]:
    """Find nearest NetworkX graph node."""
    if not NX_NODE_POSITIONS:
        return None
    
    min_dist = float('inf')
    nearest = None
    
    for node_id, (node_lat, node_lon) in NX_NODE_POSITIONS.items():
        dist = math.sqrt((node_lat - lat)**2 + (node_lon - lon)**2)
        if dist < min_dist:
            min_dist = dist
            nearest = node_id
    
    return nearest


def compute_nx_edge_weight(u, v, scenario: str) -> float:
    """Compute flood-aware edge weight."""
    data = NX_GRAPH[u][v]
    flood_class = data.get(f'flood_class_{scenario}', 0)
    length = data.get('length', 1.0)
    multiplier = FLOOD_MULTIPLIERS.get(flood_class, 1.0)
    return length * multiplier


def yen_k_shortest_paths(source, target, K: int, scenario: str) -> List[List]:
    """Yen's K-Shortest Paths algorithm."""
    
    def weight_func(u, v, d):
        return compute_nx_edge_weight(u, v, scenario)
    
    # Find first shortest path
    try:
        first_path = nx.shortest_path(NX_GRAPH, source, target, weight=weight_func)
    except nx.NetworkXNoPath:
        return []
    
    A = [first_path]
    B = []
    
    for k in range(1, K):
        prev_path = A[-1]
        
        for i in range(len(prev_path) - 1):
            spur_node = prev_path[i]
            root_path = prev_path[:i+1]
            
            G_copy = NX_GRAPH.copy()
            
            # Remove edges from previous paths
            edges_to_remove = []
            for path in A:
                if len(path) > i and path[:i+1] == root_path:
                    if i+1 < len(path):
                        u, v = path[i], path[i+1]
                        if G_copy.has_edge(u, v):
                            edges_to_remove.append((u, v))
            
            for u, v in edges_to_remove:
                if G_copy.has_edge(u, v):
                    G_copy.remove_edge(u, v)
            
            # Find spur path
            try:
                spur_path = nx.shortest_path(G_copy, spur_node, target, weight=weight_func)
                total_path = root_path[:-1] + spur_path
                
                # Calculate total weight
                total_weight = sum(weight_func(total_path[j], total_path[j+1], NX_GRAPH[total_path[j]][total_path[j+1]]) 
                                 for j in range(len(total_path) - 1))
                
                if total_path not in A and total_path not in [p for _, p in B]:
                    B.append((total_weight, total_path))
            except nx.NetworkXNoPath:
                continue
        
        if not B:
            break
        
        B.sort(key=lambda x: x[0])
        _, path = B.pop(0)
        A.append(path)
    
    return A


def score_nx_route(path: List, scenario: str) -> Dict:
    """Score a route with flood exposure and length."""
    total_length = 0.0
    flood_probas = []
    flood_classes = []
    
    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        data = NX_GRAPH[u][v]
        
        total_length += data.get('length', 0.0)
        flood_probas.append(data.get(f'flood_proba_{scenario}', 0.0))
        flood_classes.append(data.get(f'flood_class_{scenario}', 0))
    
    flood_exposure = np.mean(flood_probas) if flood_probas else 0.0
    max_flood_class = max(flood_classes) if flood_classes else 0
    
    if flood_exposure < 0.2:
        risk_label = 'Low'
    elif flood_exposure < 0.5:
        risk_label = 'Medium'
    else:
        risk_label = 'High'
    
    return {
        'total_length': total_length,
        'flood_exposure': flood_exposure,
        'max_flood_class': max_flood_class,
        'risk_label': risk_label,
        'composite_score': 0.0
    }


def normalize_nx_scores(scores_list: List[Dict]) -> List[Dict]:
    """Normalize scores across routes."""
    if not scores_list:
        return scores_list
    
    lengths = [s['total_length'] for s in scores_list]
    exposures = [s['flood_exposure'] for s in scores_list]
    
    min_length, max_length = min(lengths), max(lengths)
    min_exposure, max_exposure = min(exposures), max(exposures)
    
    for score in scores_list:
        norm_length = (score['total_length'] - min_length) / (max_length - min_length) if max_length > min_length else 0.0
        norm_exposure = (score['flood_exposure'] - min_exposure) / (max_exposure - min_exposure) if max_exposure > min_exposure else 0.0
        score['composite_score'] = 0.6 * norm_exposure + 0.4 * norm_length
    
    return scores_list


def path_to_nx_geojson(path: List, scenario: str, score_data: Dict, rank: int) -> Dict:
    """Convert path to GeoJSON Feature."""
    from shapely.geometry import MultiLineString as SMultiLineString
    
    geometries = []
    segments = []
    
    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        data = NX_GRAPH[u][v]
        
        geom = data.get('geometry')
        if geom:
            geometries.append(geom)
        
        segments.append({
            'name': data.get('name', 'Unnamed Road'),
            'highway': data.get('highway', 'unclassified'),
            'length': data.get('length', 0.0),
            'flood_class': data.get(f'flood_class_{scenario}', 0),
            'flood_proba': data.get(f'flood_proba_{scenario}', 0.0),
            'elevation': data.get('features', {}).get('elevation', 0.0)
        })
    
    multi_line = SMultiLineString(geometries) if geometries else SMultiLineString([])
    
    return {
        'type': 'Feature',
        'geometry': mapping(multi_line),
        'properties': {
            'rank': rank,
            'total_length_m': score_data['total_length'],
            'total_length_km': round(score_data['total_length'] / 1000, 2),
            'flood_exposure': round(score_data['flood_exposure'], 4),
            'max_flood_class': score_data['max_flood_class'],
            'risk_label': score_data['risk_label'],
            'composite_score': round(score_data['composite_score'], 4),
            'recommended': rank == 1,
            'scenario': scenario,
            'segment_count': len(segments),
            'segments': segments
        }
    }


def find_nearest_node(lat: float, lng: float, node_coords: Dict) -> Optional[Tuple]:
    """Find the nearest graph node to a given coordinate."""
    if not node_coords:
        return None
    
    min_dist = float('inf')
    nearest = None
    
    for node, (node_lat, node_lng) in node_coords.items():
        # Haversine distance approximation
        dlat = node_lat - lat
        dlng = node_lng - lng
        dist = math.sqrt(dlat**2 + dlng**2)
        
        if dist < min_dist:
            min_dist = dist
            nearest = node
    
    return nearest


def dijkstra_shortest_path(graph: Dict, start_node: Tuple, end_node: Tuple) -> Tuple[List, float]:
    """
    Dijkstra's algorithm with min-heap.
    Returns (path, distance) where path is list of nodes.
    """
    if start_node not in graph or end_node not in graph:
        return [], float('inf')
    
    # Priority queue: (distance, node)
    pq = [(0, start_node)]
    distances = {start_node: 0}
    previous = {}
    visited = set()
    
    while pq:
        current_dist, current_node = heapq.heappop(pq)
        
        if current_node in visited:
            continue
        
        visited.add(current_node)
        
        if current_node == end_node:
            # Reconstruct path
            path = []
            node = end_node
            while node in previous:
                path.append(node)
                node = previous[node]
            path.append(start_node)
            path.reverse()
            return path, current_dist
        
        for neighbor, edge_dist in graph.get(current_node, []):
            if neighbor in visited:
                continue
            
            new_dist = current_dist + edge_dist
            
            if neighbor not in distances or new_dist < distances[neighbor]:
                distances[neighbor] = new_dist
                previous[neighbor] = current_node
                heapq.heappush(pq, (new_dist, neighbor))
    
    return [], float('inf')


@app.post("/find-evacuation-routes")
async def find_evacuation_routes(request: RoutingRequest):
    """
    Find shortest paths to k nearest evacuation centers using Dijkstra's algorithm.
    Returns full road geometries for curved path rendering.
    """
    try:
        print(f"Finding routes from ({request.start_lat}, {request.start_lng}) with k={request.k}")
        
        # Build road graph (cached after first call)
        graph, node_coords, edge_geometries = build_road_graph()
        
        if not graph:
            raise HTTPException(status_code=500, detail="Road network not available")
        
        # Find nearest node to start location
        start_node = find_nearest_node(request.start_lat, request.start_lng, node_coords)
        if not start_node:
            raise HTTPException(status_code=400, detail="Could not find nearest road node")
        
        start_lat, start_lng = node_coords[start_node]
        print(f"Start node: {start_node}, snapped to ({start_lat}, {start_lng})")
        
        # Get evacuation centers
        if not evac_geojson or not evac_geojson.get("features"):
            raise HTTPException(status_code=500, detail="Evacuation centers not available")
        
        # Find shortest path to each evacuation center
        evac_paths = []
        
        for idx, feature in enumerate(evac_geojson["features"]):
            geom = feature.get("geometry")
            if not geom or geom.get("type") != "Point":
                continue
            
            coords = geom.get("coordinates", [])
            if len(coords) < 2:
                continue
            
            evac_lng, evac_lat = coords[0], coords[1]
            evac_node = find_nearest_node(evac_lat, evac_lng, node_coords)
            
            if not evac_node:
                continue
            
            # Find shortest path to this evacuation center
            path, distance = dijkstra_shortest_path(graph, start_node, evac_node)
            
            if path and distance < float('inf'):
                evac_paths.append({
                    "path": path,
                    "distance": distance,
                    "destination": {
                        **feature["properties"],
                        "lat": evac_lat,
                        "lng": evac_lng
                    }
                })
        
        print(f"Found {len(evac_paths)} paths to evacuation centers")
        
        # Sort by distance and take top k
        evac_paths.sort(key=lambda x: x["distance"])
        evac_paths = evac_paths[:request.k]
        
        # Convert paths to full geometries with road curves
        routes = []
        for route_idx, item in enumerate(evac_paths):
            # Build full path geometry by concatenating edge geometries
            full_path = []
            
            for i in range(len(item["path"]) - 1):
                node1 = item["path"][i]
                node2 = item["path"][i + 1]
                
                # Get the edge geometry
                edge_key = (node1, node2)
                if edge_key in edge_geometries:
                    edge_coords = edge_geometries[edge_key]
                    
                    # Add all points except the last one (to avoid duplicates)
                    if i == 0:
                        full_path.extend(edge_coords)
                    else:
                        full_path.extend(edge_coords[1:])
            
            # Get start and end points for connectors
            path_start = full_path[0] if full_path else [start_lat, start_lng]
            path_end = full_path[-1] if full_path else [start_lat, start_lng]
            
            routes.append({
                "id": route_idx + 1,
                "path": [{"lat": coord[0], "lng": coord[1]} for coord in full_path],
                "distance": item["distance"],
                "start_connector": [
                    {"lat": request.start_lat, "lng": request.start_lng},
                    {"lat": path_start[0], "lng": path_start[1]}
                ],
                "end_connector": [
                    {"lat": path_end[0], "lng": path_end[1]},
                    {"lat": item["destination"]["lat"], "lng": item["destination"]["lng"]}
                ],
                "destination": {
                    "facility": item["destination"].get("facility", "Unknown"),
                    "barangay": item["destination"].get("barangay", "Unknown"),
                    "type": item["destination"].get("type", "Other"),
                    "lat": item["destination"].get("lat", 0),
                    "lng": item["destination"].get("lng", 0)
                }
            })
        
        print(f"Returning {len(routes)} routes with full geometries")
        return {"routes": routes}
    
    except Exception as e:
        print(f"Error in pathfinding: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/route")
async def find_flood_aware_route(request: RouteRequest):
    """Find K-shortest flood-aware routes using Yen's algorithm."""
    start_time = time.time()
    
    try:
        # Validate scenario
        if request.scenario not in SCENARIOS:
            raise HTTPException(status_code=400, detail=f"Invalid scenario. Must be one of: {SCENARIOS}")
        
        # Ensure graph is loaded
        if NX_GRAPH is None:
            raise HTTPException(status_code=503, detail="Routing graph not loaded. Please wait for server startup to complete.")
        
        # If destination is null, find nearest evacuation center
        destination_lat = request.destination_lat
        destination_lon = request.destination_lon
        destination_name = None
        destination_barangay = None
        
        if destination_lat is None or destination_lon is None:
            # Load evacuation centers
            evac_file = "evacuation_centers.geojson"
            if not os.path.exists(evac_file):
                raise HTTPException(status_code=404, detail="Evacuation centers file not found")
            
            try:
                with open(evac_file, "r", encoding="utf-8") as f:
                    evac_data = json.load(f)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error loading evacuation centers: {str(e)}")
            
            # Find nearest evacuation center using Euclidean distance
            min_distance = float('inf')
            nearest_center = None
            
            for feature in evac_data.get('features', []):
                try:
                    geom = feature.get('geometry')
                    if not geom or geom.get('type') != 'Point':
                        continue
                    
                    coords = geom.get('coordinates')
                    if not coords or len(coords) < 2:
                        continue
                    
                    center_lon, center_lat = float(coords[0]), float(coords[1])
                    
                    # Euclidean distance
                    distance = math.sqrt((center_lat - request.origin_lat)**2 + (center_lon - request.origin_lon)**2)
                    
                    if distance < min_distance:
                        min_distance = distance
                        nearest_center = feature
                except (KeyError, ValueError, TypeError) as e:
                    # Skip malformed features
                    continue
            
            if nearest_center is None:
                raise HTTPException(status_code=404, detail="No valid evacuation centers found")
            
            coords = nearest_center['geometry']['coordinates']
            destination_lon, destination_lat = float(coords[0]), float(coords[1])
            destination_name = nearest_center['properties'].get('facility', 'Unknown Center')
            destination_barangay = nearest_center['properties'].get('barangay', '')
        
        # Find nearest nodes
        origin_node = get_nx_nearest_node(request.origin_lat, request.origin_lon)
        dest_node = get_nx_nearest_node(destination_lat, destination_lon)
        
        if origin_node is None or dest_node is None:
            raise HTTPException(status_code=400, detail="Location outside road network")
        
        if not NX_GRAPH.has_node(origin_node) or not NX_GRAPH.has_node(dest_node):
            raise HTTPException(status_code=400, detail="Nodes not found in graph")
        
        # Find K shortest paths
        paths = yen_k_shortest_paths(origin_node, dest_node, K=request.k, scenario=request.scenario)
        
        if not paths:
            raise HTTPException(status_code=404, detail="No route found")
        
        # Score all routes
        scores = [score_nx_route(path, request.scenario) for path in paths]
        
        # Normalize scores
        scores = normalize_nx_scores(scores)
        
        # Sort by composite score
        sorted_indices = sorted(range(len(scores)), key=lambda i: scores[i]['composite_score'])
        
        # Convert to GeoJSON
        routes = []
        for rank, idx in enumerate(sorted_indices, 1):
            feature = path_to_nx_geojson(paths[idx], request.scenario, scores[idx], rank)
            routes.append(feature)
        
        computation_time = (time.time() - start_time) * 1000
        
        # Get node positions for connector lines
        origin_node_pos = NX_NODE_POSITIONS.get(origin_node)
        dest_node_pos = NX_NODE_POSITIONS.get(dest_node)
        
        # Create connector lines (dashed lines from user/evac to road network)
        origin_connector = None
        destination_connector = None
        
        if origin_node_pos:
            origin_connector = {
                "type": "LineString",
                "coordinates": [
                    [request.origin_lon, request.origin_lat],
                    [origin_node_pos[1], origin_node_pos[0]]  # node_pos is (lat, lon)
                ]
            }
        
        if dest_node_pos:
            destination_connector = {
                "type": "LineString",
                "coordinates": [
                    [dest_node_pos[1], dest_node_pos[0]],  # node_pos is (lat, lon)
                    [destination_lon, destination_lat]
                ]
            }
        
        response = {
            "scenario": request.scenario,
            "origin": {"lat": request.origin_lat, "lon": request.origin_lon},
            "destination": {"lat": destination_lat, "lon": destination_lon},
            "routes": routes,
            "computation_time_ms": round(computation_time, 2),
            "origin_connector": origin_connector,
            "destination_connector": destination_connector
        }
        
        # Add destination name if auto-found
        if destination_name:
            response["destination_name"] = destination_name
            if destination_barangay:
                response["destination_barangay"] = destination_barangay
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in routing: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/flood-segments")
async def get_flood_segments(scenario: str = Query("25yr")):
    """Get all road segments with flood predictions for visualization."""
    
    if scenario not in SCENARIOS:
        raise HTTPException(status_code=400, detail=f"Invalid scenario. Must be one of: {SCENARIOS}")
    
    if NX_GRAPH is None:
        raise HTTPException(status_code=503, detail="Graph not loaded")
    
    features = []
    
    for u, v, data in NX_GRAPH.edges(data=True):
        geom = data.get('geometry')
        if geom is None:
            continue
        
        flood_class = data.get(f'flood_class_{scenario}', 0)
        flood_proba = data.get(f'flood_proba_{scenario}', 0.0)
        
        # Risk label
        if flood_proba < 0.2:
            risk_label = 'Low'
        elif flood_proba < 0.5:
            risk_label = 'Medium'
        else:
            risk_label = 'High'
        
        features.append({
            'type': 'Feature',
            'geometry': mapping(geom),
            'properties': {
                'osmid': data.get('osmid', ''),
                'name': data.get('name', 'Unnamed Road'),
                'highway': data.get('highway', 'unclassified'),
                'length': data.get('length', 0.0),
                'flood_class': flood_class,
                'flood_proba': round(flood_proba, 4),
                'risk_label': risk_label
            }
        })
    
    return {
        'type': 'FeatureCollection',
        'features': features
    }


@app.get("/graph-stats")
async def get_graph_stats():
    """Get graph statistics for debugging."""
    
    if NX_GRAPH is None or NX_GRAPH.number_of_nodes() == 0:
        return {
            'total_nodes': 0,
            'total_edges': 0,
            'scenarios_precomputed': [],
            'bounds': {'north': 0, 'south': 0, 'east': 0, 'west': 0}
        }
    
    # Calculate bounds
    lats = [pos[0] for pos in NX_NODE_POSITIONS.values()]
    lons = [pos[1] for pos in NX_NODE_POSITIONS.values()]
    
    return {
        'total_nodes': NX_GRAPH.number_of_nodes(),
        'total_edges': NX_GRAPH.number_of_edges(),
        'scenarios_precomputed': list(NX_MODELS.keys()),
        'bounds': {
            'north': max(lats) if lats else 0,
            'south': min(lats) if lats else 0,
            'east': max(lons) if lons else 0,
            'west': min(lons) if lons else 0
        }
    }


@app.get("/health")
async def health_check():
    return {"status": "ok"}


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def read_index():
    return FileResponse("index.html")


@app.on_event("startup")
async def startup_event():
    """Load NetworkX graph and pre-compute flood predictions on startup."""
    print("="*60)
    print("STARTUP: Loading flood-aware routing system...")
    print("="*60)
    
    # Load NetworkX graph
    load_nx_graph()
    
    if NX_GRAPH and NX_GRAPH.number_of_edges() > 0:
        # Extract features from rasters
        extract_nx_features()
        
        # Load XGBoost models
        load_nx_models()
        
        # Pre-compute flood predictions
        precompute_nx_flood()
        
        print("="*60)
        print("FLOOD-AWARE ROUTING READY")
        print(f"Graph: {NX_GRAPH.number_of_nodes()} nodes, {NX_GRAPH.number_of_edges()} edges")
        print(f"Models loaded: {list(NX_MODELS.keys())}")
        print("="*60)
    else:
        print("WARNING: NetworkX graph not loaded - routing will not be available")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
