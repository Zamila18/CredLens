"""Read-only lists for the workspace: applications, merchant directory, imports, overview.

Purpose: give each screen a small, server-side answer instead of loading thousands of rows
    into the browser, and give the officers one place to find new applications.
Owner role: D (full-stack).
Implements: product redesign (applications list, merchant directory, import history,
    dashboard overview). Nothing here writes a record; every list is audited like a read.

Rules kept from the rest of the API:
- an application is a request: it is never counted or listed as an issued loan;
- a stale assessment is reported as "not_updated", never as current;
- the review status comes from src/api/review.py and never reads the score's level.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from src.api import quality
from src.api.auth import EVERY_ROLE, READERS, CurrentUser, add_audit, require_roles
from src.api.common import api_error, refuse_rows_not_shown
from src.api.profile import consent_state
from src.api.review import _provenance, connector_record_ids, source_of
from src.api.routes_intake import build_review
from src.api.schemas import (
    ActivityItem,
    ApplicationRow,
    DirectoryPage,
    DirectoryRow,
    EvidenceOverview,
    ImportBatchDetail,
    ImportBatchOut,
    MonthCount,
    OrganizationOut,
    Overview,
    ReviewRecord,
    SourceCount,
)
from src.api.state import Services, get_services, get_session
from src.api.tenancy import merchant_in_org, org_of, organization_out
from src.db import models as db
from src.intake.policy import calendar_end

router = APIRouter(tags=["workspace"])

# Lists and the dashboard: not for a sales representative, who works on assigned shops only.
ANY_ROLE = require_roles(*READERS)
EVERYONE = require_roles(*EVERY_ROLE)
STAFF = require_roles("credit_officer")


def _org_ids(user: CurrentUser, services: Services):
    """A sub-select of the caller's organisation's merchant ids (tenancy.py)."""
    return select(db.Merchant.merchant_id).where(
        merchant_in_org(org_of(user, services.config), services.config)
    )


def _names(session: Session, merchant_ids: set[str]) -> dict[str, db.MerchantProfile]:
    """The app profiles (shop name, area) of the given merchants, by id."""
    if not merchant_ids:
        return {}
    rows = session.scalars(
        select(db.MerchantProfile).where(db.MerchantProfile.merchant_id.in_(merchant_ids))
    )
    return {row.merchant_id: row for row in rows}


def _latest_decisions(session: Session, merchant_ids: set[str]) -> dict[str, db.Decision]:
    latest: dict[str, db.Decision] = {}
    if not merchant_ids:
        return latest
    for row in session.scalars(
        select(db.Decision)
        .where(db.Decision.merchant_id.in_(merchant_ids))
        .order_by(db.Decision.decided_at)
    ):
        latest[row.merchant_id] = row
    return latest


@router.get("/applications", response_model=list[ApplicationRow])
def applications(
    user: CurrentUser = Depends(ANY_ROLE),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> list[ApplicationRow]:
    """Every application, newest first, with its assessment, review status and decision."""
    refuse_rows_not_shown(services.config)
    rows = session.scalars(
        select(db.Application)
        .where(db.Application.merchant_id.in_(_org_ids(user, services)))
        .order_by(db.Application.entered_at.desc())
    ).all()
    ids = {row.merchant_id for row in rows}
    names = _names(session, ids)
    merchants = {
        m.merchant_id: m
        for m in session.scalars(select(db.Merchant).where(db.Merchant.merchant_id.in_(ids)))
    }
    decisions = _latest_decisions(session, ids)
    out = []
    for row in rows:
        status = build_review(services, session, row.merchant_id)
        decided = decisions.get(row.merchant_id)
        if decided is not None and decided.decided_at < row.entered_at:
            decided = None  # a decision made before the application is not about it
        profile = names.get(row.merchant_id)
        out.append(
            ApplicationRow(
                application_id=row.application_id,
                merchant_id=row.merchant_id,
                shop_name=profile.shop_name if profile else None,
                area=profile.area if profile else None,
                district=merchants[row.merchant_id].district,
                requested_amount_bdt=row.requested_amount_bdt,
                purpose=row.purpose,
                business_date=row.business_date.isoformat(),
                entered_at=row.entered_at.isoformat(timespec="seconds"),
                assessment=status.assessment,
                readiness=status.readiness,
                open_checks=sum(1 for c in status.checks if c.kind != "info" and not c.passed),
                decision=decided.officer_action if decided else None,
                decided_at=decided.decided_at.isoformat(timespec="seconds") if decided else None,
            )
        )
    add_audit(session, user, "view_applications")
    session.commit()
    return out


@router.get("/directory/merchants", response_model=DirectoryPage)
def merchant_directory(
    q: str = Query(default="", max_length=80),
    source: str = Query(default="all", pattern="^(all|app|benchmark)$"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(ANY_ROLE),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> DirectoryPage:
    """Merchants, searched by id, shop name, area or district, one page at a time.

    Shops created in the app come first (newest first), then the benchmark merchants by id.
    """
    refuse_rows_not_shown(services.config)
    query = select(db.Merchant, db.MerchantProfile).join(
        db.MerchantProfile,
        db.MerchantProfile.merchant_id == db.Merchant.merchant_id,
        isouter=True,
    )
    query = query.where(merchant_in_org(org_of(user, services.config), services.config))
    words = q.strip()
    if words:
        like = f"%{words}%"
        query = query.where(
            or_(
                db.Merchant.merchant_id.ilike(like),
                db.Merchant.district.ilike(like),
                db.MerchantProfile.shop_name.ilike(like),
                db.MerchantProfile.area.ilike(like),
            )
        )
    if source == "app":
        query = query.where(db.MerchantProfile.merchant_id.is_not(None))
    elif source == "benchmark":
        query = query.where(db.MerchantProfile.merchant_id.is_(None))
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    page = session.execute(
        query.order_by(
            db.MerchantProfile.entered_at.is_(None),
            db.MerchantProfile.entered_at.desc(),
            db.Merchant.merchant_id,
        )
        .limit(limit)
        .offset(offset)
    ).all()
    as_of = services.data_today(session)
    ids = {merchant.merchant_id for merchant, _ in page}
    with_application = set(
        session.scalars(
            select(db.Application.merchant_id).where(db.Application.merchant_id.in_(ids))
        )
    )
    refused = set(
        session.scalars(
            select(db.ConsentEvent.merchant_id).where(
                db.ConsentEvent.merchant_id.in_(ids), db.ConsentEvent.response == "refused"
            )
        )
    )
    items = []
    for merchant, profile in page:
        valid, _ = consent_state(session, merchant.merchant_id, as_of)
        consent = "valid" if valid else ("refused" if merchant.merchant_id in refused else "none")
        items.append(
            DirectoryRow(
                merchant_id=merchant.merchant_id,
                shop_name=profile.shop_name if profile else None,
                area=profile.area if profile else None,
                district=merchant.district,
                shop_type=merchant.shop_type,
                created_in_app=profile is not None,
                onboarded_at=merchant.onboarded_at.isoformat(),
                consent=consent,
                has_application=merchant.merchant_id in with_application,
            )
        )
    add_audit(session, user, "view_directory")
    session.commit()
    return DirectoryPage(total=total, offset=offset, limit=limit, items=items)


def _batch_out(batch: db.ImportBatch, names: dict[str, Any]) -> dict[str, Any]:
    profile = names.get(batch.merchant_id)
    return {
        "batch_id": batch.batch_id,
        "merchant_id": batch.merchant_id,
        "shop_name": profile.shop_name if profile else None,
        "record_type": batch.record_type,
        "file_name": batch.file_name,
        "file_sha256": batch.file_sha256,
        "sheet_name": batch.sheet_name,
        "uploaded_at": batch.uploaded_at.isoformat(timespec="seconds"),
        "actor": batch.actor,
        "rows_added": batch.rows_added,
        "rows_skipped": batch.rows_skipped,
        "rows_flagged": batch.rows_flagged,
        "rows_rejected": batch.rows_rejected,
        "status": batch.status,
    }


@router.get("/import-batches", response_model=list[ImportBatchOut])
def import_batches(
    merchant_id: str | None = None,
    user: CurrentUser = Depends(STAFF),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> list[ImportBatchOut]:
    """Every spreadsheet import of the caller's organisation, newest first."""
    query = (
        select(db.ImportBatch)
        .where(db.ImportBatch.merchant_id.in_(_org_ids(user, services)))
        .order_by(db.ImportBatch.uploaded_at.desc())
    )
    if merchant_id:
        query = query.where(db.ImportBatch.merchant_id == merchant_id)
    batches = session.scalars(query).all()
    names = _names(session, {b.merchant_id for b in batches if b.merchant_id})
    add_audit(session, user, "view_import_batches", merchant_id)
    session.commit()
    return [ImportBatchOut(**_batch_out(b, names)) for b in batches]


@router.get("/import-batches/{batch_id}", response_model=ImportBatchDetail)
def import_batch(
    batch_id: str,
    user: CurrentUser = Depends(STAFF),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ImportBatchDetail:
    """One import and the purchases it saved, each with what is known about it."""
    batch = session.get(db.ImportBatch, batch_id)
    owner = session.get(db.Merchant, batch.merchant_id) if batch and batch.merchant_id else None
    org = org_of(user, services.config)
    default = services.config["organization"]["id"]
    if owner is not None and (owner.organization_id or default) != org:
        batch = None  # another organisation's import: the same answer as none
    if batch is None:
        raise api_error(404, "unknown_batch", f"No import {batch_id!r}.")
    names = _names(session, {batch.merchant_id} if batch.merchant_id else set())
    known = _provenance(session, batch.merchant_id) if batch.merchant_id else {}
    saved = [row for (kind, _), row in known.items() if row.batch_id == batch_id]
    records = []
    for row in sorted(saved, key=lambda r: r.business_date or r.entered_at.date()):
        purchase = session.get(db.Purchase, row.record_id)
        if purchase is None:
            continue
        records.append(
            ReviewRecord(
                record_type="purchase",
                business_date=purchase.purchase_date.isoformat(),
                amount_bdt=purchase.amount_bdt,
                detail=purchase.category,
                entry_method=row.entry_method,
                status=row.status,
                entered_at=row.entered_at.isoformat(timespec="seconds"),
                entered_by=row.actor,
                simulated=row.simulated,
            )
        )
    add_audit(session, user, "view_import_batch", batch.merchant_id)
    session.commit()
    return ImportBatchDetail(**_batch_out(batch, names), records=records)


@router.get("/overview", response_model=Overview)
def overview(
    user: CurrentUser = Depends(ANY_ROLE),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> Overview:
    """Counts and the latest activity for the dashboard, all counted from the database."""
    refuse_rows_not_shown(services.config)

    ids = _org_ids(user, services)

    def count(model, *where) -> int:
        return session.scalar(
            select(func.count()).select_from(model).where(model.merchant_id.in_(ids), *where)
        )

    application_loans = select(db.Application.loan_id)
    applications_list = session.scalars(
        select(db.Application).where(db.Application.merchant_id.in_(ids))
    ).all()
    decisions = _latest_decisions(session, {a.merchant_id for a in applications_list})
    awaiting = sum(
        1
        for a in applications_list
        if a.merchant_id not in decisions or decisions[a.merchant_id].decided_at < a.entered_at
    )
    scorer = services.scorer
    recent_records = session.scalars(
        select(db.RecordProvenance)
        .where(
            db.RecordProvenance.record_type != "consent",
            db.RecordProvenance.merchant_id.in_(ids),
        )
        .order_by(db.RecordProvenance.entered_at.desc())
        .limit(12)
    ).all()
    recent_decisions = session.scalars(
        select(db.Decision)
        .where(db.Decision.merchant_id.in_(ids))
        .order_by(db.Decision.decided_at.desc())
        .limit(12)
    ).all()
    names = _names(
        session,
        {r.merchant_id for r in recent_records} | {d.merchant_id for d in recent_decisions},
    )

    def name(merchant_id: str) -> str | None:
        profile = names.get(merchant_id)
        return profile.shop_name if profile else None

    events = [
        ActivityItem(
            kind="record",
            record_type=r.record_type,
            merchant_id=r.merchant_id,
            shop_name=name(r.merchant_id),
            actor=r.actor,
            at=r.entered_at.isoformat(timespec="seconds"),
            business_date=r.business_date.isoformat() if r.business_date else None,
            entry_method=r.entry_method,
        )
        for r in recent_records
    ] + [
        ActivityItem(
            kind="decision",
            merchant_id=d.merchant_id,
            shop_name=name(d.merchant_id),
            actor=d.officer_id,
            at=d.decided_at.isoformat(timespec="seconds"),
            officer_action=d.officer_action,
        )
        for d in recent_decisions
    ]
    events.sort(key=lambda e: e.at, reverse=True)
    org = org_of(user, services.config)
    reg = db.MerchantRegistration

    def registrations(*statuses: str) -> int:
        return int(
            session.scalar(
                select(func.count())
                .select_from(reg)
                .where(reg.organization_id == org, reg.status.in_(statuses))
            )
            or 0
        )

    def fsr_count(*, active_only: bool) -> int:
        query = (
            select(func.count())
            .select_from(db.Membership)
            .where(db.Membership.organization_id == org, db.Membership.role == "fsr")
        )
        if active_only:
            query = query.where(db.Membership.status == "active")
        return int(session.scalar(query) or 0)

    assigned = select(db.ShopAssignment.merchant_id).where(
        db.ShopAssignment.organization_id == org, db.ShopAssignment.ended_at.is_(None)
    )
    today = calendar_end(services.config)

    def sheets(*where) -> int:
        return int(
            session.scalar(
                select(func.count())
                .select_from(db.DailySheet)
                .where(db.DailySheet.merchant_id.in_(ids), *where)
            )
            or 0
        )

    result = Overview(
        registrations_open=registrations("draft", "form_issued", "needs_correction"),
        documents_to_review=registrations("signed_uploaded", "under_review"),
        fsrs_total=fsr_count(active_only=False),
        fsrs_active=fsr_count(active_only=True),
        merchants_unassigned=int(
            session.scalar(
                select(func.count())
                .select_from(db.Merchant)
                .where(db.Merchant.merchant_id.in_(ids), db.Merchant.merchant_id.not_in(assigned))
            )
            or 0
        ),
        submissions_today=sheets(
            db.DailySheet.business_date == today,
            db.DailySheet.status.in_(("submitted", "accepted")),
        ),
        sheets_returned=sheets(db.DailySheet.status == "returned"),
        sheets_with_drafts=sheets(db.DailySheet.status == "draft"),
        merchants_total=count(db.Merchant),
        shops_created_in_app=count(db.MerchantProfile),
        applications_total=len(applications_list),
        applications_awaiting_decision=awaiting,
        assessments_not_updated=len(
            set(getattr(scorer, "not_updated", {}) or {}) & set(session.scalars(ids))
        ),
        issued_loans=count(db.Loan, db.Loan.loan_id.not_in(application_loans)),
        repayments=count(db.Payment),
        decisions_total=count(db.Decision),
        import_batches=count(db.ImportBatch),
        calendar_end=services.config["demo"]["calendar_end"],
        recent=events[:12],
        evidence=_evidence_overview(session, services, user),
    )
    add_audit(session, user, "view_overview")
    session.commit()
    return result


MONTHS_SHOWN = 6


def _evidence_overview(session: Session, services: Services, user: CurrentUser) -> EvidenceOverview:
    """Which evidence the shops added in the app have, and where it came from.

    Counted from the records and their entry (provenance) rows; a record saved by a data
    source is counted as "data_source" (its lineage row says so). Repayments count only
    payments on issued loans: an application never has a repayment.
    """
    config = services.config
    org = org_of(user, config)
    scope = merchant_in_org(org, config)
    shops = list(
        session.scalars(
            select(db.MerchantProfile.merchant_id)
            .join(db.Merchant, db.Merchant.merchant_id == db.MerchantProfile.merchant_id)
            .where(scope)
        )
    )
    end = calendar_end(config)

    def having(model, *where) -> int:
        if not shops:
            return 0
        query = select(func.count(func.distinct(model.merchant_id))).where(
            model.merchant_id.in_(shops), *where
        )
        return session.scalar(query)

    coverage = {
        "consent": sum(consent_state(session, m, end)[0] for m in shops),
        "purchases": having(db.Purchase),
        "deliveries": having(db.Delivery),
        "repayments": having(db.Payment, db.Payment.loan_id.not_in(select(db.Application.loan_id))),
        "visits": having(db.Visit),
        "application": having(db.Application),
    }

    latest: dict[tuple[str, str], db.RecordProvenance] = {}
    if shops:
        for row in session.scalars(
            select(db.RecordProvenance)
            .where(db.RecordProvenance.merchant_id.in_(shops))
            .where(
                db.RecordProvenance.record_type.in_(("purchase", "delivery", "payment", "visit"))
            )
            .order_by(db.RecordProvenance.provenance_id)
        ):
            latest[(row.record_type, row.record_id)] = row
    from_source = connector_record_ids(session, {record_id for _, record_id in latest})
    first_month = date(end.year, end.month, 1)
    for _ in range(MONTHS_SHOWN - 1):
        first_month = (first_month - timedelta(days=1)).replace(day=1)
    by_source: dict[tuple[str, str], int] = {}
    by_month: dict[tuple[str, str], int] = {}
    for (record_type, record_id), row in latest.items():
        source = source_of(row, record_id in from_source)
        by_source[(record_type, source)] = by_source.get((record_type, source), 0) + 1
        if row.business_date and first_month <= row.business_date <= end:
            month = row.business_date.strftime("%Y-%m")
            by_month[(month, source)] = by_month.get((month, source), 0) + 1

    open_, concerns, by_group = quality.summary(session, config, org, scope)
    return EvidenceOverview(
        app_shops=len(shops),
        coverage=coverage,
        by_source=[
            SourceCount(record_type=t, source=src, records=n)
            for (t, src), n in sorted(by_source.items())
        ],
        by_month=[
            MonthCount(month=m, source=src, records=n) for (m, src), n in sorted(by_month.items())
        ],
        quality_open=open_,
        quality_concerns=concerns,
        quality_by_group=by_group,
    )


@router.get("/organization", response_model=OrganizationOut)
def organization(
    user: CurrentUser = Depends(EVERYONE),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> OrganizationOut:
    """The caller's organisation: name, environment, country, languages, currency, timezone."""
    org = org_of(user, services.config)
    return OrganizationOut(**organization_out(session, services.config, org))
