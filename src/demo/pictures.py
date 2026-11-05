"""Draw receipts and parcel slips that look like a phone photo of a real paper.

Purpose: the demonstration needs a picture behind every receipt, so the Records Desk screen
    shows a photo beside the table the way it does in real use. Each picture is drawn from the
    receipt's own lines (a printed cash memo with a wholesaler's letterhead, or a parcel
    dispatch report), then given the look of a photograph: paper tint, a slight tilt, a soft
    shadow, grain and JPEG compression. Wholesaler names, addresses and phone numbers are
    invented.
Owner role: D (full-stack).
Implements: the demonstration database for the project video.
"""

from __future__ import annotations

import io
import random
from datetime import date
from pathlib import Path
from typing import Any

from src.demo.shopup_data import ReceiptPlan
from src.receipts.samples import BN_DIGITS, FONTS, _indian

AREAS = [
    "Moghbazar",
    "Chawkbazar",
    "Katabon",
    "Nawabpur",
    "Mouchak",
    "Islampur",
    "Patenga",
    "Kandirpar",
]


def _digits(text: str, bn: bool) -> str:
    return text.translate(BN_DIGITS) if bn else text


def _pdf(height: float) -> Any:
    from fpdf import FPDF

    pdf = FPDF(unit="pt", format=(420, height))
    pdf.set_auto_page_break(False)
    pdf.add_font("inter", "", str(FONTS / "Inter-Regular.ttf"))
    pdf.add_font("inter", "B", str(FONTS / "Inter-Bold.ttf"))
    pdf.add_font("bn", "", str(FONTS / "NotoSansBengali-Regular.ttf"))
    pdf.add_font("bn", "B", str(FONTS / "NotoSansBengali-Bold.ttf"))
    pdf.set_text_shaping(True)
    pdf.add_page()
    return pdf


def _to_image(pdf: Any, scale: float = 2.2) -> Any:
    import pypdfium2 as pdfium

    page = pdfium.PdfDocument(bytes(pdf.output()))[0]
    return page.render(scale=scale).to_pil().convert("RGB")


def _scribble(pdf: Any, x: float, y: float, rng: random.Random) -> None:
    """A hand-signed look: a few quick pen strokes."""
    pdf.set_draw_color(40, 55, 120)
    pdf.set_line_width(0.9)
    px, py = x, y
    for _ in range(9):
        nx, ny = px + rng.uniform(5, 13), y + rng.uniform(-9, 9)
        pdf.line(px, py, nx, ny)
        px, py = nx, ny
    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.4)


def memo_image(plan: ReceiptPlan, buyer: str, rng: random.Random) -> Any:
    """A printed cash memo from a wholesaler."""
    bn = plan.language == "bn"
    face = "bn" if bn else "inter"
    lines = plan.lines
    height = 250 + 25 * len(lines)
    pdf = _pdf(height)
    labels = (
        (
            "ক্যাশ মেমো",
            "মেমো নং",
            "তারিখ",
            "মেসার্স",
            "বিবরণ",
            "পরিমাণ",
            "দর",
            "টাকা",
            "মোট",
            "গ্রহীতার স্বাক্ষর",
        )
        if bn
        else (
            "CASH MEMO",
            "Memo No",
            "Date",
            "M/s",
            "Item",
            "Qty",
            "Rate",
            "Amount",
            "Total",
            "Received by",
        )
    )
    area = AREAS[sum(map(ord, plan.supplier)) % len(AREAS)]
    seedling = sum(map(ord, plan.supplier))
    phone = f"017{seedling % 90 + 10:02d}-{(seedling * 7919) % 900000 + 100000}"
    pdf.set_text_color(25, 25, 40)
    pdf.set_font("inter", "B", 17)
    pdf.set_xy(15, 20)
    pdf.cell(390, 22, plan.supplier, align="C")
    pdf.set_font("inter", "", 9)
    pdf.set_xy(15, 44)
    pdf.cell(390, 12, f"{area} Wholesale Market  |  Mobile: {phone}", align="C")
    pdf.set_draw_color(25, 25, 40)
    pdf.rect(150, 62, 120, 20)
    pdf.set_font(face, "B", 11)
    pdf.set_xy(150, 64)
    pdf.cell(120, 16, labels[0], align="C")
    pdf.set_font(face, "", 11)
    pdf.set_xy(20, 92)
    pdf.cell(190, 16, f"{labels[1]}: {_digits(plan.memo_no, bn)}")
    pdf.set_xy(220, 92)
    pdf.cell(180, 16, f"{labels[2]}: {_digits(plan.day.strftime('%d/%m/%Y'), bn)}", align="R")
    pdf.set_xy(20, 112)
    pdf.cell(380, 16, f"{labels[3]}: {buyer}")
    y = 140
    cols = [(20, 175, "L"), (195, 55, "R"), (255, 65, "R"), (325, 75, "R")]
    pdf.set_font(face, "B", 11)
    for (x, w, a), text in zip(cols, labels[4:8]):
        pdf.set_xy(x, y)
        pdf.cell(w, 16, text, align=a)
    pdf.line(20, y + 19, 400, y + 19)
    pdf.set_font(face, "", 11)
    y += 25
    for ln in lines:
        qty = _digits(f"{ln['quantity']:g}", bn) + ("" if bn else f" {ln['unit']}")
        cells = [
            ln["item"],
            qty,
            _digits(_indian(ln["unit_price"]), bn),
            _digits(_indian(ln["amount_bdt"]), bn),
        ]
        for (x, w, a), text in zip(cols, cells):
            pdf.set_xy(x, y)
            pdf.cell(w, 16, text, align=a)
        y += 24
    pdf.line(20, y, 400, y)
    pdf.set_font(face, "B", 12)
    pdf.set_xy(195, y + 6)
    pdf.cell(125, 18, f"{labels[8]}:", align="R")
    pdf.set_xy(325, y + 6)
    pdf.cell(75, 18, _digits(_indian(plan.total), bn), align="R")
    pdf.set_font(face, "", 9)
    pdf.set_xy(20, y + 44)
    pdf.cell(150, 12, labels[9])
    pdf.line(20, y + 41, 130, y + 41)
    _scribble(pdf, 30, y + 33, rng)
    return _to_image(pdf)


def slip_image(plan: ReceiptPlan, shop_name: str, rng: random.Random) -> Any:
    """A parcel dispatch report: each parcel, what happened to it, and any cash on delivery."""
    lines = plan.lines
    pdf = _pdf(190 + 22 * len(lines))
    pdf.set_text_color(25, 25, 40)
    pdf.set_font("inter", "B", 15)
    pdf.set_xy(15, 20)
    pdf.cell(390, 20, "PARCEL DISPATCH REPORT", align="C")
    pdf.set_font("inter", "", 10)
    pdf.set_xy(15, 46)
    pdf.cell(390, 14, shop_name, align="C")
    pdf.set_xy(15, 64)
    pdf.cell(
        390,
        14,
        f"Report no. {plan.memo_no}   |   Week ending {plan.day.strftime('%d/%m/%Y')}",
        align="C",
    )
    cols = [(20, 88, "L"), (110, 100, "L"), (215, 80, "L"), (300, 100, "R")]
    y = 96
    pdf.set_font("inter", "B", 10)
    for (x, w, a), text in zip(cols, ("Date", "Parcel no.", "Result", "COD (BDT)")):
        pdf.set_xy(x, y)
        pdf.cell(w, 14, text, align=a)
    pdf.line(20, y + 17, 400, y + 17)
    pdf.set_font("inter", "", 10)
    y += 22
    for ln in lines:
        day = date.fromisoformat(ln["line_date"]).strftime("%d/%m/%Y")
        cod = _indian(ln["amount_bdt"]) if ln.get("amount_bdt") else "-"
        for (x, w, a), text in zip(cols, (day, ln["reference"], ln["outcome"].capitalize(), cod)):
            pdf.set_xy(x, y)
            pdf.cell(w, 14, text, align=a)
        y += 21
    pdf.line(20, y, 400, y)
    pdf.set_font("inter", "B", 10)
    pdf.set_xy(20, y + 6)
    pdf.cell(380, 14, f"Total parcels: {len(lines)}", align="R")
    return _to_image(pdf)


def photograph(image: Any, rng: random.Random, look: str = "photo") -> bytes:
    """JPEG bytes of the paper as a phone camera would see it. `look`: scan (a flat scan) or
    photo (tilt, shadow, grain, compression)."""
    import numpy as np
    from PIL import Image, ImageEnhance, ImageFilter

    paper = ImageEnhance.Brightness(image).enhance(rng.uniform(0.93, 0.98))
    if look == "scan":
        out = paper
    else:
        pad = 60
        desk = (rng.randint(150, 185), rng.randint(130, 160), rng.randint(105, 135))
        canvas = Image.new("RGB", (paper.width + 2 * pad, paper.height + 2 * pad), desk)
        shadow = Image.new("L", canvas.size, 0)
        shadow.paste(120, (pad + 8, pad + 10, pad + paper.width + 8, pad + paper.height + 10))
        shadow = shadow.filter(ImageFilter.GaussianBlur(14))
        canvas.paste(Image.new("RGB", canvas.size, (30, 25, 20)), mask=shadow)
        canvas.paste(paper, (pad, pad))
        out = canvas.rotate(
            rng.uniform(-1.6, 1.6), resample=Image.BICUBIC, expand=True, fillcolor=desk
        )
        out = ImageEnhance.Contrast(out).enhance(rng.uniform(0.9, 1.0))
        arr = np.asarray(out).astype("float32")
        yy, xx = np.mgrid[0 : arr.shape[0], 0 : arr.shape[1]]
        vignette = 1 - 0.22 * (
            ((xx / arr.shape[1] - 0.5) ** 2 + (yy / arr.shape[0] - 0.5) ** 2) * 2
        )
        arr = arr * vignette[..., None] + np.random.default_rng(rng.randint(0, 10_000)).normal(
            0, 3.5, arr.shape
        )
        out = Image.fromarray(arr.clip(0, 255).astype("uint8")).filter(
            ImageFilter.GaussianBlur(0.5)
        )
    buffer = io.BytesIO()
    out.save(buffer, "JPEG", quality=rng.randint(78, 88))
    return buffer.getvalue()


def save_preview(path: Path, data: bytes) -> None:
    path.write_bytes(data)
