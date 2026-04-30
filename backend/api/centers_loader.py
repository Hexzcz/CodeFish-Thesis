import os
import json
from typing import List, Dict
from backend.core.config import GEOJSON_PATHS

def load_centers() -> List[Dict]:
    """Load evacuation centers into memory."""
    evacuation_centers = []
    evac_file = GEOJSON_PATHS['centers']
    print("[6/6] Loading evacuation centers...")

    if not os.path.exists(evac_file):
        print(f"      WARNING: {evac_file} not found")
        return evacuation_centers

    with open(evac_file, encoding='utf-8') as f:
        evac_geojson = json.load(f)

    for feat in evac_geojson.get('features', []):
        coords = feat['geometry']['coordinates']
        props = feat.get('properties', {})
        evacuation_centers.append({
            'lat': float(coords[1]),
            'lon': float(coords[0]),
            'facility': props.get('facility', 'Unknown Center'),
            'barangay': props.get('barangay', ''),
            'type': props.get('type', 'Other'),
        })

    print(f"      {len(evacuation_centers)} centers loaded")
    return evacuation_centers

def load_centers_geojson() -> Dict:
    """Load centers GeoJSON."""
    evac_file = GEOJSON_PATHS['centers']
    if os.path.exists(evac_file):
        with open(evac_file, encoding='utf-8') as f:
            return json.load(f)
    return {}
