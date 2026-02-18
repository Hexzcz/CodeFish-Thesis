import json

def simplify_boundary():
    input_file = "district1_boundary.geojson"
    with open(input_file, 'r') as f:
        data = json.load(f)

    for feature in data['features']:
        geom = feature['geometry']
        if geom['type'] == 'MultiPolygon':
            # coordinates: [Polygon, Polygon, ...]
            # Polygon: [Ring, Ring, ...]
            # Ring: [Point, Point, ...]
            
            # Extract the coordinates of the first ring of the first polygon
            # Currently it is [[[[...]]]]
            # Level 1: [Polygons] -> coords[0] is First Polygon
            # Level 2: [Rings] -> coords[0][0] is First Ring
            # Level 3: [Points] -> coords[0][0][0] is First Point
            
            # Let's simplify to a regular Polygon
            outer_ring = geom['coordinates'][0][0]
            
            feature['geometry'] = {
                "type": "Polygon",
                "coordinates": [outer_ring]
            }
            print("Simplified MultiPolygon to Polygon.")

    with open(input_file, 'w') as f:
        json.dump(data, f)
    print("Done.")

if __name__ == "__main__":
    simplify_boundary()
