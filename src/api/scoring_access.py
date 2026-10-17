"""Getting a merchant's score card for an action, and writing down a refusal.

Purpose: the one place that turns "this merchant has no valid consent" into a 403 AND a line in
    the audit log, and that knows whether a merchant has a loan waiting for a decision.
Owner role: D (full-stack).
Implements: Phase 13 review, findings F3 and F5.

A refused attempt is worth a line: who tried to see a score, or to decide, for a merchant who has
not consented. The audit action says what was refused (`refused_score`, `refused_decision`,
`refused_questionnaire`). Nothing is disclosed by a refusal, so if the line cannot be written the
caller still gets the refusal; the failure is logged. (A read that WOULD disclose something is
the other way round: no audit entry, no answer.)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.api.auth import CurrentUser, add_audit
from src.api.common import card_or_error
from src.model.labels import LABELLED
from src.model.scoring import Scorer

log = logging.getLogger("credlens.api")


def note_refusal(
    session: Session, user: CurrentUser, action: str, merchant_id: str | None = None
) -> None:
    """Write the audit entry of a refused attempt. Never raises: a refusal stays a refusal."""
    try:
        add_audit(session, user, action, merchant_id)
        session.commit()
    except Exception:  # noqa: BLE001 - see the module docstring
        session.rollback()
        log.exception("The audit entry of a refused attempt (%s) could not be written", action)


def card_or_refuse(
    scorer: Scorer, merchant_id: str, session: Session, user: CurrentUser, refused_action: str
) -> dict[str, Any]:
    """The merchant's score card, or the HTTP error. A missing consent is also written to the
    audit log as `refused_action`."""
    try:
        return card_or_error(scorer, merchant_id)
    except HTTPException as error:
        detail = error.detail if isinstance(error.detail, dict) else {}
        if detail.get("code") == "consent_required":
            note_refusal(session, user, refused_action, merchant_id)
        raise


def has_pending_loan(scorer: Scorer, merchant_id: str) -> bool:
    """True when the merchant's latest loan has no outcome yet: the cases the queue holds."""
    return scorer.feature_row(merchant_id)["label_status"] != LABELLED
