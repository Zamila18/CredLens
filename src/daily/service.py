"""The FSR's daily sheet: save drafts, submit, correct, return, accept.

Purpose: the everyday evidence of a shop. An FSR keeps one sheet per shop per day, with as many rows
    as the day had events (purchases, sales, payments, deliveries, ...). Drafts can be edited
    freely and never influence a score. Submitting freezes the rows; a later correction is a new
    row that supersedes the old one, with a written reason. Submitted purchases, deliveries and
    loan repayments are also written to the records the assessment reads; sales, expenses, credit
    sales, supplier payments and stock counts are kept and shown but never scored.
Owner role: D (full-stack).
Implements: Phase 4 of the unified platform plan (section 12).

Which columns each kind of row uses is `daily.entry_types` in config/default.yaml.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.auth import CurrentUser, add_audit
from src.api.importer import DELIVERY_STATUSES
from src.db import models as db
from src.intake import records
from src.intake.consent import consent_state
from src.intake.policy import IntakeRefused, calendar_end, utc_now
from src.intake.records import RETURN_REASONS

FIELDS = (
    "txn_date",
    "category",
    "description",
    "quantity",
    "unit",
    "unit_price",
    "amount_bdt",
    "counterparty",
    "payment_method",
    "payment_status",
    "due_date",
    "note",
)
DATES = ("txn_date", "due_date")
NUMBERS = ("quantity", "unit_price", "amount_bdt")
TEXT_MAX = {
    "category": 64,
    "description": 200,
    "unit": 24,
    "counterparty": 80,
    "payment_method": 24,
    "payment_status": 24,
    "note": 300,
}
LOCKED = ("submitted", "accepted")


def entry_types(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return config["daily"]["entry_types"]


def _refuse(status: int, code: str, message: str, **facts: Any) -> IntakeRefused:
    return IntakeRefused(status, code, message, **facts)


def parse_row(
    config: dict[str, Any], raw: dict[str, Any], *, strict: bool, today: date
) -> tuple[dict[str, Any], dict[str, str]]:
    """(clean values, errors by field) for one row. A draft may be incomplete (not strict); a
    row being submitted must have everything its kind requires."""
    kind = raw.get("entry_type")
    spec = entry_types(config).get(kind)
    errors: dict[str, str] = {}
    if spec is None:
        return {}, {"entry_type": "Choose what kind of row this is."}
    out: dict[str, Any] = {}
    for key in FIELDS:
        value = raw.get(key)
        if key not in spec["fields"]:
            if value not in (None, ""):
                errors[key] = "This column is not used for this kind of row."
            continue
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        if key in DATES:
            try:
                day = value if isinstance(value, date) else date.fromisoformat(str(value).strip())
            except ValueError:
                errors[key] = "Write the date as YYYY-MM-DD."
                continue
            if day > today:
                errors[key] = "A record cannot be dated in the future."
            out[key] = day
        elif key in NUMBERS:
            try:
                number = float(str(value).replace(",", "").strip())
            except ValueError:
                errors[key] = "Write a number."
                continue
            if number < 0 or number != number:
                errors[key] = "Use a number of 0 or more."
            elif key in ("amount_bdt", "unit_price") and number > 1e9:
                errors[key] = "This amount is too large to be right."
            out[key] = number
        else:
            text = str(value).strip()
            if len(text) > TEXT_MAX[key]:
                errors[key] = f"Use at most {TEXT_MAX[key]} characters."
            out[key] = text
    if "quantity" in out and "unit_price" in out and "amount_bdt" not in out:
        out["amount_bdt"] = round(out["quantity"] * out["unit_price"], 2)  # a total, worked out
    if kind == "delivery":
        if out.get("category") and out["category"] not in DELIVERY_STATUSES:
            errors["category"] = f"Use one of: {', '.join(DELIVERY_STATUSES)}."
        if out.get("payment_method") and out["payment_method"] not in ("cod", "prepaid"):
            errors["payment_method"] = "Use cod or prepaid."
        if out.get("payment_status") and out["payment_status"] not in ("on_time", "late"):
            errors["payment_status"] = "Use on_time or late."
        if out.get("description") and out["description"] not in RETURN_REASONS:
            errors["description"] = f"Use one of: {', '.join(RETURN_REASONS)}."
    if strict:
        for key in spec["required"]:
            if key not in out and key not in errors:
                errors[key] = "This is required."
        if "amount_bdt" in out and out["amount_bdt"] <= 0 and "amount_bdt" not in errors:
            errors["amount_bdt"] = "The amount must be more than 0."
    return out, errors


def get_sheet(
    session: Session, org_id: str, merchant_id: str, day: date, user: CurrentUser, create: bool
) -> db.DailySheet | None:
    sheet = session.scalar(
        select(db.DailySheet).where(
            db.DailySheet.merchant_id == merchant_id, db.DailySheet.business_date == day
        )
    )
    if sheet is None and create:
        stamp = utc_now()
        sheet = db.DailySheet(
            sheet_id=f"SH-{uuid.uuid4().hex[:24]}",
            organization_id=org_id,
            merchant_id=merchant_id,
            business_date=day,
            fsr_user_id=user.user_id,
            status="draft",
            created_at=stamp,
            updated_at=stamp,
        )
        session.add(sheet)
        session.flush()
    return sheet


def _entries(session: Session, sheet_id: str, status: str | None = None) -> list[db.DailyEntry]:
    query = select(db.DailyEntry).where(db.DailyEntry.sheet_id == sheet_id)
    if status:
        query = query.where(db.DailyEntry.status == status)
    return list(session.scalars(query.order_by(db.DailyEntry.row_no, db.DailyEntry.created_at)))


def save_drafts(
    session: Session,
    config: dict[str, Any],
    user: CurrentUser,
    sheet: db.DailySheet,
    rows: list[dict[str, Any]],
    *,
    delete_missing: bool,
    source: str = "typed",
) -> tuple[list[db.DailyEntry], dict[str, dict[str, str]]]:
    """Save the draft rows of a sheet. Returns (the sheet's current drafts, errors by row key:
    the entry id, or `new-<index>` for a row without one). Incomplete rows are saved too, so
    work is never lost; submitting is what requires them complete."""
    today = calendar_end(config)
    if len(rows) > int(config["daily"]["max_rows_per_sheet"]):
        raise _refuse(413, "too_many_rows", "There are too many rows on one sheet.")
    existing = {e.entry_id: e for e in _entries(session, sheet.sheet_id, "draft")}
    errors: dict[str, dict[str, str]] = {}
    seen: set[str] = set()
    stamp = utc_now()
    for index, raw in enumerate(rows):
        entry_id = raw.get("entry_id")
        key = entry_id or f"new-{index}"
        values, problems = parse_row(config, raw, strict=False, today=today)
        if problems:
            errors[key] = problems
        if entry_id:
            entry = existing.get(entry_id)
            if entry is None:
                raise _refuse(
                    409, "not_a_draft", "That row is not a draft any more. Reload the sheet."
                )
        else:
            entry = db.DailyEntry(
                entry_id=f"DE-{uuid.uuid4().hex[:24]}",
                sheet_id=sheet.sheet_id,
                organization_id=sheet.organization_id,
                merchant_id=sheet.merchant_id,
                status="draft",
                source=raw.get("source") or source,
                created_by=user.user_id,
                created_at=stamp,
            )
            session.add(entry)
        seen.add(entry.entry_id)
        entry.row_no, entry.entry_type, entry.updated_at = (
            index + 1,
            raw.get("entry_type") or "purchase",
            stamp,
        )
        for field in FIELDS:
            setattr(entry, field, values.get(field))
        if raw.get("extraction_confidence") is not None:
            entry.extraction_confidence = float(raw["extraction_confidence"])
    if delete_missing:
        for entry_id, entry in existing.items():
            if entry_id not in seen:
                session.delete(entry)
    if sheet.status in LOCKED + ("returned",) and rows:
        sheet.status = "draft"  # new work on a submitted day: it must be submitted again
    sheet.updated_at = stamp
    add_audit(session, user, "save_daily_drafts", sheet.merchant_id)
    session.flush()
    return _entries(session, sheet.sheet_id, "draft"), errors


def _project(
    session: Session,
    config: dict[str, Any],
    user: CurrentUser,
    entry: db.DailyEntry,
    protected: frozenset[str],
) -> str | None:
    """Write a scored kind of row to the record the assessment reads. Returns its id."""
    spec = entry_types(config)[entry.entry_type]
    if not spec["scored"]:
        return None
    try:
        if entry.entry_type == "purchase":
            row, _ = records.record_purchase(
                session,
                config,
                merchant_id=entry.merchant_id,
                purchase_date=entry.txn_date,
                amount_bdt=entry.amount_bdt,
                category=entry.category,
                supplier_reference=entry.counterparty,
                invoice_reference=entry.entry_id,
                actor=user,
                protected_merchants=protected,
            )
            return row.purchase_id
        if entry.entry_type == "delivery":
            delivered = entry.category == "delivered"
            cod = entry.payment_method == "cod"
            row, _ = records.record_delivery(
                session,
                config,
                merchant_id=entry.merchant_id,
                dispatched_at=datetime.combine(entry.txn_date, time(9, 0)),
                delivered_at=datetime.combine(entry.due_date or entry.txn_date, time(15, 0))
                if delivered
                else None,
                status=entry.category,
                return_reason=entry.description
                if entry.category in ("returned", "failed")
                else None,
                is_cod=cod,
                cod_remitted_on_time=(entry.payment_status == "on_time")
                if cod and entry.payment_status
                else None,
                parcel_reference=entry.entry_id,
                actor=user,
                protected_merchants=protected,
            )
            return row.delivery_id
        if entry.entry_type == "loan_repayment":
            row, _ = records.record_repayment(
                session,
                config,
                merchant_id=entry.merchant_id,
                loan_id=entry.counterparty,
                due_date=entry.due_date,
                paid_date=entry.txn_date,
                amount_due_bdt=entry.unit_price,
                amount_paid_bdt=entry.amount_bdt,
                actor=user,
                protected_merchants=protected,
            )
            return row.payment_id
    except IntakeRefused as error:
        if error.code == "duplicate_reference":
            return None  # this row was already written on an earlier try
        raise
    return None


def submit_sheet(
    session: Session,
    config: dict[str, Any],
    user: CurrentUser,
    sheet: db.DailySheet,
    protected: frozenset[str],
) -> db.DailySheet:
    """Submit every draft of the sheet. All rows must be complete and the merchant must have a
    valid consent. Rows are frozen and the scored kinds are written to the assessment's records."""
    today = calendar_end(config)
    drafts = _entries(session, sheet.sheet_id, "draft")
    if not drafts and sheet.status != "returned":
        raise _refuse(409, "nothing_to_submit", "There are no draft rows to submit.")
    problems: dict[str, dict[str, str]] = {}
    clean: dict[str, dict[str, Any]] = {}
    for entry in drafts:
        raw = {"entry_type": entry.entry_type, **{f: getattr(entry, f) for f in FIELDS}}
        values, errors = parse_row(config, raw, strict=True, today=today)
        if errors:
            problems[entry.entry_id] = errors
        clean[entry.entry_id] = values
    if problems:
        raise _refuse(422, "rows_not_complete", "Some rows are not complete.", rows=problems)
    valid, _categories = consent_state(session, sheet.merchant_id, today)
    if not valid:
        raise _refuse(
            403,
            "consent_required",
            "This merchant has no valid consent, so no records can be submitted for them yet.",
        )
    for entry in drafts:
        entry.projected_record_id = _project(session, config, user, entry, protected)
        entry.status, entry.updated_at = "submitted", utc_now()
        session.commit()  # each row stands on its own if a later one is refused
    sheet.status, sheet.submitted_at, sheet.updated_at = "submitted", utc_now(), utc_now()
    sheet.returned_reason = None
    add_audit(session, user, "submit_daily_sheet", sheet.merchant_id)
    session.commit()
    return sheet


def amend_entry(
    session: Session,
    config: dict[str, Any],
    user: CurrentUser,
    entry: db.DailyEntry,
    raw: dict[str, Any],
    reason: str,
) -> db.DailyEntry:
    """Correct a submitted row: a new row supersedes it, with the reason. A purchase that was
    already written to the assessment's records is corrected there too (audited with the old
    and new values); a delivery or repayment must be corrected by a Credit Officer instead."""
    if entry.status != "submitted":
        raise _refuse(409, "not_submitted", "Only a submitted row can be corrected this way.")
    if len((reason or "").strip()) < int(config["daily"]["amend_reason_min_chars"]):
        raise _refuse(422, "reason_needed", "Write why this row is being corrected.")
    if entry.projected_record_id and entry.entry_type != "purchase":
        raise _refuse(
            409,
            "ask_the_officer",
            "This row is part of the records used for the assessment. "
            "Ask the Credit Officer to correct it.",
        )
    values, errors = parse_row(
        config, {"entry_type": entry.entry_type, **raw}, strict=True, today=calendar_end(config)
    )
    if errors:
        raise _refuse(
            422,
            "rows_not_complete",
            "The corrected row is not complete.",
            rows={entry.entry_id: errors},
        )
    stamp = utc_now()
    new = db.DailyEntry(
        entry_id=f"DE-{uuid.uuid4().hex[:24]}",
        sheet_id=entry.sheet_id,
        organization_id=entry.organization_id,
        merchant_id=entry.merchant_id,
        row_no=entry.row_no,
        entry_type=entry.entry_type,
        status="submitted",
        source=entry.source,
        supersedes_entry_id=entry.entry_id,
        amend_reason=reason.strip(),
        projected_record_id=entry.projected_record_id,
        created_by=user.user_id,
        created_at=stamp,
        updated_at=stamp,
    )
    for field in FIELDS:
        setattr(new, field, values.get(field))
    if entry.projected_record_id and entry.entry_type == "purchase":
        row = session.get(db.Purchase, entry.projected_record_id)
        if row is not None:
            before = f"{row.purchase_date} {row.amount_bdt} {row.category}"
            row.purchase_date, row.amount_bdt, row.category = (
                new.txn_date,
                new.amount_bdt,
                new.category,
            )
            add_audit(
                session,
                user,
                f"amend_purchase: {before} -> {new.txn_date} {new.amount_bdt} {new.category}"[:64],
                entry.merchant_id,
            )
    entry.status, entry.updated_at = "superseded", stamp
    session.add(new)
    sheet = session.get(db.DailySheet, entry.sheet_id)
    if sheet is not None and sheet.status == "accepted":
        sheet.status = "submitted"
    add_audit(session, user, "amend_daily_entry", entry.merchant_id)
    session.commit()
    return new


def return_sheet(session: Session, user: CurrentUser, sheet: db.DailySheet, reason: str) -> None:
    if sheet.status not in ("submitted", "accepted"):
        raise _refuse(409, "not_submitted", "Only a submitted sheet can be sent back.")
    if len((reason or "").strip()) < 10:
        raise _refuse(422, "reason_needed", "Write what needs correcting (10 characters or more).")
    sheet.status, sheet.returned_reason, sheet.returned_by = (
        "returned",
        reason.strip(),
        user.user_id,
    )
    sheet.updated_at = utc_now()
    add_audit(session, user, "return_daily_sheet", sheet.merchant_id)
    session.commit()


def accept_sheet(session: Session, user: CurrentUser, sheet: db.DailySheet) -> None:
    if sheet.status != "submitted":
        raise _refuse(409, "not_submitted", "Only a submitted sheet can be accepted.")
    sheet.status, sheet.reviewed_by, sheet.reviewed_at = "accepted", user.user_id, utc_now()
    add_audit(session, user, "accept_daily_sheet", sheet.merchant_id)
    session.commit()


def totals(session: Session, sheet_id: str) -> dict[str, float]:
    """Sum of amounts per kind of row over the sheet's current (not superseded) rows."""
    rows = session.execute(
        select(db.DailyEntry.entry_type, func.coalesce(func.sum(db.DailyEntry.amount_bdt), 0.0))
        .where(db.DailyEntry.sheet_id == sheet_id, db.DailyEntry.status != "superseded")
        .group_by(db.DailyEntry.entry_type)
    ).all()
    return {kind: float(total) for kind, total in rows}
