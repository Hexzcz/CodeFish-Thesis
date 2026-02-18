from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os
import numpy as np
import datetime

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_root():
    return FileResponse("index.html")

@app.get("/flood_clipped.geojson")
async def get_flood_data():
    path = "flood_clipped.geojson"
    if os.path.exists(path):
        return FileResponse(path)
    return {"error": "Flood data not found. Run main.py first."}

@app.get("/qc_boundary.geojson")
async def get_boundary_data():
    path = "qc_boundary.geojson"
    if os.path.exists(path):
        return FileResponse(path)
    return {"error": "Boundary data not found. Run main.py first."}

@app.get("/qc_roads.geojson")
async def get_roads_data():
    path = "qc_roads.geojson"
    if os.path.exists(path):
        return FileResponse(path)
    return {"error": "Road data not found. Run main.py first."}

@app.get("/project8_boundary.geojson")
async def get_project8_boundary_data():
    path = "district1_boundary.geojson"
    if os.path.exists(path):
        return FileResponse(path)
    return {"error": "District 1 boundary data not found. Run main.py first."}

@app.get("/project8_roads.geojson")
async def get_project8_roads_data():
    path = "district1_roads.geojson"
    if os.path.exists(path):
        return FileResponse(path)
    return {"error": "District 1 road data not found. Run main.py first."}

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
    uvicorn.run(app, host="0.0.0.0", port=8909)
