from pathlib import Path
import os

# Base directory (backend folder)
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

MODELS_DIR = DATA_DIR / "models"
GEOJSON_DIR = DATA_DIR / "geojson"
RASTERS_DIR = DATA_DIR / "rasters"

SCENARIOS = ['5yr', '25yr', '100yr']

MODEL_PATHS = {
    '5yr':   MODELS_DIR / 'model_5yr.pkl',
    '25yr':  MODELS_DIR / 'model_25yr.pkl',
    '100yr': MODELS_DIR / 'model_100yr.pkl'
}

RASTER_PATHS = {
    'elevation':     RASTERS_DIR / 'output_hh.tif',
    'slope':         RASTERS_DIR / 'viz.hh_slope.tif',
    'land_cover':    RASTERS_DIR / 'land_cover_aligned.tif',
    'dist_waterway': RASTERS_DIR / 'distance_to_waterways.tif',
}

FLOOD_RASTERS = {
    '5yr':   RASTERS_DIR / 'flood_hazard_fh5yr_aligned.tif',
    '25yr':  RASTERS_DIR / 'flood_hazard_fh25yr_aligned.tif',
    '100yr': RASTERS_DIR / 'flood_hazard_fh100yr_aligned.tif',
}

GEOJSON_PATHS = {
    'road_edges':      GEOJSON_DIR / 'road_edges.geojson',
    'road_nodes':      GEOJSON_DIR / 'road_nodes.geojson',
    'boundary':        GEOJSON_DIR / 'district1_boundary.geojson',
    'boundary_strict': GEOJSON_DIR / 'district1_boundary_strict.geojson',
    'centers':         GEOJSON_DIR / 'evacuation_centers.geojson'
}

DEFAULT_FEATURES = {
    'elevation': 20.0,
    'slope': 2.2,
    'land_cover': 50.0,
    'dist_waterway': 275.0,
}

LAYERS_MAP = {
    "flood_5yr":    (str(FLOOD_RASTERS['5yr']),   "flood",   255.0),
    "flood_25yr":   (str(FLOOD_RASTERS['25yr']),  "flood",   255.0),
    "flood_100yr":  (str(FLOOD_RASTERS['100yr']), "flood",   255.0),
    "land_cover":   (str(RASTER_PATHS['land_cover']),            "tab20",   0.0),
    "dist_waterway":(str(RASTER_PATHS['dist_waterway']),         "Blues_r", None),
    "elevation":    (str(RASTER_PATHS['elevation']),       "terrain", None),
    "slope":        (str(RASTER_PATHS['slope']),              "YlOrRd",  None),
}

FLOOD_COLORMAP = {
    1: (255, 255,   0, 180),
    2: (255, 140,   0, 180),
    3: (255,   0,   0, 180),
}
