import geopandas as gpd
from sqlalchemy import create_engine
import os

# --- Replace this with your actual Supabase connection string ---
# You can find this in Supabase -> Settings -> Database -> Connection string (URI)
# It looks like: postgresql://postgres.xxxxxxxx:your_password@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
DB_CONNECTION_URL = "postgresql://postgres:pWkejwZmBik1tMYr@db.uniqqsjwsqnboeuzhdyf.supabase.co:5432/postgres"

print("Connecting to Supabase...")
engine = create_engine(DB_CONNECTION_URL)

def upload_geojson(file_path, table_name, geom_type):
    print(f"Loading {file_path}...")
    if not os.path.exists(file_path):
        print(f"  -> File not found, skipping {table_name}.")
        return

    # Read the GeoJSON
    gdf = gpd.read_file(file_path)
    
    # Ensure it's in the standard WGS84 coordinate system
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
        
    # Rename 'geometry' column to 'geom' to match our PostGIS schema
    gdf = gdf.rename_geometry('geom')
    
    # Convert list/dict types to strings (PostgreSQL doesn't like Python lists in text columns)
    for col in gdf.columns:
        if gdf[col].dtype == 'object' and col != 'geom':
            gdf[col] = gdf[col].apply(lambda x: str(x) if isinstance(x, (list, dict)) else x)

    # Upload to PostGIS
    print(f"Uploading {len(gdf)} records to {table_name} table...")
    gdf.to_postgis(
        name=table_name,
        con=engine,
        if_exists='append', # Append to the tables we created via SQL
        index=False         # Don't upload the pandas index
    )
    print(f"Successfully uploaded to {table_name}!\n")

# 1. Upload Nodes
upload_geojson("backend/data/geojson/road_nodes.geojson", "road_nodes", "Point")

# 2. Upload Edges
upload_geojson("backend/data/geojson/road_edges.geojson", "road_edges", "LineString")

# 3. Upload Evacuation Centers
upload_geojson("evacuation_centers.geojson", "evacuation_centers", "Point")

# 4. Upload District Boundary (If you have a GeoJSON for it, otherwise comment this out for now)
# upload_geojson("district_1_boundary.geojson", "district_boundary", "MultiPolygon")

print("Migration complete!")
