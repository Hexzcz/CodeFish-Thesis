import os
import math
import rasterio
from typing import Dict
from backend.graph.builder import Graph
from backend.core.config import RASTER_PATHS, DEFAULT_FEATURES

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

def sample_rasters(graph: Graph) -> Graph:
    """Sample rasters at each edge centroid."""
    print("[3/6] Sampling rasters at road centroids...")

    available = {k: v for k, v in RASTER_PATHS.items() if os.path.exists(v)}
    missing = set(RASTER_PATHS) - set(available)
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
    return graph
