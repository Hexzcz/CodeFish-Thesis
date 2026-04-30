import time
from typing import Optional, Dict
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from backend.graph.nearest_node import get_nearest_node
from backend.routing.dijkstra import dijkstra
from backend.routing.yens import yens_k_shortest_paths
from backend.routing.scorer import score_routes
from backend.routing.geojson_builder import find_top_n_evacuation_centers, routes_to_geojson
from backend.core.config import SCENARIOS

router = APIRouter()

class RouteRequest(BaseModel):
    origin_lat: float
    origin_lon: float
    scenario: str = "25yr"
    k: Optional[int] = 3
    weights: Optional[Dict[str, float]] = {
        'flood': 0.5,
        'distance': 0.3,
        'road_class': 0.2
    }

def get_app_state(request: Request):
    return request.app.state.data

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

    K = min(max(request.k or 3, 1), 5)

    try:
        origin_node, origin_dist = get_nearest_node(graph, request.origin_lat, request.origin_lon)
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
    
    w = request.weights or {'flood': 0.5, 'distance': 0.3, 'road_class': 0.2}
    raw_routes = []
    seen_paths = set()

    for center in target_centers:
        try:
            d_node, d_dist = get_nearest_node(graph, center['lat'], center['lon'])
            if d_node == origin_node: continue
            
            cost, path = dijkstra(graph, origin_node, d_node, request.scenario, w, max_edge_length)
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
            d_node, d_dist = get_nearest_node(graph, main_center['lat'], main_center['lon'])
            alts = yens_k_shortest_paths(graph, origin_node, d_node, K, request.scenario, w, max_edge_length)
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

    scored = score_routes(raw_routes[:K], graph, request.scenario, w, max_edge_length)
    
    origin_node_data = graph.nodes.get(origin_node, {})
    origin_info = {
        'lat': request.origin_lat,
        'lon': request.origin_lon,
        'nearest_node_id': str(origin_node),
        'nearest_node_lat': origin_node_data.get('lat'),
        'nearest_node_lon': origin_node_data.get('lon'),
        'snap_distance_m': round(origin_dist, 1),
    }

    result = routes_to_geojson(scored, graph, request.scenario, origin_info)
    result['computation_time_ms'] = round((time.time() - t0) * 1000, 2)
    return result
