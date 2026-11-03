"""A company's own administration: profile, employees, invitations and shop assignments.

Purpose: a company runs itself. Its owner (the Credit Officer who registered it) invites
    colleagues with a code, sees who joined, resets a password with a one-time code, and
    disables an account. Any Credit Officer gives shops to Field Sales Representatives (FSRs).
Owner role: D (full-stack).
Implements: Phase 1 of the unified platform plan (sections 6 and 7).

Only the owner Credit Officer may touch invitations, employees and the profile; assignments
are open to every Credit Officer. Every route is limited to the caller's own organisation. An
owner never sees or sets a password: a reset returns a one-time setup code, shown once, which
the person uses at /setup-password.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.accounts import invitations, service
from src.accounts.service import AccountError
from src.api.auth import CurrentUser, add_audit, require_owner, require_roles
from src.api.common import api_error
from src.api.schemas import (
    AssignIn,
    AssignmentHistoryOut,
    BulkAssignIn,
    EmployeeOut,
    FsrDetailOut,
    InvitationCreate,
    InvitationCreatedOut,
    InvitationOut,
    InvitationUseOut,
    OrganizationProfileOut,
    OrganizationProfilePatch,
    SetupCodeOut,
    ShopAssignmentOut,
)
from src.api.state import Services, get_services, get_session
from src.api.tenancy import merchant_in_org, org_of
from src.db import models as db

router = APIRouter(tags=["company administration"])

OFFICER = require_roles("credit_officer")


def officer_org(
    officer: CurrentUser = Depends(OFFICER), services: Services = Depends(get_services)
) -> str:
    return org_of(officer, services.config)


def owner_org(
    owner: CurrentUser = Depends(require_owner), services: Services = Depends(get_services)
) -> str:
    return org_of(owner, services.config)


def _refused(error: AccountError):
    return api_error(error.status, error.code, error.message, **error.facts)


def _iso(moment) -> str:
    return moment.isoformat(timespec="seconds")


# --- company profile --------------------------------------------------------------------


def _profile_out(org: db.Organization) -> OrganizationProfileOut:
    return OrganizationProfileOut(
        organization_id=org.organization_id,
        name=org.name,
        legal_name=org.legal_name,
        trading_name=org.trading_name,
        registration_number=org.registration_number,
        org_type=org.org_type,
        sector=org.sector,
        official_email=org.official_email,
        contact_number=org.contact_number,
        country=org.country,
        division=org.division,
        city=org.city,
        address=org.address,
        website=org.website,
        status=org.status,
        environment=org.environment,
        fsr_label=org.fsr_label,
        created_at=_iso(org.created_at),
    )


@router.get("/org/profile", response_model=OrganizationProfileOut)
def company_profile(
    org: str = Depends(officer_org), session: Session = Depends(get_session)
) -> OrganizationProfileOut:
    """The company's registration details."""
    row = session.get(db.Organization, org)
    if row is None:
        raise api_error(404, "unknown_organization", "No such organisation.")
    return _profile_out(row)


@router.patch("/org/profile", response_model=OrganizationProfileOut)
def update_company_profile(
    body: OrganizationProfilePatch,
    owner: CurrentUser = Depends(require_owner),
    org: str = Depends(owner_org),
    session: Session = Depends(get_session),
) -> OrganizationProfileOut:
    """Change the few details an owner may edit (the legal name and registration number are
    fixed at registration)."""
    row = session.get(db.Organization, org)
    if row is None:
        raise api_error(404, "unknown_organization", "No such organisation.")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(row, key, (value or "").strip() or None)
    add_audit(session, owner, "update_company_profile")
    session.commit()
    return _profile_out(row)


# --- employees --------------------------------------------------------------------------


def _employee_out(session: Session, membership: db.Membership) -> EmployeeOut:
    user = session.get(db.User, membership.user_id)
    credential = session.get(db.UserCredential, membership.user_id)
    profile = session.get(db.StaffProfile, membership.user_id)
    shops = session.scalar(
        select(func.count())
        .select_from(db.ShopAssignment)
        .where(
            db.ShopAssignment.fsr_user_id == membership.user_id,
            db.ShopAssignment.ended_at.is_(None),
        )
    )
    return EmployeeOut(
        user_id=user.user_id,
        full_name=(profile.full_name if profile else user.display_name),
        email=credential.email if credential else None,
        mobile=(profile.mobile if profile else None) or (credential.phone if credential else None),
        role=membership.role,
        is_owner=bool(membership.is_owner),
        status=membership.status,
        job_title=profile.job_title if profile else None,
        department=profile.department if profile else None,
        employee_id=profile.employee_id if profile else None,
        territory=profile.territory if profile else None,
        registered_at=_iso(membership.created_at),
        assigned_shops=int(shops or 0),
    )


def _membership(session: Session, org: str, user_id: str) -> db.Membership:
    row = session.scalar(
        select(db.Membership).where(
            db.Membership.user_id == user_id, db.Membership.organization_id == org
        )
    )
    if row is None:
        raise api_error(404, "unknown_employee", "No such person in your company.")
    return row


@router.get("/org/employees", response_model=list[EmployeeOut])
def list_employees(
    org: str = Depends(officer_org), session: Session = Depends(get_session)
) -> list[EmployeeOut]:
    """Everyone in the company, oldest first."""
    rows = session.scalars(
        select(db.Membership)
        .where(db.Membership.organization_id == org)
        .order_by(db.Membership.created_at)
    ).all()
    return [_employee_out(session, row) for row in rows]


@router.post("/org/employees/{user_id}/reset-code", response_model=SetupCodeOut)
def reset_code(
    user_id: str,
    owner: CurrentUser = Depends(require_owner),
    org: str = Depends(owner_org),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> SetupCodeOut:
    """A new one-time code to set a new password (the reset). Earlier codes stop working."""
    membership = _membership(session, org, user_id)
    code = service.issue_setup_code(session, services.config, user_id, owner.user_id)
    add_audit(session, owner, "issue_setup_code")
    session.commit()
    hours = int(services.config["auth"]["setup_code_hours"])
    return SetupCodeOut(
        employee=_employee_out(session, membership),
        setup_code=code,
        expires_at=_iso(service.now() + timedelta(hours=hours)),
    )


@router.post("/org/employees/{user_id}/disable", response_model=EmployeeOut)
def disable_employee(
    user_id: str,
    owner: CurrentUser = Depends(require_owner),
    org: str = Depends(owner_org),
    session: Session = Depends(get_session),
) -> EmployeeOut:
    """Stop an account: it cannot sign in and its sessions end. Its records stay."""
    if user_id == owner.user_id:
        raise api_error(409, "cannot_disable_self", "You cannot disable your own account.")
    membership = _membership(session, org, user_id)
    service.disable_account(session, membership)
    for row in session.scalars(
        select(db.ShopAssignment).where(
            db.ShopAssignment.fsr_user_id == user_id, db.ShopAssignment.ended_at.is_(None)
        )
    ):
        row.ended_at, row.ended_by = service.now(), owner.user_id
    add_audit(session, owner, "disable_account")
    session.commit()
    return _employee_out(session, membership)


# --- invitations ------------------------------------------------------------------------


def _invitation_out(session: Session, row: db.Invitation) -> InvitationOut:
    uses = session.execute(
        select(db.InvitationUse, db.User, db.StaffProfile)
        .join(db.User, db.User.user_id == db.InvitationUse.user_id)
        .outerjoin(db.StaffProfile, db.StaffProfile.user_id == db.InvitationUse.user_id)
        .where(db.InvitationUse.invitation_id == row.invitation_id)
        .order_by(db.InvitationUse.used_at)
    ).all()
    return InvitationOut(
        invitation_id=row.invitation_id,
        role=row.role,
        label=row.label,
        default_territory=row.default_territory,
        code_hint=row.code_hint,
        state=invitations.state_of(row),
        expires_at=_iso(row.expires_at),
        max_uses=row.max_uses,
        use_count=row.use_count,
        created_by=row.created_by,
        created_at=_iso(row.created_at),
        uses=[
            InvitationUseOut(
                user_id=user.user_id,
                display_name=user.display_name,
                employee_id=profile.employee_id if profile else None,
                used_at=_iso(use.used_at),
            )
            for use, user, profile in uses
        ],
    )


@router.get("/org/invitations", response_model=list[InvitationOut])
def list_invitations(
    org: str = Depends(owner_org), session: Session = Depends(get_session)
) -> list[InvitationOut]:
    """The company's invitation codes (never the codes themselves) and who joined with each."""
    rows = session.scalars(
        select(db.Invitation)
        .where(db.Invitation.organization_id == org)
        .order_by(db.Invitation.created_at.desc())
    ).all()
    return [_invitation_out(session, row) for row in rows]


@router.post("/org/invitations", response_model=InvitationCreatedOut, status_code=201)
def create_invitation(
    body: InvitationCreate,
    owner: CurrentUser = Depends(require_owner),
    org: str = Depends(owner_org),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> InvitationCreatedOut:
    """Make an invitation code for FSRs or for another Credit Officer. The code is returned
    once; copy it and share it with the right people."""
    try:
        row, code = invitations.create_invitation(
            session,
            services.config,
            org,
            body.role,
            owner.user_id,
            days=body.days,
            max_uses=body.max_uses,
            default_territory=body.default_territory,
            label=body.label,
        )
    except AccountError as error:
        raise _refused(error) from None
    add_audit(session, owner, "create_invitation")
    session.commit()
    return InvitationCreatedOut(invitation=_invitation_out(session, row), code=code)


@router.post("/org/invitations/{invitation_id}/revoke", response_model=InvitationOut)
def revoke_invitation(
    invitation_id: str,
    owner: CurrentUser = Depends(require_owner),
    org: str = Depends(owner_org),
    session: Session = Depends(get_session),
) -> InvitationOut:
    """Stop a code from working. People who already joined stay."""
    try:
        row = invitations.get_for_org(session, org, invitation_id)
    except AccountError as error:
        raise _refused(error) from None
    invitations.revoke_invitation(session, row, owner.user_id)
    add_audit(session, owner, "revoke_invitation")
    session.commit()
    return _invitation_out(session, row)


@router.post(
    "/org/invitations/{invitation_id}/regenerate",
    response_model=InvitationCreatedOut,
    status_code=201,
)
def regenerate_invitation(
    invitation_id: str,
    owner: CurrentUser = Depends(require_owner),
    org: str = Depends(owner_org),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> InvitationCreatedOut:
    """Revoke a code and make a new one with the same role, limits and territory."""
    try:
        old = invitations.get_for_org(session, org, invitation_id)
        row, code = invitations.regenerate_invitation(session, services.config, old, owner.user_id)
    except AccountError as error:
        raise _refused(error) from None
    add_audit(session, owner, "regenerate_invitation")
    session.commit()
    return InvitationCreatedOut(invitation=_invitation_out(session, row), code=code)


# --- shop assignments -------------------------------------------------------------------


@router.get("/org/assignments", response_model=list[ShopAssignmentOut])
def list_assignments(
    org: str = Depends(officer_org),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> list[ShopAssignmentOut]:
    """Every shop of the organisation with its current FSR (if any)."""
    rows = session.execute(
        select(db.Merchant, db.MerchantProfile)
        .join(db.MerchantProfile, db.MerchantProfile.merchant_id == db.Merchant.merchant_id)
        .where(merchant_in_org(org, services.config))
        .order_by(db.MerchantProfile.shop_name)
    ).all()
    out = []
    for merchant, profile in rows:
        current = service.current_assignment(session, merchant.merchant_id)
        fsr = session.get(db.User, current.fsr_user_id) if current else None
        out.append(
            ShopAssignmentOut(
                merchant_id=merchant.merchant_id,
                shop_name=profile.shop_name,
                area=profile.area,
                district=merchant.district,
                fsr_user_id=current.fsr_user_id if current else None,
                fsr_name=fsr.display_name if fsr else None,
                assigned_at=_iso(current.assigned_at) if current else None,
                assigned_by=current.assigned_by if current else None,
            )
        )
    return out


@router.post("/org/assignments", response_model=ShopAssignmentOut)
def assign(
    body: AssignIn,
    officer: CurrentUser = Depends(OFFICER),
    org: str = Depends(officer_org),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ShopAssignmentOut:
    """Give a shop to an FSR (it leaves its earlier FSR, if any; the history is kept)."""
    try:
        row = service.assign_shop(
            session,
            org,
            body.merchant_id,
            body.fsr_user_id,
            officer.user_id,
            default_org=services.config["organization"]["id"],
        )
    except AccountError as error:
        raise _refused(error) from None
    add_audit(session, officer, "assign_shop", body.merchant_id)
    session.commit()
    profile = session.get(db.MerchantProfile, body.merchant_id)
    merchant = session.get(db.Merchant, body.merchant_id)
    fsr = session.get(db.User, row.fsr_user_id)
    return ShopAssignmentOut(
        merchant_id=body.merchant_id,
        shop_name=profile.shop_name if profile else None,
        area=profile.area if profile else None,
        district=merchant.district,
        fsr_user_id=row.fsr_user_id,
        fsr_name=fsr.display_name,
        assigned_at=_iso(row.assigned_at),
        assigned_by=row.assigned_by,
    )


@router.post("/org/assignments/{merchant_id}/end", status_code=204)
def end_assignment(
    merchant_id: str,
    officer: CurrentUser = Depends(OFFICER),
    org: str = Depends(officer_org),
    session: Session = Depends(get_session),
) -> None:
    """Take a shop away from its FSR. The history stays."""
    try:
        service.end_assignment(session, org, merchant_id, officer.user_id)
    except AccountError as error:
        raise _refused(error) from None
    add_audit(session, officer, "end_assignment", merchant_id)
    session.commit()


@router.post("/org/assignments/bulk", response_model=list[ShopAssignmentOut])
def assign_many(
    body: BulkAssignIn,
    officer: CurrentUser = Depends(OFFICER),
    org: str = Depends(officer_org),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> list[ShopAssignmentOut]:
    """Give several shops to one FSR at once (all or none)."""
    out = []
    try:
        for merchant_id in dict.fromkeys(body.merchant_ids):
            row = service.assign_shop(
                session,
                org,
                merchant_id,
                body.fsr_user_id,
                officer.user_id,
                default_org=services.config["organization"]["id"],
            )
            add_audit(session, officer, "assign_shop", merchant_id)
            out.append(row)
    except AccountError as error:
        session.rollback()
        raise _refused(error) from None
    session.commit()
    return [_assignment_out(session, row) for row in out]


def _assignment_out(session: Session, row: db.ShopAssignment) -> ShopAssignmentOut:
    profile = session.get(db.MerchantProfile, row.merchant_id)
    merchant = session.get(db.Merchant, row.merchant_id)
    fsr = session.get(db.User, row.fsr_user_id)
    return ShopAssignmentOut(
        merchant_id=row.merchant_id,
        shop_name=profile.shop_name if profile else None,
        area=profile.area if profile else None,
        district=merchant.district if merchant else None,
        fsr_user_id=row.fsr_user_id,
        fsr_name=fsr.display_name if fsr else None,
        assigned_at=_iso(row.assigned_at),
        assigned_by=row.assigned_by,
    )


@router.get("/org/assignments/history", response_model=list[AssignmentHistoryOut])
def assignment_history(
    merchant_id: str | None = None,
    fsr_id: str | None = None,
    org: str = Depends(officer_org),
    session: Session = Depends(get_session),
) -> list[AssignmentHistoryOut]:
    """Who had which shop and when, newest first. Ended assignments stay in the history."""
    query = select(db.ShopAssignment).where(db.ShopAssignment.organization_id == org)
    if merchant_id:
        query = query.where(db.ShopAssignment.merchant_id == merchant_id)
    if fsr_id:
        query = query.where(db.ShopAssignment.fsr_user_id == fsr_id)
    out = []
    for row in session.scalars(query.order_by(db.ShopAssignment.assigned_at.desc()).limit(500)):
        profile = session.get(db.MerchantProfile, row.merchant_id)
        fsr = session.get(db.User, row.fsr_user_id)
        out.append(
            AssignmentHistoryOut(
                merchant_id=row.merchant_id,
                shop_name=profile.shop_name if profile else None,
                fsr_user_id=row.fsr_user_id,
                fsr_name=fsr.display_name if fsr else None,
                assigned_at=_iso(row.assigned_at),
                assigned_by=row.assigned_by,
                ended_at=_iso(row.ended_at) if row.ended_at else None,
                ended_by=row.ended_by,
            )
        )
    return out


@router.get("/org/fsrs/{user_id}", response_model=FsrDetailOut)
def fsr_detail(
    user_id: str,
    org: str = Depends(officer_org),
    session: Session = Depends(get_session),
) -> FsrDetailOut:
    """One FSR: their details, their current shops, and what they have been submitting."""
    from src.api.routes_daily import SubmissionOut, _sheet_out

    membership = _membership(session, org, user_id)
    if membership.role != "fsr":
        raise api_error(404, "unknown_employee", "No such FSR in your company.")
    shops = [
        _assignment_out(session, row)
        for row in session.scalars(
            select(db.ShopAssignment).where(
                db.ShopAssignment.fsr_user_id == user_id, db.ShopAssignment.ended_at.is_(None)
            )
        )
    ]
    sheets = session.scalars(
        select(db.DailySheet)
        .where(db.DailySheet.fsr_user_id == user_id)
        .order_by(db.DailySheet.business_date.desc())
        .limit(30)
    ).all()
    recent = []
    for sheet in sheets:
        info = _sheet_out(session, sheet)
        profile = session.get(db.MerchantProfile, sheet.merchant_id)
        recent.append(
            SubmissionOut(
                sheet_id=sheet.sheet_id,
                merchant_id=sheet.merchant_id,
                shop_name=profile.shop_name if profile else None,
                business_date=info.business_date,
                fsr_user_id=user_id,
                fsr_name=info.fsr_name,
                status=sheet.status,
                rows=info.drafts + info.submitted,
                drafts=info.drafts,
                totals=info.totals,
                submitted_at=info.submitted_at,
                returned_reason=sheet.returned_reason,
            )
        )
    return FsrDetailOut(
        employee=_employee_out(session, membership),
        shops=shops,
        recent_sheets=recent,
        drafts_open=sum(1 for s in sheets if s.status == "draft"),
        returned_open=sum(1 for s in sheets if s.status == "returned"),
    )
