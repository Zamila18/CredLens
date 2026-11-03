"""Small helpers shared by every endpoint: error shape, clock, score-card lookup.

Purpose: one place for how the API says "no" and for the two rules every score request
    must obey (no valid consent, no score; a data source whose rows may not be shown).
Owner role: D (full-stack).
Implements: PROJECT_BRIEF section 8 and CLAUDE.md (non-negotiable rules).

Every error the API raises on purpose has the same body, so the dashboard can react to
`detail.code` and show `detail.message`:

    {"detail": {"code": "consent_required", "message": "..."}}
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from src.api.schemas import BandRules
from src.model.explain import ConsentRequired, RowsNotShown, refuse_hidden_rows
from src.model.score import band_lines
from src.model.scoring import Scorer, UnknownMerchant


def api_error(status_code: int, code: str, message: str, **facts) -> HTTPException:
    """An HTTP error whose body is {"detail": {"code": ..., "message": ..., ...facts}}."""
    detail = {"code": code, "message": message, **facts}
    return HTTPException(status_code=status_code, detail=detail)


def utc_now() -> datetime:
    """The current time in UTC, without a time zone, as stored in the database."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def refuse_rows_not_shown(config: dict[str, Any]) -> None:
    """403 `rows_not_shown` when the running data mode may never show rows (Home Credit)."""
    try:
        refuse_hidden_rows(config, config["data"]["mode"])
    except RowsNotShown as error:
        raise api_error(403, "rows_not_shown", str(error)) from None


def band_rules_for(config: dict[str, Any], mode: str) -> BandRules:
    """The band lines of a data mode, read from the config (never written in code here)."""
    lines = band_lines(config, mode)
    return BandRules(
        strong_min_score=lines["band_strong_min_score"],
        min_coverage=lines["band_min_coverage"],
        low_score_warning_below=lines["low_score_warning_below"],
    )


def card_or_error(scorer: Scorer, merchant_id: str) -> dict[str, Any]:
    """A merchant's score card, or the right HTTP error.

    - no valid consent: 403 `consent_required` (nothing is computed),
    - a data source whose rows may never be shown: 403 `rows_not_shown`,
    - no loan for that id: 404 `unknown_merchant`,
    - records saved but the assessment could not be redone: 409 `assessment_not_updated`
      (an older score is never shown as current).
    """
    if merchant_id in getattr(scorer, "not_updated", {}):
        raise api_error(
            409,
            "assessment_not_updated",
            "The latest records are saved, but the assessment could not be updated, so no "
            "score is shown. Check the records, or ask an administrator.",
        )
    try:
        return scorer.card(merchant_id)
    except ConsentRequired:
        raise api_error(
            403,
            "consent_required",
            "Consent needed: this merchant has no valid consent, so no score is computed.",
        ) from None
    except RowsNotShown as error:
        raise api_error(403, "rows_not_shown", str(error)) from None
    except UnknownMerchant as error:
        raise api_error(404, "unknown_merchant", str(error.args[0])) from None
