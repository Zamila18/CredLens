"""Phase 2: merchant registration with paper consent, reading of the signed form, verification.

Owner role: D (full-stack).
Implements: acceptance scenarios 4 and 5 (docs: the implementation plan).

The signed forms here are the PDFs our own endpoint produces (a digital PDF is read from its
text layer, no OCR) and scripted OCR results standing in for a photographed, hand-filled form
(the real EasyOCR engine is exercised by tools, not by the unit tests: it takes minutes).
"""

from __future__ import annotations

import copy
import io
import json

import pypdfium2 as pdfium
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.accounts import service
from src.accounts.bootstrap_platform_admins import bootstrap
from src.config import load_config
from src.db import models as db
from src.db.models import create_tables, make_engine
from src.extraction.engine import Box, FakeOcrEngine
from src.extraction.service import process_job
from src.intake.consent import consent_state
from src.onboarding import consent_text as text
from tests.test_accounts_phase1 import STRONG, client, company_body, join_body, sign_in

DETAILS = {
    "shop_name": "Bhai Bhai Store",
    "owner_name": "Abdul Karim",
    "owner_mobile": "01711111111",
    "district": "Dhaka",
    "area": "Kawran Bazar",
    "shop_type": "grocery",
    "ownership_type": "sole_proprietor",
}
ADMIN_ENV = {
    "CREDLENS_PLATFORM_ADMIN_1_EMAIL": "root@credlens.example",
    "CREDLENS_PLATFORM_ADMIN_1_PASSWORD": "Cedar-Lake-2049!",
}


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    patcher = pytest.MonkeyPatch()
    patcher.setenv("CREDLENS_SECRET_KEY", "k" * 40)
    for key, value in ADMIN_ENV.items():
        patcher.setenv(key, value)
    config = copy.deepcopy(load_config())
    config["auth"]["rate_limit"].update(
        register_per_ip=500,
        login_per_ip=500,
        login_per_identifier=500,
        invite_check_per_ip=500,
        invite_check_per_identifier=500,
    )
    config["documents"]["upload_dir"] = str(tmp_path_factory.mktemp("uploads"))
    url = "sqlite:///" + (tmp_path_factory.mktemp("phase2") / "p2.db").as_posix()
    create_tables(url)
    engine = make_engine(url)
    from src.api.main import app
    from src.api.state import Services

    services = Services(config=config, engine=engine)
    app.state.services = services
    with Session(engine) as session:
        bootstrap(session, config, ADMIN_ENV)
        session.commit()
    yield type("World", (), {"config": config, "engine": engine, "services": services})
    del app.state.services
    engine.dispose()
    patcher.undo()


@pytest.fixture(scope="module")
def team(world):
    """Padma: an owner officer, a second officer, an FSR. Sagar: one officer only."""
    anon = client()
    assert anon.post("/auth/register/company", json=company_body()).status_code == 201
    owner = sign_in("rina@padma.example")
    code = owner.post("/org/invitations", json={"role": "credit_officer"}).json()["code"]
    second = join_body(
        code,
        role="credit_officer",
        full_name="Nasrin Sultana",
        email="nasrin@padma.example",
        mobile="01733333333",
        employee_id="E-2001",
        territory="",
    )
    assert anon.post("/auth/register/join", json=second).status_code == 201
    fsr_code = owner.post("/org/invitations", json={"role": "fsr"}).json()["code"]
    assert anon.post("/auth/register/join", json=join_body(fsr_code)).status_code == 201
    assert (
        anon.post(
            "/auth/register/company",
            json=company_body(
                full_name="Joya Begum",
                email="joya@sagar.example",
                mobile="01800000001",
                legal_name="Sagar Finance Limited",
                trading_name="Sagar Finance",
                registration_number="NBFI-77-001",
                org_type="nbfi",
                official_email="info@sagar.example",
                website="",
            ),
        ).status_code
        == 201
    )
    return type(
        "Team",
        (),
        {
            "owner": owner,
            "second": sign_in("nasrin@padma.example"),
            "fsr": sign_in("karim@padma.example"),
            "solo": sign_in("joya@sagar.example"),
        },
    )


def read_queued(world, reg_id: str, pages=None) -> None:
    with Session(world.engine) as session:
        job = session.scalar(
            select(db.ExtractionJob).where(
                db.ExtractionJob.registration_id == reg_id, db.ExtractionJob.status == "queued"
            )
        )
        process_job(session, world.config, FakeOcrEngine(pages or [[]]), job.job_id)


def pdf_text(data: bytes) -> str:
    pdf = pdfium.PdfDocument(data)
    return "\n".join(p.get_textpage().get_text_range() for p in pdf)


def fields_of(c: TestClient, reg_id: str) -> dict:
    return {f["key"]: f for f in c.get(f"/registrations/{reg_id}/extraction").json()["fields"]}


# --- scenario 4: manual details, prefilled PDF, signed upload, review, verification --------


def test_registration_draft_makes_a_merchant_without_consent(world, team):
    made = team.owner.post("/registrations", json=DETAILS)
    assert made.status_code == 201, made.text
    reg = made.json()
    assert (
        reg["status"] == "draft" and reg["method"] == "manual" and reg["reg_ref"].startswith("MR-")
    )
    assert reg["merchant_id"] and reg["details"]["owner_mobile"] == "+8801711111111"
    with Session(world.engine) as session:
        merchant = session.get(db.Merchant, reg["merchant_id"])
        profile = session.get(db.MerchantProfile, reg["merchant_id"])
        assert merchant.organization_id and profile.owner_name == "Abdul Karim"
        valid, _ = consent_state(session, reg["merchant_id"], service.now().date())
        assert not valid  # nobody is assessable before the signed form is verified


def test_mandatory_details_are_named_and_optional_ones_are_not_needed(world, team):
    bad = team.owner.post("/registrations", json={"shop_name": "X", "district": "Atlantis"})
    assert bad.status_code == 422
    fields = bad.json()["detail"]["fields"]
    for key in ("owner_name", "owner_mobile", "area", "shop_type", "ownership_type", "district"):
        assert key in fields, key
    assert "legal_name" not in fields and "trade_license_number" not in fields
    for forbidden in ("nid", "national_id", "bank_account"):
        extra = team.owner.post("/registrations", json={**DETAILS, forbidden: "1"})
        assert extra.status_code == 422  # no such field exists to be collected


def test_the_prefilled_pdf_carries_the_details_the_reference_and_a_draft_stamp(world, team):
    reg = team.owner.post("/registrations", json={**DETAILS, "shop_name": "Pdf Store"}).json()
    pdf = team.owner.get(f"/registrations/{reg['reg_id']}/consent.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    shown = pdf_text(pdf.content)
    assert reg["reg_ref"] in shown and "Pdf Store" in shown and "Abdul Karim" in shown
    assert "NOT APPROVED FOR LEGAL USE" in shown  # the draft template says so on every page
    assert shown.count("Retention period") == 1 and "legal review" in shown.lower()
    for number in range(1, 12):  # eleven numbered sections
        assert f"{number}. " in shown
    assert team.owner.get(f"/registrations/{reg['reg_id']}").json()["status"] == "form_issued"
    # another company cannot reach it
    assert team.solo.get(f"/registrations/{reg['reg_id']}").status_code == 404
    assert team.solo.get(f"/registrations/{reg['reg_id']}/consent.pdf").status_code == 404


def test_signed_form_is_read_compared_reviewed_and_verified_by_another_officer(world, team):
    reg = team.owner.post("/registrations", json={**DETAILS, "shop_name": "Verify Store"}).json()
    rid = reg["reg_id"]
    form = team.owner.get(f"/registrations/{rid}/consent.pdf").content
    # file checks: a GIF is refused, so is a file that is too large
    gif = team.owner.post(
        f"/registrations/{rid}/signed", content=b"GIF89a....", headers={"Content-Type": "image/gif"}
    )
    assert gif.status_code == 415
    uploaded = team.owner.post(
        f"/registrations/{rid}/signed", content=form, headers={"Content-Type": "application/pdf"}
    )
    assert uploaded.status_code == 200 and uploaded.json()["status"] == "signed_uploaded"
    assert uploaded.json()["job"]["status"] == "queued" and uploaded.json()["has_document"]
    read_queued(world, rid)
    after = team.owner.get(f"/registrations/{rid}").json()
    assert after["status"] == "under_review" and after["job"]["status"] == "done"
    assert after["job"]["engine"] == "fake" and after["job"]["pages"] >= 2
    found = fields_of(team.owner, rid)
    assert (
        found["shop_name"]["state"] == "matched" and found["shop_name"]["value"] == "Verify Store"
    )
    assert found["owner_mobile"]["state"] == "matched"
    assert (
        found["reference"]["value"] == reg["reg_ref"] and found["reference"]["state"] == "matched"
    )
    assert found["signer_name"]["state"] == "missing"  # nobody wrote a name on the printout
    assert found["signature"]["value"] == "empty"  # no ink in the signature box
    assert found["tick:purchases"]["value"] == "no"  # nothing ticked yet

    # a person confirms one field and corrects another; the machine's value is kept beside it
    mobile = found["owner_mobile"]["field_id"]
    ok = team.owner.patch(f"/registrations/{rid}/fields/{mobile}", json={})
    assert ok.json()["state"] == "confirmed"
    signer = found["signer_name"]["field_id"]
    fixed = team.owner.patch(f"/registrations/{rid}/fields/{signer}", json={"value": "Abdul Karim"})
    assert fixed.json()["state"] == "corrected" and fixed.json()["reviewed_value"] == "Abdul Karim"

    # the document can be viewed (audited) by this company only
    doc = team.owner.get(f"/registrations/{rid}/document")
    assert doc.status_code == 200 and doc.content == form
    assert (
        doc.headers["content-type"] == "application/pdf"
        and "no-store" in doc.headers["cache-control"]
    )
    assert team.solo.get(f"/registrations/{rid}/document").status_code == 404
    assert team.fsr.get(f"/registrations/{rid}/document").status_code == 403

    # the uploader cannot verify while another Credit Officer exists
    body = {
        "categories": ["purchases", "deliveries", "payments"],
        "optional": ["questionnaire"],
        "signer_name": "Abdul Karim",
        "signature_checked": True,
        "reference_matches": True,
    }
    assert after["can_verify"] is False
    refused = team.owner.post(f"/registrations/{rid}/verify", json=body)
    assert refused.status_code == 403
    assert refused.json()["detail"]["code"] == "different_verifier_required"
    # the checks must be confirmed, with a person actually looking
    unchecked = team.second.post(
        f"/registrations/{rid}/verify", json={**body, "signature_checked": False}
    )
    assert (
        unchecked.status_code == 422
        and unchecked.json()["detail"]["code"] == "checks_not_confirmed"
    )
    verified = team.second.post(f"/registrations/{rid}/verify", json=body)
    assert verified.status_code == 200, verified.text
    done = verified.json()
    assert done["status"] == "active" and done["verification_mode"] == "distinct"
    assert done["optional_consents"] == ["questionnaire"] and done["signer_name"] == "Abdul Karim"
    with Session(world.engine) as session:
        valid, categories = consent_state(session, reg["merchant_id"], service.now().date())
        assert valid and set(categories) >= {"purchases", "deliveries", "payments", "questionnaire"}
        event = session.scalars(
            select(db.ConsentEvent).where(db.ConsentEvent.merchant_id == reg["merchant_id"])
        ).one()
        assert event.method == "paper_form_reference" and event.actor == done["verified_by"]
        audits = {a.action for a in session.scalars(select(db.AuditEntry))}
        assert "verify_registration_distinct" in audits and "view_signed_form" in audits
    # a closed case cannot be edited or verified again
    assert team.second.post(f"/registrations/{rid}/verify", json=body).status_code == 409


def test_a_single_officer_company_may_self_verify_and_it_is_recorded(world, team):
    reg = team.solo.post("/registrations", json=DETAILS).json()
    rid = reg["reg_id"]
    form = team.solo.get(f"/registrations/{rid}/consent.pdf").content
    team.solo.post(
        f"/registrations/{rid}/signed", content=form, headers={"Content-Type": "application/pdf"}
    )
    read_queued(world, rid)
    assert team.solo.get(f"/registrations/{rid}").json()["can_verify"] is True
    body = {
        "categories": ["purchases"],
        "signer_name": "Abdul Karim",
        "signature_checked": True,
        "reference_matches": True,
    }
    verified = team.solo.post(f"/registrations/{rid}/verify", json=body).json()
    assert verified["status"] == "active" and verified["verification_mode"] == "self_verified"


def test_a_return_asks_for_a_reason_and_allows_a_new_signed_form(world, team):
    reg = team.owner.post("/registrations", json={**DETAILS, "shop_name": "Return Store"}).json()
    rid = reg["reg_id"]
    form = team.owner.get(f"/registrations/{rid}/consent.pdf").content
    team.owner.post(
        f"/registrations/{rid}/signed", content=form, headers={"Content-Type": "application/pdf"}
    )
    read_queued(world, rid)
    assert (
        team.second.post(f"/registrations/{rid}/return", json={"reason": "short"}).status_code
        == 422
    )
    back = team.second.post(
        f"/registrations/{rid}/return", json={"reason": "The signature is cut off in the photo."}
    )
    assert back.json()["status"] == "needs_correction"
    again = team.owner.post(
        f"/registrations/{rid}/signed", content=form, headers={"Content-Type": "application/pdf"}
    )
    assert again.status_code == 200 and again.json()["status"] == "signed_uploaded"
    rejected = team.second.post(
        f"/registrations/{rid}/reject", json={"reason": "Not the shop owner who signed."}
    )
    assert rejected.json()["status"] == "rejected"
    assert (
        team.second.post(
            f"/registrations/{rid}/verify",
            json={
                "categories": ["purchases"],
                "signer_name": "X Y",
                "signature_checked": True,
                "reference_matches": True,
            },
        ).status_code
        == 409
    )


def test_withdrawal_ends_the_consent_and_blocks_new_assessment(world, team):
    reg = team.owner.post("/registrations", json={**DETAILS, "shop_name": "Withdraw Store"}).json()
    rid, merchant = reg["reg_id"], reg["merchant_id"]
    form = team.owner.get(f"/registrations/{rid}/consent.pdf").content
    team.owner.post(
        f"/registrations/{rid}/signed", content=form, headers={"Content-Type": "application/pdf"}
    )
    read_queued(world, rid)
    team.second.post(
        f"/registrations/{rid}/verify",
        json={
            "categories": ["purchases"],
            "signer_name": "Abdul Karim",
            "signature_checked": True,
            "reference_matches": True,
        },
    )
    with Session(world.engine) as session:
        assert consent_state(session, merchant, service.now().date())[0]
    assert team.fsr.post(
        f"/merchants/{merchant}/consent/withdraw", json={"reason": "phone call"}
    ).status_code in (403, 404)
    ended = team.owner.post(
        f"/merchants/{merchant}/consent/withdraw", json={"reason": "Told us by phone"}
    )
    assert ended.status_code == 200 and ended.json() == {"consents_ended": 1}
    with Session(world.engine) as session:
        assert not consent_state(session, merchant, service.now().date())[0]
    assert team.owner.get(f"/registrations/{rid}").json()["status"] == "withdrawn"
    again = team.owner.post(f"/merchants/{merchant}/consent/withdraw", json={"reason": "Again"})
    assert again.status_code == 409


# --- scenario 5: a blank form filled by hand -------------------------------------------


def _scan(ink_signature: bool) -> bytes:
    image = Image.new("RGB", (1654, 2339), "white")
    draw = ImageDraw.Draw(image)
    if ink_signature:  # scribble to the right of the signature label (its row is at y=2000)
        draw.line([(900, 2040), (1100, 2090), (1250, 2030)], fill="black", width=6)
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def _script() -> list[Box]:
    """What a reader would return for a hand-filled blank form: printed labels with handwritten
    values to their right (lower confidence), the owner's mobile left empty, the date written."""
    values = {
        "shop_name": ("Rahima Traders", 0.48),
        "owner_name": ("Rahima Begum", 0.55),
        "owner_mobile": ("01 811 222 333", 0.42),
        "district": ("Dhaka", 0.9),
        "area": ("Mirpur 10", 0.6),
        "shop_type": ("grocery", 0.8),
        "ownership_type": ("sole_proprietor", 0.7),
    }
    boxes = [
        Box("Form serial", 0.99, 100, 100, 420, 140),
        Box("CF-ABCD23", 0.9, 700, 100, 900, 140),
    ]
    y = 200
    for key, en, _bn, _req in text.DETAIL_FIELDS:
        boxes.append(Box(en + (" *" if _req else ""), 0.95, 100, y, 520, y + 40))
        if key in values and key != "owner_mobile":
            boxes.append(Box(values[key][0], values[key][1], 700, y, 1100, y + 40))
        y += 120
    for label, value in (
        ("Name of person signing", "Rahima Begum"),
        ("Signature or thumbprint", None),
        ("Date signed", "01/11/2026"),
    ):
        boxes.append(Box(label, 0.95, 100, y, 520, y + 40))
        if value:
            boxes.append(Box(value, 0.5, 700, y, 1000, y + 40))
        y += 120
    return boxes


def test_a_blank_form_has_its_own_serial_and_comes_back_filled(world, team):
    blank = team.owner.get("/registration-forms/blank")
    assert blank.status_code == 200 and blank.content.startswith(b"%PDF")
    serial = next(w for w in pdf_text(blank.content).split() if w.startswith("CF-"))
    other = team.owner.get("/registration-forms/blank").content
    assert serial not in pdf_text(other)  # every download is a different sheet
    assert "Owner's full name" in pdf_text(blank.content)

    came_back = team.owner.post(
        "/registrations/from-form", content=_scan(True), headers={"Content-Type": "image/png"}
    )
    assert came_back.status_code == 201, came_back.text
    reg = came_back.json()
    assert reg["method"] == "blank_form" and reg["merchant_id"] is None
    assert reg["status"] == "signed_uploaded"
    read_queued(world, reg["reg_id"], [_script()])
    rid = reg["reg_id"]
    after = team.owner.get(f"/registrations/{rid}").json()
    assert after["status"] == "under_review" and after["merchant_id"] is None
    found = fields_of(team.owner, rid)
    assert (
        found["shop_name"]["value"] == "Rahima Traders"
        and found["shop_name"]["state"] == "low_confidence"
    )
    assert (
        found["district"]["state"] == "extracted"
    )  # confident reading, still reviewed by a person
    assert found["owner_mobile"]["state"] == "missing"  # not written on the form: flagged
    assert found["signed_on"]["value"] == "2026-11-01"
    assert found["signature"]["value"] == "ink"  # ink in the box says nothing about whose it is
    assert after["details"]["shop_name"] == "Rahima Traders"  # suggestions only
    # no merchant, no consent, until the details are completed and a person verifies
    assert (
        team.second.post(
            f"/registrations/{rid}/verify",
            json={
                "categories": ["purchases"],
                "signer_name": "Rahima Begum",
                "signature_checked": True,
                "reference_matches": True,
            },
        ).json()["detail"]["code"]
        == "details_incomplete"
    )
    incomplete = team.owner.patch(f"/registrations/{rid}/details", json={"owner_mobile": "bad"})
    assert incomplete.status_code == 422
    fixed = team.owner.patch(
        f"/registrations/{rid}/details",
        json={"shop_name": "Rahima Traders", "owner_mobile": "01811222333", "area": "Mirpur 10"},
    )
    assert fixed.status_code == 200 and fixed.json()["merchant_id"]
    verified = team.second.post(
        f"/registrations/{rid}/verify",
        json={
            "categories": ["purchases", "payments"],
            "signer_name": "Rahima Begum",
            "signed_on": "2026-11-01",
            "signature_checked": True,
            "reference_matches": True,
        },
    )
    assert verified.status_code == 200 and verified.json()["status"] == "active"
    with Session(world.engine) as session:
        assert consent_state(session, fixed.json()["merchant_id"], service.now().date())[0]


def test_a_reading_failure_is_recorded_and_the_case_can_still_be_reviewed(world, team):
    reg = team.owner.post("/registrations", json={**DETAILS, "shop_name": "Broken Scan"}).json()
    rid = reg["reg_id"]
    team.owner.post(
        f"/registrations/{rid}/signed", content=_scan(False), headers={"Content-Type": "image/png"}
    )

    class Broken:
        name, version = "broken", "0"

        def read(self, image):
            raise RuntimeError("no model")

    with Session(world.engine) as session:
        job = session.scalar(
            select(db.ExtractionJob).where(db.ExtractionJob.registration_id == rid)
        )
        process_job(session, world.config, Broken(), job.job_id)
    status = team.owner.get(f"/registrations/{rid}").json()
    assert status["job"]["status"] == "failed" and "no model" in status["job"]["error"]
    assert status["status"] == "signed_uploaded"  # a person can still look at the document


# --- the consent document, in production -----------------------------------------------


def test_in_production_only_an_approved_template_can_be_issued(world, team, monkeypatch):
    admin = client()
    assert (
        admin.post(
            "/auth/login",
            json={
                "identifier": "root@credlens.example",
                "password": ADMIN_ENV["CREDLENS_PLATFORM_ADMIN_1_PASSWORD"],
            },
        ).status_code
        == 200
    )  # signed in before "production" makes the cookie secure (the test client is http)
    monkeypatch.setenv("CREDLENS_ENV", "production")
    blocked = team.owner.post("/registrations", json={**DETAILS, "shop_name": "Gate Store"})
    assert (
        blocked.status_code == 409 and blocked.json()["detail"]["code"] == "template_not_approved"
    )
    assert team.owner.get("/registration-forms/blank").status_code == 409
    listing = admin.get("/platform/consent-templates").json()
    assert listing[0]["version"] == text.VERSION and listing[0]["status"] == "draft"
    assert "legal" in listing[0]["note"].lower()
    for who in (team.owner, team.fsr):
        assert who.get("/platform/consent-templates").status_code == 403
    no_ref = admin.post(
        f"/platform/consent-templates/{text.VERSION}/status", json={"status": "approved"}
    )
    assert no_ref.status_code == 422 and no_ref.json()["detail"]["code"] == "legal_review_needed"
    approved = admin.post(
        f"/platform/consent-templates/{text.VERSION}/status",
        json={"status": "approved", "legal_review_ref": "Adv. R. Haque, Haque & Co., 2026-11-01"},
    )
    assert approved.json()["status"] == "approved"
    allowed = team.owner.post("/registrations", json={**DETAILS, "shop_name": "Gate Store"})
    assert allowed.status_code == 201 and allowed.json()["template_approved"] is True
    pdf = team.owner.get(f"/registrations/{allowed.json()['reg_id']}/consent.pdf")
    assert "NOT APPROVED" not in pdf_text(pdf.content)  # the stamp goes once it is approved


def test_roles_and_files_are_guarded(world, team):
    for path in ("/registrations", "/registration-forms/blank"):
        assert team.fsr.get(path).status_code == 403
    assert client().get("/registrations").status_code == 401
    big = team.owner.post(
        "/registrations/from-form",
        content=b"%PDF-" + b"0" * (9 * 1024 * 1024),
        headers={"Content-Type": "application/pdf"},
    )
    assert big.status_code == 413
    assert team.owner.post("/registrations/from-form", content=b"not a picture").status_code == 415
    assert team.owner.post("/registrations/from-form", content=b"").status_code == 422
    json.dumps(STRONG)  # (the password helper is shared with phase 1)
