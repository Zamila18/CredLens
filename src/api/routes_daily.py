"""Daily records, submissions to the Credit Officer, and notifications.

Purpose: the API behind the FSR's spreadsheet-style daily sheet and the Credit Officer's view of
    what comes in each day.
Owner role: D (full-stack).
Implements: Phases 4 and 5 of the unified platform plan (sections 12 and 14).

An FSR reaches only the shops assigned to them (the merchant guard answers 404 for any other
address or id). Drafts never influence a score. Submitting needs a valid consent; correcting a
submitted row creates a new row that supersedes the old one, with a reason.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from src.api.auth import CurrentUser, require_roles
from src.api.common import api_error
from src.api.imported import refresh_scoring
from src.api.schemas import (
    AmendIn,
    DailyDayOut,
    DailyEntryOut,
    DailyListOut,
    DailyRowIn,
    DailySaveIn,
    DailySheetOut,
    EntryTypeOut,
    FsrOverviewOut,
    FsrShopOut,
    ImportTableOut,
    NotificationOut,
    SubmissionOut,
)
from src.api.state import Services, get_services, get_session
from src.api.tenancy import merchant_in_org, merchant_scope, org_of
from src.daily import service as daily
from src.db import models as db
from src.intake.policy import IntakeRefused, calendar_end
from src.notifications import notify_officers, notify_user

router = APIRouter(tags=["daily records"])

WRITERS = require_roles("credit_officer", "fsr")
OFFICER = require_roles("credit_officer")
READERS = require_roles("credit_officer", "auditor", "fsr")
FSR = require_roles("fsr")
ANY_ACCOUNT = require_roles("credit_officer", "auditor", "fsr")


def _refused(error: IntakeRefused):
    return api_error(error.status, error.code, error.message, **error.facts)


def _protected(services: Services) -> frozenset[str]:
    return services.scorer.source_merchant_ids() if services.scorer is not None else frozenset()


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat(timespec="seconds") if hasattr(value, "hour") else value.isoformat()


def _day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise api_error(422, "invalid_date", "The date must be YYYY-MM-DD.") from None


def _entry_out(config: dict[str, Any], e: db.DailyEntry, sheet: db.DailySheet) -> DailyEntryOut:
    spec = daily.entry_types(config).get(e.entry_type, {})
    return DailyEntryOut(
        entry_id=e.entry_id,
        sheet_id=e.sheet_id,
        business_date=sheet.business_date.isoformat(),
        row_no=e.row_no,
        entry_type=e.entry_type,
        status=e.status,
        txn_date=_iso(e.txn_date),
        category=e.category,
        description=e.description,
        quantity=e.quantity,
        unit=e.unit,
        unit_price=e.unit_price,
        amount_bdt=e.amount_bdt,
        counterparty=e.counterparty,
        payment_method=e.payment_method,
        payment_status=e.payment_status,
        due_date=_iso(e.due_date),
        note=e.note,
        source=e.source,
        extraction_confidence=e.extraction_confidence,
        supersedes_entry_id=e.supersedes_entry_id,
        amend_reason=e.amend_reason,
        scored=bool(spec.get("scored")),
        created_by=e.created_by,
    )


def _sheet_out(session: Session, sheet: db.DailySheet) -> DailySheetOut:
    fsr = session.get(db.User, sheet.fsr_user_id)
    counts = dict(
        session.execute(
            select(db.DailyEntry.status, func.count())
            .where(db.DailyEntry.sheet_id == sheet.sheet_id)
            .group_by(db.DailyEntry.status)
        ).all()
    )
    return DailySheetOut(
        sheet_id=sheet.sheet_id,
        merchant_id=sheet.merchant_id,
        business_date=sheet.business_date.isoformat(),
        fsr_user_id=sheet.fsr_user_id,
        fsr_name=fsr.display_name if fsr else None,
        status=sheet.status,
        submitted_at=_iso(sheet.submitted_at),
        returned_reason=sheet.returned_reason,
        drafts=int(counts.get("draft", 0)),
        submitted=int(counts.get("submitted", 0)),
        totals=daily.totals(session, sheet.sheet_id),
    )


def _day_out(
    session: Session,
    config: dict[str, Any],
    sheet: db.DailySheet | None,
    errors: dict[str, dict[str, str]] | None = None,
) -> DailyDayOut:
    if sheet is None:
        return DailyDayOut(sheet=None, entries=[])
    rows = [e for e in daily._entries(session, sheet.sheet_id) if e.status != "superseded"]
    return DailyDayOut(
        sheet=_sheet_out(session, sheet),
        entries=[_entry_out(config, e, sheet) for e in rows],
        errors=errors or {},
    )


@router.get("/daily/entry-types", response_model=list[EntryTypeOut])
def entry_types(
    user: CurrentUser = Depends(ANY_ACCOUNT), services: Services = Depends(get_services)
) -> list[EntryTypeOut]:
    """The kinds of rows a daily sheet has and the columns each one uses (from the config)."""
    return [
        EntryTypeOut(
            key=key,
            en=spec["en"],
            bn=spec["bn"],
            scored=bool(spec["scored"]),
            fields=list(spec["fields"]),
            required=list(spec["required"]),
            labels=dict(spec.get("labels", {})),
        )
        for key, spec in daily.entry_types(services.config).items()
    ]


@router.get("/merchants/{merchant_id}/daily/{business_date}", response_model=DailyDayOut)
def get_day(
    merchant_id: str,
    business_date: str,
    user: CurrentUser = Depends(READERS),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> DailyDayOut:
    """One day's sheet for a shop (none yet: an empty answer)."""
    sheet = daily.get_sheet(
        session, org_of(user, services.config), merchant_id, _day(business_date), user, create=False
    )
    return _day_out(session, services.config, sheet)


@router.put("/merchants/{merchant_id}/daily/{business_date}", response_model=DailyDayOut)
def save_day(
    merchant_id: str,
    business_date: str,
    body: DailySaveIn,
    user: CurrentUser = Depends(WRITERS),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> DailyDayOut:
    """Save the draft rows of a day (also creates the sheet). Incomplete rows are kept; the
    problems of each row come back so the grid can show them."""
    day = _day(business_date)
    if day > calendar_end(services.config):
        raise api_error(422, "date_in_future", "A sheet cannot be for a day that has not come.")
    merchant = session.get(db.Merchant, merchant_id)
    if merchant is None:
        raise api_error(404, "unknown_merchant", f"No merchant {merchant_id!r}.")
    sheet = daily.get_sheet(session, org_of(user, services.config), merchant_id, day, user, True)
    try:
        _drafts, errors = daily.save_drafts(
            session,
            services.config,
            user,
            sheet,
            [r.model_dump() for r in body.rows],
            delete_missing=body.delete_missing,
        )
    except IntakeRefused as error:
        session.rollback()
        raise _refused(error) from None
    session.commit()
    return _day_out(session, services.config, sheet, errors)


@router.post("/merchants/{merchant_id}/daily/{business_date}/submit", response_model=DailyDayOut)
def submit_day(
    merchant_id: str,
    business_date: str,
    user: CurrentUser = Depends(WRITERS),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> DailyDayOut:
    """Submit the day: drafts are frozen and the scored kinds join the assessment records."""
    sheet = daily.get_sheet(
        session, org_of(user, services.config), merchant_id, _day(business_date), user, create=False
    )
    if sheet is None:
        raise api_error(404, "no_sheet", "There is no sheet for that day.")
    try:
        daily.submit_sheet(session, services.config, user, sheet, _protected(services))
    except IntakeRefused as error:
        session.rollback()
        raise _refused(error) from None
    profile = session.get(db.MerchantProfile, merchant_id)
    notify_officers(
        session,
        sheet.organization_id,
        "sheet_submitted",
        f"{user.display_name or 'An FSR'} submitted {sheet.business_date.isoformat()} for "
        f"{profile.shop_name if profile else merchant_id}.",
        f"/app/submissions?sheet={sheet.sheet_id}",
        exclude=user.user_id,
    )
    session.commit()
    refresh_scoring(services, session)
    return _day_out(session, services.config, sheet)


@router.post(
    "/merchants/{merchant_id}/daily/entries/{entry_id}/amend", response_model=DailyEntryOut
)
def amend(
    merchant_id: str,
    entry_id: str,
    body: AmendIn,
    user: CurrentUser = Depends(WRITERS),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> DailyEntryOut:
    """Correct a submitted row. The old row is kept, marked superseded, with the reason."""
    entry = session.get(db.DailyEntry, entry_id)
    if entry is None or entry.merchant_id != merchant_id:
        raise api_error(404, "unknown_entry", "No such row for this shop.")
    raw = body.model_dump(exclude={"reason"}, exclude_unset=True)
    current = {f: getattr(entry, f) for f in daily.FIELDS}
    try:
        new = daily.amend_entry(
            session, services.config, user, entry, {**current, **raw}, body.reason
        )
    except IntakeRefused as error:
        session.rollback()
        raise _refused(error) from None
    refresh_scoring(services, session)
    return _entry_out(services.config, new, session.get(db.DailySheet, new.sheet_id))


def _sheet_for(session, services, user, merchant_id, business_date) -> db.DailySheet:
    sheet = daily.get_sheet(
        session, org_of(user, services.config), merchant_id, _day(business_date), user, create=False
    )
    if sheet is None:
        raise api_error(404, "no_sheet", "There is no sheet for that day.")
    return sheet


@router.post("/merchants/{merchant_id}/daily/{business_date}/return", response_model=DailyDayOut)
def return_day(
    merchant_id: str,
    business_date: str,
    body: dict[str, str],
    user: CurrentUser = Depends(OFFICER),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> DailyDayOut:
    """Send a submitted sheet back to its FSR with a reason."""
    sheet = _sheet_for(session, services, user, merchant_id, business_date)
    try:
        daily.return_sheet(session, user, sheet, body.get("reason", ""))
    except IntakeRefused as error:
        session.rollback()
        raise _refused(error) from None
    profile = session.get(db.MerchantProfile, merchant_id)
    notify_user(
        session,
        sheet.fsr_user_id,
        sheet.organization_id,
        "sheet_returned",
        f"{sheet.business_date.isoformat()} for {profile.shop_name if profile else merchant_id} "
        f"was sent back: {sheet.returned_reason}",
        f"/app/field/shops/{merchant_id}/daily?date={sheet.business_date.isoformat()}",
    )
    session.commit()
    return _day_out(session, services.config, sheet)


@router.post("/merchants/{merchant_id}/daily/{business_date}/accept", response_model=DailyDayOut)
def accept_day(
    merchant_id: str,
    business_date: str,
    user: CurrentUser = Depends(OFFICER),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> DailyDayOut:
    """Mark a submitted sheet as reviewed."""
    sheet = _sheet_for(session, services, user, merchant_id, business_date)
    try:
        daily.accept_sheet(session, user, sheet)
    except IntakeRefused as error:
        session.rollback()
        raise _refused(error) from None
    return _day_out(session, services.config, sheet)


@router.get("/merchants/{merchant_id}/daily", response_model=DailyListOut)
def history(
    merchant_id: str,
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    entry_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=60),
    user: CurrentUser = Depends(READERS),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> DailyListOut:
    """A shop's daily records over time: sheets and rows, filtered (default: the last 30 days)."""
    end = _day(date_to) if date_to else calendar_end(services.config)
    start = _day(date_from) if date_from else end - timedelta(days=30)
    sheets = session.scalars(
        select(db.DailySheet)
        .where(
            db.DailySheet.merchant_id == merchant_id,
            db.DailySheet.business_date >= start,
            db.DailySheet.business_date <= end,
        )
        .order_by(db.DailySheet.business_date.desc())
    ).all()
    by_id = {s.sheet_id: s for s in sheets}
    query = select(db.DailyEntry).where(db.DailyEntry.sheet_id.in_(list(by_id) or [""]))
    if entry_type:
        query = query.where(db.DailyEntry.entry_type == entry_type)
    if status:
        query = query.where(db.DailyEntry.status == status)
    if q:
        like = f"%{q}%"
        query = query.where(
            or_(
                db.DailyEntry.description.ilike(like),
                db.DailyEntry.counterparty.ilike(like),
                db.DailyEntry.category.ilike(like),
                db.DailyEntry.note.ilike(like),
            )
        )
    rows = session.scalars(query.order_by(db.DailyEntry.created_at.desc()).limit(1000)).all()
    return DailyListOut(
        sheets=[_sheet_out(session, s) for s in sheets],
        entries=[_entry_out(services.config, e, by_id[e.sheet_id]) for e in rows],
    )


# --- the Credit Officer's view of what comes in ----------------------------------------


@router.get("/submissions", response_model=list[SubmissionOut])
def submissions(
    status: str | None = Query(default=None),
    fsr: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    user: CurrentUser = Depends(require_roles("credit_officer", "auditor")),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> list[SubmissionOut]:
    """Daily sheets across the company, newest first."""
    org = org_of(user, services.config)
    query = (
        select(db.DailySheet)
        .join(db.Merchant, db.Merchant.merchant_id == db.DailySheet.merchant_id)
        .where(merchant_in_org(org, services.config))
    )
    if status:
        query = query.where(db.DailySheet.status == status)
    if fsr:
        query = query.where(db.DailySheet.fsr_user_id == fsr)
    if date_from:
        query = query.where(db.DailySheet.business_date >= _day(date_from))
    sheets = session.scalars(
        query.order_by(db.DailySheet.business_date.desc(), db.DailySheet.updated_at.desc()).limit(
            limit
        )
    ).all()
    out = []
    for sheet in sheets:
        info = _sheet_out(session, sheet)
        profile = session.get(db.MerchantProfile, sheet.merchant_id)
        out.append(
            SubmissionOut(
                sheet_id=sheet.sheet_id,
                merchant_id=sheet.merchant_id,
                shop_name=profile.shop_name if profile else None,
                business_date=info.business_date,
                fsr_user_id=sheet.fsr_user_id,
                fsr_name=info.fsr_name,
                status=sheet.status,
                rows=info.drafts + info.submitted,
                drafts=info.drafts,
                totals=info.totals,
                submitted_at=info.submitted_at,
                returned_reason=sheet.returned_reason,
            )
        )
    return out


@router.get("/fsr/overview", response_model=FsrOverviewOut)
def fsr_overview(
    user: CurrentUser = Depends(FSR),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> FsrOverviewOut:
    """An FSR's start page: their shops, today's status for each, and what needs attention."""
    today = calendar_end(services.config)
    profile = session.get(db.StaffProfile, user.user_id)
    merchants = session.execute(
        select(db.Merchant, db.MerchantProfile)
        .outerjoin(db.MerchantProfile, db.MerchantProfile.merchant_id == db.Merchant.merchant_id)
        .where(merchant_scope(session, user, services.config))
        .order_by(db.MerchantProfile.shop_name)
    ).all()
    shops = []
    returned = pending = submitted_today = 0
    for merchant, prof in merchants:
        sheets = session.scalars(
            select(db.DailySheet)
            .where(db.DailySheet.merchant_id == merchant.merchant_id)
            .order_by(db.DailySheet.business_date.desc())
            .limit(40)
        ).all()
        todays = next((s for s in sheets if s.business_date == today), None)
        drafts = (
            int(
                session.scalar(
                    select(func.count())
                    .select_from(db.DailyEntry)
                    .where(
                        db.DailyEntry.sheet_id == todays.sheet_id, db.DailyEntry.status == "draft"
                    )
                )
                or 0
            )
            if todays
            else 0
        )
        returned += sum(1 for s in sheets if s.status == "returned")
        pending += drafts
        submitted_today += 1 if todays and todays.status in ("submitted", "accepted") else 0
        last = next((s for s in sheets if s.submitted_at), None)
        shops.append(
            FsrShopOut(
                merchant_id=merchant.merchant_id,
                shop_name=prof.shop_name if prof else None,
                area=prof.area if prof else None,
                district=merchant.district,
                today_status=todays.status if todays else None,
                today_drafts=drafts,
                last_submitted=last.business_date.isoformat() if last else None,
            )
        )
    return FsrOverviewOut(
        territory=profile.territory if profile else None,
        employee_id=profile.employee_id if profile else None,
        today=today.isoformat(),
        shops=shops,
        returned=returned,
        pending_drafts=pending,
        submitted_today=submitted_today,
    )


# --- notifications ----------------------------------------------------------------------


@router.get("/notifications", response_model=list[NotificationOut])
def notifications(
    user: CurrentUser = Depends(ANY_ACCOUNT), session: Session = Depends(get_session)
) -> list[NotificationOut]:
    """The caller's latest notifications (unread first)."""
    rows = session.scalars(
        select(db.Notification)
        .where(db.Notification.user_id == user.user_id)
        .order_by(db.Notification.read_at.is_(None).desc(), db.Notification.created_at.desc())
        .limit(40)
    ).all()
    return [
        NotificationOut(
            notification_id=n.notification_id,
            kind=n.kind,
            text=n.text,
            link=n.link,
            created_at=_iso(n.created_at),
            read=n.read_at is not None,
        )
        for n in rows
    ]


@router.post("/notifications/read-all", status_code=204)
def read_all(
    user: CurrentUser = Depends(ANY_ACCOUNT), session: Session = Depends(get_session)
) -> None:
    from src.accounts.service import now

    for n in session.scalars(
        select(db.Notification).where(
            db.Notification.user_id == user.user_id, db.Notification.read_at.is_(None)
        )
    ):
        n.read_at = now()
    session.commit()


_ = DailyRowIn


# --- importing a day's figures from a file -----------------------------------------------

UPLOAD_ANY = {
    "requestBody": {
        "required": True,
        "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
    }
}


def _table_out(job: db.ExtractionJob, config: dict[str, Any], entry_type: str) -> ImportTableOut:
    from src.daily import imports

    if job.status != "done" or not job.result:
        return ImportTableOut(job_id=job.job_id, status=job.status, error=job.error)
    data = json.loads(job.result)
    allowed = list(daily.entry_types(config)[entry_type]["fields"])
    return ImportTableOut(
        job_id=job.job_id,
        status="done",
        method=data["method"],
        headers=data["headers"],
        rows=data["rows"],
        confidences=data["confidences"],
        notes=data["notes"],
        suggested_mapping=imports.suggest_mapping(data["headers"], allowed),
    )


def _image_mime(body: bytes) -> str:
    return "image/jpeg" if body.startswith(b"\xff\xd8") else "image/png"


@router.post(
    "/merchants/{merchant_id}/daily-import",
    response_model=ImportTableOut,
    status_code=201,
    openapi_extra=UPLOAD_ANY,
)
async def import_upload(
    merchant_id: str,
    request: Request,
    name: str = Query(default="file"),
    entry_type: str = Query(default="purchase"),
    user: CurrentUser = Depends(WRITERS),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ImportTableOut:
    """Upload a file of daily figures. CSV, Excel and Word tables and PDFs with text are read at
    once; a photo or a scanned PDF is read by the background worker (poll the job). Nothing is
    saved as a record: the FSR maps, corrects and loads the rows as draft rows."""
    from starlette.concurrency import run_in_threadpool

    from src.accounts.service import now
    from src.api.uploads import archive_limits, check_archive, read_capped
    from src.daily import imports
    from src.onboarding.registrations import store_document

    if entry_type not in daily.entry_types(services.config):
        raise api_error(422, "invalid_choice", "Unknown kind of row.")
    limit = int(services.config["registration"]["signed_max_mb"]) * 1024 * 1024 * 2
    body = await read_capped(request, limit)
    kind = imports.kind_of(name, body)
    if kind is None:
        raise api_error(415, "file_type_not_allowed", "Upload a CSV, Excel, Word, PDF or a photo.")
    if kind in ("xlsx", "docx"):
        try:
            check_archive(body, *archive_limits(services.config))
        except ValueError as error:
            raise api_error(422, "archive_refused", str(error)) from None
    org = org_of(user, services.config)
    job = db.ExtractionJob(
        job_id=f"XJ-{uuid.uuid4().hex[:24]}",
        document_id=None,
        organization_id=org,
        merchant_id=merchant_id,
        purpose="table",
        status="queued",
        queued_at=now(),
    )
    if kind in ("pdf", "image"):
        mime = "application/pdf" if kind == "pdf" else _image_mime(body)
        doc = store_document(
            session,
            services.config,
            user,
            org,
            body,
            kind="import",
            original_name=name,
            merchant_id=merchant_id,
            registration_id=None,
        )
        job.document_id = doc.document_id
        if imports.needs_ocr(body, mime):
            session.add(job)
            session.commit()
            return _table_out(job, services.config, entry_type)
        reader = lambda data: imports.from_document(  # noqa: E731
            data, mime, None, float(services.config["ocr"]["render_scale"])
        )
    else:
        reader = {"csv": imports.from_csv, "xlsx": imports.from_xlsx, "docx": imports.from_docx}[
            kind
        ]
    try:
        table = await run_in_threadpool(reader, body)
    except Exception as error:  # noqa: BLE001 - a broken file is the user's to fix
        session.rollback()
        raise api_error(
            422, "unreadable_file", f"This file could not be read ({type(error).__name__})."
        ) from None
    job.status, job.finished_at = "done", now()
    payload = {
        **table.as_json(),
        "source_name": name[:120],
        "sha256": hashlib.sha256(body).hexdigest(),
    }
    job.result = json.dumps(payload, ensure_ascii=False)
    session.add(job)
    session.commit()
    return _table_out(job, services.config, entry_type)


@router.get("/merchants/{merchant_id}/daily-import/{job_id}", response_model=ImportTableOut)
def import_result(
    merchant_id: str,
    job_id: str,
    entry_type: str = Query(default="purchase"),
    user: CurrentUser = Depends(WRITERS),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ImportTableOut:
    """The state of an import job (and the table, once read)."""
    job = session.get(db.ExtractionJob, job_id)
    if (
        job is None
        or job.merchant_id != merchant_id
        or job.organization_id != org_of(user, services.config)
    ):
        raise api_error(404, "unknown_job", "No such import.")
    return _table_out(job, services.config, entry_type)
