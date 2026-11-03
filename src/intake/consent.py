"""Record a merchant's answer to the consent explanation (staff-assisted, simulated).

Purpose: the consent step of the demo workflow. Staff show the merchant what will be used,
    for which purpose and for how long, and record the answer.
Owner role: D (full-stack).
Implements: the implementation pack, Phase 2.5 and 3.2.

- A grant creates the canonical row in `consents` (the one the scorer and every consent
  check read) and an event that keeps what was shown, how the answer was given, who
  recorded it and when.
- A refusal creates only the event: no consent, so covered records cannot be added.
- Every consent recorded here is simulated, for synthetic merchants. A recorded answer
  is not a signature and says nothing about legal validity.
- Withdrawing a consent is not built: the scorer reads consent when it is built, so a
  withdrawal would not reach a running scorer.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from src.api.auth import CurrentUser, add_audit
from src.api.profile import consent_state
from src.db import models as db
from src.intake.policy import (
    IntakeRefused,
    add_provenance,
    benchmark_request,
    calendar_end,
    check_business_date,
    check_choice,
    demo,
    live_merchant,
    new_id,
    require_synthetic_mode,
    utc_now,
)


def record_consent_response(
    session: Session,
    config: dict[str, Any],
    *,
    merchant_id: str,
    response: str,
    categories: list[str],
    method: str,
    actor: CurrentUser,
    business_date: date,
    protected_merchants: frozenset[str] | set[str],
    commit: bool = True,
) -> db.ConsentEvent:
    """Record a grant or a refusal. Returns the event; commits, or writes nothing.

    With `commit=False` the rows are only flushed, so the caller can save more in the same
    transaction (a signed paper form, src/intake/consent_forms.py) and commit once.
    """
    settings = demo(config)["consent"]
    require_synthetic_mode(config)
    check_choice(response, list(db.CONSENT_RESPONSES), "The answer")
    check_business_date(business_date, config, "The consent date")
    check_choice(method, settings["methods"], "The way the answer was given")
    if not categories or len(set(categories)) != len(categories):
        raise IntakeRefused(422, "invalid_choice", "Name each data category once, at least one.")
    for category in categories:
        check_choice(category, settings["categories"], "A data category")
    live_merchant(session, merchant_id, protected_merchants)

    valid, _ = consent_state(session, merchant_id, calendar_end(config))
    if valid and response == "granted":
        raise IntakeRefused(
            409, "consent_already_valid", f"{merchant_id} already has a valid consent."
        )
    if valid and response == "refused":
        raise IntakeRefused(
            409,
            "withdrawal_not_supported",
            f"{merchant_id} already has a valid consent. Withdrawing a consent is not built "
            "in this prototype.",
        )

    now = utc_now()
    joined = "|".join(categories)
    consent_id = None
    try:
        if response == "granted":
            consent_id = new_id("CD")
            session.add(
                db.Consent(
                    consent_id=consent_id,
                    merchant_id=merchant_id,
                    purpose=settings["purpose"],
                    data_categories=joined,
                    granted_at=business_date,
                    expires_at=business_date + timedelta(days=settings["valid_days"]),
                    revoked_at=None,
                )
            )
            session.flush()  # the event points at this consent
        event = db.ConsentEvent(
            event_id=new_id("CE"),
            merchant_id=merchant_id,
            consent_id=consent_id,
            response=response,
            wording_version=settings["wording_version"],
            purpose=settings["purpose"],
            categories=joined,
            method=method,
            actor=actor.user_id,
            business_date=business_date,
            recorded_at=now,
            simulated=benchmark_request(),
        )
        session.add(event)
        add_provenance(
            session,
            record_type="consent",
            record_id=event.event_id,
            merchant_id=merchant_id,
            source_category="consent",
            entry_method="staff_entered",
            status="staff_entered",
            actor=actor.user_id,
            entered_at=now,
            business_date=business_date,
        )
        add_audit(session, actor, f"record_consent_{response}", merchant_id)
        if commit:
            session.commit()
        else:
            session.flush()
    except Exception:
        session.rollback()
        raise
    return event


def require_consent_for(
    session: Session, config: dict[str, Any], merchant_id: str, category: str
) -> None:
    """Refuse a record unless the merchant's valid consent covers its data category."""
    valid, categories = consent_state(session, merchant_id, calendar_end(config))
    if not valid:
        raise IntakeRefused(
            403,
            "consent_required",
            f"{merchant_id} has no valid consent, so nothing can be recorded. Record the "
            "merchant's consent first.",
        )
    if category not in categories:
        raise IntakeRefused(
            403,
            "consent_category_missing",
            f"{merchant_id}'s consent does not cover {category.replace('_', ' ')}, so this "
            "record cannot be added.",
            category=category,
        )
