import geopandas as gpd
import rasterio
from rasterio.features import rasterize
import numpy as np
import os
import glob

# Configuration
reference_raster_path = r'rasters_COP30/output_hh.tif'
# This pattern finds all flood hazard folders (5yr, 25yr, 100yr)
input_folders = glob.glob('ph137404000_fh*')

print(f"Reading reference raster: {reference_raster_path}")
with rasterio.open(reference_raster_path) as ref:
    transform = ref.transform
    width = ref.width
    height = ref.height
    crs = ref.crs
    profile = ref.profile.copy()

# Update profile for output
profile.update(
    dtype='uint8',
    count=1,
    nodata=255,
    width=width,
    height=height,
    crs=crs,
    transform=transform,
    driver='GTiff'
)

for folder in input_folders:
    # Find the .shp file inside the folder
    shp_files = glob.glob(os.path.join(folder, '*.shp'))
    if not shp_files:
        continue
        
    shapefile_path = shp_files[0]
    # Create a unique output name based on the folder name
    # e.g., ph137404000_fh5yr_30m_10m -> flood_hazard_fh5yr_aligned.tif
    parts = os.path.basename(folder).split('_')
    tag = parts[1] if len(parts) > 1 else "hazard"
    output_raster_path = f'flood_hazard_{tag}_aligned.tif'

    print(f"\n--- Processing: {folder} ---")
    print(f"Reading shapefile: {shapefile_path}")
    gdf = gpd.read_file(shapefile_path)
    
    print("Filtering hazard levels (1, 2, 3)...")
    gdf = gdf[gdf['Var'].isin([1, 2, 3])]

    if gdf.crs != crs:
        print(f"Reprojecting from {gdf.crs} to {crs}...")
        gdf = gdf.to_crs(crs)

    # Extract (geometry, value) pairs
    shapes = ((geom, value) for geom, value in zip(gdf.geometry, gdf['Var']))

    print("Rasterizing...")
    burned = rasterize(
        shapes=shapes,
        out_shape=(height, width),
        fill=0,
        transform=transform,
        all_touched=True,
        dtype='uint8'
    )

    print(f"Saving to {output_raster_path}")
    with rasterio.open(output_raster_path, 'w', **profile) as dst:
        dst.write(burned, 1)

    print(f"Verification - Min: {burned.min()}, Max: {burned.max()}, Unique: {np.unique(burned)}")

print("\nBatch processing complete.")
