"""A merchant's own sign-in: a random Merchant ID and the owner's name.

Purpose: let a shop owner open their portal (their receipts, reports and loan application)
    without an email or password. The Merchant ID is made at random when the shop is created and
    printed on the handover slip; it is not the sequential CredLens shop id, so it cannot be
    guessed from a shop's name or number. Sign-in works once the shop's consent is verified, is
    rate-limited like every other sign-in, and the merchant then sees only their own shop.
Owner role: D (full-stack).
Implements: the merchant portal of the Records Desk redesign.
"""

from __future__ import annotations

import re
import secrets
import unicodedata
import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.accounts.service import (
    AccountError,
    add_membership,
    now,
    organization_is_active,
    start_session,
)
from src.db import models as db

# No 0/O, 1/I/L, 5/S lookalikes: a slip read aloud or copied by hand stays unambiguous.
ALPHABET = "ABCDEFGHJKMNPQRTUVWXYZ2346789"
REFUSED = AccountError(401, "login_failed", "The Merchant ID or the name is not right.")


def clean_portal_id(raw: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (raw or "").upper())


def show_portal_id(clean: str) -> str:
    """MR-4K7Q-9XPT from MR4K7Q9XPT."""
    body = clean[2:] if clean.startswith("MR") else clean
    return f"MR-{body[:4]}-{body[4:8]}"


def new_portal_id(session: Session) -> str:
    """A fresh random Merchant ID that no shop has yet (about 38 bits)."""
    while True:
        body = "".join(secrets.choice(ALPHABET) for _ in range(8))
        code = f"MR{body}"
        taken = select(db.MerchantAccess.merchant_id).where(db.MerchantAccess.portal_id == code)
        if session.scalar(taken) is None:
            return code


def create_access(session: Session, merchant_id: str, organization_id: str) -> db.MerchantAccess:
    row = db.MerchantAccess(
        merchant_id=merchant_id,
        organization_id=organization_id,
        portal_id=new_portal_id(session),
        created_at=now(),
    )
    session.add(row)
    return row


def _tokens(name: str) -> list[str]:
    text = unicodedata.normalize("NFKC", name or "").casefold()
    return [t for t in re.split(r"[^\w]+", text) if t]


def name_matches(typed: str, registered: str | None) -> bool:
    """Same name regardless of case, spacing and punctuation; a first or last name alone is
    enough when it is a whole word of the registered name (at least three characters)."""
    a, b = _tokens(typed), _tokens(registered or "")
    if not a or not b:
        return False
    if "".join(a) == "".join(b):
        return True
    return all(len(t) >= 3 and t in b for t in a)


def login(session: Session, config: dict[str, Any], portal_id: str, owner_name: str, as_of: date):
    """Open a merchant's session. Returns (token, auth session, membership). One generic
    refusal for every wrong or unusable combination, so nothing is revealed about shops."""
    from src.api.profile import consent_state

    access = session.scalar(
        select(db.MerchantAccess).where(db.MerchantAccess.portal_id == clean_portal_id(portal_id))
    )
    if access is None:
        raise REFUSED
    profile = session.get(db.MerchantProfile, access.merchant_id)
    if profile is None or not name_matches(owner_name, profile.owner_name):
        raise REFUSED
    if not organization_is_active(session, config, access.organization_id):
        raise REFUSED
    valid, _ = consent_state(session, access.merchant_id, as_of)
    if not valid:
        raise AccountError(
            403,
            "portal_not_open",
            "Your portal opens once your consent form has been checked. Ask your lender.",
        )
    membership = None
    if access.user_id is not None:
        membership = session.scalar(
            select(db.Membership).where(
                db.Membership.user_id == access.user_id,
                db.Membership.merchant_id == access.merchant_id,
            )
        )
    if membership is None:
        user = db.User(
            user_id=f"U-{uuid.uuid4().hex[:20]}",
            display_name=(profile.owner_name or profile.shop_name)[:64],
            role="viewer",
            organization_id=access.organization_id,
        )
        session.add(user)
        session.flush()
        session.add(db.UserCredential(user_id=user.user_id, failed_attempts=0, created_at=now()))
        membership = add_membership(session, user.user_id, access.organization_id, "merchant", None)
        membership.merchant_id = access.merchant_id
        access.user_id = user.user_id
        session.flush()
    if membership.status != "active":
        raise REFUSED
    token, row = start_session(session, config, membership.user_id, membership)
    return token, row, membership
