"""Turn what the OCR engine read on a receipt into a header and a table, and say what to doubt.

Purpose: a misread amount must never slide into a score unnoticed. This module builds the rows
    the Records Officer sees beside the receipt image and attaches to every cell how sure the
    engine was and, more usefully, whether the numbers agree with each other: quantity times
    rate equals the amount, the amounts add up to the stated total, the date is possible, no
    amount is wildly out of line. A cell that fails a check is flagged in plain words. The reader
    never guesses silently: a digit it had to repair (a letter O read for a zero) is flagged.
Owner role: C (assessment) / D (full-stack).
Implements: the receipt pipeline of the Records Desk redesign.

Printed receipts (English or Bangla, Latin or Bangla digits) read well. Handwriting is read
poorly by the engine: the Records Officer then corrects or types the lines, and every cell
that the engine was unsure of is marked.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from src.extraction.engine import Box
from src.extraction.forms import BN_DIGITS, parse_date, rows_of

NUMBER = re.compile(r"^[৳]?\s*\d[\d,]*(\.\d+)?\s*(/-|tk|taka|bdt|টাকা)?$", re.IGNORECASE)
CONFUSED = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1", "|": "1", "S": "5", "B": "8"})
TOTAL_WORDS = ("grand total", "total", "net", "মোট", "সর্বমোট", "সর্বমোট টাকা", "মোট টাকা")
MEMO_WORDS = ("memo", "invoice", "bill", "challan", "receipt", "মেমো", "ক্যাশমেমো", "চালান")
HEADER_WORDS = {
    "item": ("item", "description", "particulars", "product", "বিবরণ", "পণ্য", "মালের নাম"),
    "quantity": ("qty", "quantity", "পরিমাণ", "সংখ্যা"),
    "unit_price": ("rate", "price", "দর", "মূল্য"),
    "amount": ("amount", "total", "টাকা", "মোট"),
}
OUTCOMES = {
    "delivered": ("delivered", "delivery done", "ডেলিভারড", "পৌঁছেছে", "সম্পন্ন"),
    "returned": ("returned", "return", "ফেরত"),
    "failed": ("failed", "undelivered", "ব্যর্থ"),
}
UNITS = (
    "kg",
    "g",
    "gm",
    "ltr",
    "l",
    "pcs",
    "pc",
    "bag",
    "sack",
    "box",
    "dozen",
    "carton",
    "কেজি",
    "লিটার",
    "পিস",
    "বস্তা",
    "বাক্স",
)
LOW_CONFIDENCE = 0.6
TOLERANCE_TAKA = 1.0
OLD_YEARS = 5


@dataclass
class Cell:
    value: Any = None
    conf: float | None = None


@dataclass
class ParsedLine:
    row_no: int
    item: Cell = field(default_factory=Cell)
    quantity: Cell = field(default_factory=Cell)
    unit: Cell = field(default_factory=Cell)
    unit_price: Cell = field(default_factory=Cell)
    amount: Cell = field(default_factory=Cell)
    line_date: Cell = field(default_factory=Cell)
    due_date: Cell = field(default_factory=Cell)
    outcome: Cell = field(default_factory=Cell)
    reference: Cell = field(default_factory=Cell)
    flags: list[dict[str, str]] = field(default_factory=list)

    def flag(self, cell: str, code: str, text: str) -> None:
        if not any(f["cell"] == cell and f["code"] == code for f in self.flags):
            self.flags.append({"cell": cell, "code": code, "text": text})


@dataclass
class ParsedReceipt:
    kind: str
    supplier: Cell = field(default_factory=Cell)
    receipt_date: Cell = field(default_factory=Cell)
    memo_no: Cell = field(default_factory=Cell)
    stated_total: Cell = field(default_factory=Cell)
    lines: list[ParsedLine] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def parse_day(text: str) -> str | None:
    """A date in a line of text. Also reads an 8-digit run written without separators
    (the reader often drops the slashes of a Bangla date) when it makes a real day."""
    found = parse_date(text)
    if found:
        return found
    digits = re.search(r"(?<!\d)(\d{2})(\d{2})(\d{4})(?!\d)", (text or "").translate(BN_DIGITS))
    if digits:
        d, m, y = (int(g) for g in digits.groups())
        try:
            return date(y, m, d).isoformat()
        except ValueError:
            return None
    return None


def to_number(text: str) -> tuple[float | None, bool]:
    """(number, repaired). Bangla digits and thousands commas are plain reading, not repair;
    a letter read for a digit is repaired and reported, so the cell gets flagged."""
    raw = (text or "").translate(BN_DIGITS).strip()
    raw = re.sub(r"(/-|tk\.?|taka|bdt|টাকা|৳)", "", raw, flags=re.IGNORECASE).strip()
    if not raw:
        return None, False
    repaired = False
    if not re.fullmatch(r"[\d,]*\.?\d*", raw):
        fixed = raw.translate(CONFUSED)
        if re.fullmatch(r"[\d,]*\.?\d*", fixed) and sum(c.isdigit() for c in raw) >= max(
            1, len(raw) // 2
        ):
            raw, repaired = fixed, True
        else:
            return None, False
    raw = raw.replace(",", "")
    if not raw or raw == ".":
        return None, False
    try:
        return float(raw), repaired
    except ValueError:
        return None, False


def _is_numberish(text: str) -> bool:
    return to_number(text)[0] is not None


def _row_text(row: list[Box]) -> str:
    return " ".join(b.text for b in row).translate(BN_DIGITS).lower()


def _has(row: list[Box], words: tuple[str, ...]) -> bool:
    low = _row_text(row)
    return any(w in low for w in words)


def _conf(boxes: list[Box]) -> float | None:
    return min((b.conf for b in boxes), default=None)


def _split_unit(text: str) -> tuple[str, str | None]:
    """'10kg' -> ('10', 'kg')."""
    match = re.fullmatch(r"([\d.,]+)\s*([^\d\s]+)", text.translate(BN_DIGITS).strip())
    if match and match.group(2).lower() in UNITS:
        return match.group(1), match.group(2)
    return text, None


def _last_number(row: list[Box]) -> tuple[float | None, float | None, bool]:
    for box in reversed(row):
        value, repaired = to_number(box.text)
        if value is not None:
            return value, box.conf, repaired
    return None, None, False


def _header(rows: list[list[Box]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in rows:
        text = _row_text(row)
        for box in row:
            when = parse_day(box.text)
            if when and "receipt_date" not in out:
                out["receipt_date"] = Cell(date.fromisoformat(when), box.conf)
        if "receipt_date" not in out:
            when = parse_day(text)
            if when:
                out["receipt_date"] = Cell(date.fromisoformat(when), _conf(row))
        if any(w in text for w in MEMO_WORDS) and "memo_no" not in out:
            # the number sits in the same box as the word, or in the box right after it
            for index, box in enumerate(row):
                if not any(w in box.text.lower() for w in MEMO_WORDS):
                    continue
                own = re.sub(r"^[^\d]*", "", box.text.translate(BN_DIGITS)).strip(" :.-#")
                after = row[index + 1] if index + 1 < len(row) else None
                if own and not parse_day(box.text):
                    out["memo_no"] = Cell(own, box.conf)
                elif after is not None and re.search(r"\d", after.text.translate(BN_DIGITS)):
                    nxt = re.sub(r"[^\d]", "", after.text.translate(BN_DIGITS))
                    if nxt and not parse_day(after.text):
                        out["memo_no"] = Cell(nxt, after.conf)
                break
    return out


def _supplier(rows: list[list[Box]], table_start: int) -> Cell:
    for row in rows[: max(table_start, 1)]:
        text = " ".join(b.text for b in row).strip()
        letters = sum(c.isalpha() for c in text)
        if letters >= 3 and not parse_date(text) and not _has(row, MEMO_WORDS):
            return Cell(text.strip(" :-"), _conf(row))
    return Cell()


def _columns(header_row: list[Box]) -> dict[str, float]:
    """Centre x of each recognised column header."""
    found: dict[str, float] = {}
    for box in header_row:
        low = box.text.lower()
        for key, words in HEADER_WORDS.items():
            if key not in found and any(w in low for w in words):
                found[key] = (box.x0 + box.x1) / 2
    return found


def _nearest(columns: dict[str, float], box: Box) -> str:
    centre = (box.x0 + box.x1) / 2
    return min(columns, key=lambda k: abs(columns[k] - centre))


def _purchase_line(no: int, row: list[Box], columns: dict[str, float]) -> ParsedLine | None:
    line = ParsedLine(row_no=no)
    text_boxes: list[Box] = []
    numbers: list[tuple[Box, float, bool]] = []
    with_unit: set[int] = set()  # boxes like "24 pcs": a number with its unit is the quantity
    for box in row:
        text, unit = _split_unit(box.text)
        value, repaired = to_number(text)
        if value is not None:
            numbers.append((box, value, repaired))
            if unit:
                line.unit = Cell(unit, box.conf)
                with_unit.add(id(box))
        elif box.text.strip().lower() in UNITS:
            line.unit = Cell(box.text.strip(), box.conf)
        else:
            text_boxes.append(box)
    if not numbers and not text_boxes:
        return None
    if text_boxes:
        line.item = Cell(" ".join(b.text for b in text_boxes).strip(), _conf(text_boxes))
    if len(columns) >= 2 and "amount" in columns:
        for box, value, repaired in numbers:
            # The column header may have been misread ("Qty" as "oty"); a number written
            # with its unit is still the quantity.
            key = "quantity" if id(box) in with_unit else _nearest(columns, box)
            cell = Cell(value, box.conf)
            if key == "quantity":
                line.quantity = cell
            elif key == "unit_price":
                line.unit_price = cell
            elif key == "amount":
                line.amount = cell
            if repaired:
                line.flag(
                    key if key != "item" else "amount",
                    "repaired_digit",
                    "A letter was read as a digit here: check the receipt.",
                )
    else:  # no recognisable header: amount is the last number, then rate, then quantity
        values = [(b, v, r) for b, v, r in numbers]
        if values:
            box, value, repaired = values[-1]
            line.amount = Cell(value, box.conf)
            if repaired:
                line.flag(
                    "amount",
                    "repaired_digit",
                    "A letter was read as a digit here: check the receipt.",
                )
        if len(values) >= 3:
            line.quantity, line.unit_price = (
                Cell(values[-3][1], values[-3][0].conf),
                Cell(values[-2][1], values[-2][0].conf),
            )
        elif len(values) == 2:
            line.quantity = Cell(values[0][1], values[0][0].conf)
    return line


def _delivery_line(no: int, row: list[Box]) -> ParsedLine | None:
    line = ParsedLine(row_no=no)
    text = _row_text(row)
    when = parse_date(text)
    if when:
        hit = [b for b in row if parse_date(b.text)] or row
        line.line_date = Cell(date.fromisoformat(when), _conf(hit))
    for outcome, words in OUTCOMES.items():
        if any(w in text for w in words):
            line.outcome = Cell(outcome, _conf(row))
            break
    amount, conf, repaired = _last_number(row)
    if amount is not None and not (when and len(row) == 1):
        line.amount = Cell(amount, conf)
        if repaired:
            line.flag(
                "amount", "repaired_digit", "A letter was read as a digit here: check the receipt."
            )
    ref = [
        b
        for b in row
        if re.search(r"[A-Za-z]", b.text) and re.search(r"\d", b.text.translate(BN_DIGITS))
    ]
    if ref:
        line.reference = Cell(ref[0].text.strip(), ref[0].conf)
    if not when and not line.outcome.value and amount is None:
        return None
    return line


def _repayment_line(no: int, row: list[Box]) -> ParsedLine | None:
    line = ParsedLine(row_no=no)
    when = parse_date(_row_text(row))
    if when:
        hit = [b for b in row if parse_date(b.text)] or row
        line.line_date = Cell(date.fromisoformat(when), _conf(hit))
    amount, conf, repaired = _last_number([b for b in row if not parse_date(b.text)])
    if amount is not None:
        line.amount = Cell(amount, conf)
        if repaired:
            line.flag(
                "amount", "repaired_digit", "A letter was read as a digit here: check the receipt."
            )
    ref = [
        b
        for b in row
        if re.search(r"[A-Za-z]", b.text) and re.search(r"\d", b.text.translate(BN_DIGITS))
    ]
    if ref:
        line.reference = Cell(ref[0].text.strip(), ref[0].conf)
    if not when and amount is None:
        return None
    return line


def check(receipt: ParsedReceipt, today: date, low_confidence: float = LOW_CONFIDENCE) -> None:
    """Attach the flags: low confidence, missing amounts, arithmetic that does not agree, an
    impossible date, an amount far out of line. Safe to run again after a person edits."""
    amounts = [ln.amount.value for ln in receipt.lines if ln.amount.value]
    typical = statistics.median(amounts) if len(amounts) >= 3 else None
    for ln in receipt.lines:
        ln.flags = [f for f in ln.flags if f["code"] == "repaired_digit"]
        for name in ("item", "quantity", "unit_price", "amount", "line_date"):
            cell = getattr(ln, name)
            if cell.value is not None and cell.conf is not None and cell.conf < low_confidence:
                ln.flag(
                    name,
                    "low_confidence",
                    "The reader was not sure about this: check it against the receipt.",
                )
        if receipt.kind == "purchase":
            if ln.amount.value is None:
                ln.flag("amount", "missing", "No amount was read for this line.")
            q, r, a = ln.quantity.value, ln.unit_price.value, ln.amount.value
            if a is not None and r is not None and q is None:
                ln.flag("quantity", "missing", "The quantity was not read: check the receipt.")
            if a is not None and q is not None and r is None:
                ln.flag("unit_price", "missing", "The rate was not read: check the receipt.")
            if q and r and a is not None and abs(q * r - a) > max(TOLERANCE_TAKA, 0.01 * a):
                ln.flag(
                    "amount",
                    "arithmetic",
                    f"Quantity times rate is {q * r:,.0f}, but the amount says {a:,.0f}.",
                )
            if typical and a and a > 10 * typical:
                ln.flag(
                    "amount",
                    "outlier",
                    "This amount is much larger than the other lines: check for an extra digit.",
                )
        elif receipt.kind in ("delivery", "repayment"):
            if ln.line_date.value is None:
                ln.flag("line_date", "missing", "No date was read for this line.")
            if receipt.kind == "repayment" and ln.amount.value is None:
                ln.flag("amount", "missing", "No amount was read for this line.")
            if receipt.kind == "delivery" and not ln.outcome.value:
                ln.flag("outcome", "missing", "Delivered, returned or failed was not read.")
        when = ln.line_date.value
        if isinstance(when, date) and when > today:
            ln.flag("line_date", "future", "This date is in the future.")
    when = receipt.receipt_date.value
    receipt.notes = [n for n in receipt.notes if not n.startswith("!")]
    if isinstance(when, date):
        if when > today:
            receipt.notes.append("!The receipt date is in the future: check it.")
        elif when.year < today.year - OLD_YEARS:
            receipt.notes.append("!The receipt date is very old: check it.")
    elif receipt.kind == "purchase":
        receipt.notes.append("!No receipt date was read.")
    total = receipt.stated_total.value
    if receipt.kind == "purchase" and total is not None and amounts:
        added = sum(amounts)
        if abs(added - total) > TOLERANCE_TAKA:
            receipt.notes.append(
                f"!The lines add up to {added:,.0f}, but the receipt total says {total:,.0f}: "
                "one amount may be misread."
            )
    if receipt.kind == "purchase" and not receipt.lines:
        receipt.notes.append("!No lines could be read: type them in beside the picture.")


def parse_receipt(
    boxes: list[Box], kind: str, today: date, low_confidence: float = LOW_CONFIDENCE
) -> ParsedReceipt:
    rows = rows_of(boxes)
    receipt = ParsedReceipt(kind=kind)
    head = _header(rows)
    receipt.receipt_date = head.get("receipt_date", Cell())
    receipt.memo_no = head.get("memo_no", Cell())

    header_index = next(
        (i for i, r in enumerate(rows) if sum(_has(r, w) for w in HEADER_WORDS.values()) >= 2),
        None,
    )
    total_index = None
    for i in range(len(rows) - 1, -1, -1):
        if (
            _has(rows[i], TOTAL_WORDS)
            and _last_number(rows[i])[0] is not None
            and i != header_index
        ):
            total_index = i
            break
    if total_index is not None:
        value, conf, repaired = _last_number(rows[total_index])
        receipt.stated_total = Cell(value, conf)
        if repaired:
            receipt.notes.append("!The total had a letter read as a digit: check it.")
    start = (header_index + 1) if header_index is not None else 0
    end = total_index if total_index is not None else len(rows)
    receipt.supplier = _supplier(
        rows, header_index if header_index is not None else min(2, len(rows))
    )
    columns = _columns(rows[header_index]) if header_index is not None else {}

    number = 0
    for row in rows[start:end]:
        if header_index is None and (
            parse_date(_row_text(row))
            and not any(_is_numberish(b.text) for b in row if not parse_date(b.text))
        ):
            continue  # a date or memo line, not a table row
        if header_index is None and _has(row, MEMO_WORDS):
            continue
        number += 1
        if kind == "purchase":
            line = _purchase_line(number, row, columns)
        elif kind == "delivery":
            line = _delivery_line(number, row)
        else:
            line = _repayment_line(number, row)
        if line is None:
            number -= 1
            continue
        receipt.lines.append(line)
    if header_index is None and receipt.lines and kind == "purchase":
        receipt.notes.append(
            "The column headings were not found: columns were guessed from the numbers."
        )
    check(receipt, today, low_confidence)
    return receipt
