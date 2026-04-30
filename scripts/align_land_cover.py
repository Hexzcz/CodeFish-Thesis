import rasterio
from rasterio.warp import reproject, Resampling
import numpy as np
import os

# Paths
reference_raster_path = r'rasters_COP30/output_hh.tif'
worldcover_raster_path = r'ESA_WorldCover_10m_2021_v200_N12E120_Map/ESA_WorldCover_10m_2021_v200_N12E120_Map.tif'
output_raster_path = r'land_cover_aligned.tif'

print(f"Reading reference grid from: {reference_raster_path}")
with rasterio.open(reference_raster_path) as ref:
    ref_profile = ref.profile
    ref_transform = ref.transform
    ref_width = ref.width
    ref_height = ref.height
    ref_crs = ref.crs

# Prepare the output profile
out_profile = ref_profile.copy()
out_profile.update({
    'dtype': 'uint8',
    'nodata': 0,
    'count': 1,
    'driver': 'GTiff'
})

print(f"Opening WorldCover raster: {worldcover_raster_path}")
with rasterio.open(worldcover_raster_path) as src:
    # Initialize the output array
    out_data = np.zeros((ref_height, ref_width), dtype='uint8')
    
    print(f"Clipping and resampling to {ref_width}x{ref_height} using Resampling.mode...")
    # reproject handles clipping, resampling and alignment in one go 
    # when provided with destination transform, crs and shape
    reproject(
        source=rasterio.band(src, 1),
        destination=out_data,
        src_transform=src.transform,
        src_crs=src.crs,
        dst_transform=ref_transform,
        dst_crs=ref_crs,
        resampling=Resampling.mode,  # Categorical data needs mode
        dst_nodata=0
    )

print(f"Saving to {output_raster_path}...")
with rasterio.open(output_raster_path, 'w', **out_profile) as dst:
    dst.write(out_data, 1)

# Verification
unique_vals, counts = np.unique(out_data, return_counts=True)
print("\nVerification - Land Cover Classes found:")
# Known ESA WorldCover mapping:
# 10: Trees, 20: Shrubland, 30: Grassland, 40: Cropland, 50: Built-up, 60: Bare/sparse, 
# 70: Snow/ice, 80: Permanent water bodies, 90: Herbaceous wetland, 95: Mangroves, 100: Moss/lichen
land_cover_mapping = {
    10: "Trees",
    20: "Shrubland",
    30: "Grassland",
    40: "Cropland",
    50: "Built-up",
    60: "Bare / sparse vegetation",
    70: "Snow and ice",
    80: "Permanent water bodies",
    90: "Herbaceous wetland",
    95: "Mangroves",
    100: "Moss and lichen",
    0: "No Data"
}

print(f"{'Value':<10} {'Class Name':<30} {'Count':<10}")
print("-" * 50)
for val, count in zip(unique_vals, counts):
    class_name = land_cover_mapping.get(val, "Unknown")
    print(f"{val:<10} {class_name:<30} {count:<10}")

print("\nProcessing complete.")
