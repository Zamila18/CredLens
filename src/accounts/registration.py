"""Registration: a new company with its first Credit Officer, and an employee joining it.

Purpose: let a financial service provider register itself and its people without a developer.
Owner role: D (full-stack).
Implements: Phase 1 of the unified platform plan (sections 5 and 6).

Rules:
- The first Credit Officer of a company registers the company and becomes its owner: its
  primary representative, who manages invitations, staff and assignments.
- Everyone else joins through an invitation code. The organisation and the role come only from
  the code; nothing the person types can choose either.
- No one-time code and no second verification step: the person sets a password (12 characters,
  policy in passwords.py) and signs in. A work email here is therefore NOT verified; an
  invitation code verifies only the link to the organisation.
- Email addresses are unique ignoring case. A company registration number is unique after
  removing spaces, dashes and case. Employee IDs are unique within a company.
- The e-mail addresses of the platform administrators (private .env) cannot be registered.
- All required details are checked together, and each problem is named by field.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.accounts import invitations
from src.accounts.bootstrap_platform_admins import platform_admin_emails
from src.accounts.passwords import hash_password
from src.accounts.service import (
    AccountError,
    add_membership,
    check_password_rules,
    create_organization,
    credential_for,
    make_user,
    normalise_identifier,
    now,
)
from src.db import models as db

ORG_TYPES = (
    "bank",
    "nbfi",
    "mfi",
    "cooperative",
    "fintech_lender",
    "distributor_lender",
    "other",
)
# Regulated lenders have a registration or licence number; others may leave it empty.
NUMBER_REQUIRED_FOR = ("bank", "nbfi", "mfi", "cooperative", "fintech_lender")
URL = re.compile(r"^(https?://)?[^\s/$.?#][^\s]*\.[^\s]{2,}$", re.IGNORECASE)


def norm_number(value: str) -> str:
    """A registration number without spaces, dashes or case: 'C-12 345' and 'c12345' match."""
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def _text(data: dict[str, Any], key: str) -> str:
    return str(data.get(key) or "").strip()


def _audit(
    session: Session, user_id: str, role: str, action: str, org_id: str | None, **detail: Any
) -> None:
    session.add(
        db.AuditEntry(
            actor=user_id,
            role=role,
            action=action,
            merchant_id=None,
            timestamp=now(),
            organization_id=org_id,
            detail=json.dumps(detail, sort_keys=True) if detail else None,
        )
    )


def _check_person(
    config: dict[str, Any], data: dict[str, Any], errors: dict[str, str]
) -> tuple[str | None, str | None]:
    """Shared checks of the personal part. Returns (email, mobile) normalised."""
    name = _text(data, "full_name")
    if not 2 <= len(name) <= 120:
        errors["full_name"] = "Give your full name (2 to 120 characters)."
    email, _ = normalise_identifier(_text(data, "email"))
    if not email:
        errors["email"] = "Give a valid work email address."
    _, mobile = normalise_identifier(_text(data, "mobile"))
    if not mobile:
        errors["mobile"] = "Give a valid mobile number, for example 01712345678."
    if len(_text(data, "department")) > 80:
        errors["department"] = "Use at most 80 characters."
    password = str(data.get("password") or "")
    if password != str(data.get("confirm_password") or ""):
        errors["confirm_password"] = "The two passwords do not match."
    else:
        try:
            check_password_rules(config, password, email=email, names=(name,))
        except AccountError as error:
            errors["password"] = error.message
    return email, mobile


def _refuse_if_taken(session: Session, email: str | None, mobile: str | None) -> None:
    """The same answer for 'exists' and 'reserved', so the form does not list who is a member."""
    taken = AccountError(
        409, "identifier_taken", "An account with this email address or mobile number exists."
    )
    if email and email in platform_admin_emails():
        raise AccountError(
            409,
            "identifier_reserved",
            "This email is reserved for CredLens platform administrators. Use a different work "
            "email.",
            fields={"email": "This email is reserved for CredLens platform administrators."},
        )
    if email and credential_for(session, email) is not None:
        raise taken
    if mobile and credential_for(session, mobile) is not None:
        raise taken


JOB_TITLES = {"credit_officer": "Credit Officer", "records_officer": "Records Officer"}


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:30].strip("-")
    return slug if len(slug) >= 3 else "company"


def register_company(
    session: Session, config: dict[str, Any], data: dict[str, Any]
) -> tuple[db.User, db.Organization]:
    """A new company and its first Credit Officer (the owner). The caller commits."""
    errors: dict[str, str] = {}
    email, mobile = _check_person(config, data, errors)

    legal = _text(data, "legal_name")
    if not 2 <= len(legal) <= 160:
        errors["legal_name"] = "Give the company's legal name."
    org_type = _text(data, "org_type")
    if org_type not in ORG_TYPES:
        errors["org_type"] = "Choose the type of organisation."
    number = _text(data, "registration_number")
    if not number and org_type in NUMBER_REQUIRED_FOR:
        errors["registration_number"] = (
            "Give the company registration or licence number (required for this type)."
        )
    if number and len(norm_number(number)) < 4:
        errors["registration_number"] = "This registration number looks too short."
    if not 2 <= len(_text(data, "sector")) <= 80:
        errors["sector"] = "Give the business sector."
    official_email, _ = normalise_identifier(_text(data, "official_email"))
    if not official_email:
        errors["official_email"] = "Give the company's official email address."
    _, contact = normalise_identifier(_text(data, "contact_number"))
    if not contact:
        errors["contact_number"] = "Give the company's contact number."
    country = _text(data, "country").upper() or "BD"
    if not re.fullmatch(r"[A-Z]{2}", country):
        errors["country"] = "Give the two-letter country code, for example BD."
    for key, label in (("division", "division or state"), ("city", "city")):
        if not 2 <= len(_text(data, key)) <= 80:
            errors[key] = f"Give the {label}."
    if not 8 <= len(_text(data, "address")) <= 400:
        errors["address"] = "Give the full business address (8 to 400 characters)."
    website = _text(data, "website")
    if website and not URL.match(website):
        errors["website"] = "This does not look like a web address."
    if errors:
        raise AccountError(422, "invalid_fields", "Some details need fixing.", fields=errors)

    _refuse_if_taken(session, email, mobile)
    norm = norm_number(number) or None
    if norm and session.scalar(
        select(db.Organization.organization_id).where(
            db.Organization.registration_number_norm == norm
        )
    ):
        raise AccountError(
            409,
            "company_already_registered",
            "A company with this registration number is already on CredLens. Ask an owner of "
            "that company for an invitation.",
        )
    if session.scalar(
        select(db.Organization.organization_id).where(
            func.lower(db.Organization.legal_name) == legal.lower(),
            func.lower(db.Organization.city) == _text(data, "city").lower(),
        )
    ):
        raise AccountError(
            409,
            "company_may_exist",
            "A company with this name in this city may already be on CredLens. Ask an owner "
            "of that company for an invitation.",
        )

    trading = _text(data, "trading_name") or None
    org_id = f"{_slug(trading or legal)}-{uuid.uuid4().hex[:6]}"
    org = create_organization(
        session,
        org_id,
        trading or legal,
        config["auth"].get("new_company_environment", "pilot"),
        country=country,
        legal_name=legal,
        trading_name=trading,
        registration_number=number or None,
        registration_number_norm=norm,
        org_type=org_type,
        sector=_text(data, "sector"),
        official_email=official_email,
        contact_number=contact,
        division=_text(data, "division"),
        city=_text(data, "city"),
        address=_text(data, "address"),
        website=website or None,
    )
    session.flush()
    user = make_user(session, org_id, _text(data, "full_name"), email, mobile)
    credential = session.get(db.UserCredential, user.user_id)
    credential.password_hash = hash_password(str(data["password"]))
    credential.password_set_at = now()
    add_membership(session, user.user_id, org_id, "credit_officer", None, is_owner=True)
    session.add(
        db.StaffProfile(
            user_id=user.user_id,
            organization_id=org_id,
            full_name=_text(data, "full_name"),
            job_title="Credit Officer (owner)",
            department=_text(data, "department") or None,
            mobile=mobile,
            created_at=now(),
        )
    )
    org.created_by = user.user_id
    _audit(session, user.user_id, "credit_officer", "register_company", org_id, legal=legal)
    return user, org


def register_join(
    session: Session, config: dict[str, Any], data: dict[str, Any]
) -> tuple[db.User, db.Organization, str]:
    """An employee joining an organisation with an invitation code. The caller commits."""
    errors: dict[str, str] = {}
    email, mobile = _check_person(config, data, errors)
    invitation = None
    try:
        invitation = invitations.resolve(session, _text(data, "invitation_code"))
    except AccountError:
        errors["invitation_code"] = invitations.INVALID.message
    employee_id = _text(data, "employee_id")
    if invitation is not None:
        chosen = _text(data, "role")
        if chosen != invitation.role:
            desk = invitation.role == "records_officer"
            kind = "a Records Desk officer" if desk else "a Credit Officer"
            errors["role"] = f"This code is for {kind}. Choose the matching role."
        if invitation.role == "records_officer" and not employee_id:
            errors["employee_id"] = "Give your employee or staff ID."
        if employee_id and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._/-]{0,39}", employee_id):
            errors["employee_id"] = "Use letters, digits and - _ . / only (up to 40)."
    if errors:
        raise AccountError(422, "invalid_fields", "Some details need fixing.", fields=errors)

    _refuse_if_taken(session, email, mobile)
    employee_norm = re.sub(r"\s+", "", employee_id).lower() or None
    if employee_norm and session.scalar(
        select(db.StaffProfile.user_id).where(
            db.StaffProfile.organization_id == invitation.organization_id,
            db.StaffProfile.employee_id_norm == employee_norm,
        )
    ):
        raise AccountError(
            409,
            "employee_id_taken",
            "This employee ID is already registered in your company. Check it with your manager.",
            fields={"employee_id": "This employee ID is already registered in your company."},
        )
    org = session.get(db.Organization, invitation.organization_id)
    invitations.take_a_place(session, invitation)
    user = make_user(session, org.organization_id, _text(data, "full_name"), email, mobile)
    credential = session.get(db.UserCredential, user.user_id)
    credential.password_hash = hash_password(str(data["password"]))
    credential.password_set_at = now()
    add_membership(session, user.user_id, org.organization_id, invitation.role, None)
    session.add(
        db.StaffProfile(
            user_id=user.user_id,
            organization_id=org.organization_id,
            full_name=_text(data, "full_name"),
            job_title=JOB_TITLES.get(invitation.role, "Staff"),
            department=_text(data, "department") or None,
            employee_id=employee_id or None,
            employee_id_norm=employee_norm,
            mobile=mobile,
            created_at=now(),
        )
    )
    session.add(
        db.InvitationUse(
            use_id=f"IU-{uuid.uuid4().hex[:24]}",
            invitation_id=invitation.invitation_id,
            user_id=user.user_id,
            organization_id=org.organization_id,
            used_at=now(),
        )
    )
    _audit(
        session,
        user.user_id,
        invitation.role,
        "register_with_invitation",
        org.organization_id,
        invitation=invitation.invitation_id,
    )
    return user, org, invitation.role
