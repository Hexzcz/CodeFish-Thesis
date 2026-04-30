from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from backend.core.startup import startup
from backend.api import routes, layers, network, centers, rainfall
import os

# Base directory for static files (frontend)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize logic
    state_data = await startup()
    app.state.data = state_data
    yield
    # Cleanup logic
    app.state.data.clear()

app = FastAPI(title="CodeFish Flood-Aware Evacuation Routing", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(routes.router)
app.include_router(layers.router)
app.include_router(network.router)
app.include_router(centers.router)
app.include_router(rainfall.router)

# Mount frontend as static files
# Ensure frontend directory exists
if not os.path.exists(FRONTEND_DIR):
    os.makedirs(FRONTEND_DIR, exist_ok=True)

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
