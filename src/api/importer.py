"""Check an uploaded CSV against the data contract, report it, and load what is accepted.

Purpose: the admin data-import screen. A person from the lender's data team exports a CSV
    from their system and uploads it; this module says which rows are acceptable and why
    the others are not, and loads the acceptable ones.
Owner role: D (full-stack).
Implements: PROJECT_BRIEF section 18, item 20 ("Data import page").

What is checked:
- the file has exactly the contract columns of the table (`src/adapters/base.py`);
- every value has the right kind (date, number, true/false, a whole number from 1 to 5 ...);
- the row's id is not repeated in the file and is not already in the database. An import
  never overwrites a row;
- every merchant id is already in the database (import `merchants` first); a payment's
  loan id must belong to the same merchant (import `loans` before `payments`).

Rows that fail are listed with their line number and the reasons. Rows that pass are loaded
in one transaction. Nothing is ever edited by hand. A production system would pull this
data from the source systems on a schedule instead of taking a file.

Only synthetic or fixture files belong here. Rows for NEW merchants (not in the original data)
are scored after loading (src/api/imported.py): same model, same feature rules, no retraining.
The original merchants' records come from the source systems and may not be added to.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Collection
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from src.adapters.base import CONTRACT
from src.api.schemas import ImportRejection, ImportReport
from src.db import models as db

# Largest upload accepted, in bytes.
MAX_IMPORT_BYTES = 10 * 1024 * 1024
# How many rejected rows are listed in a report (all of them are counted).
MAX_LISTED_REJECTIONS = 100
BATCH = 500

MODELS = {
    "merchants": db.Merchant,
    "purchases": db.Purchase,
    "deliveries": db.Delivery,
    "loans": db.Loan,
    "payments": db.Payment,
    "questionnaire": db.Questionnaire,
    "consents": db.Consent,
}
# Tables an upload may never fill (none at present; kept so a table can be closed in one place).
NEVER_IMPORTED: dict[str, str] = {}
# Tables whose rows belong to a merchant's history or permission. For a merchant of the original
# data, these come from the source systems and the consent system: a history row added here
# would show on the timeline while the score ignores it (F10), and a consent row would unlock a
# merchant who never agreed (F1). So a row naming such a merchant refuses the whole file. A NEW
# merchant (imported with `merchants`) may get all of them, consent included: that is a lender
# bringing its own customers, with the consent records of its own consent system.
HISTORY_TABLES = ("purchases", "deliveries", "payments", "loans", "questionnaire", "consents")
KNOWN_MERCHANT_MESSAGE = (
    "This merchant's records come from the source systems; imports may only add new merchants. "
    "Nothing was loaded."
)


class ImportNotAllowed(Exception):
    """The upload touches records that an import may not change. Nothing is loaded."""

    def __init__(self, message: str, merchants: list[str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.merchants = merchants or []


KEY_COLUMN = {table: CONTRACT[table][0] for table in CONTRACT}
KEY_COLUMN["payments"] = "payment_id"
KEY_COLUMN["loans"] = "loan_id"
KEY_COLUMN["questionnaire"] = "merchant_id"

DELIVERY_STATUSES = ("delivered", "returned", "failed", "cancelled")
ANSWER_COLUMNS = [c for c in CONTRACT["questionnaire"] if c not in ("merchant_id", "answered_at")]

# Column kinds per table: text, date, datetime, number, bool, label (0 or 1), answer (1 to 5).
# A name ending in "?" may be empty.
KINDS: dict[str, dict[str, str]] = {
    "merchants": {
        "merchant_id": "text",
        "onboarded_at": "date",
        "district": "text?",
        "town_tier": "text?",
        "shop_type": "text?",
        "has_trade_license": "bool?",
        "consent_data_use": "bool",
        "questionnaire_done": "bool",
    },
    "purchases": {
        "purchase_id": "text",
        "merchant_id": "text",
        "purchase_date": "date",
        "amount_bdt": "number",
        "category": "text?",
        "supplier_id": "text?",
    },
    "deliveries": {
        "delivery_id": "text",
        "merchant_id": "text",
        "dispatched_at": "datetime",
        "delivered_at": "datetime?",
        "status": "text",
        "return_reason": "text?",
        "is_cod": "bool",
        "cod_remitted_on_time": "bool?",
    },
    "loans": {
        "loan_id": "text",
        "merchant_id": "text",
        "issued_at": "date",
        "limit_bdt": "number",
        "outcome_label": "label?",
        "label_observed_at": "date?",
    },
    "payments": {
        "payment_id": "text",
        "merchant_id": "text",
        "loan_id": "text",
        "due_date": "date",
        "paid_date": "date?",
        "amount_due_bdt": "number",
        "amount_paid_bdt": "number",
    },
    "questionnaire": {
        "merchant_id": "text",
        **dict.fromkeys(ANSWER_COLUMNS, "answer"),
        "answered_at": "date",
    },
    "consents": {
        "consent_id": "text",
        "merchant_id": "text",
        "purpose": "text",
        "data_categories": "text",
        "granted_at": "date",
        "expires_at": "date",
        "revoked_at": "date?",
    },
}

TRUE_WORDS = {"true", "1", "yes"}
FALSE_WORDS = {"false", "0", "no"}


@dataclass
class _Row:
    line: int
    record_id: str | None
    values: dict[str, Any]
    problems: list[str] = field(default_factory=list)


def _parse_value(name: str, kind: str, raw: str, max_length: int | None) -> tuple[Any, str | None]:
    """Turn one cell into a value, or say what is wrong with it."""
    optional = kind.endswith("?")
    kind = kind.rstrip("?")
    text = raw.strip()
    if text == "":
        return None, None if optional else f"{name} is empty"
    try:
        if kind == "text":
            if max_length and len(text) > max_length:
                return None, f"{name} is longer than {max_length} characters"
            return text, None
        if kind == "date":
            return date.fromisoformat(text), None
        if kind == "datetime":
            return datetime.fromisoformat(text), None
        if kind == "number":
            value = float(text)
            if value != value or value < 0:  # NaN or negative
                return None, f"{name} must be a number of 0 or more"
            return value, None
        if kind == "bool":
            if text.lower() in TRUE_WORDS:
                return True, None
            if text.lower() in FALSE_WORDS:
                return False, None
            return None, f"{name} must be True or False"
        if kind == "label":
            if text in ("0", "1"):
                return int(text), None
            return None, f"{name} must be 0, 1 or empty"
        if kind == "answer":
            if text in ("1", "2", "3", "4", "5"):
                return int(text), None
            return None, f"{name} must be a whole number from 1 to 5"
    except ValueError:
        expected = {"date": "YYYY-MM-DD", "datetime": "YYYY-MM-DDTHH:MM:SS", "number": "a number"}
        return None, f"{name} is not valid (expected {expected.get(kind, kind)})"
    raise AssertionError(f"unknown column kind {kind!r}")


def _row_rules(table: str, values: dict[str, Any]) -> list[str]:
    """Rules that look at several columns of one row."""
    problems = []
    if table == "deliveries" and values.get("status") not in DELIVERY_STATUSES:
        problems.append(f"status must be one of {', '.join(DELIVERY_STATUSES)}")
    if table == "consents":
        granted, expires = values.get("granted_at"), values.get("expires_at")
        if granted and expires and expires <= granted:
            problems.append("expires_at must be after granted_at")
    if table == "loans" and values.get("outcome_label") is not None:
        if values.get("label_observed_at") is None:
            problems.append("label_observed_at is empty but outcome_label is set")
    return problems


def _chunks(items: list[str], size: int = BATCH):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _existing(session: Session, column, values: set[str]) -> set[str]:
    found: set[str] = set()
    for chunk in _chunks(sorted(values)):
        found.update(session.scalars(select(column).where(column.in_(chunk))))
    return found


def _max_lengths(table: str) -> dict[str, int | None]:
    columns = MODELS[table].__table__.columns
    return {name: getattr(columns[name].type, "length", None) for name in CONTRACT[table]}


def check_csv(
    session: Session,
    table: str,
    raw: bytes,
    scored_merchants: Collection[str] | None = None,
) -> tuple[ImportReport, list[dict[str, Any]]]:
    """Check an upload. Returns the report and the accepted rows (typed, ready to insert).

    Nothing is written. `loaded` is False and `dry_run` True in the report; the caller
    changes them if it loads the rows.

    `scored_merchants` are the merchants the scorer already knows. A history table (purchases,
    deliveries, payments, loans, questionnaire) must be given them: a row for one of them
    raises `ImportNotAllowed`, for the whole file. A file whose columns are wrong is reported
    as before, and is never looked at row by row.
    """
    if table in NEVER_IMPORTED:
        raise ImportNotAllowed(NEVER_IMPORTED[table])
    if table in HISTORY_TABLES and scored_merchants is None:
        raise ImportNotAllowed("Cannot tell which merchants are scored. Nothing was loaded.")
    report = ImportReport(
        table=table,
        dry_run=True,
        rows_received=0,
        rows_accepted=0,
        rows_rejected=0,
        loaded=False,
        note="",
    )
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        report.file_error = "The file is not UTF-8 text."
        return report, []
    reader = csv.DictReader(io.StringIO(text, newline=""))
    header = reader.fieldnames
    if not header:
        report.file_error = "The file is empty: a header line with the column names is needed."
        return report, []
    expected = CONTRACT[table]
    missing = [name for name in expected if name not in header]
    unexpected = [name for name in header if name not in expected]
    if missing or unexpected or len(set(header)) != len(header):
        report.file_error = (
            f"The columns do not match the data contract for '{table}'. "
            f"Missing: {missing or 'none'}. Unexpected: {unexpected or 'none'}. "
            f"Repeated: {sorted({n for n in header if header.count(n) > 1}) or 'none'}. "
            f"Expected exactly: {', '.join(expected)}."
        )
        return report, []

    kinds, lengths, key = KINDS[table], _max_lengths(table), KEY_COLUMN[table]
    rows: list[_Row] = []
    for raw_row in reader:
        values: dict[str, Any] = {}
        problems: list[str] = []
        if None in raw_row or any(value is None for value in raw_row.values()):
            record = _Row(reader.line_num, raw_row.get(key), {}, ["wrong number of columns"])
        else:
            for name in expected:
                value, problem = _parse_value(name, kinds[name], raw_row[name], lengths[name])
                values[name] = value
                if problem:
                    problems.append(problem)
            if not problems:
                problems.extend(_row_rules(table, values))
            record = _Row(reader.line_num, raw_row[key].strip() or None, values, problems)
        rows.append(record)
    report.rows_received = len(rows)

    if table in HISTORY_TABLES:
        known = sorted(
            {
                row.values["merchant_id"]
                for row in rows
                if row.values.get("merchant_id") in scored_merchants
            }
        )
        if known:
            raise ImportNotAllowed(KNOWN_MERCHANT_MESSAGE, known)

    _check_repeats_in_file(rows, key)
    _check_against_database(session, table, rows, key)

    accepted = [row.values for row in rows if not row.problems]
    rejected = [row for row in rows if row.problems]
    report.rows_accepted = len(accepted)
    report.rows_rejected = len(rejected)
    report.rejections = [
        ImportRejection(line=row.line, record_id=row.record_id, reasons=row.problems)
        for row in rejected[:MAX_LISTED_REJECTIONS]
    ]
    report.rejections_truncated = len(rejected) > MAX_LISTED_REJECTIONS
    return report, accepted


def _check_repeats_in_file(rows: list[_Row], key: str) -> None:
    first_line: dict[str, int] = {}
    for row in rows:
        if row.record_id is None:
            continue
        if row.record_id in first_line:
            row.problems.append(
                f"{key} {row.record_id} is repeated (first on line {first_line[row.record_id]})"
            )
        else:
            first_line[row.record_id] = row.line


def _check_against_database(session: Session, table: str, rows: list[_Row], key: str) -> None:
    """Refuse ids that already exist, merchants and loans that are not known."""
    model = MODELS[table]
    candidates = [row for row in rows if not row.problems]
    by_id = {row.record_id: row for row in candidates if row.record_id}
    for taken in _existing(session, getattr(model, key), set(by_id)):
        by_id[taken].problems.append(
            f"{key} {taken} is already in the database (an import never overwrites)"
        )

    if table == "merchants":
        return
    candidates = [row for row in rows if not row.problems]
    wanted = {row.values["merchant_id"] for row in candidates}
    known = _existing(session, db.Merchant.merchant_id, wanted)
    for row in candidates:
        if row.values["merchant_id"] not in known:
            merchant = row.values["merchant_id"]
            row.problems.append(
                f"merchant {merchant} is not in the database (import merchants first)"
            )

    if table == "payments":
        candidates = [row for row in rows if not row.problems]
        loan_ids = sorted({row.values["loan_id"] for row in candidates})
        owner: dict[str, str] = {}
        for chunk in _chunks(loan_ids):
            found = session.execute(
                select(db.Loan.loan_id, db.Loan.merchant_id).where(db.Loan.loan_id.in_(chunk))
            )
            owner.update(dict(found.all()))
        for row in candidates:
            loan = row.values["loan_id"]
            if loan not in owner:
                row.problems.append(f"loan {loan} is not in the database (import loans first)")
            elif owner[loan] != row.values["merchant_id"]:
                row.problems.append(f"loan {loan} belongs to a different merchant")


def load_rows(session: Session, table: str, accepted: list[dict[str, Any]]) -> None:
    """Write the accepted rows. The caller commits (together with the audit entry)."""
    model = MODELS[table]
    for start in range(0, len(accepted), 5000):
        session.execute(insert(model.__table__), accepted[start : start + 5000])
    if table == "questionnaire":
        ids = [row["merchant_id"] for row in accepted]
        for chunk in _chunks(ids):
            session.execute(
                update(db.Merchant)
                .where(db.Merchant.merchant_id.in_(chunk))
                .values(questionnaire_done=True)
            )
