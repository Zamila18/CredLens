"""Platform administration: the companies on CredLens (CredLens staff only).

Purpose: the four platform administrators (private .env, src/accounts/bootstrap_platform_admins.py)
    see which companies exist, suspend or reactivate one, and help an owner who lost their
    password. They never see a company's merchants, records or documents.
Owner role: D (full-stack).
Implements: Phase 1 of the unified platform plan (section 5).

Every action is written to the audit log with the organisation it touched.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.accounts import service
from src.api.auth import PLATFORM_ADMIN, CurrentUser, require_roles
from src.api.common import api_error
from src.api.routes_org import _employee_out
from src.api.schemas import (
    ConsentTemplateOut,
    ConsentTemplateStatusIn,
    PlatformOrgOut,
    PlatformOrgStatusIn,
    SetupCodeOut,
)
from src.api.state import Services, get_services, get_session
from src.db import models as db
from src.onboarding import consent_text
from src.onboarding.registrations import template_row

router = APIRouter(tags=["platform administration"])

PLATFORM = require_roles(PLATFORM_ADMIN)


def _count(session: Session, org_id: str, role: str | None = None) -> int:
    query = (
        select(func.count())
        .select_from(db.Membership)
        .where(db.Membership.organization_id == org_id, db.Membership.status == "active")
    )
    if role:
        query = query.where(db.Membership.role == role)
    return int(session.scalar(query) or 0)


def _org_out(session: Session, org: db.Organization) -> PlatformOrgOut:
    merchants = session.scalar(
        select(func.count())
        .select_from(db.Merchant)
        .where(db.Merchant.organization_id == org.organization_id)
    )
    return PlatformOrgOut(
        organization_id=org.organization_id,
        name=org.name,
        legal_name=org.legal_name,
        org_type=org.org_type,
        city=org.city,
        status=org.status,
        environment=org.environment,
        created_at=org.created_at.isoformat(timespec="seconds"),
        credit_officers=_count(session, org.organization_id, "credit_officer"),
        records_officers=_count(session, org.organization_id, "records_officer"),
        merchants=int(merchants or 0),
    )


def _audit(session: Session, admin: CurrentUser, action: str, org_id: str) -> None:
    session.add(
        db.AuditEntry(
            actor=admin.user_id,
            role=admin.role,
            action=action,
            merchant_id=None,
            timestamp=service.now(),
            organization_id=org_id,
        )
    )


def _org(session: Session, org_id: str) -> db.Organization:
    row = session.get(db.Organization, org_id)
    if row is None:
        raise api_error(404, "unknown_organization", "No such organisation.")
    return row


@router.get("/platform/orgs", response_model=list[PlatformOrgOut])
def list_orgs(
    admin: CurrentUser = Depends(PLATFORM), session: Session = Depends(get_session)
) -> list[PlatformOrgOut]:
    """Every company, newest first, with head counts only (no merchant data)."""
    rows = session.scalars(
        select(db.Organization).order_by(db.Organization.created_at.desc())
    ).all()
    return [_org_out(session, row) for row in rows]


@router.post("/platform/orgs/{organization_id}/status", response_model=PlatformOrgOut)
def set_status(
    organization_id: str,
    body: PlatformOrgStatusIn,
    admin: CurrentUser = Depends(PLATFORM),
    session: Session = Depends(get_session),
) -> PlatformOrgOut:
    """Suspend a company (nobody in it can sign in; sessions stop working) or reactivate it."""
    org = _org(session, organization_id)
    org.status = body.status
    _audit(session, admin, f"organization_{body.status}", organization_id)
    session.commit()
    return _org_out(session, org)


@router.post("/platform/orgs/{organization_id}/owner-reset", response_model=SetupCodeOut)
def owner_reset(
    organization_id: str,
    admin: CurrentUser = Depends(PLATFORM),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> SetupCodeOut:
    """A one-time code for the company's owner to set a new password. Shown once."""
    _org(session, organization_id)
    owner = session.scalar(
        select(db.Membership).where(
            db.Membership.organization_id == organization_id,
            db.Membership.is_owner.is_(True),
            db.Membership.status == "active",
        )
    )
    if owner is None:
        raise api_error(404, "no_owner", "This company has no active owner.")
    code = service.issue_setup_code(session, services.config, owner.user_id, admin.user_id)
    _audit(session, admin, "owner_reset_code", organization_id)
    session.commit()
    hours = int(services.config["auth"]["setup_code_hours"])
    return SetupCodeOut(
        employee=_employee_out(session, owner),
        setup_code=code,
        expires_at=(service.now() + timedelta(hours=hours)).isoformat(timespec="seconds"),
    )


def _template_out(row: db.ConsentTemplate) -> ConsentTemplateOut:
    return ConsentTemplateOut(
        version=row.version,
        status=row.status,
        legal_review_ref=row.legal_review_ref,
        approved_by=row.approved_by,
        approved_at=row.approved_at.isoformat(timespec="seconds") if row.approved_at else None,
        sections=len(consent_text.SECTIONS),
        note=(
            "Draft wording prepared for review by Bangladesh counsel; not legally reviewed. "
            "Approve only after a lawyer has reviewed it, and record who."
        ),
    )


@router.get("/platform/consent-templates", response_model=list[ConsentTemplateOut])
def list_templates(
    admin: CurrentUser = Depends(PLATFORM), session: Session = Depends(get_session)
) -> list[ConsentTemplateOut]:
    """The consent document versions and where each stands in legal review."""
    template_row(session)  # makes the first row on first use
    session.commit()
    return [_template_out(r) for r in session.scalars(select(db.ConsentTemplate)).all()]


@router.post("/platform/consent-templates/{version}/status", response_model=ConsentTemplateOut)
def set_template_status(
    version: str,
    body: ConsentTemplateStatusIn,
    admin: CurrentUser = Depends(PLATFORM),
    session: Session = Depends(get_session),
) -> ConsentTemplateOut:
    """Move a consent document through review. `approved` needs who reviewed it (legal review
    reference); in production only an approved version can be issued to merchants."""
    row = session.get(db.ConsentTemplate, version)
    if row is None:
        row = template_row(session) if version == consent_text.VERSION else None
    if row is None:
        raise api_error(404, "unknown_template", "No such consent document version.")
    if body.status == "approved":
        if len((body.legal_review_ref or "").strip()) < 8:
            raise api_error(
                422,
                "legal_review_needed",
                "Record who reviewed the text (name, firm, date) before approving it.",
            )
        row.legal_review_ref = body.legal_review_ref.strip()
        row.approved_by, row.approved_at = admin.user_id, service.now()
    else:
        row.approved_by = row.approved_at = None
        if body.legal_review_ref:
            row.legal_review_ref = body.legal_review_ref.strip()
    row.status = body.status
    session.add(
        db.AuditEntry(
            actor=admin.user_id,
            role=admin.role,
            action=f"consent_template_{body.status}",
            merchant_id=None,
            timestamp=service.now(),
            organization_id=None,
            detail=version,
        )
    )
    session.commit()
    return _template_out(row)
