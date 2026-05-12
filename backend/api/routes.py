import time
from typing import Optional, Dict
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
import heapq
from typing import List
from backend.graph.snap import snap_point_to_graph
from backend.routing.dijkstra import dijkstra
from backend.routing.yens import yens_k_shortest_paths
from backend.routing.scorer import score_routes
from backend.routing.geojson_builder import find_top_n_evacuation_centers, routes_to_geojson
from backend.prediction.flood_predictor import predict_scenario_on_the_fly
from backend.core.config import SCENARIOS

router = APIRouter()

class RouteRequest(BaseModel):
    origin_lat: float
    origin_lon: float
    scenario: str = "25yr"
    k: Optional[int] = 3

    weights: Optional[Dict[str, float]] = {
        'flood': 0.764,
        'distance': 0.112,
        'road_class': 0.124
    }

def get_app_state(request: Request):
    return request.app.state.data

def _dijkstra_distance_m(g, source, target) -> float:
    """Distance-only Dijkstra using edge_data['length'] in meters."""
    if not g.has_node(source) or not g.has_node(target):
        return float('inf')
    if source == target:
        return 0.0

    dist = {source: 0.0}
    heap = [(0.0, source)]
    visited = set()

    while heap:
        cur_d, u = heapq.heappop(heap)
        if u in visited:
            continue
        visited.add(u)
        if u == target:
            return cur_d

        for v, edge_data in g.get_neighbors(u):
            if v in visited:
                continue
            length_m = float(edge_data.get('length', 0.0) or 0.0)
            nd = cur_d + max(length_m, 0.0)
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                heapq.heappush(heap, (nd, v))

    return float('inf')


def _dijkstra_distance_path(g, source, target) -> tuple:
    """Distance-only Dijkstra that also returns the node path."""
    if not g.has_node(source) or not g.has_node(target):
        return float('inf'), []
    if source == target:
        return 0.0, [source]

    dist = {source: 0.0}
    prev = {source: None}
    heap = [(0.0, source)]
    visited = set()

    while heap:
        cur_d, u = heapq.heappop(heap)
        if u in visited:
            continue
        visited.add(u)
        if u == target:
            break

        for v, edge_data in g.get_neighbors(u):
            if v in visited:
                continue
            length_m = float(edge_data.get('length', 0.0) or 0.0)
            nd = cur_d + max(length_m, 0.0)
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))

    if target not in visited:
        return float('inf'), []

    path = []
    cur = target
    while cur is not None:
        path.append(cur)
        cur = prev.get(cur)
    path.reverse()
    if not path or path[0] != source:
        return float('inf'), []
    return dist[target], path

class DestinationPoint(BaseModel):
    lat: float
    lon: float

class ShortestDistanceRequest(BaseModel):
    origin_lat: float
    origin_lon: float
    destinations: List[DestinationPoint]


class ShortestPathRequest(BaseModel):
    origin_lat: float
    origin_lon: float
    destination_lat: float
    destination_lon: float
    scenario: str = "25yr"

@router.post("/route/shortest-distance")
async def shortest_distance_baseline(req: ShortestDistanceRequest, state: dict = Depends(get_app_state)):
    """Compute pure distance-only shortest path (Dijkstra) to each destination."""
    graph = state['graph']

    # Snap may mutate graph: use clone
    route_graph = graph.clone()

    try:
        origin_node, _ = snap_point_to_graph(route_graph, req.origin_lat, req.origin_lon)
    except ValueError as e:
        raise HTTPException(400, str(e))

    results = []
    for dest in req.destinations:
        try:
            d_node, _ = snap_point_to_graph(route_graph, dest.lat, dest.lon)
            dist_m = _dijkstra_distance_m(route_graph, origin_node, d_node)
            results.append({
                'destination_lat': dest.lat,
                'destination_lon': dest.lon,
                'distance_m': None if dist_m == float('inf') else round(dist_m, 2),
                'distance_km': None if dist_m == float('inf') else round(dist_m / 1000.0, 4),
            })
        except Exception:
            results.append({
                'destination_lat': dest.lat,
                'destination_lon': dest.lon,
                'distance_m': None,
                'distance_km': None,
            })

    return {'baselines': results}


@router.post("/route/shortest-path")
async def shortest_path_baseline(req: ShortestPathRequest, state: dict = Depends(get_app_state)):
    """Return distance-only shortest path geometry + metrics for interactive compare."""
    if req.scenario not in SCENARIOS:
        raise HTTPException(400, f"scenario must be one of: {SCENARIOS}")

    graph = state['graph']
    max_edge_length = state['max_edge_length']

    route_graph = graph.clone()

    try:
        origin_node, _ = snap_point_to_graph(route_graph, req.origin_lat, req.origin_lon)
    except ValueError as e:
        raise HTTPException(400, str(e))

    try:
        dest_node, _ = snap_point_to_graph(route_graph, req.destination_lat, req.destination_lon)
    except ValueError as e:
        raise HTTPException(400, str(e))

    dist_m, path = _dijkstra_distance_path(route_graph, origin_node, dest_node)
    if not path:
        raise HTTPException(404, "No path found")

    # Score the baseline path to get comparable metrics (segments, flood exposure, etc.)
    baseline_weights = {'flood': 0.0, 'distance': 1.0, 'road_class': 0.0}
    scored = score_routes([
        {
            'path': path,
            'cost': dist_m,
            'destination_info': {
                'lat': req.destination_lat,
                'lon': req.destination_lon,
                'facility': 'Shortest Path',
                'barangay': ''
            },
            'dest_node': dest_node
        }
    ], route_graph, req.scenario, baseline_weights, max_edge_length)

    if not scored:
        raise HTTPException(500, "Failed to score baseline path")

    r = scored[0]

    # Build geometry (MultiLineString) similar to routes_to_geojson
    coordinates = []
    for i in range(len(path) - 1):
        u = path[i]
        v = path[i + 1]
        edge = route_graph.get_edge(u, v)
        if edge and edge.get('geometry'):
            coordinates.append(edge['geometry'])
        else:
            nu = route_graph.nodes.get(u, {})
            nv = route_graph.nodes.get(v, {})
            coordinates.append([
                [nu.get('lon', 0), nu.get('lat', 0)],
                [nv.get('lon', 0), nv.get('lat', 0)],
            ])

    feature = {
        'type': 'Feature',
        'geometry': {'type': 'MultiLineString', 'coordinates': coordinates},
        'properties': {
            'kind': 'shortest_distance_only',
            'scenario': req.scenario,
            'total_length_m': r.get('total_length_m'),
            'total_length_km': r.get('total_length_km'),
            'flood_exposure': r.get('flood_exposure'),
            'segment_count': r.get('segment_count'),
            'segments': r.get('segments', []),
        }
    }

    return {
        'feature': feature,
        'metrics': {
            'distance_km': r.get('total_length_km'),
            'flood_susceptibility': r.get('flood_exposure'),
            'segment_count': r.get('segment_count'),
        }
    }

@router.post("/route")
async def find_route(request: RouteRequest, state: dict = Depends(get_app_state)):
    t0 = time.time()
    graph = state['graph']
    evacuation_centers = state['centers']
    max_edge_length = state['max_edge_length']

    if not (-90 <= request.origin_lat <= 90):
        raise HTTPException(400, "Invalid latitude")
    if not (-180 <= request.origin_lon <= 180):
        raise HTTPException(400, "Invalid longitude")
    if request.scenario not in SCENARIOS:
        raise HTTPException(400, f"scenario must be one of: {SCENARIOS}")

    # LAZY INFERENCE: Use a set (initialised in startup) to track predicted scenarios.
    # This is guaranteed correct unlike scanning edge dicts.
    predicted = state.setdefault('predicted_scenarios', set())
    if request.scenario not in predicted:
        print(f"[DEBUG] Running on-the-fly inference for scenario={request.scenario}")
        predict_scenario_on_the_fly(graph, state['models'], request.scenario)
        predicted.add(request.scenario)
        sample = [round(e.get(f'flood_proba_{request.scenario}', -1), 4)
                  for e in list(graph.edges.values())[:5]]
        print(f"[DEBUG] Post-inference sample flood_proba: {sample}")
    else:
        print(f"[DEBUG] Scenario {request.scenario} already predicted, skipping inference.")

    # Snapping may split edges by inserting temporary snap nodes. Use a
    # per-request graph copy so repeated identical route requests do not
    # accumulate graph mutations and drift to different paths.
    route_graph = graph.clone()

    K = min(max(request.k or 3, 1), 5)

    try:
        origin_node, origin_dist = snap_point_to_graph(
            route_graph, request.origin_lat, request.origin_lon
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    candidates = find_top_n_evacuation_centers(request.origin_lat, request.origin_lon, evacuation_centers, n=5)
    
    target_centers = []
    if candidates:
        d_min = candidates[0]['distance_m']
        for c in candidates:
            if c['distance_m'] < 2000 or c['distance_m'] < d_min * 3.0:
                target_centers.append(c)
                if len(target_centers) >= 3: break
    
    w = request.weights or {'flood': 0.764, 'distance': 0.112, 'road_class': 0.124}
    raw_routes = []
    seen_paths = set()

    for center in target_centers:
        try:
            d_node, d_dist = snap_point_to_graph(
                route_graph, center['lat'], center['lon']
            )
            if d_node == origin_node: continue
            
            cost, path = dijkstra(route_graph, origin_node, d_node, request.scenario, w, max_edge_length)
            if path:
                pt = tuple(path)
                if pt not in seen_paths:
                    seen_paths.add(pt)
                    raw_routes.append({
                        'path': path, 
                        'cost': cost, 
                        'destination_info': center,
                        'dest_node': d_node
                    })
        except:
            continue

    if len(raw_routes) < K and target_centers:
        main_center = target_centers[0]
        try:
            d_node, d_dist = snap_point_to_graph(
                route_graph, main_center['lat'], main_center['lon']
            )
            alts = yens_k_shortest_paths(route_graph, origin_node, d_node, K, request.scenario, w, max_edge_length)
            for alt in alts:
                pt = tuple(alt['path'])
                if pt not in seen_paths:
                    seen_paths.add(pt)
                    alt['destination_info'] = main_center
                    alt['dest_node'] = d_node
                    raw_routes.append(alt)
        except:
            pass

    if not raw_routes:
        raise HTTPException(404, "No evacuation route found to any nearby center.")

    scored = score_routes(raw_routes[:K], route_graph, request.scenario, w, max_edge_length)
    if scored:
        r0 = scored[0]
        s0 = r0.get('segments', [{}])[0]
        print(f"[DEBUG] scored[0] flood_exposure={r0['flood_exposure']} seg0_proba={s0.get('flood_proba')}")

    origin_node_data = route_graph.nodes.get(origin_node, {})
    origin_info = {
        'lat': request.origin_lat,
        'lon': request.origin_lon,
        'nearest_node_id': str(origin_node),
        'nearest_node_lat': origin_node_data.get('lat'),
        'nearest_node_lon': origin_node_data.get('lon'),
        'snap_distance_m': round(origin_dist, 1),
    }

    result = routes_to_geojson(scored, route_graph, request.scenario, origin_info)
    result['computation_time_ms'] = round((time.time() - t0) * 1000, 2)
    return result
