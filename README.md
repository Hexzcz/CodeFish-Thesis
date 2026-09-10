# CodeFish: Flood-Aware Evacuation Routing

Given a pin anywhere in District 1, Quezon City, CodeFish ranks three routes to
nearby evacuation centers — preferring the dry way over the short way, using an
XGBoost flood-susceptibility model and TOPSIS ranking.

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run.sh                      # or run_app.ps1 on Windows
```

http://localhost:8000 — the **resident's view**: one question, one answer.
Add `?mode=admin` for the **console**: weights, layers, TOPSIS analysis.
([ADR-0005](docs/decisions/0005-two-views.md))

No configuration needed. It runs entirely from `backend/data/` — no database,
no keys. ([ADR-0002](docs/decisions/0002-local-geojson-fallback.md))

## Deploy it

```bash
docker build -t codefish . && docker run --rm -p 8000:8000 codefish
```

Fly and Render configs are in the repo. Deploy for HTTPS above all: live
location and installing to a home screen both need a secure origin.
See [docs/deployment.md](docs/deployment.md).

## Configure it

Optional, from the environment. `cp .env.example .env`.

| Variable | If unset |
|---|---|
| `DATABASE_URL` | Bundled GeoJSON instead of Postgres |
| `JAXA_USER` / `JAXA_PASS` | Live rainfall off, and says so; simulator still works |
| `USE_LOCAL_DATA` | Implied when `DATABASE_URL` is unset |
| `ROUTE_RATE_LIMIT` | 30 route requests per caller per minute |
| `LOG_LEVEL` / `REPORT_LEVEL` | `INFO`. `REPORT_LEVEL=WARNING` drops the scoring tables |

No credential belongs in the source — `tests/test_no_committed_secrets.py`
fails the build if one reappears.

Basemap tiles and JAXA rainfall need the internet; routing does not. The 2D map
uses Esri, the 3D view OpenStreetMap (Esri has no tiles above zoom 16;
navigation runs at 17.5). Both live in `BASEMAP_3D`, `frontend/js/config.js` —
OSM's tile policy is for light use, so read it before a public demo.

## Test it

```bash
.venv/bin/python -m pytest tests -q      # 200 tests
npm test --prefix tests/e2e              # 28 in a real browser; starts the app
```

Three CI jobs on every push: backend, browser, and a container build that boots
the image and asks it for a route.

## Layout

| Directory | |
|---|---|
| `backend/domain/` | the engine: routing, scoring, prediction. Imports no framework. |
| `backend/adapters/` | everything that talks outward: database, files, rasters, FTP, HTTP |
| `backend/api/` | thin routers over the engine |
| `backend/core/` | config, logging, rate limiting, startup |
| `backend/data/` | models, rasters, GeoJSON |
| `frontend/` | plain JS and CSS, no build step |
| `scripts/` | the pipeline that produced `backend/data/` |
| `tests/` | rules, routing, offline data, secrets, translations · `tests/e2e/` for the browser |

Read [docs/architecture.md](docs/architecture.md) first — it explains the one
rule the layout depends on. Also:
[coding standards](docs/coding-standards.md) ·
[decisions](docs/decisions) ·
[model evaluation](docs/model-evaluation.md)

## Features

- TOPSIS route selection: flood 0.764, road class 0.124, distance 0.112
  ([ADR-0003](docs/decisions/0003-topsis-weights.md))
- Flood prediction per road across 5-, 25- and 100-year return periods
- Raster tiles for hazard, elevation, slope, land cover
- Live rainfall from JAXA GSMaP via PAGASA thresholds
  ([ADR-0004](docs/decisions/0004-gsmap-now-rainfall.md))
- Live navigation: 3D heading-up view, rerouting when you stray or the rain
  turns ([ADR-0007](docs/decisions/0007-live-navigation.md))
- Installable, and honest about what works offline
  ([ADR-0006](docs/decisions/0006-installable-and-offline.md))
- One colour per route from its overall flood risk, drawn from the same rule
  that writes the sentence beside it; the console keeps per-road colouring
- English and Filipino · keyboard and screen reader, checked by tests
