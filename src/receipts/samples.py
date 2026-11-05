"""Make test receipts: printed purchase memos with known contents, then photo-like damage.

Purpose: to check the OCR reading honestly. A receipt is drawn from a known spec (so the right
    answer is known), rendered like a printed memo (English or Bangla, Latin or Bangla digits),
    then damaged the way a phone photo is: tilted, blurred, dim, noisy, compressed. The check in
    `tools/receipt_ocr_check.py` reads them with the real engine and counts what was right.
Owner role: C (assessment).
Implements: "verify the OCR to work properly" of the Records Desk redesign.
"""

from __future__ import annotations

import io
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

FONTS = Path(__file__).resolve().parents[1] / "onboarding" / "fonts"
BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")

ITEMS_EN = [
    "Miniket rice",
    "Soybean oil",
    "Sugar",
    "Red lentil",
    "Flour",
    "Salt",
    "Tea leaf",
    "Onion",
    "Powder milk",
    "Biscuit",
]
ITEMS_BN = [
    "মিনিকেট চাল",
    "সয়াবিন তেল",
    "চিনি",
    "মসুর ডাল",
    "আটা",
    "লবণ",
    "চা পাতা",
    "পেঁয়াজ",
    "গুঁড়া দুধ",
    "বিস্কুট",
]
SUPPLIERS_EN = ["Hasan Traders", "Karim Wholesale", "Padma Distribution", "City Mart Supply"]
SUPPLIERS_BN = ["হাসান ট্রেডার্স", "করিম হোলসেল", "পদ্মা ডিস্ট্রিবিউশন"]


@dataclass
class SampleLine:
    item: str
    quantity: float
    unit: str
    rate: float
    amount: float


@dataclass
class Sample:
    language: str  # en | bn
    supplier: str
    memo_no: str
    day: date
    lines: list[SampleLine]
    total: float
    damage: str = "clean"
    image: Any = field(default=None, repr=False)


def _indian(n: float) -> str:
    """12345678 -> 1,23,45,678, the grouping used on Bangladeshi receipts."""
    s = str(int(round(n)))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts + [tail])


def make_spec(rng: random.Random, language: str, today: date) -> Sample:
    items = ITEMS_BN if language == "bn" else ITEMS_EN
    suppliers = SUPPLIERS_BN if language == "bn" else SUPPLIERS_EN
    count = rng.randint(3, 6)
    lines = []
    for name in rng.sample(items, count):
        qty = rng.choice([5, 10, 12, 20, 25, 40, 50])
        rate = rng.choice([45, 60, 85, 120, 140, 165, 190, 2400])
        lines.append(SampleLine(name, qty, rng.choice(["kg", "pcs"]), rate, qty * rate))
    return Sample(
        language=language,
        supplier=rng.choice(suppliers),
        memo_no=str(rng.randint(1000, 9999)),
        day=today - timedelta(days=rng.randint(2, 60)),
        lines=lines,
        total=sum(ln.amount for ln in lines),
    )


def _digits(text: str, language: str) -> str:
    return text.translate(BN_DIGITS) if language == "bn" else text


def render(sample: Sample, scale: float = 2.0) -> Any:
    """The clean printed memo as a PIL image (drawn with a shaping PDF engine)."""
    import pypdfium2 as pdfium
    from fpdf import FPDF

    pdf = FPDF(unit="pt", format=(420, 80 + 26 * (len(sample.lines) + 6)))
    pdf.set_auto_page_break(False)
    pdf.add_font("inter", "", str(FONTS / "Inter-Regular.ttf"))
    pdf.add_font("inter", "B", str(FONTS / "Inter-Bold.ttf"))
    pdf.add_font("bn", "", str(FONTS / "NotoSansBengali-Regular.ttf"))
    pdf.add_font("bn", "B", str(FONTS / "NotoSansBengali-Bold.ttf"))
    pdf.set_text_shaping(True)
    pdf.add_page()
    bn = sample.language == "bn"
    face = "bn" if bn else "inter"
    L = sample.language
    labels = (
        ("মেমো নং", "তারিখ", "বিবরণ", "পরিমাণ", "দর", "টাকা", "মোট")
        if bn
        else ("Memo No", "Date", "Item", "Qty", "Rate", "Amount", "Total")
    )
    pdf.set_font(face, "B", 16)
    pdf.set_xy(20, 24)
    pdf.cell(380, 22, sample.supplier, align="C")
    pdf.set_font(face, "", 11)
    pdf.set_xy(20, 56)
    pdf.cell(190, 18, f"{labels[0]}: {_digits(sample.memo_no, L)}")
    pdf.set_xy(220, 56)
    pdf.cell(180, 18, f"{labels[1]}: {_digits(sample.day.strftime('%d/%m/%Y'), L)}", align="R")
    y = 88
    cols = [(20, 170, "L"), (195, 55, "R"), (255, 65, "R"), (325, 75, "R")]
    pdf.set_font(face, "B", 11)
    for (x, w, a), text in zip(cols, labels[2:6]):
        pdf.set_xy(x, y)
        pdf.cell(w, 18, text, align=a)
    pdf.line(20, y + 20, 400, y + 20)
    pdf.set_font(face, "", 11)
    y += 26
    for ln in sample.lines:
        cells = [
            ln.item,
            _digits(f"{ln.quantity:g}", L) + ("" if bn else f" {ln.unit}"),
            _digits(_indian(ln.rate), L),
            _digits(_indian(ln.amount), L),
        ]
        for (x, w, a), text in zip(cols, cells):
            pdf.set_xy(x, y)
            pdf.cell(w, 18, text, align=a)
        y += 24
    pdf.line(20, y, 400, y)
    pdf.set_font(face, "B", 12)
    pdf.set_xy(195, y + 6)
    pdf.cell(130, 20, f"{labels[6]}:", align="R")
    pdf.set_xy(325, y + 6)
    pdf.cell(75, 20, _digits(_indian(sample.total), L), align="R")
    data = bytes(pdf.output())
    page = pdfium.PdfDocument(data)[0]
    return page.render(scale=scale).to_pil().convert("RGB")


def damage(image: Any, kind: str, rng: random.Random) -> Any:
    """Make a clean render look like a phone photo. `kind`: clean | tilt | blur | dim | photo."""
    import numpy as np
    from PIL import Image, ImageEnhance, ImageFilter

    if kind == "clean":
        return image
    out = image
    if kind in ("tilt", "photo"):
        angle = rng.uniform(2, 5) * rng.choice([-1, 1])
        out = out.rotate(angle, expand=True, fillcolor=(235, 235, 232), resample=Image.BICUBIC)
    if kind in ("blur", "photo"):
        out = out.filter(ImageFilter.GaussianBlur(rng.uniform(1.0, 1.8)))
    if kind in ("dim", "photo"):
        out = ImageEnhance.Brightness(out).enhance(rng.uniform(0.55, 0.75))
        out = ImageEnhance.Contrast(out).enhance(rng.uniform(0.7, 0.9))
    if kind == "photo":
        arr = np.asarray(out).astype("float32")
        arr += np.random.default_rng(rng.randint(0, 10_000)).normal(0, 9, arr.shape)
        out = Image.fromarray(arr.clip(0, 255).astype("uint8"))
        buf = io.BytesIO()
        out.save(buf, "JPEG", quality=rng.randint(45, 70))
        out = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    return out
