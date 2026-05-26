from backend.graph.builder import build_graph
from backend.graph.connectivity import ensure_connected
from backend.prediction.raster_sampler import sample_rasters
from backend.prediction.loader import load_models
from backend.prediction.flood_predictor import precompute_predictions
from backend.api.centers_loader import load_centers, load_centers_geojson
from backend.core.config import GEOJSON_PATHS
import json

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
    
    print("[5/6] Computing predictions (disabled for on-the-fly inference)...")
    # graph = precompute_predictions(graph, models)
    
    print("[6/6] Loading centers...")
    centers = load_centers()
    
    print("[7/7] Loading District 1 boundary...")
    boundary_geojson = None
    boundary_path = GEOJSON_PATHS['boundary']
    try:
        with open(boundary_path, 'r') as f:
            boundary_geojson = json.load(f)
        print(f"  Loaded boundary from {boundary_path}")
    except Exception as e:
        print(f"  Warning: Could not load boundary geojson: {e}")
    
    # Construct raw GeoJSONs for API passthrough
    from backend.core.database import get_db_connection
    from sqlalchemy import text
    
    print("[8/8] Fetching GeoJSONs from DB...")
    road_geojson = {"type": "FeatureCollection", "features": []}
    try:
        with get_db_connection() as conn:
            result = conn.execute(text("SELECT u, v, osmid, name, highway, length, ST_AsGeoJSON(geom) FROM road_edges"))
            for row in result:
                road_geojson["features"].append({
                    "type": "Feature",
                    "geometry": json.loads(row[6]),
                    "properties": {
                        "u": str(row[0]),
                        "v": str(row[1]),
                        "osmid": str(row[2]),
                        "name": str(row[3] or 'Unnamed Road'),
                        "highway": str(row[4] or 'unclassified'),
                        "length": float(row[5] or 0.0)
                    }
                })
    except Exception as e:
        print(f"Error fetching road_geojson from DB: {e}")
            
    evac_geojson = load_centers_geojson()

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
        'boundary_geojson': boundary_geojson,
        'max_edge_length': MAX_EDGE_LENGTH,
        'predicted_scenarios': set(),   # tracks which scenarios have had on-the-fly inference run
    }
