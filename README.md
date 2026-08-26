# CodeFish: Flood-Aware Evacuation Routing

Given a pin anywhere in District 1, Quezon City, CodeFish ranks three routes to
nearby evacuation centers — preferring the dry way over the short way, using an
XGBoost flood-susceptibility model and TOPSIS multi-criteria ranking.

## Running it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn backend.main:app --reload
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

With no configuration it runs entirely from the bundled data in
`backend/data/` — no database, no waiting for a connection that isn't there.
Point it at Postgres by setting `DATABASE_URL`, and it will use that instead,
falling back to the same files if it becomes unreachable. See
[ADR-0002](docs/decisions/0002-local-geojson-fallback.md).

## Configuration

Every setting is optional and read from the environment. Copy the template and
fill in what you need:

```bash
cp .env.example .env
```

| Variable | Effect if unset |
|---|---|
| `DATABASE_URL` | Reads the bundled GeoJSON instead of Postgres |
| `JAXA_USER` / `JAXA_PASS` | Live rainfall is disabled and says so; the simulator still works |
| `USE_LOCAL_DATA` | Implied whenever `DATABASE_URL` is unset |

`.env` is gitignored. No credential belongs in the source — a test
(`tests/test_no_committed_secrets.py`) fails the build if one reappears.

The Esri basemap and the JAXA rainfall fetch need the internet; routing does
not. Offline, the map draws without a basemap and rainfall reads 0.00 mm/hr.

## Installing it on a phone

The resident's view is a progressive web app: open it in Chrome or Safari and
choose "Add to Home Screen". It then opens like an app, and keeps working when
the signal does not — the map, the district, the centers and your last route
are all still there.

Routing itself needs the server, so a new route cannot be worked out offline;
the app says so rather than failing quietly. Service workers also require
HTTPS: over plain `http://` from another machine it stays an ordinary website.
See [ADR-0006](docs/decisions/0006-installable-and-offline.md).

## Walking a route

After a route is chosen, **Start navigation** follows the walker live: the map
tilts into a 3D heading-up view, the position marker moves with them, and the
panel shows the distance left. Straying from the route asks the same
flood-aware router for a new one from where they now are — never a shorter,
riskier path.

Live location needs HTTPS (or localhost). If the device cannot run the 3D view,
navigation continues on the flat map. Offline it keeps following the position
but cannot check progress or reroute, and says so. See
[ADR-0007](docs/decisions/0007-live-navigation.md).

## Checking it

```bash
.venv/bin/python -m pytest tests -q
```

Every push runs the same suite on GitHub Actions — see
[.github/workflows/tests.yml](.github/workflows/tests.yml).

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
