"""Merchant registration and paper consent: the API behind the registration wizard.

Purpose: a Credit Officer registers a merchant (typed details with a prefilled consent PDF, or a
    blank form the merchant fills by hand), uploads the signed form, reviews what the reader
    found, and a Credit Officer verifies it, which records the consent and activates the merchant.
Owner role: D (full-stack).
Implements: Phase 2 of the unified platform plan (sections 8 to 10).

Every case belongs to one company; another company's case answers 404. Files are served only
to the company's Credit Officers, with every view audited. The form text is a draft prepared
for legal review (src/onboarding/consent_text.py) and is stamped as such until a platform
administrator approves it.
"""

from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import CurrentUser, add_audit, require_roles
from src.api.common import api_error
from src.api.imported import refresh_scoring
from src.api.schemas import (
    ExtractionFieldOut,
    ExtractionJobOut,
    ExtractionOut,
    FieldReviewIn,
    ReasonIn,
    RegistrationDetailsIn,
    RegistrationOut,
    VerifyIn,
)
from src.api.state import Services, get_services, get_session
from src.api.tenancy import org_of
from src.api.uploads import read_capped
from src.db import models as db
from src.intake.policy import IntakeRefused, calendar_end
from src.onboarding import consent_text as text
from src.onboarding import registrations as svc

router = APIRouter(tags=["merchant registration"])

OFFICER = require_roles("credit_officer")
BINARY = {"schema": {"type": "string", "format": "binary"}}
UPLOAD_BODY = {
    "requestBody": {
        "required": True,
        "content": {m: BINARY for m in ("image/jpeg", "image/png", "application/pdf")},
    }
}
LABELS = {
    **{k: (en, bn) for k, en, bn, _ in text.DETAIL_FIELDS},
    "reference": text.REFERENCE_LABEL,
    "serial": text.SERIAL_LABEL,
    "signer_name": text.SIGNATURE_FIELDS[0][1:],
    "signature": text.SIGNATURE_FIELDS[1][1:],
    "signed_on": text.SIGNATURE_FIELDS[2][1:],
    **{f"tick:{k}": v for k, v in {**text.CATEGORIES, **text.OPTIONAL_PURPOSES}.items()},
}


def _refused(error: IntakeRefused):
    return api_error(error.status, error.code, error.message, **error.facts)


def _iso(moment) -> str | None:
    return moment.isoformat(timespec="seconds") if moment else None


def _protected(services: Services) -> frozenset[str]:
    return services.scorer.source_merchant_ids() if services.scorer is not None else frozenset()


def _reg(
    session: Session, user: CurrentUser, services: Services, reg_id: str
) -> db.MerchantRegistration:
    reg = session.get(db.MerchantRegistration, reg_id)
    if reg is None or reg.organization_id != org_of(user, services.config):
        raise api_error(404, "unknown_registration", "No such registration in your company.")
    return reg


def _job(session: Session, reg: db.MerchantRegistration) -> db.ExtractionJob | None:
    return session.scalar(
        select(db.ExtractionJob)
        .where(db.ExtractionJob.registration_id == reg.reg_id)
        .order_by(db.ExtractionJob.queued_at.desc())
        .limit(1)
    )


def _job_out(job: db.ExtractionJob | None) -> ExtractionJobOut | None:
    if job is None:
        return None
    return ExtractionJobOut(
        job_id=job.job_id,
        status=job.status,
        engine=job.engine,
        engine_version=job.engine_version,
        pages=job.pages,
        error=job.error,
        queued_at=_iso(job.queued_at),
        finished_at=_iso(job.finished_at),
    )


def _field_out(f: db.ExtractionField) -> ExtractionFieldOut:
    en, bn = LABELS.get(f.key, (f.key, f.key))
    return ExtractionFieldOut(
        field_id=f.field_id,
        key=f.key,
        label_en=en,
        label_bn=bn,
        value=f.value,
        confidence=f.confidence,
        method=f.method,
        expected=f.expected,
        state=f.state,
        reviewed_value=f.reviewed_value,
        page=f.page,
    )


def _out(
    session: Session, services: Services, user: CurrentUser, reg: db.MerchantRegistration
) -> RegistrationOut:
    details = json.loads(reg.details or "{}")
    creator = session.get(db.User, reg.created_by)
    has_doc = session.scalar(
        select(db.Document.document_id).where(db.Document.registration_id == reg.reg_id).limit(1)
    )
    self_upload = reg.uploaded_by == user.user_id
    can_verify = reg.status in svc.VERIFIABLE and (
        not self_upload or svc.other_officers(session, reg.organization_id, user.user_id) == 0
    )
    return RegistrationOut(
        reg_id=reg.reg_id,
        reg_ref=reg.reg_ref,
        merchant_id=reg.merchant_id,
        method=reg.method,
        status=reg.status,
        template_version=reg.template_version,
        template_approved=svc.template_row(session).status == "approved",
        shop_name=details.get("shop_name"),
        details=details,
        optional_consents=[x for x in reg.optional_consents.split("|") if x],
        form_serial=reg.form_serial,
        created_by=reg.created_by,
        created_by_name=creator.display_name if creator else None,
        created_at=_iso(reg.created_at),
        uploaded_by=reg.uploaded_by,
        uploaded_at=_iso(reg.uploaded_at),
        signer_name=reg.signer_name,
        signed_on=reg.signed_on.isoformat() if reg.signed_on else None,
        verified_by=reg.verified_by,
        verified_at=_iso(reg.verified_at),
        verification_mode=reg.verification_mode,
        reviewer_note=reg.reviewer_note,
        has_document=bool(has_doc),
        can_verify=can_verify,
        job=_job_out(_job(session, reg)),
    )


@router.post("/registrations", response_model=RegistrationOut, status_code=201)
def new_registration(
    body: RegistrationDetailsIn,
    user: CurrentUser = Depends(OFFICER),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> RegistrationOut:
    """Method 1: register a merchant from typed details. A prefilled consent PDF follows."""
    data = body.model_dump(exclude={"confirm_new"})
    try:
        reg = svc.create_registration(
            session, services.config, user, org_of(user, services.config), data, body.confirm_new
        )
    except IntakeRefused as error:
        session.rollback()
        raise _refused(error) from None
    return _out(session, services, user, reg)


@router.get("/registrations", response_model=list[RegistrationOut])
def list_registrations(
    status: str | None = Query(default=None),
    user: CurrentUser = Depends(OFFICER),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> list[RegistrationOut]:
    """The company's registration cases, newest first."""
    query = select(db.MerchantRegistration).where(
        db.MerchantRegistration.organization_id == org_of(user, services.config)
    )
    if status:
        query = query.where(db.MerchantRegistration.status == status)
    rows = session.scalars(
        query.order_by(db.MerchantRegistration.created_at.desc()).limit(300)
    ).all()
    return [_out(session, services, user, r) for r in rows]


@router.get("/registrations/{reg_id}", response_model=RegistrationOut)
def get_registration(
    reg_id: str,
    user: CurrentUser = Depends(OFFICER),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> RegistrationOut:
    return _out(session, services, user, _reg(session, user, services, reg_id))


@router.patch("/registrations/{reg_id}/details", response_model=RegistrationOut)
def edit_details(
    reg_id: str,
    body: RegistrationDetailsIn,
    user: CurrentUser = Depends(OFFICER),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> RegistrationOut:
    """Correct the details (also how a blank-form case gets its merchant, once every mandatory
    detail is there)."""
    reg = _reg(session, user, services, reg_id)
    try:
        svc.update_details(
            session,
            services.config,
            user,
            reg,
            body.model_dump(exclude={"confirm_new"}, exclude_unset=True),
            body.confirm_new,
        )
    except IntakeRefused as error:
        session.rollback()
        raise _refused(error) from None
    return _out(session, services, user, reg)


def _pdf(data: bytes, name: str) -> Response:
    return Response(
        data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/registrations/{reg_id}/consent.pdf")
def prefilled_form(
    reg_id: str,
    user: CurrentUser = Depends(OFFICER),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> Response:
    """The consent form prefilled with the typed details, to print and have signed."""
    reg = _reg(session, user, services, reg_id)
    try:
        return _pdf(svc.prefilled_pdf(session, services.config, user, reg), f"{reg.reg_ref}.pdf")
    except IntakeRefused as error:
        session.rollback()
        raise _refused(error) from None


@router.get("/registration-forms/blank")
def blank_form(
    user: CurrentUser = Depends(OFFICER),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> Response:
    """A blank form with its own serial, for the merchant to fill in by hand."""
    try:
        data, serial = svc.blank_pdf(session, services.config, user, org_of(user, services.config))
    except IntakeRefused as error:
        session.rollback()
        raise _refused(error) from None
    return _pdf(data, f"{serial}.pdf")


@router.post(
    "/registrations/from-form",
    response_model=RegistrationOut,
    status_code=201,
    openapi_extra=UPLOAD_BODY,
)
async def upload_filled_form(
    request: Request,
    name: str = Query(default="filled-form"),
    user: CurrentUser = Depends(OFFICER),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> RegistrationOut:
    """Method 2: a hand-filled blank form came back. Starts a case; the reading fills in the
    details as suggestions for the officer to review."""
    limit = int(services.config["registration"]["signed_max_mb"]) * 1024 * 1024
    body = await read_capped(request, limit)
    try:
        reg = svc.from_blank_form(
            session, services.config, user, org_of(user, services.config), body, name
        )
    except IntakeRefused as error:
        session.rollback()
        raise _refused(error) from None
    return _out(session, services, user, reg)


@router.post(
    "/registrations/{reg_id}/signed", response_model=RegistrationOut, openapi_extra=UPLOAD_BODY
)
async def upload_signed(
    reg_id: str,
    request: Request,
    name: str = Query(default="signed-form"),
    user: CurrentUser = Depends(OFFICER),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> RegistrationOut:
    """The signed form came back: store the photo or scan and queue it for reading."""
    limit = int(services.config["registration"]["signed_max_mb"]) * 1024 * 1024
    body = await read_capped(request, limit)
    reg = _reg(session, user, services, reg_id)
    try:
        svc.attach_signed(session, services.config, user, reg, body, name)
    except IntakeRefused as error:
        session.rollback()
        raise _refused(error) from None
    return _out(session, services, user, reg)


@router.get("/registrations/{reg_id}/extraction", response_model=ExtractionOut)
def extraction(
    reg_id: str,
    user: CurrentUser = Depends(OFFICER),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ExtractionOut:
    """What was read from the signed form, with confidence and how it compares to the details."""
    reg = _reg(session, user, services, reg_id)
    job = _job(session, reg)
    rows = (
        session.scalars(
            select(db.ExtractionField)
            .where(db.ExtractionField.job_id == job.job_id)
            .order_by(db.ExtractionField.field_id)
        ).all()
        if job
        else []
    )
    return ExtractionOut(job=_job_out(job), fields=[_field_out(f) for f in rows])


@router.patch("/registrations/{reg_id}/fields/{field_id}", response_model=ExtractionFieldOut)
def review_field(
    reg_id: str,
    field_id: int,
    body: FieldReviewIn,
    user: CurrentUser = Depends(OFFICER),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ExtractionFieldOut:
    """Confirm a field as read, or correct it. The reader's value is kept beside the correction."""
    reg = _reg(session, user, services, reg_id)
    try:
        return _field_out(svc.review_field(session, user, reg, field_id, body.value))
    except IntakeRefused as error:
        session.rollback()
        raise _refused(error) from None


@router.get("/registrations/{reg_id}/document")
def document(
    reg_id: str,
    user: CurrentUser = Depends(OFFICER),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> Response:
    """The uploaded signed form, as stored (every view is audited)."""
    reg = _reg(session, user, services, reg_id)
    doc = session.scalar(
        select(db.Document)
        .where(db.Document.registration_id == reg.reg_id)
        .order_by(db.Document.uploaded_at.desc())
        .limit(1)
    )
    if doc is None:
        raise api_error(404, "no_document", "No signed form has been uploaded yet.")
    try:
        data = svc.read_document(services.config, doc)
    except IntakeRefused as error:
        raise _refused(error) from None
    add_audit(session, user, "view_signed_form", reg.merchant_id)
    session.commit()
    return Response(
        data,
        media_type=doc.mime,
        headers={
            "Content-Disposition": f'inline; filename="{reg.reg_ref}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/registrations/{reg_id}/verify", response_model=RegistrationOut)
def verify(
    reg_id: str,
    body: VerifyIn,
    user: CurrentUser = Depends(OFFICER),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> RegistrationOut:
    """A person verifies the signed document. This records the consent (for the boxes ticked)
    and activates the merchant."""
    reg = _reg(session, user, services, reg_id)
    try:
        signed_on = (
            date.fromisoformat(body.signed_on) if body.signed_on else calendar_end(services.config)
        )
    except ValueError:
        raise api_error(422, "invalid_date", "The signing date must be YYYY-MM-DD.") from None
    try:
        svc.verify(
            session,
            services.config,
            user,
            reg,
            categories=body.categories,
            optional=body.optional,
            signer_name=body.signer_name,
            signed_on=signed_on,
            signature_checked=body.signature_checked,
            reference_matches=body.reference_matches,
            protected=_protected(services),
        )
    except IntakeRefused as error:
        session.rollback()
        raise _refused(error) from None
    refresh_scoring(services, session)
    return _out(session, services, user, reg)


def _close(reg_id: str, body: ReasonIn, user, services, session, reject: bool) -> RegistrationOut:
    reg = _reg(session, user, services, reg_id)
    try:
        svc.reject_or_return(session, user, reg, reason=body.reason, reject=reject)
    except IntakeRefused as error:
        session.rollback()
        raise _refused(error) from None
    return _out(session, services, user, reg)


@router.post("/registrations/{reg_id}/reject", response_model=RegistrationOut)
def reject(
    reg_id: str,
    body: ReasonIn,
    user: CurrentUser = Depends(OFFICER),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> RegistrationOut:
    """Reject the registration with a written reason."""
    return _close(reg_id, body, user, services, session, True)


@router.post("/registrations/{reg_id}/return", response_model=RegistrationOut)
def send_back(
    reg_id: str,
    body: ReasonIn,
    user: CurrentUser = Depends(OFFICER),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> RegistrationOut:
    """Send the registration back for correction (a new signed form or fixed details)."""
    return _close(reg_id, body, user, services, session, False)


@router.post("/merchants/{merchant_id}/consent/withdraw", status_code=200)
def withdraw(
    merchant_id: str,
    body: ReasonIn,
    user: CurrentUser = Depends(OFFICER),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> dict[str, int]:
    """The merchant withdraws consent: it ends today, new assessments stop, the score is hidden."""
    try:
        ended = svc.withdraw_consent(session, services.config, user, merchant_id, body.reason)
    except IntakeRefused as error:
        session.rollback()
        raise _refused(error) from None
    refresh_scoring(services, session)
    return {"consents_ended": ended}
