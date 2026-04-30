import math
import numpy as np
import io
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw
from shapely.geometry import box
import geopandas as gpd
import os
from backend.core.config import GEOJSON_PATHS, FLOOD_COLORMAP

STRICT_BOUNDARY_GEOM = None
if os.path.exists(GEOJSON_PATHS['boundary_strict']):
    try:
        _bdf = gpd.read_file(GEOJSON_PATHS['boundary_strict'])
        if not _bdf.empty:
            STRICT_BOUNDARY_GEOM = _bdf.geometry.union_all() if hasattr(_bdf.geometry, 'union_all') else _bdf.geometry.unary_union
    except Exception as _e:
        print(f"Error loading boundary for clipping: {_e}")

def tile_bounds_wgs84(tx, ty, tz):
    n = 2 ** tz
    west  =  tx / n * 360.0 - 180.0
    east  = (tx + 1) / n * 360.0 - 180.0
    north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * ty / n))))
    south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (ty + 1) / n))))
    return west, south, east, north

def build_clip_mask(tx, ty, tz, size=256):
    if STRICT_BOUNDARY_GEOM is None:
        return np.ones((size, size), dtype=bool)
    west, south, east, north = tile_bounds_wgs84(tx, ty, tz)
    tile_box = box(west, south, east, north)
    clipped = STRICT_BOUNDARY_GEOM.intersection(tile_box)
    if clipped.is_empty:
        return np.zeros((size, size), dtype=bool)

    tile_w = east - west
    tile_h = north - south

    def geo_to_pix(lon, lat):
        return (lon - west) / tile_w * size, (north - lat) / tile_h * size

    img_mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(img_mask)

    def draw_poly(poly):
        coords = [geo_to_pix(lon, lat) for lon, lat in poly.exterior.coords]
        if len(coords) >= 3:
            draw.polygon(coords, fill=255)
        for interior in poly.interiors:
            coords = [geo_to_pix(lon, lat) for lon, lat in interior.coords]
            if len(coords) >= 3:
                draw.polygon(coords, fill=0)

    if clipped.geom_type == "Polygon":
        draw_poly(clipped)
    elif clipped.geom_type in ("MultiPolygon", "GeometryCollection"):
        for g in clipped.geoms:
            if g.geom_type == "Polygon":
                draw_poly(g)

    return np.array(img_mask) > 0

def get_transparent_tile():
    buf = io.BytesIO()
    Image.fromarray(np.zeros((256, 256, 4), dtype=np.uint8)).save(buf, format="PNG")
    return buf.getvalue()

def render_flood(data, valid):
    rgba = np.zeros((256, 256, 4), dtype=np.uint8)
    for val, color in FLOOD_COLORMAP.items():
        idx = (data == val) & valid
        rgba[idx] = color
    buf = io.BytesIO()
    Image.fromarray(rgba).save(buf, format="PNG")
    return buf.getvalue()

def render_continuous(data, valid, cmap_name):
    if not np.any(valid):
        return get_transparent_tile()
    fdata = data.astype(float)
    vmin, vmax = float(fdata[valid].min()), float(fdata[valid].max())
    normed = np.zeros_like(fdata)
    if vmax > vmin:
        normed[valid] = (fdata[valid] - vmin) / (vmax - vmin)
    cmap = plt.get_cmap(cmap_name)
    rgba = (cmap(normed) * 255).astype(np.uint8)
    rgba[~valid] = 0
    buf = io.BytesIO()
    Image.fromarray(rgba).save(buf, format="PNG")
    return buf.getvalue()
