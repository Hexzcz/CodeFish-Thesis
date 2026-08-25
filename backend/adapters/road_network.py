"""Loading the road network — from Supabase, or from the bundled GeoJSON.

Both loaders produce the same `Graph`; the database is tried first and the
files are the fallback, so the app still runs with no network. See
`docs/decisions/0002-local-geojson-fallback.md`.
"""
import json
from typing import Dict

from backend.core.config import GEOJSON_PATHS
from backend.domain.graph import Graph


def _blank_edge_data(osmid, name, highway, length, coords) -> Dict:
    return {
        'osmid': str(osmid),
        'name': str(name or 'Unnamed Road'),
        'highway': str(highway or 'unclassified'),
        'length': length,
        'geometry': coords,
        'flood_class_5yr':   None,
        'flood_class_25yr':  None,
        'flood_class_100yr': None,
        'flood_proba_5yr':   None,
        'flood_proba_25yr':  None,
        'flood_proba_100yr': None,
        'elevation': None,
        'features': None,
    }

def build_graph_from_files() -> Graph:
    """Build the Graph from the bundled road_nodes/road_edges GeoJSON (offline)."""
    graph = Graph()
    max_edge_length_found = 0.0

    print("Loading nodes from local GeoJSON...")
    with open(GEOJSON_PATHS['road_nodes'], 'r') as f:
        nodes_geojson = json.load(f)
    for feature in nodes_geojson.get('features', []):
        props = feature.get('properties', {})
        coords = feature.get('geometry', {}).get('coordinates', [None, None])
        lat = props.get('lat', coords[1])
        lon = props.get('lon', coords[0])
        if lat is None or lon is None:
            continue
        graph.add_node(str(props.get('osmid')), lat=float(lat), lon=float(lon))

    print("Loading edges from local GeoJSON...")
    with open(GEOJSON_PATHS['road_edges'], 'r') as f:
        edges_geojson = json.load(f)
    for feature in edges_geojson.get('features', []):
        props = feature.get('properties', {})
        u = str(props.get('u'))
        v = str(props.get('v'))

        # If nodes don't exist, we can't create the edge
        if not graph.has_node(u) or not graph.has_node(v):
            continue

        l_val = float(props.get('length') or 0.0)
        if l_val > max_edge_length_found:
            max_edge_length_found = l_val

        coords_raw = feature.get('geometry', {}).get('coordinates', [])

        graph.add_edge(u, v, _blank_edge_data(
            props.get('osmid'), props.get('name'), props.get('highway'), l_val, coords_raw
        ))

    graph.max_edge_length = max_edge_length_found
    print(f"Graph built with {graph.node_count()} nodes and {graph.edge_count()} edges.")
    return graph

def build_graph() -> Graph:
    """Load road_nodes and road_edges from Supabase, falling back to local GeoJSON."""
    from backend.core.config import USE_LOCAL_DATA
    from backend.adapters.database import get_db_connection
    from sqlalchemy import text
    import json

    if USE_LOCAL_DATA:
        return build_graph_from_files()

    graph = Graph()
    max_edge_length_found = 0.0

    try:
        with get_db_connection() as conn:
            # 1. Load Nodes
            print("Fetching nodes from Supabase...")
            nodes_result = conn.execute(text("SELECT osmid, lat, lon FROM road_nodes"))
            for row in nodes_result:
                osmid_str = str(row[0])
                graph.add_node(osmid_str, lat=row[1], lon=row[2])

            # 2. Load Edges
            print("Fetching edges from Supabase...")
            edges_result = conn.execute(text("SELECT u, v, osmid, name, highway, length, ST_AsGeoJSON(geom) as geom_json FROM road_edges"))
            for row in edges_result:
                u = str(row[0])
                v = str(row[1])

                # If nodes don't exist, we can't create the edge
                if not graph.has_node(u) or not graph.has_node(v):
                    continue

                l_val = float(row[5] or 0.0)
                if l_val > max_edge_length_found:
                    max_edge_length_found = l_val

                geom_json = json.loads(row[6])
                coords_raw = geom_json.get('coordinates', [])

                graph.add_edge(u, v, _blank_edge_data(
                    row[2], row[3], row[4], l_val, coords_raw
                ))

        print(f"Graph built with {graph.node_count()} nodes and {graph.edge_count()} edges.")
    except Exception as e:
        print(f"Error building graph from DB: {e}")

    if graph.edge_count() == 0:
        print("  Falling back to local GeoJSON road network.")
        return build_graph_from_files()

    graph.max_edge_length = max_edge_length_found
    return graph


def load_road_geojson() -> Dict:
    """The road network as raw GeoJSON, for the map to draw.

    Same fallback as `build_graph`: database first, bundled file otherwise.
    """
    from backend.core.config import USE_LOCAL_DATA
    from backend.adapters.database import get_db_connection
    from sqlalchemy import text

    if USE_LOCAL_DATA:
        return _road_geojson_from_file()

    road_geojson = {"type": "FeatureCollection", "features": []}
    try:
        with get_db_connection() as conn:
            result = conn.execute(text(
                "SELECT u, v, osmid, name, highway, length, ST_AsGeoJSON(geom) FROM road_edges"
            ))
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
                        "length": float(row[5] or 0.0),
                    },
                })
    except Exception as e:
        print(f"Error fetching road_geojson from DB: {e}")

    if not road_geojson["features"]:
        print("  Falling back to local road edges GeoJSON.")
        return _road_geojson_from_file()
    return road_geojson


def _road_geojson_from_file() -> Dict:
    with open(GEOJSON_PATHS['road_edges'], 'r') as f:
        return json.load(f)
