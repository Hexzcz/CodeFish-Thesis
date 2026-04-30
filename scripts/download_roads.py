import osmnx as ox, json, math
from shapely.geometry import mapping
from shapely.ops import linemerge

print("Downloading District 1 road network...")

try:
    G = ox.graph_from_place(
        "District 1, Quezon City, Metro Manila, Philippines",
        network_type="drive"
    )
except Exception:
    G = ox.graph_from_place(
        "Quezon City, Metro Manila, Philippines",
        network_type="drive"
    )

edges = ox.graph_to_gdfs(G, nodes=False, edges=True).reset_index()
print(f"Downloaded {len(edges)} edges")

def simplify_geom(geom):
    if geom.geom_type == "MultiLineString":
        merged = linemerge(geom)
        if merged.geom_type == "LineString":
            return merged
        return max(geom.geoms, key=lambda g: g.length)
    return geom

def get_name(row):
    v = row.get("name", None)
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "Unnamed Road"
    if isinstance(v, list):
        return v[0] if v else "Unnamed Road"
    return str(v)

def get_highway(row):
    v = row.get("highway", "unclassified")
    if isinstance(v, list):
        v = v[0] if v else "unclassified"
    return str(v)

def get_osmid(row):
    v = row.get("osmid", 0)
    if isinstance(v, list):
        v = v[0] if v else 0
    try: return int(v)
    except: return 0

features = []
for _, row in edges.iterrows():
    try:
        geom = simplify_geom(row["geometry"])
        if geom is None or geom.is_empty:
            continue
        features.append({
            "type": "Feature",
            "geometry": mapping(geom),
            "properties": {
                "osmid":    get_osmid(row),
                "name":     get_name(row),
                "highway":  get_highway(row),
                "length":   round(float(row.get("length", 0)), 2)
            }
        })
    except Exception as ex:
        continue

geojson = {"type": "FeatureCollection", "features": features}
with open("road_edges.geojson", "w", encoding="utf-8") as f:
    json.dump(geojson, f)

print(f"Saved road_edges.geojson with {len(features)} features")
