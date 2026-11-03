# ruff: noqa: F811  (fixtures imported from another test module are redefined as arguments)
"""Phases 3 to 5: FSR assignment, the daily sheet, imports, and the Credit Officer's monitoring.

Owner role: D (full-stack).
Implements: acceptance scenarios 6 and 7 (docs: the implementation plan) and the isolation checks
that go with them.

Real accounts throughout: a company's owner and second Credit Officer, two FSRs, and a second
company. Merchants become assessable the real way: a registration, a signed form, verification.
"""

from __future__ import annotations

import io
import json

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import load_config
from src.db import models as db
from src.extraction.engine import Box, FakeOcrEngine
from src.extraction.service import process_job
from src.intake.policy import real_today
from tests.test_accounts_phase1 import STRONG, client, join_body, sign_in
from tests.test_registration_phase2 import DETAILS, read_queued, team, world  # noqa: F401

TODAY = real_today(load_config()).isoformat()


def active_merchant(team, world, name: str) -> str:  # noqa: F811
    """A merchant registered, signed, read and verified, so it has a valid consent."""
    reg = team.owner.post("/registrations", json={**DETAILS, "shop_name": name}).json()
    rid = reg["reg_id"]
    form = team.owner.get(f"/registrations/{rid}/consent.pdf").content
    team.owner.post(
        f"/registrations/{rid}/signed", content=form, headers={"Content-Type": "application/pdf"}
    )
    read_queued(world, rid)
    done = team.second.post(
        f"/registrations/{rid}/verify",
        json={
            "categories": ["purchases", "deliveries", "payments"],
            "signer_name": "Abdul Karim",
            "signature_checked": True,
            "reference_matches": True,
        },
    )
    assert done.status_code == 200, done.text
    return reg["merchant_id"]


@pytest.fixture(scope="module")
def crew(world, team):  # noqa: F811
    """Two more FSRs besides Karim, three active merchants, and the people's ids."""
    anon = client()
    code = team.owner.post("/org/invitations", json={"role": "fsr", "max_uses": 3}).json()["code"]
    assert (
        anon.post(
            "/auth/register/join",
            json=join_body(
                code,
                full_name="Joya Rani",
                email="joya.rani@padma.example",
                mobile="01744440001",
                employee_id="E-1002",
                territory="Uttara",
            ),
        ).status_code
        == 201
    )
    people = {p["email"]: p for p in team.owner.get("/org/employees").json()}
    shops = {
        n: active_merchant(team, world, n) for n in ("Alpha Store", "Beta Store", "Gamma Store")
    }
    return type(
        "Crew",
        (),
        {
            "karim": team.fsr,
            "karim_id": people["karim@padma.example"]["user_id"],
            "joya": sign_in("joya.rani@padma.example"),
            "joya_id": people["joya.rani@padma.example"]["user_id"],
            "shops": shops,
        },
    )


def assign(team, merchant: str, fsr_id: str):  # noqa: F811
    return team.owner.post(
        "/org/assignments", json={"merchant_id": merchant, "fsr_user_id": fsr_id}
    )


# --- scenario 6: assignment ---------------------------------------------------------------


def test_an_fsr_sees_and_reaches_only_the_shops_assigned_to_them(team, crew):
    alpha, beta = crew.shops["Alpha Store"], crew.shops["Beta Store"]
    assert assign(team, alpha, crew.karim_id).status_code == 200
    assert assign(team, beta, crew.joya_id).status_code == 200
    mine = crew.karim.get("/fsr/overview").json()
    assert [s["merchant_id"] for s in mine["shops"]] == [alpha]
    assert mine["territory"] == "Mirpur" and mine["employee_id"] == "E-1001"
    assert [s["merchant_id"] for s in crew.joya.get("/fsr/overview").json()["shops"]] == [beta]
    # a manipulated address or direct call for someone else's shop is "not found", never "forbidden"
    for method, path, body in (
        ("get", f"/merchants/{beta}", None),
        ("get", f"/merchants/{beta}/daily/{TODAY}", None),
        ("put", f"/merchants/{beta}/daily/{TODAY}", {"rows": []}),
        ("post", f"/merchants/{beta}/daily/{TODAY}/submit", None),
        ("get", f"/merchants/{beta}/workflow", None),
    ):
        reply = getattr(crew.karim, method)(path, **({"json": body} if body is not None else {}))
        assert reply.status_code == 404, (method, path)
    # and the other company cannot reach any of them
    assert team.solo.get(f"/merchants/{alpha}").status_code == 404
    assert team.solo.get(f"/merchants/{alpha}/daily/{TODAY}").status_code == 404
    assert team.solo.get("/submissions").json() == []


def test_reassigning_keeps_the_history_and_moves_access(team, crew):
    gamma = crew.shops["Gamma Store"]
    assert assign(team, gamma, crew.karim_id).status_code == 200
    assert crew.karim.get(f"/merchants/{gamma}/daily/{TODAY}").status_code == 200
    assert assign(team, gamma, crew.joya_id).status_code == 200  # moved
    assert crew.karim.get(f"/merchants/{gamma}/daily/{TODAY}").status_code == 404
    assert crew.joya.get(f"/merchants/{gamma}/daily/{TODAY}").status_code == 200
    history = team.second.get("/org/assignments/history", params={"merchant_id": gamma}).json()
    assert [(h["fsr_name"], h["ended_at"] is None) for h in history] == [
        ("Joya Rani", True),
        ("Karim Uddin", False),
    ]
    assert team.fsr.get("/org/assignments/history").status_code == 403
    bulk = team.owner.post(
        "/org/assignments/bulk", json={"merchant_ids": [gamma], "fsr_user_id": crew.karim_id}
    )
    assert bulk.status_code == 200 and bulk.json()[0]["fsr_name"] == "Karim Uddin"
    detail = team.second.get(f"/org/fsrs/{crew.karim_id}").json()
    assert {s["merchant_id"] for s in detail["shops"]} >= {crew.shops["Alpha Store"], gamma}
    assert team.fsr.get(f"/org/fsrs/{crew.karim_id}").status_code == 403
    assign(team, gamma, crew.joya_id)


# --- scenario 6: the daily sheet ----------------------------------------------------------

ROWS = [
    {
        "entry_type": "purchase",
        "txn_date": TODAY,
        "category": "rice",
        "counterparty": "Hasan Traders",
        "quantity": "10",
        "unit": "sack",
        "unit_price": "2500",
    },
    {
        "entry_type": "purchase",
        "txn_date": TODAY,
        "category": "oil",
        "amount_bdt": "18000",
        "counterparty": "Hasan Traders",
    },
    {
        "entry_type": "sale",
        "txn_date": TODAY,
        "description": "Daily takings",
        "amount_bdt": "42000",
    },
]


def purchases_of(world, merchant: str) -> list[db.Purchase]:
    with Session(world.engine) as session:
        return list(session.scalars(select(db.Purchase).where(db.Purchase.merchant_id == merchant)))


def test_the_daily_sheet_from_draft_to_submitted_to_amended(world, team, crew):
    shop = crew.shops["Alpha Store"]
    kinds = {k["key"]: k for k in crew.karim.get("/daily/entry-types").json()}
    assert kinds["purchase"]["scored"] and not kinds["sale"]["scored"]
    assert "unit_price" in kinds["purchase"]["fields"] and "amount_bdt" in kinds["sale"]["required"]

    # an incomplete row is saved as a draft with its problems named; nothing is scored
    saved = crew.karim.put(
        f"/merchants/{shop}/daily/{TODAY}",
        json={"rows": [*ROWS, {"entry_type": "purchase", "category": "salt"}]},
    )
    assert saved.status_code == 200, saved.text
    day = saved.json()
    assert day["sheet"]["status"] == "draft" and day["sheet"]["drafts"] == 4
    assert purchases_of(world, shop) == []  # drafts never reach the assessment
    assert day["errors"] == {}  # drafts may be incomplete; submitting is what checks
    assert day["entries"][0]["amount_bdt"] == 25000.0  # a total worked out from quantity x price
    notes = crew.karim.put(
        f"/merchants/{shop}/daily/{TODAY}",
        json={"rows": [{"entry_type": "sale", "txn_date": "not-a-date", "amount_bdt": "x"}]},
    ).json()
    assert set(next(iter(notes["errors"].values()))) == {"txn_date", "amount_bdt"}

    # draft rows can be edited and deleted freely; submitting needs every row complete
    drafts = crew.karim.put(f"/merchants/{shop}/daily/{TODAY}", json={"rows": [*ROWS]}).json()
    assert [e["row_no"] for e in drafts["entries"]] == [1, 2, 3]
    bad = crew.karim.put(
        f"/merchants/{shop}/daily/{TODAY}",
        json={"rows": [*ROWS, {"entry_type": "purchase", "txn_date": TODAY}]},
    )
    assert bad.status_code == 200
    refused = crew.karim.post(f"/merchants/{shop}/daily/{TODAY}/submit")
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "rows_not_complete"
    crew.karim.put(f"/merchants/{shop}/daily/{TODAY}", json={"rows": [*ROWS]})

    submitted = crew.karim.post(f"/merchants/{shop}/daily/{TODAY}/submit")
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["sheet"]["status"] == "submitted"
    assert {e["status"] for e in submitted.json()["entries"]} == {"submitted"}
    assert sorted(p.amount_bdt for p in purchases_of(world, shop)) == [
        18000.0,
        25000.0,
    ]  # sale is not scored

    # a submitted row does not change silently: saving the grid again leaves it as it was
    again = crew.karim.put(f"/merchants/{shop}/daily/{TODAY}", json={"rows": []}).json()
    assert [e["status"] for e in again["entries"]] == ["submitted"] * 3
    assert again["sheet"]["status"] == "submitted"

    # a correction is a new row that supersedes the old one, with a reason
    first = next(
        e for e in again["entries"] if e["entry_type"] == "purchase" and e["amount_bdt"] == 25000.0
    )
    no_reason = crew.karim.post(
        f"/merchants/{shop}/daily/entries/{first['entry_id']}/amend",
        json={"reason": "x", "amount_bdt": "24000"},
    )
    assert no_reason.status_code == 422
    fixed = crew.karim.post(
        f"/merchants/{shop}/daily/entries/{first['entry_id']}/amend",
        json={"reason": "Supplier gave a discount", "amount_bdt": "24000"},
    )
    assert fixed.status_code == 200 and fixed.json()["supersedes_entry_id"] == first["entry_id"]
    assert sorted(p.amount_bdt for p in purchases_of(world, shop)) == [18000.0, 24000.0]
    listing = crew.karim.get(f"/merchants/{shop}/daily").json()
    statuses = sorted(
        (e["status"], e["amount_bdt"]) for e in listing["entries"] if e["entry_type"] == "purchase"
    )
    assert ("superseded", 25000.0) in statuses and ("submitted", 24000.0) in statuses
    assert listing["sheets"][0]["totals"]["purchase"] == 42000.0  # the current rows only


def test_submitting_needs_a_valid_consent_and_the_right_kind_of_row(world, team, crew):
    reg = team.owner.post(
        "/registrations", json={**DETAILS, "shop_name": "No Consent Store"}
    ).json()
    assert assign(team, reg["merchant_id"], crew.karim_id).status_code == 200
    day = f"/merchants/{reg['merchant_id']}/daily/{TODAY}"
    crew.karim.put(day, json={"rows": [ROWS[2]]})
    blocked = crew.karim.post(f"{day}/submit")
    assert blocked.status_code == 403 and blocked.json()["detail"]["code"] == "consent_required"
    wrong = crew.karim.put(
        day, json={"rows": [{"entry_type": "sale", "txn_date": TODAY, "due_date": TODAY}]}
    )
    assert "due_date" in next(
        iter(wrong.json()["errors"].values())
    )  # a column the kind does not use
    future = crew.karim.put(f"/merchants/{reg['merchant_id']}/daily/2999-01-01", json={"rows": []})
    assert future.status_code == 422


def test_a_delivery_and_a_loan_repayment_become_assessment_records(world, team, crew):
    shop = crew.shops["Alpha Store"]
    with Session(world.engine) as session:
        before = len(
            list(session.scalars(select(db.Delivery).where(db.Delivery.merchant_id == shop)))
        )
    day = f"/merchants/{shop}/daily/2020-01-02"
    rows = [
        {
            "entry_type": "delivery",
            "txn_date": "2020-01-02",
            "due_date": "2020-01-03",
            "category": "delivered",
            "payment_method": "cod",
            "payment_status": "on_time",
        },
    ]
    assert crew.karim.put(day, json={"rows": rows}).status_code == 200
    done = crew.karim.post(f"{day}/submit")
    assert done.status_code == 200, done.text
    with Session(world.engine) as session:
        after = list(session.scalars(select(db.Delivery).where(db.Delivery.merchant_id == shop)))
    assert len(after) == before + 1 and after[-1].is_cod and after[-1].cod_remitted_on_time
    # a projected delivery cannot be changed by the FSR: the officer corrects it
    entry = done.json()["entries"][0]
    refused = crew.karim.post(
        f"/merchants/{shop}/daily/entries/{entry['entry_id']}/amend",
        json={"reason": "wrong status", "category": "returned"},
    )
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "ask_the_officer"
    # a loan repayment must name a real earlier loan of this shop
    pay = f"/merchants/{shop}/daily/2020-01-04"
    crew.karim.put(
        pay,
        json={
            "rows": [
                {
                    "entry_type": "loan_repayment",
                    "txn_date": "2020-01-04",
                    "counterparty": "L-NONE",
                    "unit_price": "1000",
                    "amount_bdt": "1000",
                    "due_date": "2020-01-04",
                }
            ]
        },
    )
    bad = crew.karim.post(f"{pay}/submit")
    assert bad.status_code in (404, 409, 422)


# --- scenario 6/8 of the plan: what the Credit Officer sees ---------------------------------


def test_the_credit_officer_sees_submissions_and_can_return_or_accept(world, team, crew):
    shop = crew.shops["Beta Store"]
    day = f"/merchants/{shop}/daily/{TODAY}"
    crew.joya.put(day, json={"rows": [ROWS[1], ROWS[2]]})
    crew.joya.post(f"{day}/submit")
    feed = team.second.get("/submissions").json()
    mine = next(s for s in feed if s["merchant_id"] == shop and s["business_date"] == TODAY)
    assert mine["status"] == "submitted" and mine["fsr_name"] == "Joya Rani" and mine["rows"] == 2
    assert mine["totals"]["sale"] == 42000.0
    only_joya = team.second.get("/submissions", params={"fsr": crew.joya_id}).json()
    assert {s["fsr_name"] for s in only_joya} == {"Joya Rani"}
    assert any("submitted" in n["text"] for n in team.owner.get("/notifications").json())
    # the FSR cannot review their own work
    assert (
        crew.joya.post(f"{day}/return", json={"reason": "I want to change it"}).status_code == 403
    )
    assert crew.joya.post(f"{day}/accept").status_code == 403
    assert team.second.post(f"{day}/return", json={"reason": "short"}).status_code == 422
    back = team.second.post(f"{day}/return", json={"reason": "The supplier name is missing."})
    assert back.json()["sheet"]["status"] == "returned"
    note = crew.joya.get("/notifications").json()[0]
    assert "sent back" in note["text"] and not note["read"]
    assert crew.joya.get("/fsr/overview").json()["returned"] >= 1
    # the FSR corrects (an amendment) and submits again; the officer accepts
    entry = next(e for e in back.json()["entries"] if e["entry_type"] == "purchase")
    crew.joya.post(
        f"/merchants/{shop}/daily/entries/{entry['entry_id']}/amend",
        json={"reason": "Added the supplier", "counterparty": "Hasan Traders"},
    )
    crew.joya.put(
        day, json={"rows": [{"entry_type": "sale", "txn_date": TODAY, "amount_bdt": "500"}]}
    )
    resub = crew.joya.post(f"{day}/submit").json()
    assert resub["sheet"]["status"] == "submitted"
    accepted = team.owner.post(f"{day}/accept")
    assert accepted.json()["sheet"]["status"] == "accepted"
    assert crew.joya.post("/notifications/read-all").status_code == 204
    assert all(n["read"] for n in crew.joya.get("/notifications").json())
    # an auditor-style read of another company's feed is empty; FSRs have no feed at all
    assert crew.joya.get("/submissions").status_code == 403


# --- scenario 7: importing figures from files ----------------------------------------------


def _csv() -> bytes:
    return (
        "Date,Item,Supplier,Qty,Rate,Total\n"
        f"{TODAY},sugar,Hasan Traders,5,1200,6000\n"
        f"{TODAY},flour,Karim & Sons,3,900,2700\n"
    ).encode()


def _xlsx() -> bytes:
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.append(["তারিখ", "পণ্য", "মোট টাকা"])
    sheet.append([TODAY, "rice", 25000])
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def _docx() -> bytes:
    import docx

    document = docx.Document()
    table = document.add_table(rows=2, cols=3)
    for index, text in enumerate(("Date", "Description", "Amount")):
        table.rows[0].cells[index].text = text
    for index, text in enumerate((TODAY, "Tea", "800")):
        table.rows[1].cells[index].text = text
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


def test_figures_from_csv_excel_and_word_become_reviewed_drafts(world, team, crew):
    shop = crew.shops["Alpha Store"]
    base = f"/merchants/{shop}/daily-import"
    csv_read = crew.karim.post(
        base, params={"name": "day.csv", "entry_type": "purchase"}, content=_csv()
    )
    assert csv_read.status_code == 201, csv_read.text
    table = csv_read.json()
    assert table["status"] == "done" and table["method"] == "csv"
    assert table["headers"] == ["Date", "Item", "Supplier", "Qty", "Rate", "Total"]
    assert (
        table["suggested_mapping"]["txn_date"] == 0
        and table["suggested_mapping"]["counterparty"] == 2
    )
    xlsx = crew.karim.post(base, params={"name": "register.xlsx"}, content=_xlsx()).json()
    assert xlsx["method"] == "xlsx" and xlsx["rows"][0][2] == "25000"
    assert xlsx["suggested_mapping"].get("amount_bdt") == 2
    word = crew.karim.post(
        base, params={"name": "note.docx", "entry_type": "sale"}, content=_docx()
    ).json()
    assert word["method"] == "docx" and word["rows"] == [[TODAY, "Tea", "800"]]
    # the FSR maps and corrects, then loads them as DRAFT rows: still nothing in the assessment
    mapping = table["suggested_mapping"]
    rows = [
        {
            "entry_type": "purchase",
            "source": "import",
            "txn_date": r[mapping["txn_date"]],
            "category": r[1],
            "counterparty": r[2],
            "amount_bdt": r[mapping["amount_bdt"]],
        }
        for r in table["rows"]
    ]
    before = len(purchases_of(world, shop))
    day = f"/merchants/{shop}/daily/{TODAY}"
    loaded = crew.karim.put(day, json={"rows": rows, "delete_missing": False}).json()
    assert [e["source"] for e in loaded["entries"] if e["status"] == "draft"] == [
        "import",
        "import",
    ]
    assert len(purchases_of(world, shop)) == before
    crew.karim.put(day, json={"rows": [], "delete_missing": True})  # leave the sheet clean
    # not a table, or not a supported file
    assert crew.karim.post(base, params={"name": "x.exe"}, content=b"MZ\x90\x00").status_code == 415
    assert team.solo.post(base, content=_csv()).status_code == 404  # not their shop


def test_a_photographed_register_is_read_by_the_worker_with_confidence(world, team, crew):
    from PIL import Image

    shop = crew.shops["Alpha Store"]
    out = io.BytesIO()
    Image.new("RGB", (1200, 1600), "white").save(out, "PNG")
    queued = crew.karim.post(
        f"/merchants/{shop}/daily-import", params={"name": "page.png"}, content=out.getvalue()
    )
    assert queued.status_code == 201 and queued.json()["status"] == "queued"
    job_id = queued.json()["job_id"]
    boxes = [
        Box("Date", 0.9, 50, 100, 150, 140),
        Box("Item", 0.9, 400, 100, 500, 140),
        Box("Amount", 0.9, 800, 100, 950, 140),
        Box(TODAY, 0.55, 50, 200, 250, 240),
        Box("soap", 0.4, 400, 200, 520, 240),
        Box("1,500", 0.35, 800, 200, 900, 240),
    ]
    with Session(world.engine) as session:
        process_job(session, world.config, FakeOcrEngine([boxes]), job_id)
    done = crew.karim.get(f"/merchants/{shop}/daily-import/{job_id}").json()
    assert done["status"] == "done" and done["method"] == "ocr"
    assert done["headers"] == ["Date", "Item", "Amount"] and done["rows"] == [
        [TODAY, "soap", "1,500"]
    ]
    assert done["confidences"] and done["confidences"][0] < 0.6  # handwriting-like: flagged
    assert any("machine" in n for n in done["notes"])
    assert team.solo.get(f"/merchants/{shop}/daily-import/{job_id}").status_code == 404
    with Session(world.engine) as session:
        assert (
            session.scalar(
                select(db.ExtractionJob).where(db.ExtractionJob.job_id == job_id)
            ).purpose
            == "table"
        )
    json.dumps(STRONG)
