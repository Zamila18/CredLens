"""FastAPI application.

Purpose: the only door between the React dashboard and the data. Consent,
    roles, audit and the no-auto-decision rule are enforced here.
Owner role: D (full-stack).
Implements: PROJECT_BRIEF section 8 and docs/HANDOVER.md Part E.

Endpoints (who may call): see the module docstrings of routes_merchants.py,
routes_decisions.py, routes_consents.py and routes_admin.py. Roles come from the demo header
token in auth.py. Two endpoints need no token: GET /health (which data mode, which banner)
and GET /ready (can the API answer yet).

Settings from the environment (a server sets them in its .env, see deploy/env.template):
- CREDLENS_ENV=production   no /docs, /redoc or /openapi.json (they list every endpoint).
- CREDLENS_CORS_ORIGINS     the origins that may call the API from a browser, comma separated.
                            Empty: none. Behind Nginx the dashboard and the API share one
                            address, so a server needs none.
- CREDLENS_DATA_MODE        the data mode (config/default.yaml has the default).

Run with: python tasks.py api   (then open http://localhost:8000/docs)
The scorer is built once at start-up, which takes about half a minute. The port does not
answer until it has finished: wait for GET /ready (deploy/wait_for_api.py does).
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.auth import TOKEN_HEADER
from src.api.routes_admin import router as admin_router
from src.api.routes_consents import router as consents_router
from src.api.routes_decisions import router as decisions_router
from src.api.routes_merchants import router as merchants_router
from src.api.schemas import HealthResponse, ReadyResponse
from src.api.state import Services, build_services
from src.config import banner_text, load_config

# The React dev server (Vite). Set CREDLENS_CORS_ORIGINS (comma separated) for another origin.
CORS_ENV_VAR = "CREDLENS_CORS_ORIGINS"
DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
ENV_VAR = "CREDLENS_ENV"
PRODUCTION = "production"
CHECK_HINT = "Run on the server: python -m src.api.preflight --server"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the scorer and open the database once, when the API starts."""
    app.state.services = build_services()
    yield
    app.state.services.engine.dispose()


def cors_origins_from_environment() -> list[str]:
    """The origins that may call the API from a browser. An empty setting means none."""
    raw = os.environ.get(CORS_ENV_VAR, DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def not_ready_problems(services: Services | None) -> list[str]:
    """Plain reasons the API cannot answer yet. The details are in the server log only."""
    if services is None:
        return ["The API is still starting."]
    problems = []
    if services.database_error:
        problems.append(f"The database is not ready. {CHECK_HINT}")
    if services.scorer is None:
        problems.append(f"The scorer is not ready. {CHECK_HINT}")
    return problems


def create_app(production: bool = False, cors_origins: list[str] | None = None) -> FastAPI:
    """Build the API. `production` switches off the pages that list every endpoint."""
    app = FastAPI(
        title="CredLens API",
        description="Explainable merchant readiness for lenders. Decision support only.",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins_from_environment() if cors_origins is None else cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=[TOKEN_HEADER, "Content-Type"],
        expose_headers=["X-Total-Count"],
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

    @app.get("/ready", response_model=ReadyResponse, responses={503: {"model": ReadyResponse}})
    def ready() -> ReadyResponse | JSONResponse:
        """200 when the database is open and the scorer is built; 503 and the reason if not.

        Needs no token. Says nothing that is not already public: no paths, no addresses.
        """
        services: Services | None = getattr(app.state, "services", None)
        problems = not_ready_problems(services)
        answer = ReadyResponse(
            ready=not problems,
            scorer=bool(services and services.scorer),
            database=bool(services and not services.database_error),
            model_version=services.scorer.model_version if services and services.scorer else None,
            problems=problems,
        )
        if problems:
            return JSONResponse(status_code=503, content=answer.model_dump())
        return answer

    return app


app = create_app(production=os.environ.get(ENV_VAR, "").strip().lower() == PRODUCTION)
