"""Tests for the admin data import: POST /admin/import/{table}.

Owner role: D (full-stack).
Implements: PROJECT_BRIEF section 18, item 20.

Each test starts from an empty database (only the four demo users) and imports the hand-made
files in tests/fixtures/contract/ or small files written here. No scorer is needed: the
import works on the database alone. No network.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from src.api import importer, routes_admin
from src.api.main import app
from src.api.schemas import ImportReport
from src.api.state import Services
from src.config import load_config
from src.db import models as db
from src.db.load import DEMO_USERS
from tests.conftest import FIXTURES
from tests.test_api import ADMIN, OFFICER, count

# every table an upload may fill, in the order they must be imported ("consents" is never one)
ORDER = ["merchants", "loans", "purchases", "deliveries", "payments", "questionnaire"]
MODEL_OF = importer.MODELS


@pytest.fixture()
def empty(tmp_path):
    """An API on an empty database with the demo users, and no scorer."""
    url = "sqlite:///" + (tmp_path / "import.db").as_posix()
    db.create_tables(url)
    engine = db.make_engine(url)
    with engine.begin() as connection:
        connection.execute(insert(db.User.__table__), DEMO_USERS)
    # a scorer that knows no merchant: every merchant in these files is new to it
    nobody = type("Scorer", (), {"merchant_ids": lambda self: []})()
    app.state.services = Services(config=load_config(), engine=engine, scorer=nobody)
    world = type("World", (), {"engine": engine})
    try:
        yield TestClient(app), world
    finally:
        del app.state.services
        engine.dispose()


def fixture_csv(table: str) -> bytes:
    return (FIXTURES / "contract" / f"{table}.csv").read_bytes()


def upload(api, table: str, content: bytes | str, params: str = "", headers=ADMIN):
    if isinstance(content, str):
        content = content.encode("utf-8")
    response = api.post(
        f"/admin/import/{table}{params}",
        headers={**headers, "Content-Type": "text/csv"},
        content=content,
    )
    return response


def report_of(response) -> ImportReport:
    assert response.status_code == 200, response.text
    return ImportReport.model_validate(response.json())


def load_fixtures(api, tables=ORDER) -> None:
    for table in tables:
        assert report_of(upload(api, table, fixture_csv(table))).loaded, table


MERCHANT_HEADER = (
    "merchant_id,onboarded_at,district,town_tier,shop_type,has_trade_license,"
    "consent_data_use,questionnaire_done\n"
)


def merchants_csv(*rows: str) -> str:
    return MERCHANT_HEADER + "\n".join(rows) + "\n"


# --- the happy path ---------------------------------------------------------------------


def test_the_fixture_files_import_in_order_and_are_reported(empty):
    api, world = empty
    for table in ORDER:
        rows = fixture_csv(table).decode().strip().count("\n")  # lines minus the header
        report = report_of(upload(api, table, fixture_csv(table)))
        assert report.table == table
        assert (report.rows_received, report.rows_accepted, report.rows_rejected) == (rows, rows, 0)
        assert report.loaded and not report.dry_run and report.file_error is None
        assert report.rejections == []
        assert "trained again" in report.note
        assert count(world, MODEL_OF[table]) == rows, table
    # each import left its own audit entry
    for table in ORDER:
        assert count(world, db.AuditEntry, db.AuditEntry.action == f"import_{table}") == 1
    with Session(world.engine) as session:
        entry = session.scalars(select(db.AuditEntry).order_by(db.AuditEntry.id)).first()
        assert (entry.actor, entry.role) == ("admin-1", "admin")
        assert session.get(db.Merchant, "FIX-M001").questionnaire_done is True
        loan = session.get(db.Loan, "FIX-L001")
        assert (loan.issued_at, loan.outcome_label) == (date(2025, 4, 1), 1)


def test_a_dry_run_checks_and_reports_but_loads_nothing(empty):
    api, world = empty
    report = report_of(upload(api, "merchants", fixture_csv("merchants"), "?dry_run=true"))
    assert report.dry_run and not report.loaded
    assert report.rows_accepted == 6 and report.rows_rejected == 0
    assert "nothing was loaded" in report.note.lower()
    assert count(world, db.Merchant) == 0
    assert count(world, db.AuditEntry, db.AuditEntry.action == "check_import_merchants") == 1
    # the same file loads for real afterwards
    assert report_of(upload(api, "merchants", fixture_csv("merchants"))).loaded
    assert count(world, db.Merchant) == 6


def test_files_with_a_byte_order_mark_and_windows_line_ends_are_accepted(empty):
    api, world = empty
    text = fixture_csv("merchants").decode().replace("\n", "\r\n")
    report = report_of(upload(api, "merchants", b"\xef\xbb\xbf" + text.encode()))
    assert report.rows_accepted == 6 and report.loaded


# --- the whole file is refused ----------------------------------------------------------


@pytest.mark.parametrize(
    "content,fragment",
    [
        (b"", "empty"),
        (b"\xff\xfe\x00bad", "UTF-8"),
        (b"merchant_id,onboarded_at\nM1,2025-01-01\n", "Missing"),
        (
            MERCHANT_HEADER.replace("\n", ",secret_score\n").encode()
            + b"M1,2025-01-01,D,metro,x,True,True,True,9\n",
            "Unexpected: ['secret_score']",
        ),
        (MERCHANT_HEADER.replace("district", "merchant_id").encode(), "Repeated"),
    ],
)
def test_a_file_with_the_wrong_columns_is_refused_whole(empty, content, fragment):
    api, world = empty
    report = report_of(upload(api, "merchants", content))
    assert report.file_error and fragment in report.file_error
    assert report.rows_accepted == 0 and not report.loaded
    assert count(world, db.Merchant) == 0
    assert "Nothing was loaded" in report.note


def test_the_error_names_the_columns_the_table_expects(empty):
    api, _ = empty
    report = report_of(upload(api, "loans", "loan_id,merchant_id\nL1,M1\n"))
    for name in ("issued_at", "limit_bdt", "outcome_label", "label_observed_at"):
        assert name in report.file_error


# --- single rows are refused, the rest load ---------------------------------------------


def test_bad_rows_are_listed_with_line_and_reason_and_good_rows_still_load(empty):
    api, world = empty
    content = merchants_csv(
        "M-OK-1,2025-01-10,Dhaka,metro,grocery,True,True,False",  # line 2: fine
        "M-BAD-DATE,10/01/2025,Dhaka,metro,grocery,True,True,False",  # line 3
        "M-BAD-BOOL,2025-01-10,Dhaka,metro,grocery,maybe,True,False",  # line 4
        ",2025-01-10,Dhaka,metro,grocery,True,True,False",  # line 5: no id
        "M-OK-1,2025-02-10,Dhaka,metro,grocery,True,True,False",  # line 6: repeated id
        "M-SHORT,2025-01-10,Dhaka",  # line 7: too few columns
        "M-LONG,2025-01-10,Dhaka,metro,grocery,True,True,False,extra",  # line 8: too many
        "M-OK-2,2025-03-10,,,,,True,True",  # line 9: optional columns left empty
        "M-NO-CONSENT-FIELD,2025-03-10,Dhaka,metro,grocery,True,,False",  # line 10
        "M" + "9" * 40 + ",2025-03-10,Dhaka,metro,grocery,True,True,False",  # line 11: too long
    )
    report = report_of(upload(api, "merchants", content))
    assert (report.rows_received, report.rows_accepted, report.rows_rejected) == (10, 2, 8)
    reasons = {r.line: " ".join(r.reasons) for r in report.rejections}
    assert set(reasons) == {3, 4, 5, 6, 7, 8, 10, 11}
    assert "onboarded_at is not valid" in reasons[3] and "YYYY-MM-DD" in reasons[3]
    assert "has_trade_license must be True or False" in reasons[4]
    assert "merchant_id is empty" in reasons[5]
    assert "repeated (first on line 2)" in reasons[6]
    assert "wrong number of columns" in reasons[7] and "wrong number of columns" in reasons[8]
    assert "consent_data_use is empty" in reasons[10]
    assert "longer than 32" in reasons[11]
    assert {r.line: r.record_id for r in report.rejections}[3] == "M-BAD-DATE"
    assert report.loaded
    with Session(world.engine) as session:
        assert sorted(session.scalars(select(db.Merchant.merchant_id))) == ["M-OK-1", "M-OK-2"]
        assert session.get(db.Merchant, "M-OK-2").district is None


def test_only_the_first_rejections_are_listed_but_all_are_counted(empty, monkeypatch):
    api, _ = empty
    monkeypatch.setattr(importer, "MAX_LISTED_REJECTIONS", 3)
    content = merchants_csv(*[f"M{n},bad,D,metro,x,True,True,True" for n in range(8)])
    report = report_of(upload(api, "merchants", content))
    assert report.rows_rejected == 8 and len(report.rejections) == 3
    assert report.rejections_truncated and not report.loaded
    assert "No row passed" in report.note


def test_an_import_never_overwrites_a_row(empty):
    api, world = empty
    load_fixtures(api, ["merchants", "loans"])
    changed = fixture_csv("merchants").decode().replace("Dhaka", "Elsewhere")
    report = report_of(upload(api, "merchants", changed))
    assert report.rows_accepted == 0 and report.rows_rejected == 6 and not report.loaded
    assert all("already in the database" in r.reasons[0] for r in report.rejections)
    with Session(world.engine) as session:
        assert session.get(db.Merchant, "FIX-M001").district == "Dhaka"
    # in particular a loan's outcome cannot be changed by importing the loan again
    first_loan = "FIX-L001,FIX-M001,2025-04-01,50000,"
    flipped = fixture_csv("loans").decode().replace(first_loan + "1", first_loan + "0")
    report = report_of(upload(api, "loans", flipped))
    assert report.rows_rejected >= 1 and not report.loaded
    with Session(world.engine) as session:
        assert session.get(db.Loan, "FIX-L001").outcome_label == 1


def test_a_second_import_of_the_same_file_loads_nothing_new(empty):
    api, world = empty
    load_fixtures(api, ["merchants"])
    again = report_of(upload(api, "merchants", fixture_csv("merchants")))
    assert again.rows_accepted == 0 and again.rows_rejected == 6 and not again.loaded
    assert count(world, db.Merchant) == 6


# --- rows must point at things that exist -----------------------------------------------


def test_every_merchant_id_must_already_be_known(empty):
    api, world = empty
    # purchases first, merchants not yet loaded
    report = report_of(upload(api, "purchases", fixture_csv("purchases")))
    assert report.rows_accepted == 0 and not report.loaded
    assert all("import merchants first" in r.reasons[0] for r in report.rejections)
    load_fixtures(api, ["merchants"])
    header = "purchase_id,merchant_id,purchase_date,amount_bdt,category,supplier_id\n"
    report = report_of(
        upload(
            api,
            "purchases",
            header
            + "NEW-1,FIX-M001,2025-05-01,1000,rice_grain,S1\n"
            + "NEW-2,NOBODY,2025-05-01,1000,,\n",
        )
    )
    assert (report.rows_accepted, report.rows_rejected) == (1, 1)
    assert report.rejections[0].record_id == "NEW-2" and report.rejections[0].line == 3
    assert count(world, db.Purchase) == 1


def test_a_payment_must_belong_to_a_known_loan_of_the_same_merchant(empty):
    api, world = empty
    load_fixtures(api, ["merchants", "loans"])
    header = "payment_id,merchant_id,loan_id,due_date,paid_date,amount_due_bdt,amount_paid_bdt\n"
    content = header + "\n".join(
        [
            "P-OK,FIX-M001,FIX-L001,2025-05-01,2025-05-01,50000,50000",
            "P-NO-LOAN,FIX-M001,L-MISSING,2025-05-01,,50000,0",
            "P-OTHER,FIX-M002,FIX-L001,2025-05-01,,50000,0",
        ]
    )
    report = report_of(upload(api, "payments", content + "\n"))
    assert (report.rows_accepted, report.rows_rejected) == (1, 2)
    reasons = {r.record_id: r.reasons[0] for r in report.rejections}
    assert "import loans first" in reasons["P-NO-LOAN"]
    assert "different merchant" in reasons["P-OTHER"]
    with Session(world.engine) as session:
        unpaid = session.get(db.Payment, "P-OK")
        assert unpaid.paid_date == date(2025, 5, 1)


# --- values must make sense -------------------------------------------------------------


@pytest.mark.parametrize(
    "table,row,fragment",
    [
        ("loans", "L1,FIX-M001,2025-04-01,5,2,2025-06-30", "outcome_label must be 0, 1 or empty"),
        ("loans", "L1,FIX-M001,2025-04-01,50000,1,", "label_observed_at is empty"),
        ("loans", "L1,FIX-M001,2025-04-01,-5,,", "limit_bdt must be a number of 0 or more"),
        ("loans", "L1,FIX-M001,2025-04-01,lots,,", "limit_bdt is not valid"),
        ("loans", "L1,FIX-M001,not-a-date,50,,", "issued_at is not valid"),
    ],
)
def test_loan_values_are_checked(empty, table, row, fragment):
    api, _ = empty
    load_fixtures(api, ["merchants"])
    header = "loan_id,merchant_id,issued_at,limit_bdt,outcome_label,label_observed_at\n"
    report = report_of(upload(api, table, header + row + "\n"))
    assert report.rows_accepted == 0
    assert fragment in report.rejections[0].reasons[0]


def test_deliveries_and_questionnaire_values_are_checked(empty):
    api, world = empty
    load_fixtures(api, ["merchants"])
    deliveries = report_of(
        upload(
            api,
            "deliveries",
            "delivery_id,merchant_id,dispatched_at,delivered_at,status,return_reason,is_cod,cod_remitted_on_time\n"
            "D1,FIX-M001,2025-02-05T09:00:00,,approved,,True,\n"
            "D2,FIX-M001,2025-02-05T09:00:00,,delivered,,True,\n"
            "D3,FIX-M001,yesterday,,delivered,,True,\n",
        )
    )
    assert deliveries.rows_accepted == 1
    assert "status must be one of" in deliveries.rejections[0].reasons[0]
    answers = (
        "merchant_id,spend1,spend2,save1,save2,borrow1,borrow2,plan1,plan2,"
        "stress,confidence,answered_at\n"
    )
    questionnaire = report_of(
        upload(
            api,
            "questionnaire",
            answers
            + "FIX-M001,6,3,3,3,3,3,3,3,3,3,2025-01-01\n"
            + "FIX-M002,0,3,3,3,3,3,3,3,3,3,2025-01-01\n"
            + "FIX-M003,3,3,3,3,3,3,3,3,3,3,2025-01-01\n",
        )
    )
    assert (questionnaire.rows_accepted, questionnaire.rows_rejected) == (1, 2)
    assert all("from 1 to 5" in r.reasons[0] for r in questionnaire.rejections)
    with Session(world.engine) as session:
        assert session.get(db.Merchant, "FIX-M003").questionnaire_done is True
        assert session.get(db.Merchant, "FIX-M001").questionnaire_done is True


def test_a_second_questionnaire_for_the_same_merchant_is_refused(empty):
    api, _ = empty
    load_fixtures(api, ["merchants", "questionnaire"])
    again = report_of(upload(api, "questionnaire", fixture_csv("questionnaire")))
    assert again.rows_accepted == 0 and not again.loaded
    assert "already in the database" in again.rejections[0].reasons[0]


# --- who, what and how big --------------------------------------------------------------


def test_only_an_admin_may_import_and_an_unknown_table_is_a_404(empty):
    api, world = empty
    assert upload(api, "merchants", fixture_csv("merchants"), headers=OFFICER).status_code == 403
    assert upload(api, "merchants", fixture_csv("merchants"), headers={}).status_code == 401
    assert count(world, db.Merchant) == 0
    for table in ("users", "decisions", "audit_log", "model_versions", "load_info", "nothing"):
        response = upload(api, table, "a\n1\n")
        assert response.status_code == 404, table
        assert response.json()["detail"]["code"] == "unknown_table"


def test_a_file_that_is_too_large_is_refused(empty, monkeypatch):
    api, world = empty
    monkeypatch.setattr(routes_admin, "MAX_IMPORT_BYTES", 100)
    response = upload(api, "merchants", fixture_csv("merchants"))
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "file_too_large"
    assert count(world, db.Merchant) == 0


def test_import_is_closed_when_a_public_data_mode_is_active(empty):
    api, world = empty
    config = load_config()
    config["data"]["mode"] = "taiwan_cc"
    app.state.services = Services(config=config, engine=world.engine)
    response = upload(api, "merchants", fixture_csv("merchants"))
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "import_not_available"
    assert count(world, db.Merchant) == 0


def test_the_import_only_adds_rows_and_changes_no_other_table(empty):
    api, world = empty
    load_fixtures(api, ["merchants", "loans"])
    before = {name: count(world, model) for name, model in MODEL_OF.items()}
    decisions, users = count(world, db.Decision), count(world, db.User)
    upload(api, "loans", fixture_csv("loans"))  # all refused as repeats
    upload(api, "payments", fixture_csv("payments"))
    after = {name: count(world, model) for name, model in MODEL_OF.items()}
    assert after["merchants"] == before["merchants"] and after["loans"] == before["loans"]
    assert after["payments"] == len(fixture_csv("payments").decode().strip().splitlines()) - 1
    assert (count(world, db.Decision), count(world, db.User)) == (decisions, users)


def test_importing_new_rows_moves_the_date_the_api_treats_as_today(empty):
    api, world = empty
    load_fixtures(api, ["merchants", "loans", "purchases"])
    services = app.state.services
    with Session(world.engine) as session:
        first = services.data_today(session)
    header = "purchase_id,merchant_id,purchase_date,amount_bdt,category,supplier_id\n"
    upload(api, "purchases", header + "LATE,FIX-M001,2031-01-01,1,,\n")
    with Session(world.engine) as session:
        assert services.data_today(session) == date(2031, 1, 1) > first
