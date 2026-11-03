"""Create the platform administrators listed in the private .env.

Run: python -m src.accounts.bootstrap_platform_admins

Purpose: CredLens staff accounts with platform-wide access are not self-service. Up to four are
    configured in the private .env (never committed):

        CREDLENS_PLATFORM_ADMIN_1_EMAIL=      CREDLENS_PLATFORM_ADMIN_1_PASSWORD=
        ... _2_ ... _3_ ... _4_

Owner role: D (full-stack).
Implements: Phase 1 of the unified platform plan (section 5).

Rules:
- Explicit and idempotent. A configured admin that does not exist is created (Argon2id hash,
  policy checked). One that already exists is left alone: its password is NOT reset by running
  this again or by restarting the server. To set the password again on purpose, pass
  `--reset N` (N = 1 to 4); it asks for nothing and logs nothing.
- Passwords are never printed, logged, returned or stored in plain text. The report names the
  slot and the email only.
- There is no screen or endpoint that creates or promotes a platform admin. Only the rows made
  here can hold the role, and these e-mail addresses cannot be registered as company users.
- A missing email or password for a slot just leaves that slot unconfigured.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from src.accounts.passwords import hash_password
from src.accounts.service import (
    AccountError,
    check_password_rules,
    credential_for,
    make_user,
    normalise_identifier,
    now,
)
from src.config import PROJECT_ROOT, load_config
from src.db import models as db

SLOTS = (1, 2, 3, 4)


@dataclass(frozen=True)
class SlotResult:
    slot: int
    email: str | None
    outcome: str  # created | exists | reset | not_configured | invalid
    detail: str = ""


def _slot_values(env: Mapping[str, str], slot: int) -> tuple[str, str]:
    email = (env.get(f"CREDLENS_PLATFORM_ADMIN_{slot}_EMAIL") or "").strip().lower()
    password = env.get(f"CREDLENS_PLATFORM_ADMIN_{slot}_PASSWORD") or ""
    return email, password


def platform_admin_emails(env: Mapping[str, str] | None = None) -> set[str]:
    """The configured platform admin addresses (reserved: nobody can register them)."""
    if env is None:
        load_dotenv(PROJECT_ROOT / ".env")
        env = os.environ
    return {e for e in (_slot_values(env, n)[0] for n in SLOTS) if e}


def bootstrap(
    session: Session,
    config: dict,
    env: Mapping[str, str],
    reset: tuple[int, ...] = (),
) -> list[SlotResult]:
    """Create (or, for the slots in `reset`, set the password again of) the configured admins.
    The caller commits. Passwords are only read here, never returned."""
    results: list[SlotResult] = []
    for slot in SLOTS:
        email, password = _slot_values(env, slot)
        if not email and not password:
            results.append(SlotResult(slot, None, "not_configured"))
            continue
        normalised, _ = normalise_identifier(email)
        if not normalised or not password:
            results.append(SlotResult(slot, email or None, "invalid", "email or password missing"))
            continue
        existing = credential_for(session, normalised)
        if existing is not None:
            is_admin = session.get(db.PlatformAdmin, existing.user_id) is not None
            if not is_admin:
                results.append(
                    SlotResult(slot, normalised, "invalid", "this email belongs to a company user")
                )
            elif slot in reset:
                try:
                    check_password_rules(config, password, email=normalised)
                except AccountError as error:
                    results.append(SlotResult(slot, normalised, "invalid", error.message))
                    continue
                existing.password_hash = hash_password(password)
                existing.password_set_at = now()
                existing.failed_attempts, existing.locked_until = 0, None
                from src.accounts.service import revoke_all_sessions

                revoke_all_sessions(session, existing.user_id)
                results.append(SlotResult(slot, normalised, "reset"))
            else:
                results.append(SlotResult(slot, normalised, "exists"))
            continue
        try:
            check_password_rules(config, password, email=normalised)
        except AccountError as error:
            results.append(SlotResult(slot, normalised, "invalid", error.message))
            continue
        user = make_user(session, None, f"Platform admin {slot}", normalised, None)
        credential = session.get(db.UserCredential, user.user_id)
        credential.password_hash = hash_password(password)
        credential.password_set_at = now()
        session.add(
            db.PlatformAdmin(user_id=user.user_id, slot=slot, source="env", created_at=now())
        )
        session.add(
            db.AuditEntry(
                actor=user.user_id,
                role="platform_admin",
                action="platform_admin_created",
                merchant_id=None,
                timestamp=now(),
                organization_id=None,
                detail=f'{{"slot": {slot}}}',
            )
        )
        results.append(SlotResult(slot, normalised, "created"))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create the platform admins listed in .env.")
    parser.add_argument(
        "--reset",
        type=int,
        action="append",
        default=[],
        choices=SLOTS,
        help="set the password of this slot again from .env (repeat for several)",
    )
    args = parser.parse_args(argv)
    load_dotenv(PROJECT_ROOT / ".env")

    from sqlalchemy import create_engine

    from src.config import get_database_url
    from src.db.models import Base

    config = load_config()
    engine = create_engine(get_database_url(config))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        results = bootstrap(session, config, os.environ, tuple(args.reset))
        session.commit()
    for r in results:
        line = f"slot {r.slot}: {r.outcome}" + (f" ({r.email})" if r.email else "")
        print(line + (f" - {r.detail}" if r.detail else ""))
    return 1 if any(r.outcome == "invalid" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
