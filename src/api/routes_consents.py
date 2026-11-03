"""GET /consents: every consent record, one page at a time.

Purpose: the main table of the dashboard's consent page: who consented to what, from when
    to when, and whether it still holds.
Owner role: D (full-stack).
Implements: PROJECT_BRIEF section 9 (consent view) and section 18, item 38.

Rules kept here:
- Read only. There is no endpoint to revoke or edit a consent (see GET
  /merchants/{id}/consent for why).
- The status is worked out for the last day in the data ("today" for the data), with the
  same rule the scorer uses: granted on or before that day, expires after it, not revoked on
  or before it. So a merchant with a `valid` record here is one the queue scores.
- Every read writes an audit entry before anything is returned.
- A data mode whose rows may never be shown (Home Credit) gets 403 `rows_not_shown`.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from src.api.auth import READERS, CurrentUser, add_audit, require_roles
from src.api.common import refuse_rows_not_shown
from src.api.schemas import ConsentList, ConsentListItem
from src.api.state import Services, get_services, get_session
from src.api.tenancy import merchant_in_org, org_of
from src.db import models as db

router = APIRouter(tags=["consents"])

STATUSES = ("valid", "expired", "revoked", "not_started")
# Most records one answer may hold; the whole table is about 19,500 rows.
CONSENTS_MAX_ROWS = 500
CONSENTS_DEFAULT_ROWS = 100


def status_of(row: db.Consent, as_of: date) -> str:
    """valid, expired, revoked or not_started on `as_of` (revoked wins, then expired)."""
    if row.revoked_at is not None and row.revoked_at <= as_of:
        return "revoked"
    if row.expires_at <= as_of:
        return "expired"
    if row.granted_at > as_of:
        return "not_started"
    return "valid"


def status_condition(status: str, as_of: date):
    """The same rule as `status_of`, as a database condition."""
    not_revoked = or_(db.Consent.revoked_at.is_(None), db.Consent.revoked_at > as_of)
    if status == "revoked":
        return and_(db.Consent.revoked_at.is_not(None), db.Consent.revoked_at <= as_of)
    if status == "expired":
        return and_(not_revoked, db.Consent.expires_at <= as_of)
    if status == "not_started":
        return and_(not_revoked, db.Consent.expires_at > as_of, db.Consent.granted_at > as_of)
    return and_(not_revoked, db.Consent.expires_at > as_of, db.Consent.granted_at <= as_of)


@router.get("/consents", response_model=ConsentList)
def list_consents(
    merchant_id: str | None = None,
    status_filter: Literal["valid", "expired", "revoked", "not_started"] | None = Query(
        default=None, alias="status"
    ),
    limit: int = Query(default=CONSENTS_DEFAULT_ROWS, ge=1, le=CONSENTS_MAX_ROWS),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_roles(*READERS)),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ConsentList:
    """Consent records ordered by merchant id, then grant date. Every role. Audited.

    `merchant_id` narrows to one merchant, `status` to one status. `counts` gives the
    number of records per status for the merchant filter, for the tiles above the table.
    """
    refuse_rows_not_shown(services.config)
    as_of = services.data_today(session)
    scope = [db.Consent.merchant_id == merchant_id] if merchant_id else []
    # Only the caller's organisation's merchants (tenancy.py).
    scope.append(
        db.Consent.merchant_id.in_(
            select(db.Merchant.merchant_id).where(
                merchant_in_org(org_of(user, services.config), services.config)
            )
        )
    )

    counts = {
        name: session.scalar(
            select(func.count())
            .select_from(db.Consent)
            .where(*scope, status_condition(name, as_of))
        )
        for name in STATUSES
    }
    wanted = [status_condition(status_filter, as_of)] if status_filter else []
    total = counts[status_filter] if status_filter else sum(counts.values())
    rows = session.scalars(
        select(db.Consent)
        .where(*scope, *wanted)
        .order_by(db.Consent.merchant_id, db.Consent.granted_at, db.Consent.consent_id)
        .limit(limit)
        .offset(offset)
    ).all()
    items = [
        ConsentListItem(
            consent_id=row.consent_id,
            merchant_id=row.merchant_id,
            purpose=row.purpose,
            data_categories=[part for part in row.data_categories.split("|") if part],
            granted_at=row.granted_at.isoformat(),
            expires_at=row.expires_at.isoformat(),
            revoked_at=row.revoked_at.isoformat() if row.revoked_at else None,
            status=status_of(row, as_of),
        )
        for row in rows
    ]
    add_audit(session, user, "view_consents", merchant_id)
    session.commit()
    return ConsentList(
        as_of=as_of.isoformat(),
        total=total,
        limit=limit,
        offset=offset,
        counts=counts,
        items=items,
    )
