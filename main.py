import geopandas as gpd
import pandas as pd
import osmnx as ox
import os
from datetime import datetime

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# ---------------------
# 1. Get Project 8 Boundary
# ---------------------
log("Getting Project 8 boundary (Baesa, Bahay Toro, Sangandaan)...")
barangays = [
    "Baesa, Quezon City, Philippines",
    "Bahay Toro, Quezon City, Philippines",
    "Sangandaan, Quezon City, Philippines"
]

project8_parts = []
for brgy in barangays:
    try:
        brgy_gdf = ox.geocode_to_gdf(brgy)
        brgy_gdf = brgy_gdf.to_crs(epsg=4326)
        project8_parts.append(brgy_gdf)
        log(f"  ✓ Loaded {brgy}")
    except Exception as e:
        log(f"  ✗ Failed to load {brgy}: {e}")

if not project8_parts:
    log("Critical Error: Could not load any Project 8 barangays. Exiting.")
    exit(1)

project8_boundary_gdf = gpd.GeoDataFrame(
    pd.concat(project8_parts, ignore_index=True),
    crs=project8_parts[0].crs
).dissolve()
log(f"  ✓ Project 8 boundary created (EPSG:4326)")

# ---------------------
# 2. Get Road Network (with 500m Buffer for Context)
# ---------------------
log("Fetching road network (with 500m buffer for context)...")
# Filter to UTM for accurate buffering in meters
utm_crs = project8_boundary_gdf.estimate_utm_crs()
buffered_boundary_utm = project8_boundary_gdf.to_crs(utm_crs).buffer(500)
# Convert back to EPSG:4326 for OSMnx
buffered_boundary_4326 = buffered_boundary_utm.to_crs(epsg=4326).iloc[0]

G = ox.graph_from_polygon(buffered_boundary_4326, network_type='all', retain_all=True)
nodes, buffered_roads = ox.graph_to_gdfs(G)
log(f"  ✓ {len(buffered_roads)} road segments fetched (including 500m buffer)")

# ---------------------
# 3. Load and CLIP Flood Data (Strictly to Project 8)
# ---------------------
log("Checking flood shapefile CRS...")
temp_gdf = gpd.read_file("ph137404000_fh100yr_30m_10m.shp", rows=1)
shapefile_crs = temp_gdf.crs
log(f"  ✓ Shapefile CRS: {shapefile_crs}")

log("Loading flood data using mask...")
boundary_for_mask = project8_boundary_gdf.to_crs(shapefile_crs)
flood_gdf = gpd.read_file("ph137404000_fh100yr_30m_10m.shp", mask=boundary_for_mask)
flood_gdf = flood_gdf.to_crs(epsg=4326)

log("Clipping flood polygons strictly to Project 8 boundary...")
flood_gdf = gpd.clip(flood_gdf, project8_boundary_gdf)

log("Simplifying flood geometries for performance...")
flood_gdf['geometry'] = flood_gdf.simplify(0.00005, preserve_topology=True)
log(f"  ✓ Processed {len(flood_gdf)} clipped flood polygons")

# ---------------------
# 4. Analyze Risk (on Buffered Roads)
# ---------------------
log("Analyzing flood risk...")
if buffered_roads.crs != flood_gdf.crs:
    buffered_roads = buffered_roads.to_crs(flood_gdf.crs)

# Spatial join to apply risk level from flood polygons to roads
roads_joined = gpd.sjoin(buffered_roads, flood_gdf[['Var', 'geometry']], how="left", predicate="intersects")

if 'Var' in roads_joined.columns:
    roads_joined['Var'] = pd.to_numeric(roads_joined['Var'], errors='coerce').fillna(0)
    # Take max risk per road segment
    road_risks = roads_joined.groupby(level=[0, 1, 2])['Var'].max()
    buffered_roads['risk_level'] = road_risks
else:
    buffered_roads['risk_level'] = 0
log("  ✓ Risk analysis complete")

# ---------------------
# 5. Save Files
# ---------------------
log("Getting QC boundary reference...")
qc_boundary_gdf = ox.geocode_to_gdf("Quezon City, Philippines").to_crs(epsg=4326)

log("Saving results...")
output_files = {
    "flood_clipped.geojson": flood_gdf,
    "qc_boundary.geojson": qc_boundary_gdf,
    "project8_boundary.geojson": project8_boundary_gdf,
    "project8_roads.geojson": buffered_roads
}

for filename, gdf in output_files.items():
    if os.path.exists(filename):
        os.remove(filename)
    gdf.to_file(filename, driver="GeoJSON")
    log(f"  ✓ Saved {filename}")

if os.path.exists("qc_roads.geojson"):
    os.remove("qc_roads.geojson")

log("Success! Project 8 data with 500m road buffer is ready.")
