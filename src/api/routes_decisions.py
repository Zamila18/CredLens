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

from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.auth import EVERY_ROLE, CurrentUser, add_audit, require_roles
from src.api.common import api_error, band_rules_for, utc_now
from src.api.model_card_view import load_model_card
from src.api.schemas import AuditEntry, DataMode, Decision, DecisionCreate, ModelCard
from src.api.scoring_access import card_or_refuse, has_pending_loan, note_refusal
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
    response: Response,
    user: CurrentUser = Depends(require_roles("officer")),
    services: Services = Depends(get_services),
    scorer: Scorer = Depends(get_scorer),
    session: Session = Depends(get_session),
) -> Decision:
    """Record an officer's decision on a merchant. Officer only; a viewer can never POST.

    The score shown and the model version come from the Scorer. Refused, and the refusal written
    to the audit log as `refused_decision`:
    - no valid consent: no score, so no decision (403 `consent_required`);
    - no loan waiting: the merchant's latest loan already has an outcome, so there is nothing
      to decide (409 `no_pending_loan`).

    Pressing the button twice: when the same officer records the same action with the same
    reason on the same merchant again within `api.duplicate_decision_seconds` (5), the earlier
    decision is returned (HTTP 200, not 201) and nothing is added.
    """
    if session.get(db.Merchant, merchant_id) is None:
        raise api_error(404, "unknown_merchant", f"No merchant {merchant_id!r} in the database.")
    card = card_or_refuse(scorer, merchant_id, session, user, "refused_decision")
    if not has_pending_loan(scorer, merchant_id):
        note_refusal(session, user, "refused_decision", merchant_id)
        raise api_error(
            409,
            "no_pending_loan",
            "This merchant has no loan waiting for a decision: the latest loan's outcome is "
            "already known.",
        )
    reason = (body.reason_text or "").strip() or None
    window = timedelta(seconds=services.config["api"]["duplicate_decision_seconds"])
    same = (
        db.Decision.officer_id == user.user_id,
        db.Decision.merchant_id == merchant_id,
        db.Decision.officer_action == body.officer_action,
        db.Decision.reason_text.is_(None) if reason is None else db.Decision.reason_text == reason,
        db.Decision.decided_at >= utc_now() - window,
    )
    earlier = session.scalars(
        select(db.Decision).where(*same).order_by(db.Decision.decided_at.desc())
    ).first()
    if earlier is not None:
        response.status_code = 200
        return _decision_out(earlier)
    row = db.Decision(
        decision_id=f"DEC-{uuid4().hex}",
        merchant_id=merchant_id,
        officer_id=user.user_id,
        model_version=card["model_version"],
        score_shown=card["score"],
        officer_action=body.officer_action,
        reason_text=reason,
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
    response: Response,
    merchant_id: str | None = None,
    limit: int | None = Query(default=None, ge=1, description="At most this many; default: all"),
    offset: int = Query(default=0, ge=0, description="Skip this many of the newest"),
    session: Session = Depends(get_session),
) -> list[Decision]:
    """Decision history, newest first; `merchant_id` narrows it to one merchant.

    Without `limit` every decision is returned, as before. With `limit` and `offset` a page is;
    the header `X-Total-Count` always holds how many decisions match (all pages together).
    """
    query = select(db.Decision).order_by(db.Decision.decided_at.desc(), db.Decision.decision_id)
    total = select(func.count()).select_from(db.Decision)
    if merchant_id:
        query = query.where(db.Decision.merchant_id == merchant_id)
        total = total.where(db.Decision.merchant_id == merchant_id)
    response.headers["X-Total-Count"] = str(session.scalar(total))
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    return [_decision_out(row) for row in session.scalars(query)]


@router.get(
    "/model/card",
    response_model=ModelCard,
    dependencies=[Depends(require_roles(*EVERY_ROLE))],
)
def model_card(
    mode: DataMode | None = Query(
        default=None, description="Another data mode's card; default: the mode the API runs"
    ),
    services: Services = Depends(get_services),
) -> ModelCard:
    """Model facts and limits. Every role: officers make the decisions, so they need the
    limits most.

    `?mode=` serves the card of another data mode, so the dashboard can show the public
    data results while the API scores the synthetic data. A card holds totals only, never
    a row, so this is allowed for every mode, Home Credit included.
    """
    running = services.config["data"]["mode"]
    if mode is None or mode == running:
        version = services.scorer.model_version if services.scorer else None
        card = load_model_card(running, version)
    else:
        card = load_model_card(mode, None)
    card.band_rules = band_rules_for(services.config, card.data_mode)
    return card


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
