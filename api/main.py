"""
api.main
--------
FastAPI application entrypoint.

Run locally:
    uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

The app does NOTHING domain-specific here. All logic is in core.engine.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.auth_routes import router as auth_router
from api.history_routes import router as history_router
from api.routes import router
from core.config import get_settings
from core.db import get_conn  # triggers schema init
from core.logging_setup import get_logger, setup_logging

setup_logging()
log = get_logger(__name__)

app = FastAPI(
    title="AI Interview Platform",
    version="1.1.0",
    description=(
        "Domain-aware, experience-calibrated AI interviewer. "
        "CLI and Web UI share the same Core Engine. "
        "LLM router: Gemini → OpenRouter (auto-discovery + meta-routers)."
    ),
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All API routes live under /api/v1
app.include_router(router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(history_router, prefix="/api/v1")


@app.on_event("startup")
def _on_startup() -> None:
    # Try to initialise the DB. If it fails (e.g., DATABASE_URL not yet
    # set on first deploy), DON'T crash the worker — log loudly and let
    # /api/v1/health still return 200 so platform health checks pass and
    # the operator can fix env vars without rebuilding.
    try:
        get_conn()
    except Exception as e:
        log.error(
            "DB initialization failed at startup — set DATABASE_URL and redeploy. Error: %s",
            e,
        )
    log.info(
        "API starting on %s:%d (gemini=%s, openrouter=%s, db=%s)",
        settings.api.host, settings.api.port,
        bool(settings.llm.gemini_api_key),
        bool(settings.llm.openrouter_api_key),
        settings.storage.database_url,
    )


# ---------------------------------------------------------------------------
# Static frontend (optional — set SERVE_FRONTEND=1 and place a built React
# app at $FRONTEND_DIST_DIR, default ./frontend_dist, to serve the UI from
# the same origin as the API).
# ---------------------------------------------------------------------------

_serve_frontend = os.getenv("SERVE_FRONTEND", "0") in ("1", "true", "True")
_dist_dir = Path(os.getenv("FRONTEND_DIST_DIR", "./frontend_dist")).resolve()

if _serve_frontend and _dist_dir.is_dir():
    log.info("Serving frontend from %s", _dist_dir)

    # /assets/* → static files; everything else falls through to API or SPA.
    app.mount("/assets", StaticFiles(directory=_dist_dir / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def _spa_root():
        return FileResponse(_dist_dir / "index.html")

    # SPA fallback: any non-API path returns index.html so client-side
    # routing works on refresh.
    @app.get("/{full_path:path}", include_in_schema=False)
    def _spa_fallback(full_path: str):
        # API and docs routes are handled by FastAPI before this fires.
        candidate = _dist_dir / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_dist_dir / "index.html")

else:
    @app.get("/", tags=["meta"])
    def root():
        return {
            "name": "AI Interview Platform",
            "docs": "/docs",
            "health": "/api/v1/health",
        }
