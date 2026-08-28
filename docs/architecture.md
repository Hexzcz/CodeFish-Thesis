# Architecture

The map to read before touching anything. The goal of this layout is **low
cognitive load**: you should be able to hold the whole thing in your head.

## The whole system in one picture

```
  You drop a pin  ───▶  Engine  ───▶  Three routes, ranked  ───▶  You pick one
   somewhere in         what a route         by flood risk           and evacuate
   District 1           costs, and              first
                        which one wins
```

Three parts. **`backend/domain/`** decides where you should go and knows
nothing about the web, the database or the file system. **`backend/adapters/`**
answers the things the engine cannot do alone — read a raster, query Supabase,
fetch rainfall over FTP. **`backend/api/` + `frontend/`** is the application:
it wires one to the other and draws the map.

## Guiding principles

- **The engine depends on nothing.** Business rules sit at the centre; the
  frameworks sit at the edge and point inward. `tests/test_dependency_rule.py`
  enforces this, because the failure it prevents is invisible until the day you
  want to test the router without standing up a server.
- **Deep modules.** Prefer a simple interface over a powerful implementation.
  `plan_evacuation_routes` is one call; snapping, candidate selection, Yen's
  alternatives and TOPSIS ranking are all hidden behind it.
- **The app must run with nothing plugged in.** No database, no internet, no
  API keys — otherwise it cannot be demonstrated. Every remote source has a
  bundled fallback. See [ADR-0002](decisions/0002-local-geojson-fallback.md).
- **Errors are explicit and typed.** A pin 800 m from the nearest road is a
  400 with a sentence, not a route from somewhere else. Rainfall that cannot
  be fetched is a 502, not 0.00 mm/hr.

## Layout

```
backend/
├── domain/                  THE ENGINE — no framework imports
│   ├── graph.py             the road network: nodes, edges, attributes
│   ├── geo.py               distances, nearest node, point-in-district
│   ├── routing/
│   │   ├── dijkstra.py      flood-weighted shortest path
│   │   ├── distance.py      plain shortest path — the baseline
│   │   ├── yens.py          k alternative routes
│   │   ├── weights.py       the WSM edge cost
│   │   ├── snapping.py      attaching a dropped pin to the network
│   │   ├── edge_split.py    inserting a node partway along a road
│   │   ├── connectivity.py  keeping the graph one piece
│   │   └── scoring/         what a route costs, and which one wins
│   ├── navigation/          where you are along a route you were given
│   ├── prediction/          flood class per edge; rainfall → which model
│   └── services/            the use cases: plan routes, choose centers
├── adapters/                THE EDGES — the only I/O
│   ├── road_network.py      Supabase, or the bundled GeoJSON
│   ├── evacuation_centers.py
│   ├── raster_sampler.py    terrain features under each road
│   ├── tile_renderer.py     raster → PNG map tiles
│   ├── model_store.py       loading the XGBoost models
│   ├── jaxa_ftp.py          GSMaP rainfall
│   ├── nominatim.py         address search
│   ├── database.py
│   └── reporting/           the scoring breakdown printed to the terminal
├── api/                     THE HTTP EDGE — thin routers, schemas, presenters
├── core/                    config, and the startup that wires it together
└── data/                    models, rasters, GeoJSON
```

### The dependency rule

```
   api  ─▶  adapters  ─▶  domain
   (HTTP)   (I/O)         (pure rules — imports no framework)
```

Nothing in `backend/domain/` may import fastapi, starlette, pydantic,
sqlalchemy, psycopg2, rasterio, rio_tiler, geopandas, matplotlib, PIL, httpx,
ftplib, joblib or xgboost — nor anything from `backend/adapters/` or
`backend/api/`. numpy and pandas are fine: they compute, they do not talk to
anything. `pytest tests/` fails the build if this is broken. See
[ADR-0001](decisions/0001-engine-and-adapters.md).

### What the engine asks the edges for

| It needs | The adapter | Without it |
|---|---|---|
| the road network | `road_network.py` | bundled `road_edges.geojson` |
| evacuation centers | `evacuation_centers.py` | bundled `evacuation_centers.geojson` |
| terrain under a road | `raster_sampler.py` | `DEFAULT_FEATURES` in config |
| flood models | `model_store.py` | no prediction — startup fails loudly |
| current rainfall | `jaxa_ftp.py` | the simulator, or 0.00 mm/hr |
| an address → a point | `nominatim.py` | click the map instead |

### The frontend mirrors it

```
frontend/
├── sw.js         the service worker: what still works with no signal
├── manifest.webmanifest, icons/    what makes it installable
├── vendor/leaflet/                 vendored, so the map needs no CDN
└── js/
├── mode.js       which face you get: simple, or the admin console
├── i18n.js       English and Filipino for the resident's view
├── pwa.js        registration, the offline banner, the last-route memory
├── map/          the Leaflet map and the district outline
├── layers/       raster overlays and the road layer
├── centers/      evacuation center markers
├── routing/      the request, drawing routes, visibility, the baseline
├── navigation/   walking it: the GPS watch, the 3D map, the follow camera,
│                 the rainfall watch, and the session that reroutes when
│                 someone strays or the weather turns
├── simple/       the resident's view: the flow, the card, the way there,
│                 and the one file that turns model output into sentences
└── ui/           the console: sidebar, rainfall controls, and
    └── panel/    the analysis panel: overview, segments, baseline, compare
```

Two views, one page. `<html data-mode="simple|admin">` decides what is shown;
both share the same map and the same `requestRoutes()`. See
[ADR-0005](decisions/0005-two-views.md).

A second map — MapLibre GL — provides the tilted 3D navigation view; Leaflet
still owns 2D. Following a route live, including how deviation is detected and
why rerouting calls the ordinary router, is
[ADR-0007](decisions/0007-live-navigation.md).

The resident's view reflows to a bottom sheet below 768px and the app installs
to a home screen. Routing still needs the server — what does and does not
survive going offline is written down in
[ADR-0006](decisions/0006-installable-and-offline.md).

Plain scripts on `window`, no build step — deliberately, because this has to
run from a folder on a laptop during a defense. `index.html` loads them in
dependency order and each `?v=` bumps when its file changes.

## Checking it

```bash
.venv/bin/python -m pytest tests -q     # the dependency rule, routing, offline data
USE_LOCAL_DATA=1 .venv/bin/python -m uvicorn backend.main:app --reload
```
