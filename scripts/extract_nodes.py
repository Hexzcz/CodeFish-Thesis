"""
Extract nodes from road_edges.geojson to create road_nodes.geojson
"""
import geopandas as gpd
from shapely.geometry import Point
import json

print("Loading road edges...")
edges = gpd.read_file('road_edges.geojson')

print(f"Loaded {len(edges)} edges")

# Extract unique nodes from edges
nodes = {}

for idx, row in edges.iterrows():
    u = row.get('u')
    v = row.get('v')
    geom = row.geometry
    
    if geom is None or geom.geom_type not in ['LineString', 'MultiLineString']:
        continue
    
    # Get coordinates
    if geom.geom_type == 'LineString':
        coords = list(geom.coords)
    else:
        coords = list(geom.geoms[0].coords)
    
    if len(coords) < 2:
        continue
    
    # Start node
    if u is not None and u not in nodes:
        nodes[u] = Point(coords[0])
    
    # End node
    if v is not None and v not in nodes:
        nodes[v] = Point(coords[-1])

print(f"Extracted {len(nodes)} unique nodes")

# Create GeoDataFrame
features = []
for osmid, point in nodes.items():
    features.append({
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [point.x, point.y]
        },
        'properties': {
            'osmid': osmid,
            'lat': point.y,
            'lon': point.x
        }
    })

geojson = {
    'type': 'FeatureCollection',
    'features': features
}

print("Writing road_nodes.geojson...")
with open('road_nodes.geojson', 'w') as f:
    json.dump(geojson, f)

print("Done!")
