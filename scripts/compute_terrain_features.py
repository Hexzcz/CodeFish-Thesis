"""
Computes new terrain features from the FABDEM for Pillar 1 improvement:
- TWI (Topographic Wetness Index)
- Flow Accumulation
- Profile Curvature
- Plan Curvature
- Aspect

Steps:
  1. Reproject FABDEM from EPSG:4326 → EPSG:32651 (UTM Zone 51N) — required by whitebox
  2. Run whitebox terrain analysis tools
  3. Reproject all outputs back to EPSG:4326 to match the reference training grid
  4. Clip/resample all outputs to match the reference raster exactly
"""

import os
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import numpy as np
import whitebox

# ─── PATHS ───────────────────────────────────────────────────────────────────
FABDEM_PATH     = 'N14E121_FABDEM_V1-2.tif'
REFERENCE_PATH  = 'rasters_COP30/output_hh.tif'   # defines the target grid
WORK_DIR        = 'terrain_features'
os.makedirs(WORK_DIR, exist_ok=True)

FABDEM_UTM      = os.path.join(WORK_DIR, 'fabdem_utm.tif')
FILLED_UTM      = os.path.join(WORK_DIR, 'fabdem_utm_filled.tif')
FLOW_DIR_UTM    = os.path.join(WORK_DIR, 'flow_dir_utm.tif')
FLOW_ACC_UTM    = os.path.join(WORK_DIR, 'flow_acc_utm.tif')
SLOPE_UTM       = os.path.join(WORK_DIR, 'slope_utm.tif')
TWI_UTM         = os.path.join(WORK_DIR, 'twi_utm.tif')
ASPECT_UTM      = os.path.join(WORK_DIR, 'aspect_utm.tif')
PROFILE_CUR_UTM = os.path.join(WORK_DIR, 'profile_curvature_utm.tif')
PLAN_CUR_UTM    = os.path.join(WORK_DIR, 'plan_curvature_utm.tif')
SPI_UTM         = os.path.join(WORK_DIR, 'spi_utm.tif')
STI_UTM         = os.path.join(WORK_DIR, 'sti_utm.tif')

TARGET_CRS = 'EPSG:32651'   # WGS 84 / UTM Zone 51N (Philippines)
FINAL_CRS  = 'EPSG:4326'

# ─── STEP 1: Reproject FABDEM → UTM ──────────────────────────────────────────
print("Step 1: Reprojecting FABDEM to UTM Zone 51N...")
with rasterio.open(FABDEM_PATH) as src:
    transform, width, height = calculate_default_transform(
        src.crs, TARGET_CRS, src.width, src.height, *src.bounds
    )
    meta = src.meta.copy()
    meta.update({'crs': TARGET_CRS, 'transform': transform,
                 'width': width, 'height': height, 'nodata': -9999.0, 'dtype': 'float32'})
    with rasterio.open(FABDEM_UTM, 'w', **meta) as dst:
        reproject(source=rasterio.band(src, 1), destination=rasterio.band(dst, 1),
                  src_transform=src.transform, src_crs=src.crs,
                  dst_transform=transform, dst_crs=TARGET_CRS,
                  resampling=Resampling.bilinear)
print(f"  Saved: {FABDEM_UTM}")

# ─── STEP 2: Run WhiteboxTools ────────────────────────────────────────────────
print("\nStep 2: Running WhiteboxTools terrain analysis...")
wbt = whitebox.WhiteboxTools()
wbt.set_verbose_mode(False)
wbt.set_working_dir(os.path.abspath(WORK_DIR))

fabdem_utm_name     = 'fabdem_utm.tif'
filled_utm_name     = 'fabdem_utm_filled.tif'
flow_dir_utm_name   = 'flow_dir_utm.tif'
flow_acc_utm_name   = 'flow_acc_utm.tif'
slope_utm_name      = 'slope_utm.tif'
twi_utm_name        = 'twi_utm.tif'
aspect_utm_name     = 'aspect_utm.tif'
profile_cur_name    = 'profile_curvature_utm.tif'
plan_cur_name       = 'plan_curvature_utm.tif'
spi_utm_name        = 'spi_utm.tif'
sti_utm_name        = 'sti_utm.tif'

# 2a. Fill depressions (required before flow analysis)
print("  Filling depressions...")
wbt.fill_depressions(dem=fabdem_utm_name, output=filled_utm_name)

# 2b. Flow direction (D8)
print("  Computing D8 flow direction...")
wbt.d8_pointer(dem=filled_utm_name, output=flow_dir_utm_name)

# 2c. Flow accumulation
print("  Computing flow accumulation...")
wbt.d8_flow_accumulation(i=flow_dir_utm_name, output=flow_acc_utm_name, out_type='cells', pntr=True)

# 2d. Slope (degrees, used for TWI)
print("  Computing slope...")
wbt.slope(dem=filled_utm_name, output=slope_utm_name, units='degrees')

# 2e. TWI
print("  Computing TWI...")
wbt.wetness_index(sca=flow_acc_utm_name, slope=slope_utm_name, output=twi_utm_name)

# 2f. Aspect
print("  Computing aspect...")
wbt.aspect(dem=filled_utm_name, output=aspect_utm_name)

# 2g. Profile curvature
print("  Computing profile curvature...")
wbt.profile_curvature(dem=filled_utm_name, output=profile_cur_name)

# 2h. Plan curvature
print("  Computing plan curvature...")
wbt.plan_curvature(dem=filled_utm_name, output=plan_cur_name)

# 2i. Stream Power Index (SPI)
print("  Computing Stream Power Index (SPI)...")
wbt.stream_power_index(sca=flow_acc_utm_name, slope=slope_utm_name, output=spi_utm_name)

# 2j. Sediment Transport Index (STI)
print("  Computing Sediment Transport Index (STI)...")
wbt.sediment_transport_index(sca=flow_acc_utm_name, slope=slope_utm_name, output=sti_utm_name)

print("  WhiteboxTools analysis complete.")

# ─── STEP 3: Reproject & align all outputs to reference grid ─────────────────
print("\nStep 3: Reprojecting and aligning all outputs to reference grid...")

with rasterio.open(REFERENCE_PATH) as ref:
    ref_transform = ref.transform
    ref_crs       = ref.crs
    ref_width     = ref.width
    ref_height    = ref.height
    ref_bounds    = ref.bounds

feature_files = {
    'twi':               (TWI_UTM,         'terrain_features/twi_aligned.tif'),
    'flow_accumulation': (FLOW_ACC_UTM,    'terrain_features/flow_acc_aligned.tif'),
    'aspect':            (ASPECT_UTM,      'terrain_features/aspect_aligned.tif'),
    'profile_curvature': (PROFILE_CUR_UTM, 'terrain_features/profile_curvature_aligned.tif'),
    'plan_curvature':    (PLAN_CUR_UTM,    'terrain_features/plan_curvature_aligned.tif'),
    'spi':               (SPI_UTM,         'terrain_features/spi_aligned.tif'),
    'sti':               (STI_UTM,         'terrain_features/sti_aligned.tif'),
}

for name, (src_path, dst_path) in feature_files.items():
    print(f"  Aligning: {name} ...")
    with rasterio.open(src_path) as src:
        meta = src.meta.copy()
        meta.update({
            'crs':       ref_crs,
            'transform': ref_transform,
            'width':     ref_width,
            'height':    ref_height,
            'nodata':    -9999.0,
            'dtype':     'float32'
        })
        with rasterio.open(dst_path, 'w', **meta) as dst:
            reproject(
                source=rasterio.band(src, 1),
                destination=rasterio.band(dst, 1),
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=ref_transform,
                dst_crs=ref_crs,
                resampling=Resampling.bilinear
            )
    print(f"    Saved: {dst_path}")

print("\nAll terrain features computed and aligned!")
print("Outputs ready in terrain_features/:")
for name, (_, dst) in feature_files.items():
    print(f"  {dst}")
