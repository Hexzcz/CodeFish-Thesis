import osmnx as ox
import geopandas as gpd
from shapely.geometry import box, Polygon, MultiPolygon
import json
import os

def download_boundary():
    # Attempt 1: Specific query
    query = "District 1, Quezon City, Metro Manila, Philippines"
    print(f"Attempting to download boundary for: {query}")
    
    try:
        # ox.geocode_to_gdf can be picky, let's try direct search
        gdf = ox.geocode_to_gdf(query)
        if gdf.empty:
            raise ValueError("Empty GDF")
    except Exception as e:
        print(f"Query '{query}' failed: {e}")
        # Attempt 2: Broader query + Bounding Box clip
        qc_query = "Quezon City, Metro Manila, Philippines"
        print(f"Attempting fallback: {qc_query} clipped to District 1 bounds")
        
        # Bounding box coordinates from requirements
        # north=14.70, south=14.58, east=121.13, west=120.99
        west, south, east, north = 120.99, 14.58, 121.13, 14.70
        
        try:
            gdf = ox.geocode_to_gdf(qc_query)
            if not gdf.empty:
                bbox = box(west, south, east, north)
                bbox_gdf = gpd.GeoDataFrame({'geometry': [bbox]}, crs="EPSG:4326")
                # Clip QC geometry to District 1 bbox
                gdf = gpd.clip(gdf, bbox_gdf)
            
            if gdf.empty or gdf.geometry.iloc[0] is None:
                raise ValueError("Clipped GDF is empty")
        except Exception as e2:
            print(f"Fallback query failed: {e2}")
            # Attempt 3: Final fallback - Pure Box
            print("Generating fallback rectangular boundary from bounding box")
            west, south, east, north = 120.99, 14.58, 121.13, 14.70
            bbox = box(west, south, east, north)
            gdf = gpd.GeoDataFrame({'geometry': [bbox]}, crs="EPSG:4326")

    # Ensure EPSG:4326
    gdf = gdf.to_crs("EPSG:4326")
    
    # Export 1: Original
    # Ensure it's a FeatureCollection
    gdf.to_file("district1_boundary.geojson", driver='GeoJSON')
    
    # Export 2: Simplified for clipping
    gdf_strict = gdf.copy()
    gdf_strict['geometry'] = gdf_strict.geometry.simplify(tolerance=0.0001, preserve_topology=True)
    gdf_strict.to_file("district1_boundary_strict.geojson", driver='GeoJSON')
    
    # Metrics
    geom = gdf.geometry.iloc[0]
    # Area in km2 (approx for EPSG:4326, better to use projected)
    # Re-project to UTM 51N (Philippines) for accurate area
    gdf_utm = gdf.to_crs(epsg=32651) 
    area_km2 = gdf_utm.area.sum() / 1_000_000

    print("-" * 30)
    print(f"Boundary type: {type(geom).__name__}")
    print(f"Bounds: {gdf.total_bounds}")
    print(f"Area: {area_km2:.2f} km²")
    print("Files saved successfully:")
    print(" - district1_boundary.geojson")
    print(" - district1_boundary_strict.geojson")
    print("-" * 30)

if __name__ == "__main__":
    download_boundary()
