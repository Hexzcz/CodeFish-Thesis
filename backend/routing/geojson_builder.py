import math
from typing import List, Dict
from backend.graph.builder import Graph
from backend.graph.nearest_node import LAT_TO_M, LON_TO_M

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

def routes_to_geojson(scored_routes: List[Dict], graph: Graph, scenario: str, origin_info: Dict) -> Dict:
    """Format scored routes into GeoJSON response."""
    features = []
    
    # Primary destination is Rank 1
    primary_route = scored_routes[0]
    primary_center = primary_route.get('destination_info', {})
    primary_d_node = primary_route.get('dest_node')
    primary_d_data = graph.nodes.get(primary_d_node, {})

    for route in scored_routes:
        coordinates = []
        for i in range(len(route['path']) - 1):
            u = route['path'][i]
            v = route['path'][i + 1]
            edge = graph.get_edge(u, v)
            if edge and edge.get('geometry'):
                coordinates.append(edge['geometry'])
            else:
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
                'scenario': scenario,
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
                'destination_lat': route.get('destination_info', {}).get('lat'),
                'destination_lon': route.get('destination_info', {}).get('lon'),
            },
        })

    return {
        'scenario': scenario,
        'k_found': len(features),
        'origin': origin_info,
        'destination': {
            'name': primary_center.get('facility', 'Unknown'),
            'barangay': primary_center.get('barangay', ''),
            'lat': primary_center.get('lat'),
            'lon': primary_center.get('lon'),
            'nearest_node_id': str(primary_d_node),
            'nearest_node_lat': primary_d_data.get('lat'),
            'nearest_node_lon': primary_d_data.get('lon'),
            'snap_distance_m': 0,
            'straight_line_distance_m': primary_center.get('distance_m', 0),
        },
        'routes': features
    }
