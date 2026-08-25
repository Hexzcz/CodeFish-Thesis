# CodeFish: Flood-Aware Evacuation Routing

Given a pin anywhere in District 1, Quezon City, CodeFish ranks three routes to
nearby evacuation centers — preferring the dry way over the short way, using an
XGBoost flood-susceptibility model and TOPSIS multi-criteria ranking.

## Running it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
USE_LOCAL_DATA=1 .venv/bin/python -m uvicorn backend.main:app --reload
```

Then open http://localhost:8000. On Windows, `run_app.ps1` does the same;
on macOS or Linux, `./run.sh`.

## Two views

`http://localhost:8000` opens the **resident's view**: one question — where are
you — and one answer, with the flood-model vocabulary kept out of it.

`http://localhost:8000/?mode=admin` opens the **console**: rainfall source,
criteria weights, raster layers, and the full TOPSIS/WSM analysis panel. The
choice is remembered per browser; each view links to the other. See
[ADR-0005](docs/decisions/0005-two-views.md).

`USE_LOCAL_DATA=1` runs entirely from the bundled data in `backend/data/`, with
no database. Without it the app tries Supabase first (`DATABASE_URL`) and falls
back to the same files if it cannot reach it — so it works either way, it just
waits for the connection to time out first. See
[ADR-0002](docs/decisions/0002-local-geojson-fallback.md).

The Esri basemap and the JAXA rainfall fetch need the internet; routing does
not. Offline, the map draws without a basemap and rainfall reads 0.00 mm/hr.

## Checking it

```bash
.venv/bin/python -m pytest tests -q
```

## Where things are

| Directory | What lives there |
|---|---|
| `backend/domain/` | the engine: routing, scoring, prediction rules. Imports no framework. |
| `backend/adapters/` | everything that talks outward: database, files, rasters, FTP, HTTP |
| `backend/api/` | the HTTP layer — thin routers over the engine |
| `backend/core/` | configuration, and the startup that wires it all together |
| `backend/data/` | models, rasters and GeoJSON — the app's whole world |
| `frontend/` | the map: plain JS and CSS, no build step |
| `scripts/` | the data pipeline that produced `backend/data/` |
| `tests/` | the dependency rule, the routing behaviour, the offline data |
| `docs/` | [architecture](docs/architecture.md) · [coding standards](docs/coding-standards.md) · [decisions](docs/decisions) · [model evaluation](docs/model-evaluation.md) |

Read [docs/architecture.md](docs/architecture.md) before changing anything —
it explains the one rule the layout depends on.

## Features

- Multi-criteria route selection (TOPSIS): flood exposure 0.764, road class
  0.124, distance 0.112 — see [ADR-0003](docs/decisions/0003-topsis-weights.md)
- Flood prediction per road segment across 5-, 25- and 100-year return periods
- Real-time raster tile rendering of hazard, elevation, slope and land cover
- Live rainfall from JAXA GSMaP, mapped to a return period by PAGASA
  thresholds — see [ADR-0004](docs/decisions/0004-gsmap-now-rainfall.md)
- Side-by-side comparison against the plain shortest-distance route
