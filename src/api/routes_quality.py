"""Data quality: the organisation's issues and a person's review of each one.

Purpose: one place where officers see what in the evidence needs attention, and record
    what they found, with a written note.
Owner role: D (full-stack).
Implements: Workstream D (matching and data quality). The checks are in src/api/quality.py.

Rules:
- every role can read; officers and administrators review;
- a review never changes, merges or removes a record, and never changes a score;
- a review is refused when the evidence changed since the issue was read (409), so a
  person never signs off something they did not see;
- everything is scoped to the caller's organisation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api import quality
from src.api.auth import READERS, CurrentUser, add_audit, require_roles
from src.api.common import api_error, refuse_rows_not_shown
from src.api.schemas import (
    QualityEvidence,
    QualityIssueOut,
    QualityReport,
    QualityReviewIn,
    QualityReviewOut,
)
from src.api.state import Services, get_services, get_session
from src.api.tenancy import merchant_in_org, org_of
from src.db import models as db
from src.intake.policy import calendar_end, new_id, utc_now

router = APIRouter(tags=["data quality"])

ANY_ROLE = require_roles(*READERS)
STAFF = require_roles("credit_officer")


def _review_out(row: db.QualityReview, fingerprint: str) -> QualityReviewOut:
    return QualityReviewOut(
        review_id=row.review_id,
        outcome=row.outcome,
        note=row.note,
        actor=row.actor,
        decided_at=row.decided_at.isoformat(timespec="seconds"),
        concern=row.outcome in quality.CONCERNS,
        current=row.fingerprint == fingerprint,
    )


def _issue_out(issue: quality.Issue, reviews: list[db.QualityReview]) -> QualityIssueOut:
    return QualityIssueOut(
        issue_key=issue.key,
        kind=issue.kind,
        group=issue.group,
        status=quality.status_of(issue, reviews),
        merchant_id=issue.merchant_id,
        other_merchant_id=issue.other_merchant_id,
        connection_id=issue.connection_id,
        batch_id=issue.batch_id,
        facts=issue.facts,
        evidence=[QualityEvidence(**vars(e)) for e in issue.evidence],
        fingerprint=issue.fingerprint,
        outcomes=list(issue.outcomes),
        reviews=[_review_out(r, issue.fingerprint) for r in reversed(reviews)],
    )


def _issues(session: Session, services: Services, user: CurrentUser) -> list[quality.Issue]:
    org = org_of(user, services.config)
    return quality.find_issues(session, services.config, org, merchant_in_org(org, services.config))


@router.get("/quality/issues", response_model=QualityReport)
def quality_issues(
    status: str = Query(default="open", pattern="^(open|reviewed|all)$"),
    group: str | None = Query(default=None, max_length=32),
    merchant_id: str | None = Query(default=None, max_length=32),
    user: CurrentUser = Depends(ANY_ROLE),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> QualityReport:
    """The organisation's data-quality issues. `open` includes issues whose evidence changed
    after a review; `merchant_id` keeps the issues about one shop (either side of a pair),
    and the counts follow it. `group` and `status` filter the list only."""
    refuse_rows_not_shown(services.config)
    org = org_of(user, services.config)
    reviews = quality.latest_reviews(session, org)
    rows = [_issue_out(i, reviews.get(i.key, [])) for i in _issues(session, services, user)]
    if merchant_id:
        rows = [r for r in rows if merchant_id in (r.merchant_id, r.other_merchant_id)]
    counts = {"open": 0, "reviewed": 0, "concerns": 0}
    by_kind: dict[str, int] = {}
    for row in rows:
        if row.status == "reviewed":
            counts["reviewed"] += 1
            counts["concerns"] += bool(row.reviews and row.reviews[0].concern)
        else:
            counts["open"] += 1
            by_kind[row.kind] = by_kind.get(row.kind, 0) + 1
    if group:
        rows = [r for r in rows if r.group == group]
    if status == "open":
        rows = [r for r in rows if r.status != "reviewed"]
    elif status == "reviewed":
        rows = [r for r in rows if r.status == "reviewed"]
    add_audit(session, user, "view_quality", merchant_id if rows and merchant_id else None)
    session.commit()
    return QualityReport(
        as_of=calendar_end(services.config).isoformat(), by_kind=by_kind, issues=rows, **counts
    )


@router.post("/quality/reviews", response_model=QualityIssueOut, status_code=201)
def review_issue(
    body: QualityReviewIn,
    user: CurrentUser = Depends(STAFF),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> QualityIssueOut:
    """Record what a person found about one issue, with a note. Changes no record."""
    org = org_of(user, services.config)
    issue = next((i for i in _issues(session, services, user) if i.key == body.issue_key), None)
    if issue is None:
        raise api_error(404, "unknown_issue", "This issue is not open in your organisation.")
    if not issue.outcomes:
        raise api_error(
            409,
            "not_reviewable",
            "This issue is fixed by adding or correcting evidence, not by a review.",
        )
    if body.outcome not in issue.outcomes:
        raise api_error(
            422,
            "invalid_outcome",
            f"Choose one of: {', '.join(issue.outcomes)}.",
            allowed=list(issue.outcomes),
        )
    if body.fingerprint != issue.fingerprint:
        raise api_error(
            409,
            "issue_changed",
            "The records behind this issue changed after you opened it. Read it again first.",
        )
    note = body.note.strip()
    if len(note) < int(services.config["quality"]["note_min_chars"]):
        raise api_error(
            422,
            "note_too_short",
            "Write a short note saying what you checked.",
            min_chars=int(services.config["quality"]["note_min_chars"]),
        )
    row = db.QualityReview(
        review_id=new_id("QR"),
        organization_id=org,
        issue_key=issue.key,
        kind=issue.kind,
        merchant_id=issue.merchant_id,
        fingerprint=issue.fingerprint,
        outcome=body.outcome,
        note=note,
        actor=user.user_id,
        decided_at=utc_now(),
    )
    session.add(row)
    add_audit(session, user, f"quality_{body.outcome}", issue.merchant_id)
    session.commit()
    reviews = quality.latest_reviews(session, org).get(issue.key, [])
    return _issue_out(issue, reviews)
