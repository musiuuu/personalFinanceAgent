"""FastAPI entrypoint.

Dev:  uvicorn app.main:app --reload          (API only; Vite serves the UI)
Prod: a single container serves BOTH the API (under /api) and the built React
app (at /), so the whole demo is one origin and one URL — no CORS, no second
deploy. See the repo Dockerfile.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import chat, dashboard, goals, ingest
from .config import get_settings
from .db import init_db
from .seed import seed_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_if_empty()
    yield


app = FastAPI(
    title="Personal Finance Agent",
    description="LLM plans, routes and explains; a deterministic engine computes.",
    lifespan=lifespan,
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API lives under /api so it can coexist with the SPA served at /.
app.include_router(ingest.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(goals.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}


# Serve the built frontend in production (mounted last so API routes win).
_dist = settings.frontend_dist or str(
    Path(__file__).resolve().parents[2] / "frontend" / "dist"
)
if Path(_dist).is_dir():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="spa")
