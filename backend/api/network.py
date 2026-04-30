import json
import os
from fastapi import APIRouter, HTTPException, Depends, Request
from backend.core.config import GEOJSON_PATHS

router = APIRouter()

def get_app_state(request: Request):
    return request.app.state.data

@router.get("/boundary")
async def get_boundary():
    path = GEOJSON_PATHS['boundary']
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    raise HTTPException(status_code=404, detail="Boundary not found")

@router.get("/roads")
async def get_roads(state: dict = Depends(get_app_state)):
    road_geojson = state.get('road_geojson')
    if road_geojson is None:
        raise HTTPException(404, "Road GeoJSON not loaded")
    return road_geojson

@router.get("/graph-stats")
async def get_graph_stats(state: dict = Depends(get_app_state)):
    graph = state['graph']
    models = state['models']
    lats = [n['lat'] for n in graph.nodes.values()]
    lons = [n['lon'] for n in graph.nodes.values()]
    return {
        'total_nodes': graph.node_count(),
        'total_edges': graph.edge_count(),
        'scenarios_precomputed': list(models.keys()),
        'bounds': {
            'north': max(lats) if lats else 0,
            'south': min(lats) if lats else 0,
            'east': max(lons) if lons else 0,
            'west': min(lons) if lons else 0,
        },
    }

@router.get("/graph/diagnostics")
async def get_graph_diagnostics(state: dict = Depends(get_app_state)):
    graph = state['graph']
    models = state['models']
    centers = state['centers']
    
    if graph.node_count() == 0:
        return {"error": "Graph not loaded yet"}

    lats = [n['lat'] for n in graph.nodes.values()]
    lons = [n['lon'] for n in graph.nodes.values()]

    sample_nodes = [
        {'id': str(nid), 'lat': n['lat'], 'lon': n['lon']}
        for nid, n in list(graph.nodes.items())[:3]
    ]

    highway_counts = {}
    seen_edges = set()
    for (u, v), edge in graph.edges.items():
        key = (min(u, v), max(u, v))
        if key in seen_edges:
            continue
        seen_edges.add(key)
        hw = str(edge.get('highway', 'other') or 'other')
        hw = hw if hw in ('primary', 'secondary', 'tertiary', 'residential', 'service') else 'other'
        highway_counts[hw] = highway_counts.get(hw, 0) + 1

    return {
        "total_nodes": graph.node_count(),
        "total_edges": graph.edge_count(),
        "is_connected": hasattr(graph, 'main_component') and len(graph.main_component) == graph.node_count(),
        "main_component_size": len(graph.main_component) if hasattr(graph, 'main_component') else 0,
        "evacuation_centers_loaded": len(centers),
        "models_loaded": list(models.keys()),
        "bounds": {
            "north": round(max(lats), 6),
            "south": round(min(lats), 6),
            "east": round(max(lons), 6),
            "west": round(min(lons), 6),
        },
        "sample_nodes": sample_nodes,
        "road_type_breakdown": highway_counts,
    }
