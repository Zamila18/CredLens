"""Demo role check, and the audit helper.

Purpose: a simple role switch (officer / admin / viewer) read from a header token, to show
    role-based access without a full login system. THIS IS A DEMO ROLE SWITCH, NOT A REAL
    LOGIN: anyone who knows a user id can send it. Say so if a judge asks.
Owner role: D (full-stack).
Implements: PROJECT_BRIEF sections 3 and 8 (roles).

How it works: the request carries the header `X-Demo-Token: <user id>`, for example
`officer-1`. The user is looked up in the `users` table and the role comes from there.
No token, or a token that is not a user: 401. A user whose role may not do the thing: 403.

  officer: queue, profile, score, consent, model card, decide, record questionnaire answers.
  admin:   queue, profile, score, decisions, model card, audit log, data import.
  viewer:  read-only: queue, profile, score, consent, decisions, model card. Can never POST.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from src.api.common import api_error, utc_now
from src.api.state import get_session
from src.db import models as db

TOKEN_HEADER = "X-Demo-Token"

# officer: queue, score, decide. admin: plus audit and model card. viewer: read-only.
ROLES = ("officer", "admin", "viewer")

EVERY_ROLE = ("officer", "admin", "viewer")


@dataclass(frozen=True)
class CurrentUser:
    """Who is calling: a demo user and the role the database gives them."""

    user_id: str
    role: str


def role_from_token(token: str | None, session: Session) -> CurrentUser:
    """Return the user for a header token, or raise 401."""
    if not token or not token.strip():
        raise api_error(
            401, "missing_token", f"Send the demo user id in the {TOKEN_HEADER} header."
        )
    user = session.get(db.User, token.strip())
    if user is None:
        raise api_error(401, "unknown_token", "That token is not a known demo user.")
    return CurrentUser(user_id=user.user_id, role=user.role)


def require_roles(*allowed: str):
    """A dependency that lets only the given roles through (403 for any other role)."""

    def dependency(
        token: str | None = Header(default=None, alias=TOKEN_HEADER),
        session: Session = Depends(get_session),
    ) -> CurrentUser:
        user = role_from_token(token, session)
        if user.role not in allowed:
            raise api_error(
                403,
                "role_not_allowed",
                f"The {user.role} role cannot do this. Allowed: {', '.join(allowed)}.",
            )
        return user

    return dependency


def add_audit(
    session: Session, user: CurrentUser, action: str, merchant_id: str | None = None
) -> None:
    """Add one audit row (who, role, what, which merchant, when in UTC). The caller commits.

    The audit log is append-only: nothing in the API can change or remove a row.
    """
    session.add(
        db.AuditEntry(
            actor=user.user_id,
            role=user.role,
            action=action,
            merchant_id=merchant_id,
            timestamp=utc_now(),
        )
    )
