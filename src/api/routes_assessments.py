"""Stored assessments and the company's range policy.

Purpose: the API behind the officer's "Run assessment", the assessment history, the recompute
    check, and the owner's range-policy page.
Owner role: C (assessment).
Implements: Phase 6 of the unified platform plan (section 15).

Decision support only: an assessment is a stored record of what the model and the policy said.
It approves nothing. The company owner approves a range policy; with none approved there is
no range, only the score and reasons.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.accounts.service import now
from src.api.auth import CurrentUser, add_audit, require_owner, require_roles
from src.api.common import api_error
from src.api.imported import refresh_scoring
from src.api.scoring_access import note_refusal
from src.api.state import Services, get_services, get_session
from src.api.tenancy import org_of
from src.assessment import range_engine, service
from src.db import models as db
from src.model.explain import ConsentRequired
from src.model.scoring import UnknownMerchant

router = APIRouter(tags=["assessments"])
OFFICER = require_roles("credit_officer")
READ = require_roles("credit_officer", "auditor")


class AssessmentOut(BaseModel):
    assessment_id: str
    merchant_id: str
    status: str
    model_version: str
    probability: float
    score: int
    band: str
    coverage: float
    low_score_warning: bool
    input_snapshot: dict[str, float | None]
    evidence_refs: dict[str, Any]
    reasons_positive: list[Any]
    reasons_negative: list[Any]
    summary_en: str | None
    summary_bn: str | None
    range_policy_id: str | None
    range_available: bool
    range_reason: str | None
    range_min_bdt: float | None
    range_max_bdt: float | None
    currency: str
    range_inputs: dict[str, Any]
    range_reasoning: list[str]
    assessed_by: str
    assessed_at: str


class VerifyOut(BaseModel):
    probability_matches: bool
    range_matches: bool
    recomputed_probability: float
    recomputed_range: list[float] | None


class PolicyIn(BaseModel):
    parameters: dict[str, Any]
    note: str | None = Field(default=None, max_length=300)


class PolicyOut(BaseModel):
    policy_id: str
    version: int
    status: str
    parameters: dict[str, Any]
    note: str | None
    created_by: str
    created_at: str
    approved_by: str | None
    approved_at: str | None


def _out(row: db.Assessment) -> AssessmentOut:
    return AssessmentOut(
        assessment_id=row.assessment_id,
        merchant_id=row.merchant_id,
        status=row.status,
        model_version=row.model_version,
        probability=row.probability,
        score=row.score,
        band=row.band,
        coverage=row.coverage,
        low_score_warning=row.low_score_warning,
        input_snapshot=json.loads(row.input_snapshot),
        evidence_refs=json.loads(row.evidence_refs),
        reasons_positive=json.loads(row.reasons_positive),
        reasons_negative=json.loads(row.reasons_negative),
        summary_en=row.summary_en,
        summary_bn=row.summary_bn,
        range_policy_id=row.range_policy_id,
        range_available=row.range_available,
        range_reason=row.range_reason,
        range_min_bdt=row.range_min_bdt,
        range_max_bdt=row.range_max_bdt,
        currency=row.currency,
        range_inputs=json.loads(row.range_inputs or "{}"),
        range_reasoning=json.loads(row.range_reasoning or "[]"),
        assessed_by=row.assessed_by,
        assessed_at=row.assessed_at.isoformat(timespec="seconds"),
    )


def _policy_out(row: db.RangePolicy) -> PolicyOut:
    return PolicyOut(
        policy_id=row.policy_id,
        version=row.version,
        status=row.status,
        parameters=json.loads(row.parameters),
        note=row.note,
        created_by=row.created_by,
        created_at=row.created_at.isoformat(timespec="seconds"),
        approved_by=row.approved_by,
        approved_at=row.approved_at.isoformat(timespec="seconds") if row.approved_at else None,
    )


@router.post("/merchants/{merchant_id}/assessments", response_model=AssessmentOut, status_code=201)
def run_assessment(
    merchant_id: str,
    user: CurrentUser = Depends(OFFICER),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> AssessmentOut:
    """Score the merchant now and store the assessment (superseding the previous one)."""
    refresh_scoring(services, session)
    scorer = services.scorer
    if scorer is None:
        raise api_error(503, "no_model", "No model is loaded.")
    try:
        row = service.run_assessment(
            session,
            scorer,
            org_of(user, services.config),
            user.user_id,
            merchant_id,
            services.data_today(session),
        )
    except ConsentRequired:
        note_refusal(session, user, "refused_assessment", merchant_id)
        raise api_error(
            403, "consent_required", "This merchant has no valid consent, so no assessment."
        ) from None
    except UnknownMerchant:
        raise api_error(409, "no_loan_data", "There is nothing to assess yet.") from None
    add_audit(session, user, "run_assessment", merchant_id)
    session.commit()
    return _out(row)


@router.get("/merchants/{merchant_id}/assessments", response_model=list[AssessmentOut])
def list_assessments(
    merchant_id: str,
    user: CurrentUser = Depends(READ),
    session: Session = Depends(get_session),
) -> list[AssessmentOut]:
    """Every stored assessment of the merchant, newest first."""
    rows = session.scalars(
        select(db.Assessment)
        .where(db.Assessment.merchant_id == merchant_id)
        .order_by(db.Assessment.assessed_at.desc())
    ).all()
    return [_out(r) for r in rows]


@router.get("/merchants/{merchant_id}/assessments/{assessment_id}/verify", response_model=VerifyOut)
def verify_assessment(
    merchant_id: str,
    assessment_id: str,
    user: CurrentUser = Depends(READ),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> VerifyOut:
    """Recompute a stored assessment from its own inputs and policy; say whether it matches."""
    row = session.get(db.Assessment, assessment_id)
    if row is None or row.merchant_id != merchant_id:
        raise api_error(404, "unknown_assessment", "No such assessment.")
    return VerifyOut(**service.reproduce(session, services.scorer, row))


# --- the company range policy ------------------------------------------------------------


@router.get("/org/range-policies", response_model=list[PolicyOut])
def list_policies(
    user: CurrentUser = Depends(READ),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> list[PolicyOut]:
    rows = session.scalars(
        select(db.RangePolicy)
        .where(db.RangePolicy.organization_id == org_of(user, services.config))
        .order_by(db.RangePolicy.version.desc())
    ).all()
    return [_policy_out(r) for r in rows]


@router.post("/org/range-policies", response_model=PolicyOut, status_code=201)
def create_policy(
    body: PolicyIn,
    user: CurrentUser = Depends(require_owner),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> PolicyOut:
    """Write a new draft policy (nothing is in force until the owner approves it)."""
    try:
        params = range_engine.check_parameters(body.parameters)
    except range_engine.PolicyError as error:
        raise api_error(422, "invalid_policy", str(error)) from None
    org = org_of(user, services.config)
    last = session.scalar(
        select(db.RangePolicy.version)
        .where(db.RangePolicy.organization_id == org)
        .order_by(db.RangePolicy.version.desc())
    )
    row = db.RangePolicy(
        policy_id=f"RP-{uuid.uuid4().hex[:20]}",
        organization_id=org,
        version=(last or 0) + 1,
        status="draft",
        parameters=json.dumps(params),
        note=body.note,
        created_by=user.user_id,
        created_at=now(),
    )
    session.add(row)
    add_audit(session, user, "create_range_policy")
    session.commit()
    return _policy_out(row)


def _owned(session: Session, policy_id: str, org: str) -> db.RangePolicy:
    row = session.get(db.RangePolicy, policy_id)
    if row is None or row.organization_id != org:
        raise api_error(404, "unknown_policy", "No such policy.")
    return row


@router.post("/org/range-policies/{policy_id}/approve", response_model=PolicyOut)
def approve_policy(
    policy_id: str,
    user: CurrentUser = Depends(require_owner),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> PolicyOut:
    """Put a draft in force; the policy in force until now is retired (and kept)."""
    org = org_of(user, services.config)
    row = _owned(session, policy_id, org)
    if row.status != "draft":
        raise api_error(409, "not_a_draft", "Only a draft policy can be approved.")
    current = service.approved_policy(session, org)
    if current is not None:
        current.status = "retired"
    row.status, row.approved_by, row.approved_at = "approved", user.user_id, now()
    add_audit(session, user, "approve_range_policy")
    session.commit()
    return _policy_out(row)


@router.post("/org/range-policies/{policy_id}/retire", response_model=PolicyOut)
def retire_policy(
    policy_id: str,
    user: CurrentUser = Depends(require_owner),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> PolicyOut:
    """Take a policy out of force; ranges are then unavailable until another is approved."""
    row = _owned(session, policy_id, org_of(user, services.config))
    if row.status == "retired":
        raise api_error(409, "already_retired", "This policy is already retired.")
    row.status = "retired"
    add_audit(session, user, "retire_range_policy")
    session.commit()
    return _policy_out(row)
