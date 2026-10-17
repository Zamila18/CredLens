"""What the API keeps in memory while it runs: config, database engine, scorer.

Purpose: build the `Scorer` ONCE when the API starts (it takes about half a minute because
    it builds the feature table) and hand it, with a database session, to the endpoints.
Owner role: D (full-stack).
Implements: docs/HANDOVER.md "What the API can call for real scores".

If the data or the trained model is missing the API still starts, so `/health` works.
The endpoints that need the missing part answer 503 and say which command to run.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
from fastapi import Depends, Request
from sqlalchemy import func, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src.api.common import api_error
from src.config import get_database_url, load_config
from src.db import models as db
from src.model.scoring import Scorer

log = logging.getLogger("credlens.api")


@dataclass
class Services:
    """Everything the endpoints share. Created once, at start-up."""

    config: dict[str, Any]
    engine: Engine
    scorer: Scorer | None = None
    scorer_error: str | None = None
    database_error: str | None = None
    _data_today: date | None = None

    def data_today(self, session: Session) -> date:
        """The last day anything happened in the data: "today" for the data.

        The same rule as `src.model.labels.latest_date`, read from the database, so that
        "is this consent valid" gives the same answer here as in the review queue.
        """
        if self._data_today is None:
            columns = (
                db.Purchase.purchase_date,
                db.Delivery.dispatched_at,
                db.Loan.issued_at,
                db.Payment.paid_date,
            )
            days = [session.scalar(select(func.max(column))) for column in columns]
            days = [pd.Timestamp(day).date() for day in days if day is not None]
            self._data_today = max(days) if days else date.today()
        return self._data_today

    def forget_data_today(self) -> None:
        """Call after rows were imported: the last day may have moved."""
        self._data_today = None


def build_services(config: dict[str, Any] | None = None) -> Services:
    """Open the database and build the scorer. Problems are recorded, not raised."""
    config = config or load_config()
    engine = db.make_engine(get_database_url(config))
    services = Services(config=config, engine=engine)

    if not inspect(engine).has_table("users"):
        services.database_error = (
            "The database is empty. Create it with: python tasks.py data"
        )
    if services.database_error is None:
        # Read the last day of the data now, so the first profile request is not the slow one.
        with Session(engine) as session:
            services.data_today(session)
    try:
        services.scorer = Scorer(config)
        if services.database_error is None:
            # Merchants imported before a restart are scored again (src/api/imported.py).
            from src.api.imported import refresh_imported

            with Session(engine) as session:
                refresh_imported(services, session)
    except Exception as error:  # noqa: BLE001 - the API must still start so /health works
        log.exception("The scorer could not be built")
        services.scorer_error = (
            f"The scorer is not ready ({type(error).__name__}: {error}). "
            "Run: python tasks.py data, then python tasks.py train, then start the API again."
        )
    return services


def get_services(request: Request) -> Services:
    """The shared services; 503 when the app was started without them."""
    services = getattr(request.app.state, "services", None)
    if services is None:
        raise api_error(503, "not_started", "The API has not finished starting.")
    return services


def get_scorer(services: Services = Depends(get_services)) -> Scorer:
    """The scorer built at start-up; 503 if it could not be built."""
    if services.scorer is None:
        raise api_error(
            503, "scorer_not_ready", services.scorer_error or "The scorer is not ready."
        )
    return services.scorer


def get_session(services: Services = Depends(get_services)):
    """One database session per request."""
    if services.database_error:
        raise api_error(503, "database_not_ready", services.database_error)
    with Session(services.engine) as session:
        yield session
