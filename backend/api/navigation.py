"""Navigation endpoints — following a route that has already been chosen.

Thin, like the others: validate, call the domain, shape the answer. Choosing a
route stays with `POST /route`; if someone has wandered off, the frontend asks
that endpoint again rather than anything here inventing a path.
"""
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.domain.navigation.progress import OFF_ROUTE_M, route_progress

router = APIRouter(prefix="/navigation", tags=["navigation"])

# A route with more points than this is not a walk through one district.
MAX_ROUTE_POINTS = 5000


class ProgressRequest(BaseModel):
    lat: float
    lon: float
    # [[lon, lat], ...] in travel order, as the route GeoJSON is drawn.
    route: List[List[float]]


@router.post("/progress")
async def get_progress(req: ProgressRequest):
    """Where a live position sits along a route that was already chosen."""
    if not (-90 <= req.lat <= 90) or not (-180 <= req.lon <= 180):
        raise HTTPException(400, "Invalid coordinates")
    if len(req.route) > MAX_ROUTE_POINTS:
        raise HTTPException(413, f"Route has more than {MAX_ROUTE_POINTS} points")

    try:
        progress = route_progress(req.route, req.lat, req.lon)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {**progress.to_dict(), "off_route_threshold_m": OFF_ROUTE_M}
