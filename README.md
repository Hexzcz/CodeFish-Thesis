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

## Features
- Multi-criteria route selection (TOPSIS)
- Real-time raster tile rendering
- Flood risk prediction across varied climate scenarios
- Interactive decision matrix comparison
