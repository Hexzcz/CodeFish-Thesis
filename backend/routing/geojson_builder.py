import math
from typing import List, Dict
from backend.graph.builder import Graph
from backend.graph.nearest_node import LAT_TO_M, LON_TO_M

DEFAULT_DESTINATION_CLUSTER_RADIUS_M = 50.0


def _distance_m(a: Dict, b: Dict) -> float:
    dlat = (a['lat'] - b['lat']) * LAT_TO_M
    dlon = (a['lon'] - b['lon']) * LON_TO_M
    return math.sqrt(dlat ** 2 + dlon ** 2)


def _cluster_facility_label(members: List[Dict]) -> str:
    if len(members) == 1:
        return members[0].get('facility', 'Unknown')

    anchor = members[0].get('facility', 'Evacuation Center')
    return f"{anchor} (+{len(members) - 1} nearby)"


def cluster_evacuation_centers(
    centers: List[Dict],
    radius_m: float = DEFAULT_DESTINATION_CLUSTER_RADIUS_M,
) -> List[Dict]:
    """Group centers that are within radius_m of another member for routing."""
    remaining = list(centers)
    clusters = []

    while remaining:
        seed = remaining.pop(0)
        members = [seed]
        queue = [seed]

        while queue:
            current = queue.pop(0)
            nearby = [c for c in remaining if _distance_m(current, c) <= radius_m]
            if not nearby:
                continue

            nearby_ids = {id(c) for c in nearby}
            remaining = [c for c in remaining if id(c) not in nearby_ids]
            members.extend(nearby)
            queue.extend(nearby)

        centroid_lat = sum(c['lat'] for c in members) / len(members)
        centroid_lon = sum(c['lon'] for c in members) / len(members)
        representative = min(
            members,
            key=lambda c: (c['lat'] - centroid_lat) ** 2 + (c['lon'] - centroid_lon) ** 2,
        )
        member_summaries = [
            {
                'facility': c.get('facility', 'Unknown'),
                'barangay': c.get('barangay', ''),
                'type': c.get('type', 'Other'),
                'lat': c.get('lat'),
                'lon': c.get('lon'),
            }
            for c in members
        ]

        clusters.append({
            **representative,
            'lat': centroid_lat,
            'lon': centroid_lon,
            'facility': _cluster_facility_label(members),
            'barangay': representative.get('barangay', ''),
            'clustered': len(members) > 1,
            'cluster_radius_m': radius_m,
            'cluster_size': len(members),
            'cluster_members': member_summaries,
        })

    return clusters


def find_top_n_evacuation_centers(
    origin_lat: float,
    origin_lon: float,
    centers: List[Dict],
    n: int = 3,
    cluster_radius_m: float = DEFAULT_DESTINATION_CLUSTER_RADIUS_M,
) -> List[Dict]:
    """Find the top N evacuation centers by straight-line distance."""
    if not centers:
        raise ValueError("No evacuation centers loaded")

    route_centers = cluster_evacuation_centers(centers, cluster_radius_m)

    scored = []
    for center in route_centers:
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
                'destination_clustered': route.get('destination_info', {}).get('clustered', False),
                'destination_cluster_size': route.get('destination_info', {}).get('cluster_size', 1),
                'destination_cluster_members': route.get('destination_info', {}).get('cluster_members', []),
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
            'clustered': primary_center.get('clustered', False),
            'cluster_size': primary_center.get('cluster_size', 1),
            'cluster_members': primary_center.get('cluster_members', []),
        },
        'routes': features
    }
