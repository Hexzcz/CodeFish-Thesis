from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, calculate_default_transform, reproject
import whitebox


ROOT = Path(__file__).resolve().parents[1]
WORK_DIR = ROOT / "terrain_features" / "hand_work"
OUTPUT_DIR = ROOT / "terrain_features"
DEM_PATH = ROOT / "backend" / "data" / "rasters" / "output_hh.tif"
REFERENCE_PATH = DEM_PATH
TARGET_CRS = "EPSG:32651"


def reproject_dem_to_utm(dem_path: Path, output_path: Path) -> None:
    with rasterio.open(dem_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, TARGET_CRS, src.width, src.height, *src.bounds
        )
        meta = src.meta.copy()
        meta.update(
            {
                "crs": TARGET_CRS,
                "transform": transform,
                "width": width,
                "height": height,
                "nodata": -9999.0,
                "dtype": "float32",
            }
        )
        with rasterio.open(output_path, "w", **meta) as dst:
            reproject(
                source=rasterio.band(src, 1),
                destination=rasterio.band(dst, 1),
                src_transform=src.transform,
                src_crs=src.crs,
                src_nodata=src.nodata,
                dst_transform=transform,
                dst_crs=TARGET_CRS,
                dst_nodata=-9999.0,
                resampling=Resampling.bilinear,
            )


def align_to_reference(src_path: Path, dst_path: Path, reference_path: Path) -> None:
    with rasterio.open(reference_path) as ref, rasterio.open(src_path) as src:
        meta = ref.meta.copy()
        meta.update({"dtype": "float32", "nodata": -9999.0, "count": 1})
        data = np.full((ref.height, ref.width), -9999.0, dtype=np.float32)
        reproject(
            source=rasterio.band(src, 1),
            destination=data,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=src.nodata,
            dst_transform=ref.transform,
            dst_crs=ref.crs,
            dst_nodata=-9999.0,
            resampling=Resampling.bilinear,
        )
        data = np.where(np.isfinite(data), np.maximum(data, 0.0), -9999.0).astype(np.float32)
        with rasterio.open(dst_path, "w", **meta) as dst:
            dst.write(data, 1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Derive HAND using DEM filling, D8 flow accumulation, stream thresholding, and elevation above stream."
    )
    parser.add_argument("--dem", type=Path, default=DEM_PATH)
    parser.add_argument("--reference", type=Path, default=REFERENCE_PATH)
    parser.add_argument("--threshold", type=float, default=150.0, help="Flow accumulation cell threshold for drainage extraction.")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR / "hand_aligned.tif")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    dem_utm = WORK_DIR / "dem_utm.tif"
    filled_utm = WORK_DIR / "dem_utm_filled.tif"
    pointer_utm = WORK_DIR / "d8_pointer_utm.tif"
    flow_acc_utm = WORK_DIR / "flow_acc_utm.tif"
    streams_utm = WORK_DIR / f"streams_threshold_{int(args.threshold)}_utm.tif"
    hand_utm = WORK_DIR / f"hand_threshold_{int(args.threshold)}_utm.tif"

    print("Step 1: Reproject DEM to UTM Zone 51N")
    reproject_dem_to_utm(args.dem, dem_utm)

    wbt = whitebox.WhiteboxTools()
    wbt.set_verbose_mode(False)
    wbt.set_working_dir(str(WORK_DIR))

    print("Step 2: Fill depressions")
    wbt.fill_depressions(dem_utm.name, filled_utm.name)

    print("Step 3: Compute D8 flow direction")
    wbt.d8_pointer(filled_utm.name, pointer_utm.name)

    print("Step 4: Compute D8 flow accumulation")
    wbt.d8_flow_accumulation(pointer_utm.name, flow_acc_utm.name, out_type="cells", pntr=True)

    print(f"Step 5: Extract drainage network with threshold={args.threshold:g} cells")
    wbt.extract_streams(flow_acc_utm.name, streams_utm.name, args.threshold, zero_background=True)

    print("Step 6: Compute HAND as elevation above nearest drainage")
    wbt.elevation_above_stream(filled_utm.name, streams_utm.name, hand_utm.name)

    print("Step 7: Align HAND to current backend feature grid")
    align_to_reference(hand_utm, args.output, args.reference)
    print(f"Saved HAND raster: {args.output}")


if __name__ == "__main__":
    main()
