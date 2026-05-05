import os
import json
from typing import List, Dict
from backend.core.config import GEOJSON_PATHS

def load_centers() -> List[Dict]:
    """Load evacuation centers from Supabase."""
    from backend.core.database import get_db_connection
    from sqlalchemy import text
    import json
    
    evacuation_centers = []
    print("[6/6] Loading evacuation centers from DB...")
    try:
        with get_db_connection() as conn:
            result = conn.execute(text("SELECT id, barangay, facility, type, ST_AsGeoJSON(geom) FROM evacuation_centers"))
            for row in result:
                geom = json.loads(row[4])
                coords = geom.get('coordinates', [0, 0])
                evacuation_centers.append({
                    'lat': float(coords[1]),
                    'lon': float(coords[0]),
                    'facility': str(row[2] or 'Unknown Center'),
                    'barangay': str(row[1] or ''),
                    'type': str(row[3] or 'Other'),
                })
        print(f"      {len(evacuation_centers)} centers loaded")
    except Exception as e:
        print(f"Error loading centers from DB: {e}")
    return evacuation_centers

def load_centers_geojson() -> Dict:
    """Load centers GeoJSON from Supabase."""
    from backend.core.database import get_db_connection
    from sqlalchemy import text
    import json
    
    geojson = {
        "type": "FeatureCollection",
        "features": []
    }
    try:
        with get_db_connection() as conn:
            result = conn.execute(text("SELECT id, barangay, facility, type, ST_AsGeoJSON(geom) FROM evacuation_centers"))
            for row in result:
                geojson["features"].append({
                    "type": "Feature",
                    "geometry": json.loads(row[4]),
                    "properties": {
                        "id": str(row[0]),
                        "barangay": str(row[1] or ''),
                        "facility": str(row[2] or 'Unknown Center'),
                        "type": str(row[3] or 'Other')
                    }
                })
    except Exception as e:
        print(f"Error loading centers geojson from DB: {e}")
    return geojson
