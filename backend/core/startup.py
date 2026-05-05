from backend.graph.builder import build_graph
from backend.graph.connectivity import ensure_connected
from backend.prediction.raster_sampler import sample_rasters
from backend.prediction.loader import load_models
from backend.prediction.flood_predictor import precompute_predictions
from backend.api.centers_loader import load_centers, load_centers_geojson

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
    
    # Construct raw GeoJSONs for API passthrough
    from backend.core.database import get_db_connection
    from sqlalchemy import text
    import json
    
    print("[7/7] Fetching GeoJSONs from DB...")
    road_geojson = {"type": "FeatureCollection", "features": []}
    try:
        with get_db_connection() as conn:
            result = conn.execute(text("SELECT osmid, name, highway, length, ST_AsGeoJSON(geom) FROM road_edges"))
            for row in result:
                road_geojson["features"].append({
                    "type": "Feature",
                    "geometry": json.loads(row[4]),
                    "properties": {
                        "osmid": str(row[0]),
                        "name": str(row[1] or 'Unnamed Road'),
                        "highway": str(row[2] or 'unclassified'),
                        "length": float(row[3] or 0.0)
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
        'max_edge_length': MAX_EDGE_LENGTH,
        'predicted_scenarios': set(),   # tracks which scenarios have had on-the-fly inference run
    }
