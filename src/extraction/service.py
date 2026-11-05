"""Run a reading job: document in, fields (with confidence and a comparison) out.

Purpose: turn a stored scan, photo or PDF of a consent form into `extraction_fields` rows that a
    person then reviews. The engine and its version are recorded on the job.
Owner role: D (full-stack).
Implements: Phase 2 of the unified platform plan (section 10).

Upload -> validate (done at upload) -> text (native for a digital PDF, EasyOCR for a scan or a
photo) -> fields found next to their printed labels -> compared with what was entered ->
stored for review. Nothing here records consent or changes a merchant.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.accounts.service import now
from src.db import models as db
from src.extraction import forms
from src.extraction.engine import Box, OcrEngine
from src.extraction.pages import load_pages
from src.onboarding.registrations import read_document

log = logging.getLogger(__name__)


def process_job(session: Session, config: dict[str, Any], engine: OcrEngine, job_id: str) -> None:
    """Read one queued job. Failures are recorded on the job, never raised."""
    job = session.get(db.ExtractionJob, job_id)
    if job is None or job.status != "queued":
        return
    job.status, job.started_at, job.engine, job.engine_version = (
        "running",
        now(),
        engine.name,
        engine.version,
    )
    session.commit()
    try:
        (_read_receipt if job.purpose == "receipt" else _read)(session, config, engine, job)
        job.status = "done"
    except Exception as error:  # noqa: BLE001 - recorded on the job for the officer to see
        log.exception("Reading job %s failed", job_id)
        session.rollback()
        job = session.get(db.ExtractionJob, job_id)
        job.status, job.error = "failed", f"{type(error).__name__}: {error}"[:500]
    job.finished_at = now()
    session.commit()


def _read_receipt(
    session: Session, config: dict[str, Any], engine: OcrEngine, job: db.ExtractionJob
) -> None:
    """A receipt: read every page, build the header and table, and write them to the receipt."""
    from src.intake.policy import real_today
    from src.receipts import parse, prepare, service

    receipt = session.scalar(select(db.Receipt).where(db.Receipt.job_id == job.job_id))
    doc = session.get(db.Document, job.document_id)
    data = read_document(config, doc)
    pages = load_pages(data, doc.mime, float(config["ocr"]["render_scale"]), wanted="all")
    boxes, offset = [], 0.0
    for page in pages:
        found = (
            page.native_boxes
            if page.native_boxes is not None
            else engine.read(prepare.straighten(page.image))
        )
        boxes.extend(
            Box(b.text, b.conf, b.x0, b.y0 + offset, b.x1, b.y1 + offset) for b in found
        )
        offset += page.image.height
    low = float(config["ocr"]["low_confidence_below"])
    parsed = parse.parse_receipt(boxes, receipt.kind, real_today(config), low)
    service.apply_parsed(session, receipt, parsed)
    job.pages = len(pages)
    session.commit()


def _read(
    session: Session, config: dict[str, Any], engine: OcrEngine, job: db.ExtractionJob
) -> None:
    ocr = config["ocr"]
    doc = session.get(db.Document, job.document_id)
    reg = session.get(db.MerchantRegistration, job.registration_id)
    data = read_document(config, doc)
    pages = load_pages(data, doc.mime, float(ocr["render_scale"]))
    job.pages = len(pages)
    boxes, methods = {}, {}
    for page in pages:
        if page.native_boxes is not None:
            boxes[page.number], methods[page.number] = page.native_boxes, "native_pdf"
        else:
            boxes[page.number], methods[page.number] = engine.read(page.image), "ocr"
    found = forms.read_form(pages, boxes, methods)

    qr = forms.decode_qr(pages[0].image) if pages else None
    if qr:
        found["reference" if qr.startswith("MR-") else "serial"] = forms.FieldResult(
            "reference" if qr.startswith("MR-") else "serial",
            qr,
            qr,
            1.0,
            "qr",
            1,
            None,
            None,
            "extracted",
        )
    expected = json.loads(reg.details or "{}") if reg.method == "manual" else None
    fields = forms.compare(
        found,
        expected,
        low_confidence_below=float(ocr["low_confidence_below"]),
        match_threshold=float(ocr["match_threshold"]),
    )
    # the printed reference must be this form's: a different one is a mismatch, not a reading
    want = reg.reg_ref if reg.method == "manual" else None
    for f in fields:
        if f.key == "reference" and want and f.value:
            f.expected = want
            if forms.norm(f.value) != forms.norm(want):
                f.state = (
                    "mismatch" if (f.conf or 0) >= 0.9 or f.method == "qr" else "low_confidence"
                )
            else:
                f.state = "matched"
    session.execute(delete(db.ExtractionField).where(db.ExtractionField.job_id == job.job_id))
    for f in fields:
        session.add(
            db.ExtractionField(
                job_id=job.job_id,
                registration_id=reg.reg_id,
                key=f.key,
                raw_text=f.raw,
                value=f.value,
                confidence=f.conf,
                method=f.method,
                expected=f.expected,
                state=f.state,
                page=f.page,
                bbox=json.dumps([round(v) for v in f.bbox]) if f.bbox else None,
            )
        )
    if reg.status == "signed_uploaded":
        reg.status = "under_review"
    if reg.method == "blank_form":  # suggestions for the officer to review; nothing is created
        suggested = {
            f.key: f.value for f in fields if f.value and f.key in {k for k, *_ in _detail_keys()}
        }
        merged = {**suggested, **json.loads(reg.details or "{}")}
        reg.details = json.dumps(merged, ensure_ascii=False)
    reg.updated_at = now()
    session.commit()


def _detail_keys():
    from src.onboarding.consent_text import DETAIL_FIELDS

    return DETAIL_FIELDS


def next_queued(session: Session) -> str | None:
    return session.scalar(
        select(db.ExtractionJob.job_id)
        .where(db.ExtractionJob.status == "queued")
        .order_by(db.ExtractionJob.queued_at)
        .limit(1)
    )
