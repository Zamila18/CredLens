"""Decision, model card and audit endpoints.

Purpose: POST /merchants/{id}/decision, GET /decisions, GET /model/card, GET /audit.
Owner role: D (full-stack).
Implements: PROJECT_BRIEF section 8. Request and response shapes are in src/api/schemas.py.

Rules kept here:
- A decision is always an officer's action (accept, override up or down, needs more
  info). There is no approve or decline, and nothing here touches a loan.
- An override without a written reason is rejected (422), by the request shape and, as a
  second guard, by the database.
- The score and the model version stored with a decision are taken from the Scorer on the
  server, never from the request.
- Decisions and audit entries are only ever added: there is no route that edits or
  deletes one.
- /audit is for admins. Reading it writes an audit entry of its own.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import EVERY_ROLE, CurrentUser, add_audit, require_roles
from src.api.common import api_error, card_or_error, utc_now
from src.api.model_card_view import load_model_card
from src.api.schemas import AuditEntry, Decision, DecisionCreate, ModelCard
from src.api.state import Services, get_scorer, get_services, get_session
from src.db import models as db
from src.model.scoring import Scorer

router = APIRouter(tags=["decisions"])

# Most rows GET /audit returns in one answer.
AUDIT_MAX_ROWS = 1000
AUDIT_DEFAULT_ROWS = 200


def _decision_out(row: db.Decision) -> Decision:
    return Decision(
        decision_id=row.decision_id,
        merchant_id=row.merchant_id,
        officer_id=row.officer_id,
        model_version=row.model_version,
        score_shown=row.score_shown,
        officer_action=row.officer_action,
        reason_text=row.reason_text,
        decided_at=row.decided_at.isoformat(timespec="seconds"),
    )


@router.post("/merchants/{merchant_id}/decision", response_model=Decision, status_code=201)
def record_decision(
    merchant_id: str,
    body: DecisionCreate,
    user: CurrentUser = Depends(require_roles("officer")),
    scorer: Scorer = Depends(get_scorer),
    session: Session = Depends(get_session),
) -> Decision:
    """Record an officer's decision on a merchant. Officer only; a viewer can never POST.

    The score shown and the model version come from the Scorer. A merchant without a
    valid consent has no score, so no decision can be recorded (403 `consent_required`).
    """
    if session.get(db.Merchant, merchant_id) is None:
        raise api_error(404, "unknown_merchant", f"No merchant {merchant_id!r} in the database.")
    card = card_or_error(scorer, merchant_id)
    row = db.Decision(
        decision_id=f"DEC-{uuid4().hex}",
        merchant_id=merchant_id,
        officer_id=user.user_id,
        model_version=card["model_version"],
        score_shown=card["score"],
        officer_action=body.officer_action,
        reason_text=(body.reason_text or "").strip() or None,
        decided_at=utc_now(),
    )
    session.add(row)
    add_audit(session, user, "record_decision", merchant_id)
    session.commit()
    return _decision_out(row)


@router.get(
    "/decisions", response_model=list[Decision], dependencies=[Depends(require_roles(*EVERY_ROLE))]
)
def decision_history(
    merchant_id: str | None = None, session: Session = Depends(get_session)
) -> list[Decision]:
    """Decision history, newest first; `merchant_id` narrows it to one merchant."""
    query = select(db.Decision).order_by(db.Decision.decided_at.desc(), db.Decision.decision_id)
    if merchant_id:
        query = query.where(db.Decision.merchant_id == merchant_id)
    return [_decision_out(row) for row in session.scalars(query)]


@router.get(
    "/model/card",
    response_model=ModelCard,
    dependencies=[Depends(require_roles(*EVERY_ROLE))],
)
def model_card(services: Services = Depends(get_services)) -> ModelCard:
    """Model facts and limits. Every role: officers make the decisions, so they need the
    limits most."""
    version = services.scorer.model_version if services.scorer else None
    return load_model_card(services.config["data"]["mode"], version)


@router.get("/audit", response_model=list[AuditEntry])
def audit_log(
    merchant_id: str | None = None,
    limit: int = Query(default=AUDIT_DEFAULT_ROWS, ge=1, le=AUDIT_MAX_ROWS),
    user: CurrentUser = Depends(require_roles("admin")),
    session: Session = Depends(get_session),
) -> list[AuditEntry]:
    """The audit log, newest first. Admin only. This read is itself audited."""
    add_audit(session, user, "view_audit_log")
    session.commit()
    query = select(db.AuditEntry).order_by(db.AuditEntry.id.desc()).limit(limit)
    if merchant_id:
        query = query.where(db.AuditEntry.merchant_id == merchant_id)
    return [
        AuditEntry(
            id=row.id,
            actor=row.actor,
            role=row.role,
            action=row.action,
            merchant_id=row.merchant_id,
            timestamp=row.timestamp.isoformat(timespec="seconds"),
        )
        for row in session.scalars(query)
    ]
