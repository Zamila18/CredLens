# ruff: noqa: F811  (fixtures imported from another test module are redefined as arguments)
"""The Records Desk, the merchant portal and the receipt checks.

Owner role: D (full-stack).
Implements: the receipt workflow of the Records Desk redesign.

Real accounts throughout: a company's owner and second officer, a Records Desk officer, a
merchant who signs in with a Merchant ID, and a second company. The OCR engine is a fake that
returns known boxes; the real engine is measured separately (`python -m src.receipts.ocr_check`).
"""

from __future__ import annotations

import io
from datetime import date, timedelta

import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.imported import tables_for_merchants
from src.db import models as db
from src.extraction.engine import Box, FakeOcrEngine
from src.extraction.service import process_job
from src.receipts import parse
from tests.test_accounts_phase1 import client
from tests.test_registration_phase2 import active_merchant, team, world  # noqa: F401

DAY = date.today() - timedelta(days=10)


def box(text, x, y, conf=0.95, w=80):
    return Box(text, conf, x, y, x + w, y + 20)


def memo(rows, total="3,000", header=True, day=DAY, conf=None):
    """Boxes of a printed memo: supplier, memo no, date, column heads, lines, total."""
    boxes = [
        box("Hasan Traders", 100, 10, w=160),
        box("Memo No: 4657", 20, 40, w=120),
        box(f"Date: {day.strftime('%d/%m/%Y')}", 250, 40, w=130),
    ]
    if header:
        boxes += [
            box("Item", 20, 80),
            box("Qty", 170, 80),
            box("Rate", 250, 80),
            box("Amount", 330, 80),
        ]
    for i, (item, qty, rate, amount) in enumerate(rows):
        y = 110 + 30 * i
        sure = (conf or {}).get(i, 0.97)
        boxes += [
            box(item, 20, y),
            box(qty, 170, y),
            box(rate, 250, y),
            box(amount, 330, y, conf=sure),
        ]
    if total is not None:
        y = 110 + 30 * len(rows) + 20
        boxes += [box("Total:", 250, y), box(total, 330, y)]
    return boxes


GOOD = [("Sugar", "5", "165", "825"), ("Tea leaf", "25", "120", "3000")]
GOOD_TOTAL = "3,825"


# --- the reader's checks, as plain functions -----------------------------------------------


def test_a_clean_memo_is_read_into_header_and_lines_with_nothing_to_check():
    got = parse.parse_receipt(memo(GOOD, GOOD_TOTAL), "purchase", date.today())
    assert got.supplier.value == "Hasan Traders" and got.memo_no.value == "4657"
    assert got.receipt_date.value == DAY and got.stated_total.value == 3825
    assert [
        (ln.item.value, ln.quantity.value, ln.unit_price.value, ln.amount.value) for ln in got.lines
    ] == [
        ("Sugar", 5, 165, 825),
        ("Tea leaf", 25, 120, 3000),
    ]
    assert not any(ln.flags for ln in got.lines) and not got.notes


def test_a_quantity_with_its_unit_is_read_even_when_the_column_header_was_misread():
    """The real reader returned "oty" for the "Qty" header: the quantity must not be lost."""
    rows = [("Sugar", "5 kg", "165", "825"), ("Tea leaf", "25 kg", "120", "3000")]
    boxes = [
        Box("oty", 0.6, b.x0, b.y0, b.x1, b.y1) if b.text == "Qty" else b
        for b in memo(rows, GOOD_TOTAL)
    ]
    parsed = parse.parse_receipt(boxes, "purchase", DAY + timedelta(days=1), 0.75)
    assert [ln.quantity.value for ln in parsed.lines] == [5, 25]
    assert [ln.unit.value for ln in parsed.lines] == ["kg", "kg"]
    assert [ln.amount.value for ln in parsed.lines] == [825, 3000] and not parsed.notes


def test_the_arithmetic_catches_a_misread_amount_even_when_the_reader_was_sure():
    rows = [("Sugar", "5", "165", "925"), GOOD[1]]  # a 8 read as a 9, confidence still high
    got = parse.parse_receipt(memo(rows, GOOD_TOTAL), "purchase", date.today())
    first = got.lines[0]
    assert [f["code"] for f in first.flags] == ["arithmetic"] and first.flags[0]["cell"] == "amount"
    assert any("add up to 3,925" in n for n in got.notes)  # and the lines no longer match the total


def test_low_confidence_missing_amounts_and_repaired_digits_are_flagged_never_hidden():
    rows = [("Sugar", "5", "165", "8Z5"), ("Rice", "5", "120", "600"), ("Oil", "5", "", "")]
    got = parse.parse_receipt(memo(rows, None, conf={1: 0.3}), "purchase", date.today())
    codes = {(ln.row_no, f["cell"], f["code"]) for ln in got.lines for f in ln.flags}
    assert (2, "amount", "low_confidence") in codes
    assert (3, "amount", "missing") in codes
    assert parse.to_number("1O5") == (105.0, True) and parse.to_number("1,05,000") == (
        105000.0,
        False,
    )
    assert parse.to_number("৩,৫০০") == (3500.0, False) and parse.to_number("abc") == (None, False)


def test_an_impossible_date_and_an_outlier_are_flagged():
    future = date.today() + timedelta(days=5)
    rows = [
        ("A", "1", "100", "100"),
        ("B", "1", "110", "110"),
        ("C", "1", "120", "120"),
        ("D", "1", "9000", "99000"),
    ]
    got = parse.parse_receipt(memo(rows, None, day=future), "purchase", date.today())
    assert any("future" in n for n in got.notes)
    assert any(f["code"] == "outlier" for f in got.lines[3].flags)


# --- the whole workflow -----------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def scorer(world, api_world):
    from src.model.scoring import Scorer

    world.services.scorer = Scorer(api_world.config, tables=api_world.tables, saved=api_world.saved)
    yield
    world.services.scorer = None


def png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (400, 300), "white").save(buffer, "PNG")
    return buffer.getvalue()


def upload(team, world, merchant, boxes, kind="purchase"):
    sent = team.desk.post(
        f"/merchants/{merchant}/receipts",
        params={"kind": kind, "name": "memo.png"},
        content=png(),
        headers={"Content-Type": "application/octet-stream"},
    )
    assert sent.status_code == 201, sent.text
    receipt_id = sent.json()["receipt_id"]
    with Session(world.engine) as session:
        receipt = session.get(db.Receipt, receipt_id)
        process_job(session, world.config, FakeOcrEngine([boxes]), receipt.job_id)
    return receipt_id


@pytest.fixture(scope="module")
def shop(team, world):
    return active_merchant(team, world, "Receipt Store")


def purchases(world, merchant):
    with Session(world.engine) as session:
        return sorted(
            (p.category, p.amount_bdt)
            for p in session.scalars(select(db.Purchase).where(db.Purchase.merchant_id == merchant))
        )


def test_upload_is_read_and_nothing_reaches_the_records_before_publishing(team, world, shop):
    rid = upload(team, world, shop, memo(GOOD, GOOD_TOTAL))
    got = team.desk.get(f"/receipts/{rid}").json()
    assert (
        got["status"] == "extracted"
        and got["reading"] == "done"
        and got["supplier"] == "Hasan Traders"
    )
    assert [ln["amount_bdt"] for ln in got["lines"]] == [825, 3000] and got["cells_to_check"] == 0
    assert purchases(world, shop) == []  # unchecked data never reaches the score or the officers
    assert team.desk.get(f"/receipts/{rid}/document").status_code == 200
    assert team.owner.get(f"/receipts/{rid}").status_code == 200  # an officer may read
    assert team.owner.put(f"/receipts/{rid}", json={"header": {}, "lines": []}).status_code == 403
    assert team.solo.get(f"/receipts/{rid}").status_code == 404  # another company sees nothing
    assert team.solo.get(f"/receipts/{rid}/document").status_code == 404


def test_flagged_cells_must_be_acknowledged_and_corrections_clear_them(team, world, shop):
    bad = [("Sugar", "5", "165", "925"), GOOD[1]]
    rid = upload(team, world, shop, memo(bad, GOOD_TOTAL))
    got = team.desk.get(f"/receipts/{rid}").json()
    assert got["cells_to_check"] == 1 and got["notes"]
    refused = team.desk.post(f"/receipts/{rid}/publish", json={})
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "cells_need_checking"
    # the officer reads the paper, corrects the cell: the flag goes and the total agrees again
    lines = [
        {"line_id": ln["line_id"], "amount_bdt": 825 if ln["row_no"] == 1 else ln["amount_bdt"]}
        for ln in got["lines"]
    ]
    fixed = team.desk.put(f"/receipts/{rid}", json={"header": {}, "lines": lines}).json()
    assert fixed["status"] == "checked" and fixed["cells_to_check"] == 0 and not fixed["notes"]
    assert fixed["lines"][0]["confidence"]["amount_bdt"] == 1.0  # a person read it
    assert (
        team.desk.put(
            f"/receipts/{rid}", json={"header": {"stated_total": "x"}, "lines": lines}
        ).status_code
        == 422
    )
    bad_date = team.desk.put(
        f"/receipts/{rid}", json={"header": {"receipt_date": "soon"}, "lines": lines}
    )
    assert bad_date.status_code == 422
    done = team.desk.post(f"/receipts/{rid}/publish", json={})
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "published" and purchases(world, shop) == [
        ("Sugar", 825.0),
        ("Tea leaf", 3000.0),
    ]
    again = team.desk.post(f"/receipts/{rid}/publish", json={})
    assert again.status_code == 409  # a receipt is published once
    assert team.desk.put(f"/receipts/{rid}", json={"header": {}, "lines": []}).status_code == 409


def test_a_receipt_can_be_rejected_with_a_reason_and_typed_receipts_work(team, world, shop):
    rid = upload(team, world, shop, memo(GOOD, GOOD_TOTAL, header=False))
    assert team.desk.post(f"/receipts/{rid}/reject", json={"reason": "x"}).status_code == 422
    assert (
        team.desk.post(
            f"/receipts/{rid}/reject", json={"reason": "Not this shop's receipt"}
        ).json()["status"]
        == "rejected"
    )
    typed = team.desk.post(f"/merchants/{shop}/receipts/typed", json={"kind": "purchase"}).json()
    assert typed["method"] == "typed" and typed["lines"] == []
    assert team.desk.get(f"/receipts/{typed['receipt_id']}/document").status_code == 404
    saved = team.desk.put(
        f"/receipts/{typed['receipt_id']}",
        json={
            "header": {"supplier": "Rahim", "receipt_date": DAY.isoformat()},
            "lines": [{"item": "Salt", "quantity": 10, "unit_price": 30, "amount_bdt": 300}],
        },
    )
    assert saved.status_code == 200 and saved.json()["cells_to_check"] == 0
    assert team.desk.post(f"/receipts/{typed['receipt_id']}/publish", json={}).status_code == 200
    assert ("Salt", 300.0) in purchases(world, shop)
    # a shop without a verified consent takes no receipts
    reg = team.owner.post(
        "/registrations",
        json={
            "shop_name": "No Consent Store",
            "owner_name": "Z Z",
            "owner_mobile": "01711000099",
            "district": "Dhaka",
            "area": "X",
            "shop_type": "grocery",
            "ownership_type": "sole_proprietor",
        },
    ).json()
    refused = team.desk.post(
        f"/merchants/{reg['merchant_id']}/receipts/typed", json={"kind": "purchase"}
    )
    assert refused.status_code == 403


# --- the merchant's side ----------------------------------------------------------------------


def merchant_id_of(team, shop) -> str:
    got = team.owner.get(f"/merchants/{shop}/access").json()
    assert got["portal_open"] and got["portal_id"].startswith("MR-") and len(got["portal_id"]) == 12
    return got["portal_id"]


def test_the_merchant_id_is_random_signs_in_with_the_owners_name_and_is_rate_limited(
    team, world, shop
):
    portal = merchant_id_of(team, shop)
    assert (
        team.desk.get(f"/merchants/{shop}/access").status_code == 403
    )  # the slip is the officer's
    assert shop not in portal  # not the sequential shop id
    anon = client()
    wrong_name = anon.post(
        "/auth/merchant-login", json={"merchant_id": portal, "owner_name": "Somebody Else"}
    )
    wrong_id = anon.post(
        "/auth/merchant-login", json={"merchant_id": "MR-AAAA-BBBB", "owner_name": "Abdul Karim"}
    )
    assert wrong_name.status_code == wrong_id.status_code == 401
    assert (
        wrong_name.json()["detail"] == wrong_id.json()["detail"]
    )  # the same answer: nothing leaks
    ok = anon.post(
        "/auth/merchant-login",
        json={"merchant_id": portal.lower(), "owner_name": "  abdul  KARIM "},
    )
    assert ok.status_code == 200, ok.text
    me = anon.get("/auth/me").json()
    assert me["role"] == "merchant" and me["merchant_id"] == shop and not me["is_owner"]
    # a first name alone is enough when it is a whole word of the registered name
    assert (
        client()
        .post("/auth/merchant-login", json={"merchant_id": portal, "owner_name": "Karim"})
        .status_code
        == 200
    )


def test_a_merchant_reaches_only_their_own_shop(team, world, shop):
    portal = merchant_id_of(team, shop)
    other = active_merchant(team, world, "Other Store")
    me = client()
    assert (
        me.post(
            "/auth/merchant-login", json={"merchant_id": portal, "owner_name": "Abdul Karim"}
        ).status_code
        == 200
    )
    assert me.get(f"/merchants/{shop}").status_code in (200, 403)
    assert me.get(f"/merchants/{other}").status_code == 404
    for path in (
        "/receipts",
        "/merchant-reports",
        "/org/employees",
        "/org/range-policies",
        "/submissions",
    ):
        assert me.get(path).status_code in (403, 404), path
    assert me.post(f"/merchants/{shop}/assessments").status_code == 403
    assert (
        me.post(f"/merchants/{shop}/decision", json={"officer_action": "accept"}).status_code == 403
    )
    assert me.get("/portal/me").json()["shop_name"] == "Receipt Store"
    assert team.owner.get("/portal/me").status_code == 403  # staff have no portal


def test_records_published_then_reported_leave_the_score_until_answered(team, world, shop):
    portal = merchant_id_of(team, shop)
    me = client()
    me.post("/auth/merchant-login", json={"merchant_id": portal, "owner_name": "Abdul Karim"})
    records = me.get("/portal/records").json()
    assert records and all(r["lines"] for r in records)
    sugar = next(ln for r in records for ln in r["lines"] if ln["item"] == "Sugar")
    assert sugar["shown_state"] == "checked" and sugar["flags"] == [] and sugar["confidence"] == {}
    # the receipt looks right to the merchant
    rid = records[0]["receipt_id"]
    assert me.post(f"/portal/receipts/{rid}/confirm").status_code == 200

    # a proof photo and a report
    proof = me.post(
        "/portal/proof",
        params={"name": "mine.png"},
        content=png(),
        headers={"Content-Type": "application/octet-stream"},
    )
    assert proof.status_code == 201
    short = me.post(f"/portal/lines/{sugar['line_id']}/report", json={"note": "bad"})
    assert short.status_code == 422
    report = me.post(
        f"/portal/lines/{sugar['line_id']}/report",
        json={
            "note": "My copy says 725 for the sugar",
            "claimed_amount_bdt": 725,
            "proof_document_id": proof.json()["document_id"],
        },
    )
    assert report.status_code == 201, report.text
    flag_id = report.json()["flag_id"]
    assert (
        me.post(
            f"/portal/lines/{sugar['line_id']}/report", json={"note": "again, still wrong"}
        ).status_code
        == 409
    )

    with Session(world.engine) as session:  # while open, the line stays out of the score
        held = tables_for_merchants(session, [shop])["purchases"]
        assert 825.0 not in set(held["amount_bdt"]) and 3000.0 in set(held["amount_bdt"])
        # the purchase record itself is untouched: nothing is deleted
        assert ("Sugar", 825.0) in purchases(world, shop)

    open_reports = team.desk.get("/merchant-reports").json()
    mine = next(r for r in open_reports if r["flag_id"] == flag_id)
    assert (
        mine["claimed_amount_bdt"] == 725
        and mine["has_proof"]
        and mine["recorded_amount_bdt"] == 825
    )
    assert team.desk.get(f"/merchant-reports/{flag_id}/proof").status_code == 200
    assert team.solo.get(f"/merchant-reports/{flag_id}/proof").status_code == 404
    assert (
        team.owner.post(
            f"/merchant-reports/{flag_id}/resolve", json={"accept": True, "note": "ok fine"}
        ).status_code
        == 403
    )
    assert (
        team.desk.post(
            f"/merchant-reports/{flag_id}/resolve", json={"accept": True, "note": "ok"}
        ).status_code
        == 422
    )
    done = team.desk.post(
        f"/merchant-reports/{flag_id}/resolve",
        json={"accept": True, "note": "Checked your copy: corrected."},
    )
    assert done.status_code == 200 and done.json()["status"] == "accepted"
    assert ("Sugar", 725.0) in purchases(world, shop)  # the record the score reads now says 725
    with Session(world.engine) as session:
        back = tables_for_merchants(session, [shop])["purchases"]
        assert 725.0 in set(back["amount_bdt"])  # and the line is back in the score
    seen = me.get("/portal/reports").json()[0]
    assert seen["status"] == "accepted" and seen["answer"].startswith("Checked")
    state = next(
        ln for r in me.get("/portal/records").json() for ln in r["lines"] if ln["item"] == "Sugar"
    )
    assert state["shown_state"] == "corrected" and state["amount_bdt"] == 725
    assert (
        team.desk.post(
            f"/merchant-reports/{flag_id}/resolve", json={"accept": False, "note": "twice"}
        ).status_code
        == 409
    )


def test_a_merchant_applies_and_the_officers_see_it(team, world, shop):
    portal = merchant_id_of(team, shop)
    me = client()
    me.post("/auth/merchant-login", json={"merchant_id": portal, "owner_name": "Abdul Karim"})
    status = me.get("/portal/application").json()
    assert status["can_apply"] and not status["has_application"] and status["purposes"]
    bad = me.post(
        "/portal/application", json={"requested_amount_bdt": -5, "purpose": status["purposes"][0]}
    )
    assert bad.status_code == 422
    made = me.post(
        "/portal/application",
        json={"requested_amount_bdt": 40000, "purpose": status["purposes"][0]},
    )
    assert made.status_code == 201, made.text
    got = made.json()
    assert (
        got["has_application"] and got["status"] == "received" and "score" not in str(got).lower()
    )
    assert (
        me.post(
            "/portal/application",
            json={"requested_amount_bdt": 1000, "purpose": status["purposes"][0]},
        ).status_code
        == 409
    )
    apps = team.owner.get("/applications").json()
    mine = next(a for a in apps if a["merchant_id"] == shop)
    assert mine["submitted_by_merchant"] is True and mine["requested_amount_bdt"] == 40000
    bell = team.owner.get("/notifications").json()
    assert any("applied for a loan" in n["text"] for n in bell)
    assert team.solo.get("/applications").json() == []
    # an assessment was stored for the officers, with a plain result
    stored = team.owner.get(f"/merchants/{shop}/assessments").json()
    assert stored and stored[0]["status"] == "current"


# --- straightening a tilted photo -----------------------------------------------------------


def test_a_tilted_photo_is_straightened_and_a_blank_one_is_left_alone():
    import random

    from src.receipts import prepare, samples

    spec = samples.make_spec(random.Random(4), "en", date.today())
    clean = samples.render(spec)
    for angle in (3.0, -4.0):
        tilted = clean.rotate(angle, expand=True, fillcolor=(235, 235, 232), resample=Image.BICUBIC)
        assert abs(prepare.estimate_tilt(tilted) + angle) < 0.8
    assert prepare.estimate_tilt(Image.new("RGB", (300, 300), "white")) == 0.0
    flat = prepare.straighten(clean)
    assert flat.size == clean.size  # already upright: not resampled
