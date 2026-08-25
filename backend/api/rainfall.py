"""Rainfall endpoints.

Both endpoints do the same thing; they stay separate so the explicit "Fetch
from FTP" button can grow its own logging or rate limiting later.
"""
import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.adapters.jaxa_ftp import RainfallUnavailable, fetch_rainfall
from backend.domain.prediction.rainfall_scenario import scenario_for_intensity

router = APIRouter(prefix="/rainfall", tags=["rainfall"])

MAX_HOURS_BACK = 6


def _build_response(mode: str, timestamp: Optional[str], step: int) -> dict:
    dt = datetime.datetime.now()
    if timestamp:
        try:
            dt = datetime.datetime.fromisoformat(timestamp.replace('Z', ''))
        except ValueError:
            pass  # An unparseable timestamp falls back to now, as before.

    try:
        value, message = fetch_rainfall(mode, dt, step)
    except RainfallUnavailable as e:
        # Surface the failure instead of reporting it as 0.00 mm/hr.
        raise HTTPException(status_code=502, detail=str(e))

    return {
        "intensity": round(value, 2),
        "mapping": scenario_for_intensity(value),
        "message": message,
        "mode": mode,
        "step": step,
        "time_ph": dt.strftime("%Y-%m-%d %H:%M"),
    }


@router.get("/jaxa")
async def get_jaxa_data(
    mode: str = Query("forecast"),
    timestamp: Optional[str] = None,
    step: int = Query(1, ge=1, le=MAX_HOURS_BACK),
):
    """Rainfall intensity over District 1, and the model it maps to."""
    return _build_response(mode, timestamp, step)


@router.get("/jaxa/ftp")
async def get_jaxa_ftp(
    mode: str = Query("forecast"),
    timestamp: Optional[str] = None,
    step: int = Query(1, ge=1, le=MAX_HOURS_BACK),
):
    """Explicit FTP pull, triggered by the 'Fetch from FTP' button."""
    return _build_response(mode, timestamp, step)
