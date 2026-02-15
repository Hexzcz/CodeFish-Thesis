import geopandas as gpd
import pandas as pd
import osmnx as ox
import os
from datetime import datetime

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# ---------------------
# 1. Get District 1 Boundary
# ---------------------
log("Getting District 1 (QC) boundary...")
district1_barangays = [
    "Alicia", "Bagong Pag-asa", "Bahay Toro", "Balingasa", "Bungad",
    "Damar", "Damayan", "Del Monte", "Katipunan", "Lourdes",
    "Maharlika", "Manresa", "Mariblo", "Masambong", "N.S. Amoranto",
    "Nayong Kanluran", "Paang Bundok", "Pag-ibig sa Nayon", "Paltok", "Paraiso",
    "Phil-Am", "Project 6", "Ramon Magsaysay", "Saint Peter", "Salvacion",
    "San Antonio", "San Isidro Labrador", "San Jose", "Santa Cruz", "Santa Teresita",
    "Sto. Cristo", "Santo Domingo", "Siena", "Talayan", "Vasra",
    "Veterans Village", "West Triangle"
]

district1_parts = []
for brgy in district1_barangays:
    query = f"{brgy}, Quezon City, Philippines"
    try:
        brgy_gdf = ox.geocode_to_gdf(query)
        brgy_gdf = brgy_gdf.to_crs(epsg=4326)
        district1_parts.append(brgy_gdf)
        log(f"  ✓ Loaded {brgy}")
    except Exception as e:
        log(f"  ✗ Failed to load {brgy}: {e}")

if not district1_parts:
    log("Critical Error: Could not load any District 1 barangays. Exiting.")
    exit(1)

district1_boundary_gdf = gpd.GeoDataFrame(
    pd.concat(district1_parts, ignore_index=True),
    crs=district1_parts[0].crs
).dissolve()
log(f"  ✓ District 1 boundary created (EPSG:4326)")

# ---------------------
# 2. Get Road Network (with 500m Buffer for Context)
# ---------------------
log("Fetching road network (with 500m buffer for context)...")
utm_crs = district1_boundary_gdf.estimate_utm_crs()
buffered_boundary_utm = district1_boundary_gdf.to_crs(utm_crs).buffer(500)
buffered_boundary_4326 = buffered_boundary_utm.to_crs(epsg=4326).iloc[0]

G = ox.graph_from_polygon(buffered_boundary_4326, network_type='all', retain_all=True)
nodes, buffered_roads = ox.graph_to_gdfs(G)
log(f"  ✓ {len(buffered_roads)} road segments fetched (including 500m buffer)")

# ---------------------
# 3. Load and CLIP Flood Data (Strictly to District 1)
# ---------------------
log("Checking flood shapefile...")
temp_gdf = gpd.read_file("ph137404000_fh100yr_30m_10m.shp", rows=1)
shapefile_crs = temp_gdf.crs

log("Loading and clipping flood data...")
boundary_for_mask = district1_boundary_gdf.to_crs(shapefile_crs)
flood_gdf = gpd.read_file("ph137404000_fh100yr_30m_10m.shp", mask=boundary_for_mask)
flood_gdf = flood_gdf.to_crs(epsg=4326)
flood_gdf = gpd.clip(flood_gdf, district1_boundary_gdf)

log("Simplifying flood geometries...")
flood_gdf['geometry'] = flood_gdf.simplify(0.00005, preserve_topology=True)
log(f"  ✓ Processed {len(flood_gdf)} clipped flood polygons")

# ---------------------
# 4. Analyze Risk
# ---------------------
log("Analyzing flood risk on roads...")
if buffered_roads.crs != flood_gdf.crs:
    buffered_roads = buffered_roads.to_crs(flood_gdf.crs)

roads_joined = gpd.sjoin(buffered_roads, flood_gdf[['Var', 'geometry']], how="left", predicate="intersects")

if 'Var' in roads_joined.columns:
    roads_joined['Var'] = pd.to_numeric(roads_joined['Var'], errors='coerce').fillna(0)
    road_risks = roads_joined.groupby(level=[0, 1, 2])['Var'].max()
    buffered_roads['risk_level'] = road_risks
else:
    buffered_roads['risk_level'] = 0
log("  ✓ Risk analysis complete")

# ---------------------
# 5. Save Files
# ---------------------
qc_boundary_gdf = ox.geocode_to_gdf("Quezon City, Philippines").to_crs(epsg=4326)

log("Saving results...")
output_files = {
    "flood_clipped.geojson": flood_gdf,
    "qc_boundary.geojson": qc_boundary_gdf,
    "district1_boundary.geojson": district1_boundary_gdf,
    "district1_roads.geojson": buffered_roads
}

for filename, gdf in output_files.items():
    if os.path.exists(filename):
        os.remove(filename)
    gdf.to_file(filename, driver="GeoJSON")
    log(f"  ✓ Saved {filename}")

log("Success! District 1 data is ready.")
