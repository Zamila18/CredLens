"""Business records typed in by staff: purchases, deliveries and repayments.

Purpose: the "Add records" step of the field workflow.
Owner role: D (full-stack).
Implements: the implementation pack, Phase 3.3.

Each record goes into the same contract table the scorer reads (purchases, deliveries,
payments), with a provenance row saying it was typed in by staff and is not verified, and
an audit entry, all in one transaction. Rules:
- only fields the tables can hold are asked for; product, quantity or sales are not;
- the merchant's valid consent must cover the record's data category;
- a repayment must point at one of the merchant's real earlier loans, never at an
  application (the database refuses that too);
- before anything is saved, the merchant's scoring inputs are built once with the new
  record; if they cannot be built, nothing is saved, so one bad record can never stop the
  assessment of every other merchant;
- the same person saving the same record again within `demo.duplicate_entry_seconds` (a
  double tap) gets the first record back, and nothing is added.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import CurrentUser, add_audit
from src.api.importer import DELIVERY_STATUSES
from src.db import models as db
from src.intake.consent import require_consent_for
from src.intake.policy import (
    IntakeRefused,
    add_provenance,
    calendar_end,
    check_business_date,
    check_choice,
    demo,
    live_merchant,
    new_id,
    require_synthetic_mode,
    utc_now,
)

RETURN_REASONS = ("refused", "wrong_item", "address_issue", "rider_issue", "other")
TEXT_MAX = 32
CATEGORY_MAX = 64


def check_scoring_inputs(session: Session, config: dict[str, Any], merchant_id: str) -> None:
    """Build this merchant's scoring inputs from what is staged in the session.

    Called after the new rows are flushed and before the commit. A merchant without a loan
    or application has nothing to score yet, so there is nothing to check.
    """
    from src.api.imported import tables_for_merchants
    from src.model.dataset import build_dataset

    tables = tables_for_merchants(session, [merchant_id])
    if tables["loans"].empty:
        return
    try:
        build_dataset(tables, config, as_of=calendar_end(config))
    except Exception as error:  # noqa: BLE001 - any failure here means "do not save"
        raise IntakeRefused(
            422,
            "records_not_usable",
            "These records could not be read for the assessment, so nothing was saved. Check "
            "the dates and amounts.",
            problem=type(error).__name__,
        ) from None


def counts_for_assessment(session: Session, merchant_id: str, day: date) -> bool | None:
    """Whether a record of this date can count for the merchant's application.

    The model uses only records dated strictly before the application date. None: there is
    no application yet.
    """
    application = session.scalar(
        select(db.Application).where(db.Application.merchant_id == merchant_id)
    )
    return None if application is None else day < application.business_date


def _recent_same(
    session: Session,
    config: dict[str, Any],
    actor: CurrentUser,
    merchant_id: str,
    record_type: str,
    model,
    key: str,
    values: dict[str, Any],
):
    """The record this person saved with the same values a moment ago, if any."""
    since = utc_now() - timedelta(seconds=demo(config)["duplicate_entry_seconds"])
    recent = session.scalars(
        select(db.RecordProvenance.record_id).where(
            db.RecordProvenance.merchant_id == merchant_id,
            db.RecordProvenance.record_type == record_type,
            db.RecordProvenance.actor == actor.user_id,
            db.RecordProvenance.entered_at >= since,
        )
    ).all()
    for record_id in recent:
        row = session.get(model, record_id)
        if row is not None and all(getattr(row, name) == value for name, value in values.items()):
            return row
    return None


def _id_for(prefix: str, merchant_id: str, reference: str | None) -> str:
    """An id from the merchant and the paper's own reference (so it is recognised again), or new."""
    if not reference:
        return new_id(prefix)
    digest = hashlib.sha256(f"{merchant_id}|{reference.strip().casefold()}".encode()).hexdigest()
    return f"{prefix}-{digest[:24]}"


def _clean_reference(reference: str | None) -> str | None:
    reference = (reference or "").strip() or None
    if reference and len(reference) > TEXT_MAX:
        raise IntakeRefused(
            422, "invalid_reference", f"The reference is longer than {TEXT_MAX} characters."
        )
    return reference


def _save(
    session: Session,
    config: dict[str, Any],
    *,
    row,
    record_type: str,
    record_id: str,
    merchant_id: str,
    category: str,
    business_date: date,
    actor: CurrentUser,
    audit_action: str,
):
    """Write the record, its provenance and its audit entry; check the scoring inputs first."""
    now = utc_now()
    try:
        session.add(row)
        add_provenance(
            session,
            record_type=record_type,
            record_id=record_id,
            merchant_id=merchant_id,
            source_category=category,
            entry_method="staff_entered",
            status="staff_entered",
            actor=actor.user_id,
            entered_at=now,
            business_date=business_date,
        )
        session.flush()
        check_scoring_inputs(session, config, merchant_id)
        add_audit(session, actor, audit_action, merchant_id)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return row


def record_purchase(
    session: Session,
    config: dict[str, Any],
    *,
    merchant_id: str,
    purchase_date: date,
    amount_bdt: float,
    category: str | None,
    supplier_reference: str | None,
    invoice_reference: str | None,
    actor: CurrentUser,
    protected_merchants: frozenset[str] | set[str],
) -> tuple[db.Purchase, bool]:
    """Save a stock purchase. Returns (purchase, True when it was a repeat of a moment ago)."""
    require_synthetic_mode(config)
    check_business_date(purchase_date, config, "The purchase date")
    if not _is_amount(amount_bdt) or amount_bdt <= 0:
        raise IntakeRefused(422, "invalid_amount", "The amount must be more than 0 taka.")
    category = (category or "").strip() or None
    if category and len(category) > CATEGORY_MAX:
        raise IntakeRefused(
            422, "invalid_category", f"The item type is longer than {CATEGORY_MAX} characters."
        )
    supplier = _clean_reference(supplier_reference)
    reference = _clean_reference(invoice_reference)
    live_merchant(session, merchant_id, protected_merchants)
    require_consent_for(session, config, merchant_id, "purchases")

    values = {"purchase_date": purchase_date, "amount_bdt": float(amount_bdt), "category": category}
    earlier = _recent_same(
        session, config, actor, merchant_id, "purchase", db.Purchase, "purchase_id", values
    )
    purchase_id = _id_for("PU", merchant_id, reference)
    # A double tap is the same paper again: a different memo number is a different purchase.
    if earlier is not None and (not reference or earlier.purchase_id == purchase_id):
        return earlier, True
    if reference and session.get(db.Purchase, purchase_id) is not None:
        raise IntakeRefused(
            409,
            "duplicate_reference",
            f"A purchase with the reference {reference!r} is already saved.",
        )
    row = db.Purchase(
        purchase_id=purchase_id,
        merchant_id=merchant_id,
        purchase_date=purchase_date,
        amount_bdt=float(amount_bdt),
        category=category,
        supplier_id=supplier,
    )
    _save(
        session,
        config,
        row=row,
        record_type="purchase",
        record_id=purchase_id,
        merchant_id=merchant_id,
        category="purchases",
        business_date=purchase_date,
        actor=actor,
        audit_action="record_purchase",
    )
    return row, False


def record_delivery(
    session: Session,
    config: dict[str, Any],
    *,
    merchant_id: str,
    dispatched_at: datetime,
    delivered_at: datetime | None,
    status: str,
    return_reason: str | None,
    is_cod: bool,
    cod_remitted_on_time: bool | None,
    parcel_reference: str | None,
    actor: CurrentUser,
    protected_merchants: frozenset[str] | set[str],
) -> tuple[db.Delivery, bool]:
    """Save one of the merchant's own parcels. Returns (delivery, repeat flag)."""
    require_synthetic_mode(config)
    check_business_date(dispatched_at.date(), config, "The dispatch date")
    check_choice(status, list(DELIVERY_STATUSES), "The delivery status")
    if status == "delivered":
        if delivered_at is None:
            raise IntakeRefused(422, "invalid_dates", "A delivered parcel needs its delivery date.")
    elif delivered_at is not None:
        raise IntakeRefused(422, "invalid_dates", "Only a delivered parcel has a delivery date.")
    if delivered_at is not None:
        check_business_date(delivered_at.date(), config, "The delivery date")
        if delivered_at < dispatched_at:
            raise IntakeRefused(422, "invalid_dates", "A parcel cannot arrive before it was sent.")
    if status in ("returned", "failed"):
        if return_reason is not None:
            check_choice(return_reason, list(RETURN_REASONS), "The reason")
    elif return_reason is not None:
        raise IntakeRefused(422, "invalid_choice", "Only a returned or failed parcel has a reason.")
    if not is_cod and cod_remitted_on_time is not None:
        raise IntakeRefused(
            422, "invalid_choice", "Cash-on-delivery timing applies only to COD parcels."
        )
    reference = _clean_reference(parcel_reference)
    live_merchant(session, merchant_id, protected_merchants)
    require_consent_for(session, config, merchant_id, "deliveries")

    values = {"dispatched_at": dispatched_at, "status": status, "is_cod": bool(is_cod)}
    earlier = _recent_same(
        session, config, actor, merchant_id, "delivery", db.Delivery, "delivery_id", values
    )
    if earlier is not None:
        return earlier, True
    delivery_id = _id_for("DE", merchant_id, reference)
    if reference and session.get(db.Delivery, delivery_id) is not None:
        raise IntakeRefused(
            409,
            "duplicate_reference",
            f"A parcel with the reference {reference!r} is already saved.",
        )
    row = db.Delivery(
        delivery_id=delivery_id,
        merchant_id=merchant_id,
        dispatched_at=dispatched_at,
        delivered_at=delivered_at,
        status=status,
        return_reason=return_reason,
        is_cod=bool(is_cod),
        cod_remitted_on_time=cod_remitted_on_time if is_cod else None,
    )
    _save(
        session,
        config,
        row=row,
        record_type="delivery",
        record_id=delivery_id,
        merchant_id=merchant_id,
        category="deliveries",
        business_date=dispatched_at.date(),
        actor=actor,
        audit_action="record_delivery",
    )
    return row, False


def record_repayment(
    session: Session,
    config: dict[str, Any],
    *,
    merchant_id: str,
    loan_id: str,
    due_date: date,
    paid_date: date | None,
    amount_due_bdt: float,
    amount_paid_bdt: float,
    actor: CurrentUser,
    protected_merchants: frozenset[str] | set[str],
) -> tuple[db.Payment, bool]:
    """Save an instalment of one of the merchant's real earlier loans. Returns (payment, repeat)."""
    require_synthetic_mode(config)
    check_business_date(due_date, config, "The due date")
    if paid_date is not None:
        check_business_date(paid_date, config, "The payment date")
    if not _is_amount(amount_due_bdt) or amount_due_bdt <= 0:
        raise IntakeRefused(422, "invalid_amount", "The amount due must be more than 0 taka.")
    if not _is_amount(amount_paid_bdt) or not 0 <= amount_paid_bdt <= amount_due_bdt:
        raise IntakeRefused(
            422, "invalid_amount", "The amount paid must be between 0 and the amount due."
        )
    if paid_date is None and amount_paid_bdt > 0:
        raise IntakeRefused(
            422, "invalid_dates", "A payment with an amount needs its payment date."
        )
    live_merchant(session, merchant_id, protected_merchants)
    loan = session.get(db.Loan, loan_id)
    if loan is None or loan.merchant_id != merchant_id:
        raise IntakeRefused(
            422, "wrong_loan", "Choose one of this merchant's own loans for the repayment."
        )
    if session.scalar(select(db.Application.loan_id).where(db.Application.loan_id == loan_id)):
        raise IntakeRefused(
            422,
            "application_not_loan",
            "This is an application, not an issued loan: a repayment cannot be recorded "
            "against it.",
        )
    if due_date < loan.issued_at:
        raise IntakeRefused(
            422, "invalid_dates", "The due date cannot be before the loan was issued."
        )
    require_consent_for(session, config, merchant_id, "payments")

    values = {
        "loan_id": loan_id,
        "due_date": due_date,
        "paid_date": paid_date,
        "amount_due_bdt": float(amount_due_bdt),
        "amount_paid_bdt": float(amount_paid_bdt),
    }
    earlier = _recent_same(
        session, config, actor, merchant_id, "payment", db.Payment, "payment_id", values
    )
    if earlier is not None:
        return earlier, True
    payment_id = new_id("PA")
    row = db.Payment(payment_id=payment_id, merchant_id=merchant_id, **values)
    _save(
        session,
        config,
        row=row,
        record_type="payment",
        record_id=payment_id,
        merchant_id=merchant_id,
        category="payments",
        business_date=paid_date or due_date,
        actor=actor,
        audit_action="record_repayment",
    )
    return row, False


def _is_amount(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value
