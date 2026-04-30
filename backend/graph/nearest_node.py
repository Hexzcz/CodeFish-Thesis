import math
from typing import Tuple, Any
from backend.graph.builder import Graph

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
