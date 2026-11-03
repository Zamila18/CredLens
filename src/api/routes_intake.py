"""The demo workflow's endpoints: find or add a shop, consent, records, visits, application.

Purpose: what the field screens and the officer workspace call to write and read records.
Owner role: D (full-stack).
Implements: the implementation pack, Phase 3.

Rules kept here (the checks themselves live in src/intake/, so no endpoint can skip them):
- Writes are for officers only. In this prototype the field workflow runs under the officer
  demo identity: there is no separate field role, so the server does NOT separate field
  staff from the officers who decide. Viewers and admins cannot write here.
- A refused write saves nothing. A refusal about consent, mode or the benchmark data is
  written to the audit log.
- After a save the scorer reads every created merchant again. The answer says whether the
  assessment was refreshed or could not be updated; an older score is never shown as new.
- Every read of a merchant's records writes an audit entry before anything is returned.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from src.api import review
from src.api.auth import EVERY_ROLE, CurrentUser, add_audit, require_roles
from src.api.common import api_error, refuse_rows_not_shown
from src.api.imported import refresh_imported, refresh_real
from src.api.importer import DELIVERY_STATUSES
from src.api.profile import consent_state
from src.api.receipt import build_receipt
from src.api.schemas import (
    ApplicationCreate,
    ApplicationOut,
    AssessmentOutcome,
    ConsentEventOut,
    ConsentResponseCreate,
    DeliveryCreate,
    DemoSettings,
    ImportInspect,
    ImportPreview,
    ImportResult,
    ImportRow,
    ImportSheet,
    MerchantCreate,
    MerchantLoan,
    MerchantSummary,
    PurchaseCreate,
    Receipt,
    RecordSaved,
    RepaymentCreate,
    ReviewStatus,
    VisitCreate,
    WorkflowStatus,
)
from src.api.scoring_access import note_refusal
from src.api.state import Services, get_services, get_session
from src.api.tenancy import merchant_scope, org_of
from src.config import load_config
from src.db import models as db
from src.intake import spreadsheet
from src.intake.applications import create_application
from src.intake.consent import record_consent_response
from src.intake.merchants import create_merchant, districts, search_merchants, shop_types
from src.intake.policy import IntakeRefused, benchmark_request, calendar_end, demo, live_merchant
from src.intake.records import (
    RETURN_REASONS,
    counts_for_assessment,
    record_delivery,
    record_purchase,
    record_repayment,
)
from src.intake.visits import record_visit
from src.model.explain import ConsentRequired
from src.model.scoring import UnknownMerchant

router = APIRouter(tags=["demo workflow"])

ANY_ROLE = require_roles(*EVERY_ROLE)
# Field work: the sandbox officer, or a sales representative on an assigned shop (the
# merchant guard in tenancy.py checks the assignment).
OFFICER_ONLY = require_roles("credit_officer", "fsr")
SHOP_CREATORS = require_roles("credit_officer", "fsr")

# Refusals worth a line in the audit log: someone tried to write what they may not.
AUDITED_REFUSALS = {
    "consent_required",
    "consent_category_missing",
    "intake_closed",
    "benchmark_merchant",
}


# --- helpers -------------------------------------------------------------------------------


def _day(value: str | None, config: dict[str, Any], what: str) -> date:
    """A business date from the request; the calendar's end when it is not given."""
    if value is None:
        return calendar_end(config)
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise api_error(422, "invalid_date", f"{what} must be a date like 2026-08-30.") from None


def _moment(value: str | None, what: str) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=None)
    except ValueError:
        raise api_error(422, "invalid_date", f"{what} must be like 2026-08-30T10:30.") from None


def _protected(services: Services) -> frozenset[str]:
    """The benchmark merchants: read-only for the workflow."""
    if services.scorer is None:
        raise api_error(
            503, "scorer_not_ready", services.scorer_error or "The scorer is not ready."
        )
    return services.scorer.source_merchant_ids()


def _refused(
    error: IntakeRefused, session: Session, user: CurrentUser, action: str, merchant_id: str | None
):
    """Turn a refusal into the API's error shape; audit the ones that matter."""
    if error.code in AUDITED_REFUSALS:
        note_refusal(session, user, f"refused_{action}", merchant_id)
    return api_error(error.status, error.code, error.message, **error.facts)


def _assessment(services: Services, session: Session, merchant_id: str) -> AssessmentOutcome:
    """Read every created merchant into the scorer again and say how this one came out."""
    if benchmark_request():
        services.forget_data_today()
        refresh_imported(services, session)
    else:
        refresh_real(services, session)
    scorer = services.scorer
    if merchant_id in scorer.not_updated:
        return AssessmentOutcome(
            status="not_updated",
            message="Saved. The assessment could not be updated, so no score is shown for now.",
        )
    if merchant_id in scorer.merchant_ids():
        return AssessmentOutcome(status="refreshed", message="Saved. The assessment is up to date.")
    return AssessmentOutcome(
        status="no_application",
        message="Saved. There is no application yet, so there is nothing to assess.",
    )


def _saved(
    services: Services,
    session: Session,
    *,
    record_type: str,
    record_id: str,
    merchant_id: str,
    business_date: date,
    repeat: bool,
) -> RecordSaved:
    provenance = session.scalars(
        select(db.RecordProvenance)
        .where(
            db.RecordProvenance.record_type == record_type,
            db.RecordProvenance.record_id == record_id,
        )
        .order_by(db.RecordProvenance.provenance_id.desc())
    ).first()
    return RecordSaved(
        record_type=record_type,
        record_id=record_id,
        merchant_id=merchant_id,
        business_date=business_date.isoformat(),
        entered_at=provenance.entered_at.isoformat(timespec="seconds") if provenance else None,
        entry_method=provenance.entry_method if provenance else "staff_entered",
        status=provenance.status if provenance else "staff_entered",
        repeat=repeat,
        counts_for_assessment=(
            None
            if record_type == "application"
            else counts_for_assessment(session, merchant_id, business_date)
        ),
        assessment=_assessment(services, session, merchant_id),
    )


def _summary(session: Session, merchant: db.Merchant) -> MerchantSummary:
    profile = session.get(db.MerchantProfile, merchant.merchant_id)
    return MerchantSummary(
        merchant_id=merchant.merchant_id,
        shop_name=profile.shop_name if profile else None,
        area=profile.area if profile else None,
        district=merchant.district,
        shop_type=merchant.shop_type,
        created_in_app=profile is not None,
    )


def _merchant(session: Session, merchant_id: str) -> db.Merchant:
    merchant = session.get(db.Merchant, merchant_id)
    if merchant is None:
        raise api_error(404, "unknown_merchant", f"No merchant {merchant_id!r} in the database.")
    return merchant


def _application_out(services: Services, application: db.Application) -> ApplicationOut:
    scorer = services.scorer
    if scorer is not None and application.merchant_id in scorer.not_updated:
        status = "not_updated"
    elif scorer is not None and application.merchant_id in scorer.merchant_ids():
        status = "current"
    else:
        status = "not_scored"
    return ApplicationOut(
        application_id=application.application_id,
        loan_id=application.loan_id,
        merchant_id=application.merchant_id,
        requested_amount_bdt=application.requested_amount_bdt,
        purpose=application.purpose,
        purpose_note=application.purpose_note,
        business_date=application.business_date.isoformat(),
        entered_at=application.entered_at.isoformat(timespec="seconds"),
        created_by=application.created_by,
        assessment_status=status,
    )


# --- settings and search ------------------------------------------------------------------


@router.get("/demo/settings", response_model=DemoSettings)
def demo_settings(services: Services = Depends(get_services)) -> DemoSettings:
    """The demo's rules from the config, for the forms (choices, limits, the calendar).

    Needs no token: it holds no data about anyone.
    """
    config = load_config()
    settings = demo(config)
    matches = None
    if benchmark_request() and not services.database_error:
        with Session(services.engine) as session:
            matches = services.data_today(session) == calendar_end(config)
    return DemoSettings(
        # A real organisation's account: real records, dated up to today's real date.
        synthetic_only=settings["synthetic_only"] if benchmark_request() else False,
        calendar_end=calendar_end(config).isoformat(),
        calendar_matches_data=matches,
        consent_wording_version=settings["consent"]["wording_version"],
        consent_purpose=settings["consent"]["purpose"],
        consent_categories=settings["consent"]["categories"],
        consent_methods=settings["consent"]["methods"],
        consent_valid_days=settings["consent"]["valid_days"],
        application_purposes=settings["application"]["purposes"],
        max_requested_bdt=settings["application"]["max_requested_bdt"],
        application_note_max_chars=settings["application"]["note_max_chars"],
        visit_outcomes=settings["visit"]["outcomes"],
        visit_note_max_chars=settings["visit"]["note_max_chars"],
        import_max_file_mb=settings["purchase_import"]["max_file_mb"],
        import_max_rows=settings["purchase_import"]["max_rows"],
        range_policy_enabled=True,
        districts=sorted(districts(config)),
        shop_types=shop_types(config),
        delivery_statuses=list(DELIVERY_STATUSES),
        return_reasons=list(RETURN_REASONS),
    )


@router.get("/search/merchants", response_model=list[MerchantSummary])
def merchant_search(
    q: str = Query(min_length=2, max_length=80),
    limit: int = Query(default=20, ge=1, le=50),
    user: CurrentUser = Depends(ANY_ROLE),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> list[dict]:
    """Merchants whose id starts with `q`, or whose shop name or area contains it. Audited."""
    refuse_rows_not_shown(services.config)
    found = search_merchants(
        session, q, limit, merchant_scope(session, user, services.config)
    )
    add_audit(session, user, "search_merchants")
    session.commit()
    return found


# --- writes -------------------------------------------------------------------------------


@router.post("/merchants", response_model=MerchantSummary, status_code=201)
def new_merchant(
    body: MerchantCreate,
    user: CurrentUser = Depends(SHOP_CREATORS),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> MerchantSummary:
    """Create a synthetic shop. 409 `possible_duplicate` lists likely matches; send
    `confirm_new: true` once staff are sure it is a different shop."""
    config = services.config
    try:
        merchant = create_merchant(
            session,
            config,
            shop_name=body.shop_name,
            area=body.area,
            district=body.district,
            shop_type=body.shop_type,
            has_trade_license=body.has_trade_license,
            business_date=_day(body.start_date, config, "The start date"),
            actor=user,
            confirm_new=body.confirm_new,
        )
    except IntakeRefused as error:
        raise _refused(error, session, user, "create_merchant", None) from None
    if user.role == "fsr":  # a shop an FSR registers is theirs to work on
        from src.accounts.service import assign_shop

        assign_shop(
            session,
            org_of(user, config),
            merchant.merchant_id,
            user.user_id,
            user.user_id,
            default_org=config["organization"]["id"],
        )
        add_audit(session, user, "assign_shop", merchant.merchant_id)
        session.commit()
    return _summary(session, merchant)


@router.post(
    "/merchants/{merchant_id}/consent-responses", response_model=ConsentEventOut, status_code=201
)
def consent_response(
    merchant_id: str,
    body: ConsentResponseCreate,
    user: CurrentUser = Depends(OFFICER_ONLY),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ConsentEventOut:
    """Record the merchant's answer to the consent explanation (staff-assisted, simulated).

    A grant creates the consent the scorer reads; a refusal records only the answer.
    """
    config = services.config
    try:
        event = record_consent_response(
            session,
            config,
            merchant_id=merchant_id,
            response=body.response,
            categories=body.categories,
            method=body.method,
            actor=user,
            business_date=_day(body.business_date, config, "The consent date"),
            protected_merchants=_protected(services),
        )
    except IntakeRefused as error:
        raise _refused(error, session, user, "consent_response", merchant_id) from None
    services.forget_data_today()
    refresh_imported(services, session)
    return ConsentEventOut(
        event_id=event.event_id,
        merchant_id=merchant_id,
        consent_id=event.consent_id,
        response=event.response,
        categories=event.categories.split("|"),
        method=event.method,
        wording_version=event.wording_version,
        business_date=event.business_date.isoformat(),
        recorded_at=event.recorded_at.isoformat(timespec="seconds"),
        recorded_by=event.actor,
        simulated=event.simulated,
    )


@router.post("/merchants/{merchant_id}/purchases", response_model=RecordSaved, status_code=201)
def new_purchase(
    merchant_id: str,
    body: PurchaseCreate,
    user: CurrentUser = Depends(OFFICER_ONLY),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> RecordSaved:
    """Save a stock purchase typed in by staff (not verified)."""
    config = services.config
    try:
        row, repeat = record_purchase(
            session,
            config,
            merchant_id=merchant_id,
            purchase_date=_day(body.purchase_date, config, "The purchase date"),
            amount_bdt=body.amount_bdt,
            category=body.category,
            supplier_reference=body.supplier_reference,
            invoice_reference=body.invoice_reference,
            actor=user,
            protected_merchants=_protected(services),
        )
    except IntakeRefused as error:
        raise _refused(error, session, user, "purchase", merchant_id) from None
    return _saved(
        services,
        session,
        record_type="purchase",
        record_id=row.purchase_id,
        merchant_id=merchant_id,
        business_date=row.purchase_date,
        repeat=repeat,
    )


@router.post("/merchants/{merchant_id}/deliveries", response_model=RecordSaved, status_code=201)
def new_delivery(
    merchant_id: str,
    body: DeliveryCreate,
    user: CurrentUser = Depends(OFFICER_ONLY),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> RecordSaved:
    """Save one of the shop's own parcels, typed in by staff (not verified)."""
    config = services.config
    dispatched = _moment(body.dispatched_at, "The dispatch time")
    try:
        row, repeat = record_delivery(
            session,
            config,
            merchant_id=merchant_id,
            dispatched_at=dispatched,
            delivered_at=_moment(body.delivered_at, "The delivery time"),
            status=body.status,
            return_reason=body.return_reason,
            is_cod=body.is_cod,
            cod_remitted_on_time=body.cod_remitted_on_time,
            parcel_reference=body.parcel_reference,
            actor=user,
            protected_merchants=_protected(services),
        )
    except IntakeRefused as error:
        raise _refused(error, session, user, "delivery", merchant_id) from None
    return _saved(
        services,
        session,
        record_type="delivery",
        record_id=row.delivery_id,
        merchant_id=merchant_id,
        business_date=row.dispatched_at.date(),
        repeat=repeat,
    )


@router.post("/merchants/{merchant_id}/repayments", response_model=RecordSaved, status_code=201)
def new_repayment(
    merchant_id: str,
    body: RepaymentCreate,
    user: CurrentUser = Depends(OFFICER_ONLY),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> RecordSaved:
    """Save an instalment of one of the shop's real earlier loans (never an application)."""
    config = services.config
    try:
        row, repeat = record_repayment(
            session,
            config,
            merchant_id=merchant_id,
            loan_id=body.loan_id,
            due_date=_day(body.due_date, config, "The due date"),
            paid_date=_day(body.paid_date, config, "The payment date") if body.paid_date else None,
            amount_due_bdt=body.amount_due_bdt,
            amount_paid_bdt=body.amount_paid_bdt,
            actor=user,
            protected_merchants=_protected(services),
        )
    except IntakeRefused as error:
        raise _refused(error, session, user, "repayment", merchant_id) from None
    return _saved(
        services,
        session,
        record_type="payment",
        record_id=row.payment_id,
        merchant_id=merchant_id,
        business_date=row.paid_date or row.due_date,
        repeat=repeat,
    )


@router.post("/merchants/{merchant_id}/visits", response_model=RecordSaved, status_code=201)
def new_visit(
    merchant_id: str,
    body: VisitCreate,
    user: CurrentUser = Depends(OFFICER_ONLY),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> RecordSaved:
    """Save a field visit. A visit never changes a score."""
    config = services.config
    try:
        visit = record_visit(
            session,
            config,
            merchant_id=merchant_id,
            business_date=_day(body.business_date, config, "The visit date"),
            outcome=body.outcome,
            note=body.note,
            actor=user,
            protected_merchants=_protected(services),
        )
    except IntakeRefused as error:
        raise _refused(error, session, user, "visit", merchant_id) from None
    return _saved(
        services,
        session,
        record_type="visit",
        record_id=visit.visit_id,
        merchant_id=merchant_id,
        business_date=visit.business_date,
        repeat=False,
    )


@router.post("/merchants/{merchant_id}/application", response_model=RecordSaved, status_code=201)
def new_application(
    merchant_id: str,
    body: ApplicationCreate,
    user: CurrentUser = Depends(OFFICER_ONLY),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> RecordSaved:
    """Create the merchant's one application and assess it with the saved model.

    The answer says separately that the application was saved and whether the assessment
    was refreshed. Nothing is approved or issued.
    """
    config = services.config
    try:
        application = create_application(
            session,
            config,
            merchant_id=merchant_id,
            requested_amount_bdt=body.requested_amount_bdt,
            purpose=body.purpose,
            purpose_note=body.purpose_note,
            business_date=_day(body.business_date, config, "The application date"),
            actor=user,
            protected_merchants=_protected(services),
        )
    except IntakeRefused as error:
        raise _refused(error, session, user, "application", merchant_id) from None
    return _saved(
        services,
        session,
        record_type="application",
        record_id=application.application_id,
        merchant_id=merchant_id,
        business_date=application.business_date,
        repeat=False,
    )


# --- reads ------------------------------------------------------------------------------


@router.get("/merchants/{merchant_id}/application", response_model=ApplicationOut)
def merchant_application(
    merchant_id: str,
    user: CurrentUser = Depends(ANY_ROLE),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ApplicationOut:
    """The merchant's application and whether its assessment is current. Audited."""
    refuse_rows_not_shown(services.config)
    _merchant(session, merchant_id)
    application = session.scalar(
        select(db.Application).where(db.Application.merchant_id == merchant_id)
    )
    if application is None:
        raise api_error(404, "no_application", f"{merchant_id} has no application.")
    add_audit(session, user, "view_application", merchant_id)
    session.commit()
    return _application_out(services, application)


@router.get("/merchants/{merchant_id}/loans", response_model=list[MerchantLoan])
def merchant_loans(
    merchant_id: str,
    user: CurrentUser = Depends(ANY_ROLE),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> list[MerchantLoan]:
    """Every loan-shaped row of the merchant, each said plainly: an issued loan or an
    application. Only an issued loan can receive a repayment. Audited."""
    refuse_rows_not_shown(services.config)
    _merchant(session, merchant_id)
    requested = dict(
        session.execute(
            select(db.Application.loan_id, db.Application.requested_amount_bdt).where(
                db.Application.merchant_id == merchant_id
            )
        ).all()
    )
    loans = session.scalars(
        select(db.Loan).where(db.Loan.merchant_id == merchant_id).order_by(db.Loan.issued_at)
    ).all()
    add_audit(session, user, "view_loans", merchant_id)
    session.commit()
    return [
        MerchantLoan(
            loan_id=loan.loan_id,
            kind="application" if loan.loan_id in requested else "loan",
            issued_at=loan.issued_at.isoformat(),
            limit_bdt=None if loan.loan_id in requested else loan.limit_bdt,
            requested_amount_bdt=requested.get(loan.loan_id),
            has_outcome=loan.outcome_label is not None,
            repayment_allowed=loan.loan_id not in requested,
        )
        for loan in loans
    ]


@router.get("/merchants/{merchant_id}/workflow", response_model=WorkflowStatus)
def merchant_workflow(
    merchant_id: str,
    user: CurrentUser = Depends(ANY_ROLE),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> WorkflowStatus:
    """Where the merchant is in the field workflow, from the saved records. Audited."""
    refuse_rows_not_shown(services.config)
    merchant = _merchant(session, merchant_id)
    status = _workflow(services, session, merchant)
    add_audit(session, user, "view_workflow", merchant_id)
    session.commit()
    return status


# --- Excel purchase import -------------------------------------------------------------------
# The workbook is the raw request body (no form encoding); the choices are query parameters.
# Inspect and preview write nothing; commit works everything out again from the same file.


def _mapping(raw: str) -> dict[str, str | None]:
    try:
        mapping = json.loads(raw)
    except ValueError:
        mapping = None
    if not isinstance(mapping, dict) or not all(
        isinstance(k, str) and (v is None or isinstance(v, str)) for k, v in mapping.items()
    ):
        raise api_error(422, "invalid_mapping", "The column choices could not be read.")
    return {name: mapping.get(name) or None for name in spreadsheet.FIELDS}


def _workbook(services: Services, session: Session, user, merchant_id: str, body: bytes):
    spreadsheet.check_merchant(session, services.config, merchant_id, _protected(services))
    return spreadsheet.read_workbook(body, services.config)


def _plan(services, session, user, merchant_id, body, sheet, mapping, date_order):
    book = _workbook(services, session, user, merchant_id, body)
    plan = spreadsheet.plan_rows(
        session, services.config, merchant_id=merchant_id, workbook=book, sheet_name=sheet,
        mapping=mapping, date_order=date_order,
    )
    return book, plan


def _row_out(row: spreadsheet.PlannedRow) -> ImportRow:
    return ImportRow(
        row_number=row.row_number,
        outcome=row.outcome,
        code=row.code,
        purchase_date=row.purchase_date.isoformat() if row.purchase_date else None,
        amount_bdt=row.amount_bdt,
        category=row.category,
        invoice_reference=row.invoice_reference,
        supplier_reference=row.supplier_reference,
    )


@router.post("/merchants/{merchant_id}/purchase-import/inspect", response_model=ImportInspect)
async def purchase_import_inspect(
    merchant_id: str,
    request: Request,
    user: CurrentUser = Depends(OFFICER_ONLY),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ImportInspect:
    """Read an .xlsx workbook: its sheets, their columns and a suggested mapping. Saves nothing."""
    body = await request.body()

    def run() -> ImportInspect:
        try:
            book = _workbook(services, session, user, merchant_id, body)
        except IntakeRefused as error:
            raise _refused(error, session, user, "purchase_import", merchant_id) from None
        return ImportInspect(
            file_sha256=book.sha256,
            sheets=[
                spreadsheet_sheet(sheet) for sheet in book.sheets.values() if sheet.header
            ],
            fields=list(spreadsheet.FIELDS),
            required=list(spreadsheet.REQUIRED),
        )

    return await run_in_threadpool(run)


def spreadsheet_sheet(sheet: spreadsheet.Sheet) -> ImportSheet:
    return ImportSheet(
        name=sheet.name,
        columns=sheet.header,
        rows=len(sheet.rows),
        truncated=sheet.truncated,
        suggested=spreadsheet.suggest_mapping(sheet.header),
    )


@router.post("/merchants/{merchant_id}/purchase-import/preview", response_model=ImportPreview)
async def purchase_import_preview(
    merchant_id: str,
    request: Request,
    sheet: str,
    mapping: str,
    date_order: str = "auto",
    user: CurrentUser = Depends(OFFICER_ONLY),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ImportPreview:
    """What would happen to every row of the chosen sheet. Saves nothing."""
    body = await request.body()
    columns = _mapping(mapping)

    def run() -> ImportPreview:
        try:
            book, plan = _plan(
                services, session, user, merchant_id, body, sheet, columns, date_order
            )
        except IntakeRefused as error:
            raise _refused(error, session, user, "purchase_import", merchant_id) from None
        return ImportPreview(
            preview_token=plan.token,
            file_sha256=book.sha256,
            sheet=sheet,
            date_order=date_order,
            date_order_needed=plan.date_order_needed,
            truncated=plan.truncated,
            counts=plan.counts(),
            rows=[_row_out(r) for r in plan.rows],
        )

    return await run_in_threadpool(run)


@router.post(
    "/merchants/{merchant_id}/purchase-import/commit", response_model=ImportResult, status_code=201
)
async def purchase_import_commit(
    merchant_id: str,
    request: Request,
    sheet: str,
    mapping: str,
    preview_token: str,
    date_order: str = "auto",
    keep_flagged: str = "",
    file_name: str = "workbook.xlsx",
    user: CurrentUser = Depends(OFFICER_ONLY),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ImportResult:
    """Save the previewed rows. Refused when the file or the choices changed since the preview."""
    body = await request.body()
    columns = _mapping(mapping)
    try:
        keep = {int(n) for n in keep_flagged.split(",") if n.strip()}
    except ValueError:
        raise api_error(422, "invalid_rows", "The rows to keep could not be read.") from None

    def run() -> ImportResult:
        try:
            book, plan = _plan(
                services, session, user, merchant_id, body, sheet, columns, date_order
            )
            if plan.token != preview_token:
                raise IntakeRefused(
                    409,
                    "preview_changed",
                    "The file or the choices changed since the preview. Preview again.",
                )
            batch = spreadsheet.commit_rows(
                session, services.config, merchant_id=merchant_id, plan=plan,
                keep_flagged=keep, file_name=file_name, file_sha=book.sha256, sheet_name=sheet,
                actor=user,
            )
        except IntakeRefused as error:
            raise _refused(error, session, user, "purchase_import", merchant_id) from None
        flagged = plan.counts()["flag"]
        kept = sum(1 for r in plan.rows if r.outcome == "flag" and r.row_number in keep)
        return ImportResult(
            batch_id=batch.batch_id,
            added=batch.rows_added,
            skipped=batch.rows_skipped,
            flagged_kept=kept,
            flagged_left=flagged - kept,
            rejected=batch.rows_rejected,
            assessment=_assessment(services, session, merchant_id),
        )

    return await run_in_threadpool(run)


@router.get("/merchants/{merchant_id}/receipt", response_model=Receipt)
def merchant_receipt(
    merchant_id: str,
    user: CurrentUser = Depends(OFFICER_ONLY),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> Receipt:
    """The shop's data receipt: consent answers and every record entered, how and when.

    Officers only (they hand it to the retailer); audited. Shops created in the app only:
    the benchmark merchants have no entry records to show.
    """
    refuse_rows_not_shown(services.config)
    try:
        merchant = live_merchant(session, merchant_id, _protected(services))
    except IntakeRefused as error:
        raise _refused(error, session, user, "receipt", merchant_id) from None
    result = build_receipt(session, services.config, _summary(session, merchant))
    add_audit(session, user, "view_receipt", merchant_id)
    session.commit()
    return result


def build_review(services: Services, session: Session, merchant_id: str) -> ReviewStatus:
    """The review status of one merchant (no audit entry): shared by the review and the
    applications list. The rules are in src/api/review.py."""
    config = services.config
    scorer = services.scorer
    valid, _ = consent_state(session, merchant_id, services.data_today(session))
    application = session.scalar(
        select(db.Application).where(db.Application.merchant_id == merchant_id)
    )
    band = None
    if not valid:
        assessment = "consent_required"
    elif scorer is not None and merchant_id in scorer.not_updated:
        assessment = "not_updated"
    else:
        try:
            band = scorer.card(merchant_id)["band"] if scorer is not None else None
            assessment = "current" if band is not None else "not_scored"
        except (ConsentRequired, UnknownMerchant):
            assessment = "not_scored"
    evidence = review.evidence_groups(
        session, config, merchant_id, application.loan_id if application else None
    )
    counts = {g.group: g.total for g in evidence}
    checks = review.build_checks(
        config,
        consent_valid=valid,
        assessment=assessment,
        band=band,
        has_application=application is not None,
        visits=counts["visits"],
        deliveries=counts["deliveries"],
    )
    return ReviewStatus(
        merchant_id=merchant_id,
        application=_application_out(services, application) if application else None,
        assessment=assessment,
        readiness=review.readiness(checks, assessment),
        checks=checks,
        evidence=evidence,
        range=review.range_guidance(
            config,
            session,
            merchant_id,
            application,
            assessment,
            band,
            services.data_today(session),
            getattr(session.get(db.Merchant, merchant_id), 'organization_id', None),
        ),
        evidence_requests=review.evidence_requests(
            session, config, merchant_id, application is not None
        ),
    )


@router.get("/merchants/{merchant_id}/review", response_model=ReviewStatus)
def merchant_review(
    merchant_id: str,
    user: CurrentUser = Depends(ANY_ROLE),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ReviewStatus:
    """The officer workspace: review readiness, evidence with provenance, range guidance.

    Audited. The rules are in src/api/review.py; none of them reads the score's level.
    """
    refuse_rows_not_shown(services.config)
    _merchant(session, merchant_id)
    status = build_review(services, session, merchant_id)
    add_audit(session, user, "view_review", merchant_id)
    session.commit()
    return status


@router.get("/field/shops", response_model=list[WorkflowStatus])
def field_shops(
    limit: int = Query(default=30, ge=1, le=100),
    user: CurrentUser = Depends(ANY_ROLE),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> list[WorkflowStatus]:
    """The shops created in the app, newest first, each with its next step. Audited."""
    refuse_rows_not_shown(services.config)
    rows = session.execute(
        select(db.Merchant)
        .join(db.MerchantProfile, db.MerchantProfile.merchant_id == db.Merchant.merchant_id)
        .where(merchant_scope(session, user, services.config))
        .order_by(db.MerchantProfile.entered_at.desc(), db.Merchant.merchant_id.desc())
        .limit(limit)
    ).scalars().all()
    shops = [_workflow(services, session, merchant) for merchant in rows]
    add_audit(session, user, "view_field_shops")
    session.commit()
    return shops


def _workflow(services: Services, session: Session, merchant: db.Merchant) -> WorkflowStatus:
    """The workflow status of one merchant, from the saved records (no audit entry)."""
    merchant_id = merchant.merchant_id
    valid, categories = consent_state(session, merchant_id, calendar_end(services.config))
    refused = session.scalar(
        select(func.count())
        .select_from(db.ConsentEvent)
        .where(db.ConsentEvent.merchant_id == merchant_id, db.ConsentEvent.response == "refused")
    )

    def count(model) -> int:
        return session.scalar(
            select(func.count()).select_from(model).where(model.merchant_id == merchant_id)
        )

    application = session.scalar(
        select(db.Application).where(db.Application.merchant_id == merchant_id)
    )
    records = {
        "purchases": count(db.Purchase),
        "deliveries": count(db.Delivery),
        "repayments": count(db.Payment),
        "visits": count(db.Visit),
    }
    if not valid:
        next_step = "record_consent"
    elif application is not None:
        next_step = "await_review"
    elif not any(records.values()):
        next_step = "add_records"
    else:
        next_step = "create_application"
    profile = session.get(db.MerchantProfile, merchant_id)
    return WorkflowStatus(
        merchant=_summary(session, merchant),
        consent="valid" if valid else ("refused" if refused else "none"),
        consent_categories=sorted(categories),
        records=records,
        application=_application_out(services, application) if application else None,
        next_step=next_step,
        created_at=profile.entered_at.isoformat(timespec="seconds") if profile else None,
        calendar_end=services.config["demo"]["calendar_end"],
    )
