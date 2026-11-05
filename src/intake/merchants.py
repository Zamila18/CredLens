"""Create a synthetic merchant in the app, and find merchants by id or shop name.

Purpose: the first step of the field workflow: find the shop, or add it.
Owner role: D (full-stack).
Implements: the implementation pack, Phase 3.1.

- The server makes the permanent id (CL-M-000001, CL-M-000002 ...). Nobody types it.
- The shop name and area are labels for people, kept in `merchant_profiles`. Two shops may
  share a name: a likely duplicate is shown, and staff must say on purpose that this is a
  different shop. Nothing is ever merged because names look alike.
- Only the minimum is asked: name, area, district, shop type, trade licence. No national
  id, phone number or owner name.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from src.api.auth import CurrentUser, add_audit
from src.db import models as db
from src.intake.policy import (
    IntakeRefused,
    add_provenance,
    check_business_date,
    check_choice,
    require_synthetic_mode,
    utc_now,
)

ID_PREFIX = "CL-M-"
NAME_MAX = 80
SEARCH_LIMIT = 20


def districts(config: dict[str, Any]) -> dict[str, str]:
    """District -> town tier, from the generator's lists (the same ones the data uses)."""
    return {
        district: tier
        for tier, names in config["generator"]["districts"].items()
        for district in names
    }


def shop_types(config: dict[str, Any]) -> list[str]:
    """The shop types the data knows."""
    return list(config["generator"]["categories"])


def normalised(name: str) -> str:
    """A name for comparing: lower case, letters and digits only, single spaces."""
    return " ".join(re.sub(r"[^\w]+", " ", name.casefold()).split())


def _next_id(session: Session) -> str:
    """The next permanent id. SQLite lets one writer in at a time, so two cannot clash."""
    latest = session.scalar(
        select(func.max(db.Merchant.merchant_id)).where(
            db.Merchant.merchant_id.like(f"{ID_PREFIX}%")
        )
    )
    number = int(latest[len(ID_PREFIX) :]) + 1 if latest else 1
    return f"{ID_PREFIX}{number:06d}"


def likely_duplicates(
    session: Session, shop_name: str, district: str, scope: Any = None
) -> list[dict[str, Any]]:
    """Shops created in the app with the same name (compared loosely) in the same district.

    `scope` is an SQL condition on the merchant (its organisation): a shop of another
    organisation is never shown as a candidate.
    """
    wanted = normalised(shop_name)
    query = (
        select(db.MerchantProfile, db.Merchant.district)
        .join(db.Merchant, db.Merchant.merchant_id == db.MerchantProfile.merchant_id)
        .where(db.Merchant.district == district)
    )
    if scope is not None:
        query = query.where(scope)
    rows = session.execute(query).all()
    return [
        {"merchant_id": profile.merchant_id, "shop_name": profile.shop_name, "area": profile.area}
        for profile, _ in rows
        if normalised(profile.shop_name) == wanted
    ]


def create_merchant(
    session: Session,
    config: dict[str, Any],
    *,
    shop_name: str,
    area: str | None,
    district: str,
    shop_type: str,
    has_trade_license: bool | None,
    business_date: date,
    actor: CurrentUser,
    confirm_new: bool = False,
) -> db.Merchant:
    """Create the merchant and its profile. A likely duplicate is refused (409
    `possible_duplicate`, with the candidates) unless `confirm_new` says it is another shop."""
    require_synthetic_mode(config)
    shop_name = (shop_name or "").strip()
    if not normalised(shop_name) or len(shop_name) > NAME_MAX:
        raise IntakeRefused(
            422, "invalid_name", f"Give the shop's name (at most {NAME_MAX} characters)."
        )
    area = (area or "").strip() or None
    if area and len(area) > NAME_MAX:
        raise IntakeRefused(422, "invalid_name", f"The area is longer than {NAME_MAX} characters.")
    tiers = districts(config)
    check_choice(district, list(tiers), "The district")
    check_choice(shop_type, shop_types(config), "The shop type")
    check_business_date(business_date, config, "The start date")

    from src.api.tenancy import merchant_in_org, org_of

    scope = merchant_in_org(org_of(actor, config), config)
    candidates = likely_duplicates(session, shop_name, district, scope)
    if candidates and not confirm_new:
        raise IntakeRefused(
            409,
            "possible_duplicate",
            f"A shop called '{shop_name}' already exists in {district}. Open it if it is the "
            "same shop, or confirm that this is a different shop.",
            candidates=candidates,
        )

    now = utc_now()
    merchant_id = _next_id(session)
    merchant = db.Merchant(
        merchant_id=merchant_id,
        onboarded_at=business_date,
        district=district,
        town_tier=tiers[district],
        shop_type=shop_type,
        has_trade_license=has_trade_license,
        consent_data_use=False,  # not used anywhere: consent lives in `consents`
        questionnaire_done=False,
        organization_id=actor.organization_id,  # the creator's organisation (empty: default)
    )
    try:
        session.add(merchant)
        session.flush()
        session.add(
            db.MerchantProfile(
                merchant_id=merchant_id,
                shop_name=shop_name,
                area=area,
                created_by=actor.user_id,
                entered_at=now,
            )
        )
        from src.accounts.merchant_access import create_access

        create_access(session, merchant_id, org_of(actor, config))
        add_provenance(
            session,
            record_type="merchant",
            record_id=merchant_id,
            merchant_id=merchant_id,
            source_category="merchant",
            entry_method="staff_entered",
            status="staff_entered",
            actor=actor.user_id,
            entered_at=now,
            business_date=business_date,
        )
        add_audit(session, actor, "create_merchant", merchant_id)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return merchant


def search_merchants(
    session: Session, query: str, limit: int = SEARCH_LIMIT, scope: Any = None
) -> list[dict[str, Any]]:
    """Merchants whose id starts with the query, or whose shop name contains it.

    Benchmark merchants have no name, so they are found by id only.
    """
    text = (query or "").strip()
    if len(text) < 2:
        return []
    pattern = f"%{text}%"
    rows = session.execute(
        select(db.Merchant, db.MerchantProfile)
        .outerjoin(db.MerchantProfile, db.MerchantProfile.merchant_id == db.Merchant.merchant_id)
        .where(
            or_(
                db.Merchant.merchant_id.ilike(f"{text}%"),
                db.MerchantProfile.shop_name.ilike(pattern),
                db.MerchantProfile.area.ilike(pattern),
            ),
            *([scope] if scope is not None else []),
        )
        .order_by(db.MerchantProfile.shop_name.is_(None), db.Merchant.merchant_id)
        .limit(limit)
    ).all()
    return [
        {
            "merchant_id": merchant.merchant_id,
            "shop_name": profile.shop_name if profile else None,
            "area": profile.area if profile else None,
            "district": merchant.district,
            "shop_type": merchant.shop_type,
            "created_in_app": profile is not None,
        }
        for merchant, profile in rows
    ]
