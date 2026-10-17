"""Merchants added by an import: read their records from the database and score them.

Purpose: a lender's file of NEW merchants (merchants, loans, purchases, deliveries, payments,
    questionnaire, consents) is checked and loaded by the import; this module then gives
    those merchants to the scorer, so they appear in the review queue with a score.
Owner role: D (full-stack), with the lead.
Implements: the live import demo (PROJECT_BRIEF section 18, item 45).

What it does and does not do:
- The model is NOT retrained. The saved model and the same feature rules are applied to the
  new merchants' own records, as of the same "today" as the rest of the data.
- Only merchants that are not in the original data are read here. The original merchants'
  history comes from the source systems and may not be changed by an import (Phase 13, F10).
- It runs after every import that loads rows, and once when the API starts, so imported
  merchants survive a restart.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.adapters.base import CONTRACT, check_frame
from src.db import models as db

log = logging.getLogger("credlens.api")

# The database table behind each contract table.
MODELS = {
    "merchants": db.Merchant,
    "purchases": db.Purchase,
    "deliveries": db.Delivery,
    "payments": db.Payment,
    "loans": db.Loan,
    "questionnaire": db.Questionnaire,
    "consents": db.Consent,
}
BATCH = 500


def imported_merchant_ids(session: Session, source: frozenset[str] | set[str]) -> list[str]:
    """Merchants in the database that are not in the original data: the imported ones."""
    ids = session.scalars(select(db.Merchant.merchant_id)).all()
    return sorted(m for m in ids if m not in source)


def _value(value: Any) -> Any:
    """Dates and times as ISO text, like the generated CSV files the pipeline reads."""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def tables_for_merchants(session: Session, merchant_ids: list[str]) -> dict[str, pd.DataFrame]:
    """The seven contract tables, holding only these merchants' rows."""
    tables: dict[str, pd.DataFrame] = {}
    for name, model in MODELS.items():
        columns = CONTRACT[name]
        rows: list[dict[str, Any]] = []
        for start in range(0, len(merchant_ids), BATCH):
            chunk = merchant_ids[start : start + BATCH]
            found = session.scalars(select(model).where(model.merchant_id.in_(chunk))).all()
            rows += [{c: _value(getattr(r, c)) for c in columns} for r in found]
        tables[name] = check_frame(name, pd.DataFrame(rows, columns=columns))
    return tables


def refresh_imported(services: Any, session: Session) -> list[str]:
    """Give the scorer every imported merchant. Returns those that can now be scored.

    Does nothing when the scorer is not ready. A failure is logged and leaves the scorer as
    it was: the import itself has already succeeded.
    """
    scorer = services.scorer
    if scorer is None:
        return []
    try:
        ids = imported_merchant_ids(session, scorer.source_merchant_ids())
        tables = tables_for_merchants(session, ids) if ids else None
        return scorer.set_imported(tables)
    except Exception:  # noqa: BLE001 - see the docstring
        log.exception("Imported merchants could not be scored")
        return []
