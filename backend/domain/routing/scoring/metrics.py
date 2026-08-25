"""What one route costs: how long, how flooded, what it is made of.

One route in, one dict of measurements out. No ranking happens here — see
`topsis.py` for that.
"""
from typing import Dict

from backend.domain.graph import Graph
from backend.domain.routing.weights import compute_wsm_weight, HIGHWAY_RANK, MAX_RANK


def measure_route(
    route_data: Dict,
    g: Graph,
    scenario: str,
    weights_map: Dict[str, float],
    max_edge_length: float,
) -> Dict:
    """Measure a single path: length, flood exposure, and per-segment detail."""
    path = route_data['path']

    total_length = 0.0
    total_flood_proba = 0.0
    weighted_flood_proba = 0.0
    max_flood_class = 0
    segment_count = 0
    flood_class_counts = {0: 0, 1: 0, 2: 0}
    segments = []

    for i in range(len(path) - 1):
        edge = g.get_edge(path[i], path[i + 1])
        if not edge:
            continue

        length = float(edge.get('length', 0.0))
        flood_class = int(edge.get(f'flood_class_{scenario}', 0) or 0)
        flood_proba = float(edge.get(f'flood_proba_{scenario}', 0.0) or 0.0)
        elevation = float(edge.get('elevation', 0.0) or 0.0)

        flood_proba_array = edge.get(f'flood_proba_array_{scenario}', [1.0, 0.0, 0.0])

        total_length += length
        total_flood_proba += flood_proba
        weighted_flood_proba += flood_proba * length
        max_flood_class = max(max_flood_class, flood_class)
        flood_class_counts[min(flood_class, 2)] += 1
        segment_count += 1

        segment_data = {
            'name': edge.get('name', 'Unnamed Road'),
            'highway': edge.get('highway', 'unclassified'),
            'length': round(length, 2),
            'flood_class': flood_class,
            'flood_proba': round(flood_proba, 4),
            'flood_proba_array': [round(p, 3) for p in flood_proba_array],
            'elevation': round(elevation, 2),
            'wsm_cost': round(compute_wsm_weight(edge, scenario, weights_map, max_edge_length), 4)
        }
        segments.append(segment_data)


    avg_flood_proba = weighted_flood_proba / total_length if total_length > 0 else 0.0

    wsm_flood_total = sum(s['flood_proba'] * weights_map['flood'] for s in segments) * 100.0
    wsm_dist_total = sum((min(s['length'] / max_edge_length, 2.0)) * weights_map['distance'] for s in segments) * 100.0
    
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
        'destination_info': route_data.get('destination_info'),
        'dest_node': route_data.get('dest_node')
    }

    return r_final
