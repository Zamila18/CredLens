"""The merchant's own portal: their records, their reports of mistakes, their loan application.

Purpose: a shop owner checks what the lender has recorded about their business, reports a
    wrong line with the correct amount and a photo of their own copy, and applies for a loan.
    A merchant reaches only their own shop; they never see the score, the range or an officer's
    notes. Nothing here approves or declines credit.
Owner role: D (full-stack).
Implements: the merchant portal of the Records Desk redesign.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import CurrentUser, add_audit, require_roles
from src.api.common import api_error
from src.api.imported import refresh_scoring
from src.api.profile import consent_state
from src.api.routes_receipts import (
    UPLOAD_ANY,
    LineOut,
    _document_response,
    auto_assess,
    line_out,
    protected,
)
from src.api.state import Services, get_services, get_session
from src.api.tenancy import org_of
from src.api.uploads import read_capped
from src.db import models as db
from src.intake.applications import create_application
from src.intake.policy import IntakeRefused
from src.notifications import notify_officers
from src.onboarding import registrations as docs
from src.receipts import service

router = APIRouter(tags=["portal"])
MERCHANT = require_roles("merchant")

STATE_WORDS = {
    "published": "Checked",
    "disputed": "You reported this: waiting for an answer",
}


class PortalMe(BaseModel):
    shop_name: str | None
    owner_name: str | None
    area: str | None
    consent_valid: bool
    receipts_published: int
    reports_open: int
    has_application: bool


class PortalLine(LineOut):
    shown_state: str = Field(description="checked | reported | corrected | kept")
    answer: str | None = None


class PortalReceipt(BaseModel):
    receipt_id: str
    kind: str
    supplier: str | None
    receipt_date: str | None
    memo_no: str | None
    stated_total: float | None
    lines_total: float
    confirmed: bool
    has_picture: bool
    lines: list[PortalLine]


class ReportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str = Field(max_length=1000)
    claimed_amount_bdt: float | None = None
    proof_document_id: str | None = None


class PortalReport(BaseModel):
    flag_id: str
    status: str
    receipt_id: str
    supplier: str | None
    item: str | None
    recorded_amount_bdt: float | None
    claimed_amount_bdt: float | None
    note: str
    answer: str | None
    raised_at: str
    resolved_at: str | None


class ProofOut(BaseModel):
    document_id: str


class ApplyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_amount_bdt: float
    purpose: str
    purpose_note: str | None = Field(default=None, max_length=300)


class ApplicationStatus(BaseModel):
    has_application: bool
    requested_amount_bdt: float | None = None
    purpose: str | None = None
    applied_on: str | None = None
    status: str | None = Field(default=None, description="received | decided")
    status_text: str | None = None
    max_requested_bdt: float
    purposes: list[str]
    can_apply: bool
    cannot_apply_reason: str | None = None


def _own(user: CurrentUser) -> str:
    if not user.merchant_id:
        raise api_error(403, "not_a_merchant", "This account has no shop.")
    return user.merchant_id


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat(timespec="seconds") if hasattr(value, "hour") else value.isoformat()


def _latest_flags(session: Session, merchant_id: str) -> dict[str, db.ReceiptFlag]:
    out: dict[str, db.ReceiptFlag] = {}
    for flag in session.scalars(
        select(db.ReceiptFlag)
        .where(db.ReceiptFlag.merchant_id == merchant_id)
        .order_by(db.ReceiptFlag.raised_at)
    ):
        out[flag.line_id] = flag
    return out


def _state(row: db.ReceiptLine, flag: db.ReceiptFlag | None) -> tuple[str, str | None]:
    if row.status == "disputed":
        return "reported", None
    if flag is not None and flag.status == "accepted":
        return "corrected", flag.resolution_note
    if flag is not None and flag.status == "rejected":
        return "kept", flag.resolution_note
    return "checked", None


@router.get("/portal/me", response_model=PortalMe)
def portal_me(
    user: CurrentUser = Depends(MERCHANT),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> PortalMe:
    merchant_id = _own(user)
    profile = session.get(db.MerchantProfile, merchant_id)
    valid, _ = consent_state(session, merchant_id, services.data_today(session))
    published = session.scalars(
        select(db.Receipt.receipt_id).where(
            db.Receipt.merchant_id == merchant_id, db.Receipt.status == "published"
        )
    ).all()
    open_reports = session.scalars(
        select(db.ReceiptFlag.flag_id).where(
            db.ReceiptFlag.merchant_id == merchant_id, db.ReceiptFlag.status == "open"
        )
    ).all()
    has_app = session.scalar(
        select(db.Application.application_id).where(db.Application.merchant_id == merchant_id)
    )
    return PortalMe(
        shop_name=profile.shop_name if profile else None,
        owner_name=profile.owner_name if profile else None,
        area=profile.area if profile else None,
        consent_valid=bool(valid),
        receipts_published=len(published),
        reports_open=len(open_reports),
        has_application=has_app is not None,
    )


@router.get("/portal/records", response_model=list[PortalReceipt])
def portal_records(
    user: CurrentUser = Depends(MERCHANT),
    session: Session = Depends(get_session),
) -> list[PortalReceipt]:
    """Every receipt the lender has published for this shop, with each line and its state."""
    merchant_id = _own(user)
    flags = _latest_flags(session, merchant_id)
    out = []
    for receipt in session.scalars(
        select(db.Receipt)
        .where(db.Receipt.merchant_id == merchant_id, db.Receipt.status == "published")
        .order_by(db.Receipt.published_at.desc())
        .limit(200)
    ):
        lines = []
        for row in service.lines_of(session, receipt.receipt_id):
            state, answer = _state(row, flags.get(row.line_id))
            base = line_out(row).model_dump()
            base.update(flags=[], confidence={})  # the reader's doubts are for the Records Desk
            lines.append(PortalLine(**base, shown_state=state, answer=answer))
        out.append(
            PortalReceipt(
                receipt_id=receipt.receipt_id,
                kind=receipt.kind,
                supplier=receipt.supplier,
                receipt_date=_iso(receipt.receipt_date),
                memo_no=receipt.memo_no,
                stated_total=receipt.stated_total,
                lines_total=float(sum(r.amount_bdt or 0 for r in lines)),
                confirmed=receipt.merchant_confirmed_at is not None,
                has_picture=receipt.document_id is not None,
                lines=lines,
            )
        )
    return out


def _own_receipt(session: Session, user: CurrentUser, receipt_id: str) -> db.Receipt:
    receipt = session.get(db.Receipt, receipt_id)
    if receipt is None or receipt.merchant_id != _own(user) or receipt.status != "published":
        raise api_error(404, "unknown_receipt", "No such receipt.")
    return receipt


@router.get("/portal/receipts/{receipt_id}/picture")
def portal_picture(
    receipt_id: str,
    user: CurrentUser = Depends(MERCHANT),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> Response:
    return _document_response(session, services, user, _own_receipt(session, user, receipt_id))


@router.post("/portal/receipts/{receipt_id}/confirm", response_model=PortalMe)
def portal_confirm(
    receipt_id: str,
    user: CurrentUser = Depends(MERCHANT),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> PortalMe:
    """The merchant says this receipt looks right."""
    receipt = _own_receipt(session, user, receipt_id)
    try:
        service.confirm(session, receipt)
    except service.ReceiptError as error:
        raise api_error(error.status, error.code, error.message) from None
    add_audit(session, user, "merchant_confirms_receipt", receipt.merchant_id)
    session.commit()
    return portal_me(user, services, session)


@router.post("/portal/proof", response_model=ProofOut, status_code=201, openapi_extra=UPLOAD_ANY)
async def portal_proof(
    request: Request,
    name: str = Query(default="proof"),
    user: CurrentUser = Depends(MERCHANT),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ProofOut:
    """Upload a photo of the merchant's own copy, to attach to a report."""
    body = await read_capped(
        request, int(services.config["registration"]["signed_max_mb"]) * 1024 * 1024
    )
    try:
        doc = docs.store_document(
            session,
            services.config,
            user,
            org_of(user, services.config),
            body,
            kind="report_proof",
            original_name=name,
            merchant_id=_own(user),
            registration_id=None,
        )
    except IntakeRefused as error:
        session.rollback()
        raise api_error(error.status, error.code, error.message) from None
    session.commit()
    return ProofOut(document_id=doc.document_id)


@router.post("/portal/lines/{line_id}/report", response_model=PortalReport, status_code=201)
def portal_report(
    line_id: str,
    body: ReportIn,
    user: CurrentUser = Depends(MERCHANT),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> PortalReport:
    """Report a published line as wrong. It leaves the score until the Records Desk answers."""
    merchant_id = _own(user)
    line = session.get(db.ReceiptLine, line_id)
    if line is None or line.merchant_id != merchant_id:
        raise api_error(404, "unknown_line", "No such line.")
    proof = None
    if body.proof_document_id:
        proof = session.get(db.Document, body.proof_document_id)
        if proof is None or proof.merchant_id != merchant_id or proof.kind != "report_proof":
            raise api_error(404, "unknown_proof", "That photo was not found. Upload it again.")
    try:
        flag = service.raise_flag(session, user, line, body.note, body.claimed_amount_bdt, proof)
    except service.ReceiptError as error:
        session.rollback()
        raise api_error(error.status, error.code, error.message) from None
    add_audit(session, user, "merchant_reports_line", merchant_id)
    session.commit()
    auto_assess(services, session, user, merchant_id)
    return _report_out(session, flag)


def _report_out(session: Session, flag: db.ReceiptFlag) -> PortalReport:
    line = session.get(db.ReceiptLine, flag.line_id)
    receipt = session.get(db.Receipt, flag.receipt_id)
    return PortalReport(
        flag_id=flag.flag_id,
        status=flag.status,
        receipt_id=flag.receipt_id,
        supplier=receipt.supplier,
        item=line.item,
        recorded_amount_bdt=line.amount_bdt,
        claimed_amount_bdt=flag.claimed_amount_bdt,
        note=flag.note,
        answer=flag.resolution_note,
        raised_at=_iso(flag.raised_at),
        resolved_at=_iso(flag.resolved_at),
    )


@router.get("/portal/reports", response_model=list[PortalReport])
def portal_reports(
    user: CurrentUser = Depends(MERCHANT), session: Session = Depends(get_session)
) -> list[PortalReport]:
    return [
        _report_out(session, f)
        for f in session.scalars(
            select(db.ReceiptFlag)
            .where(db.ReceiptFlag.merchant_id == _own(user))
            .order_by(db.ReceiptFlag.raised_at.desc())
        )
    ]


# --- the loan application --------------------------------------------------------------------


def _application_status(
    session: Session, services: Services, user: CurrentUser
) -> ApplicationStatus:
    merchant_id = _own(user)
    settings = services.config["demo"]["application"]
    base = dict(
        max_requested_bdt=float(settings["max_requested_bdt"]), purposes=list(settings["purposes"])
    )
    app = session.scalar(select(db.Application).where(db.Application.merchant_id == merchant_id))
    if app is not None:
        decided = session.scalar(
            select(db.Decision.decision_id).where(db.Decision.merchant_id == merchant_id).limit(1)
        )
        return ApplicationStatus(
            has_application=True,
            requested_amount_bdt=app.requested_amount_bdt,
            purpose=app.purpose,
            applied_on=_iso(app.business_date),
            can_apply=False,
            cannot_apply_reason="You have already applied.",
            status="decided" if decided else "received",
            status_text=(
                "Your lender has recorded a decision and will contact you."
                if decided
                else "Your application was received and is being reviewed by your lender."
            ),
            **base,
        )
    valid, _ = consent_state(session, merchant_id, services.data_today(session))
    return ApplicationStatus(
        has_application=False,
        can_apply=bool(valid),
        cannot_apply_reason=None if valid else "Your consent form has not been checked yet.",
        **base,
    )


@router.get("/portal/application", response_model=ApplicationStatus)
def portal_application(
    user: CurrentUser = Depends(MERCHANT),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ApplicationStatus:
    return _application_status(session, services, user)


@router.post("/portal/application", response_model=ApplicationStatus, status_code=201)
def portal_apply(
    body: ApplyIn,
    user: CurrentUser = Depends(MERCHANT),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ApplicationStatus:
    """The merchant applies for a loan. It appears to the Credit Officers like any application."""
    merchant_id = _own(user)
    try:
        create_application(
            session,
            services.config,
            merchant_id=merchant_id,
            requested_amount_bdt=body.requested_amount_bdt,
            purpose=body.purpose,
            purpose_note=body.purpose_note,
            business_date=services.data_today(session),
            actor=user,
            protected_merchants=protected(services),
        )
    except IntakeRefused as error:
        session.rollback()
        raise api_error(error.status, error.code, error.message) from None
    profile = session.get(db.MerchantProfile, merchant_id)
    notify_officers(
        session,
        org_of(user, services.config),
        "merchant_application",
        f"{profile.shop_name if profile else merchant_id} applied for a loan.",
        f"/app/merchants/{merchant_id}",
    )
    add_audit(session, user, "merchant_applies", merchant_id)
    session.commit()
    refresh_scoring(services, session)
    auto_assess(services, session, user, merchant_id)
    return _application_status(session, services, user)
