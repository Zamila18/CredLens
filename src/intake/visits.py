"""Record a field visit to a shop.

Purpose: a short, structured note of what staff found on a visit (the shop was open and
    trading, the owner was away, a follow-up is needed ...). Not a report and not a CRM.
Owner role: D (full-stack).
Implements: the implementation pack, Phase 2.4 and 3.3.

A visit is never a model input: it does not change a score. It needs a valid consent that
covers field visits.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from src.api.auth import CurrentUser, add_audit
from src.db import models as db
from src.intake.consent import require_consent_for
from src.intake.policy import (
    add_provenance,
    benchmark_request,
    check_business_date,
    check_choice,
    check_note,
    demo,
    live_merchant,
    new_id,
    require_synthetic_mode,
    utc_now,
)


def record_visit(
    session: Session,
    config: dict[str, Any],
    *,
    merchant_id: str,
    business_date: date,
    outcome: str,
    note: str | None,
    actor: CurrentUser,
    protected_merchants: frozenset[str] | set[str],
) -> db.Visit:
    """Record a visit. Returns it; commits, or writes nothing."""
    settings = demo(config)["visit"]
    require_synthetic_mode(config)
    check_business_date(business_date, config, "The visit date")
    check_choice(outcome, settings["outcomes"], "The visit outcome")
    note = check_note(note, settings["note_max_chars"])
    live_merchant(session, merchant_id, protected_merchants)
    require_consent_for(session, config, merchant_id, "field_visits")

    now = utc_now()
    visit = db.Visit(
        visit_id=new_id("VI"),
        merchant_id=merchant_id,
        business_date=business_date,
        outcome=outcome,
        note=note,
        actor=actor.user_id,
        entered_at=now,
        simulated=benchmark_request(),
    )
    try:
        session.add(visit)
        add_provenance(
            session,
            record_type="visit",
            record_id=visit.visit_id,
            merchant_id=merchant_id,
            source_category="field_visits",
            entry_method="staff_entered",
            status="staff_entered",
            actor=actor.user_id,
            entered_at=now,
            business_date=business_date,
        )
        add_audit(session, actor, "record_visit", merchant_id)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return visit
