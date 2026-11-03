"""Company invitation codes: make, list, revoke, regenerate, and resolve one.

Purpose: let an organisation's Credit Officer bring colleagues in. A valid code binds a new
    account to the right organisation and role; the person cannot choose either.
Owner role: D (full-stack).

Rules:
- Only a keyed hash (HMAC-SHA256 with the server's secret key) of the code is stored. The code
  is shown once, when it is made; afterwards only its last four characters (the hint) show.
- A code works until `expires_at`, until it is revoked, or until it has been used `max_uses`
  times. Using it is one atomic database update, so two people cannot take the last place.
- A wrong, expired, revoked, used-up or suspended-organisation code all give the same answer.
- A correct code verifies the person's link to that CredLens organisation. It is not
  independent legal verification of the company.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.accounts.keys import secret_key
from src.accounts.passwords import clean_code, keyed_code_hash, new_invitation_code
from src.accounts.service import AccountError, now
from src.db import models as db

INVALID = AccountError(
    400,
    "invalid_invitation",
    "This invitation code does not work. Check it, or ask your company for a new one.",
)


def _hash(code: str) -> str:
    return keyed_code_hash(code, secret_key())


def create_invitation(
    session: Session,
    config: dict[str, Any],
    organization_id: str,
    role: str,
    created_by: str,
    *,
    days: int | None = None,
    max_uses: int = 1,
    default_territory: str | None = None,
    label: str | None = None,
) -> tuple[db.Invitation, str]:
    """A new invitation and its code (returned once; only a hash is stored)."""
    rules = config["auth"]
    if role not in db.INVITATION_ROLES:
        raise AccountError(422, "bad_role", f"Invite as one of: {', '.join(db.INVITATION_ROLES)}.")
    days = int(days if days is not None else rules["invitation_default_days"])
    if not 1 <= days <= int(rules["invitation_max_days"]):
        raise AccountError(422, "bad_expiry", f"Choose 1 to {rules['invitation_max_days']} days.")
    if not 1 <= int(max_uses) <= int(rules["invitation_max_uses"]):
        raise AccountError(
            422, "bad_max_uses", f"Choose 1 to {rules['invitation_max_uses']} people."
        )
    code = new_invitation_code()
    row = db.Invitation(
        invitation_id=f"IN-{uuid.uuid4().hex[:24]}",
        organization_id=organization_id,
        role=role,
        code_hash=_hash(code),
        code_hint=clean_code(code)[-4:],
        default_territory=(default_territory or "").strip() or None,
        label=(label or "").strip()[:80] or None,
        expires_at=now() + timedelta(days=days),
        max_uses=int(max_uses),
        use_count=0,
        status="active",
        created_by=created_by,
        created_at=now(),
    )
    session.add(row)
    return row, code


def state_of(row: db.Invitation) -> str:
    """active | revoked | expired | used_up (what the owner sees)."""
    if row.status == "revoked":
        return "revoked"
    if row.expires_at <= now():
        return "expired"
    if row.use_count >= row.max_uses:
        return "used_up"
    return "active"


def get_for_org(session: Session, organization_id: str, invitation_id: str) -> db.Invitation:
    row = session.get(db.Invitation, invitation_id)
    if row is None or row.organization_id != organization_id:
        raise AccountError(404, "unknown_invitation", "No such invitation.")
    return row


def revoke_invitation(session: Session, row: db.Invitation, actor: str) -> None:
    if row.status != "revoked":
        row.status, row.revoked_at, row.revoked_by = "revoked", now(), actor


def regenerate_invitation(
    session: Session, config: dict[str, Any], row: db.Invitation, actor: str
) -> tuple[db.Invitation, str]:
    """Revoke the invitation and make a new one with the same role, limits and territory."""
    revoke_invitation(session, row, actor)
    remaining_days = max(1, (row.expires_at - row.created_at).days)
    return create_invitation(
        session,
        config,
        row.organization_id,
        row.role,
        actor,
        days=min(remaining_days, int(config["auth"]["invitation_max_days"])),
        max_uses=row.max_uses,
        default_territory=row.default_territory,
        label=row.label,
    )


def resolve(session: Session, code: str) -> db.Invitation:
    """The usable invitation for a code, or the one generic refusal."""
    if len(clean_code(code)) != 16:
        raise INVALID
    row = session.scalar(select(db.Invitation).where(db.Invitation.code_hash == _hash(code)))
    if row is None or state_of(row) != "active":
        raise INVALID
    org = session.get(db.Organization, row.organization_id)
    if org is None or org.status != "active":
        raise INVALID
    return row


def take_a_place(session: Session, row: db.Invitation) -> None:
    """Use one place of the invitation, atomically (refused when someone took the last one)."""
    result = session.execute(
        update(db.Invitation)
        .where(
            db.Invitation.invitation_id == row.invitation_id,
            db.Invitation.status == "active",
            db.Invitation.use_count < db.Invitation.max_uses,
            db.Invitation.expires_at > now(),
        )
        .values(use_count=db.Invitation.use_count + 1)
    )
    if result.rowcount != 1:
        raise INVALID
