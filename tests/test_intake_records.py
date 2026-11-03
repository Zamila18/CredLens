"""Tests for the records the demo workflow adds: consent, visits and applications.

Owner role: D (full-stack).
Implements: the implementation pack, Phase 2.8: atomic writes, one application per
    merchant, merchant/loan matching, no repayment against an application, consent grant
    and refusal, category checks, the demo calendar, real versus simulated time, the
    benchmark merchants kept read-only, and refusal when synthetic-only mode is off.

Every test works in a temporary database loaded with a small generated world, plus merchants
the test creates itself. Nothing here touches data/app.db.
"""

from __future__ import annotations

import copy
import uuid
from datetime import timedelta

import pandas as pd
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from src.api.auth import CurrentUser
from src.api.imported import tables_for_merchants
from src.api.importer import check_csv
from src.config import load_config
from src.db import models as db
from src.db.load import load_tables
from src.db.models import make_engine
from src.intake.applications import application_loan_ids, create_application, is_application
from src.intake.consent import record_consent_response
from src.intake.policy import IntakeRefused, calendar_end, utc_now
from src.intake.visits import record_visit
from src.model.labels import latest_date
from src.model.scoring import Scorer
from src.model.train import load_model
from src.synth.generate import build_tables

OFFICER = CurrentUser(user_id="officer-1", role="credit_officer")
ALL_CATEGORIES = ["purchases", "deliveries", "payments", "questionnaire", "field_visits"]


@pytest.fixture(scope="module")
def world():
    config = copy.deepcopy(load_config())
    config["data"]["n_merchants"] = 600
    return build_tables(config, 0.5)[0]


@pytest.fixture(scope="module")
def config(world) -> dict:
    """The default config, with the demo calendar ending on this small world's last day."""
    settings = copy.deepcopy(load_config())
    settings["data"]["n_merchants"] = 600
    settings["demo"]["calendar_end"] = latest_date(world).date().isoformat()
    return settings


@pytest.fixture(scope="module")
def engine(world, tmp_path_factory):
    url = "sqlite:///" + (tmp_path_factory.mktemp("intake") / "intake.db").as_posix()
    load_tables(world, url)
    engine = make_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def benchmark(world) -> frozenset[str]:
    """The read-only merchants: everyone in the generated world."""
    return frozenset(world["merchants"]["merchant_id"])


@pytest.fixture()
def session(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture()
def live(session, config) -> str:
    """A merchant created in the app (not a benchmark merchant), with no records yet."""
    merchant_id = f"LIVE-{uuid.uuid4().hex[:8]}"
    session.add(
        db.Merchant(
            merchant_id=merchant_id,
            onboarded_at=calendar_end(config) - timedelta(days=150),
            district="Dhaka",
            town_tier="metro",
            shop_type="grocery",
            has_trade_license=False,
            consent_data_use=False,
            questionnaire_done=False,
        )
    )
    session.commit()
    return merchant_id


def grant(session, config, merchant_id, benchmark, categories=None, **overrides):
    arguments = dict(
        merchant_id=merchant_id,
        response="granted",
        categories=ALL_CATEGORIES if categories is None else categories,
        method="assisted_on_phone",
        actor=OFFICER,
        business_date=calendar_end(config) - timedelta(days=5),
        protected_merchants=benchmark,
    )
    arguments.update(overrides)
    return record_consent_response(session, config, **arguments)


def apply(session, config, merchant_id, benchmark, **overrides):
    arguments = dict(
        merchant_id=merchant_id,
        requested_amount_bdt=25000,
        purpose="inventory_restock",
        purpose_note="Eid stock",
        business_date=calendar_end(config),
        actor=OFFICER,
        protected_merchants=benchmark,
    )
    arguments.update(overrides)
    return create_application(session, config, **arguments)


def count(session, model, merchant_id) -> int:
    return session.scalar(
        select(func.count()).select_from(model).where(model.merchant_id == merchant_id)
    )


def provenance(session, merchant_id) -> list[db.RecordProvenance]:
    query = select(db.RecordProvenance).where(db.RecordProvenance.merchant_id == merchant_id)
    return list(session.scalars(query))


def audit_actions(session, merchant_id) -> list[str]:
    query = select(db.AuditEntry.action).where(db.AuditEntry.merchant_id == merchant_id)
    return list(session.scalars(query))


# --- consent ------------------------------------------------------------------------------


def test_a_grant_creates_the_consent_the_scorer_reads_and_an_event(
    session, config, live, benchmark
):
    before = utc_now()
    event = grant(session, config, live, benchmark)
    consent = session.get(db.Consent, event.consent_id)

    assert event.response == "granted" and event.simulated is True
    assert consent.merchant_id == live and consent.revoked_at is None
    assert consent.data_categories == "|".join(ALL_CATEGORIES)
    assert consent.granted_at == event.business_date
    assert consent.expires_at == event.business_date + timedelta(
        days=config["demo"]["consent"]["valid_days"]
    )
    assert event.wording_version == config["demo"]["consent"]["wording_version"]
    assert event.method == "assisted_on_phone" and event.actor == "officer-1"
    # the real moment of recording is kept apart from the simulated business date
    assert before <= event.recorded_at <= utc_now()
    assert event.recorded_at.date() != event.business_date
    rows = provenance(session, live)
    assert [(r.record_type, r.entry_method, r.status, r.simulated) for r in rows] == [
        ("consent", "staff_entered", "staff_entered", True)
    ]
    assert audit_actions(session, live) == ["record_consent_granted"]


def test_a_refusal_records_only_an_event(session, config, live, benchmark):
    event = record_consent_response(
        session,
        config,
        merchant_id=live,
        response="refused",
        categories=["purchases"],
        method="verbal_recorded_by_staff",
        actor=OFFICER,
        business_date=calendar_end(config),
        protected_merchants=benchmark,
    )
    assert event.response == "refused" and event.consent_id is None
    assert count(session, db.Consent, live) == 0
    with pytest.raises(IntakeRefused) as refused:
        apply(session, config, live, benchmark)
    assert refused.value.code == "consent_required"


def test_unknown_categories_methods_and_answers_are_refused(session, config, live, benchmark):
    for overrides in (
        {"categories": ["bank_statements"]},
        {"categories": []},
        {"categories": ["purchases", "purchases"]},
        {"method": "signature"},
        {"response": "maybe"},
    ):
        with pytest.raises(IntakeRefused) as refused:
            grant(session, config, live, benchmark, **overrides)
        assert refused.value.code == "invalid_choice", overrides
    assert count(session, db.ConsentEvent, live) == 0


def test_a_second_grant_and_a_withdrawal_are_refused(session, config, live, benchmark):
    grant(session, config, live, benchmark)
    with pytest.raises(IntakeRefused) as again:
        grant(session, config, live, benchmark)
    assert again.value.code == "consent_already_valid"
    with pytest.raises(IntakeRefused) as withdraw:
        grant(session, config, live, benchmark, response="refused")
    assert withdraw.value.code == "withdrawal_not_supported"
    assert count(session, db.ConsentEvent, live) == 1


def test_a_visit_needs_a_consent_that_covers_field_visits(session, config, live, benchmark):
    grant(session, config, live, benchmark, categories=["purchases", "payments"])
    with pytest.raises(IntakeRefused) as refused:
        record_visit(
            session,
            config,
            merchant_id=live,
            business_date=calendar_end(config),
            outcome="shop_open_trading",
            note=None,
            actor=OFFICER,
            protected_merchants=benchmark,
        )
    assert refused.value.code == "consent_category_missing"
    assert count(session, db.Visit, live) == 0


def test_a_visit_is_recorded_with_its_provenance(session, config, live, benchmark):
    grant(session, config, live, benchmark)
    visit = record_visit(
        session,
        config,
        merchant_id=live,
        business_date=calendar_end(config) - timedelta(days=1),
        outcome="follow_up_needed",
        note="  Owner asked to come back after Friday prayers.  ",
        actor=OFFICER,
        protected_merchants=benchmark,
    )
    assert visit.note == "Owner asked to come back after Friday prayers."
    assert visit.simulated is True
    assert ("visit", "field_visits") in {
        (r.record_type, r.source_category) for r in provenance(session, live)
    }
    assert "record_visit" in audit_actions(session, live)


# --- the demo calendar and synthetic-only mode -------------------------------------------


def test_business_dates_after_the_demo_calendar_are_refused(session, config, live, benchmark):
    late = calendar_end(config) + timedelta(days=1)
    with pytest.raises(IntakeRefused) as consent:
        grant(session, config, live, benchmark, business_date=late)
    assert consent.value.code == "date_after_demo_calendar"
    grant(session, config, live, benchmark)
    with pytest.raises(IntakeRefused) as visit:
        record_visit(
            session,
            config,
            merchant_id=live,
            business_date=late,
            outcome="shop_open_trading",
            note=None,
            actor=OFFICER,
            protected_merchants=benchmark,
        )
    assert visit.value.code == "date_after_demo_calendar"
    with pytest.raises(IntakeRefused) as application:
        apply(session, config, live, benchmark, business_date=late)
    assert application.value.code == "date_after_demo_calendar"
    # the last day itself is allowed
    apply(session, config, live, benchmark, business_date=calendar_end(config))


def test_every_intake_write_is_refused_when_synthetic_mode_is_off(session, config, live, benchmark):
    grant(session, config, live, benchmark)
    closed = copy.deepcopy(config)
    closed["demo"]["synthetic_only"] = False
    other = f"LIVE-{uuid.uuid4().hex[:8]}"
    attempts = (
        lambda: grant(session, closed, other, benchmark),
        lambda: record_visit(
            session,
            closed,
            merchant_id=live,
            business_date=calendar_end(config),
            outcome="shop_open_trading",
            note=None,
            actor=OFFICER,
            protected_merchants=benchmark,
        ),
        lambda: apply(session, closed, live, benchmark),
    )
    for attempt in attempts:
        with pytest.raises(IntakeRefused) as refused:
            attempt()
        assert refused.value.code == "intake_closed"
    assert count(session, db.Visit, live) == 0 and count(session, db.Application, live) == 0


def test_benchmark_merchants_stay_read_only(session, config, benchmark):
    merchant_id = sorted(benchmark)[0]
    events = count(session, db.ConsentEvent, merchant_id)
    with pytest.raises(IntakeRefused) as refused:
        grant(session, config, merchant_id, benchmark)
    assert refused.value.code == "benchmark_merchant"
    with pytest.raises(IntakeRefused) as application:
        apply(session, config, merchant_id, benchmark)
    assert application.value.code == "benchmark_merchant"
    assert count(session, db.ConsentEvent, merchant_id) == events


def test_an_unknown_merchant_is_refused(session, config, benchmark):
    with pytest.raises(IntakeRefused) as refused:
        grant(session, config, "NOBODY", benchmark)
    assert refused.value.code == "unknown_merchant"


# --- applications ---------------------------------------------------------------------


def test_an_application_and_its_scoring_row_are_written_together(session, config, live, benchmark):
    grant(session, config, live, benchmark)
    application = apply(session, config, live, benchmark)
    loan = session.get(db.Loan, application.loan_id)

    assert loan.merchant_id == live and loan.issued_at == application.business_date
    assert loan.outcome_label is None and loan.label_observed_at is None
    # the request lives only in the application; the scoring row carries no amount
    assert loan.limit_bdt == 0.0 and application.requested_amount_bdt == 25000
    assert application.demo_synthetic is True and application.created_by == "officer-1"
    assert is_application(session, application.loan_id)
    assert application_loan_ids(session, [application.loan_id, "L0000001"]) == {application.loan_id}
    assert ("application", "application") in {
        (r.record_type, r.source_category) for r in provenance(session, live)
    }
    assert "create_application" in audit_actions(session, live)


def test_one_application_per_merchant_ever(session, engine, config, live, benchmark):
    grant(session, config, live, benchmark)
    first = apply(session, config, live, benchmark)
    with pytest.raises(IntakeRefused) as refused:
        apply(session, config, live, benchmark, requested_amount_bdt=5000)
    assert refused.value.code == "application_exists"
    # the database refuses it too, whoever writes
    other_loan = f"LA-test-{uuid.uuid4().hex[:8]}"
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO loans (loan_id, merchant_id, issued_at, limit_bdt) "
                "VALUES (:l, :m, :d, 0)"
            ),
            {"l": other_loan, "m": live, "d": first.business_date},
        )
    with pytest.raises(Exception, match="UNIQUE"):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO applications (application_id, loan_id, merchant_id, "
                    "requested_amount_bdt, purpose, business_date, created_by, entered_at, "
                    "demo_synthetic) VALUES ('AP-dup', :l, :m, 100, 'other', :d, 'officer-1', "
                    ":d, 1)"
                ),
                {"l": other_loan, "m": live, "d": first.business_date},
            )


def test_an_application_must_point_at_a_loan_row_of_the_same_merchant(
    session, engine, config, live, benchmark
):
    someone_else = session.scalar(select(db.Loan.loan_id).where(db.Loan.merchant_id != live))
    with pytest.raises(Exception, match="same merchant"):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO applications (application_id, loan_id, merchant_id, "
                    "requested_amount_bdt, purpose, business_date, created_by, entered_at, "
                    "demo_synthetic) VALUES ('AP-x', :l, :m, 100, 'other', '2026-01-01', "
                    "'officer-1', '2026-01-01', 1)"
                ),
                {"l": someone_else, "m": live},
            )


def test_no_repayment_can_point_at_an_application(session, engine, config, live, benchmark):
    grant(session, config, live, benchmark)
    application = apply(session, config, live, benchmark)
    insert = text(
        "INSERT INTO payments (payment_id, merchant_id, loan_id, due_date, paid_date, "
        "amount_due_bdt, amount_paid_bdt) VALUES (:p, :m, :l, '2026-09-30', NULL, 100, 0)"
    )
    with pytest.raises(Exception, match="repayment cannot be recorded"):
        with engine.begin() as connection:
            connection.execute(insert, {"p": "P-app", "m": live, "l": application.loan_id})
    # the admin import reports it as a rejected row, with the reason, and loads nothing
    csv_text = (
        "payment_id,merchant_id,loan_id,due_date,paid_date,amount_due_bdt,amount_paid_bdt\n"
        f"P-app-csv,{live},{application.loan_id},2026-09-30,,100,0\n"
    )
    report, accepted = check_csv(session, "payments", csv_text.encode(), benchmark)
    assert accepted == [] and report.rows_rejected == 1
    assert "is an application, not an issued loan" in report.rejections[0].reasons[0]


def test_the_scoring_row_of_an_application_cannot_be_changed(
    session, engine, config, live, benchmark
):
    grant(session, config, live, benchmark)
    application = apply(session, config, live, benchmark)
    for statement in (
        "UPDATE loans SET outcome_label = 1, label_observed_at = '2026-10-01' WHERE loan_id = :l",
        "UPDATE loans SET limit_bdt = 25000 WHERE loan_id = :l",
        "DELETE FROM loans WHERE loan_id = :l",
    ):
        with pytest.raises(Exception, match="cannot be changed or deleted"):
            with engine.begin() as connection:
                connection.execute(text(statement), {"l": application.loan_id})


def test_the_history_tables_are_append_only(session, engine, config, live, benchmark):
    grant(session, config, live, benchmark)
    apply(session, config, live, benchmark)
    for table in db.RECORD_HISTORY_TABLES:
        if not session.scalar(text(f"SELECT count(*) FROM {table}")):
            continue
        for statement in (
            f"UPDATE {table} SET business_date = business_date",
            f"DELETE FROM {table}",
        ):
            if table in ("import_batches",) and "business_date" in statement:
                statement = f"UPDATE {table} SET status = status"
            with pytest.raises(Exception, match="append-only"):
                with engine.begin() as connection:
                    connection.execute(text(statement))


def test_an_application_dated_before_the_latest_loan_is_refused(session, config, benchmark):
    """A lender-imported merchant with an earlier loan: the application must come after it."""
    merchant_id = f"LIVE-{uuid.uuid4().hex[:8]}"
    end = calendar_end(config)
    session.add(
        db.Merchant(
            merchant_id=merchant_id,
            onboarded_at=end - timedelta(days=300),
            consent_data_use=True,
            questionnaire_done=False,
        )
    )
    session.commit()  # the merchant first: the models declare no order between the two
    session.add(
        db.Loan(
            loan_id=f"L-{merchant_id}",
            merchant_id=merchant_id,
            issued_at=end - timedelta(days=10),
            limit_bdt=30000.0,
        )
    )
    session.commit()
    grant(session, config, merchant_id, benchmark)
    with pytest.raises(IntakeRefused) as refused:
        apply(session, config, merchant_id, benchmark, business_date=end - timedelta(days=20))
    assert refused.value.code == "application_before_latest_loan"


def test_amount_purpose_and_note_are_checked(session, config, live, benchmark):
    grant(session, config, live, benchmark)
    for overrides, code in (
        ({"requested_amount_bdt": 0}, "invalid_amount"),
        ({"requested_amount_bdt": -5}, "invalid_amount"),
        (
            {"requested_amount_bdt": config["demo"]["application"]["max_requested_bdt"] + 1},
            "invalid_amount",
        ),
        ({"requested_amount_bdt": True}, "invalid_amount"),
        ({"purpose": "holiday"}, "invalid_choice"),
        ({"purpose_note": "x" * 301}, "note_too_long"),
    ):
        with pytest.raises(IntakeRefused) as refused:
            apply(session, config, live, benchmark, **overrides)
        assert refused.value.code == code, overrides
    assert count(session, db.Application, live) == 0


# --- one transaction ------------------------------------------------------------------


def test_a_failed_write_leaves_nothing_behind(session, config, live, benchmark, monkeypatch):
    def broken_audit(*args, **kwargs):
        raise RuntimeError("the audit entry could not be written")

    monkeypatch.setattr("src.intake.consent.add_audit", broken_audit)
    with pytest.raises(RuntimeError):
        grant(session, config, live, benchmark)
    assert count(session, db.Consent, live) == 0
    assert count(session, db.ConsentEvent, live) == 0
    assert provenance(session, live) == []

    monkeypatch.undo()
    grant(session, config, live, benchmark)
    monkeypatch.setattr("src.intake.applications.add_audit", broken_audit)
    with pytest.raises(RuntimeError):
        apply(session, config, live, benchmark)
    assert count(session, db.Application, live) == 0
    assert count(session, db.Loan, live) == 0


# --- the application through the existing scorer --------------------------------------


def test_a_new_application_is_scored_by_the_saved_model_and_the_amount_changes_nothing(
    session, config, world, benchmark
):
    """Two identical new merchants asking for very different amounts get the same score."""
    end = calendar_end(config)
    scorer = Scorer(config, tables=world, saved=load_model("synthetic_bd"))
    merchants = []
    for amount in (10000, 900000):
        merchant_id = f"LIVE-{uuid.uuid4().hex[:8]}"
        session.add(
            db.Merchant(
                merchant_id=merchant_id,
                onboarded_at=end - timedelta(days=200),
                consent_data_use=True,
                questionnaire_done=False,
            )
        )
        session.commit()  # the merchant first: the models declare no order between the two
        for days_ago, value in ((90, 8000.0), (60, 9500.0), (30, 11000.0), (7, 12000.0)):
            session.add(
                db.Purchase(
                    purchase_id=f"PU-{merchant_id}-{days_ago}",
                    merchant_id=merchant_id,
                    purchase_date=end - timedelta(days=days_ago),
                    amount_bdt=value,
                    category="rice_grain",
                    supplier_id="S0001",
                )
            )
        session.commit()
        grant(session, config, merchant_id, benchmark)
        apply(session, config, merchant_id, benchmark, requested_amount_bdt=amount)
        merchants.append(merchant_id)

    scored = scorer.set_imported(tables_for_merchants(session, merchants))
    assert set(merchants) <= set(scored)
    cards = [scorer.card(merchant_id) for merchant_id in merchants]
    assert cards[0]["score"] == cards[1]["score"]
    assert cards[0]["probability"] == pytest.approx(cards[1]["probability"])
    # the scored row is the application's row, still waiting for an outcome
    rows = [scorer.feature_row(merchant_id) for merchant_id in merchants]
    assert all(row["loan_id"].startswith("LA-") for row in rows)
    assert all(pd.isna(row["label"]) for row in rows)
