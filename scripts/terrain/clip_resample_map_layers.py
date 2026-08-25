from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.warp import Resampling, reproject
from scipy.ndimage import distance_transform_edt


ROOT = Path(__file__).resolve().parent.parent
RASTERS_DIR = ROOT / "backend" / "data" / "rasters"
BOUNDARY_PATH = ROOT / "backend" / "data" / "geojson" / "district1_boundary_strict.geojson"
REFERENCE_RASTER = RASTERS_DIR / "flood_hazard_fh25yr_aligned.tif"

SOURCES = {
    "elevation": ROOT / "terrain_features" / "fabdem_utm_filled.tif",
    "elevation_fallback": ROOT / "rasters_COP30" / "output_hh.tif",
    "slope": ROOT / "terrain_features" / "slope_utm.tif",
    "slope_fallback": ROOT / "viz" / "viz.hh_slope.tif",
    "land_cover": ROOT / "ESA_WorldCover_10m_2021_v200_N12E120_Map" / "ESA_WorldCover_10m_2021_v200_N12E120_Map.tif",
    "waterways": ROOT / "hotosm_phl_waterways_lines_shp" / "hotosm_phl_waterways_lines_shp.shp",
}

OUTPUTS = {
    "elevation": RASTERS_DIR / "output_hh.tif",
    "slope": RASTERS_DIR / "viz.hh_slope.tif",
    "land_cover": RASTERS_DIR / "land_cover_aligned.tif",
    "dist_waterway": RASTERS_DIR / "distance_to_waterways.tif",
}


def read_reference_grid():
    with rasterio.open(REFERENCE_RASTER) as ref:
        profile = ref.profile.copy()
        transform = ref.transform
        crs = ref.crs
        shape = (ref.height, ref.width)
        bounds = ref.bounds
        resolution = ref.res
    return profile, transform, crs, shape, bounds, resolution


def build_boundary_mask(transform, crs, shape):
    boundary = gpd.read_file(BOUNDARY_PATH).to_crs(crs)
    geom = boundary.geometry.union_all() if hasattr(boundary.geometry, "union_all") else boundary.geometry.unary_union
    mask = rasterize(
        [(geom, 1)],
        out_shape=shape,
        transform=transform,
        fill=0,
        all_touched=True,
        dtype="uint8",
    ).astype(bool)
    return mask, geom


def write_raster(path, data, profile, dtype, nodata):
    out_profile = profile.copy()
    out_profile.update(
        dtype=dtype,
        count=1,
        nodata=nodata,
        compress="lzw",
        tiled=True,
        blockxsize=256,
        blockysize=256,
    )
    with rasterio.open(path, "w", **out_profile) as dst:
        dst.write(data.astype(dtype), 1)


def resample_raster(source_path, transform, crs, shape, dtype, nodata, resampling):
    destination = np.full(shape, nodata, dtype=np.dtype(dtype))
    with rasterio.open(source_path) as src:
        reproject(
            source=rasterio.band(src, 1),
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=src.nodata,
            dst_transform=transform,
            dst_crs=crs,
            dst_nodata=nodata,
            resampling=resampling,
        )
    return destination


def valid_mask(data, nodata):
    if np.issubdtype(data.dtype, np.floating):
        valid = ~np.isnan(data)
    else:
        valid = np.ones(data.shape, dtype=bool)
    if nodata is not None:
        valid &= data != nodata
    return valid


def composite_rasters(primary_path, fallback_path, transform, crs, shape, mask, dtype, nodata, resampling):
    primary = resample_raster(primary_path, transform, crs, shape, dtype, nodata, resampling)
    combined = primary.copy()
    primary_valid = valid_mask(primary, nodata) & mask

    if fallback_path is not None and Path(fallback_path).exists():
        fallback = resample_raster(fallback_path, transform, crs, shape, dtype, nodata, resampling)
        fallback_valid = valid_mask(fallback, nodata) & mask
        fill_mask = (~primary_valid) & fallback_valid
        combined[fill_mask] = fallback[fill_mask]
        print(f"Filled {int(fill_mask.sum())} pixels in {Path(primary_path).name} from {Path(fallback_path).name}")

    combined[~mask] = nodata
    return combined


def fill_boundary_gaps(data, mask, nodata):
    valid = valid_mask(data, nodata) & mask
    missing = mask & ~valid
    if not missing.any() or not valid.any():
        return data

    nearest_index = distance_transform_edt(~valid, return_distances=False, return_indices=True)
    filled = data.copy()
    filled[missing] = filled[tuple(nearest_index[:, missing])]
    print(f"Filled {int(missing.sum())} remaining interior gaps by nearest-neighbor propagation")
    return filled


def build_distance_to_waterways(profile, transform, crs, shape, mask):
    waterways = gpd.read_file(SOURCES["waterways"]).to_crs(crs)
    binary = rasterize(
        ((geom, 1) for geom in waterways.geometry if geom is not None and not geom.is_empty),
        out_shape=shape,
        transform=transform,
        fill=0,
        all_touched=True,
        dtype="uint8",
    )
    pixel_distance = distance_transform_edt(binary == 0)
    distance_meters = (pixel_distance * abs(transform.a)).astype("float32")
    distance_meters[~mask] = -9999.0
    return distance_meters


def summarize(path):
    with rasterio.open(path) as src:
        data = src.read(1)
        valid = data if src.nodata is None else data[data != src.nodata]
        if valid.size:
            summary = f"min={float(np.nanmin(valid)):.3f}, max={float(np.nanmax(valid)):.3f}"
        else:
            summary = "no valid pixels"
        print(
            f"{path.name}: crs={src.crs}, res={src.res}, "
            f"shape={(src.width, src.height)}, nodata={src.nodata}, {summary}"
        )


def main():
    profile, transform, crs, shape, bounds, resolution = read_reference_grid()
    mask, _ = build_boundary_mask(transform, crs, shape)

    print(f"Reference: {REFERENCE_RASTER}")
    print(f"Grid: {shape[1]} x {shape[0]} pixels at {resolution[0]} m, CRS {crs}")
    print(f"Bounds: {tuple(round(v, 3) for v in bounds)}")
    print(f"Boundary valid pixels: {int(mask.sum())}")

    elevation = composite_rasters(
        SOURCES["elevation"], SOURCES["elevation_fallback"], transform, crs, shape, mask,
        "float32", -9999.0, Resampling.bilinear
    )
    elevation = fill_boundary_gaps(elevation, mask, -9999.0)
    write_raster(OUTPUTS["elevation"], elevation, profile, "float32", -9999.0)
    summarize(OUTPUTS["elevation"])

    slope = composite_rasters(
        SOURCES["slope"], SOURCES["slope_fallback"], transform, crs, shape, mask,
        "float32", -9999.0, Resampling.bilinear
    )
    slope = fill_boundary_gaps(slope, mask, -9999.0)
    write_raster(OUTPUTS["slope"], slope, profile, "float32", -9999.0)
    summarize(OUTPUTS["slope"])

    land_cover = resample_raster(
        SOURCES["land_cover"], transform, crs, shape,
        "uint8", 0, Resampling.mode
    )
    land_cover[~mask] = 0
    write_raster(OUTPUTS["land_cover"], land_cover, profile, "uint8", 0)
    summarize(OUTPUTS["land_cover"])

    distance = build_distance_to_waterways(profile, transform, crs, shape, mask)
    write_raster(OUTPUTS["dist_waterway"], distance, profile, "float32", -9999.0)
    summarize(OUTPUTS["dist_waterway"])


if __name__ == "__main__":
    main()
