"""Limits on how fast one address or one identifier may try a public, guessable action.

Purpose: slow down password guessing, mass registration and invitation-code guessing. The
    per-account lockout (service.login) stays; this adds a per-address and a per-identifier
    window that also covers actions with no account yet (registration, checking a code).
Owner role: D (full-stack).

Tries are rows in `auth_attempts` (no password or code is stored; the identifier is hashed),
so the limit holds across several server processes. Rows older than a day are removed. Behind
a reverse proxy, set CREDLENS_TRUST_PROXY=1 to read the address from X-Forwarded-For (only do
this when the proxy sets that header itself). Nginx `limit_req` in front is a second layer.
"""

from __future__ import annotations

import hashlib
import os
from datetime import timedelta
from typing import Any

from fastapi import Request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from src.accounts.service import AccountError, now
from src.db import models as db


def client_ip(request: Request) -> str:
    if os.environ.get("CREDLENS_TRUST_PROXY", "").strip() == "1":
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()[:64]
    return (request.client.host if request.client else "unknown")[:64]


def identifier_key(identifier: str) -> str:
    return hashlib.sha256((identifier or "").strip().lower().encode("utf-8")).hexdigest()


def _count(session: Session, kind: str, column, value: str, since, failures_only: bool) -> int:
    query = (
        select(func.count())
        .select_from(db.AuthAttempt)
        .where(db.AuthAttempt.kind == kind, column == value, db.AuthAttempt.at >= since)
    )
    if failures_only:
        query = query.where(db.AuthAttempt.succeeded.is_(False))
    return int(session.scalar(query) or 0)


def check(
    session: Session,
    config: dict[str, Any],
    kind: str,
    ip: str,
    identifier: str | None,
    *,
    per_ip: str,
    per_identifier: str | None = None,
    failures_only: bool = False,
) -> None:
    """Refuse (429) when the address or the identifier has tried too often in the window."""
    limits = config["auth"]["rate_limit"]
    since = now() - timedelta(minutes=int(limits["window_minutes"]))
    too_many = AccountError(
        429, "too_many_attempts", "Too many attempts. Wait a few minutes and try again."
    )
    if _count(session, kind, db.AuthAttempt.ip, ip, since, failures_only) >= int(limits[per_ip]):
        raise too_many
    if identifier and per_identifier:
        key = identifier_key(identifier)
        if _count(session, kind, db.AuthAttempt.identifier_hash, key, since, failures_only) >= int(
            limits[per_identifier]
        ):
            raise too_many


def record(session: Session, kind: str, ip: str, identifier: str | None, succeeded: bool) -> None:
    """Remember one try. The caller commits."""
    session.add(
        db.AuthAttempt(
            kind=kind,
            ip=ip,
            identifier_hash=identifier_key(identifier) if identifier else None,
            succeeded=succeeded,
            at=now(),
        )
    )
    session.execute(delete(db.AuthAttempt).where(db.AuthAttempt.at < now() - timedelta(days=1)))
