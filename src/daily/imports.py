"""Read a table of daily records from a file: CSV, Excel, Word, a PDF, or a photo or scan.

Purpose: an FSR often already has the day's figures on paper or in a sheet. This turns the file
    into rows of text that the FSR then maps to columns, corrects and loads as DRAFT rows of a
    daily sheet. Nothing read here is stored as a record: it reaches the assessment only after
    the FSR reviews it, saves it as drafts and submits the sheet (src/daily/service.py).
Owner role: D (full-stack).
Implements: Phase 4 of the unified platform plan (section 13).

Methods, in order of reliability: CSV, Excel and Word tables are read exactly; a PDF with a text
layer is read from its text; a photo or a scanned PDF goes to the OCR worker (EasyOCR) and each
cell comes back with its confidence. Handwritten registers are read poorly: every row of such an
import carries its confidence and is shown for correction. Google Sheets work through an
Excel or CSV download.
"""

from __future__ import annotations

import csv
import io
import re
import statistics
from dataclasses import dataclass, field
from typing import Any

from src.extraction.engine import Box
from src.extraction.forms import rows_of
from src.extraction.pages import load_pages

MAX_ROWS = 400
MAX_COLS = 20

# Header words that suggest a field (English and Bangla), per field.
SYNONYMS: dict[str, tuple[str, ...]] = {
    "txn_date": ("date", "day", "তারিখ", "dispatched", "paid on"),
    "amount_bdt": ("amount", "total", "price", "value", "taka", "bdt", "টাকা", "মোট", "দাম", "paid"),
    "counterparty": ("supplier", "customer", "party", "vendor", "name", "সরবরাহকারী", "ক্রেতা", "loan"),
    "category": ("item", "goods", "kind", "category", "product", "পণ্য", "ধরন", "status"),
    "description": ("description", "details", "note", "বিবরণ", "reason"),
    "quantity": ("qty", "quantity", "pcs", "পরিমাণ", "সংখ্যা"),
    "unit": ("unit", "একক"),
    "unit_price": ("rate", "unit price", "per unit", "দর", "due"),
    "payment_method": ("method", "payment", "mode", "cod"),
    "payment_status": ("paid status", "state", "on time"),
    "due_date": ("due", "delivered", "মেয়াদ"),
    "note": ("remark", "remarks", "memo", "মন্তব্য"),
}


@dataclass
class Table:
    headers: list[str]
    rows: list[list[str]]
    method: str
    confidences: list[float] = field(default_factory=list)  # one per row (0 to 1), may be empty
    notes: list[str] = field(default_factory=list)

    def as_json(self) -> dict[str, Any]:
        return {
            "headers": self.headers,
            "rows": self.rows,
            "method": self.method,
            "confidences": self.confidences,
            "notes": self.notes,
        }


def _clip(table: list[list[str]]) -> list[list[str]]:
    width = min(max((len(r) for r in table), default=0), MAX_COLS)
    return [[(c or "").strip() for c in (r + [""] * width)[:width]] for r in table[: MAX_ROWS + 1]]


def _split_header(
    rows: list[list[str]], method: str, confidences: list[float] | None = None
) -> Table:
    rows = [r for r in _clip(rows) if any(c for c in r)]
    if not rows:
        return Table([], [], method, notes=["Nothing could be read from this file."])
    headers, body = rows[0], rows[1:]
    return Table(
        headers, body, method, (confidences or [])[1 : len(body) + 1] if confidences else []
    )


def from_csv(data: bytes) -> Table:
    text = data.decode("utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:4000], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    return _split_header([list(r) for r in csv.reader(io.StringIO(text), dialect)], "csv")


def from_xlsx(data: bytes) -> Table:
    from openpyxl import load_workbook

    book = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    sheet = book.worksheets[0]
    rows = []
    for row in sheet.iter_rows(values_only=True):
        rows.append(
            [
                "" if v is None else (v.date().isoformat() if hasattr(v, "date") else str(v))
                for v in row
            ]
        )
        if len(rows) > MAX_ROWS + 1:
            break
    return _split_header(rows, "xlsx")


def from_docx(data: bytes) -> Table:
    import docx

    document = docx.Document(io.BytesIO(data))
    if document.tables:
        table = max(document.tables, key=lambda t: len(t.rows))
        return _split_header([[cell.text for cell in row.cells] for row in table.rows], "docx")
    lines = [p.text for p in document.paragraphs if p.text.strip()]
    return _split_header([re.split(r"\t|\s{2,}|,", line) for line in lines], "docx")


def _table_from_boxes(boxes: list[Box], method: str) -> Table:
    """Group boxes into lines, then take each line's boxes as its cells (left to right)."""
    rows = rows_of(boxes)
    cells = [[b.text for b in row] for row in rows]
    confs = [statistics.fmean(b.conf for b in row) for row in rows]
    gap = statistics.median(b.height for b in boxes) if boxes else 0
    merged = []
    for row in rows:  # merge pieces of one cell that sit very close together
        line, last = [], None
        for box in row:
            if last is not None and box.x0 - last.x1 < gap * 0.8:
                line[-1] = line[-1] + " " + box.text
            else:
                line.append(box.text)
            last = box
        merged.append(line)
    table = _split_header(merged if merged else cells, method, confs)
    table.notes.append("Read by a machine: check every cell against the document.")
    return table


def from_document(data: bytes, mime: str, engine: Any, render_scale: float) -> Table:
    """A PDF or an image: the text layer when there is one, otherwise the OCR engine."""
    pages = load_pages(data, mime, render_scale, wanted="all")
    boxes: list[Box] = []
    method = "pdf_text"
    offset = 0.0
    for page in pages:
        found = page.native_boxes
        if found is None:
            method = "ocr"
            found = engine.read(page.image)
        height = page.image.height
        boxes.extend(Box(b.text, b.conf, b.x0, b.y0 + offset, b.x1, b.y1 + offset) for b in found)
        offset += height
    return _table_from_boxes(boxes, method)


def needs_ocr(data: bytes, mime: str) -> bool:
    """Whether reading this file needs the OCR worker (a photo, or a PDF with no text layer)."""
    if mime != "application/pdf":
        return True
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    return any(page.get_textpage().count_chars() < 200 for page in pdf)


def suggest_mapping(headers: list[str], allowed: list[str]) -> dict[str, int]:
    """field -> column index, from the header words (a person can change it)."""
    mapping: dict[str, int] = {}
    taken: set[int] = set()
    for field_name in allowed:
        words = SYNONYMS.get(field_name, ())
        for index, header in enumerate(headers):
            low = header.lower()
            if index not in taken and any(w in low for w in words):
                mapping[field_name] = index
                taken.add(index)
                break
    return mapping


def kind_of(name: str, data: bytes) -> str | None:
    """csv | xlsx | docx | pdf | image, from the first bytes and the file name."""
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n")):
        return "image"
    if data.startswith(b"PK"):
        low = name.lower()
        if low.endswith(".xlsx") or low.endswith(".xlsm"):
            return "xlsx"
        if low.endswith(".docx"):
            return "docx"
        import zipfile

        try:
            names = zipfile.ZipFile(io.BytesIO(data)).namelist()
        except zipfile.BadZipFile:
            return None
        if any(n.startswith("xl/") for n in names):
            return "xlsx"
        if any(n.startswith("word/") for n in names):
            return "docx"
        return None
    try:
        sample = data[:2000].decode("utf-8-sig")
    except UnicodeDecodeError:
        return None
    return "csv" if re.search(r"[,;\t|]", sample) else None
