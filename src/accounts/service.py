"""Accounts: organisations, staff accounts, sign-in, sessions, setup codes, shop assignments.

Purpose: real sign-in for CredLens platform administrators and for an organisation's staff.
Owner role: D (full-stack).
Implements: Phase 1 of the unified platform plan (accounts, companies, invitations).

Rules:
- The role comes from the server: a platform admin from `platform_admins`, everyone else from
  the account's membership. Nothing the browser sends can choose or change it.
- A password is never stored or logged; only an Argon2id hash (passwords.py). Older scrypt
  hashes still verify and are replaced by an Argon2id hash on the next successful sign-in.
- Passwords follow the policy in passwords.py (12 characters, mixed case, digit, symbol, not a
  common password, not built from the person's own email or name).
- Sign-in failures say the same thing whatever was wrong (no hint which accounts exist).
  Several failures in a row lock the account for a while.
- A session token lives only in an HttpOnly cookie; the database keeps its hash. A session
  ends at logout, after `session_idle_minutes` without use, or `session_max_hours` after
  sign-in. Setting a new password ends every session of that account.
- An organisation's owner never sees or sets an employee's password. They give a one-time
  setup code (shown once); the person sets their own password with it. The same code flow is
  the password reset. A suspended organisation cannot sign in.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.accounts.passwords import (
    code_hash,
    hash_password,
    needs_rehash,
    new_setup_code,
    new_token,
    password_problems,
    session_hash,
    verify_password,
)
from src.db import models as db

ORGANIZATION_ENVIRONMENTS = ("pilot", "production")
PLATFORM_ROLE = "platform_admin"
# The legacy `users.role` column only allows the three old demo values. A real account's
# role lives in its membership (or `platform_admins`); the legacy column holds the
# least-privileged value and is never read for authorisation.
LEGACY_ROLE_FOR_ACCOUNTS = "viewer"
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AccountError(Exception):
    """A refused account action. `status` is the HTTP status; `code` is machine-readable."""

    def __init__(self, status: int, code: str, message: str, **facts: Any) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.facts = status, code, message, facts


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def settings(config: dict[str, Any]) -> dict[str, Any]:
    return config["auth"]


def normalise_identifier(identifier: str) -> tuple[str | None, str | None]:
    """(email, phone) from what a person typed. A Bangladesh mobile number written as
    01XXXXXXXXX is stored as +8801XXXXXXXXX. Emails are stored in lower case, so two
    spellings of one address are one account."""
    text = (identifier or "").strip()
    if "@" in text:
        return (text.lower(), None) if EMAIL.match(text) else (None, None)
    digits = re.sub(r"[\s\-()]", "", text)
    if re.fullmatch(r"01\d{9}", digits):
        digits = "+880" + digits[1:]
    if re.fullmatch(r"\+?\d{8,15}", digits):
        return None, digits if digits.startswith("+") else "+" + digits
    return None, None


def credential_for(session: Session, identifier: str) -> db.UserCredential | None:
    email, phone = normalise_identifier(identifier)
    if email:
        return session.scalar(select(db.UserCredential).where(db.UserCredential.email == email))
    if phone:
        return session.scalar(select(db.UserCredential).where(db.UserCredential.phone == phone))
    return None


def active_membership(session: Session, user_id: str) -> db.Membership | None:
    return session.scalar(
        select(db.Membership)
        .where(db.Membership.user_id == user_id, db.Membership.status == "active")
        .order_by(db.Membership.created_at)
        .limit(1)
    )


def is_platform_admin(session: Session, user_id: str) -> bool:
    return session.get(db.PlatformAdmin, user_id) is not None


def organization_is_active(session: Session, config: dict[str, Any], organization_id: str) -> bool:
    """A company can sign in only while its status is active. The reserved benchmark
    organisation has no row (it comes from the config) and counts as active."""
    org = session.get(db.Organization, organization_id)
    if org is None:
        return organization_id == config["organization"]["id"]
    return org.status == "active"


# --- organisations and accounts ---------------------------------------------------------


def create_organization(
    session: Session,
    organization_id: str,
    name: str,
    environment: str,
    country: str = "BD",
    languages: str = "en|bn",
    currency: str = "BDT",
    timezone_name: str = "Asia/Dhaka",
    **details: Any,
) -> db.Organization:
    """An organisation (pilot or production). `details` are the company fields of the
    registration form (legal_name, registration_number, ...)."""
    if environment not in ORGANIZATION_ENVIRONMENTS:
        raise AccountError(
            422, "bad_environment", f"Use one of {', '.join(ORGANIZATION_ENVIRONMENTS)}."
        )
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,46}", organization_id):
        raise AccountError(
            422, "bad_organization_id", "Use 3 to 47 lower-case letters, digits or dashes."
        )
    if session.get(db.Organization, organization_id) is not None:
        raise AccountError(409, "organization_exists", f"{organization_id} already exists.")
    row = db.Organization(
        organization_id=organization_id,
        name=name.strip(),
        environment=environment,
        country=country,
        languages=languages,
        currency=currency,
        timezone=timezone_name,
        created_at=now(),
        status="active",
        **details,
    )
    session.add(row)
    return row


def check_password_rules(
    config: dict[str, Any], password: str, *, email: str | None = None, names: tuple[str, ...] = ()
) -> None:
    """Refuse a password that breaks the policy, saying what to change."""
    problems = password_problems(
        password,
        min_chars=int(settings(config)["password_min_chars"]),
        email=email,
        names=names,
    )
    if problems:
        raise AccountError(422, "weak_password", " ".join(problems))


def make_user(
    session: Session,
    organization_id: str | None,
    display_name: str,
    email: str | None,
    phone: str | None,
) -> db.User:
    """A user row and its credential row (no password yet)."""
    user = db.User(
        user_id=f"U-{uuid.uuid4().hex[:20]}",
        display_name=display_name,
        role=LEGACY_ROLE_FOR_ACCOUNTS,
        organization_id=organization_id,
    )
    session.add(user)
    session.flush()
    session.add(
        db.UserCredential(
            user_id=user.user_id, email=email, phone=phone, failed_attempts=0, created_at=now()
        )
    )
    return user


def add_membership(
    session: Session,
    user_id: str,
    organization_id: str,
    role: str,
    created_by: str | None,
    is_owner: bool = False,
) -> db.Membership:
    membership = db.Membership(
        membership_id=f"MB-{uuid.uuid4().hex[:24]}",
        user_id=user_id,
        organization_id=organization_id,
        role=role,
        status="active",
        is_owner=is_owner,
        created_by=created_by,
        created_at=now(),
    )
    session.add(membership)
    return membership


def create_account(
    session: Session,
    config: dict[str, Any],
    organization_id: str,
    display_name: str,
    identifier: str,
    role: str,
    created_by: str | None,
    is_owner: bool = False,
) -> tuple[db.User, db.Membership, str]:
    """A staff account and its membership, plus a one-time setup code (returned once).

    Used by the command line (`python -m src.accounts.cli`) and by tests; people normally
    register themselves (src/accounts/registration.py).
    """
    org = session.get(db.Organization, organization_id)
    if org is None or org.status != "active":
        raise AccountError(404, "unknown_organization", "No such organisation.")
    if role not in db.STAFF_ROLES:
        raise AccountError(422, "bad_role", f"Use one of {', '.join(db.STAFF_ROLES)}.")
    name = (display_name or "").strip()
    if not 2 <= len(name) <= 64:
        raise AccountError(422, "bad_name", "Give a name of 2 to 64 characters.")
    email, phone = normalise_identifier(identifier)
    if not (email or phone):
        raise AccountError(422, "bad_identifier", "Give an email address or a mobile number.")
    if credential_for(session, identifier) is not None:
        raise AccountError(409, "identifier_taken", "An account with this email or number exists.")
    user = make_user(session, organization_id, name, email, phone)
    membership = add_membership(
        session, user.user_id, organization_id, role, created_by, is_owner=is_owner
    )
    code = issue_setup_code(session, config, user.user_id, created_by or "system")
    return user, membership, code


def issue_setup_code(
    session: Session, config: dict[str, Any], user_id: str, created_by: str
) -> str:
    """A new one-time code for the account. Earlier unused codes stop working."""
    for old in session.scalars(
        select(db.PasswordSetupCode).where(
            db.PasswordSetupCode.user_id == user_id, db.PasswordSetupCode.used_at.is_(None)
        )
    ):
        old.used_at = now()
    code = new_setup_code()
    session.add(
        db.PasswordSetupCode(
            code_hash=code_hash(code),
            user_id=user_id,
            created_by=created_by,
            created_at=now(),
            expires_at=now() + timedelta(hours=int(settings(config)["setup_code_hours"])),
        )
    )
    return code


def set_password_with_code(
    session: Session, config: dict[str, Any], identifier: str, code: str, password: str
) -> db.User:
    """Set (or reset) the password of the account the code belongs to."""
    refused = AccountError(
        400, "bad_code", "This code does not work. Ask your administrator for a new one."
    )
    credential = credential_for(session, identifier)
    row = session.get(db.PasswordSetupCode, code_hash(code or ""))
    if (
        credential is None
        or row is None
        or row.user_id != credential.user_id
        or row.used_at is not None
        or row.expires_at < now()
    ):
        raise refused
    user = session.get(db.User, credential.user_id)
    check_password_rules(
        config, password, email=credential.email, names=(user.display_name if user else "",)
    )
    credential.password_hash = hash_password(password)
    credential.password_set_at = now()
    credential.failed_attempts = 0
    credential.locked_until = None
    row.used_at = now()
    revoke_all_sessions(session, credential.user_id)
    return user


def change_password(
    session: Session, config: dict[str, Any], user_id: str, current: str, new: str
) -> None:
    credential = session.get(db.UserCredential, user_id)
    if credential is None or not verify_password(current, credential.password_hash):
        raise AccountError(400, "wrong_password", "The current password is not right.")
    user = session.get(db.User, user_id)
    check_password_rules(
        config, new, email=credential.email, names=(user.display_name if user else "",)
    )
    credential.password_hash = hash_password(new)
    credential.password_set_at = now()
    revoke_all_sessions(session, user_id)


# --- sign-in and sessions ---------------------------------------------------------------


def login(
    session: Session, config: dict[str, Any], identifier: str, password: str
) -> tuple[str, db.AuthSession, db.Membership | None]:
    """Check the password and open a session. Returns the raw token (for the cookie only).
    The membership is None for a platform admin."""
    refused = AccountError(401, "login_failed", "The email/number or password is not right.")
    rules = settings(config)
    credential = credential_for(session, identifier)
    if credential is None or not credential.password_hash:
        raise refused
    if credential.locked_until and credential.locked_until > now():
        raise AccountError(
            429, "account_locked", "Too many wrong attempts. Wait a few minutes and try again."
        )
    if not verify_password(password or "", credential.password_hash):
        credential.failed_attempts = (credential.failed_attempts or 0) + 1
        if credential.failed_attempts >= int(rules["max_failed_logins"]):
            credential.locked_until = now() + timedelta(minutes=int(rules["lockout_minutes"]))
            credential.failed_attempts = 0
        session.commit()
        raise refused
    membership = None
    if not is_platform_admin(session, credential.user_id):
        membership = active_membership(session, credential.user_id)
        if membership is None or not organization_is_active(
            session, config, membership.organization_id
        ):
            raise AccountError(403, "no_active_membership", "This account has no active access.")
    credential.failed_attempts = 0
    credential.locked_until = None
    if needs_rehash(credential.password_hash):  # an older scrypt (or weaker Argon2) hash
        credential.password_hash = hash_password(password)
    token, row = start_session(session, config, credential.user_id, membership)
    return token, row, membership


def start_session(
    session: Session, config: dict[str, Any], user_id: str, membership: db.Membership | None
) -> tuple[str, db.AuthSession]:
    """Open a session for an account that has already been checked. The raw token is returned
    once (for the cookie); only its hash is stored."""
    token = new_token()
    started = now()
    row = db.AuthSession(
        token_hash=session_hash(token),
        user_id=user_id,
        membership_id=membership.membership_id if membership else None,
        created_at=started,
        last_seen_at=started,
        expires_at=started + timedelta(hours=int(settings(config)["session_max_hours"])),
    )
    session.add(row)
    return token, row


def resolve_session(
    session: Session, config: dict[str, Any], token: str
) -> tuple[db.User, db.Membership | None] | None:
    """The account behind a session token, or None when it is unknown, ended or expired.
    The membership is None for a platform admin."""
    row = session.get(db.AuthSession, session_hash(token))
    if row is None or row.revoked_at is not None:
        return None
    moment = now()
    idle = timedelta(minutes=int(settings(config)["session_idle_minutes"]))
    if row.expires_at <= moment or row.last_seen_at + idle <= moment:
        return None
    membership = None
    if row.membership_id is None:
        if not is_platform_admin(session, row.user_id):
            return None
    else:
        membership = session.get(db.Membership, row.membership_id)
        if membership is None or membership.status != "active":
            return None
        if not organization_is_active(session, config, membership.organization_id):
            return None
    if (moment - row.last_seen_at).total_seconds() > 60:  # keep writes rare
        row.last_seen_at = moment
        session.commit()
    return session.get(db.User, row.user_id), membership


def logout(session: Session, token: str) -> None:
    row = session.get(db.AuthSession, session_hash(token))
    if row is not None and row.revoked_at is None:
        row.revoked_at = now()


def revoke_all_sessions(session: Session, user_id: str) -> None:
    for row in session.scalars(
        select(db.AuthSession).where(
            db.AuthSession.user_id == user_id, db.AuthSession.revoked_at.is_(None)
        )
    ):
        row.revoked_at = now()


def disable_account(session: Session, membership: db.Membership) -> None:
    membership.status = "disabled"
    revoke_all_sessions(session, membership.user_id)
