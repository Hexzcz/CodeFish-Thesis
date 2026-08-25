"""Distances, nearest nodes, and whether a point falls inside the district.

Plain geometry over lat/lon — no projection library, because everything here
happens inside one city and the flat-earth error at this scale is metres.
"""
import math
from typing import Any, List, Optional, Tuple

from backend.domain.graph import Graph

# District 1 QC bounding box, used when the boundary file is unavailable.
DISTRICT1_VIEWBOX = {
    "west": 120.96,
    "south": 14.63,
    "east": 121.08,
    "north": 14.74,
}

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


# ── Point-in-polygon, for keeping search results inside the district ────────
def point_in_ring(point: tuple, ring: List[tuple]) -> bool:
    """Ray casting algorithm for point-in-polygon."""
    x, y = point
    inside = False
    for i in range(len(ring)):
        j = (i - 1) % len(ring)
        xi, yi = ring[i]
        xj, yj = ring[j]
        intersect = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi)
        if intersect:
            inside = not inside
    return inside


def point_in_polygon(point: tuple, polygon_coords: List[List[tuple]]) -> bool:
    """Check if point is inside polygon (with holes)."""
    if not polygon_coords:
        return False
    outer = polygon_coords[0]
    if not point_in_ring(point, outer):
        return False
    for hole in polygon_coords[1:]:
        if point_in_ring(point, hole):
            return False
    return True


def point_in_boundary(lat: float, lon: float, boundary_geojson: Optional[dict] = None) -> bool:
    """Check if point is inside District 1 boundary."""
    if not boundary_geojson:
        return True  # Allow if boundary not loaded
    
    point = (lon, lat)
    geom = boundary_geojson.get("geometry")
    if not geom:
        return True
    
    if geom["type"] == "Polygon":
        return point_in_polygon(point, geom["coordinates"])
    elif geom["type"] == "MultiPolygon":
        return any(point_in_polygon(point, poly) for poly in geom["coordinates"])
    
    return True


def boundary_viewbox(boundary_geojson: Optional[dict] = None) -> dict:
    """Extract or return fallback viewbox for District 1."""
    if boundary_geojson:
        geom = boundary_geojson.get("geometry")
        if geom:
            coords = []
            def _walk(arr):
                if isinstance(arr, list):
                    if len(arr) == 2 and isinstance(arr[0], (int, float)) and isinstance(arr[1], (int, float)):
                        coords.append(tuple(arr))
                    else:
                        for item in arr:
                            _walk(item)
            _walk(geom.get("coordinates", []))
            if coords:
                west = min(c[0] for c in coords)
                south = min(c[1] for c in coords)
                east = max(c[0] for c in coords)
                north = max(c[1] for c in coords)
                return {"west": west, "south": south, "east": east, "north": north}
    
    return DISTRICT1_VIEWBOX
