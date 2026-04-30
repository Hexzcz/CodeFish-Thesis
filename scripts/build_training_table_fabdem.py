import rasterio
import numpy as np
import pandas as pd
import argparse
import os

def main():
    parser = argparse.ArgumentParser(description="Build master training table from rasters.")
    parser.add_argument("--label_file", required=True, help="Path to the flood hazard raster (Y label).")
    parser.add_argument("--output_csv", required=True, help="Output CSV filename.")
    args = parser.parse_args()

    # Note: Using the FABDEM aligned raster
    elevation_path = r'fabdem_aligned.tif'
    slope_path = r'viz/viz.hh_slope.tif'
    land_cover_path = r'backend/data/rasters/land_cover_aligned.tif'
    dist_waterway_path = r'backend/data/rasters/distance_to_waterways.tif'

    print(f"Input label file: {args.label_file}")

    def read_raster(path):
        with rasterio.open(path) as src:
            return src.read(1).flatten()

    # 1. Read and flatten all rasters
    print("Reading and flattening rasters...")
    elevation = read_raster(elevation_path)
    slope = read_raster(slope_path)
    land_cover = read_raster(land_cover_path)
    dist_waterway = read_raster(dist_waterway_path)
    flood_class = read_raster(args.label_file)

    total_pixels_before = len(elevation)
    print(f"Total pixels before cleaning: {total_pixels_before}")

    # 2. Stack into a DataFrame
    df = pd.DataFrame({
        'elevation': elevation,
        'slope': slope,
        'land_cover': land_cover,
        'dist_waterway': dist_waterway,
        'flood_class': flood_class
    })

    # 3. Remove nodata values
    mask = (
        (df['elevation'] > -9999) &
        (df['slope'] > -9999) &
        (df['land_cover'] != 0) &
        (df['dist_waterway'] > -9999) &
        (df['flood_class'] != 255)
    )
    df_clean = df[mask].reset_index(drop=True)
    
    total_pixels_after = len(df_clean)
    print(f"Total pixels after nodata removal: {total_pixels_after}")

    # 4. Class balance and Undersampling
    counts_before = df_clean['flood_class'].value_counts().sort_index()
    print("\nClass distribution before undersampling:")
    print(counts_before)

    flooded_count = df_clean[df_clean['flood_class'].isin([1, 2, 3])].shape[0]
    
    df_not_flooded = df_clean[df_clean['flood_class'] == 0]
    df_flooded = df_clean[df_clean['flood_class'].isin([1, 2, 3])]

    # Downsample class 0 to match flooded_count
    if len(df_not_flooded) > flooded_count:
        df_not_flooded_sampled = df_not_flooded.sample(n=flooded_count, random_state=42)
    else:
        df_not_flooded_sampled = df_not_flooded

    # Combine
    df_final = pd.concat([df_not_flooded_sampled, df_flooded]).sample(frac=1, random_state=42).reset_index(drop=True)

    counts_after = df_final['flood_class'].value_counts().sort_index()
    print("\nClass distribution after undersampling:")
    print(counts_after)

    print(f"\nFinal table shape: {df_final.shape}")

    # 5. Save and Verify
    df_final.to_csv(args.output_csv, index=False)
    print(f"Saved to {args.output_csv}")

if __name__ == "__main__":
    main()
