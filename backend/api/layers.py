import os
import numpy as np
from fastapi import APIRouter, Response, Query, HTTPException, Request, Depends
from rio_tiler.io import Reader
from rio_tiler.errors import TileOutsideBounds
from backend.adapters.tile_renderer import render_flood, render_continuous, render_terrain_rgb, build_clip_mask, get_transparent_tile
from backend.core.config import LAYERS_MAP, SCENARIOS, TERRAIN_RASTER

from backend.api.dependencies import get_app_state

from backend.core.logging import get_logger

log = get_logger(__name__)

router = APIRouter()

@router.get("/tiles/terrain-rgb/{z}/{x}/{y}.png")
async def get_terrain_tile(z: int, x: int, y: int):
    """Elevation as Terrain-RGB, for the 3D view to drape the map over.

    Unclipped on purpose: terrain cut off at the district boundary would leave
    a wall around it. Outside the DEM the tile is flat sea level.
    """
    if not os.path.exists(TERRAIN_RASTER):
        return Response(content=get_transparent_tile(), media_type="image/png")

    try:
        with Reader(str(TERRAIN_RASTER)) as src:
            try:
                img = src.tile(x, y, z, tilesize=256, nodata=-9999.0)
            except TileOutsideBounds:
                return Response(content=get_transparent_tile(), media_type="image/png")

        raw_mask = img.mask
        valid = (raw_mask == 255) if raw_mask.dtype == np.uint8 else (raw_mask > 0)
        content = render_terrain_rgb(img.data[0], valid)
        return Response(content=content, media_type="image/png",
                        headers={"Cache-Control": "public, max-age=86400"})
    except Exception as e:
        log.warning(f"Terrain tile error {z}/{x}/{y}: {e}")
        return Response(content=get_transparent_tile(), media_type="image/png")


@router.get("/tiles/{layer_name}/{z}/{x}/{y}.png")
async def get_tile(layer_name: str, z: int, x: int, y: int, clip: bool = Query(True)):
    info = LAYERS_MAP.get(layer_name)
    if not info:
        return Response(content=get_transparent_tile(), media_type="image/png")

    file_path, cmap_or_type, nodata_override = info
    if not os.path.exists(file_path):
        return Response(content=get_transparent_tile(), media_type="image/png")

    try:
        with Reader(file_path) as src:
            try:
                kwargs = {"tilesize": 256}
                if nodata_override is not None:
                    kwargs["nodata"] = nodata_override
                img = src.tile(x, y, z, **kwargs)
            except TileOutsideBounds:
                return Response(content=get_transparent_tile(), media_type="image/png")

        data = img.data[0]
        raw_mask = img.mask
        valid = (raw_mask == 255) if raw_mask.dtype == np.uint8 else (raw_mask > 0)

        if clip:
            valid = valid & build_clip_mask(x, y, z)

        if not np.any(valid):
            return Response(content=get_transparent_tile(), media_type="image/png")

        content = (
            render_flood(data, valid)
            if cmap_or_type == "flood"
            else render_continuous(data, valid, cmap_or_type)
        )
        # The rasters behind these tiles are static files; a tile for a given
        # layer and z/x/y is always the same picture. An hour is conservative.
        return Response(content=content, media_type="image/png",
                        headers={"Cache-Control": "public, max-age=3600"})

    except Exception as e:
        log.warning(f"Tile error {layer_name} {z}/{x}/{y}: {e}")
        return Response(content=get_transparent_tile(), media_type="image/png")

@router.get("/flood-segments")
async def get_flood_segments(scenario: str = Query("25yr"), state: dict = Depends(get_app_state)):
    """Return all road edges with flood predictions as GeoJSON."""
    if scenario not in SCENARIOS:
        raise HTTPException(400, f"scenario must be one of {SCENARIOS}")

    graph = state['graph']
    features = []
    seen = set()
    for (u, v), edge in graph.edges.items():
        key = (min(u, v), max(u, v))
        if key in seen:
            continue
        seen.add(key)

        coords = edge.get('geometry', [])
        if not coords:
            continue

        flood_class  = int(edge.get(f'flood_class_{scenario}', 0) or 0)
        flood_proba  = float(edge.get(f'flood_proba_{scenario}', 0.0) or 0.0)
        risk_label = 'Low' if flood_proba < 0.2 else ('Medium' if flood_proba < 0.5 else 'High')

        features.append({
            'type': 'Feature',
            'geometry': {'type': 'LineString', 'coordinates': coords},
            'properties': {
                'osmid': edge.get('osmid', ''),
                'name': edge.get('name', 'Unnamed Road'),
                'highway': edge.get('highway', 'unclassified'),
                'length': edge.get('length', 0.0),
                'flood_class': flood_class,
                'flood_proba': round(flood_proba, 4),
                'risk_label': risk_label,
            },
        })

    return {'type': 'FeatureCollection', 'features': features}
