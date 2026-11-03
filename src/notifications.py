"""Short messages for people (a sheet came in, a sheet was sent back, a form needs checking).

Purpose: tell the right person that something waits for them, without email: the header bell
    reads these (GET /notifications). Nothing here carries a secret or a merchant's details.
Owner role: D (full-stack).
Implements: Phase 5 of the unified platform plan (notifications).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.accounts.service import now
from src.db import models as db


def notify_user(
    session: Session, user_id: str, org_id: str, kind: str, text: str, link: str | None = None
) -> None:
    """Add one notification. The caller commits."""
    session.add(
        db.Notification(
            notification_id=f"NT-{uuid.uuid4().hex[:24]}", user_id=user_id, organization_id=org_id,
            kind=kind, text=text[:300], link=link, created_at=now(),
        )
    )


def notify_officers(
    session: Session, org_id: str, kind: str, text: str, link: str | None = None,
    exclude: str | None = None,
) -> None:
    """Tell every active Credit Officer of the company (except `exclude`)."""
    for user_id in session.scalars(
        select(db.Membership.user_id).where(
            db.Membership.organization_id == org_id, db.Membership.role == "credit_officer",
            db.Membership.status == "active",
        )
    ):
        if user_id != exclude:
            notify_user(session, user_id, org_id, kind, text, link)
