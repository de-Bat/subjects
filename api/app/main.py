"""FastAPI app: mounts every router, runs migrations on startup, initializes search index."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import categories, events, ingest, items, search, settings
from .db import run_migrations

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_migrations()
    try:
        from .services.search import ensure_index

        await ensure_index()
    except Exception as exc:
        log.warning("meilisearch index init skipped: %s", exc)
    yield


app = FastAPI(title="Subjects", version="0.1.0", lifespan=lifespan)

# Single-user LAN app; extension + PWA + iOS Shortcut post cross-origin. Auth is the guard.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (ingest.router, items.router, categories.router, events.router,
               search.router, settings.router):
    app.include_router(router, prefix="/api")


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
