import json

def fix_geojson():
    # 1. Fix District 1 Boundary
    # I have to reconstruct it carefully because the previous attempt failed.
    # Looking at the coordinates in Step 730, it seems the MultiPolygon has multiple rings.
    # The first list in [[[[...]]]] is the main ring.
    
    with open('district1_boundary.geojson', 'r') as f:
        data = json.load(f)

    for feature in data['features']:
        if feature['geometry']['type'] == 'MultiPolygon':
            # Identify the largest polygon by coordinate count (heuristic for main district)
            polygons = feature['geometry']['coordinates']
            main_poly_idx = 0
            max_len = 0
            for i, poly in enumerate(polygons):
                if len(poly[0]) > max_len:
                    max_len = len(poly[0])
                    main_poly_idx = i
            
            # Keep only the main polygon and its outer ring (remove holes)
            feature['geometry']['coordinates'] = [[polygons[main_poly_idx][0]]]

    with open('district1_boundary.geojson', 'w') as f:
        json.dump(data, f)
    print("Fixed District 1 Boundary.")

    # 2. Fix Road Network (Filtering by District 1 Boundary)
    # We'll use a simple bounding box check first to remove distant clusters like those near Marikina.
    # District 1 is roughly [120.98, 14.61] to [121.06, 14.68]
    # Marikina is much further east (approx 121.10+)
    
    with open('district1_roads.geojson', 'r') as f:
        roads_data = json.load(f)

    # District 1 Boundary Box (Roughly)
    MIN_LON, MAX_LON = 120.98, 121.06
    MIN_LAT, MAX_LAT = 14.61, 14.70

    filtered_features = []
    removed_count = 0
    for feature in roads_data['features']:
        coords = feature['geometry']['coordinates']
        # Check if any part of the road is within our rough District 1 box
        is_inside = False
        if feature['geometry']['type'] == 'LineString':
            for pt in coords:
                if MIN_LON <= pt[0] <= MAX_LON and MIN_LAT <= pt[1] <= MAX_LAT:
                    is_inside = True
                    break
        elif feature['geometry']['type'] == 'Point':
            pt = coords
            if MIN_LON <= pt[0] <= MAX_LON and MIN_LAT <= pt[1] <= MAX_LAT:
                is_inside = True
        
        if is_inside:
            filtered_features.append(feature)
        else:
            removed_count += 1

    roads_data['features'] = filtered_features
    with open('district1_roads.geojson', 'w') as f:
        json.dump(roads_data, f)
    print(f"Filtered Road Network: Removed {removed_count} outlier features.")

if __name__ == "__main__":
    fix_geojson()
