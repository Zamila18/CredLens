"""Create a merchant's working-capital application, and the row that lets it be scored.

Purpose: the application step of the demo workflow.
Owner role: D (full-stack), with the lead.
Implements: the implementation pack, Phase 2.1 and 3.4, and the go/no-go of appendix A9.

How it fits the existing scorer: the scorer scores a merchant's most recent loan row. So an
application writes one loan-shaped row (no outcome, a limit of 0) and an `applications` row
that names it. What the Phase 1 tests showed (tests/test_application_scoring_safety.py):
- the scored row's own limit never reaches the model, so the score does not assess the
  requested amount at all; the amount is kept only in `applications`, and the row's limit
  is 0 so no view can mistake the request for an issued limit;
- a loan row with no payments adds no credit history; the database refuses any repayment
  against an application's row, and any change to that row.

The row is not an issued loan. One application per merchant, ever, in this prototype.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.auth import CurrentUser, add_audit
from src.api.profile import consent_state
from src.db import models as db
from src.intake.policy import (
    IntakeRefused,
    add_provenance,
    calendar_end,
    check_business_date,
    check_choice,
    check_note,
    demo,
    live_merchant,
    new_id,
    require_synthetic_mode,
    utc_now,
)
from src.intake.records import check_scoring_inputs


def create_application(
    session: Session,
    config: dict[str, Any],
    *,
    merchant_id: str,
    requested_amount_bdt: float,
    purpose: str,
    purpose_note: str | None,
    business_date: date,
    actor: CurrentUser,
    protected_merchants: frozenset[str] | set[str],
) -> db.Application:
    """Create the application and its scoring row in one transaction. Returns the application."""
    settings = demo(config)["application"]
    require_synthetic_mode(config)
    check_business_date(business_date, config, "The application date")
    check_choice(purpose, settings["purposes"], "The purpose")
    purpose_note = check_note(purpose_note, settings["note_max_chars"], "The explanation")
    if (
        not isinstance(requested_amount_bdt, (int, float))
        or isinstance(requested_amount_bdt, bool)
        or not 0 < requested_amount_bdt <= settings["max_requested_bdt"]
    ):
        raise IntakeRefused(
            422,
            "invalid_amount",
            "The requested amount must be more than 0 and at most "
            f"{settings['max_requested_bdt']:,} taka.",
        )
    live_merchant(session, merchant_id, protected_merchants)

    valid, _ = consent_state(session, merchant_id, calendar_end(config))
    if not valid:
        raise IntakeRefused(
            403,
            "consent_required",
            f"{merchant_id} has no valid consent. Record the merchant's consent before "
            "an application.",
        )
    if session.scalar(select(db.Application).where(db.Application.merchant_id == merchant_id)):
        raise IntakeRefused(
            409,
            "application_exists",
            f"{merchant_id} already has an application. This prototype allows one "
            "application per merchant.",
        )
    latest = session.scalar(
        select(func.max(db.Loan.issued_at)).where(db.Loan.merchant_id == merchant_id)
    )
    if latest is not None and business_date < latest:
        # The scorer reads the most recent loan row; an earlier date would score the wrong row.
        raise IntakeRefused(
            409,
            "application_before_latest_loan",
            f"The application date must be on or after {merchant_id}'s latest loan "
            f"({latest.isoformat()}).",
        )

    now = utc_now()
    loan_id = new_id("LA")
    application = db.Application(
        application_id=new_id("AP"),
        loan_id=loan_id,
        merchant_id=merchant_id,
        requested_amount_bdt=float(requested_amount_bdt),
        purpose=purpose,
        purpose_note=purpose_note,
        business_date=business_date,
        created_by=actor.user_id,
        entered_at=now,
        demo_synthetic=True,
    )
    try:
        session.add(
            db.Loan(
                loan_id=loan_id,
                merchant_id=merchant_id,
                issued_at=business_date,
                limit_bdt=0.0,
                outcome_label=None,
                label_observed_at=None,
            )
        )
        session.flush()  # the application points at this row
        session.add(application)
        add_provenance(
            session,
            record_type="application",
            record_id=application.application_id,
            merchant_id=merchant_id,
            source_category="application",
            entry_method="staff_entered",
            status="staff_entered",
            actor=actor.user_id,
            entered_at=now,
            business_date=business_date,
        )
        session.flush()
        check_scoring_inputs(session, config, merchant_id)
        add_audit(session, actor, "create_application", merchant_id)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return application


def is_application(session: Session, loan_id: str) -> bool:
    """True when this loan-shaped row is an application, not an issued loan."""
    return (
        session.scalar(select(db.Application.loan_id).where(db.Application.loan_id == loan_id))
        is not None
    )


def application_loan_ids(session: Session, loan_ids: list[str] | None = None) -> set[str]:
    """The loan rows that are applications (all of them, or those among `loan_ids`)."""
    query = select(db.Application.loan_id)
    if loan_ids is not None:
        query = query.where(db.Application.loan_id.in_(loan_ids))
    return set(session.scalars(query))
