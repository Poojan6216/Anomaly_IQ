"""
AnomalyIQ FastAPI application entry point.
Uses the modern lifespan context manager (replaces deprecated @app.on_event).
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

_CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")


# ---------------------------------------------------------------------------
# Lifespan — startup + shutdown in one place
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ──────────────────────────────────────────────────────────
    logger.info("AnomalyIQ backend starting up…")

    # 1. Connect to MongoDB
    from backend.database.mongodb import connect_db
    connect_db()
    logger.info("MongoDB connected.")

    # 2. Register the running event loop so background threads can broadcast
    #    WebSocket events via asyncio.run_coroutine_threadsafe()
    from backend.api.websocket import set_main_loop
    set_main_loop(asyncio.get_event_loop())
    logger.info("WebSocket event loop registered.")

    # 3. Start the background agent scheduler
    from backend.agents.scheduler import start_scheduler
    start_scheduler()
    logger.info("Task scheduler started.")

    # 4. Launch the WebSocket heartbeat coroutine
    from backend.api.websocket import _heartbeat_loop
    heartbeat_task = asyncio.create_task(_heartbeat_loop())
    logger.info("WebSocket heartbeat started.")

    logger.info("AnomalyIQ is ready — docs at /docs")

    yield  # ── application runs here ──

    # ── SHUTDOWN ─────────────────────────────────────────────────────────
    logger.info("AnomalyIQ backend shutting down…")

    heartbeat_task.cancel()

    from backend.agents.scheduler import stop_scheduler
    stop_scheduler()

    from backend.database.mongodb import disconnect_db
    disconnect_db()

    logger.info("Shutdown complete.")


# ---------------------------------------------------------------------------
# App initialisation
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AnomalyIQ — AWS Cost Guardian",
    version="1.0.0",
    description=(
        "Multi-agent AI system for real-time AWS cost anomaly detection, "
        "root-cause analysis, forecasting, and recommendations."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

from backend.api.routes import router as api_router        # noqa: E402
from backend.api.gcp_routes import router as gcp_router    # noqa: E402
from backend.api.websocket import router as ws_router      # noqa: E402

app.include_router(api_router)
app.include_router(gcp_router)
app.include_router(ws_router)


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": "AnomalyIQ AWS Cost Guardian",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
        "websocket": "/ws",
    }
