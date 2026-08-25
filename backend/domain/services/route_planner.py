"""The evacuation-routing use case: origin in, ranked routes out.

This is the orchestration that used to live inside the HTTP handler. It knows
nothing about FastAPI — no request objects, no status codes — so the same plan
can be produced from a test, a script, or another interface.

Errors are explicit and typed (`RoutingError` below): callers decide what a
failure looks like to a user.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.domain.graph import Graph
from backend.domain.routing.dijkstra import dijkstra
from backend.domain.routing.distance import shortest_distance, shortest_distance_path
from backend.domain.routing.scoring import score_routes
from backend.domain.routing.snapping import snap_point_to_graph
from backend.domain.routing.yens import yens_k_shortest_paths
from backend.domain.services.center_selection import find_top_n_evacuation_centers

# A center further than this is only considered when nothing closer exists.
NEARBY_CENTER_M = 2000.0
# ...or when it is within this multiple of the nearest center's distance.
NEARBY_CENTER_FACTOR = 3.0
MAX_CANDIDATE_CENTERS = 5
MAX_ROUTES = 5

DEFAULT_WEIGHTS = {'flood': 0.764, 'distance': 0.112, 'road_class': 0.124}


class RoutingError(Exception):
    """Routing could not produce an answer. The message is user-facing."""


class NoRouteFound(RoutingError):
    """The origin is on the network, but no center can be reached from it."""


@dataclass
class RoutePlan:
    """Ranked routes plus what a caller needs to read them.

    `graph` is the per-request copy the routes refer to: snapping splits edges,
    so the geometry of these routes only exists in this copy. `origin_node` is
    the node the origin snapped onto, needed to compute baselines against it.
    """
    routes: List[Dict]
    origin_info: Dict
    graph: Graph
    origin_node: Any


def plan_evacuation_routes(
    graph: Graph,
    evacuation_centers: List[Dict],
    origin_lat: float,
    origin_lon: float,
    scenario: str,
    weights: Optional[Dict[str, float]],
    max_edge_length: float,
    k: int = 3,
    penalty_factor: float = 3.0,
) -> RoutePlan:
    """Rank up to `k` flood-aware routes from an origin to nearby centers."""
    # Snapping inserts temporary nodes. Work on a copy so repeated identical
    # requests cannot accumulate mutations and drift to different paths.
    route_graph = graph.clone()
    k = min(max(k or 3, 1), MAX_ROUTES)
    weights = weights or DEFAULT_WEIGHTS

    origin_node, origin_dist = snap_point_to_graph(route_graph, origin_lat, origin_lon)

    targets = _reachable_centers(route_graph, origin_node, origin_lat, origin_lon, evacuation_centers)
    raw_routes = _routes_to_centers(route_graph, origin_node, targets, scenario, weights, max_edge_length, k)

    # One center with several ways to reach it beats one route to each of
    # several centers, so top up with alternatives before giving up.
    if len(raw_routes) < k and targets:
        raw_routes.extend(
            _alternative_routes(
                route_graph, origin_node, targets[0], scenario, weights,
                max_edge_length, k, penalty_factor,
                seen={tuple(r['path']) for r in raw_routes},
            )
        )

    if not raw_routes:
        raise NoRouteFound("No evacuation route found to any nearby center.")

    scored = score_routes(raw_routes[:k], route_graph, scenario, weights, max_edge_length)

    origin_node_data = route_graph.nodes.get(origin_node, {})
    origin_info = {
        'lat': origin_lat,
        'lon': origin_lon,
        'nearest_node_id': str(origin_node),
        'nearest_node_lat': origin_node_data.get('lat'),
        'nearest_node_lon': origin_node_data.get('lon'),
        'snap_distance_m': round(origin_dist, 1),
    }
    return RoutePlan(
        routes=scored,
        origin_info=origin_info,
        graph=route_graph,
        origin_node=origin_node,
    )


def distance_baselines(
    graph: Graph,
    origin_node,
    scored: List[Dict],
    scenario: str,
    weights: Dict[str, float],
    max_edge_length: float,
) -> List[Optional[Dict]]:
    """Score the plain shortest-distance route to each ranked route's target.

    One entry per route, aligned by index; None where no baseline exists.
    """
    baselines: List[Optional[Dict]] = []
    for route in scored:
        dest_node = route.get('dest_node')
        if dest_node and dest_node != origin_node:
            base_dist, base_path = shortest_distance_path(graph, origin_node, dest_node)
            if base_path:
                measured = score_routes([{
                    'path': base_path,
                    'cost': base_dist,
                    'destination_info': route.get('destination_info', {}),
                    'dest_node': dest_node,
                }], graph, scenario, weights, max_edge_length)
                baselines.append(measured[0] if measured else None)
                continue
        baselines.append(None)
    return baselines


def _reachable_centers(
    graph: Graph, origin_node, origin_lat: float, origin_lon: float, centers: List[Dict]
) -> List[Dict]:
    """Nearby centers, re-ranked by real network distance rather than crow-flies."""
    candidates = find_top_n_evacuation_centers(origin_lat, origin_lon, centers, n=10)

    reachable = []
    for center in candidates:
        try:
            center_node, _ = snap_point_to_graph(graph, center['lat'], center['lon'])
        except ValueError:
            continue
        if center_node == origin_node:
            continue
        distance = shortest_distance(graph, origin_node, center_node)
        if distance < float('inf'):
            reachable.append({**center, 'distance_m': round(distance, 1), '_snap_node': center_node})

    reachable.sort(key=lambda c: c['distance_m'])
    if not reachable:
        return []

    nearest = reachable[0]['distance_m']
    close_enough = [
        c for c in reachable
        if c['distance_m'] < NEARBY_CENTER_M or c['distance_m'] < nearest * NEARBY_CENTER_FACTOR
    ][:MAX_CANDIDATE_CENTERS]

    return close_enough or reachable[:3]


def _routes_to_centers(
    graph: Graph, origin_node, centers: List[Dict], scenario: str,
    weights: Dict[str, float], max_edge_length: float, k: int,
) -> List[Dict]:
    """One flood-aware route per candidate center, skipping duplicate paths."""
    routes: List[Dict] = []
    seen: set = set()

    for center in centers:
        if len(routes) >= k:
            break
        try:
            dest_node, _ = snap_point_to_graph(graph, center['lat'], center['lon'])
        except ValueError:
            continue
        if dest_node == origin_node:
            continue

        cost, path = dijkstra(graph, origin_node, dest_node, scenario, weights, max_edge_length)
        if not path or tuple(path) in seen:
            continue
        seen.add(tuple(path))
        routes.append({
            'path': path,
            'cost': cost,
            'destination_info': center,
            'dest_node': dest_node,
        })
    return routes


def _alternative_routes(
    graph: Graph, origin_node, center: Dict, scenario: str, weights: Dict[str, float],
    max_edge_length: float, k: int, penalty_factor: float, seen: set,
) -> List[Dict]:
    """Yen's k-shortest alternatives to a single center, minus paths already found."""
    try:
        dest_node, _ = snap_point_to_graph(graph, center['lat'], center['lon'])
    except ValueError:
        return []

    alternatives = yens_k_shortest_paths(
        graph, origin_node, dest_node, k, scenario, weights, max_edge_length, penalty_factor
    )

    fresh = []
    for alt in alternatives:
        if tuple(alt['path']) in seen:
            continue
        seen.add(tuple(alt['path']))
        alt['destination_info'] = center
        alt['dest_node'] = dest_node
        fresh.append(alt)
    return fresh
