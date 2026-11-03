"""The printable consent and registration form, as a PDF.

Purpose: a company prints this, the merchant reads and signs it, and a photo or scan comes back
    to be read and checked. Two kinds: a form PREFILLED with the merchant details a Credit
    Officer typed in (it carries the registration reference), and a BLANK form the merchant
    fills by hand (it carries a unique form serial).
Owner role: D (full-stack).
Implements: Phase 2 of the unified platform plan (sections 8 to 10).

How it is made: fpdf2 with HarfBuzz text shaping (uharfbuzz), so Bangla conjuncts join the way
they should, and the fonts in src/onboarding/fonts (Noto Sans Bengali and Inter, both under the
SIL Open Font Licence). Every detail sits on its own line as a printed English label (with the
Bangla label under it) and a value or an underline to its right, so that the reader of a scan
(src/extraction/) can find a label and take the text beside it.

A version that is not approved is stamped across every page: DRAFT - NOT APPROVED FOR LEGAL USE.
The registration reference is printed as text and as a QR code; the text is what the reader
relies on, the QR is a convenience.
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

import segno
from fpdf import FPDF

from src.onboarding import consent_text as text

FONT_DIR = Path(__file__).with_name("fonts")
INK = (17, 27, 66)
MUTED = (93, 107, 130)
LINE = (120, 130, 150)
WATERMARK = (225, 228, 235)
DRAFT_NOTICE = "DRAFT - NOT APPROVED FOR LEGAL USE"

LABEL_W = 62  # mm, the label column
VALUE_X = 15 + LABEL_W + 3


class _Form(FPDF):
    def __init__(self, *, ref: str, template: str, draft: bool, footer_note: str) -> None:
        super().__init__(format="A4")
        self.ref, self.template, self.draft, self.footer_note = ref, template, draft, footer_note
        self.set_margins(15, 14, 15)
        self.set_auto_page_break(True, margin=18)
        for family, style, name in (
            ("Inter", "", "Inter-Regular.ttf"),
            ("Inter", "B", "Inter-Bold.ttf"),
            ("Bn", "", "NotoSansBengali-Regular.ttf"),
            ("Bn", "B", "NotoSansBengali-Bold.ttf"),
        ):
            self.add_font(family, style, str(FONT_DIR / name))
        self.set_text_shaping(True)
        self.set_title("Consent to use shop records")

    def header(self) -> None:
        if self.draft:
            with self.rotation(angle=40, x=105, y=150):
                self.set_font("Inter", "B", 30)
                self.set_text_color(*WATERMARK)
                self.text(18, 150, DRAFT_NOTICE)
        self.set_text_color(*INK)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font("Inter", "", 7.5)
        self.set_text_color(*MUTED)
        draft = f"  |  {DRAFT_NOTICE}" if self.draft else ""
        self.cell(
            0,
            4,
            f"{self.footer_note}  |  {self.template}  |  Page {self.page_no()}/{{nb}}{draft}",
            align="C",
        )


BENGALI = re.compile(r"([ঀ-৿‌‍]+(?:[ ]+[ঀ-৿‌‍]+)*)")


def _runs(value: str) -> list[tuple[str, bool]]:
    """Split text into runs of Bangla and of everything else, so each run gets the font that
    has its letters (a font without a fallback shapes Bangla correctly)."""
    return [(part, bool(BENGALI.fullmatch(part))) for part in BENGALI.split(value) if part]


def _write(
    pdf: _Form,
    value: str,
    *,
    size: float,
    bold: bool = False,
    height: float = 5,
    bn_size: float | None = None,
) -> None:
    """Write mixed English and Bangla text from the current position, wrapping as needed."""
    for run, is_bn in _runs(value):
        pdf.set_font(
            "Bn" if is_bn else "Inter", "B" if bold else "", (bn_size or size) if is_bn else size
        )
        pdf.write(height, run)


def _qr_png(value: str) -> io.BytesIO:
    buffer = io.BytesIO()
    segno.make(value, error="l", version=3).save(buffer, kind="png", scale=5, border=4)
    buffer.seek(0)
    return buffer


def _heading(pdf: _Form, en: str, bn: str) -> None:
    pdf.ln(2)
    pdf.set_text_color(*INK)
    pdf.set_x(15)
    _write(pdf, en, size=10.5, bold=True, height=5.2)
    pdf.ln(5.4)
    pdf.set_x(15)
    _write(pdf, bn, size=10, bold=True, height=5.4)
    pdf.ln(5.6)


def _paragraphs(pdf: _Form, en: list[str], bn: list[str]) -> None:
    pdf.set_text_color(*INK)
    for paragraph in en:
        pdf.set_x(15)
        _write(pdf, paragraph, size=9, height=4.5)
        pdf.ln(5.3)
    for paragraph in bn:
        pdf.set_x(15)
        _write(pdf, paragraph, size=9, height=5)
        pdf.ln(5.8)


def _field_row(pdf: _Form, label_en: str, label_bn: str, value: str | None, required: bool) -> None:
    """A label (English, with the Bangla under it) and a value or underline on the same line."""
    top = pdf.get_y()
    if top > 262:
        pdf.add_page()
        top = pdf.get_y()
    pdf.set_text_color(*INK)
    pdf.set_xy(15, top)
    _write(pdf, label_en + (" *" if required else ""), size=9, bold=required, height=5)
    pdf.set_text_color(*MUTED)
    pdf.set_xy(15, top + 4.6)
    _write(pdf, label_bn, size=7.5, height=4)
    pdf.set_text_color(*INK)
    pdf.set_xy(VALUE_X, top)
    _write(pdf, (value or "")[:60], size=10, height=5)
    pdf.set_draw_color(*LINE)
    pdf.line(VALUE_X, top + 8.2, 195, top + 8.2)
    pdf.set_y(top + 11)


def _checkbox(pdf: _Form, en: str, bn: str) -> None:
    top = pdf.get_y()
    if top > 268:
        pdf.add_page()
        top = pdf.get_y()
    pdf.set_draw_color(*INK)
    pdf.rect(15, top + 0.4, 4.2, 4.2)
    pdf.set_left_margin(22)
    pdf.set_xy(22, top)
    pdf.set_text_color(*INK)
    _write(pdf, en, size=9, height=4.6)
    pdf.ln(4.8)
    pdf.set_x(22)
    pdf.set_text_color(*MUTED)
    _write(pdf, bn, size=8.5, height=4.6)
    pdf.ln(5.8)
    pdf.set_left_margin(15)


def build_consent_pdf(
    *,
    org_name: str,
    org_contact: str,
    reference: str,
    form_kind: str,  # prefilled | blank
    details: dict[str, Any] | None,
    template_version: str,
    template_approved: bool,
    retention: str,
    valid_days: int,
    issued_by: str,
    issued_on: str,
    district_labels: dict[str, str] | None = None,
) -> bytes:
    """The consent form as PDF bytes. `details` is the merchant's entered data (prefilled) or
    None (blank). `reference` is the registration reference or the blank form's serial."""
    prefilled = form_kind == "prefilled"
    pdf = _Form(
        ref=reference,
        template=template_version,
        draft=not template_approved,
        footer_note=f"{org_name}  |  {'Ref' if prefilled else 'Serial'} {reference}",
    )
    pdf.alias_nb_pages()
    pdf.add_page()

    # --- title block -----------------------------------------------------------------
    pdf.set_text_color(*INK)
    pdf.set_xy(15, 14)
    _write(pdf, "Merchant registration and consent", size=15, bold=True, height=7)
    pdf.ln(7.5)
    _write(pdf, "মার্চেন্ট নিবন্ধন ও সম্মতি", size=12, bold=True, height=7)
    pdf.ln(7.5)
    _write(pdf, org_name, size=11, bold=True, height=6)
    pdf.ln(6.5)
    pdf.set_text_color(*MUTED)
    _write(pdf, f"Issued {issued_on} by {issued_by}", size=8, height=4)
    pdf.ln(5)
    pdf.image(_qr_png(reference), x=165, y=13, w=28)
    block_bottom = max(pdf.get_y(), 45)
    pdf.set_y(block_bottom + 1)

    label_en, label_bn = text.REFERENCE_LABEL if prefilled else text.SERIAL_LABEL
    _field_row(pdf, label_en, label_bn, reference, True)

    # --- merchant details ------------------------------------------------------------
    _heading(pdf, "Merchant details  (* required)", "মার্চেন্টের তথ্য  (* আবশ্যক)")
    values = dict(details or {})
    if district_labels and values.get("district") in district_labels:
        values["district"] = district_labels[values["district"]]
    for key, en, bn, required in text.DETAIL_FIELDS:
        raw = values.get(key)
        _field_row(
            pdf, en, bn, str(raw) if (prefilled and raw not in (None, "")) else None, required
        )

    # --- the eleven sections ---------------------------------------------------------
    for section in text.render_sections(
        org=org_name, org_contact=org_contact, retention=retention, valid_days=valid_days
    ):
        title_en, title_bn = section["title"]
        _heading(pdf, f"{section['no']}. {title_en}", f"{section['no']}. {title_bn}")
        _paragraphs(pdf, section["en"], section["bn"])

    # --- agreement boxes (all empty: the merchant ticks) -----------------------------
    _heading(
        pdf,
        "I agree that these kinds of records may be used (tick each one you agree to)",
        "আমি এই ধরনের রেকর্ড ব্যবহারে রাজি (যেগুলোতে রাজি সেগুলোতে টিক দিন)",
    )
    for _key, (en, bn) in text.CATEGORIES.items():
        _checkbox(pdf, en, bn)
    _heading(
        pdf,
        "Optional. Each is separate; leaving one empty changes nothing about the rest.",
        "ঐচ্ছিক। প্রতিটি আলাদা; কোনোটি ফাঁকা রাখলে বাকিগুলোর কিছু বদলায় না।",
    )
    for _key, (en, bn) in text.OPTIONAL_PURPOSES.items():
        _checkbox(pdf, en, bn)

    # --- signature block -------------------------------------------------------------
    if pdf.get_y() > 175:  # keep the signature block on one page
        pdf.add_page()
    _heading(pdf, "Signature", "সই")
    for key, en, bn in text.SIGNATURE_FIELDS:
        height_before = pdf.get_y()
        _field_row(pdf, en, bn, None, True)
        if key == "signature":
            pdf.set_y(height_before + 18)  # room to sign
    _field_row(pdf, "Staff member's name", "কর্মীর নাম", issued_by if prefilled else None, False)
    _field_row(pdf, "Staff signature", "কর্মীর সই", None, False)

    pdf.set_text_color(*MUTED)
    pdf.set_x(15)
    _write(
        pdf,
        "CredLens supports a person's decision; it never approves or refuses credit by itself. "
        "Keep your copy of this form.",
        size=7.5,
        height=3.8,
    )
    return bytes(pdf.output())
