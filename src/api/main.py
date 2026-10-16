"""FastAPI application.

Purpose: the only door between the React dashboard and the data. Consent,
    roles, audit and the no-auto-decision rule are enforced here.
Owner role: D (full-stack).
Implements: PROJECT_BRIEF section 8 and docs/HANDOVER.md Part E.

Endpoints (who may call): see the module docstrings of routes_merchants.py,
routes_decisions.py and routes_admin.py. Roles come from the demo header token in auth.py.

Run with: python tasks.py api   (then open http://localhost:8000/docs)
The scorer is built once at start-up, which takes about half a minute.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.auth import TOKEN_HEADER
from src.api.routes_admin import router as admin_router
from src.api.routes_consents import router as consents_router
from src.api.routes_decisions import router as decisions_router
from src.api.routes_merchants import router as merchants_router
from src.api.schemas import HealthResponse
from src.api.state import build_services
from src.config import banner_text, load_config

# The React dev server (Vite). Set CREDLENS_CORS_ORIGINS (comma separated) for another origin.
CORS_ENV_VAR = "CREDLENS_CORS_ORIGINS"
DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the scorer and open the database once, when the API starts."""
    app.state.services = build_services()
    yield
    app.state.services.engine.dispose()


app = FastAPI(
    title="CredLens API",
    description="Explainable merchant readiness for lenders. Decision support only.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.environ.get(CORS_ENV_VAR, DEFAULT_CORS_ORIGINS).split(",")
        if origin.strip()
    ],
    allow_methods=["GET", "POST"],
    allow_headers=[TOKEN_HEADER, "Content-Type"],
)
app.include_router(merchants_router)
app.include_router(consents_router)
app.include_router(decisions_router)
app.include_router(admin_router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Say the API is up, which data mode is active, and the banner to display."""
    mode = load_config()["data"]["mode"]
    return HealthResponse(status="ok", data_mode=mode, banner=banner_text(mode))
