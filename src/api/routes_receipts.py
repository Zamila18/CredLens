"""The Records Desk: upload receipts, check what was read, publish, and answer merchants.

Purpose: the API behind the Records Officer's work. A receipt is uploaded for a shop; the reader
    fills a table (a background job); the officer compares it with the picture, fixes it and
    publishes it, which is the only way a receipt reaches the credit officers and the score.
    A merchant's report of a mistake comes back here to be accepted or rejected with a reason.
Owner role: D (full-stack).
Implements: the receipt workflow of the Records Desk redesign.

Credit Officers and Auditors may read; only the Records Desk changes anything. Nothing here
approves or declines credit.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.accounts import merchant_access
from src.api.auth import CurrentUser, add_audit, require_roles
from src.api.common import api_error
from src.api.imported import refresh_scoring
from src.api.profile import consent_state
from src.api.state import Services, get_services, get_session
from src.api.tenancy import org_of
from src.api.uploads import read_capped
from src.db import models as db
from src.onboarding import registrations as docs
from src.receipts import service

router = APIRouter(tags=["receipts"])
DESK = require_roles("records_officer")
DESK_READ = require_roles("records_officer", "credit_officer", "auditor")
OFFICER = require_roles("credit_officer")

UPLOAD_ANY = {
    "requestBody": {
        "required": True,
        "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
    }
}


# --- shapes ------------------------------------------------------------------------------------


class CellFlag(BaseModel):
    cell: str
    code: str
    text: str


class LineOut(BaseModel):
    line_id: str
    row_no: int
    status: str
    item: str | None
    quantity: float | None
    unit: str | None
    unit_price: float | None
    amount_bdt: float | None
    line_date: str | None
    due_date: str | None
    outcome: str | None
    reference: str | None
    confidence: dict[str, float]
    flags: list[CellFlag]
    edited: bool


class ReceiptOut(BaseModel):
    receipt_id: str
    merchant_id: str
    shop_name: str | None
    kind: str
    status: str
    method: str
    reading: str = Field(description="none | queued | running | done | failed")
    reading_error: str | None
    supplier: str | None
    receipt_date: str | None
    memo_no: str | None
    stated_total: float | None
    lines_total: float
    notes: list[str]
    lines: list[LineOut]
    has_document: bool
    uploaded_at: str
    published_at: str | None
    merchant_confirmed_at: str | None
    reject_reason: str | None
    cells_to_check: int


class ReceiptRow(BaseModel):
    receipt_id: str
    merchant_id: str
    shop_name: str | None
    kind: str
    status: str
    reading: str
    supplier: str | None
    receipt_date: str | None
    lines: int
    cells_to_check: int
    lines_total: float
    uploaded_at: str


class HeaderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier: str | None = None
    receipt_date: str | None = None
    memo_no: str | None = None
    stated_total: float | str | None = None


class LineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_id: str | None = None
    item: str | None = None
    quantity: float | str | None = None
    unit: str | None = None
    unit_price: float | str | None = None
    amount_bdt: float | str | None = None
    line_date: str | None = None
    due_date: str | None = None
    outcome: str | None = None
    reference: str | None = None


class ReceiptSaveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    header: HeaderIn = HeaderIn()
    lines: list[LineIn]


class PublishIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    acknowledged: bool = Field(
        default=False, description="The officer compared the highlighted cells with the paper."
    )


class RejectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(max_length=300)


class TypedReceiptIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str


class ReportOut(BaseModel):
    flag_id: str
    status: str
    merchant_id: str
    shop_name: str | None
    receipt_id: str
    receipt_kind: str
    supplier: str | None
    receipt_date: str | None
    line_no: int
    item: str | None
    recorded_amount_bdt: float | None
    claimed_amount_bdt: float | None
    note: str
    has_proof: bool
    raised_at: str
    resolution_note: str | None
    resolved_at: str | None


class ResolveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accept: bool
    amount_bdt: float | None = None
    note: str = Field(max_length=300)


class ShopPick(BaseModel):
    merchant_id: str
    shop_name: str | None
    area: str | None
    owner_name: str | None
    receipts_to_check: int


class MerchantAccessOut(BaseModel):
    merchant_id: str
    shop_name: str | None
    owner_name: str | None
    portal_id: str
    portal_open: bool
    sign_in_hint: str


# --- helpers -----------------------------------------------------------------------------------


def _refused(error: service.ReceiptError):
    return api_error(error.status, error.code, error.message, **error.facts)


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat(timespec="seconds") if hasattr(value, "hour") else value.isoformat()


def _shop(session: Session, merchant_id: str) -> str | None:
    profile = session.get(db.MerchantProfile, merchant_id)
    return profile.shop_name if profile else None


def reading_state(session: Session, receipt: db.Receipt) -> tuple[str, str | None]:
    if not receipt.job_id:
        return "none", None
    job = session.get(db.ExtractionJob, receipt.job_id)
    return (job.status, job.error) if job else ("none", None)


def line_out(row: db.ReceiptLine) -> LineOut:
    return LineOut(
        line_id=row.line_id,
        row_no=row.row_no,
        status=row.status,
        item=row.item,
        quantity=row.quantity,
        unit=row.unit,
        unit_price=row.unit_price,
        amount_bdt=row.amount_bdt,
        line_date=_iso(row.line_date),
        due_date=_iso(row.due_date),
        outcome=row.outcome,
        reference=row.reference,
        confidence=service.confidence_of(row),
        flags=[CellFlag(**f) for f in service.flags_of(row)],
        edited=bool(row.edited),
    )


def receipt_out(session: Session, receipt: db.Receipt) -> ReceiptOut:
    rows = service.lines_of(session, receipt.receipt_id)
    reading, error = reading_state(session, receipt)
    return ReceiptOut(
        receipt_id=receipt.receipt_id,
        merchant_id=receipt.merchant_id,
        shop_name=_shop(session, receipt.merchant_id),
        kind=receipt.kind,
        status=receipt.status,
        method=receipt.method,
        reading=reading,
        reading_error=error,
        supplier=receipt.supplier,
        receipt_date=_iso(receipt.receipt_date),
        memo_no=receipt.memo_no,
        stated_total=receipt.stated_total,
        lines_total=float(sum(r.amount_bdt or 0 for r in rows)),
        notes=service.notes_of(receipt),
        lines=[line_out(r) for r in rows],
        has_document=receipt.document_id is not None,
        uploaded_at=_iso(receipt.uploaded_at),
        published_at=_iso(receipt.published_at),
        merchant_confirmed_at=_iso(receipt.merchant_confirmed_at),
        reject_reason=receipt.reject_reason,
        cells_to_check=sum(1 for r in rows if service.flags_of(r)),
    )


def get_receipt(session: Session, user: CurrentUser, services: Services, receipt_id: str):
    receipt = session.get(db.Receipt, receipt_id)
    if receipt is None or receipt.organization_id != org_of(user, services.config):
        raise api_error(404, "unknown_receipt", "No such receipt.")
    return receipt


def protected(services: Services) -> frozenset[str]:
    if services.scorer is None:
        raise api_error(
            503, "scorer_not_ready", services.scorer_error or "The scorer is not ready."
        )
    return services.scorer.source_merchant_ids()


def auto_assess(services: Services, session: Session, user: CurrentUser, merchant_id: str) -> None:
    """After new checked evidence: refresh the scorer and, when the shop has an application,
    store a fresh assessment. Best effort: the records are already saved."""
    try:
        refresh_scoring(services, session)
        if session.scalar(
            select(db.Application.application_id).where(db.Application.merchant_id == merchant_id)
        ):
            from src.assessment.service import run_assessment

            run_assessment(
                session,
                services.scorer,
                org_of(user, services.config),
                user.user_id,
                merchant_id,
                services.data_today(session),
            )
            session.commit()
    except Exception:  # noqa: BLE001 - never undo published records because a score could not run
        session.rollback()


@router.get("/receipt-shops", response_model=list[ShopPick])
def receipt_shops(
    user: CurrentUser = Depends(DESK),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> list[ShopPick]:
    """The shops the Records Desk can add receipts to: the company's, with a verified consent."""
    from src.api.tenancy import merchant_in_org

    org = org_of(user, services.config)
    today = services.data_today(session)
    out = []
    for merchant in session.scalars(
        select(db.Merchant)
        .where(merchant_in_org(org, services.config))
        .order_by(db.Merchant.merchant_id)
    ):
        valid, _ = consent_state(session, merchant.merchant_id, today)
        profile = session.get(db.MerchantProfile, merchant.merchant_id)
        if not valid or profile is None:
            continue
        waiting = session.scalar(
            select(func.count())
            .select_from(db.Receipt)
            .where(
                db.Receipt.merchant_id == merchant.merchant_id,
                db.Receipt.status.in_(("extracted", "checked")),
            )
        )
        out.append(
            ShopPick(
                merchant_id=merchant.merchant_id,
                shop_name=profile.shop_name,
                area=profile.area,
                owner_name=profile.owner_name,
                receipts_to_check=int(waiting or 0),
            )
        )
    return out


# --- receipts ----------------------------------------------------------------------------------


@router.post(
    "/merchants/{merchant_id}/receipts",
    response_model=ReceiptOut,
    status_code=201,
    openapi_extra=UPLOAD_ANY,
)
async def upload_receipt(
    merchant_id: str,
    request: Request,
    kind: str = Query(default="purchase"),
    name: str = Query(default="receipt"),
    user: CurrentUser = Depends(DESK),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ReceiptOut:
    """Upload a receipt photo, scan or PDF for a shop. It is read in the background."""
    org = org_of(user, services.config)
    valid, _ = consent_state(session, merchant_id, services.data_today(session))
    if not valid:
        raise api_error(
            403, "consent_required", "This shop's consent form has not been verified yet."
        )
    body = await read_capped(
        request, int(services.config["registration"]["signed_max_mb"]) * 1024 * 1024
    )
    try:
        document = docs.store_document(
            session,
            services.config,
            user,
            org,
            body,
            kind="receipt",
            original_name=name,
            merchant_id=merchant_id,
            registration_id=None,
        )
        receipt = service.create_receipt(session, user, org, merchant_id, kind, document)
    except service.ReceiptError as error:
        session.rollback()
        raise _refused(error) from None
    except docs.IntakeRefused as error:
        session.rollback()
        raise api_error(error.status, error.code, error.message) from None
    add_audit(session, user, "upload_receipt", merchant_id)
    session.commit()
    return receipt_out(session, receipt)


@router.post("/merchants/{merchant_id}/receipts/typed", response_model=ReceiptOut, status_code=201)
def typed_receipt(
    merchant_id: str,
    body: TypedReceiptIn,
    user: CurrentUser = Depends(DESK),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ReceiptOut:
    """Start a receipt with no file: the officer types the lines (handwritten or lost paper)."""
    valid, _ = consent_state(session, merchant_id, services.data_today(session))
    if not valid:
        raise api_error(
            403, "consent_required", "This shop's consent form has not been verified yet."
        )
    try:
        receipt = service.create_receipt(
            session, user, org_of(user, services.config), merchant_id, body.kind, None
        )
    except service.ReceiptError as error:
        raise _refused(error) from None
    add_audit(session, user, "start_typed_receipt", merchant_id)
    session.commit()
    return receipt_out(session, receipt)


@router.get("/receipts", response_model=list[ReceiptRow])
def list_receipts(
    status: str | None = Query(default=None),
    merchant_id: str | None = Query(default=None),
    user: CurrentUser = Depends(DESK_READ),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> list[ReceiptRow]:
    """The company's receipts, newest first."""
    query = select(db.Receipt).where(db.Receipt.organization_id == org_of(user, services.config))
    if status:
        query = query.where(db.Receipt.status == status)
    if merchant_id:
        query = query.where(db.Receipt.merchant_id == merchant_id)
    out = []
    for receipt in session.scalars(query.order_by(db.Receipt.uploaded_at.desc()).limit(300)):
        rows = service.lines_of(session, receipt.receipt_id)
        reading, _ = reading_state(session, receipt)
        out.append(
            ReceiptRow(
                receipt_id=receipt.receipt_id,
                merchant_id=receipt.merchant_id,
                shop_name=_shop(session, receipt.merchant_id),
                kind=receipt.kind,
                status=receipt.status,
                reading=reading,
                supplier=receipt.supplier,
                receipt_date=_iso(receipt.receipt_date),
                lines=len(rows),
                cells_to_check=sum(1 for r in rows if service.flags_of(r)),
                lines_total=float(sum(r.amount_bdt or 0 for r in rows)),
                uploaded_at=_iso(receipt.uploaded_at),
            )
        )
    return out


@router.get("/receipts/{receipt_id}", response_model=ReceiptOut)
def receipt_detail(
    receipt_id: str,
    user: CurrentUser = Depends(DESK_READ),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ReceiptOut:
    return receipt_out(session, get_receipt(session, user, services, receipt_id))


@router.put("/receipts/{receipt_id}", response_model=ReceiptOut)
def save_receipt(
    receipt_id: str,
    body: ReceiptSaveIn,
    user: CurrentUser = Depends(DESK),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ReceiptOut:
    """Save the officer's corrections. The checks run again on the new numbers."""
    receipt = get_receipt(session, user, services, receipt_id)
    try:
        service.save_edits(
            session,
            user,
            receipt,
            body.header.model_dump(exclude_unset=True),
            [line.model_dump(exclude_unset=True) for line in body.lines],
            services.data_today(session),
            float(services.config["ocr"]["low_confidence_below"]),
        )
    except service.ReceiptError as error:
        session.rollback()
        raise _refused(error) from None
    add_audit(session, user, "check_receipt", receipt.merchant_id)
    session.commit()
    return receipt_out(session, receipt)


@router.get("/receipts/{receipt_id}/document")
def receipt_document(
    receipt_id: str,
    user: CurrentUser = Depends(DESK_READ),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> Response:
    """The uploaded receipt, as stored (every view is audited)."""
    receipt = get_receipt(session, user, services, receipt_id)
    return _document_response(session, services, user, receipt)


def _document_response(
    session: Session, services: Services, user: CurrentUser, receipt: db.Receipt
) -> Response:
    doc = session.get(db.Document, receipt.document_id) if receipt.document_id else None
    if doc is None:
        raise api_error(404, "no_document", "This receipt has no picture (it was typed in).")
    try:
        data = docs.read_document(services.config, doc)
    except docs.IntakeRefused as error:
        raise api_error(error.status, error.code, error.message) from None
    add_audit(session, user, "view_receipt_picture", receipt.merchant_id)
    session.commit()
    return Response(
        data,
        media_type=doc.mime,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/receipts/{receipt_id}/publish", response_model=ReceiptOut)
def publish_receipt(
    receipt_id: str,
    body: PublishIn,
    user: CurrentUser = Depends(DESK),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ReceiptOut:
    """Publish the checked receipt: its lines reach the credit officers and the score."""
    receipt = get_receipt(session, user, services, receipt_id)
    try:
        service.publish(
            session, services.config, user, receipt, protected(services), body.acknowledged
        )
    except service.ReceiptError as error:
        session.rollback()
        raise _refused(error) from None
    session.commit()
    auto_assess(services, session, user, receipt.merchant_id)
    session.refresh(receipt)
    return receipt_out(session, receipt)


@router.post("/receipts/{receipt_id}/reject", response_model=ReceiptOut)
def reject_receipt(
    receipt_id: str,
    body: RejectIn,
    user: CurrentUser = Depends(DESK),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ReceiptOut:
    receipt = get_receipt(session, user, services, receipt_id)
    try:
        service.reject(session, user, receipt, body.reason)
    except service.ReceiptError as error:
        session.rollback()
        raise _refused(error) from None
    session.commit()
    return receipt_out(session, receipt)


# --- merchants' reports ------------------------------------------------------------------------


def report_out(session: Session, flag: db.ReceiptFlag) -> ReportOut:
    line = session.get(db.ReceiptLine, flag.line_id)
    receipt = session.get(db.Receipt, flag.receipt_id)
    return ReportOut(
        flag_id=flag.flag_id,
        status=flag.status,
        merchant_id=flag.merchant_id,
        shop_name=_shop(session, flag.merchant_id),
        receipt_id=flag.receipt_id,
        receipt_kind=receipt.kind,
        supplier=receipt.supplier,
        receipt_date=_iso(receipt.receipt_date),
        line_no=line.row_no,
        item=line.item,
        recorded_amount_bdt=line.amount_bdt,
        claimed_amount_bdt=flag.claimed_amount_bdt,
        note=flag.note,
        has_proof=flag.proof_document_id is not None,
        raised_at=_iso(flag.raised_at),
        resolution_note=flag.resolution_note,
        resolved_at=_iso(flag.resolved_at),
    )


def _flag(session: Session, user: CurrentUser, services: Services, flag_id: str) -> db.ReceiptFlag:
    flag = session.get(db.ReceiptFlag, flag_id)
    if flag is None or flag.organization_id != org_of(user, services.config):
        raise api_error(404, "unknown_report", "No such report.")
    return flag


@router.get("/merchant-reports", response_model=list[ReportOut])
def list_reports(
    status: str | None = Query(default="open"),
    user: CurrentUser = Depends(DESK_READ),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> list[ReportOut]:
    """Mistakes merchants reported on their receipts, oldest open first."""
    query = select(db.ReceiptFlag).where(
        db.ReceiptFlag.organization_id == org_of(user, services.config)
    )
    if status and status != "all":
        query = query.where(db.ReceiptFlag.status == status)
    order = db.ReceiptFlag.raised_at.asc() if status == "open" else db.ReceiptFlag.raised_at.desc()
    return [report_out(session, f) for f in session.scalars(query.order_by(order).limit(300))]


@router.post("/merchant-reports/{flag_id}/resolve", response_model=ReportOut)
def resolve_report(
    flag_id: str,
    body: ResolveIn,
    user: CurrentUser = Depends(DESK),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ReportOut:
    """Accept (correct the line) or reject a report, with a note the merchant will read."""
    flag = _flag(session, user, services, flag_id)
    try:
        service.resolve_flag(
            session, services.config, user, flag, body.accept, body.amount_bdt, body.note
        )
    except service.ReceiptError as error:
        session.rollback()
        raise _refused(error) from None
    session.commit()
    auto_assess(services, session, user, flag.merchant_id)
    session.refresh(flag)
    return report_out(session, flag)


@router.get("/merchant-reports/{flag_id}/proof")
def report_proof(
    flag_id: str,
    user: CurrentUser = Depends(DESK_READ),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> Response:
    flag = _flag(session, user, services, flag_id)
    doc = session.get(db.Document, flag.proof_document_id) if flag.proof_document_id else None
    if doc is None:
        raise api_error(404, "no_document", "The merchant attached no proof.")
    try:
        data = docs.read_document(services.config, doc)
    except docs.IntakeRefused as error:
        raise api_error(error.status, error.code, error.message) from None
    add_audit(session, user, "view_report_proof", flag.merchant_id)
    session.commit()
    return Response(
        data,
        media_type=doc.mime,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


# --- the Merchant ID, for the handover slip ------------------------------------------------------


@router.get("/merchants/{merchant_id}/access", response_model=MerchantAccessOut)
def merchant_access_info(
    merchant_id: str,
    user: CurrentUser = Depends(OFFICER),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> MerchantAccessOut:
    """The shop's Merchant ID, to print on its handover slip (every view is audited)."""
    access = session.get(db.MerchantAccess, merchant_id)
    if access is None:
        raise api_error(404, "no_access", "This shop has no Merchant ID.")
    profile = session.get(db.MerchantProfile, merchant_id)
    valid, _ = consent_state(session, merchant_id, services.data_today(session))
    add_audit(session, user, "view_merchant_id", merchant_id)
    session.commit()
    return MerchantAccessOut(
        merchant_id=merchant_id,
        shop_name=profile.shop_name if profile else None,
        owner_name=profile.owner_name if profile else None,
        portal_id=merchant_access.show_portal_id(access.portal_id),
        portal_open=bool(valid),
        sign_in_hint="The merchant signs in with this Merchant ID and the owner's name."
        if valid
        else "The portal opens once the consent form has been checked.",
    )


@router.post("/merchants/{merchant_id}/access/reissue", response_model=MerchantAccessOut)
def reissue_merchant_id(
    merchant_id: str,
    user: CurrentUser = Depends(OFFICER),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> MerchantAccessOut:
    """Give the shop a new Merchant ID (the old one stops working and open sessions end)."""
    access = session.get(db.MerchantAccess, merchant_id)
    if access is None:
        raise api_error(404, "no_access", "This shop has no Merchant ID.")
    access.portal_id = merchant_access.new_portal_id(session)
    if access.user_id:
        from src.accounts.service import revoke_all_sessions

        revoke_all_sessions(session, access.user_id)
    add_audit(session, user, "reissue_merchant_id", merchant_id)
    session.commit()
    return merchant_access_info(merchant_id, user, services, session)


def counts(session: Session, org: str) -> dict[str, int]:
    """Numbers for the officer's overview."""

    def n(model, *where) -> int:
        return int(
            session.scalar(
                select(func.count()).select_from(model).where(model.organization_id == org, *where)
            )
            or 0
        )

    return {
        "receipts_to_check": n(db.Receipt, db.Receipt.status.in_(("extracted", "checked"))),
        "receipts_published": n(db.Receipt, db.Receipt.status == "published"),
        "lines_disputed": n(db.ReceiptLine, db.ReceiptLine.status == "disputed"),
        "merchant_reports_open": n(db.ReceiptFlag, db.ReceiptFlag.status == "open"),
    }


_ = (date, Any)
