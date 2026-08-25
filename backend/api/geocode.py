"""Address search, restricted to District 1.

Nominatim's answers are untrusted input: every result is re-checked against
the district boundary here before the browser ever sees it. Bounding the
search box is a hint to Nominatim; the boundary filter is the guarantee.
"""
from fastapi import APIRouter, HTTPException, Query, Request

from backend.adapters.nominatim import (
    RATE_LIMIT_MAX,
    RATE_LIMIT_WINDOW,
    GeocodingError,
    cache_results,
    cached_results,
    search_addresses,
    within_rate_limit,
)
from backend.domain.geo import boundary_viewbox, point_in_boundary

router = APIRouter(prefix="/api/geocode", tags=["geocode"])


@router.get("/")
async def geocode_address(
    request: Request,
    query: str = Query(..., min_length=3, description="Address to geocode"),
):
    """Geocode an address, returning only places inside District 1."""
    session_id = (
        request.cookies.get("session_id")
        or request.headers.get("x-session-id")
        or f"anon_{hash(query)}"
    )

    if not within_rate_limit(session_id):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: maximum {RATE_LIMIT_MAX} requests per {RATE_LIMIT_WINDOW} seconds",
        )

    cached = cached_results(query)
    if cached is not None:
        return {"results": cached, "cached": True}

    boundary_geojson = getattr(request.app.state, "data", {}).get("boundary_geojson")

    try:
        items = await search_addresses(query, boundary_viewbox(boundary_geojson))
    except GeocodingError as e:
        raise HTTPException(status_code=502, detail=str(e))

    results = []
    for item in items:
        try:
            lat = float(item.get("lat"))
            lon = float(item.get("lon"))
        except (TypeError, ValueError):
            continue
        if not point_in_boundary(lat, lon, boundary_geojson):
            continue
        results.append({
            "lat": lat,
            "lon": lon,
            "display_name": item.get("display_name", ""),
            "address": item.get("address", {}),
        })

    cache_results(query, results)
    return {"results": results, "cached": False}
