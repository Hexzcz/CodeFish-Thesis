import os
import json
from typing import List, Dict
from backend.core.config import GEOJSON_PATHS, USE_LOCAL_DATA

def _load_centers_file() -> Dict:
    """Read the bundled evacuation_centers GeoJSON."""
    with open(GEOJSON_PATHS['centers'], 'r') as f:
        return json.load(f)

def load_centers_from_file() -> List[Dict]:
    """Load evacuation centers from the bundled GeoJSON (offline)."""
    evacuation_centers = []
    geojson = _load_centers_file()
    for feature in geojson.get('features', []):
        props = feature.get('properties', {})
        coords = feature.get('geometry', {}).get('coordinates', [0, 0])
        evacuation_centers.append({
            'lat': float(coords[1]),
            'lon': float(coords[0]),
            'facility': str(props.get('facility') or 'Unknown Center'),
            'barangay': str(props.get('barangay') or ''),
            'type': str(props.get('type') or 'Other'),
        })
    print(f"      {len(evacuation_centers)} centers loaded from local GeoJSON")
    return evacuation_centers

def load_centers() -> List[Dict]:
    """Load evacuation centers from Supabase, falling back to local GeoJSON."""
    from backend.core.database import get_db_connection
    from sqlalchemy import text
    import json

    if USE_LOCAL_DATA:
        print("[6/6] Loading evacuation centers from local GeoJSON...")
        return load_centers_from_file()

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

    if not evacuation_centers:
        print("  Falling back to local evacuation centers GeoJSON.")
        return load_centers_from_file()
    return evacuation_centers

def load_centers_geojson() -> Dict:
    """Load centers GeoJSON from Supabase, falling back to local GeoJSON."""
    from backend.core.database import get_db_connection
    from sqlalchemy import text
    import json

    if USE_LOCAL_DATA:
        return _load_centers_file()

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

    if not geojson["features"]:
        print("  Falling back to local evacuation centers GeoJSON.")
        return _load_centers_file()
    return geojson
