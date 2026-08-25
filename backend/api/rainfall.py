from fastapi import APIRouter, Query, HTTPException
from typing import Optional
import datetime
import ftplib
import gzip
import io
import re
import struct

router = APIRouter(prefix="/rainfall", tags=["rainfall"])

JAXA_HOST = "hokusai.eorc.jaxa.jp"
JAXA_USER = "rainmap"
JAXA_PASS = "Niskur+1404"

# GSMaP_NOW: half-hourly rain rate for the latest 24 hours.
# Files are named gsmap_now.YYYYMMDD.HHNN.dat.gz (UTC start time); the
# gsmap_now.YYYYMMDD.HHMM_hhnn.dat.gz form is the same data, so it is skipped.
JAXA_NOW_DIR = "/now/latest/"
JAXA_NOW_FILE = re.compile(r"^gsmap_now\.(\d{8})\.(\d{4})\.dat\.gz$")

# QC District 1 coordinates
_LAT = 14.64
_LON = 121.02
_LAT_IDX = int((60 - _LAT) / 0.1)
_LON_IDX = int(_LON / 0.1)
_PIXEL_OFFSET = (_LAT_IDX * 3600 + _LON_IDX) * 4


def _intensity_to_mapping(value: float) -> str:
    """Map JAXA GSMaP rainfall intensity to CODEFISH return period scenario.
    Thresholds based on PAGASA rainfall intensity classification:
      Low:      < 7.5 mm/hr  → 5-year return period
      Moderate: 7.5–30 mm/hr → 25-year return period
      High:     > 30 mm/hr   → 100-year return period
    """
    if value > 30:
        return "100yr"
    elif value >= 7.5:
        return "25yr"
    return "5yr"


def _read_pixel(bio: io.BytesIO) -> float:
    bio.seek(0)
    with gzip.GzipFile(fileobj=bio) as gz:
        data = gz.read()
        val = struct.unpack_from('<f', data, _PIXEL_OFFSET)[0]
        return max(0.0, float(val))


def _list_now_files(ftp) -> list:
    """Return [(utc_datetime, filename), ...] from /now/latest, oldest first."""
    ftp.cwd(JAXA_NOW_DIR)
    names = []
    ftp.retrlines('NLST', names.append)

    available = []
    for name in names:
        match = JAXA_NOW_FILE.match(name)
        if match:
            ts = datetime.datetime.strptime(match.group(1) + match.group(2), "%Y%m%d%H%M")
            available.append((ts, name))
    available.sort()
    return available


def get_jaxa_rainfall_data(
    mode: str,
    target_time: Optional[datetime.datetime] = None,
    step: int = 1,
) -> tuple:
    """
    Fetch JAXA GSMaP rainfall intensity for District 1, QC.

    For nowcast mode (mode != 'historical'):
      - GSMaP_NOW observed rain rate, step = hours back from the latest
        available half-hourly file (step=1 → latest).

    For historical mode:
      - target_time is used directly (local PH time → converted to UTC)

    Raises RuntimeError if the file cannot be fetched.
    """
    try:
        ftp = ftplib.FTP(JAXA_HOST, timeout=20)
        ftp.login(JAXA_USER, JAXA_PASS)
    except Exception as e:
        raise RuntimeError(f"Could not connect to JAXA FTP: {e}")

    try:
        if mode == "historical":
            utc_time = target_time - datetime.timedelta(hours=8)
            ts = utc_time.strftime("%Y%m%d.%H00")
            directory = f"/realtime/archive/{utc_time.strftime('%Y/%m/%d')}/"
            filename = f"gsmap_nrt.{ts}.dat.gz"
            ftp.cwd(directory)

        else:  # nowcast — latest observed rain rate
            available = _list_now_files(ftp)
            if not available:
                raise RuntimeError(f"No GSMaP_NOW files found in {JAXA_NOW_DIR}")

            # step is 1-based hours back: step=1 → latest, step=2 → one hour earlier.
            latest_ts = available[-1][0]
            wanted = latest_ts - datetime.timedelta(hours=step - 1)
            usable = [entry for entry in available if entry[0] <= wanted]
            _, filename = usable[-1] if usable else available[0]

        bio = io.BytesIO()
        ftp.retrbinary(f"RETR {filename}", bio.write)
        ftp.quit()
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"JAXA FTP fetch failed: {e}")

    rainfall = _read_pixel(bio)
    return rainfall, f"Success – {filename}"


# ── Shared response builder ──────────────────────────────────────────────────
def _build_response(mode: str, timestamp: Optional[str], step: int) -> dict:
    dt = datetime.datetime.now()
    if timestamp:
        try:
            dt = datetime.datetime.fromisoformat(timestamp.replace('Z', ''))
        except Exception:
            pass

    try:
        value, message = get_jaxa_rainfall_data(mode, dt, step)
    except RuntimeError as e:
        # Surface the failure instead of reporting it as 0.00 mm/hr.
        raise HTTPException(status_code=502, detail=str(e))

    mapping = _intensity_to_mapping(value)

    return {
        "intensity": round(value, 2),
        "mapping": mapping,
        "message": message,
        "mode": mode,
        "step": step,
        "time_ph": dt.strftime("%Y-%m-%d %H:%M"),
    }


# ── /rainfall/jaxa ──────────────────────────────────────────────────────────
@router.get("/jaxa")
async def get_jaxa_data(
    mode: str = Query("forecast"),
    timestamp: Optional[str] = None,
    step: int = Query(1, ge=1, le=6),
):
    return _build_response(mode, timestamp, step)


# ── /rainfall/jaxa/ftp  (explicit FTP fetch triggered by button) ────────────
@router.get("/jaxa/ftp")
async def get_jaxa_ftp(
    mode: str = Query("forecast"),
    timestamp: Optional[str] = None,
    step: int = Query(1, ge=1, le=6),
):
    """
    Explicit FTP pull triggered by the 'Fetch from FTP' button on the frontend.
    Functionally identical to /jaxa but separated so it can have distinct
    logging, rate-limiting, or caching behaviour in the future.
    """
    return _build_response(mode, timestamp, step)
