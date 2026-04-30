import rasterio
import numpy as np
import pandas as pd
import argparse
import os

def main():
    parser = argparse.ArgumentParser(description="Build master training table (All Features, No Undersampling)")
    parser.add_argument("--label_file", required=True, help="Path to the flood hazard raster (Y label).")
    parser.add_argument("--output_csv", required=True, help="Output CSV filename.")
    args = parser.parse_args()

    # Original features
    elevation_path    = r'fabdem_aligned.tif'
    slope_path        = r'viz/viz.hh_slope.tif'
    land_cover_path   = r'backend/data/rasters/land_cover_aligned.tif'
    dist_waterway_path= r'backend/data/rasters/distance_to_waterways.tif'

    # New Pillar 1 features
    twi_path          = r'terrain_features/twi_aligned.tif'
    flow_acc_path     = r'terrain_features/flow_acc_aligned.tif'
    aspect_path       = r'terrain_features/aspect_aligned.tif'
    profile_cur_path  = r'terrain_features/profile_curvature_aligned.tif'
    plan_cur_path     = r'terrain_features/plan_curvature_aligned.tif'

    def read_raster(path):
        with rasterio.open(path) as src:
            nodata = src.nodata
            data = src.read(1).astype(np.float32).flatten()
            if nodata is not None:
                data[data == nodata] = np.nan
            return data

    print("Reading and flattening rasters...")
    elevation     = read_raster(elevation_path)
    slope         = read_raster(slope_path)
    land_cover    = read_raster(land_cover_path)
    dist_waterway = read_raster(dist_waterway_path)
    twi           = read_raster(twi_path)
    flow_acc      = read_raster(flow_acc_path)
    aspect        = read_raster(aspect_path)
    profile_cur   = read_raster(profile_cur_path)
    plan_cur      = read_raster(plan_cur_path)
    flood_class   = read_raster(args.label_file)

    df = pd.DataFrame({
        'elevation':        elevation,
        'slope':            slope,
        'land_cover':       land_cover,
        'dist_waterway':    dist_waterway,
        'twi':              twi,
        'flow_accumulation':flow_acc,
        'aspect':           aspect,
        'profile_curvature':profile_cur,
        'plan_curvature':   plan_cur,
        'flood_class':      flood_class
    })

    # Clean nodata values
    mask = (
        (df['elevation'] > -9999) &
        (df['slope'] > -9999) &
        (df['land_cover'] != 0) &
        (df['dist_waterway'] > -9999) &
        (df['flood_class'] != 255) &
        df['twi'].notna() &
        df['flow_accumulation'].notna() &
        df['aspect'].notna() &
        df['profile_curvature'].notna() &
        df['plan_curvature'].notna()
    )
    df_clean = df[mask].reset_index(drop=True)
    
    print(f"Total valid pixels: {len(df_clean)}")
    print("\nClass distribution (Fully Imbalanced):")
    print(df_clean['flood_class'].value_counts().sort_index())

    # We do NOT undersample anymore. The training script will handle SMOTE.
    df_clean.to_csv(args.output_csv, index=False)
    print(f"Saved FULL imbalanced dataset to {args.output_csv}")

if __name__ == "__main__":
    main()
