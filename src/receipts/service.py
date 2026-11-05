"""Receipts: from an uploaded file to checked records, and a merchant's right to dispute them.

Purpose: the one place that moves a receipt through its states. A Records Officer uploads a
    receipt; the reader fills a table; the officer checks and corrects it and publishes it;
    only then do its lines become purchases, deliveries or repayments that credit officers and
    the score can see. A merchant may report a published line as wrong; that line is left out of
    the score until the Records Desk answers. Nothing here approves or declines credit.
Owner role: D (full-stack).
Implements: the receipt workflow of the Records Desk redesign.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.accounts.service import now
from src.api.auth import CurrentUser, add_audit
from src.db import models as db
from src.intake import records
from src.intake.policy import IntakeRefused, add_provenance
from src.notifications import notify_officers, notify_user
from src.receipts import parse

CELLS = (
    "item",
    "quantity",
    "unit",
    "unit_price",
    "amount_bdt",
    "line_date",
    "due_date",
    "outcome",
    "reference",
)
NUMERIC = ("quantity", "unit_price", "amount_bdt")
DATES = ("line_date", "due_date")
PARSED_NAME = {"amount_bdt": "amount"}


class ReceiptError(Exception):
    def __init__(self, status: int, code: str, message: str, **facts: Any) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.facts = status, code, message, facts


def _loads(text: str | None, default: Any) -> Any:
    try:
        return json.loads(text) if text else default
    except ValueError:
        return default


def notes_of(receipt: db.Receipt) -> list[str]:
    return _loads(receipt.notes, [])


def flags_of(line: db.ReceiptLine) -> list[dict[str, str]]:
    return _loads(line.flags, [])


def confidence_of(line: db.ReceiptLine) -> dict[str, float]:
    return _loads(line.confidence, {})


# --- creating and filling ------------------------------------------------------------------


def create_receipt(
    session: Session,
    user: CurrentUser,
    org: str,
    merchant_id: str,
    kind: str,
    document: db.Document | None,
) -> db.Receipt:
    """A receipt for a shop, with its reading job queued when there is a file. The caller
    commits."""
    if kind not in db.RECEIPT_KINDS:
        raise ReceiptError(422, "invalid_choice", "Choose purchase, delivery or repayment.")
    receipt = db.Receipt(
        receipt_id=f"RC-{uuid.uuid4().hex[:24]}",
        organization_id=org,
        merchant_id=merchant_id,
        kind=kind,
        status="extracted",
        document_id=document.document_id if document else None,
        method="ocr" if document else "typed",
        uploaded_by=user.user_id,
        uploaded_at=now(),
    )
    session.add(receipt)
    session.flush()
    if document is not None:
        job = db.ExtractionJob(
            job_id=f"XJ-{uuid.uuid4().hex[:24]}",
            document_id=document.document_id,
            organization_id=org,
            merchant_id=merchant_id,
            purpose="receipt",
            status="queued",
            queued_at=now(),
        )
        session.add(job)
        receipt.job_id = job.job_id
    return receipt


def _write_cell(line: db.ReceiptLine, name: str, cell: parse.Cell, conf: dict[str, float]) -> None:
    value = cell.value
    if name in ("line_date", "due_date") and isinstance(value, date):
        setattr(line, name, value)
    elif name == "amount":
        line.amount_bdt = value
    elif name == "unit_price":
        line.unit_price = value
    elif name in ("item", "quantity", "unit", "outcome", "reference"):
        setattr(line, name, value)
    if value is not None and cell.conf is not None:
        conf["amount_bdt" if name == "amount" else name] = round(float(cell.conf), 3)


def apply_parsed(session: Session, receipt: db.Receipt, parsed: parse.ParsedReceipt) -> None:
    """Fill the header and replace the lines with what the reader found."""
    receipt.supplier = parsed.supplier.value
    receipt.receipt_date = parsed.receipt_date.value
    receipt.memo_no = parsed.memo_no.value
    receipt.stated_total = parsed.stated_total.value
    receipt.notes = json.dumps(parsed.notes, ensure_ascii=False)
    for old in session.scalars(
        select(db.ReceiptLine).where(db.ReceiptLine.receipt_id == receipt.receipt_id)
    ):
        session.delete(old)
    session.flush()
    for ln in parsed.lines:
        conf: dict[str, float] = {}
        row = db.ReceiptLine(
            line_id=f"RL-{uuid.uuid4().hex[:24]}",
            receipt_id=receipt.receipt_id,
            organization_id=receipt.organization_id,
            merchant_id=receipt.merchant_id,
            row_no=ln.row_no,
            status="extracted",
            created_at=now(),
        )
        for name in (
            "item",
            "quantity",
            "unit",
            "unit_price",
            "amount",
            "line_date",
            "due_date",
            "outcome",
            "reference",
        ):
            _write_cell(row, name, getattr(ln, name), conf)
        row.confidence = json.dumps(conf)
        row.flags = json.dumps(
            [{**f, "cell": "amount_bdt" if f["cell"] == "amount" else f["cell"]} for f in ln.flags]
        )
        session.add(row)


def _to_parsed(receipt: db.Receipt, lines: list[db.ReceiptLine]) -> parse.ParsedReceipt:
    parsed = parse.ParsedReceipt(kind=receipt.kind)
    parsed.stated_total = parse.Cell(receipt.stated_total, 1.0)
    parsed.receipt_date = parse.Cell(receipt.receipt_date, 1.0)
    for row in lines:
        conf = confidence_of(row)
        ln = parse.ParsedLine(row_no=row.row_no)
        for name in (
            "item",
            "quantity",
            "unit",
            "unit_price",
            "line_date",
            "due_date",
            "outcome",
            "reference",
        ):
            setattr(ln, name, parse.Cell(getattr(row, name), conf.get(name)))
        ln.amount = parse.Cell(row.amount_bdt, conf.get("amount_bdt"))
        ln.flags = [
            {**f, "cell": "amount" if f["cell"] == "amount_bdt" else f["cell"]}
            for f in flags_of(row)
            if f["code"] == "repaired_digit"
        ]
        parsed.lines.append(ln)
    return parsed


def recheck(
    session: Session, receipt: db.Receipt, today: date, low_confidence: float
) -> parse.ParsedReceipt:
    lines = _lines(session, receipt.receipt_id)
    parsed = _to_parsed(receipt, lines)
    parse.check(parsed, today, low_confidence)
    receipt.notes = json.dumps(parsed.notes, ensure_ascii=False)
    for row, ln in zip(lines, parsed.lines):
        row.flags = json.dumps(
            [{**f, "cell": "amount_bdt" if f["cell"] == "amount" else f["cell"]} for f in ln.flags]
        )
    return parsed


def _lines(session: Session, receipt_id: str) -> list[db.ReceiptLine]:
    return list(
        session.scalars(
            select(db.ReceiptLine)
            .where(db.ReceiptLine.receipt_id == receipt_id)
            .order_by(db.ReceiptLine.row_no)
        )
    )


def lines_of(session: Session, receipt_id: str) -> list[db.ReceiptLine]:
    return _lines(session, receipt_id)


# --- editing ---------------------------------------------------------------------------------


def _number(value: Any, label: str) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(str(value).replace(",", ""))
    except ValueError:
        raise ReceiptError(422, "invalid_number", f"{label} must be a number.") from None
    if number < 0 or number > 1e9:
        raise ReceiptError(422, "invalid_number", f"{label} is out of range.")
    return number


def _day(value: Any, label: str) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise ReceiptError(422, "invalid_date", f"{label} must be written YYYY-MM-DD.") from None


def save_edits(
    session: Session,
    user: CurrentUser,
    receipt: db.Receipt,
    header: dict[str, Any],
    rows: list[dict[str, Any]],
    today: date,
    low_confidence: float,
) -> None:
    """Apply the Records Officer's corrections. A cell the officer changed or typed is no longer
    'unsure' (it was read by a person); the checks run again on the new numbers."""
    if receipt.status not in ("extracted", "checked"):
        raise ReceiptError(409, "receipt_closed", "This receipt is already published or rejected.")
    if len(rows) > 200:
        raise ReceiptError(422, "too_many_lines", "A receipt can have at most 200 lines.")
    if "supplier" in header:
        receipt.supplier = (header["supplier"] or "").strip()[:120] or None
    if "memo_no" in header:
        receipt.memo_no = (header["memo_no"] or "").strip()[:60] or None
    if "receipt_date" in header:
        receipt.receipt_date = _day(header["receipt_date"], "The receipt date")
    if "stated_total" in header:
        receipt.stated_total = _number(header["stated_total"], "The total")
    existing = {r.line_id: r for r in _lines(session, receipt.receipt_id)}
    keep: set[str] = set()
    for number, data in enumerate(rows, start=1):
        row = existing.get(data.get("line_id") or "")
        if row is None:
            row = db.ReceiptLine(
                line_id=f"RL-{uuid.uuid4().hex[:24]}",
                receipt_id=receipt.receipt_id,
                organization_id=receipt.organization_id,
                merchant_id=receipt.merchant_id,
                status="extracted",
                created_at=now(),
            )
            session.add(row)
        keep.add(row.line_id)
        row.row_no = number
        conf = confidence_of(row)
        for name in CELLS:
            if name not in data:
                continue
            raw = data[name]
            if name in NUMERIC:
                new: Any = _number(raw, name.replace("_", " "))
            elif name in DATES:
                new = _day(raw, name.replace("_", " "))
            else:
                new = str(raw).strip() if raw not in (None, "") else None
                if new and name == "outcome" and new not in ("delivered", "returned", "failed"):
                    raise ReceiptError(
                        422, "invalid_choice", "Outcome is delivered, returned or failed."
                    )
                if new:
                    new = new[:120]
            if getattr(row, name) != new:
                setattr(row, name, new)
                row.edited = True
                conf[name] = 1.0
        row.confidence = json.dumps(conf)
        row.status = "checked"
    for line_id, row in existing.items():
        if line_id not in keep:
            session.delete(row)
    session.flush()
    receipt.status, receipt.checked_by = "checked", user.user_id
    recheck(session, receipt, today, low_confidence)


# --- publishing ------------------------------------------------------------------------------


def open_flag_count(session: Session, receipt_id: str) -> int:
    return sum(1 for ln in _lines(session, receipt_id) if flags_of(ln))


def _project(
    session: Session,
    config: dict[str, Any],
    user: CurrentUser,
    receipt: db.Receipt,
    row: db.ReceiptLine,
    protected: frozenset[str],
) -> str:
    """Write one checked line to the record the assessment reads. Returns that record's id."""
    day = row.line_date or receipt.receipt_date
    try:
        if receipt.kind == "purchase":
            made, _ = records.record_purchase(
                session,
                config,
                merchant_id=receipt.merchant_id,
                purchase_date=day,
                amount_bdt=row.amount_bdt,
                category=row.item,
                supplier_reference=receipt.supplier,
                invoice_reference=row.line_id,
                actor=user,
                protected_merchants=protected,
            )
            return made.purchase_id
        if receipt.kind == "delivery":
            delivered = row.outcome == "delivered"
            made, _ = records.record_delivery(
                session,
                config,
                merchant_id=receipt.merchant_id,
                dispatched_at=datetime.combine(day, time(9, 0)),
                delivered_at=datetime.combine(row.due_date or day, time(15, 0))
                if delivered
                else None,
                status=row.outcome,
                return_reason=None,
                is_cod=bool(row.amount_bdt),
                cod_remitted_on_time=None,
                parcel_reference=row.reference or row.line_id,
                actor=user,
                protected_merchants=protected,
            )
            return made.delivery_id
        made, _ = records.record_repayment(
            session,
            config,
            merchant_id=receipt.merchant_id,
            loan_id=row.reference or "",
            due_date=row.due_date or day,
            paid_date=day,
            amount_due_bdt=row.unit_price or row.amount_bdt,
            amount_paid_bdt=row.amount_bdt,
            actor=user,
            protected_merchants=protected,
        )
        return made.payment_id
    except IntakeRefused as error:
        if error.code == "duplicate_reference":  # written on an earlier try: find it again
            prefix = {"purchase": "PU", "delivery": "DE", "repayment": "PA"}[receipt.kind]
            ref = row.line_id if receipt.kind == "purchase" else (row.reference or row.line_id)
            return records._id_for(prefix, receipt.merchant_id, ref)
        raise ReceiptError(
            error.status, error.code, f"Line {row.row_no}: {error.message}"
        ) from None


def _complete(receipt: db.Receipt, row: db.ReceiptLine) -> str | None:
    day = row.line_date or receipt.receipt_date
    if day is None:
        return "has no date"
    if receipt.kind in ("purchase", "repayment") and not (row.amount_bdt and row.amount_bdt > 0):
        return "has no amount"
    if receipt.kind == "delivery" and row.outcome not in ("delivered", "returned", "failed"):
        return "has no delivery result"
    if receipt.kind == "repayment" and not row.reference:
        return "has no loan reference"
    return None


def publish(
    session: Session,
    config: dict[str, Any],
    user: CurrentUser,
    receipt: db.Receipt,
    protected: frozenset[str],
    acknowledged: bool,
) -> int:
    """Make the receipt's lines visible to the credit officers and the score. Returns how many
    lines were published. Refused while cells still need a look, unless the officer says they
    compared them with the paper."""
    if receipt.status not in ("extracted", "checked"):
        raise ReceiptError(409, "receipt_closed", "This receipt is already published or rejected.")
    rows = _lines(session, receipt.receipt_id)
    if not rows:
        raise ReceiptError(422, "no_lines", "There are no lines to publish. Add the lines first.")
    for row in rows:
        problem = _complete(receipt, row)
        if problem:
            raise ReceiptError(422, "line_incomplete", f"Line {row.row_no} {problem}.")
    pending = open_flag_count(session, receipt.receipt_id)
    if pending and not acknowledged:
        raise ReceiptError(
            409,
            "cells_need_checking",
            f"{pending} line(s) still have cells to check. Compare them with the receipt, "
            "then confirm.",
            lines=pending,
        )
    for row in rows:
        if row.projected_record_id is None:
            row.projected_record_id = _project(session, config, user, receipt, row, protected)
            add_provenance(
                session,
                record_type={
                    "purchase": "purchase",
                    "delivery": "delivery",
                    "repayment": "payment",
                }[receipt.kind],
                record_id=row.projected_record_id,
                merchant_id=receipt.merchant_id,
                source_category={
                    "purchase": "purchases",
                    "delivery": "deliveries",
                    "repayment": "payments",
                }[receipt.kind],
                entry_method="receipt_desk",
                status="reviewed",
                actor=user.user_id,
                entered_at=now(),
                business_date=row.line_date or receipt.receipt_date,
            )
        row.status = "published"
    receipt.status, receipt.published_by, receipt.published_at = "published", user.user_id, now()
    add_audit(session, user, "publish_receipt", receipt.merchant_id)
    return len(rows)


def reject(session: Session, user: CurrentUser, receipt: db.Receipt, reason: str) -> None:
    if receipt.status not in ("extracted", "checked"):
        raise ReceiptError(409, "receipt_closed", "This receipt is already published or rejected.")
    reason = (reason or "").strip()
    if len(reason) < 3:
        raise ReceiptError(422, "reason_needed", "Say why this receipt is rejected.")
    receipt.status, receipt.reject_reason = "rejected", reason[:300]
    add_audit(session, user, "reject_receipt", receipt.merchant_id)


# --- the merchant's side ---------------------------------------------------------------------


def confirm(session: Session, receipt: db.Receipt) -> None:
    if receipt.status != "published":
        raise ReceiptError(409, "not_published", "This receipt is not ready for your review.")
    receipt.merchant_confirmed_at = receipt.merchant_confirmed_at or now()


def raise_flag(
    session: Session,
    user: CurrentUser,
    line: db.ReceiptLine,
    note: str,
    claimed: float | None,
    proof: db.Document | None,
) -> db.ReceiptFlag:
    """The merchant says a published line is wrong. The line leaves the score until answered."""
    if line.status not in ("published",):
        raise ReceiptError(409, "not_flaggable", "Only a published line can be reported.")
    note = (note or "").strip()
    if len(note) < 5:
        raise ReceiptError(422, "note_needed", "Say what is wrong (at least a few words).")
    if claimed is not None and not 0 <= claimed <= 1e9:
        raise ReceiptError(422, "invalid_number", "The amount is out of range.")
    flag = db.ReceiptFlag(
        flag_id=f"RF-{uuid.uuid4().hex[:24]}",
        line_id=line.line_id,
        receipt_id=line.receipt_id,
        organization_id=line.organization_id,
        merchant_id=line.merchant_id,
        note=note[:1000],
        claimed_amount_bdt=claimed,
        proof_document_id=proof.document_id if proof else None,
        status="open",
        raised_by=user.user_id,
        raised_at=now(),
    )
    session.add(flag)
    line.status = "disputed"
    for member in session.scalars(
        select(db.Membership.user_id).where(
            db.Membership.organization_id == line.organization_id,
            db.Membership.role == "records_officer",
            db.Membership.status == "active",
        )
    ):
        notify_user(
            session,
            member,
            line.organization_id,
            "merchant_report",
            "A merchant reported a mistake on a receipt line.",
            "/app/reports",
        )
    return flag


def resolve_flag(
    session: Session,
    config: dict[str, Any],
    user: CurrentUser,
    flag: db.ReceiptFlag,
    accept: bool,
    amount: float | None,
    note: str,
) -> None:
    """Answer a report. Accepting corrects the line (and the record the score reads); rejecting
    puts the line back as it was. Either way the line returns to the score."""
    if flag.status != "open":
        raise ReceiptError(409, "already_resolved", "This report was already answered.")
    note = (note or "").strip()
    if len(note) < 3:
        raise ReceiptError(422, "note_needed", "Write the answer the merchant will read.")
    line = session.get(db.ReceiptLine, flag.line_id)
    if accept:
        new = amount if amount is not None else flag.claimed_amount_bdt
        if new is None or new <= 0:
            raise ReceiptError(422, "amount_needed", "Give the corrected amount.")
        receipt = session.get(db.Receipt, line.receipt_id)
        line.amount_bdt = float(new)
        line.edited = True
        if line.projected_record_id and receipt.kind == "purchase":
            purchase = session.get(db.Purchase, line.projected_record_id)
            if purchase is not None:
                purchase.amount_bdt = float(new)
        elif line.projected_record_id and receipt.kind == "repayment":
            payment = session.get(db.Payment, line.projected_record_id)
            if payment is not None:
                payment.amount_paid_bdt = min(float(new), payment.amount_due_bdt)
        if line.projected_record_id:
            add_provenance(
                session,
                record_type="purchase" if receipt.kind == "purchase" else "payment",
                record_id=line.projected_record_id,
                merchant_id=line.merchant_id,
                source_category="purchases" if receipt.kind == "purchase" else "payments",
                entry_method="receipt_desk",
                status="reviewed",
                actor=user.user_id,
                entered_at=now(),
                business_date=line.line_date,
            )
    flag.status = "accepted" if accept else "rejected"
    flag.resolved_by, flag.resolved_at, flag.resolution_note = user.user_id, now(), note[:300]
    line.status = "published"
    add_audit(session, user, "resolve_merchant_report", flag.merchant_id)
    notify_officers(
        session,
        flag.organization_id,
        "report_resolved",
        "A merchant's report was answered; the line is back in the score.",
        f"/app/merchants/{flag.merchant_id}",
    )


def disputed_record_ids(session: Session, merchant_ids: list[str]) -> set[str]:
    """The purchase, delivery and payment ids that must stay out of the score right now."""
    if not merchant_ids:
        return set()
    return {
        rid
        for rid in session.scalars(
            select(db.ReceiptLine.projected_record_id).where(
                db.ReceiptLine.merchant_id.in_(merchant_ids),
                db.ReceiptLine.status == "disputed",
                db.ReceiptLine.projected_record_id.is_not(None),
            )
        )
        if rid
    }
