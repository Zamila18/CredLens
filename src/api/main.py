"""FastAPI application.

Purpose: the only door between the React dashboard and the data. Consent,
    roles, audit and the no-auto-decision rule are enforced here.
Owner role: D (full-stack).
Implements: PROJECT_BRIEF section 8. Phase 0 has only GET /health; the other
    endpoints arrive in Phase 9.

Run with: python tasks.py api   (then open http://localhost:8000/docs)
"""

from __future__ import annotations

from fastapi import FastAPI

from src.api.routes_decisions import router as decisions_router
from src.api.routes_merchants import router as merchants_router
from src.api.schemas import HealthResponse
from src.config import banner_text, load_config

app = FastAPI(
    title="CredLens API",
    description="Explainable merchant readiness for lenders. Decision support only.",
    version="0.1.0",
)
app.include_router(merchants_router)
app.include_router(decisions_router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Say the API is up, which data mode is active, and the banner to display."""
    mode = load_config()["data"]["mode"]
    return HealthResponse(status="ok", data_mode=mode, banner=banner_text(mode))
