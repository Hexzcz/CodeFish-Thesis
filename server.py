from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import numpy as np
import datetime
import json
import geopandas as gpd
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

# Allow CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Connection
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_root():
    return FileResponse("index.html")

def get_gdf_as_json(table_name):
    """Helper to fetch from PostGIS and return as JSON."""
    try:
        query = f"SELECT * FROM {table_name}"
        gdf = gpd.read_postgis(query, engine, geom_col='geometry')
        # Ensure it's WGS84
        if gdf.crs is None:
            gdf.set_crs(epsg=4326, inplace=True)
        return json.loads(gdf.to_json())
    except Exception as e:
        print(f"Error fetching {table_name}: {e}")
        return {"error": str(e)}

@app.get("/flood_clipped.geojson")
async def get_flood_data():
    return get_gdf_as_json("flood_hazard")

@app.get("/qc_boundary.geojson")
async def get_boundary_data():
    return get_gdf_as_json("qc_boundary")

@app.get("/district1_boundary.geojson")
async def get_district1_boundary():
    return get_gdf_as_json("district_boundary")

@app.get("/project8_boundary.geojson")
async def get_project8_boundary_data():
    # Maps to district_boundary as per original logic
    return get_gdf_as_json("district_boundary")

@app.get("/district1_roads.geojson")
async def get_district1_roads():
    return get_gdf_as_json("roads")

@app.get("/project8_roads.geojson")
async def get_project8_roads_data():
    # Maps to roads (district1_roads) as per original logic
    return get_gdf_as_json("roads")

@app.get("/evacuation_sites.geojson")
async def get_evacuation_sites():
    return get_gdf_as_json("evacuation_sites")

# --- Original Logic for JAXA FTP ---
from jaxa_ftp import fetch_jaxa_forecast
from pydantic import BaseModel

class FTPConfig(BaseModel):
    host: str
    user: str
    password: str
    date: str = "" # Optional date YYYY-MM-DD
    hour: str = "" # Optional hour 00-23

@app.post("/sync_jaxa_ftp")
async def sync_ftp(config: FTPConfig):
    success = fetch_jaxa_forecast(config.host, config.user, config.password, date=config.date, hour=config.hour)
    if success:
        return {"status": "success", "message": "JAXA data refreshed from FTP."}
    else:
        return {"status": "error", "message": "Failed to connect or download from JAXA FTP."}

@app.get("/jaxa_rainfall_latest")
async def get_jaxa_rainfall():
    path = "cache/jaxa_qc_latest.json"
    if os.path.exists(path):
        return FileResponse(path)
    return {"error": "JAXA data not synced yet."}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8909))
    uvicorn.run(app, host="0.0.0.0", port=port)
