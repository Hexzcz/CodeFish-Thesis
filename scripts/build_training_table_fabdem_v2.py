import rasterio
import numpy as np
import pandas as pd
import argparse
import os

def main():
    parser = argparse.ArgumentParser(description="Build master training table from rasters (FABDEM + new terrain features).")
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
    spi_path          = r'terrain_features/spi_aligned.tif'
    sti_path          = r'terrain_features/sti_aligned.tif'

    print(f"Input label file: {args.label_file}")

    def read_raster(path):
        with rasterio.open(path) as src:
            nodata = src.nodata
            data = src.read(1).astype(np.float32).flatten()
            if nodata is not None:
                data[data == nodata] = np.nan
            return data

    # 1. Read and flatten all rasters
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
    spi           = read_raster(spi_path)
    sti           = read_raster(sti_path)
    flood_class   = read_raster(args.label_file)

    print(f"Total pixels before cleaning: {len(elevation)}")

    # 2. Stack into a DataFrame
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
        'spi':              spi,
        'sti':              sti,
        'flood_class':      flood_class
    })

    # 3. Remove nodata values — drop any row with NaN or sentinel nodata
    # Also keep original hard-coded nodata checks for older rasters
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
        df['plan_curvature'].notna() &
        df['spi'].notna() &
        df['sti'].notna()
    )
    df_clean = df[mask].reset_index(drop=True)
    
    print(f"Total pixels after nodata removal: {len(df_clean)}")

    # 4. Class balance check
    counts_before = df_clean['flood_class'].value_counts().sort_index()
    print("\nClass distribution before undersampling:")
    print(counts_before)

    flooded_count = df_clean[df_clean['flood_class'].isin([1, 2, 3])].shape[0]
    df_not_flooded = df_clean[df_clean['flood_class'] == 0]
    df_flooded = df_clean[df_clean['flood_class'].isin([1, 2, 3])]

    if len(df_not_flooded) > flooded_count:
        df_not_flooded_sampled = df_not_flooded.sample(n=flooded_count, random_state=42)
    else:
        df_not_flooded_sampled = df_not_flooded

    df_final = pd.concat([df_not_flooded_sampled, df_flooded]).sample(frac=1, random_state=42).reset_index(drop=True)

    counts_after = df_final['flood_class'].value_counts().sort_index()
    print("\nClass distribution after undersampling:")
    print(counts_after)
    print(f"\nFinal table shape: {df_final.shape}")

    df_final.to_csv(args.output_csv, index=False)
    print(f"Saved to {args.output_csv}")

if __name__ == "__main__":
    main()
