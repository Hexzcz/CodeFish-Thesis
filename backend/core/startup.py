"""Composition root: build everything the app needs, once, at boot.

Reads left to right — network, then terrain, then models, then destinations —
and hands the result to the API as `app.state.data`. Nothing here decides
anything; the adapters fetch and the engine computes.
"""
import json

from backend.adapters.evacuation_centers import load_centers, load_centers_geojson
from backend.adapters.model_store import load_models
from backend.adapters.raster_sampler import sample_rasters
from backend.adapters.road_network import build_graph, load_road_geojson
from backend.core.config import GEOJSON_PATHS
from backend.domain.routing.connectivity import ensure_connected

from backend.core.logging import get_logger

log = get_logger(__name__)

_STEPS = 7


def _step(n: int, message: str) -> None:
    log.info(f"[{n}/{_STEPS}] {message}")


async def startup() -> dict:
    """Assemble the application state. Returns the dict the API reads from."""
    log.info("=" * 52)
    log.info("  CodeFish Flood-Aware Routing — Starting Up  ")
    log.info("=" * 52)

    _step(1, "Loading road network...")
    graph = build_graph()

    _step(2, "Checking connectivity...")
    graph = ensure_connected(graph)

    _step(3, "Sampling rasters at road centroids...")
    graph = sample_rasters(graph)

    _step(4, "Loading models...")
    models = load_models()

    _step(5, "Loading evacuation centers...")
    centers = load_centers()

    _step(6, "Loading District 1 boundary...")
    boundary_geojson = _load_boundary()

    _step(7, "Loading map layers...")
    road_geojson = load_road_geojson()
    evac_geojson = load_centers_geojson()

    log.info("")
    log.info("Application ready.")
    log.info("POST /route — flood-aware routing active")
    log.info("=" * 52)

    return {
        'graph': graph,
        'models': models,
        'centers': centers,
        'road_geojson': road_geojson,
        'evac_geojson': evac_geojson,
        'boundary_geojson': boundary_geojson,
        'max_edge_length': graph.max_edge_length,
        # Flood inference runs lazily, per scenario, on first request.
        'predicted_scenarios': set(),
    }


def _load_boundary() -> dict | None:
    """The district outline. Missing it is a warning, not a failure: the map
    still draws, and geocoding falls back to a bounding box."""
    path = GEOJSON_PATHS['boundary']
    try:
        with open(path, 'r') as f:
            boundary = json.load(f)
        log.info(f"  Loaded boundary from {path}")
        return boundary
    except (OSError, json.JSONDecodeError) as e:
        log.warning(f"  Warning: Could not load boundary geojson: {e}")
        return None
