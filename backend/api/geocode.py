from fastapi import APIRouter, Query, HTTPException, Request
from typing import Optional, List, Dict
import httpx
import time
import hashlib

router = APIRouter(prefix="/api/geocode", tags=["geocode"])

# ── In-memory cache with TTL (5 minutes) ───────────────────────────────────────
_GEOCODE_CACHE: Dict[str, tuple] = {}  # key: (results, timestamp)
_CACHE_TTL = 300  # 5 minutes

# ── Rate limiting per session (10 requests per minute) ─────────────────────────
_RATE_LIMITS: Dict[str, List[float]] = {}  # session_id: [timestamps]
_RATE_LIMIT_WINDOW = 60  # 1 minute
_RATE_LIMIT_MAX = 10  # max requests per window

# ── Nominatim configuration ─────────────────────────────────────────────────────
NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = "CodeFish/1.0 (Flood-Aware Routing; contact: research@example.com)"

# ── District 1 QC bounding box (fallback if boundary not loaded) ───────────────
_DISTRICT1_VIEWBOX = {
    "west": 120.96,
    "south": 14.63,
    "east": 121.08,
    "north": 14.74
}


def _get_cache_key(query: str) -> str:
    """Generate cache key from query string."""
    return hashlib.md5(query.encode()).hexdigest()


def _get_cached_results(query: str) -> Optional[List[dict]]:
    """Return cached results if still valid."""
    key = _get_cache_key(query)
    if key in _GEOCODE_CACHE:
        results, timestamp = _GEOCODE_CACHE[key]
        if time.time() - timestamp < _CACHE_TTL:
            return results
        else:
            del _GEOCODE_CACHE[key]
    return None


def _cache_results(query: str, results: List[dict]):
    """Cache results with current timestamp."""
    key = _get_cache_key(query)
    _GEOCODE_CACHE[key] = (results, time.time())


def _check_rate_limit(session_id: str) -> bool:
    """Check if session has exceeded rate limit."""
    now = time.time()
    if session_id not in _RATE_LIMITS:
        _RATE_LIMITS[session_id] = []
    
    # Remove timestamps outside the window
    _RATE_LIMITS[session_id] = [
        ts for ts in _RATE_LIMITS[session_id] if now - ts < _RATE_LIMIT_WINDOW
    ]
    
    if len(_RATE_LIMITS[session_id]) >= _RATE_LIMIT_MAX:
        return False
    
    _RATE_LIMITS[session_id].append(now)
    return True


def _point_in_ring(point: tuple, ring: List[tuple]) -> bool:
    """Ray casting algorithm for point-in-polygon."""
    x, y = point
    inside = False
    for i in range(len(ring)):
        j = (i - 1) % len(ring)
        xi, yi = ring[i]
        xj, yj = ring[j]
        intersect = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi)
        if intersect:
            inside = not inside
    return inside


def _point_in_polygon(point: tuple, polygon_coords: List[List[tuple]]) -> bool:
    """Check if point is inside polygon (with holes)."""
    if not polygon_coords:
        return False
    outer = polygon_coords[0]
    if not _point_in_ring(point, outer):
        return False
    for hole in polygon_coords[1:]:
        if _point_in_ring(point, hole):
            return False
    return True


def _point_in_district_boundary(lat: float, lon: float, boundary_geojson: Optional[dict] = None) -> bool:
    """Check if point is inside District 1 boundary."""
    if not boundary_geojson:
        return True  # Allow if boundary not loaded
    
    point = (lon, lat)
    geom = boundary_geojson.get("geometry")
    if not geom:
        return True
    
    if geom["type"] == "Polygon":
        return _point_in_polygon(point, geom["coordinates"])
    elif geom["type"] == "MultiPolygon":
        return any(_point_in_polygon(point, poly) for poly in geom["coordinates"])
    
    return True


def _get_district1_viewbox(boundary_geojson: Optional[dict] = None) -> dict:
    """Extract or return fallback viewbox for District 1."""
    if boundary_geojson:
        geom = boundary_geojson.get("geometry")
        if geom:
            coords = []
            def _walk(arr):
                if isinstance(arr, list):
                    if len(arr) == 2 and isinstance(arr[0], (int, float)) and isinstance(arr[1], (int, float)):
                        coords.append(tuple(arr))
                    else:
                        for item in arr:
                            _walk(item)
            _walk(geom.get("coordinates", []))
            if coords:
                west = min(c[0] for c in coords)
                south = min(c[1] for c in coords)
                east = max(c[0] for c in coords)
                north = max(c[1] for c in coords)
                return {"west": west, "south": south, "east": east, "north": north}
    
    return _DISTRICT1_VIEWBOX


@router.get("/")
async def geocode_address(
    request: Request,
    query: str = Query(..., min_length=3, description="Address to geocode"),
):
    """
    Geocode an address using OpenStreetMap Nominatim, restricted to QC District 1.
    
    Features:
    - Rate limited: 10 requests per minute per session
    - Cached: Results cached for 5 minutes
    - Bounded: Restricted to District 1 viewbox + boundary filter
    - Proper headers: User-Agent and Accept headers for Nominatim compliance
    """
    # Get session ID from cookie or generate one
    session_id = request.cookies.get("session_id") or request.headers.get("x-session-id")
    if not session_id:
        session_id = f"anon_{hash(query)}"  # Fallback for anonymous requests
    
    # Check rate limit
    if not _check_rate_limit(session_id):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: maximum {_RATE_LIMIT_MAX} requests per {_RATE_LIMIT_WINDOW} seconds"
        )
    
    # Check cache first
    cached = _get_cached_results(query)
    if cached:
        return {"results": cached, "cached": True}
    
    # Get District 1 boundary from app state if available
    boundary_geojson = None
    try:
        boundary_geojson = request.app.state.data.get("boundary_geojson")
    except Exception:
        boundary_geojson = None
    
    # Build viewbox
    viewbox = _get_district1_viewbox(boundary_geojson)
    viewbox_str = f"{viewbox['west']},{viewbox['north']},{viewbox['east']},{viewbox['south']}"
    
    # Prepare Nominatim request
    params = {
        "format": "jsonv2",
        "limit": 8,
        "addressdetails": 1,
        "bounded": 1,
        "viewbox": viewbox_str,
        "q": f"{query}, Quezon City",
    }
    
    headers = {
        "User-Agent": NOMINATIM_USER_AGENT,
        "Accept": "application/json",
    }
    
    # Call Nominatim
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(NOMINATIM_BASE_URL, params=params, headers=headers)
            response.raise_for_status()
            items = response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Nominatim API error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Geocoding failed: {str(e)}")
    
    if not isinstance(items, list):
        items = []
    
    # Parse and filter results
    filtered = []
    for item in items:
        try:
            lat = float(item.get("lat"))
            lon = float(item.get("lon"))
            if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float))):
                continue
            
            # Strict boundary filter
            if not _point_in_district_boundary(lat, lon, boundary_geojson):
                continue
            
            filtered.append({
                "lat": lat,
                "lon": lon,
                "display_name": item.get("display_name", ""),
                "address": item.get("address", {}),
            })
        except (ValueError, TypeError):
            continue
    
    # Cache results
    _cache_results(query, filtered)
    
    return {"results": filtered, "cached": False}
