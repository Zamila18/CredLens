"""The header bell: a person's short messages (a merchant applied, a report came in).

Purpose: tell the right person that something waits for them, without email. Polled by the
    page every half minute. Nothing here carries a secret or a merchant's details.
Owner role: D (full-stack).
Implements: notifications of the unified platform plan.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.accounts.service import now
from src.api.auth import ANY_ACCOUNT, CurrentUser, require_roles
from src.api.state import get_session
from src.db import models as db

router = APIRouter(tags=["notifications"])


class NotificationOut(BaseModel):
    notification_id: str
    kind: str
    text: str
    link: str | None
    created_at: str
    read: bool


@router.get("/notifications", response_model=list[NotificationOut])
def notifications(
    user: CurrentUser = Depends(require_roles(*ANY_ACCOUNT)),
    session: Session = Depends(get_session),
) -> list[NotificationOut]:
    """The caller's latest notifications (unread first)."""
    rows = session.scalars(
        select(db.Notification)
        .where(db.Notification.user_id == user.user_id)
        .order_by(db.Notification.read_at.is_(None).desc(), db.Notification.created_at.desc())
        .limit(40)
    ).all()
    return [
        NotificationOut(
            notification_id=n.notification_id,
            kind=n.kind,
            text=n.text,
            link=n.link,
            created_at=n.created_at.isoformat(timespec="seconds"),
            read=n.read_at is not None,
        )
        for n in rows
    ]


@router.post("/notifications/read-all", status_code=204)
def read_all(
    user: CurrentUser = Depends(require_roles(*ANY_ACCOUNT)),
    session: Session = Depends(get_session),
) -> None:
    for n in session.scalars(
        select(db.Notification).where(
            db.Notification.user_id == user.user_id, db.Notification.read_at.is_(None)
        )
    ):
        n.read_at = now()
    session.commit()
