"""Test-only: real sessions for the few people the API tests act as.

Purpose: the API tests need callers with different roles on a small benchmark database. In
    the product every caller signs in with a password; here the tests insert a membership and
    a session row with a known token, so a request carries `Cookie: credlens_session=<token>`
    exactly as a signed-in browser does. Nothing like this exists in the application: no
    header or token chooses a user there.
Owner role: D (full-stack).

The people (user ids are the ones the benchmark loader creates):
    officer-1  credit officer                           OFFICER
    officer-2  credit officer                           OFFICER_2
    admin-1    credit officer, the company owner        ADMIN
    viewer-1   auditor                                  VIEWER
    fsr-1      field sales representative               FSR
All belong to the reserved benchmark organisation (config `organization.id`).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from src.accounts.passwords import session_hash
from src.api.auth import SESSION_COOKIE
from src.config import load_config
from src.db import models as db

# user id, role, owner
PEOPLE = (
    ("officer-1", "credit_officer", False),
    ("officer-2", "credit_officer", False),
    ("admin-1", "credit_officer", True),
    ("viewer-1", "auditor", False),
    ("fsr-1", "fsr", False),
)


def token_for(user_id: str) -> str:
    return f"test-session-{user_id}"


def headers_for(user_id: str) -> dict[str, str]:
    return {"Cookie": f"{SESSION_COOKIE}={token_for(user_id)}"}


OFFICER = headers_for("officer-1")
OFFICER_2 = headers_for("officer-2")
ADMIN = headers_for("admin-1")
VIEWER = headers_for("viewer-1")
FSR = headers_for("fsr-1")


def seed_person(
    session: Session, user_id: str, role: str, org_id: str, owner: bool = False
) -> None:
    """One person in an organisation with a long-lived session (see token_for)."""
    far, now = datetime(2100, 1, 1), datetime(2026, 1, 1)
    if session.get(db.User, user_id) is None:
        session.add(db.User(user_id=user_id, display_name=user_id, role="viewer"))
        session.flush()
    membership_id = f"MB-test-{user_id}"
    if session.get(db.Membership, membership_id) is None:
        session.add(
            db.Membership(
                membership_id=membership_id,
                user_id=user_id,
                organization_id=org_id,
                role=role,
                status="active",
                is_owner=owner,
                created_by=None,
                created_at=now,
            )
        )
    if session.get(db.AuthSession, session_hash(token_for(user_id))) is None:
        session.add(
            db.AuthSession(
                token_hash=session_hash(token_for(user_id)),
                user_id=user_id,
                membership_id=membership_id,
                created_at=now,
                last_seen_at=far - timedelta(days=1),
                expires_at=far,
            )
        )


def seed_accounts(engine, config: dict | None = None) -> None:
    """Add the people above to the benchmark organisation, each with a long-lived session."""
    org_id = (config or load_config())["organization"]["id"]
    with Session(engine) as session:
        for user_id, role, owner in PEOPLE:
            seed_person(session, user_id, role, org_id, owner)
        session.commit()
