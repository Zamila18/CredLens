"""Organisations: who may see which merchants.

Purpose: the institution boundary. Every merchant belongs to one organisation, and so do
    its applications, records, decisions and audit entries. A user sees only their own
    organisation's merchants: asking for another organisation's merchant answers 404, the
    same as a merchant that does not exist, so ids cannot be probed.
Owner role: D (full-stack).
Implements: product reassessment, workstream B (organisation foundation).

An empty `organization_id` means the default organisation (config `organization`). That is
where every benchmark merchant and every existing user lives, so existing databases keep
working after `python -m src.db.upgrade` adds the empty columns.

The guard runs on every request whose path names a merchant (`/merchants/{merchant_id}/…`).
List endpoints filter with `merchant_in_org`, or `merchant_scope` where a sales representative
may call them. Neither replaces the role checks.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.api.auth import CurrentUser
from src.api.common import api_error
from src.db import models as db


def default_org(config: dict[str, Any]) -> str:
    return config["organization"]["id"]


def org_of(user: CurrentUser, config: dict[str, Any]) -> str:
    """The caller's organisation (the default one when the user row names none)."""
    return user.organization_id or default_org(config)


def merchant_in_org(org: str, config: dict[str, Any]):
    """SQL condition: the merchant (db.Merchant) belongs to `org`."""
    column = db.Merchant.organization_id
    if org == default_org(config):
        return or_(column.is_(None), column == org)
    return column == org


def same_org(merchant: db.Merchant, org: str, config: dict[str, Any]) -> bool:
    return (merchant.organization_id or default_org(config)) == org


def org_merchant_ids(session: Session, org: str, config: dict[str, Any]) -> set[str]:
    """Every merchant id of the organisation (used to filter the score-based queue)."""
    return set(session.scalars(select(db.Merchant.merchant_id).where(merchant_in_org(org, config))))


def merchant_scope(session: Session, user: CurrentUser, config: dict[str, Any]):
    """SQL condition on db.Merchant: the merchants this caller may see. The organisation's,
    and for a sales representative only the shops assigned to them."""
    condition = merchant_in_org(org_of(user, config), config)
    if user.role == "fsr":
        from src.accounts.service import assigned_merchant_ids

        condition = condition & db.Merchant.merchant_id.in_(
            list(assigned_merchant_ids(session, user.user_id))
        )
    return condition


def may_see(
    session: Session, user: CurrentUser, merchant: db.Merchant, config: dict[str, Any]
) -> bool:
    """May this caller see this merchant (the merchant guard's rule)."""
    if not same_org(merchant, org_of(user, config), config):
        return False
    if user.role == "fsr":
        from src.accounts.service import assigned_merchant_ids

        return merchant.merchant_id in assigned_merchant_ids(session, user.user_id)
    return True


def merchant_guard(request: Request) -> None:
    """On a path naming a merchant: answer 404 unless the caller may see it (their
    organisation's merchant; for a sales representative, a shop assigned to them).
    Without a caller nothing is decided here; the endpoint's own role check answers 401.
    """
    merchant_id = request.path_params.get("merchant_id")
    user: CurrentUser | None = getattr(request.state, "user", None)
    if not merchant_id or user is None:
        return
    services = request.app.state.services
    with Session(services.engine) as session:
        merchant = session.get(db.Merchant, merchant_id)
        if merchant is None:
            return  # the endpoint answers 404 itself
        if not may_see(session, user, merchant, services.config):
            raise api_error(
                404, "unknown_merchant", f"No merchant {merchant_id!r} in the database."
            )


def organization_out(session: Session, config: dict[str, Any], org: str) -> dict[str, Any]:
    """The organisation's settings: its row, or the default one from the config."""
    row = session.get(db.Organization, org)
    if row is not None:
        return {
            "organization_id": row.organization_id,
            "name": row.name,
            "environment": row.environment,
            "country": row.country,
            "languages": [x for x in row.languages.split("|") if x],
            "currency": row.currency,
            "timezone": row.timezone,
        }
    settings = config["organization"]
    return {
        "organization_id": settings["id"],
        "name": settings["name"],
        "environment": settings["environment"],
        "country": settings["country"],
        "languages": list(settings["languages"]),
        "currency": settings["currency"],
        "timezone": settings["timezone"],
    }
