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
    """Merchants in the database that are not in the original data: the imported ones.

    Only sandbox merchants. A real organisation's merchants are never given to the scorer:
    the model is trained on synthetic data and its "today" is the synthetic calendar, so its
    numbers would mean nothing for them (see `real_organization_ids`).
    """
    real = real_organization_ids(session)
    rows = session.execute(select(db.Merchant.merchant_id, db.Merchant.organization_id)).all()
    return sorted(m for m, org in rows if m not in source and org not in real)


def refresh_real(services: Any, session: Session) -> list[str]:
    """Give the scorer every real organisation's shops, scored as of today's real date.

    Like `refresh_imported`, but for pilot and production organisations. A shop whose
    records cannot be read is listed in `scorer.not_updated`, so no stale score shows.
    """
    from src.intake.policy import real_today

    scorer = services.scorer
    if scorer is None:
        return []
    real = real_organization_ids(session)
    if not real:
        scorer.set_real(None, None)
        return []
    ids = list(
        session.scalars(
            select(db.Merchant.merchant_id).where(db.Merchant.organization_id.in_(real))
        )
    )
    today = real_today(services.config)
    try:
        return scorer.set_real(tables_for_merchants(session, ids) if ids else None, today)
    except Exception:  # noqa: BLE001 - try one by one, as refresh_imported does
        log.exception("Real shops could not be scored together; trying one by one")
    from src.model.dataset import build_dataset

    usable = []
    for merchant_id in ids:
        try:
            build_dataset(
                tables_for_merchants(session, [merchant_id]),
                scorer.config,
                as_of=today,
                mode=scorer.mode,
            )
            usable.append(merchant_id)
        except Exception as error:  # noqa: BLE001 - recorded per merchant
            scorer.not_updated[merchant_id] = type(error).__name__
    return scorer.set_real(tables_for_merchants(session, usable) if usable else None, today)


def real_organization_ids(session: Session) -> set[str]:
    """Organisations that are not the reserved benchmark organisation (pilot or production)."""
    return set(
        session.scalars(
            select(db.Organization.organization_id).where(
                db.Organization.environment != "benchmark"
            )
        )
    )


def _value(value: Any) -> Any:
    """Dates and times as ISO text, like the generated CSV files the pipeline reads."""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def tables_for_merchants(session: Session, merchant_ids: list[str]) -> dict[str, pd.DataFrame]:
    """The seven contract tables, holding only these merchants' rows."""
    from src.receipts.service import disputed_record_ids

    # A line the merchant has reported as wrong stays out of the score until it is answered.
    held_out = disputed_record_ids(session, merchant_ids)
    tables: dict[str, pd.DataFrame] = {}
    for name, model in MODELS.items():
        columns = CONTRACT[name]
        rows: list[dict[str, Any]] = []
        ids = {"purchases": "purchase_id", "deliveries": "delivery_id", "payments": "payment_id"}
        key = ids.get(name)
        for start in range(0, len(merchant_ids), BATCH):
            chunk = merchant_ids[start : start + BATCH]
            found = session.scalars(select(model).where(model.merchant_id.in_(chunk))).all()
            rows += [
                {c: _value(getattr(r, c)) for c in columns}
                for r in found
                if not (key and getattr(r, key) in held_out)
            ]
        tables[name] = check_frame(name, pd.DataFrame(rows, columns=columns))
    return tables


def refresh_imported(services: Any, session: Session) -> list[str]:
    """Give the scorer every imported merchant. Returns those that can now be scored.

    Does nothing when the scorer is not ready. The records are already saved whatever
    happens here. Every merchant created or imported so far is read again, not only the
    latest one, so earlier records are never dropped.

    If the merchants cannot all be scored together, each one is tried on its own: the ones
    that work are scored, and the ones that do not are left out and listed in
    `scorer.not_updated` (merchant id -> kind of problem). The API then answers
    "assessment not updated" for them instead of an older score. If even that fails, every
    imported merchant is listed, so no stale score is ever shown as current.
    """
    scorer = services.scorer
    if scorer is None:
        return []
    try:
        ids = imported_merchant_ids(session, scorer.source_merchant_ids())
    except Exception:  # noqa: BLE001 - the records stay saved; say so and stop
        log.exception("The imported merchants could not be listed")
        return []
    try:
        scored = scorer.set_imported(tables_for_merchants(session, ids) if ids else None)
        scorer.not_updated = {}
        return scored
    except Exception:  # noqa: BLE001 - find which merchants cause it
        log.exception("Imported merchants could not be scored together; trying one by one")

    from src.model.dataset import build_dataset

    usable, failed = [], {}
    for merchant_id in ids:
        try:
            tables = tables_for_merchants(session, [merchant_id])
            build_dataset(tables, scorer.config, as_of=scorer.as_of, mode=scorer.mode)
            usable.append(merchant_id)
        except Exception as error:  # noqa: BLE001 - recorded per merchant
            failed[merchant_id] = type(error).__name__
    try:
        scored = scorer.set_imported(tables_for_merchants(session, usable) if usable else None)
    except Exception:  # noqa: BLE001 - nothing can be trusted as current
        log.exception("Imported merchants could not be scored")
        scorer.not_updated = dict.fromkeys(ids, "refresh_failed")
        return []
    scorer.not_updated = failed
    return scored


def refresh_scoring(services: Any, session: Session) -> None:
    """After records or a consent changed: give the scorer the current state for the caller's
    side (the benchmark organisation's synthetic shops, or the real companies')."""
    from src.intake.policy import benchmark_request

    if benchmark_request():
        services.forget_data_today()
        refresh_imported(services, session)
    else:
        refresh_real(services, session)
