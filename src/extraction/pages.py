"""Turn an uploaded file into pages the reader can use.

Purpose: images become one page; a PDF with real text (a digital file) gives its text boxes
    directly (no OCR needed: more accurate); a scanned PDF is rendered to images for OCR.
Owner role: D (full-stack).
Implements: Phase 2 of the unified platform plan (section 10, "native PDF first, OCR for scans").
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

from PIL import Image

from src.extraction.engine import Box

Image.MAX_IMAGE_PIXELS = 60_000_000  # refuse decompression bombs
NATIVE_MIN_CHARS = 200  # fewer characters than this on a PDF page: treat it as a scan


@dataclass
class Page:
    number: int  # 1-based
    image: Any  # a PIL image (rendered for a digital PDF too, for ink checks)
    native_boxes: list[Box] | None  # set when the PDF page has a text layer


def _native_boxes(page: Any, scale: float) -> list[Box] | None:
    """The text of a digital PDF page as boxes, built character by character: a new box starts
    at a new line or after a gap wider than a couple of characters, so a printed label and the
    value beside it stay two boxes."""
    textpage = page.get_textpage()
    total = textpage.count_chars()
    if total < NATIVE_MIN_CHARS:
        return None
    height = page.get_height()
    boxes: list[Box] = []
    chars: list[str] = []
    left = right = bottom = top = 0.0
    prev_right = None

    def flush() -> None:
        value = "".join(chars).strip()
        if value:
            boxes.append(
                Box(
                    value,
                    1.0,
                    left * scale,
                    (height - top) * scale,
                    right * scale,
                    (height - bottom) * scale,
                )
            )
        chars.clear()

    for index in range(total):
        char = textpage.get_text_range(index, 1)
        cl, cb, cr, ct = textpage.get_charbox(index)
        if char in ("\r", "\n") or cr <= cl:
            flush()
            prev_right = None
            continue
        width = cr - cl
        same_line = chars and abs(((ct + cb) / 2) - ((top + bottom) / 2)) < (ct - cb) * 0.6
        near = prev_right is not None and (cl - prev_right) < max(width, 1.0) * 2.2
        if chars and not (same_line and near):
            flush()
        if not chars:
            left, bottom, right, top = cl, cb, cr, ct
        else:
            left, bottom = min(left, cl), min(bottom, cb)
            right, top = max(right, cr), max(top, ct)
        chars.append(char)
        prev_right = cr
    flush()
    return boxes


def load_pages(
    data: bytes, mime: str, render_scale: float, wanted: str = "first_and_last"
) -> list[Page]:
    """The pages to read. For a PDF of more than two pages, `first_and_last` keeps page one
    (reference and details) and the last two (agreement boxes and signature): reading every
    page of a long PDF would take minutes on a CPU."""
    if mime == "application/pdf":
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(data)
        count = len(pdf)
        numbers = list(range(count))
        if wanted == "first_and_last" and count > 2:
            numbers = sorted({0, max(count - 2, 0), count - 1})
        pages = []
        for index in numbers:
            page = pdf[index]
            image = page.render(scale=render_scale).to_pil().convert("RGB")
            pages.append(Page(index + 1, image, _native_boxes(page, render_scale)))
        return pages
    image = Image.open(io.BytesIO(data))
    image.load()
    return [Page(1, _normalise(image), None)]


def _normalise(image: Image.Image, longest: int = 2600) -> Image.Image:
    """Upright (EXIF), RGB, and not larger than needed: a phone photo is 4000 pixels wide."""
    from PIL import ImageOps

    image = ImageOps.exif_transpose(image).convert("RGB")
    if max(image.size) > longest:
        ratio = longest / max(image.size)
        image = image.resize((int(image.width * ratio), int(image.height * ratio)))
    return image
