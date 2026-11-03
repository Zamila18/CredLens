"""Read the fields of a consent form from OCR boxes, and compare them with what was entered.

Purpose: the form is printed by us, so every detail sits on a line as a printed English label
    with the value (typed or handwritten) to its right. This module groups boxes into lines,
    finds each label by fuzzy match (a skewed or rescaled photo still works), takes the text
    beside it, and flags what is missing, different or uncertain. It also decodes the QR code,
    suggests which agreement boxes look ticked, and checks whether the signature box has ink.
Owner role: D (full-stack).
Implements: Phase 2 of the unified platform plan (section 10).

None of this is a decision. A confident reading can still be wrong, a handwritten one often is,
and "ink in the signature box" says nothing about whose signature it is: a person looks at the
document and confirms every field and the signature (src/onboarding/registrations.py).
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from typing import Any

from src.extraction.engine import Box
from src.onboarding import consent_text as text

BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
LABEL_MATCH = 0.78  # how like a printed label a line must start to count as that label


@dataclass
class FieldResult:
    key: str
    raw: str | None
    value: str | None
    conf: float | None
    method: str  # ocr | native_pdf | qr | ink_check
    page: int | None
    bbox: tuple[float, float, float, float] | None
    expected: str | None
    state: str  # matched | extracted | missing | mismatch | low_confidence | not_given | ...


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9ঀ-৿]", "", (value or "").translate(BN_DIGITS).lower())


def digits(value: str) -> str:
    return re.sub(r"\D", "", (value or "").translate(BN_DIGITS))


def rows_of(boxes: list[Box]) -> list[list[Box]]:
    """Boxes grouped into lines (by vertical centre), each line left to right."""
    if not boxes:
        return []
    height = statistics.median(b.height for b in boxes)
    rows: list[list[Box]] = []
    for box in sorted(boxes, key=lambda b: b.yc):
        if rows and abs(box.yc - statistics.fmean(b.yc for b in rows[-1])) < 0.6 * height:
            rows[-1].append(box)
        else:
            rows.append([box])
    return [sorted(row, key=lambda b: b.x0) for row in rows]


def _row_text(row: list[Box]) -> str:
    return " ".join(b.text for b in row)


def _best_row(rows: list[list[Box]], label: str) -> tuple[list[Box] | None, float]:
    target = norm(label)
    best, best_score = None, 0.0
    for row in rows:
        prefix = norm(_row_text(row))[: len(target) + 3]
        score = SequenceMatcher(None, target, prefix).ratio()
        if score > best_score:
            best, best_score = row, score
    return (best, best_score) if best_score >= LABEL_MATCH else (None, best_score)


def _split_label(row: list[Box], label: str) -> tuple[list[Box], list[Box]]:
    """The boxes that make up the label, and the boxes after it (the value)."""
    need = len(norm(label)) * 0.85
    seen = ""
    for index, box in enumerate(row):
        seen += norm(box.text)
        if len(seen) >= need:
            return row[: index + 1], row[index + 1 :]
    return row, []


def _value_from_row(row: list[Box], label: str) -> tuple[str, float | None, tuple | None]:
    label_boxes, rest = _split_label(row, label)
    if not rest:
        # label and value in one box: cut the label's length off the text
        joined = label_boxes[-1].text
        cut = max(len(label) - 2, 0)
        tail = joined[cut:].strip(" :*_.-") if len(joined) > len(label) + 2 else ""
        if tail:
            box = label_boxes[-1]
            return tail, box.conf, (box.x0, box.y0, box.x1, box.y1)
        return "", None, None
    value = " ".join(b.text for b in rest).strip(" :*_.-|")
    conf = statistics.fmean(b.conf for b in rest)
    bbox = (
        min(b.x0 for b in rest),
        min(b.y0 for b in rest),
        max(b.x1 for b in rest),
        max(b.y1 for b in rest),
    )
    return value, conf, bbox


def parse_date(value: str) -> str | None:
    cleaned = (value or "").translate(BN_DIGITS)
    match = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", cleaned)
    if match:
        y, m, d = (int(g) for g in match.groups())
    else:
        match = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})", cleaned)
        if not match:
            return None
        d, m, y = (int(g) for g in match.groups())
        y += 2000 if y < 100 else 0
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def ink_fraction(image: Any, box: tuple[float, float, float, float], dark: int = 110) -> float:
    """Share of dark pixels in a region of the page (grey level below `dark`)."""
    import numpy as np

    x0, y0, x1, y1 = (int(max(v, 0)) for v in box)
    region = np.asarray(image.convert("L"))[y0:y1, x0:x1]
    return float((region < dark).mean()) if region.size else 0.0


def decode_qr(image: Any) -> str | None:
    """The text of a QR code on the page, if one can be found."""
    import cv2
    import numpy as np

    detector = cv2.QRCodeDetector()
    frame = np.asarray(image.convert("RGB"))
    for scale in (1.0, 0.6, 1.5):
        picture = frame if scale == 1.0 else cv2.resize(frame, None, fx=scale, fy=scale)
        value, _, _ = detector.detectAndDecode(picture)
        if value:
            return value
    # a small code in the corner: cut it out, enlarge it and read it again
    height, width = frame.shape[:2]
    corner = frame[: int(height * 0.2), int(width * 0.6) :]
    for factor in (3.0, 2.0, 4.0):
        big = cv2.resize(corner, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)
        value, _, _ = detector.detectAndDecode(big)
        if value:
            return value
    return None


def read_form(
    pages: list[Any],  # [Page] from src.extraction.pages
    boxes_by_page: dict[int, list[Box]],
    method_by_page: dict[int, str],
) -> dict[str, FieldResult]:
    """Every field of the form that can be found, as raw readings (no comparison yet)."""
    results: dict[str, FieldResult] = {}
    targets: list[tuple[str, str]] = [
        ("reference", text.REFERENCE_LABEL[0]),
        ("serial", text.SERIAL_LABEL[0]),
    ]
    targets += [(key, en) for key, en, _bn, _req in text.DETAIL_FIELDS]
    targets += [(key, en) for key, en, _bn in text.SIGNATURE_FIELDS if key != "signature"]
    for page in pages:
        rows = rows_of(boxes_by_page.get(page.number, []))
        method = method_by_page.get(page.number, "ocr")
        for key, label in targets:
            if key in results and results[key].value:
                continue
            row, _score = _best_row(rows, label)
            if row is None:
                continue
            value, conf, bbox = _value_from_row(row, label)
            results[key] = FieldResult(
                key, value, value or None, conf, method, page.number, bbox, None, "extracted"
            )
        # signature box and agreement boxes need pixels, so only on a picture of the page
        scale = page.image.width / 210.0  # pixels per millimetre if the page fills the picture
        sig_row, _ = _best_row(
            rows, dict((k, en) for k, en, _ in text.SIGNATURE_FIELDS)["signature"]
        )
        if sig_row is not None and "signature" not in results:
            label_boxes, _rest = _split_label(sig_row, "Signature or thumbprint")
            x0 = label_boxes[-1].x1 + 2 * scale
            y0 = min(b.y0 for b in sig_row) - 1 * scale
            region = (x0, y0, page.image.width * 0.97, y0 + 17 * scale)
            density = ink_fraction(page.image, region)
            results["signature"] = FieldResult(
                "signature",
                None,
                "ink" if density > 0.004 else "empty",
                None,
                "ink_check",
                page.number,
                region,
                None,
                "present" if density > 0.004 else "empty",
            )
        for key, (en, _bn) in {**text.CATEGORIES, **text.OPTIONAL_PURPOSES}.items():
            if f"tick:{key}" in results:
                continue
            row, _s = _best_row(rows, en[:30])
            if row is None:
                continue
            first = row[0]
            region = (
                first.x0 - 6.2 * scale,
                first.yc - 1.4 * scale,
                first.x0 - 2.0 * scale,
                first.yc + 1.4 * scale,
            )
            density = ink_fraction(page.image, region)
            ticked = density > 0.06
            results[f"tick:{key}"] = FieldResult(
                f"tick:{key}",
                None,
                "yes" if ticked else "no",
                None,
                "ink_check",
                page.number,
                region,
                None,
                "present" if ticked else "empty",
            )
    return results


def compare(
    found: dict[str, FieldResult],
    expected: dict[str, Any] | None,
    *,
    low_confidence_below: float,
    match_threshold: float,
) -> list[FieldResult]:
    """Set each field's state against what was entered (manual method) or on its own (blank form).

    Order of seriousness: missing, mismatch, low confidence, matched. Optional fields that were
    left empty are `not_given`, not a problem.
    """
    out: list[FieldResult] = []
    for key, _en, _bn, required in text.DETAIL_FIELDS:
        field = found.get(key) or FieldResult(
            key, None, None, None, "ocr", None, None, None, "missing"
        )
        want = (
            None
            if expected is None
            else (str(expected.get(key)) if expected.get(key) not in (None, "") else None)
        )
        field.expected = want
        if not field.value:
            field.state = "missing" if (required or want) else "not_given"
        elif want is not None:
            same = (
                digits(field.value)[-10:] == digits(want)[-10:]
                if key in ("owner_mobile", "alternate_contact", "representative_mobile")
                else SequenceMatcher(None, norm(field.value), norm(want)).ratio() >= match_threshold
            )
            if not same:
                field.state = "mismatch"
            elif (field.conf or 0) < low_confidence_below:
                field.state = "low_confidence"
            else:
                field.state = "matched"
        else:
            field.state = (
                "low_confidence" if (field.conf or 0) < low_confidence_below else "extracted"
            )
        out.append(field)
    for key in ("reference", "serial", "signer_name", "signed_on", "signature"):
        if key in found:
            field = found[key]
            if key in ("signer_name", "signed_on", "signature") and not field.value:
                field.state = "missing"
            elif key == "signed_on" and field.value:
                iso = parse_date(field.value)
                field.value = iso or field.value
                field.state = "extracted" if iso else "low_confidence"
            elif key in ("reference", "serial") and field.method != "qr":
                field.state = (
                    "low_confidence" if (field.conf or 0) < low_confidence_below else "extracted"
                )
            elif key in ("signer_name",) and (field.conf or 0) < low_confidence_below:
                field.state = "low_confidence"
            out.append(field)
        elif key in ("signer_name", "signed_on", "signature"):
            out.append(FieldResult(key, None, None, None, "ocr", None, None, None, "missing"))
    out.extend(v for k, v in found.items() if k.startswith("tick:"))
    return out
