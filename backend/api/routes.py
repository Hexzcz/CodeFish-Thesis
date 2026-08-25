"""Routing endpoints.

Thin on purpose: parse the request, call the planner, shape the answer, map a
domain error onto a status code. The routing itself lives in
`backend/domain/services/route_planner.py`.
"""
import time

from fastapi import APIRouter, Depends, HTTPException

from backend.adapters.reporting.route_report import (
    print_baseline_comparison,
    print_route_breakdown,
)
from backend.api.dependencies import get_app_state
from backend.api.presenters.route_geojson import routes_to_geojson
from backend.api.schemas import (
    RouteRequest,
    ShortestDistanceRequest,
    ShortestPathRequest,
)
from backend.core.config import SCENARIOS
from backend.domain.prediction.flood import predict_scenario_on_the_fly
from backend.domain.routing.distance import shortest_distance, shortest_distance_path
from backend.domain.routing.scoring import score_routes
from backend.domain.routing.snapping import snap_point_to_graph
from backend.domain.services.route_planner import (
    DEFAULT_WEIGHTS,
    NoRouteFound,
    RoutingError,
    distance_baselines,
    plan_evacuation_routes,
)

router = APIRouter()


def _require_valid_origin(lat: float, lon: float) -> None:
    if not (-90 <= lat <= 90):
        raise HTTPException(400, "Invalid latitude")
    if not (-180 <= lon <= 180):
        raise HTTPException(400, "Invalid longitude")


def _require_known_scenario(scenario: str) -> None:
    if scenario not in SCENARIOS:
        raise HTTPException(400, f"scenario must be one of: {SCENARIOS}")


def _ensure_scenario_predicted(state: dict, scenario: str) -> None:
    """Run flood inference for a scenario once, the first time it is asked for.

    The set of already-predicted scenarios is tracked explicitly rather than
    inferred from edge attributes, which was easy to get wrong.
    """
    predicted = state.setdefault('predicted_scenarios', set())
    if scenario in predicted:
        return
    predict_scenario_on_the_fly(state['graph'], state['models'], scenario)
    predicted.add(scenario)


@router.post("/route/shortest-distance")
async def shortest_distance_baseline(req: ShortestDistanceRequest, state: dict = Depends(get_app_state)):
    """Distance-only shortest path (Dijkstra) to each destination."""
    _require_valid_origin(req.origin_lat, req.origin_lon)

    # Snapping mutates the graph, so every request works on its own copy.
    route_graph = state['graph'].clone()

    try:
        origin_node, _ = snap_point_to_graph(route_graph, req.origin_lat, req.origin_lon)
    except ValueError as e:
        raise HTTPException(400, str(e))

    results = []
    for dest in req.destinations:
        distance_m = float('inf')
        try:
            dest_node, _ = snap_point_to_graph(route_graph, dest.lat, dest.lon)
            distance_m = shortest_distance(route_graph, origin_node, dest_node)
        except ValueError:
            pass  # Unreachable destinations are reported as null, not an error.

        reachable = distance_m != float('inf')
        results.append({
            'destination_lat': dest.lat,
            'destination_lon': dest.lon,
            'distance_m': round(distance_m, 2) if reachable else None,
            'distance_km': round(distance_m / 1000.0, 4) if reachable else None,
        })

    return {'baselines': results}


@router.post("/route/shortest-path")
async def shortest_path_baseline(req: ShortestPathRequest, state: dict = Depends(get_app_state)):
    """Distance-only shortest path geometry and metrics, for side-by-side compare."""
    _require_valid_origin(req.origin_lat, req.origin_lon)
    _require_known_scenario(req.scenario)

    route_graph = state['graph'].clone()

    try:
        origin_node, _ = snap_point_to_graph(route_graph, req.origin_lat, req.origin_lon)
        dest_node, _ = snap_point_to_graph(route_graph, req.destination_lat, req.destination_lon)
    except ValueError as e:
        raise HTTPException(400, str(e))

    distance_m, path = shortest_distance_path(route_graph, origin_node, dest_node)
    if not path:
        raise HTTPException(404, "No path found")

    scored = score_routes([{
        'path': path,
        'cost': distance_m,
        'destination_info': {
            'lat': req.destination_lat,
            'lon': req.destination_lon,
            'facility': 'Shortest Path',
            'barangay': '',
        },
        'dest_node': dest_node,
    }], route_graph, req.scenario, DEFAULT_WEIGHTS, state['max_edge_length'])

    if not scored:
        raise HTTPException(500, "Failed to score baseline path")

    route = scored[0]
    return {
        'feature': {
            'type': 'Feature',
            'geometry': {
                'type': 'MultiLineString',
                'coordinates': _path_geometry(route_graph, path),
            },
            'properties': {
                'kind': 'shortest_distance_only',
                'scenario': req.scenario,
                'total_length_m': route.get('total_length_m'),
                'total_length_km': route.get('total_length_km'),
                'flood_exposure': route.get('flood_exposure'),
                'segment_count': route.get('segment_count'),
                'segments': route.get('segments', []),
            },
        },
        'metrics': {
            'distance_km': route.get('total_length_km'),
            'flood_susceptibility': route.get('flood_exposure'),
            'segment_count': route.get('segment_count'),
        },
    }


@router.post("/route")
async def find_route(request: RouteRequest, state: dict = Depends(get_app_state)):
    """Rank flood-aware evacuation routes from an origin to nearby centers."""
    started = time.time()
    _require_valid_origin(request.origin_lat, request.origin_lon)
    _require_known_scenario(request.scenario)
    _ensure_scenario_predicted(state, request.scenario)

    weights = request.weights or DEFAULT_WEIGHTS
    penalty_factor = request.penalty_factor if (request.penalty_factor or 0) > 0 else 3.0

    try:
        plan = plan_evacuation_routes(
            graph=state['graph'],
            evacuation_centers=state['centers'],
            origin_lat=request.origin_lat,
            origin_lon=request.origin_lon,
            scenario=request.scenario,
            weights=weights,
            max_edge_length=state['max_edge_length'],
            k=request.k or 3,
            penalty_factor=penalty_factor,
        )
    except NoRouteFound as e:
        raise HTTPException(404, str(e))
    except RoutingError as e:
        raise HTTPException(400, str(e))
    except ValueError as e:  # raised by snapping when the origin is off-network
        raise HTTPException(400, str(e))

    print_route_breakdown(plan.routes, request.scenario, weights, state['max_edge_length'])
    baselines = distance_baselines(
        plan.graph, plan.origin_node, plan.routes,
        request.scenario, weights, state['max_edge_length'],
    )
    print_baseline_comparison(plan.routes, baselines, request.scenario, weights, state['max_edge_length'])

    result = routes_to_geojson(plan.routes, plan.graph, request.scenario, plan.origin_info)
    result['computation_time_ms'] = round((time.time() - started) * 1000, 2)
    return result


def _path_geometry(graph, path) -> list:
    """Coordinates for each hop, falling back to a straight line between nodes."""
    coordinates = []
    for u, v in zip(path, path[1:]):
        edge = graph.get_edge(u, v)
        if edge and edge.get('geometry'):
            coordinates.append(edge['geometry'])
        else:
            node_u = graph.nodes.get(u, {})
            node_v = graph.nodes.get(v, {})
            coordinates.append([
                [node_u.get('lon', 0), node_u.get('lat', 0)],
                [node_v.get('lon', 0), node_v.get('lat', 0)],
            ])
    return coordinates
