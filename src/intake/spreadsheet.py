"""Stock purchases from an Excel workbook (.xlsx), for one merchant created in the app.

Purpose: let field staff bring in a shop's purchase sheet without knowing CSV, JSON or the
    data contract's column names. Read the workbook, suggest which column is which, show
    what would happen to every row, and save only after the person confirms.
Owner role: D (full-stack).
Implements: implementation pack, Phase 7 (7.2 to 7.5).

The rules:
- Inspecting and previewing write nothing. The workbook itself is never stored, only its
  SHA-256 fingerprint.
- A preview is bound to the file, the sheet, the column mapping, the date order and the
  merchant (`preview_token`). Commit works the rows out again from the uploaded file and
  refuses when the token no longer matches: the person must preview again.
- A row with an invoice reference gets the same id a typed-in purchase with that reference
  gets, so a paper already entered by hand is recognised. A row without one gets an id from
  the file's fingerprint, the sheet and the row number: uploading the same workbook again
  adds nothing, while a different file with a lookalike row is flagged for a person to
  decide, never dropped silently.
- Saved rows say how they entered (`imported_spreadsheet`, not verified) and which import
  batch brought them. Rows are saved in one transaction, after the same scoring-input check
  as a typed-in record.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import CurrentUser, add_audit
from src.db import models as db
from src.intake.consent import require_consent_for
from src.intake.policy import (
    IntakeRefused,
    add_provenance,
    calendar_end,
    demo,
    live_merchant,
    new_id,
    require_synthetic_mode,
    utc_now,
)
from src.intake.records import CATEGORY_MAX, TEXT_MAX, _id_for, check_scoring_inputs

FIELDS = ("purchase_date", "amount_bdt", "category", "invoice_reference", "supplier_reference")
REQUIRED = ("purchase_date", "amount_bdt")
DATE_ORDERS = ("auto", "dmy", "mdy")

# Headers people write, by field: the contract name first, then common words (lower case,
# spaces and punctuation ignored when comparing).
SYNONYMS: dict[str, tuple[str, ...]] = {
    "purchase_date": ("purchase_date", "date", "purchase date", "invoice date", "bill date",
                      "memo date", "তারিখ", "ক্রয়ের তারিখ"),
    "amount_bdt": ("amount_bdt", "amount", "total", "total amount", "amount (bdt)", "taka",
                   "tk", "bill amount", "net amount", "টাকা", "মোট", "পরিমাণ"),
    "category": ("category", "item", "items", "product", "products", "description", "goods",
                 "পণ্য", "বিবরণ"),
    "invoice_reference": ("invoice_reference", "invoice", "invoice no", "invoice number",
                          "bill no", "bill number", "memo no", "receipt no", "reference", "ref",
                          "চালান নং", "মেমো নং"),
    "supplier_reference": ("supplier_reference", "supplier", "vendor", "wholesaler",
                           "distributor", "company", "সরবরাহকারী"),
}

BANGLA_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
EXCEL_EPOCH = date(1899, 12, 30)


def _key(text: str) -> str:
    return re.sub(r"[\s_\-.:#()]+", " ", text.strip().casefold()).strip()


@dataclass
class Sheet:
    name: str
    header: list[str]
    rows: list[tuple[int, list[Any]]]  # (row number in Excel, values under the header)
    truncated: bool = False


@dataclass
class Workbook:
    sha256: str
    sheets: dict[str, Sheet]


def read_workbook(data: bytes, config: dict[str, Any]) -> Workbook:
    """Every sheet of an .xlsx file: the first non-empty row is the header."""
    from openpyxl import load_workbook

    limits = demo(config)["purchase_import"]
    if not data:
        raise IntakeRefused(422, "empty_file", "The file is empty.")
    if len(data) > limits["max_file_mb"] * 1024 * 1024:
        raise IntakeRefused(
            413, "file_too_large", f"The file is larger than {limits['max_file_mb']} MB."
        )
    try:
        book = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except (zipfile.BadZipFile, KeyError, OSError, ValueError):
        raise IntakeRefused(
            422,
            "not_a_workbook",
            "This is not an Excel workbook (.xlsx). Save the sheet as .xlsx and try again.",
        ) from None
    sheets: dict[str, Sheet] = {}
    try:
        for ws in book.worksheets:
            header: list[str] | None = None
            rows: list[tuple[int, list[Any]]] = []
            truncated = False
            for number, values in enumerate(ws.iter_rows(values_only=True), start=1):
                values = list(values)
                if all(v is None or str(v).strip() == "" for v in values):
                    continue
                if header is None:
                    header = [str(v).strip() if v is not None else "" for v in values]
                    continue
                if len(rows) >= limits["max_rows"]:
                    truncated = True
                    break
                rows.append((number, values + [None] * (len(header) - len(values))))
            sheets[ws.title] = Sheet(ws.title, header or [], rows, truncated)
    finally:
        book.close()
    if not any(s.header for s in sheets.values()):
        raise IntakeRefused(422, "empty_workbook", "The workbook has no rows to read.")
    return Workbook(hashlib.sha256(data).hexdigest(), sheets)


def suggest_mapping(header: list[str]) -> dict[str, str | None]:
    """For each field, the header that looks like it (contract name first), or None."""
    keys = {_key(h): h for h in header if h}
    mapping: dict[str, str | None] = {}
    used: set[str] = set()
    for name in FIELDS:
        found = None
        for word in SYNONYMS[name]:
            column = keys.get(_key(word))
            if column and column not in used:
                found = column
                break
        mapping[name] = found
        if found:
            used.add(found)
    return mapping


def parse_amount(value: Any) -> float | None:
    """Taka from a number or text like '৳ 9,500', 'Tk 9500.00' or '৯৫০০'. None if unreadable."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).translate(BANGLA_DIGITS).casefold()
    text = re.sub(r"(৳|taka|tk\.?|bdt|/-|,|\s)", "", text)
    if not re.fullmatch(r"-?\d+(\.\d+)?", text):
        return None
    return float(text)


def parse_date(value: Any, order: str) -> tuple[date | None, bool]:
    """A date, and whether it is ambiguous (like 03/04/2026) when `order` is 'auto'."""
    if isinstance(value, datetime):
        return value.date(), False
    if isinstance(value, date):
        return value, False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 20000 < value < 80000:  # an Excel day number that was not formatted as a date
            return EXCEL_EPOCH + timedelta(days=int(value)), False
        return None, False
    if value is None:
        return None, False
    text = str(value).translate(BANGLA_DIGITS).strip()
    match = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if match:
        return _make(int(match[1]), int(match[2]), int(match[3])), False
    match = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2}|\d{4})", text)
    if match:
        a, b, year = int(match[1]), int(match[2]), int(match[3])
        year = year + 2000 if year < 100 else year
        if a > 12 or (order == "dmy" and b <= 12):
            return _make(year, b, a), False
        if b > 12 or order == "mdy":
            return _make(year, a, b), False
        if a == b:
            return _make(year, a, b), False
        return None, True
    for pattern in ("%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y", "%d-%b-%Y", "%d-%b-%y"):
        try:
            return datetime.strptime(text.replace(",", ""), pattern).date(), False
        except ValueError:
            continue
    return None, False


def _make(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def preview_token(
    merchant_id: str, file_sha: str, sheet: str, mapping: dict[str, str | None], order: str
) -> str:
    """What a preview is bound to: merchant, file, sheet, mapping and date order."""
    bound = json.dumps(
        {"m": merchant_id, "f": file_sha, "s": sheet, "map": mapping, "o": order, "t": "purchase"},
        sort_keys=True,
    )
    return hashlib.sha256(bound.encode()).hexdigest()


@dataclass
class PlannedRow:
    row_number: int
    outcome: str  # add | skip | flag | reject
    code: str  # why, for the screen's wording
    purchase_date: date | None = None
    amount_bdt: float | None = None
    category: str | None = None
    invoice_reference: str | None = None
    supplier_reference: str | None = None
    record_id: str | None = None


@dataclass
class Plan:
    token: str
    date_order_needed: bool
    rows: list[PlannedRow] = field(default_factory=list)
    truncated: bool = False

    def counts(self) -> dict[str, int]:
        out = {"add": 0, "skip": 0, "flag": 0, "reject": 0}
        for row in self.rows:
            out[row.outcome] += 1
        return out


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    return text or None


def check_mapping(sheet: Sheet, mapping: dict[str, str | None]) -> None:
    """Refuse a mapping that names a column the sheet does not have, or leaves out a must."""
    unknown = sorted(f for f in mapping if f not in FIELDS)
    if unknown:
        raise IntakeRefused(422, "unknown_field", f"Unknown field(s): {', '.join(unknown)}.")
    for name in REQUIRED:
        if not mapping.get(name):
            raise IntakeRefused(
                422, "missing_column", "Choose the columns for the date and the amount.",
                field=name,
            )
    chosen = [c for c in mapping.values() if c]
    for column in chosen:
        if column not in sheet.header:
            raise IntakeRefused(
                422, "missing_column", f"The sheet has no column {column!r}.", column=column
            )
    if len(set(chosen)) != len(chosen):
        raise IntakeRefused(422, "column_used_twice", "Each column can be used for one field only.")


def plan_rows(
    session: Session,
    config: dict[str, Any],
    *,
    merchant_id: str,
    workbook: Workbook,
    sheet_name: str,
    mapping: dict[str, str | None],
    date_order: str,
) -> Plan:
    """What would happen to every row. Writes nothing."""
    if date_order not in DATE_ORDERS:
        raise IntakeRefused(422, "invalid_date_order", "The date order must be auto, dmy or mdy.")
    sheet = workbook.sheets.get(sheet_name)
    if sheet is None:
        raise IntakeRefused(
            422, "unknown_sheet", f"The workbook has no sheet {sheet_name!r}.",
            sheets=list(workbook.sheets),
        )
    check_mapping(sheet, mapping)
    index = {name: sheet.header.index(col) for name, col in mapping.items() if col}
    end = calendar_end(config)
    plan = Plan(
        token=preview_token(merchant_id, workbook.sha256, sheet_name, mapping, date_order),
        date_order_needed=False,
        truncated=sheet.truncated,
    )
    existing = {
        (p.purchase_date, round(p.amount_bdt, 2))
        for p in session.scalars(select(db.Purchase).where(db.Purchase.merchant_id == merchant_id))
    }
    seen_ids: set[str] = set()
    seen_values: set[tuple[date, float]] = set()

    for number, values in sheet.rows:
        cell = {name: values[i] if i < len(values) else None for name, i in index.items()}
        row = PlannedRow(row_number=number, outcome="reject", code="")
        row.purchase_date, ambiguous = parse_date(cell.get("purchase_date"), date_order)
        row.amount_bdt = parse_amount(cell.get("amount_bdt"))
        row.category = _text(cell.get("category"))
        row.invoice_reference = _text(cell.get("invoice_reference"))
        row.supplier_reference = _text(cell.get("supplier_reference"))
        plan.rows.append(row)
        if ambiguous:
            plan.date_order_needed = True
            row.code = "ambiguous_date"
        elif cell.get("purchase_date") in (None, ""):
            row.code = "missing_date"
        elif row.purchase_date is None:
            row.code = "bad_date"
        elif row.purchase_date > end:
            row.code = "date_after_calendar"
        elif cell.get("amount_bdt") in (None, ""):
            row.code = "missing_amount"
        elif row.amount_bdt is None or row.amount_bdt <= 0:
            row.code = "bad_amount"
        elif row.category and len(row.category) > CATEGORY_MAX:
            row.code = "category_too_long"
        elif any(len(v or "") > TEXT_MAX for v in (row.invoice_reference, row.supplier_reference)):
            row.code = "reference_too_long"
        if row.code:
            continue
        if row.invoice_reference:
            row.record_id = _id_for("PU", merchant_id, row.invoice_reference)
        else:
            digest = hashlib.sha256(
                f"{merchant_id}|{workbook.sha256}|{sheet_name}|{number}".encode()
            ).hexdigest()
            row.record_id = f"PU-{digest[:24]}"
        if row.record_id in seen_ids:
            row.code = "reference_twice_in_file"
            continue
        seen_ids.add(row.record_id)
        if session.get(db.Purchase, row.record_id) is not None:
            row.outcome = "skip"
            row.code = "reference_saved" if row.invoice_reference else "row_imported_before"
            continue
        value = (row.purchase_date, round(row.amount_bdt, 2))
        if value in existing or value in seen_values:
            row.outcome, row.code = "flag", "possible_duplicate"
        else:
            row.outcome, row.code = "add", "new"
        seen_values.add(value)
    return plan


def check_merchant(
    session: Session, config: dict[str, Any], merchant_id: str, protected: frozenset[str]
) -> None:
    """The guards every step repeats: synthetic mode, a merchant created in the app, consent."""
    require_synthetic_mode(config)
    live_merchant(session, merchant_id, protected)
    require_consent_for(session, config, merchant_id, "purchases")


def commit_rows(
    session: Session,
    config: dict[str, Any],
    *,
    merchant_id: str,
    plan: Plan,
    keep_flagged: set[int],
    file_name: str,
    file_sha: str,
    sheet_name: str,
    actor: CurrentUser,
) -> db.ImportBatch:
    """Save the rows to add (and the flagged rows the person chose to keep) in one transaction."""
    if plan.date_order_needed:
        raise IntakeRefused(
            422, "date_order_needed", "Some dates could be read two ways. Choose the date order."
        )
    keep = [
        r
        for r in plan.rows
        if r.outcome == "add" or (r.outcome == "flag" and r.row_number in keep_flagged)
    ]
    counts = plan.counts()
    now = utc_now()
    batch = db.ImportBatch(
        batch_id=new_id("IB"),
        actor=actor.user_id,
        merchant_id=merchant_id,
        record_type="purchase",
        file_name=file_name[:128],
        file_sha256=file_sha,
        sheet_name=sheet_name[:64],
        mapping_sha256=plan.token,
        uploaded_at=now,
        rows_added=len(keep),
        rows_skipped=counts["skip"],
        rows_flagged=counts["flag"] - sum(r.outcome == "flag" for r in keep),
        rows_rejected=counts["reject"],
        status="committed",
    )
    try:
        session.add(batch)
        session.flush()
        for row in keep:
            session.add(
                db.Purchase(
                    purchase_id=row.record_id,
                    merchant_id=merchant_id,
                    purchase_date=row.purchase_date,
                    amount_bdt=float(row.amount_bdt),
                    category=row.category,
                    supplier_id=row.supplier_reference,
                )
            )
            add_provenance(
                session,
                record_type="purchase",
                record_id=row.record_id,
                merchant_id=merchant_id,
                source_category="purchases",
                entry_method="imported_spreadsheet",
                status="imported_spreadsheet",
                actor=actor.user_id,
                entered_at=now,
                business_date=row.purchase_date,
                batch_id=batch.batch_id,
            )
        session.flush()
        check_scoring_inputs(session, config, merchant_id)
        add_audit(session, actor, "import_purchases", merchant_id)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return batch
