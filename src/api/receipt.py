"""The merchant's data receipt: what CredLens holds about one shop created in the app.

Purpose: give the retailer a readable record of what was recorded about their shop, how
    and when, so they can spot a mistake and say so.
Owner role: D (full-stack).
Implements: implementation pack, Phase 8.1.

What it holds: the shop's reference, every consent answer (marked simulated), and every
record entered for the shop with its source category, entry method, status, business date
and real entry time. What it never holds: a score, a decision, any officer's note (visit
notes and application notes are left out), anything about another shop, or a claim that a
record came from a provider.

Only staff open it (officers, inside the app); there is no merchant login and no public link.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.schemas import MerchantSummary, Receipt, ReceiptConsent, ReceiptRecord
from src.db import models as db
from src.intake.policy import utc_now

# record type -> (table, id column, amount shown, detail code shown)
_TABLES = {
    "purchase": (db.Purchase, "purchase_id", lambda r: r.amount_bdt, lambda r: r.category),
    "delivery": (db.Delivery, "delivery_id", lambda r: None, lambda r: r.status),
    "payment": (db.Payment, "payment_id", lambda r: r.amount_paid_bdt, lambda r: None),
    "visit": (db.Visit, "visit_id", lambda r: None, lambda r: r.outcome),
    "application": (
        db.Application, "application_id", lambda r: r.requested_amount_bdt, lambda r: r.purpose
    ),
}


def build_receipt(
    session: Session, config: dict[str, Any], merchant: MerchantSummary
) -> Receipt:
    """The receipt of one shop, from its consent events and its provenance rows."""
    merchant_id = merchant.merchant_id
    events = session.scalars(
        select(db.ConsentEvent)
        .where(db.ConsentEvent.merchant_id == merchant_id)
        .order_by(db.ConsentEvent.recorded_at)
    ).all()
    consent = [
        ReceiptConsent(
            response=e.response,
            categories=[c for c in e.categories.split("|") if c],
            method=e.method,
            wording_version=e.wording_version,
            business_date=e.business_date.isoformat(),
            recorded_at=e.recorded_at.isoformat(timespec="seconds"),
            simulated=e.simulated,
        )
        for e in events
    ]

    # The latest provenance row of each record (a change of status is a new row).
    latest: dict[tuple[str, str], db.RecordProvenance] = {}
    for row in session.scalars(
        select(db.RecordProvenance)
        .where(db.RecordProvenance.merchant_id == merchant_id)
        .order_by(db.RecordProvenance.provenance_id)
    ):
        if row.record_type != "consent":
            latest[(row.record_type, row.record_id)] = row

    records = []
    for (kind, record_id), row in latest.items():
        amount = detail = None
        if kind in _TABLES:
            model, _, amount_of, detail_of = _TABLES[kind]
            saved = session.get(model, record_id)
            if saved is None:
                continue  # never list what is not stored
            amount, detail = amount_of(saved), detail_of(saved)
        records.append(
            ReceiptRecord(
                record_type=kind,
                business_date=row.business_date.isoformat() if row.business_date else None,
                amount_bdt=amount,
                detail=detail,
                source_category=row.source_category,
                entry_method=row.entry_method,
                status=row.status,
                entered_at=row.entered_at.isoformat(timespec="seconds"),
            )
        )
    records.sort(key=lambda r: (r.business_date or "", r.entered_at))
    return Receipt(
        merchant=merchant,
        generated_at=utc_now().isoformat(timespec="seconds"),
        calendar_end=config["demo"]["calendar_end"],
        consent=consent,
        records=records,
    )
