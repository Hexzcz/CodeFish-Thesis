# CodeFish: Flood-Aware Evacuation Routing

A modular FastAPI + Leaflet system for Philippine flood evacuation routing.

## Structure
- `backend/`: FastAPI application
  - `core/`: Config & Startup logic
  - `graph/`: Network infrastructure
  - `prediction/`: Flood prediction engine (XGBoost)
  - `routing/`: Road graph algorithms (Dijkstra, Yen's, TOPSIS)
  - `tiles/`: Raster tile server logic
  - `api/`: Endpoint definitions
  - `data/`: Local storage for models and geo-files
- `frontend/`: Single-Page Application
  - `css/`: Modular styling
  - `js/`: Modular logic (Map, Layers, Routing, UI)
- `scripts/`: Data fetching and prep utilities

## Setup
1. `pip install -r requirements.txt`
2. Run backend: `python backend/main.py`
3. Access: `http://localhost:8000`

## Offline mode
Road network, evacuation centers, and their GeoJSON layers are normally read from
Supabase (`DATABASE_URL`, see `backend/core/database.py`). When the database is
unreachable, each loader automatically falls back to the bundled files in
`backend/data/geojson/` (`road_nodes`, `road_edges`, `evacuation_centers`), so the
app still starts and routes.

To skip the database entirely — and avoid the connection timeouts on startup — set
`USE_LOCAL_DATA=1`:

```
USE_LOCAL_DATA=1 python -m uvicorn backend.main:app --reload
```

Note: the Esri basemap tiles and the JAXA rainfall fetch still require an internet
connection. Without one, the map renders without a basemap and rainfall intensity
stays at 0.00 mm/hr; routing is unaffected.

## Features
- Multi-criteria route selection (TOPSIS)
- Real-time raster tile rendering
- Flood risk prediction across varied climate scenarios
- Interactive decision matrix comparison
