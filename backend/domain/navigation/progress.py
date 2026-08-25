"""Where you are along the route you were given.

Three questions a walking person has, answered from one GPS fix:

    Am I still on the route?      → distance to the nearest point on the line
    How much further?             → what is left of the line ahead of me
    Am I there?                   → how close the destination is

Pure geometry over the route the router already produced. It decides nothing
about *which* route is right — that stays with the planner, and rerouting means
asking the planner again, never patching a path together here.
"""
from dataclasses import dataclass, asdict
from typing import Dict, List, Sequence, Tuple

from backend.domain.geo import LAT_TO_M, LON_TO_M

# Further than this from the line and the route is no longer being followed.
# Wide enough to absorb a phone GPS fix drifting across a street (10–20 m is
# ordinary), tight enough to notice a wrong turn at the first corner.
OFF_ROUTE_M = 40.0

# Close enough to the destination to call it arrived.
ARRIVAL_M = 25.0


@dataclass
class RouteProgress:
    """What one position means for one route."""
    distance_from_route_m: float
    remaining_m: float
    travelled_m: float
    nearest_index: int
    off_route: bool
    arrived: bool

    def to_dict(self) -> Dict:
        return asdict(self)


def route_progress(
    coordinates: Sequence[Sequence[float]],
    lat: float,
    lon: float,
    off_route_m: float = OFF_ROUTE_M,
    arrival_m: float = ARRIVAL_M,
) -> RouteProgress:
    """Locate a position against a route line.

    `coordinates` is [[lon, lat], ...] in travel order — the same order the
    route GeoJSON is drawn in, so "remaining" means what is ahead, not what is
    nearest the end.

    Raises ValueError on a route with nothing to follow: a caller asking about
    an empty route has a bug, and answering "0 m remaining" would hide it.
    """
    points = [(float(c[1]), float(c[0])) for c in coordinates if c is not None and len(c) >= 2]
    if len(points) < 2:
        raise ValueError("a route needs at least two points to be followed")

    best_distance = float('inf')
    best_index = 0
    best_fraction = 0.0

    for index in range(len(points) - 1):
        distance, fraction = _distance_to_segment(lat, lon, points[index], points[index + 1])
        if distance < best_distance:
            best_distance = distance
            best_index = index
            best_fraction = fraction

    segment_lengths = [
        _distance_m(points[i], points[i + 1]) for i in range(len(points) - 1)
    ]
    total = sum(segment_lengths)

    travelled = sum(segment_lengths[:best_index]) + segment_lengths[best_index] * best_fraction
    travelled = min(max(travelled, 0.0), total)
    remaining = total - travelled

    # Arrival is measured to the destination itself, not to the end of the
    # line: someone standing at the gate has arrived even if the drawn route
    # stops a few metres short of it.
    to_destination = _distance_m((lat, lon), points[-1])

    return RouteProgress(
        distance_from_route_m=round(best_distance, 1),
        remaining_m=round(remaining, 1),
        travelled_m=round(travelled, 1),
        nearest_index=best_index,
        off_route=best_distance > off_route_m,
        arrived=to_destination <= arrival_m,
    )


def _distance_m(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Flat-earth distance in metres. Good to centimetres at city scale."""
    dy = (a[0] - b[0]) * LAT_TO_M
    dx = (a[1] - b[1]) * LON_TO_M
    return (dx * dx + dy * dy) ** 0.5


def _distance_to_segment(
    lat: float, lon: float, start: Tuple[float, float], end: Tuple[float, float]
) -> Tuple[float, float]:
    """Distance in metres to a segment, and how far along it the foot falls.

    The fraction is clamped to [0, 1]: past either end, the nearest point is
    that end, which is what walking off the end of a street means.
    """
    ay, ax = start[0] * LAT_TO_M, start[1] * LON_TO_M
    by, bx = end[0] * LAT_TO_M, end[1] * LON_TO_M
    py, px = lat * LAT_TO_M, lon * LON_TO_M

    dx, dy = bx - ax, by - ay
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5, 0.0

    fraction = ((px - ax) * dx + (py - ay) * dy) / length_squared
    fraction = min(max(fraction, 0.0), 1.0)

    foot_x = ax + fraction * dx
    foot_y = ay + fraction * dy
    return ((px - foot_x) ** 2 + (py - foot_y) ** 2) ** 0.5, fraction
