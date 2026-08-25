"""Shaping scored routes into the GeoJSON the map draws.

Presentation only: every number here was computed in the engine. This decides
what the browser receives and under which key.
"""
from typing import Dict, List

from backend.domain.graph import Graph


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
            nu = graph.nodes.get(u, {})
            nv = graph.nodes.get(v, {})
            if edge and edge.get('geometry'):
                geom = edge['geometry']  # [[lon, lat], ...]
                # Align geometry to traversal direction u→v.
                # OSM edges can be stored in either direction; check whether
                # the geometry's start point is closer to u or to v, and
                # reverse the coordinate list if it is stored backwards.
                if geom and nu:
                    u_lon, u_lat = nu.get('lon', 0), nu.get('lat', 0)
                    sx, sy = geom[0][0], geom[0][1]
                    ex, ey = geom[-1][0], geom[-1][1]
                    dist_start_to_u = (sx - u_lon) ** 2 + (sy - u_lat) ** 2
                    dist_end_to_u   = (ex - u_lon) ** 2 + (ey - u_lat) ** 2
                    if dist_end_to_u < dist_start_to_u:
                        geom = list(reversed(geom))
                coordinates.append(geom)
            else:
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
