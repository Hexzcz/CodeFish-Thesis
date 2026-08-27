# CodeFish, packaged.
#
# Two stages so the compilers that build the geo wheels do not ship: the final
# image carries the interpreter, the installed packages and the app, and
# nothing that was only needed to get them there.

# ── Build ───────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies change far less often than the code, so they are their own
# layer and a code edit does not reinstall geopandas.
COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install -r requirements.txt

# ── Run ─────────────────────────────────────────────────────────────────────
FROM python:3.12-slim

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # No database is configured by default: the image is self-contained and
    # runs from the bundled GeoJSON. Set DATABASE_URL to change that.
    USE_LOCAL_DATA=1

# The wheels are prebuilt but not self-contained: rasterio links against
# libexpat and XGBoost against libgomp, neither of which python:*-slim ships.
# Without these the app dies at import with a missing .so — which is exactly
# the kind of thing that only shows up in the container.
RUN apt-get update && \
    apt-get install -y --no-install-recommends libexpat1 libgomp1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=build /opt/venv /opt/venv
COPY backend/ backend/
COPY frontend/ frontend/

# Nothing here needs to write to disk or run as root.
RUN useradd --create-home --uid 10001 codefish && chown -R codefish:codefish /app
USER codefish

EXPOSE 8000

# The platform tells us which port to listen on; 8000 when it does not.
CMD ["sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
