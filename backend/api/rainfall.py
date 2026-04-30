from fastapi import APIRouter, Query, HTTPException
from typing import Optional
import datetime
import ftplib
import gzip
import io
import struct

router = APIRouter(prefix="/rainfall", tags=["rainfall"])

JAXA_HOST = "hokusai.eorc.jaxa.jp"
JAXA_USER = "rainmap"
JAXA_PASS = "Niskur+1404"

# QC District 1 coordinates
_LAT = 14.64
_LON = 121.02
_LAT_IDX = int((60 - _LAT) / 0.1)
_LON_IDX = int(_LON / 0.1)
_PIXEL_OFFSET = (_LAT_IDX * 3600 + _LON_IDX) * 4


def _intensity_to_mapping(value: float) -> str:
    if value >= 50:
        return "100yr"
    elif value >= 25:
        return "25yr"
    return "5yr"


def _read_pixel(bio: io.BytesIO) -> float:
    bio.seek(0)
    with gzip.GzipFile(fileobj=bio) as gz:
        data = gz.read()
        val = struct.unpack_from('<f', data, _PIXEL_OFFSET)[0]
        return max(0.0, float(val))


def get_jaxa_rainfall_data(
    mode: str,
    target_time: Optional[datetime.datetime] = None,
    range_type: str = "short",
    step: int = 1,
) -> tuple:
    """
    Fetch JAXA GSMaP rainfall intensity for District 1, QC.

    For forecast mode:
      - range_type='short'  → short-range forecast, step = hour offset (1-6)
      - range_type='medium' → medium-range forecast, step = day offset  (1-5)

    For historical mode:
      - target_time is used directly (local PH time → converted to UTC)
    """
    try:
        ftp = ftplib.FTP(JAXA_HOST, timeout=20)
        ftp.login(JAXA_USER, JAXA_PASS)

        filename = ""
        directory = ""

        if mode == "historical":
            utc_time = target_time - datetime.timedelta(hours=8)
            ts = utc_time.strftime("%Y%m%d.%H00")
            directory = f"/realtime/archive/{utc_time.strftime('%Y/%m/%d')}/"
            filename = f"gsmap_nrt.{ts}.dat.gz"

        else:  # forecast
            directory = "/forecast/archive/"
            ftp.cwd(directory)
            files = []
            ftp.retrlines('NLST', files.append)
            fcst_files = sorted([f for f in files if "gsmap_fcst" in f and f.endswith(".dat.gz")])
            if not fcst_files:
                ftp.quit()
                return 0.0, "No forecast files found"

            # Each forecast file covers one time-step.
            # step is 1-based: step=1 → first/nearest file.
            # For medium range files are typically labelled by day.
            step_idx = max(0, min(step - 1, len(fcst_files) - 1))
            filename = fcst_files[step_idx]

        ftp.cwd(directory)
        bio = io.BytesIO()
        ftp.retrbinary(f"RETR {filename}", bio.write)
        ftp.quit()

        rainfall = _read_pixel(bio)
        return rainfall, f"Success – {filename}"

    except Exception as e:
        return 0.0, str(e)


# ── Shared response builder ──────────────────────────────────────────────────
def _build_response(mode: str, timestamp: Optional[str], range_type: str, step: int) -> dict:
    dt = datetime.datetime.now()
    if timestamp:
        try:
            dt = datetime.datetime.fromisoformat(timestamp.replace('Z', ''))
        except Exception:
            pass

    value, message = get_jaxa_rainfall_data(mode, dt, range_type, step)
    mapping = _intensity_to_mapping(value)

    return {
        "intensity": round(value, 2),
        "mapping": mapping,
        "message": message,
        "mode": mode,
        "range": range_type,
        "step": step,
        "time_ph": dt.strftime("%Y-%m-%d %H:%M"),
    }


# ── /rainfall/jaxa  (existing — now also accepts step) ─────────────────────
@router.get("/jaxa")
async def get_jaxa_data(
    mode: str = Query("forecast"),
    timestamp: Optional[str] = None,
    range: str = Query("short"),
    step: int = Query(1, ge=1, le=6),
):
    return _build_response(mode, timestamp, range, step)


# ── /rainfall/jaxa/ftp  (explicit FTP fetch triggered by button) ────────────
@router.get("/jaxa/ftp")
async def get_jaxa_ftp(
    mode: str = Query("forecast"),
    timestamp: Optional[str] = None,
    range: str = Query("short"),
    step: int = Query(1, ge=1, le=6),
):
    """
    Explicit FTP pull triggered by the 'Fetch from FTP' button on the frontend.
    Functionally identical to /jaxa but separated so it can have distinct
    logging, rate-limiting, or caching behaviour in the future.
    """
    return _build_response(mode, timestamp, range, step)
