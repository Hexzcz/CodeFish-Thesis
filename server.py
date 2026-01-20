from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os

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
    path = "project8_boundary.geojson"
    if os.path.exists(path):
        return FileResponse(path)
    return {"error": "Project 8 boundary data not found. Run main.py first."}

@app.get("/project8_roads.geojson")
async def get_project8_roads_data():
    path = "project8_roads.geojson"
    if os.path.exists(path):
        return FileResponse(path)
    return {"error": "Project 8 road data not found. Run main.py first."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8909)
