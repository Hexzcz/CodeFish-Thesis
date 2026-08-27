from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from backend.core.logging import configure_logging, get_logger
from backend.core.startup import startup
from backend.api import routes, layers, network, centers, rainfall, geocode, navigation
import os

# Base directory for static files (frontend)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

configure_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize logic
    state_data = await startup()
    app.state.data = state_data
    yield
    # Cleanup logic
    app.state.data.clear()

class GZipExceptTiles:
    """gzip the data, leave the pictures alone.

    The road network compresses from 1.7 MB to about 265 KB, which on mobile
    data is the difference that matters. Map tiles are PNGs — already
    compressed, and the most-requested thing here — so spending CPU trying to
    compress them again on every pan would be a cost with no benefit.
    """

    def __init__(self, app, **options):
        self.compressed = GZipMiddleware(app, **options)
        self.plain = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and scope.get("path", "").startswith("/tiles/"):
            await self.plain(scope, receive, send)
        else:
            await self.compressed(scope, receive, send)


app = FastAPI(title="CodeFish Flood-Aware Evacuation Routing", lifespan=lifespan)

app.add_middleware(GZipExceptTiles, minimum_size=1024)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # No cookies, no auth headers: nothing here is credentialed, and "*" with
    # credentials is a combination browsers refuse anyway.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(routes.router)
app.include_router(layers.router)
app.include_router(network.router)
app.include_router(centers.router)
app.include_router(rainfall.router)
app.include_router(geocode.router)
app.include_router(navigation.router)

# Mount frontend as static files
# Ensure frontend directory exists
if not os.path.exists(FRONTEND_DIR):
    os.makedirs(FRONTEND_DIR, exist_ok=True)

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
