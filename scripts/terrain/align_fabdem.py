import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import numpy as np

def align_raster(src_path, ref_path, dst_path):
    with rasterio.open(ref_path) as ref:
        ref_meta = ref.meta.copy()
        ref_transform = ref.transform
        ref_crs = ref.crs
        ref_width = ref.width
        ref_height = ref.height

    with rasterio.open(src_path) as src:
        # We want to reproject src to match ref exactly
        dst_meta = src.meta.copy()
        dst_meta.update({
            'crs': ref_crs,
            'transform': ref_transform,
            'width': ref_width,
            'height': ref_height,
            'nodata': -9999
        })

        with rasterio.open(dst_path, 'w', **dst_meta) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=ref_transform,
                    dst_crs=ref_crs,
                    resampling=Resampling.bilinear
                )
    print(f"Aligned {src_path} to match {ref_path}. Saved to {dst_path}")

if __name__ == "__main__":
    src = 'N14E121_FABDEM_V1-2.tif'
    ref = 'rasters_COP30/output_hh.tif'
    dst = 'fabdem_aligned.tif'
    align_raster(src, ref, dst)
