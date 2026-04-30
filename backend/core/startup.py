from backend.graph.builder import build_graph
from backend.graph.connectivity import ensure_connected
from backend.prediction.raster_sampler import sample_rasters
from backend.prediction.loader import load_models
from backend.prediction.flood_predictor import precompute_predictions
from backend.api.centers_loader import load_centers
import os
import json
from backend.core.config import GEOJSON_PATHS

async def startup():
    print("=" * 52)
    print("  CodeFish Flood-Aware Routing — Starting Up  ")
    print("=" * 52)

    print("[1/6] Loading road network...")
    graph = build_graph()
    
    print("[2/6] Checking connectivity...")
    graph = ensure_connected(graph)
    
    # Store global max edge length if needed
    MAX_EDGE_LENGTH = graph.max_edge_length
    
    print("[3/6] Sampling rasters...")
    graph = sample_rasters(graph)
    
    print("[4/6] Loading models...")
    models = load_models()
    
    print("[5/6] Computing predictions...")
    graph = precompute_predictions(graph, models)
    
    print("[6/6] Loading centers...")
    centers = load_centers()
    
    # Load raw GeoJSONs for API passthrough
    road_geojson = None
    if os.path.exists(GEOJSON_PATHS['road_edges']):
        with open(GEOJSON_PATHS['road_edges'], encoding='utf-8') as f:
            road_geojson = json.load(f)
            
    evac_geojson = None
    if os.path.exists(GEOJSON_PATHS['centers']):
        with open(GEOJSON_PATHS['centers'], encoding='utf-8') as f:
            evac_geojson = json.load(f)

    print()
    print("Application ready.")
    print("POST /route — flood-aware routing active")
    print("=" * 52)
    
    return {
        'graph': graph,
        'models': models,
        'centers': centers,
        'road_geojson': road_geojson,
        'evac_geojson': evac_geojson,
        'max_edge_length': MAX_EDGE_LENGTH
    }
