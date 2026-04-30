import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from scipy.ndimage import distance_transform_edt
import numpy as np
import os

# Paths
shapefile_path = r'hotosm_phl_waterways_lines_shp/hotosm_phl_waterways_lines_shp.shp'
reference_raster_path = r'rasters_COP30/output_hh.tif'
output_raster_path = r'distance_to_waterways.tif'

# 1. Read reference raster metadata
print(f"Reading reference raster: {reference_raster_path}")
with rasterio.open(reference_raster_path) as ref:
    transform = ref.transform
    width = ref.width
    height = ref.height
    crs = ref.crs
    profile = ref.profile.copy()

# 2. Read and reproject shapefile
print(f"Reading shapefile: {shapefile_path}")
gdf = gpd.read_file(shapefile_path)

if gdf.crs != crs:
    print(f"Reprojecting vector from {gdf.crs} to {crs}")
    gdf = gdf.to_crs(crs)

# 3. Rasterize lines (1 = waterway, 0 = non-waterway)
print("Rasterizing waterway lines...")
# Create a binary mask of waterways
# We burn '1' onto a '0' background
binary_mask = rasterize(
    shapes=((geom, 1) for geom in gdf.geometry),
    out_shape=(height, width),
    transform=transform,
    all_touched=True,
    fill=0,
    dtype='uint8'
)

# 4. Compute Distance Transform
# distance_transform_edt computes distance to the nearest zero-valued pixel.
# To compute distance to lines (value 1), we invert the mask so lines are 0.
print("Computing Euclidean distance transform...")
inverted_mask = (binary_mask == 0).astype(np.uint8)
pixel_distances = distance_transform_edt(inverted_mask)

# 5. Convert to meters
# Requirement: ~30.9m per pixel
CELL_SIZE_METERS = 30.9
print(f"Converting pixel distance to meters (factor: {CELL_SIZE_METERS})")
distance_meters = (pixel_distances * CELL_SIZE_METERS).astype(np.float32)

# 6. Prepare Profile and Save
nodata_value = -9999
profile.update(
    dtype='float32',
    count=1,
    nodata=nodata_value,
    width=width,
    height=height,
    crs=crs,
    transform=transform,
    driver='GTiff'
)

print(f"Saving to {output_raster_path}")
with rasterio.open(output_raster_path, 'w', **profile) as dst:
    dst.write(distance_meters, 1)

# 7. Verification
print("\nVerification:")
print(f"Min distance: {distance_meters.min():.2f}m")
print(f"Max distance: {distance_meters.max():.2f}m")
print(f"Mean distance: {distance_meters.mean():.2f}m")
