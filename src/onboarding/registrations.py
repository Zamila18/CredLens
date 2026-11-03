"""Merchant registration with paper consent: from details to an active, consented merchant.

Purpose: the one path by which a merchant becomes assessable. A Credit Officer registers the
    merchant (method 1: types the details, prints a prefilled form; method 2: gives out a blank
    form that the merchant fills by hand), the merchant signs on paper, a photo or scan comes
    back, the text is read by a machine (src/extraction/), and a PERSON verifies the signed
    document. Only then is the consent recorded and the merchant active.
Owner role: D (full-stack).
Implements: Phase 2 of the unified platform plan (section 8).

Rules:
- Optical reading never decides anything. A person checks each field, looks at the document,
  and confirms the signature appears to match and the reference is the right form.
- The verifier is a different Credit Officer than the uploader whenever the company has another
  active one; a company with a single officer may verify its own upload, and that is recorded
  as `self_verified` on the case and in the audit log.
- Consent is recorded with method `paper_form_reference` for exactly the boxes the merchant
  ticked, dated the day they signed; the signed file, its SHA-256, the template version, what
  the machine read and who reviewed are all kept as the proof of consent.
- Mandatory details are the few the assessment needs. National ID and account numbers are never
  asked for.
- In production only an approved template version can be issued (config `registration`).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.accounts.service import AccountError, normalise_identifier, now
from src.api.auth import CurrentUser, add_audit
from src.config import PROJECT_ROOT
from src.db import models as db
from src.intake.consent import record_consent_response
from src.intake.merchants import create_merchant, districts, shop_types
from src.intake.policy import IntakeRefused, calendar_end
from src.onboarding import consent_text as text
from src.onboarding.pdf import build_consent_pdf

REF_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
REQUIRED = [key for key, _en, _bn, required in text.DETAIL_FIELDS if required]
EDITABLE_STATUSES = ("draft", "form_issued", "needs_correction")
VERIFIABLE = ("signed_uploaded", "under_review")


def _refuse(status: int, code: str, message: str, **facts: Any) -> IntakeRefused:
    return IntakeRefused(status, code, message, **facts)


def _ref(prefix: str, session: Session, table, column) -> str:
    while True:
        value = f"{prefix}-" + "".join(secrets.choice(REF_ALPHABET) for _ in range(6))
        if session.scalar(select(func.count()).select_from(table).where(column == value)) == 0:
            return value


# --- the template -----------------------------------------------------------------------


def template_row(session: Session) -> db.ConsentTemplate:
    row = session.get(db.ConsentTemplate, text.VERSION)
    if row is None:
        row = db.ConsentTemplate(version=text.VERSION, status="draft", created_at=now())
        session.add(row)
        session.flush()
    return row


def template_allowed(session: Session, config: dict[str, Any]) -> tuple[bool, bool]:
    """(may a form be issued, is the template approved). In production only an approved
    template may be issued; anywhere else a draft is stamped DRAFT on every page."""
    approved = template_row(session).status == "approved"
    mode = config["registration"]["require_approved_template"]
    production = os.environ.get("CREDLENS_ENV", "").strip().lower() == "production"
    must = mode == "always" or (mode == "auto" and production)
    return (approved or not must), approved


# --- details ----------------------------------------------------------------------------


def clean_details(
    config: dict[str, Any], raw: dict[str, Any], *, require: bool
) -> tuple[dict, dict]:
    """(details, errors by field). With `require`, every mandatory field must be present."""
    errors: dict[str, str] = {}
    out: dict[str, Any] = {}
    for key, _en, _bn, _req in text.DETAIL_FIELDS:
        value = raw.get(key)
        value = None if value is None else str(value).strip()
        if value:
            out[key] = value
    for key in REQUIRED:
        if require and not out.get(key):
            errors[key] = "This is required."
    if out.get("shop_name") and len(out["shop_name"]) > 80:
        errors["shop_name"] = "Use at most 80 characters."
    for key in ("owner_mobile", "alternate_contact", "representative_mobile"):
        if out.get(key):
            _, phone = normalise_identifier(out[key])
            if phone:
                out[key] = phone
            else:
                errors[key] = "Give a valid mobile number."
    if out.get("district") and out["district"] not in districts(config):
        errors["district"] = "Choose a district from the list."
    if out.get("shop_type") and out["shop_type"] not in shop_types(config):
        errors["shop_type"] = "Choose a business category from the list."
    if (
        out.get("ownership_type")
        and out["ownership_type"] not in config["registration"]["ownership_types"]
    ):
        errors["ownership_type"] = "Choose the ownership type from the list."
    for key, low, high in (("established_year", 1900, now().year), ("branches", 1, 500)):
        if out.get(key):
            if re.fullmatch(r"\d{1,4}", out[key]) and low <= int(out[key]) <= high:
                out[key] = int(out[key])
            else:
                errors[key] = f"Use a whole number from {low} to {high}."
    return out, errors


def organization_names(session: Session, config: dict[str, Any], org_id: str) -> tuple[str, str]:
    row = session.get(db.Organization, org_id)
    if row is None:
        s = config["organization"]
        return s["name"], ""
    contact = ", ".join(x for x in (row.official_email, row.contact_number) if x)
    return row.name, contact


# --- creating and editing ---------------------------------------------------------------


def _apply_profile(session: Session, merchant_id: str, details: dict[str, Any]) -> None:
    profile = session.get(db.MerchantProfile, merchant_id)
    merchant = session.get(db.Merchant, merchant_id)
    for key in (
        "legal_name",
        "owner_name",
        "owner_mobile",
        "alternate_contact",
        "ownership_type",
        "established_year",
        "trade_license_number",
        "branches",
        "representative_name",
        "representative_mobile",
    ):
        if key in details:
            setattr(profile, key, details[key])
    if "area" in details:
        profile.area = details["area"]
    if "trade_license_number" in details:
        merchant.has_trade_license = True


def _make_merchant(
    session: Session,
    config: dict[str, Any],
    actor: CurrentUser,
    details: dict[str, Any],
    confirm_new: bool,
) -> str:
    try:
        merchant = create_merchant(
            session,
            config,
            shop_name=details["shop_name"],
            area=details.get("area"),
            district=details["district"],
            shop_type=details["shop_type"],
            has_trade_license=True if details.get("trade_license_number") else None,
            business_date=calendar_end(config),
            actor=actor,
            confirm_new=confirm_new,
        )
    except IntakeRefused:
        raise
    _apply_profile(session, merchant.merchant_id, details)
    return merchant.merchant_id


def create_registration(
    session: Session,
    config: dict[str, Any],
    actor: CurrentUser,
    org_id: str,
    raw_details: dict[str, Any],
    confirm_new: bool = False,
) -> db.MerchantRegistration:
    """Method 1: the details are typed in. The merchant row is made at once (without consent:
    it cannot be assessed until the signed form is verified). Commits."""
    allowed, _approved = template_allowed(session, config)
    if not allowed:
        raise _refuse(
            409,
            "template_not_approved",
            "The consent document has not been approved for use yet. Ask a platform administrator.",
        )
    details, errors = clean_details(config, raw_details, require=True)
    if errors:
        raise _refuse(422, "invalid_fields", "Some details need fixing.", fields=errors)
    merchant_id = _make_merchant(session, config, actor, details, confirm_new)
    stamp = now()
    reg = db.MerchantRegistration(
        reg_id=f"RG-{uuid.uuid4().hex[:24]}",
        reg_ref=_ref("MR", session, db.MerchantRegistration, db.MerchantRegistration.reg_ref),
        organization_id=org_id,
        merchant_id=merchant_id,
        method="manual",
        status="draft",
        template_version=text.VERSION,
        details=json.dumps(details, ensure_ascii=False),
        created_by=actor.user_id,
        created_at=stamp,
        updated_at=stamp,
    )
    session.add(reg)
    add_audit(session, actor, "create_registration", merchant_id)
    session.commit()
    return reg


def update_details(
    session: Session,
    config: dict[str, Any],
    actor: CurrentUser,
    reg: db.MerchantRegistration,
    raw_details: dict[str, Any],
    confirm_new: bool = False,
) -> db.MerchantRegistration:
    """Change the details of a case that has not been verified. A blank-form case gets its
    merchant row here, once every mandatory detail is there (the officer's reviewed values)."""
    if reg.status not in EDITABLE_STATUSES + ("signed_uploaded", "under_review"):
        raise _refuse(409, "registration_closed", "This registration can no longer be edited.")
    current = json.loads(reg.details or "{}")
    merged = {**current, **{k: v for k, v in raw_details.items() if v is not None}}
    details, errors = clean_details(
        config, merged, require=reg.merchant_id is not None or reg.method == "manual"
    )
    if errors:
        raise _refuse(422, "invalid_fields", "Some details need fixing.", fields=errors)
    if reg.merchant_id is None and all(details.get(k) for k in REQUIRED):
        reg.merchant_id = _make_merchant(session, config, actor, details, confirm_new)
    elif reg.merchant_id is not None:
        _apply_profile(session, reg.merchant_id, details)
    reg.details = json.dumps(details, ensure_ascii=False)
    reg.updated_at = now()
    add_audit(session, actor, "update_registration", reg.merchant_id)
    session.commit()
    return reg


# --- the forms --------------------------------------------------------------------------


def _pdf_common(session: Session, config: dict[str, Any], org_id: str) -> dict[str, Any]:
    name, contact = organization_names(session, config, org_id)
    _allowed, approved = template_allowed(session, config)
    return dict(
        org_name=name,
        org_contact=contact or "-",
        template_version=text.VERSION,
        template_approved=approved,
        retention=config["registration"]["retention_text"],
        valid_days=int(config["demo"]["consent"]["valid_days"]),
        district_labels=None,
        issued_on=calendar_end(config).isoformat(),
    )


def prefilled_pdf(
    session: Session, config: dict[str, Any], actor: CurrentUser, reg: db.MerchantRegistration
) -> bytes:
    """The prefilled form for a typed-in registration. The case becomes `form_issued`."""
    if reg.method != "manual":
        raise _refuse(409, "no_prefilled_form", "A blank-form case has no prefilled form.")
    if reg.status not in EDITABLE_STATUSES:
        raise _refuse(409, "registration_closed", "The form was already signed and returned.")
    allowed, _ = template_allowed(session, config)
    if not allowed:
        raise _refuse(409, "template_not_approved", "The consent document has not been approved.")
    data = build_consent_pdf(
        **_pdf_common(session, config, reg.organization_id),
        reference=reg.reg_ref,
        form_kind="prefilled",
        details=json.loads(reg.details),
        issued_by=actor.display_name or actor.user_id,
    )
    if reg.status == "draft":
        reg.status, reg.updated_at = "form_issued", now()
    add_audit(session, actor, "issue_prefilled_form", reg.merchant_id)
    session.commit()
    return data


def blank_pdf(
    session: Session, config: dict[str, Any], actor: CurrentUser, org_id: str
) -> tuple[bytes, str]:
    """A blank form with its own serial. Returns (pdf bytes, serial)."""
    allowed, _ = template_allowed(session, config)
    if not allowed:
        raise _refuse(409, "template_not_approved", "The consent document has not been approved.")
    serial = _ref("CF", session, db.BlankFormSerial, db.BlankFormSerial.serial)
    session.add(
        db.BlankFormSerial(
            serial=serial,
            organization_id=org_id,
            template_version=text.VERSION,
            issued_by=actor.user_id,
            issued_at=now(),
        )
    )
    data = build_consent_pdf(
        **_pdf_common(session, config, org_id),
        reference=serial,
        form_kind="blank",
        details=None,
        issued_by=actor.display_name or actor.user_id,
    )
    add_audit(session, actor, "issue_blank_form")
    session.commit()
    return data, serial


# --- uploads ----------------------------------------------------------------------------

_MAGIC = (
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"%PDF-", "application/pdf", "pdf"),
)


def file_kind(body: bytes) -> tuple[str, str] | None:
    """(media type, extension) from the first bytes (not the file name), or None."""
    for magic, mime, ext in _MAGIC:
        if body.startswith(magic):
            return mime, ext
    return None


def upload_root(config: dict[str, Any]) -> Path:
    path = Path(config["documents"]["upload_dir"])
    return path if path.is_absolute() else PROJECT_ROOT / path


def store_document(
    session: Session,
    config: dict[str, Any],
    actor: CurrentUser,
    org_id: str,
    body: bytes,
    *,
    kind: str,
    original_name: str,
    merchant_id: str | None,
    registration_id: str | None,
) -> db.Document:
    """Check and save an uploaded file. The caller commits (and removes the file on failure)."""
    limit = int(config["registration"]["signed_max_mb"]) * 1024 * 1024
    if not body:
        raise _refuse(422, "empty_file", "Choose the photo or scan of the signed form.")
    if len(body) > limit:
        raise _refuse(
            413,
            "file_too_large",
            f"The file is larger than {config['registration']['signed_max_mb']} MB.",
        )
    detected = file_kind(body)
    if detected is None:
        raise _refuse(415, "file_type_not_allowed", "Upload a photo (JPEG or PNG) or a PDF.")
    mime, ext = detected
    document_id = f"DC-{uuid.uuid4().hex[:24]}"
    relative = Path(org_id) / f"{document_id}.{ext}"
    path = upload_root(config) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    row = db.Document(
        document_id=document_id,
        organization_id=org_id,
        merchant_id=merchant_id,
        registration_id=registration_id,
        kind=kind,
        original_name=(original_name or "upload")[:200],
        mime=mime,
        size=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        path=relative.as_posix(),
        uploaded_by=actor.user_id,
        uploaded_at=now(),
    )
    session.add(row)
    return row


def read_document(config: dict[str, Any], doc: db.Document) -> bytes:
    """The stored bytes, refused when missing, outside the upload folder, or changed."""
    root = upload_root(config).resolve()
    path = (root / doc.path).resolve()
    if root not in path.parents or not path.is_file():
        raise _refuse(404, "file_missing", "The file is missing from storage.")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != doc.sha256:
        raise _refuse(409, "file_changed", "The stored file changed after it was uploaded.")
    return data


def queue_extraction(
    session: Session, doc: db.Document, reg: db.MerchantRegistration
) -> db.ExtractionJob:
    job = db.ExtractionJob(
        job_id=f"XJ-{uuid.uuid4().hex[:24]}",
        document_id=doc.document_id,
        organization_id=reg.organization_id,
        registration_id=reg.reg_id,
        status="queued",
        queued_at=now(),
    )
    session.add(job)
    return job


def attach_signed(
    session: Session,
    config: dict[str, Any],
    actor: CurrentUser,
    reg: db.MerchantRegistration,
    body: bytes,
    original_name: str,
) -> db.Document:
    """The signed form came back (method 1). Stores it and queues the reading. Commits."""
    if reg.method != "manual" or reg.status not in ("draft", "form_issued", "needs_correction"):
        raise _refuse(
            409, "registration_closed", "A signed form cannot be added to this registration now."
        )
    doc = store_document(
        session,
        config,
        actor,
        reg.organization_id,
        body,
        kind="consent_signed",
        original_name=original_name,
        merchant_id=reg.merchant_id,
        registration_id=reg.reg_id,
    )
    try:
        queue_extraction(session, doc, reg)
        reg.status, reg.uploaded_by, reg.uploaded_at, reg.updated_at = (
            "signed_uploaded",
            actor.user_id,
            now(),
            now(),
        )
        add_audit(session, actor, "upload_signed_form", reg.merchant_id)
        session.commit()
    except Exception:
        session.rollback()
        (upload_root(config) / doc.path).unlink(missing_ok=True)
        raise
    return doc


def from_blank_form(
    session: Session,
    config: dict[str, Any],
    actor: CurrentUser,
    org_id: str,
    body: bytes,
    original_name: str,
) -> db.MerchantRegistration:
    """Method 2: a hand-filled blank form came back. Starts a case with no details yet; the
    reading fills them in as suggestions the officer reviews. Commits."""
    stamp = now()
    reg = db.MerchantRegistration(
        reg_id=f"RG-{uuid.uuid4().hex[:24]}",
        reg_ref=_ref("MR", session, db.MerchantRegistration, db.MerchantRegistration.reg_ref),
        organization_id=org_id,
        merchant_id=None,
        method="blank_form",
        status="signed_uploaded",
        template_version=text.VERSION,
        details="{}",
        created_by=actor.user_id,
        created_at=stamp,
        updated_at=stamp,
        uploaded_by=actor.user_id,
        uploaded_at=stamp,
    )
    session.add(reg)
    session.flush()
    doc = store_document(
        session,
        config,
        actor,
        org_id,
        body,
        kind="consent_filled_form",
        original_name=original_name,
        merchant_id=None,
        registration_id=reg.reg_id,
    )
    try:
        queue_extraction(session, doc, reg)
        add_audit(session, actor, "upload_filled_form")
        session.commit()
    except Exception:
        session.rollback()
        (upload_root(config) / doc.path).unlink(missing_ok=True)
        raise
    return reg


# --- review and verification ------------------------------------------------------------


def review_field(
    session: Session,
    actor: CurrentUser,
    reg: db.MerchantRegistration,
    field_id: int,
    value: str | None,
) -> db.ExtractionField:
    """A person confirms (no value) or corrects (a value) one field read from the document."""
    field = session.get(db.ExtractionField, field_id)
    if field is None or field.registration_id != reg.reg_id:
        raise _refuse(404, "unknown_field", "No such field on this registration.")
    if reg.status in ("active", "rejected", "withdrawn"):
        raise _refuse(409, "registration_closed", "This registration is closed.")
    if value is None or value.strip() == (field.value or "").strip():
        field.state, field.reviewed_value = "confirmed", field.value
    else:
        field.state, field.reviewed_value = "corrected", value.strip()
    field.reviewed_by, field.reviewed_at = actor.user_id, now()
    add_audit(session, actor, "review_field", reg.merchant_id)
    session.commit()
    return field


def other_officers(session: Session, org_id: str, exclude_user: str | None) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(db.Membership)
            .where(
                db.Membership.organization_id == org_id,
                db.Membership.role == "credit_officer",
                db.Membership.status == "active",
                db.Membership.user_id != (exclude_user or ""),
            )
        )
        or 0
    )


def verify(
    session: Session,
    config: dict[str, Any],
    actor: CurrentUser,
    reg: db.MerchantRegistration,
    *,
    categories: list[str],
    optional: list[str],
    signer_name: str,
    signed_on: date,
    signature_checked: bool,
    reference_matches: bool,
    protected: frozenset[str],
) -> db.MerchantRegistration:
    """A person verifies the signed document: the consent is recorded and the case is active."""
    if reg.status not in VERIFIABLE:
        raise _refuse(409, "not_ready_to_verify", "There is no signed form waiting to be verified.")
    if reg.merchant_id is None:
        raise _refuse(409, "details_incomplete", "Complete and save the merchant details first.")
    if not (signature_checked and reference_matches):
        raise _refuse(
            422,
            "checks_not_confirmed",
            "Look at the signed form first: confirm the reference is right and the signature "
            "and name appear to match the owner.",
        )
    valid = list(text.CATEGORIES)
    if (
        not categories
        or any(c not in valid for c in categories)
        or len(set(categories)) != len(categories)
    ):
        raise _refuse(
            422, "invalid_categories", "Tick the kinds of records the merchant agreed to."
        )
    if any(o not in text.OPTIONAL_PURPOSES for o in optional):
        raise _refuse(422, "invalid_optional", "Unknown optional agreement.")
    if not 2 <= len((signer_name or "").strip()) <= 120:
        raise _refuse(422, "invalid_signer", "Write the name of the person who signed.")
    mode = "distinct"
    if reg.uploaded_by == actor.user_id:
        if other_officers(session, reg.organization_id, actor.user_id) > 0:
            raise _refuse(
                403,
                "different_verifier_required",
                "Another Credit Officer must verify a form you uploaded.",
            )
        mode = "self_verified"
    consent_categories = categories + (["questionnaire"] if "questionnaire" in optional else [])
    try:
        event = record_consent_response(
            session,
            config,
            merchant_id=reg.merchant_id,
            response="granted",
            categories=consent_categories,
            method="paper_form_reference",
            actor=actor,
            business_date=signed_on,
            protected_merchants=protected,
            commit=False,
        )
        reg.status, reg.verified_by, reg.verified_at = "active", actor.user_id, now()
        reg.verification_mode, reg.consent_id = mode, event.consent_id
        reg.signer_name, reg.signed_on = signer_name.strip(), signed_on
        reg.optional_consents = "|".join(optional)
        reg.updated_at = now()
        add_audit(session, actor, f"verify_registration_{mode}", reg.merchant_id)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return reg


def reject_or_return(
    session: Session, actor: CurrentUser, reg: db.MerchantRegistration, *, reason: str, reject: bool
) -> db.MerchantRegistration:
    if reg.status not in VERIFIABLE + EDITABLE_STATUSES:
        raise _refuse(409, "registration_closed", "This registration is closed.")
    if len((reason or "").strip()) < 10:
        raise _refuse(422, "reason_needed", "Write a reason of at least 10 characters.")
    reg.status = "rejected" if reject else "needs_correction"
    reg.reviewer_note, reg.updated_at = reason.strip(), now()
    add_audit(
        session, actor, "reject_registration" if reject else "return_registration", reg.merchant_id
    )
    session.commit()
    return reg


def withdraw_consent(
    session: Session, config: dict[str, Any], actor: CurrentUser, merchant_id: str, reason: str
) -> int:
    """The merchant withdraws consent: every open consent ends today, so no new assessment
    can be made and the score is no longer shown. What was lawfully done before stays on
    record; retention and deletion are handled under the company's retention policy."""
    if len((reason or "").strip()) < 5:
        raise _refuse(
            422, "reason_needed", "Write how the withdrawal was received (5 characters or more)."
        )
    open_consents = session.scalars(
        select(db.Consent).where(
            db.Consent.merchant_id == merchant_id, db.Consent.revoked_at.is_(None)
        )
    ).all()
    if not open_consents:
        raise _refuse(409, "no_open_consent", "This merchant has no open consent.")
    today = calendar_end(config)
    for row in open_consents:
        row.revoked_at = today
    for reg in session.scalars(
        select(db.MerchantRegistration).where(
            db.MerchantRegistration.merchant_id == merchant_id,
            db.MerchantRegistration.status == "active",
        )
    ):
        reg.status, reg.reviewer_note, reg.updated_at = "withdrawn", reason.strip(), now()
    add_audit(session, actor, "withdraw_consent", merchant_id)
    session.commit()
    return len(open_consents)


__all__ = ["AccountError"]
