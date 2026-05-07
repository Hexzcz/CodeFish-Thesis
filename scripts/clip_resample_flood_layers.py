from pathlib import Path
import math

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin


ROOT = Path(__file__).resolve().parent.parent
BOUNDARY_PATH = ROOT / "backend" / "data" / "geojson" / "district1_boundary_strict.geojson"
OUTPUT_DIR = ROOT / "backend" / "data" / "rasters"
TARGET_RESOLUTION_M = 30
NODATA = 255

FLOOD_SOURCES = {
    "fh5yr": ROOT / "ph137404000_fh5yr_30m_10m" / "ph137404000_fh5yr_30m_10m.shp",
    "fh25yr": ROOT / "ph137404000_fh25yr_30m_10m" / "ph137404000_fh25yr_30m_10m.shp",
    "fh100yr": ROOT / "ph137404000_fh100yr_30m_10m" / "ph137404000_fh100yr_30m_10m.shp",
}


def snapped_grid(bounds, resolution):
    minx, miny, maxx, maxy = bounds
    west = math.floor(minx / resolution) * resolution
    south = math.floor(miny / resolution) * resolution
    east = math.ceil(maxx / resolution) * resolution
    north = math.ceil(maxy / resolution) * resolution
    width = int(round((east - west) / resolution))
    height = int(round((north - south) / resolution))
    return west, south, east, north, width, height


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    first_source = next(iter(FLOOD_SOURCES.values()))
    source_crs = gpd.read_file(first_source, rows=1).crs

    boundary = gpd.read_file(BOUNDARY_PATH).to_crs(source_crs)
    boundary_geom = boundary.geometry.union_all() if hasattr(boundary.geometry, "union_all") else boundary.geometry.unary_union

    west, south, east, north, width, height = snapped_grid(boundary.total_bounds, TARGET_RESOLUTION_M)
    transform = from_origin(west, north, TARGET_RESOLUTION_M, TARGET_RESOLUTION_M)
    out_shape = (height, width)

    boundary_mask = rasterize(
        [(boundary_geom, 1)],
        out_shape=out_shape,
        transform=transform,
        fill=0,
        all_touched=True,
        dtype="uint8",
    ).astype(bool)

    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "uint8",
        "crs": source_crs,
        "transform": transform,
        "nodata": NODATA,
        "compress": "lzw",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }

    print(f"Boundary: {BOUNDARY_PATH}")
    print(f"Target CRS: {source_crs}")
    print(f"Target grid: {width} x {height} pixels at {TARGET_RESOLUTION_M} m")
    print(f"Target bounds: {(west, south, east, north)}")

    for tag, source_path in FLOOD_SOURCES.items():
        print(f"\nProcessing {tag}: {source_path}")
        hazards = gpd.read_file(source_path)
        if hazards.crs != source_crs:
            hazards = hazards.to_crs(source_crs)

        hazards = hazards[hazards["Var"].isin([1, 2, 3])].copy()
        hazards["geometry"] = hazards.geometry.intersection(boundary_geom)
        hazards = hazards[~hazards.geometry.is_empty & hazards.geometry.notna()]

        shapes = ((geom, int(value)) for geom, value in zip(hazards.geometry, hazards["Var"]))
        burned = rasterize(
            shapes,
            out_shape=out_shape,
            transform=transform,
            fill=0,
            all_touched=True,
            dtype="uint8",
        )
        burned[~boundary_mask] = NODATA

        output_path = OUTPUT_DIR / f"flood_hazard_{tag}_aligned.tif"
        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(burned, 1)

        valid = burned[burned != NODATA]
        unique, counts = np.unique(valid, return_counts=True)
        summary = {int(v): int(c) for v, c in zip(unique, counts)}
        print(f"Wrote {output_path}")
        print(f"Valid class counts: {summary}")


if __name__ == "__main__":
    main()
