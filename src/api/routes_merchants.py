"""Merchant endpoints: review queue, profile, score and questionnaire.

Purpose: GET /merchants, GET /merchants/{id}, GET /merchants/{id}/score and
    POST /merchants/{id}/questionnaire.
Owner role: D (full-stack).
Implements: PROJECT_BRIEF sections 8 and 18 (item 20). Response shapes are in
    src/api/schemas.py and sample responses are in tests/fixtures/api/.

Rules kept here:
- Every read of a profile or a score writes an audit entry, before anything is returned.
  If the audit entry cannot be written, nothing is returned.
- No valid consent, no score (403 `consent_required`).
- Scores, coverage and bands come from the Scorer. Nothing is computed here.
- Nothing here changes a loan, and nothing here approves or declines anything.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

import pandas as pd
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import EVERY_ROLE, CurrentUser, add_audit, require_roles
from src.api.common import api_error, band_rules_for, refuse_rows_not_shown
from src.api.profile import (
    QUESTIONNAIRE_CONSENT_CATEGORY,
    build_profile,
    consent_state,
    questionnaire_summary,
)
from src.api.schemas import (
    Band,
    ConsentView,
    MerchantProfile,
    MerchantQueueItem,
    QuestionnaireCreate,
    QuestionnaireSummary,
    ScoreResponse,
)
from src.api.scoring_access import card_or_refuse, note_refusal
from src.api.state import Services, get_scorer, get_services, get_session
from src.db import models as db
from src.model.explain import RowsNotShown
from src.model.scoring import Scorer, UnknownMerchant

router = APIRouter(tags=["merchants"])

ANY_ROLE = require_roles(*EVERY_ROLE)
OFFICER_ONLY = require_roles("officer")


def _known_merchant(session: Session, merchant_id: str) -> db.Merchant:
    merchant = session.get(db.Merchant, merchant_id)
    if merchant is None:
        raise api_error(404, "unknown_merchant", f"No merchant {merchant_id!r} in the database.")
    return merchant


def _refuse_hidden_rows(services: Services) -> None:
    """A data mode whose rows may never be shown (Home Credit) has no merchant pages."""
    refuse_rows_not_shown(services.config)


def _optional(value, cast):
    return None if value is None or pd.isna(value) else cast(value)


@router.get("/merchants", response_model=list[MerchantQueueItem])
def review_queue(
    status_filter: Literal["pending", "decided"] | None = Query(default=None, alias="status"),
    band: Band | None = None,
    town_tier: str | None = None,
    user: CurrentUser = Depends(ANY_ROLE),
    scorer: Scorer = Depends(get_scorer),
    session: Session = Depends(get_session),
) -> list[MerchantQueueItem]:
    """The review queue: merchants whose latest loan has no outcome yet, oldest first.

    `status` is "decided" when an officer has recorded a decision on the merchant (the
    decisions table has no loan id, so one decision covers the merchant), else "pending".
    Pending merchants come first. A merchant without consent is listed with no score,
    coverage or band. The queue shows the score and band of thousands of merchants, so every
    read writes an audit entry `view_queue` (before the list is returned).
    """
    try:
        queue = scorer.queue()
    except RowsNotShown as error:
        raise api_error(403, "rows_not_shown", str(error)) from None
    if queue.empty:
        add_audit(session, user, "view_queue")
        session.commit()
        return []

    details = {
        row.merchant_id: row
        for row in session.execute(
            select(
                db.Merchant.merchant_id,
                db.Merchant.onboarded_at,
                db.Merchant.district,
                db.Merchant.town_tier,
                db.Merchant.shop_type,
            )
        )
    }
    decided = set(session.scalars(select(db.Decision.merchant_id).distinct()))

    items: list[MerchantQueueItem] = []
    for row in queue.itertuples(index=False):
        merchant = details.get(row.merchant_id)
        if merchant is None:
            raise api_error(
                500,
                "data_mismatch",
                f"Merchant {row.merchant_id} is in the scorer but not in the database. "
                "Load the same data into both: python tasks.py data --reset-db",
            )
        is_decided = row.merchant_id in decided
        items.append(
            MerchantQueueItem(
                merchant_id=row.merchant_id,
                district=merchant.district,
                town_tier=merchant.town_tier,
                shop_type=merchant.shop_type,
                onboarded_at=merchant.onboarded_at.isoformat(),
                status="decided" if is_decided else "pending",
                pending_since=None if is_decided else row.pending_since,
                score=_optional(row.score, int),
                coverage=_optional(row.coverage, float),
                band=_optional(row.band, str),
                low_score_warning=_optional(row.low_score_warning, bool),
                consent_valid=bool(row.consent_valid),
            )
        )

    if status_filter:
        items = [item for item in items if item.status == status_filter]
    if band:
        items = [item for item in items if item.band == band]
    if town_tier:
        items = [item for item in items if item.town_tier == town_tier]
    items.sort(
        key=lambda item: (item.status != "pending", item.pending_since or "", item.merchant_id)
    )
    add_audit(session, user, "view_queue")
    session.commit()
    return items


@router.get("/merchants/{merchant_id}", response_model=MerchantProfile)
def merchant_profile(
    merchant_id: str,
    user: CurrentUser = Depends(ANY_ROLE),
    services: Services = Depends(get_services),
    scorer: Scorer = Depends(get_scorer),
    session: Session = Depends(get_session),
) -> MerchantProfile:
    """The merchant's profile and timeline. Writes an audit entry.

    Without a valid consent the profile says `consent_valid: false` and holds no
    behaviour: no summaries, no questionnaire, no timeline.
    """
    _refuse_hidden_rows(services)
    merchant = _known_merchant(session, merchant_id)
    as_of = services.data_today(session)
    consent_valid, _ = consent_state(session, merchant_id, as_of)
    feature_row = None
    if consent_valid:
        try:
            feature_row = scorer.feature_row(merchant_id)
        except UnknownMerchant:
            feature_row = None  # a merchant with no loan has no 90-day summaries
    profile = build_profile(
        session, merchant, services.config["data"]["mode"], consent_valid, feature_row, as_of
    )
    add_audit(session, user, "view_profile", merchant_id)
    session.commit()
    return profile


@router.get("/merchants/{merchant_id}/score", response_model=ScoreResponse)
def merchant_score(
    merchant_id: str,
    user: CurrentUser = Depends(ANY_ROLE),
    scorer: Scorer = Depends(get_scorer),
    session: Session = Depends(get_session),
) -> dict:
    """The score card: score, coverage, band, reasons and the model version. Audited.

    403 `consent_required` when the merchant has no valid consent: nothing is computed.
    """
    card = card_or_refuse(scorer, merchant_id, session, user, "refused_score")
    card["band_rules"] = band_rules_for(scorer.config, card["data_mode"])
    add_audit(session, user, "view_score", merchant_id)
    session.commit()
    return card


@router.get("/merchants/{merchant_id}/consent", response_model=ConsentView)
def merchant_consent(
    merchant_id: str,
    user: CurrentUser = Depends(ANY_ROLE),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ConsentView:
    """The merchant's consent, read live from the database. Every role. Audited.

    There is no endpoint to revoke a consent: the scorer reads consent once, when the API
    starts, so a revoked consent would still be scored until a restart. Revoking must
    wait until scoring checks consent live.
    """
    _refuse_hidden_rows(services)
    _known_merchant(session, merchant_id)
    as_of = services.data_today(session)
    valid, categories = consent_state(session, merchant_id, as_of)
    rows = session.scalars(
        select(db.Consent)
        .where(db.Consent.merchant_id == merchant_id)
        .order_by(db.Consent.granted_at)
    ).all()
    records = [
        {
            "consent_id": row.consent_id,
            "purpose": row.purpose,
            "data_categories": row.data_categories,
            "granted_at": row.granted_at.isoformat() if row.granted_at else None,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
        }
        for row in rows
    ]
    add_audit(session, user, "view_consent", merchant_id)
    session.commit()
    return ConsentView(
        merchant_id=merchant_id,
        valid=valid,
        as_of=as_of.isoformat(),
        data_categories=sorted(categories),
        records=records,
    )


@router.post("/merchants/{merchant_id}/questionnaire", response_model=QuestionnaireSummary)
def save_questionnaire(
    merchant_id: str,
    answers: QuestionnaireCreate,
    user: CurrentUser = Depends(OFFICER_ONLY),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> QuestionnaireSummary:
    """Record the merchant's ten answers (1 to 5). Officer only. Audited.

    Needs a valid consent that covers the questionnaire. Saving again replaces the earlier
    answers (the audit log keeps the history of who saved and when). It never changes the
    score, which does not use the questionnaire.
    """
    _refuse_hidden_rows(services)
    merchant = _known_merchant(session, merchant_id)
    valid, categories = consent_state(session, merchant_id, services.data_today(session))
    if not valid:
        note_refusal(session, user, "refused_questionnaire", merchant_id)
        raise api_error(
            403,
            "consent_required",
            "Consent needed: this merchant has no valid consent, so nothing is recorded.",
        )
    if QUESTIONNAIRE_CONSENT_CATEGORY not in categories:
        note_refusal(session, user, "refused_questionnaire", merchant_id)
        raise api_error(
            403,
            "consent_scope",
            "The merchant's consent does not cover the questionnaire, so nothing is recorded.",
        )
    session.merge(
        db.Questionnaire(merchant_id=merchant_id, answered_at=date.today(), **answers.model_dump())
    )
    merchant.questionnaire_done = True
    add_audit(session, user, "record_questionnaire", merchant_id)
    session.commit()
    summary = questionnaire_summary(session, merchant_id)
    assert summary is not None
    return summary
