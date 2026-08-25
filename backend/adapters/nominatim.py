"""Address search through OpenStreetMap Nominatim.

Nominatim asks callers to identify themselves and not to hammer it, so the
cache and the rate limit are part of using it correctly, not an optimisation.
Results are filtered to District 1 by the caller.
"""
import hashlib
import time
from typing import Dict, List, Optional

import httpx


class GeocodingError(RuntimeError):
    """Nominatim could not be reached or answered with an error."""


# ── In-memory cache with TTL (5 minutes) ───────────────────────────────────────
_GEOCODE_CACHE: Dict[str, tuple] = {}  # key: (results, timestamp)
_CACHE_TTL = 300  # 5 minutes

# ── Rate limiting per session (10 requests per minute) ─────────────────────────
_RATE_LIMITS: Dict[str, List[float]] = {}  # session_id: [timestamps]
RATE_LIMIT_WINDOW = 60  # 1 minute
RATE_LIMIT_MAX = 10  # max requests per window

# ── Nominatim configuration ─────────────────────────────────────────────────────
NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = "CodeFish/1.0 (Flood-Aware Routing; contact: research@example.com)"

def _get_cache_key(query: str) -> str:
    """Generate cache key from query string."""
    return hashlib.md5(query.encode()).hexdigest()


def cached_results(query: str) -> Optional[List[dict]]:
    """Return cached results if still valid."""
    key = _get_cache_key(query)
    if key in _GEOCODE_CACHE:
        results, timestamp = _GEOCODE_CACHE[key]
        if time.time() - timestamp < _CACHE_TTL:
            return results
        else:
            del _GEOCODE_CACHE[key]
    return None


def cache_results(query: str, results: List[dict]):
    """Cache results with current timestamp."""
    key = _get_cache_key(query)
    _GEOCODE_CACHE[key] = (results, time.time())


def within_rate_limit(session_id: str) -> bool:
    """Check if session has exceeded rate limit."""
    now = time.time()
    if session_id not in _RATE_LIMITS:
        _RATE_LIMITS[session_id] = []
    
    # Remove timestamps outside the window
    _RATE_LIMITS[session_id] = [
        ts for ts in _RATE_LIMITS[session_id] if now - ts < RATE_LIMIT_WINDOW
    ]
    
    if len(_RATE_LIMITS[session_id]) >= RATE_LIMIT_MAX:
        return False
    
    _RATE_LIMITS[session_id].append(now)
    return True




async def search_addresses(query: str, viewbox: Dict[str, float]) -> List[dict]:
    """Ask Nominatim for places matching `query` inside `viewbox`.

    Raises GeocodingError; returns raw Nominatim items, unfiltered.
    """
    params = {
        "format": "jsonv2",
        "limit": 8,
        "addressdetails": 1,
        "bounded": 1,
        "viewbox": f"{viewbox['west']},{viewbox['north']},{viewbox['east']},{viewbox['south']}",
        "q": f"{query}, Quezon City",
    }
    headers = {
        "User-Agent": NOMINATIM_USER_AGENT,
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(NOMINATIM_BASE_URL, params=params, headers=headers)
            response.raise_for_status()
            items = response.json()
    except httpx.HTTPStatusError as e:
        raise GeocodingError(f"Nominatim API error: {e}")
    except Exception as e:
        raise GeocodingError(f"Geocoding failed: {e}")

    return items if isinstance(items, list) else []
