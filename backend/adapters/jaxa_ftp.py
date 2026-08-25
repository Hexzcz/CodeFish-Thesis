"""Reading rainfall from JAXA's GSMaP FTP server.

Two products, two paths: GSMaP_NOW under /now/latest is observed rain rate for
the last 24 hours at half-hour steps, and /realtime/archive holds the hourly
near-real-time archive. Neither is a forecast — see
`docs/decisions/0004-gsmap-now-rainfall.md`.
"""
import datetime
import ftplib
import gzip
import io
import re
import struct
from typing import Optional


class RainfallUnavailable(RuntimeError):
    """The rainfall file could not be fetched. The message is user-facing."""


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


def fetch_rainfall(
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

    Raises RainfallUnavailable if the file cannot be fetched.
    """
    try:
        ftp = ftplib.FTP(JAXA_HOST, timeout=20)
        ftp.login(JAXA_USER, JAXA_PASS)
    except Exception as e:
        raise RainfallUnavailable(f"Could not connect to JAXA FTP: {e}")

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
                raise RainfallUnavailable(f"No GSMaP_NOW files found in {JAXA_NOW_DIR}")

            # step is 1-based hours back: step=1 → latest, step=2 → one hour earlier.
            latest_ts = available[-1][0]
            wanted = latest_ts - datetime.timedelta(hours=step - 1)
            usable = [entry for entry in available if entry[0] <= wanted]
            _, filename = usable[-1] if usable else available[0]

        bio = io.BytesIO()
        ftp.retrbinary(f"RETR {filename}", bio.write)
        ftp.quit()
    except RainfallUnavailable:
        raise
    except Exception as e:
        raise RainfallUnavailable(f"JAXA FTP fetch failed: {e}")

    rainfall = _read_pixel(bio)
    return rainfall, f"Success – {filename}"
