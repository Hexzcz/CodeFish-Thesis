"""Choosing which evacuation centers are worth routing to.

Centers cluster: a barangay hall, its covered court and its day-care centre
often share one gate. Routing to all three produces three copies of the same
route, so they are collapsed into one destination first.
"""
import math
from typing import Dict, List

from backend.domain.geo import LAT_TO_M, LON_TO_M

# Centers closer together than this are treated as one destination.
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
