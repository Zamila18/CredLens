"""Tests for the demo workflow's endpoints (src/api/routes_intake.py).

Owner role: D (full-stack).
Implements: the implementation pack, Phase 3.9: permissions, consent, merchant creation and
    duplicates, records, repeat submissions, the benchmark kept read-only, applications and
    every place that must tell an application from an issued loan, and a failed refresh
    that must never show an older score as current.

The tests run the whole API on its own small world (a temporary database, a model trained
on it). Nothing here touches data/app.db.
"""

from __future__ import annotations

import copy
from datetime import timedelta
from types import SimpleNamespace

import pytest
from accounts_seed import headers_for, seed_accounts, seed_person  # noqa: F401
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config import load_config
from src.db import models as db
from src.db.load import load_tables
from src.db.mifos_adapter import build_export
from src.db.models import make_engine
from src.model.dataset import build_dataset
from src.model.labels import latest_date
from src.model.scoring import Scorer
from src.model.train import train_models
from src.synth.generate import build_tables

OFFICER = headers_for("officer-1")
ADMIN = headers_for("admin-1")
VIEWER = headers_for("viewer-1")
ALL = ["purchases", "deliveries", "payments", "questionnaire", "field_visits"]


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    from src.api.state import Services

    config = copy.deepcopy(load_config())
    config["data"]["n_merchants"] = 800
    config["model"]["bootstrap_resamples"] = 20
    config["model"]["candidates"] = ["logistic_regression"]
    config["score"]["reasons_report_sample"] = 10
    tables = build_tables(config, 0.5)[0]
    config["demo"]["calendar_end"] = latest_date(tables).date().isoformat()
    trained = train_models(build_dataset(tables, config), config)
    saved = {
        "model": trained["model"],
        "calibrator": trained["calibrator"],
        "features": trained["features"],
        "version_id": "test-intake",
    }
    url = "sqlite:///" + (tmp_path_factory.mktemp("api_intake") / "api.db").as_posix()
    load_tables(tables, url)
    engine = make_engine(url)
    seed_accounts(engine, config)
    services = Services(
        config=config, engine=engine, scorer=Scorer(config, tables=tables, saved=saved)
    )
    yield SimpleNamespace(services=services, tables=tables, config=config, engine=engine, url=url)
    engine.dispose()


@pytest.fixture(scope="module")
def api(world, monkeypatch_module):
    from src.api.main import app

    # /demo/settings reads the config file; give it this world's calendar.
    monkeypatch_module.setattr("src.api.routes_intake.load_config", lambda: world.config)
    app.state.services = world.services
    try:
        yield TestClient(app)
    finally:
        del app.state.services


@pytest.fixture(scope="module")
def monkeypatch_module():
    patcher = pytest.MonkeyPatch()
    yield patcher
    patcher.undo()


@pytest.fixture(scope="module")
def end(world):
    from datetime import date

    return date.fromisoformat(world.config["demo"]["calendar_end"])


_shop_counter = iter(range(1, 10_000))


def new_shop(api, **overrides) -> str:
    body = {
        "shop_name": f"Test Store {next(_shop_counter)}",
        "area": "Kawran Bazar",
        "district": "Dhaka",
        "shop_type": "grocery",
        "has_trade_license": False,
    }
    body.update(overrides)
    response = api.post("/merchants", json=body, headers=OFFICER)
    assert response.status_code == 201, response.text
    return response.json()["merchant_id"]


def consent(api, merchant_id, categories=None, response="granted"):
    return api.post(
        f"/merchants/{merchant_id}/consent-responses",
        json={
            "response": response,
            "categories": categories or ALL,
            "method": "assisted_on_phone",
        },
        headers=OFFICER,
    )


def purchase(api, merchant_id, day, amount=9000.0, **extra):
    return api.post(
        f"/merchants/{merchant_id}/purchases",
        json={"purchase_date": day.isoformat(), "amount_bdt": amount, **extra},
        headers=OFFICER,
    )


def ready_shop(api, end) -> str:
    """A shop with consent and a few purchases, ready for an application."""
    merchant_id = new_shop(api)
    assert consent(api, merchant_id).status_code == 201
    for days_ago, amount in ((80, 7000.0), (50, 8800.0), (20, 9900.0)):
        assert purchase(api, merchant_id, end - timedelta(days=days_ago), amount).status_code == 201
    return merchant_id


def apply(api, merchant_id, amount=30000):
    return api.post(
        f"/merchants/{merchant_id}/application",
        json={"requested_amount_bdt": amount, "purpose": "inventory_restock"},
        headers=OFFICER,
    )


def audit(world, merchant_id) -> list[str]:
    with Session(world.engine) as session:
        query = select(db.AuditEntry.action).where(db.AuditEntry.merchant_id == merchant_id)
        return list(session.scalars(query))


# --- settings, merchants and search -----------------------------------------------------


def test_demo_settings_come_from_the_config_and_need_no_token(api, world):
    body = api.get("/demo/settings").json()
    assert body["synthetic_only"] is True
    assert body["calendar_end"] == world.config["demo"]["calendar_end"]
    assert body["calendar_matches_data"] is True
    assert body["consent_categories"] == world.config["demo"]["consent"]["categories"]
    assert "Dhaka" in body["districts"] and "grocery" in body["shop_types"]


def test_a_new_shop_gets_a_permanent_server_id_and_can_be_found(api, world):
    merchant_id = new_shop(api, shop_name="Moyna Variety Store")
    assert merchant_id.startswith("CL-M-")
    found = api.get("/search/merchants", params={"q": "moyna"}, headers=VIEWER).json()
    assert [shop["merchant_id"] for shop in found] == [merchant_id]
    assert found[0]["created_in_app"] is True and found[0]["shop_name"] == "Moyna Variety Store"
    profile = api.get(f"/merchants/{merchant_id}", headers=OFFICER)
    assert profile.status_code == 200
    assert "create_merchant" in audit(world, merchant_id)


def test_a_likely_duplicate_must_be_confirmed_and_is_never_merged(api):
    first = new_shop(api, shop_name="New Star Store", district="Sylhet")
    again = api.post(
        "/merchants",
        json={"shop_name": "new  star store!", "district": "Sylhet", "shop_type": "grocery"},
        headers=OFFICER,
    )
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "possible_duplicate"
    assert [c["merchant_id"] for c in again.json()["detail"]["candidates"]] == [first]
    second = new_shop(api, shop_name="New Star Store", district="Sylhet", confirm_new=True)
    assert second != first
    # the same name in another district is not a likely duplicate
    assert new_shop(api, shop_name="New Star Store", district="Khulna")


def test_benchmark_merchants_are_found_by_id(api, world):
    merchant_id = world.tables["merchants"]["merchant_id"].iloc[0]
    found = api.get("/search/merchants", params={"q": merchant_id}, headers=OFFICER).json()
    assert found[0]["merchant_id"] == merchant_id and found[0]["created_in_app"] is False


def test_bad_shop_details_are_refused(api):
    for body in (
        {"shop_name": "  ", "district": "Dhaka", "shop_type": "grocery"},
        {"shop_name": "A shop", "district": "Atlantis", "shop_type": "grocery"},
        {"shop_name": "A shop", "district": "Dhaka", "shop_type": "casino"},
    ):
        assert api.post("/merchants", json=body, headers=OFFICER).status_code == 422


# --- permissions -----------------------------------------------------------------------


@pytest.mark.parametrize("headers", [VIEWER])  # an auditor reads; it never writes
def test_only_officers_can_write(api, headers, end):
    merchant_id = new_shop(api)
    writes = [
        ("/merchants", {"shop_name": "X", "district": "Dhaka", "shop_type": "grocery"}),
        (
            f"/merchants/{merchant_id}/consent-responses",
            {"response": "granted", "categories": ALL, "method": "assisted_on_phone"},
        ),
        (
            f"/merchants/{merchant_id}/purchases",
            {"purchase_date": end.isoformat(), "amount_bdt": 10.0},
        ),
        (f"/merchants/{merchant_id}/visits", {"outcome": "shop_open_trading"}),
        (
            f"/merchants/{merchant_id}/application",
            {"requested_amount_bdt": 100, "purpose": "other"},
        ),
    ]
    for url, body in writes:
        response = api.post(url, json=body, headers=headers)
        assert response.status_code == 403, url
    assert api.post("/merchants", json=writes[0][1]).status_code == 401


# --- consent and records -----------------------------------------------------------------


def test_consent_comes_first_and_refusals_are_audited(api, world, end):
    merchant_id = new_shop(api)
    response = purchase(api, merchant_id, end)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "consent_required"
    assert "refused_purchase" in audit(world, merchant_id)
    refused = consent(api, merchant_id, response="refused")
    assert refused.status_code == 201 and refused.json()["consent_id"] is None
    assert purchase(api, merchant_id, end).status_code == 403
    workflow = api.get(f"/merchants/{merchant_id}/workflow", headers=OFFICER).json()
    assert workflow["consent"] == "refused" and workflow["next_step"] == "record_consent"


def test_a_grant_is_labelled_simulated_and_unlocks_covered_records_only(api, end):
    merchant_id = new_shop(api)
    granted = consent(api, merchant_id, categories=["purchases"]).json()
    assert granted["simulated"] is True
    assert granted["label"] == "Simulated consent (synthetic demo)"
    assert granted["business_date"] == end.isoformat()
    assert granted["recorded_at"][:10] != granted["business_date"]  # real time kept apart
    assert purchase(api, merchant_id, end - timedelta(days=3)).status_code == 201
    visit = api.post(
        f"/merchants/{merchant_id}/visits", json={"outcome": "shop_open_trading"}, headers=OFFICER
    )
    assert visit.status_code == 403
    assert visit.json()["detail"]["code"] == "consent_category_missing"


def test_a_purchase_is_saved_with_provenance_and_a_double_tap_adds_nothing(api, world, end):
    merchant_id = new_shop(api)
    consent(api, merchant_id)
    first = purchase(api, merchant_id, end - timedelta(days=2), 4500.0, category="rice")
    assert first.status_code == 201
    saved = first.json()
    assert saved["entry_method"] == "staff_entered" and saved["status"] == "staff_entered"
    assert saved["repeat"] is False and saved["assessment"]["status"] == "no_application"
    again = purchase(api, merchant_id, end - timedelta(days=2), 4500.0, category="rice")
    assert again.json()["repeat"] is True
    assert again.json()["record_id"] == saved["record_id"]
    with Session(world.engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(db.Purchase)
                .where(db.Purchase.merchant_id == merchant_id)
            )
            == 1
        )


def test_a_paper_reference_is_recognised_again(api, end):
    merchant_id = new_shop(api)
    consent(api, merchant_id)
    assert (
        purchase(
            api, merchant_id, end - timedelta(days=9), 100.0, invoice_reference="INV-77"
        ).status_code
        == 201
    )
    again = purchase(api, merchant_id, end - timedelta(days=8), 200.0, invoice_reference="inv-77")
    assert again.status_code == 409 and again.json()["detail"]["code"] == "duplicate_reference"


def test_dates_after_the_calendar_and_bad_values_are_refused(api, end):
    merchant_id = new_shop(api)
    consent(api, merchant_id)
    late = purchase(api, merchant_id, end + timedelta(days=1))
    assert late.status_code == 422 and late.json()["detail"]["code"] == "date_after_demo_calendar"
    assert purchase(api, merchant_id, end, amount=0).status_code == 422
    delivery = api.post(
        f"/merchants/{merchant_id}/deliveries",
        json={"dispatched_at": f"{end}T10:00", "status": "lost", "is_cod": True},
        headers=OFFICER,
    )
    assert delivery.status_code == 422


def test_a_delivery_is_saved(api, end):
    merchant_id = new_shop(api)
    consent(api, merchant_id)
    response = api.post(
        f"/merchants/{merchant_id}/deliveries",
        json={
            "dispatched_at": f"{end - timedelta(days=4)}T09:30",
            "delivered_at": f"{end - timedelta(days=3)}T15:00",
            "status": "delivered",
            "is_cod": True,
            "cod_remitted_on_time": True,
        },
        headers=OFFICER,
    )
    assert response.status_code == 201, response.text


def test_benchmark_merchants_stay_read_only(api, world, end):
    merchant_id = world.tables["merchants"]["merchant_id"].iloc[0]
    response = purchase(api, merchant_id, end)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "benchmark_merchant"
    assert apply(api, merchant_id).json()["detail"]["code"] == "benchmark_merchant"


def test_nothing_can_be_written_when_synthetic_mode_is_off(api, world, end, monkeypatch):
    merchant_id = new_shop(api)
    monkeypatch.setitem(world.config["demo"], "synthetic_only", False)
    assert consent(api, merchant_id).json()["detail"]["code"] == "intake_closed"
    shop = api.post(
        "/merchants",
        json={"shop_name": "Closed shop", "district": "Dhaka", "shop_type": "grocery"},
        headers=OFFICER,
    )
    assert shop.status_code == 403 and shop.json()["detail"]["code"] == "intake_closed"


# --- applications ------------------------------------------------------------------------


def test_an_application_is_assessed_by_the_saved_model(api, end):
    merchant_id = ready_shop(api, end)
    response = apply(api, merchant_id, amount=45000)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved["record_type"] == "application"
    assert saved["assessment"]["status"] == "refreshed"
    score = api.get(f"/merchants/{merchant_id}/score", headers=OFFICER)
    assert score.status_code == 200 and 0 <= score.json()["score"] <= 100
    application = api.get(f"/merchants/{merchant_id}/application", headers=VIEWER).json()
    assert application["requested_amount_bdt"] == 45000
    assert application["assessment_status"] == "current"
    assert "not an issued loan" in application["note"]
    queue = {item["merchant_id"]: item for item in api.get("/merchants", headers=OFFICER).json()}
    assert queue[merchant_id]["status"] == "pending"
    workflow = api.get(f"/merchants/{merchant_id}/workflow", headers=OFFICER).json()
    assert workflow["next_step"] == "await_review"
    # a record dated after the application cannot count for it, and the answer says so
    later = purchase(api, merchant_id, end, 5000.0)
    assert later.json()["counts_for_assessment"] is False


def test_one_application_per_merchant(api, end):
    merchant_id = ready_shop(api, end)
    assert apply(api, merchant_id).status_code == 201
    again = apply(api, merchant_id, amount=1000)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "application_exists"


def test_an_application_is_never_shown_or_exported_as_an_issued_loan(api, world, end):
    merchant_id = ready_shop(api, end)
    apply(api, merchant_id, amount=52000)
    loans = api.get(f"/merchants/{merchant_id}/loans", headers=OFFICER).json()
    assert len(loans) == 1
    assert loans[0]["kind"] == "application" and loans[0]["limit_bdt"] is None
    assert loans[0]["requested_amount_bdt"] == 52000 and loans[0]["repayment_allowed"] is False
    timeline = api.get(f"/merchants/{merchant_id}", headers=OFFICER).json()["timeline"]
    events = [event for event in timeline if event["stream"] == "loan"]
    assert [event["kind"] for event in events] == ["application"]
    assert events[0]["amount_bdt"] == 52000 and "not a loan" in events[0]["label"]
    exported = build_export(world.url)["loans"]
    assert loans[0]["loan_id"] not in set(exported["externalId"])


def test_a_repayment_needs_a_real_earlier_loan_of_the_same_merchant(api, world, end):
    merchant_id = ready_shop(api, end)
    apply(api, merchant_id)
    application_loan = api.get(f"/merchants/{merchant_id}/loans", headers=OFFICER).json()[0][
        "loan_id"
    ]
    body = {
        "due_date": end.isoformat(),
        "paid_date": end.isoformat(),
        "amount_due_bdt": 100,
        "amount_paid_bdt": 100,
    }
    on_application = api.post(
        f"/merchants/{merchant_id}/repayments",
        json={"loan_id": application_loan, **body},
        headers=OFFICER,
    )
    assert on_application.status_code == 422
    assert on_application.json()["detail"]["code"] == "application_not_loan"
    someone_elses = world.tables["loans"]["loan_id"].iloc[0]
    wrong = api.post(
        f"/merchants/{merchant_id}/repayments",
        json={"loan_id": someone_elses, **body},
        headers=OFFICER,
    )
    assert wrong.json()["detail"]["code"] == "wrong_loan"


def test_a_repayment_on_a_real_earlier_loan_is_saved(api, world, end):
    """A merchant that came with a lender's earlier loan (as an import would bring it)."""
    merchant_id = new_shop(api)
    consent(api, merchant_id)
    with Session(world.engine) as session:
        session.add(
            db.Loan(
                loan_id=f"L-{merchant_id}",
                merchant_id=merchant_id,
                issued_at=end - timedelta(days=100),
                limit_bdt=20000.0,
            )
        )
        session.commit()
    response = api.post(
        f"/merchants/{merchant_id}/repayments",
        json={
            "loan_id": f"L-{merchant_id}",
            "due_date": (end - timedelta(days=70)).isoformat(),
            "paid_date": (end - timedelta(days=72)).isoformat(),
            "amount_due_bdt": 20000,
            "amount_paid_bdt": 20000,
        },
        headers=OFFICER,
    )
    assert response.status_code == 201, response.text
    loans = api.get(f"/merchants/{merchant_id}/loans", headers=OFFICER).json()
    assert loans[0]["kind"] == "loan" and loans[0]["repayment_allowed"] is True


def test_an_officer_can_decide_on_an_application(api, end):
    merchant_id = ready_shop(api, end)
    apply(api, merchant_id)
    decision = api.post(
        f"/merchants/{merchant_id}/decision",
        json={"officer_action": "needs_more_info", "reason_text": "Ask for supplier invoices."},
        headers=OFFICER,
    )
    assert decision.status_code == 201, decision.text
    assert decision.json()["band_shown"] is not None


# --- a failed refresh never shows an older score as current -----------------------------


def test_a_failed_refresh_says_not_updated_and_keeps_the_records(api, world, end, monkeypatch):
    healthy = ready_shop(api, end)
    apply(api, healthy)
    broken = ready_shop(api, end)
    apply(api, broken)
    assert api.get(f"/merchants/{broken}/score", headers=OFFICER).status_code == 200

    import src.model.dataset as dataset_module

    real = dataset_module.build_dataset

    def failing_for_broken(tables, *args, **kwargs):
        if broken in set(tables["merchants"]["merchant_id"]):
            raise ValueError("cannot read these records")
        return real(tables, *args, **kwargs)

    monkeypatch.setattr(dataset_module, "build_dataset", failing_for_broken)
    monkeypatch.setattr("src.model.scoring.build_dataset", failing_for_broken)
    monkeypatch.setattr("src.intake.records.check_scoring_inputs", lambda *a, **k: None)
    visit = api.post(
        f"/merchants/{broken}/visits", json={"outcome": "follow_up_needed"}, headers=OFFICER
    )
    assert visit.status_code == 201  # the record is saved
    assert visit.json()["assessment"]["status"] == "not_updated"

    stale = api.get(f"/merchants/{broken}/score", headers=OFFICER)
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "assessment_not_updated"
    decision = api.post(
        f"/merchants/{broken}/decision", json={"officer_action": "accept"}, headers=OFFICER
    )
    assert decision.status_code == 409
    queue = {item["merchant_id"]: item for item in api.get("/merchants", headers=OFFICER).json()}
    assert broken not in queue or (
        queue[broken]["score"] is None and queue[broken]["assessment_status"] == "not_updated"
    )
    assert api.get(f"/merchants/{healthy}/score", headers=OFFICER).status_code == 200
    application = api.get(f"/merchants/{broken}/application", headers=OFFICER).json()
    assert application["assessment_status"] == "not_updated"
    stale_review = api.get(f"/merchants/{broken}/review", headers=OFFICER).json()
    assert stale_review["assessment"] == "not_updated"
    assert stale_review["readiness"] == "not_updated"

    monkeypatch.undo()
    # once the records can be read again, the next save brings the assessment back
    again = api.post(
        f"/merchants/{broken}/visits", json={"outcome": "shop_open_trading"}, headers=OFFICER
    )
    assert again.json()["assessment"]["status"] == "refreshed"
    assert api.get(f"/merchants/{broken}/score", headers=OFFICER).status_code == 200


def test_records_that_cannot_be_scored_are_not_saved(api, world, end, monkeypatch):
    merchant_id = ready_shop(api, end)
    apply(api, merchant_id)

    def broken(*args, **kwargs):
        raise ValueError("cannot read these records")

    monkeypatch.setattr("src.model.dataset.build_dataset", broken)
    response = purchase(api, merchant_id, end - timedelta(days=5), 777.0)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "records_not_usable"
    with Session(world.engine) as session:
        amounts = session.scalars(
            select(db.Purchase.amount_bdt).where(db.Purchase.merchant_id == merchant_id)
        ).all()
    assert 777.0 not in amounts


def test_the_field_list_shows_created_shops_newest_first_with_their_next_step(api, end):
    first = new_shop(api)
    second = ready_shop(api, end)
    shops = api.get("/field/shops", params={"limit": 50}, headers=VIEWER).json()
    order = [shop["merchant"]["merchant_id"] for shop in shops]
    assert order.index(second) < order.index(first)
    by_id = {shop["merchant"]["merchant_id"]: shop for shop in shops}
    assert by_id[first]["next_step"] == "record_consent"
    assert by_id[second]["next_step"] == "create_application"
    assert by_id[second]["created_at"] and by_id[second]["calendar_end"] == end.isoformat()
    assert all(shop["merchant"]["created_in_app"] for shop in shops)


# --- officer workspace (Phase 6) ----------------------------------------------------------


def _checks(review) -> dict[str, dict]:
    return {c["code"]: c for c in review["checks"]}


def test_the_review_of_an_application_follows_the_written_rules(api, world, end):
    from src.api import review as rules
    from src.api.schemas import ReadinessCheck

    merchant_id = ready_shop(api, end)
    apply(api, merchant_id, amount=40000)
    review = api.get(f"/merchants/{merchant_id}/review", headers=VIEWER).json()
    band = api.get(f"/merchants/{merchant_id}/score", headers=OFFICER).json()["band"]

    assert review["application"]["requested_amount_bdt"] == 40000
    assert review["assessment"] == "current"
    checks = _checks(review)
    assert checks["consent"]["passed"] and checks["assessment"]["passed"]
    assert checks["history"]["passed"] == (band != "Needs more info")
    assert checks["field_visit"] == {"code": "field_visit", "kind": "check", "passed": False}
    assert checks["deliveries"]["kind"] == "info" and not checks["deliveries"]["passed"]
    expected = rules.readiness([ReadinessCheck(**c) for c in review["checks"]], "current")
    assert review["readiness"] == expected

    groups = {g["group"]: g for g in review["evidence"]}
    assert groups["purchases"]["total"] == 3 == groups["purchases"]["with_entry_record"]
    first = groups["purchases"]["latest"][0]
    assert first["entry_method"] == "staff_entered" and first["simulated"] is True
    assert first["business_date"] == (end - timedelta(days=20)).isoformat()  # newest first
    assert groups["repayments"]["total"] == 0  # an application never has a repayment
    rng = review["range"]  # no company policy is approved: there is no range
    assert rng["available"] is False and rng["reason"] == "policy_not_configured"
    assert "view_review" in audit(world, merchant_id)

    # a field visit settles the one check; the score and its band are untouched
    api.post(
        f"/merchants/{merchant_id}/visits", json={"outcome": "shop_open_trading"}, headers=OFFICER
    )
    after = api.get(f"/merchants/{merchant_id}/review", headers=OFFICER).json()
    assert _checks(after)["field_visit"]["passed"] is True
    assert after["readiness"] in ("ready", "more_info_needed")
    assert api.get(f"/merchants/{merchant_id}/score", headers=OFFICER).json()["band"] == band


def test_without_consent_the_review_asks_for_more_information(api):
    merchant_id = new_shop(api)
    review = api.get(f"/merchants/{merchant_id}/review", headers=OFFICER).json()
    assert review["assessment"] == "consent_required"
    assert review["readiness"] == "more_info_needed"
    assert review["application"] is None
    assert not _checks(review)["consent"]["passed"]


def test_benchmark_records_have_no_invented_entry_record(api, world):
    merchant_id = world.tables["merchants"]["merchant_id"].iloc[0]
    review = api.get(f"/merchants/{merchant_id}/review", headers=OFFICER)
    assert review.status_code == 200
    for group in review.json()["evidence"]:
        assert group["with_entry_record"] == 0
        assert all(r["entry_method"] is None for r in group["latest"])


def test_missing_deliveries_never_block_review_and_no_range_when_the_policy_is_off(world, end):
    from src.api import review as rules

    checks = rules.build_checks(
        world.config,
        consent_valid=True,
        assessment="current",
        band="Review",
        has_application=True,
        visits=1,
        deliveries=0,
    )
    assert rules.readiness(checks, "current") == "ready"
    low = rules.build_checks(
        world.config,
        consent_valid=True,
        assessment="current",
        band="Needs more info",
        has_application=False,
        visits=0,
        deliveries=5,
    )
    assert rules.readiness(low, "current") == "more_info_needed"
    assert rules.readiness(checks, "not_updated") == "not_updated"
    with Session(world.engine) as session:
        guidance = rules.range_guidance(
            world.config, session, "none", None, "current", "Strong", end
        )
    assert guidance.available is False and guidance.reason == "policy_not_configured"


# --- Excel purchase import (Phase 7) -------------------------------------------------------


def _xlsx(rows: list[list], title: str = "Purchases") -> bytes:
    import io

    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.title = title
    for row in rows:
        sheet.append(row)
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


MAPPING = (
    '{"purchase_date": "Date", "amount_bdt": "Total", "category": "Items",'
    ' "invoice_reference": "Memo No"}'
)
SIMPLE = '{"purchase_date": "Date", "amount_bdt": "Total"}'


def _import(api, merchant_id, data, step, **params):
    params = {"sheet": "Purchases", "mapping": MAPPING, **params}
    return api.post(
        f"/merchants/{merchant_id}/purchase-import/{step}",
        content=data,
        params=params if step != "inspect" else None,
        headers=OFFICER,
    )


def _commit(api, merchant_id, data, **params):
    preview = _import(api, merchant_id, data, "preview", **params).json()
    return preview, _import(
        api, merchant_id, data, "commit", preview_token=preview["preview_token"], **params
    )


def _purchases(world, merchant_id) -> int:
    with Session(world.engine) as session:
        query = select(func.count()).select_from(db.Purchase)
        return session.scalar(query.where(db.Purchase.merchant_id == merchant_id))


def test_a_workbook_is_inspected_with_suggested_columns_and_nothing_saved(api, world, end):
    merchant_id = new_shop(api)
    consent(api, merchant_id)
    data = _xlsx([["Memo No", "Date", "Items", "Total"], ["M-1", end.isoformat(), "Rice", 500]])
    inspect = _import(api, merchant_id, data, "inspect")
    assert inspect.status_code == 200, inspect.text
    sheet = inspect.json()["sheets"][0]
    assert sheet["name"] == "Purchases" and sheet["rows"] == 1
    assert sheet["suggested"]["amount_bdt"] == "Total"
    assert sheet["suggested"]["invoice_reference"] == "Memo No"
    assert _import(api, merchant_id, data, "preview").status_code == 200
    assert _purchases(world, merchant_id) == 0  # inspect and preview write nothing


def test_bad_files_wrong_sheets_and_missing_columns_are_refused(api, world, end):
    merchant_id = new_shop(api)
    consent(api, merchant_id)
    data = _xlsx([["Date", "Total"], [end.isoformat(), 500]])
    bad = _import(api, merchant_id, b"a,b\n1,2", "inspect")
    assert bad.json()["detail"]["code"] == "not_a_workbook"
    wrong = _import(api, merchant_id, data, "preview", sheet="Sheet9")
    assert wrong.status_code == 422 and wrong.json()["detail"]["code"] == "unknown_sheet"
    missing = _import(api, merchant_id, data, "preview")  # MAPPING names Items and Memo No
    assert missing.status_code == 422 and missing.json()["detail"]["code"] == "missing_column"
    no_amount = _import(api, merchant_id, data, "preview", mapping='{"purchase_date": "Date"}')
    assert no_amount.json()["detail"]["code"] == "missing_column"
    benchmark = world.tables["merchants"]["merchant_id"].iloc[0]
    refused = _import(api, benchmark, data, "inspect")
    assert refused.json()["detail"]["code"] == "benchmark_merchant"
    no_consent = new_shop(api)
    assert _import(api, no_consent, data, "inspect").status_code == 403
    viewer = api.post(
        f"/merchants/{merchant_id}/purchase-import/inspect", content=data, headers=VIEWER
    )
    assert viewer.status_code == 403


def test_rows_are_previewed_and_saved_with_provenance_and_errors_stay_out(api, world, end):
    merchant_id = new_shop(api)
    consent(api, merchant_id)
    day = end - timedelta(days=10)
    data = _xlsx(
        [
            ["Memo No", "Date", "Items", "Total"],
            ["M-1", day.isoformat(), "Rice", "৳ 9,500"],
            [None, day.isoformat(), "Oil", 1200],
            ["M-3", (end + timedelta(days=5)).isoformat(), "Soap", 300],  # after the calendar
            ["M-4", "someday", "Salt", 100],
            ["M-5", day.isoformat(), "Sugar", "lots"],
        ]
    )
    preview, committed = _commit(api, merchant_id, data)
    assert preview["counts"] == {"add": 2, "skip": 0, "flag": 0, "reject": 3}
    codes = {r["row_number"]: r["code"] for r in preview["rows"]}
    assert codes[4] == "date_after_calendar" and codes[5] == "bad_date"
    assert codes[6] == "bad_amount"
    assert committed.status_code == 201, committed.text
    result = committed.json()
    assert (result["added"], result["rejected"]) == (2, 3)
    assert _purchases(world, merchant_id) == 2
    with Session(world.engine) as session:
        rows = session.scalars(
            select(db.RecordProvenance).where(
                db.RecordProvenance.merchant_id == merchant_id,
                db.RecordProvenance.record_type == "purchase",
            )
        ).all()
        batch = session.get(db.ImportBatch, result["batch_id"])
        assert {r.entry_method for r in rows} == {"imported_spreadsheet"}
        assert {r.batch_id for r in rows} == {result["batch_id"]}
        assert batch.rows_added == 2 and len(batch.file_sha256) == 64
    assert "import_purchases" in audit(world, merchant_id)
    left_out = _issues(api, merchant_id=merchant_id)[f"import:{result['batch_id']}"]
    assert left_out["kind"] == "import_rows_left_out" and left_out["facts"]["rejected"] == 3
    assert _review(api, left_out, "acknowledged").json()["status"] == "reviewed"

    # the same workbook again adds nothing: every row is recognised
    again_preview, again = _commit(api, merchant_id, data)
    assert again_preview["counts"]["add"] == 0 and again_preview["counts"]["skip"] == 2
    assert again.json()["added"] == 0 and _purchases(world, merchant_id) == 2


def test_references_already_typed_in_are_skipped_and_lookalikes_are_flagged(api, world, end):
    merchant_id = new_shop(api)
    consent(api, merchant_id)
    day = end - timedelta(days=3)
    purchase(api, merchant_id, day, 700.0, invoice_reference="M-77")
    purchase(api, merchant_id, day, 450.0)
    data = _xlsx(
        [
            ["Memo No", "Date", "Items", "Total"],
            ["M-77", day.isoformat(), None, 700],  # typed in already, same paper
            [None, day.isoformat(), None, 450],  # same date and amount, no reference
            [None, (day - timedelta(days=1)).isoformat(), None, 900],  # new
            ["M-80", day.isoformat(), None, 120],
            ["M-80", day.isoformat(), None, 130],  # the same reference twice in the file
        ]
    )
    preview = _import(api, merchant_id, data, "preview").json()
    by_row = {r["row_number"]: (r["outcome"], r["code"]) for r in preview["rows"]}
    assert by_row[2] == ("skip", "reference_saved")
    assert by_row[3] == ("flag", "possible_duplicate")
    assert by_row[4] == ("add", "new")
    assert by_row[6] == ("reject", "reference_twice_in_file")
    # a flagged row is saved only when the person keeps it
    kept = _import(
        api, merchant_id, data, "commit", preview_token=preview["preview_token"], keep_flagged="3"
    ).json()
    assert (kept["added"], kept["flagged_kept"], kept["flagged_left"]) == (3, 1, 0)
    assert _purchases(world, merchant_id) == 5


def test_ambiguous_dates_need_a_chosen_order(api, world):
    merchant_id = new_shop(api)
    consent(api, merchant_id)
    data = _xlsx([["Date", "Total"], ["03/04/2026", 500], ["25/04/2026", 600]])
    preview = _import(api, merchant_id, data, "preview", mapping=SIMPLE).json()
    assert preview["date_order_needed"] is True
    assert preview["rows"][0]["code"] == "ambiguous_date"
    refused = _import(
        api, merchant_id, data, "commit", mapping=SIMPLE, preview_token=preview["preview_token"]
    )
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "date_order_needed"
    chosen = _import(api, merchant_id, data, "preview", mapping=SIMPLE, date_order="dmy").json()
    assert chosen["date_order_needed"] is False
    assert chosen["rows"][0]["purchase_date"] == "2026-04-03"


def test_a_changed_file_or_mapping_after_the_preview_is_refused(api, world, end):
    merchant_id = new_shop(api)
    consent(api, merchant_id)
    data = _xlsx([["Date", "Total", "Other"], [end.isoformat(), 500, 1]])
    token = _import(api, merchant_id, data, "preview", mapping=SIMPLE).json()["preview_token"]
    changed = _xlsx([["Date", "Total", "Other"], [end.isoformat(), 5000, 1]])
    refused = _import(api, merchant_id, changed, "commit", mapping=SIMPLE, preview_token=token)
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "preview_changed"
    other = '{"purchase_date": "Date", "amount_bdt": "Other"}'
    refused = _import(api, merchant_id, data, "commit", mapping=other, preview_token=token)
    assert refused.json()["detail"]["code"] == "preview_changed"
    assert _purchases(world, merchant_id) == 0


def test_an_import_that_cannot_be_scored_saves_nothing(api, world, end, monkeypatch):
    from src.intake.policy import IntakeRefused

    merchant_id = ready_shop(api, end)
    apply(api, merchant_id)
    before = _purchases(world, merchant_id)

    def refuse(*args, **kwargs):
        raise IntakeRefused(422, "records_not_usable", "These records could not be read.")

    monkeypatch.setattr("src.intake.spreadsheet.check_scoring_inputs", refuse)
    data = _xlsx([["Date", "Total"], [(end - timedelta(days=40)).isoformat(), 800]])
    _, committed = _commit(api, merchant_id, data, mapping=SIMPLE)
    assert committed.status_code == 422
    assert committed.json()["detail"]["code"] == "records_not_usable"
    assert _purchases(world, merchant_id) == before
    with Session(world.engine) as session:
        query = select(func.count()).select_from(db.ImportBatch)
        assert session.scalar(query.where(db.ImportBatch.merchant_id == merchant_id)) == 0


# --- data receipt and evidence requests (Phase 8) ------------------------------------------


def test_the_receipt_lists_what_is_stored_and_nothing_private(api, world, end):
    merchant_id = ready_shop(api, end)
    api.post(
        f"/merchants/{merchant_id}/visits",
        json={"outcome": "shop_open_trading", "note": "PRIVATE officer remark"},
        headers=OFFICER,
    )
    api.post(
        f"/merchants/{merchant_id}/application",
        json={
            "requested_amount_bdt": 25000,
            "purpose": "inventory_restock",
            "purpose_note": "PRIVATE note",
        },
        headers=OFFICER,
    )
    response = api.get(f"/merchants/{merchant_id}/receipt", headers=OFFICER)
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert receipt["merchant"]["merchant_id"] == merchant_id
    assert receipt["consent"][0]["response"] == "granted"
    assert receipt["consent"][0]["simulated"] is True
    kinds = [r["record_type"] for r in receipt["records"]]
    assert kinds.count("purchase") == 3
    assert {"merchant", "visit", "application"} <= set(kinds)
    application = next(r for r in receipt["records"] if r["record_type"] == "application")
    assert application["amount_bdt"] == 25000
    text = response.text
    for private in ("PRIVATE", "score", "decision", "probability", "officer_action"):
        assert private not in text
    assert all(r["entry_method"] == "staff_entered" for r in receipt["records"])
    assert "view_receipt" in audit(world, merchant_id)


def test_the_receipt_is_for_officers_and_app_shops_only(api, world):
    merchant_id = new_shop(api)
    assert api.get(f"/merchants/{merchant_id}/receipt", headers=VIEWER).status_code == 403
    assert api.get(f"/merchants/{merchant_id}/receipt", headers=ADMIN).status_code == 200
    assert api.get(f"/merchants/{merchant_id}/receipt").status_code == 401
    benchmark = world.tables["merchants"]["merchant_id"].iloc[0]
    refused = api.get(f"/merchants/{benchmark}/receipt", headers=OFFICER)
    assert refused.status_code == 409
    assert api.get("/merchants/CL-M-999999/receipt", headers=OFFICER).status_code == 404
    # a refusal is on the receipt too, with no records after it
    consent(api, merchant_id, response="refused")
    receipt = api.get(f"/merchants/{merchant_id}/receipt", headers=OFFICER).json()
    assert [c["response"] for c in receipt["consent"]] == ["refused"]
    assert [r["record_type"] for r in receipt["records"]] == ["merchant"]


def test_evidence_requests_follow_the_written_rules(api, world, end):
    name = f"Evidence Store {next(_shop_counter)}"
    first = new_shop(api, shop_name=name)
    duplicate_id = new_shop(api, shop_name=name, confirm_new=True)
    consent(api, duplicate_id)
    day = end - timedelta(days=12)
    purchase(api, duplicate_id, day, 64000.0, invoice_reference="BIG-1")
    purchase(api, duplicate_id, day - timedelta(days=5), 800.0, invoice_reference="A-1")
    purchase(api, duplicate_id, day - timedelta(days=5), 800.0, invoice_reference="A-2")
    apply(api, duplicate_id)
    review = api.get(f"/merchants/{duplicate_id}/review", headers=OFFICER).json()
    codes = [r["code"] for r in review["evidence_requests"]]
    assert codes == [
        "confirm_not_same_shop",
        "confirm_possible_duplicate",
        "show_memo_for_large_purchase",
    ]
    asks = {r["code"]: r for r in review["evidence_requests"]}
    assert asks["confirm_not_same_shop"]["other_merchant_id"] == first
    assert asks["show_memo_for_large_purchase"]["amount_bdt"] == 64000.0
    assert asks["confirm_possible_duplicate"]["amount_bdt"] == 800.0

    empty = new_shop(api)
    consent(api, empty)
    assert api.get(f"/merchants/{empty}/review", headers=OFFICER).json()["evidence_requests"] == []
    benchmark = world.tables["merchants"]["merchant_id"].iloc[0]
    bench = api.get(f"/merchants/{benchmark}/review", headers=OFFICER).json()
    assert bench["evidence_requests"] == []  # generated rows have no paper to ask for


# --- workspace lists and overview (product redesign) ---------------------------------------


def test_the_applications_list_shows_requests_with_review_and_decision(api, world, end):
    merchant_id = ready_shop(api, end)
    apply(api, merchant_id, amount=27000)
    rows = {r["merchant_id"]: r for r in api.get("/applications", headers=VIEWER).json()}
    row = rows[merchant_id]
    assert row["requested_amount_bdt"] == 27000 and row["shop_name"].startswith("Test Store")
    assert row["assessment"] == "current" and row["decision"] is None
    review = api.get(f"/merchants/{merchant_id}/review", headers=OFFICER).json()
    assert row["readiness"] == review["readiness"]
    api.post(
        f"/merchants/{merchant_id}/decision",
        json={"officer_action": "needs_more_info"},
        headers=OFFICER,
    )
    again = {r["merchant_id"]: r for r in api.get("/applications", headers=OFFICER).json()}
    assert again[merchant_id]["decision"] == "needs_more_info"


def test_the_directory_searches_and_pages_on_the_server(api, world):
    name = f"Directory Store {next(_shop_counter)}"
    merchant_id = new_shop(api, shop_name=name, area="Uttara")
    page = api.get("/directory/merchants", params={"q": name}, headers=VIEWER).json()
    assert page["total"] == 1 and page["items"][0]["merchant_id"] == merchant_id
    assert page["items"][0]["created_in_app"] is True
    assert page["items"][0]["consent"] == "none"
    benchmark = api.get(
        "/directory/merchants", params={"source": "benchmark", "limit": 5}, headers=VIEWER
    ).json()
    assert benchmark["total"] == len(world.tables["merchants"])
    assert len(benchmark["items"]) == 5
    assert not any(i["created_in_app"] for i in benchmark["items"])
    first = api.get("/directory/merchants", params={"limit": 3}, headers=VIEWER).json()
    assert first["items"][0]["created_in_app"] is True  # shops made in the app come first
    assert api.get("/directory/merchants", params={"limit": 500}).status_code in (401, 422)


def test_import_batches_list_and_detail(api, world, end):
    merchant_id = new_shop(api)
    consent(api, merchant_id)
    data = _xlsx([["Date", "Total"], [(end - timedelta(days=4)).isoformat(), 640]])
    _, committed = _commit(api, merchant_id, data, mapping=SIMPLE)
    batch_id = committed.json()["batch_id"]
    batches = api.get(
        "/import-batches", params={"merchant_id": merchant_id}, headers=OFFICER
    ).json()
    assert [b["batch_id"] for b in batches] == [batch_id]
    detail = api.get(f"/import-batches/{batch_id}", headers=ADMIN).json()
    assert detail["rows_added"] == 1 and len(detail["records"]) == 1
    assert detail["records"][0]["entry_method"] == "imported_spreadsheet"
    assert api.get("/import-batches", headers=VIEWER).status_code == 403
    assert api.get("/import-batches/IB-none", headers=OFFICER).status_code == 404


def test_the_overview_counts_from_the_database(api, world, end):
    merchant_id = ready_shop(api, end)
    apply(api, merchant_id)
    data = api.get("/overview", headers=VIEWER).json()
    with Session(world.engine) as session:
        applications = session.scalar(select(func.count()).select_from(db.Application))
        loans = session.scalar(select(func.count()).select_from(db.Loan))
        merchants = session.scalar(select(func.count()).select_from(db.Merchant))
    assert data["applications_total"] == applications
    assert data["issued_loans"] == loans - applications  # an application is never a loan
    assert data["merchants_total"] == merchants
    assert 0 <= data["applications_awaiting_decision"] <= applications
    assert data["recent"] and data["recent"][0]["at"] >= data["recent"][-1]["at"]
    assert any(e["merchant_id"] == merchant_id for e in data["recent"])

    evidence = data["evidence"]
    with Session(world.engine) as session:
        shops = session.scalar(select(func.count()).select_from(db.MerchantProfile))
        typed = session.scalar(
            select(func.count(func.distinct(db.RecordProvenance.record_id))).where(
                db.RecordProvenance.record_type == "purchase",
                db.RecordProvenance.entry_method == "staff_entered",
            )
        )
    assert evidence["app_shops"] == shops
    assert evidence["coverage"]["application"] == applications
    assert 1 <= evidence["coverage"]["purchases"] <= shops
    by_source = {(r["record_type"], r["source"]): r["records"] for r in evidence["by_source"]}
    assert by_source[("purchase", "typed_in")] == typed
    assert sum(r["records"] for r in evidence["by_month"]) <= sum(by_source.values())
    assert all(r["month"] <= end.isoformat()[:7] for r in evidence["by_month"])

    review = api.get(f"/merchants/{merchant_id}/review", headers=VIEWER).json()
    purchases = next(g for g in review["evidence"] if g["group"] == "purchases")
    assert purchases["by_source"] == {"typed_in": 3}
    benchmark = world.tables["merchants"]["merchant_id"].iloc[0]
    bench = api.get(f"/merchants/{benchmark}/review", headers=VIEWER).json()
    assert set().union(*(g["by_source"] for g in bench["evidence"])) <= {"generated"}


def test_the_profile_names_a_shop_created_in_the_app(api, end):
    merchant_id = ready_shop(api, end)
    apply(api, merchant_id)
    profile = api.get(f"/merchants/{merchant_id}", headers=VIEWER).json()
    assert profile["shop_name"].startswith("Test Store") and profile["area"] == "Kawran Bazar"


# --- organisations: the institution boundary (workstream B) --------------------------------

OFFICER_B = headers_for("officer-b")


@pytest.fixture(scope="module")
def org_b(api, world):
    """A second organisation with one officer, added straight to the test database."""
    from datetime import datetime

    with Session(world.engine) as session:
        session.add(
            db.Organization(
                organization_id="org-b",
                name="Second Institution",
                environment="pilot",
                country="BD",
                languages="en|bn",
                currency="BDT",
                timezone="Asia/Dhaka",
                created_at=datetime(2026, 10, 31),
            )
        )
        session.add(
            db.User(
                user_id="officer-b",
                display_name="Officer B",
                role="viewer",
                organization_id="org-b",
            )
        )
        session.flush()
        seed_person(session, "officer-b", "credit_officer", "org-b", owner=True)
        session.commit()
    return "org-b"


def test_each_organisation_sees_only_its_own_merchants(api, world, org_b, end):
    name = f"Boundary Store {next(_shop_counter)}"
    created = api.post(
        "/merchants",
        json={"shop_name": name, "district": "Dhaka", "shop_type": "grocery"},
        headers=OFFICER_B,
    )
    assert created.status_code == 201, created.text
    b_shop = created.json()["merchant_id"]
    with Session(world.engine) as session:
        assert session.get(db.Merchant, b_shop).organization_id == "org-b"

    # The default organisation cannot read or write org B's shop: the same 404 as no shop.
    for path in ("", "/workflow", "/receipt", "/review", "/consent", "/loans"):
        response = api.get(f"/merchants/{b_shop}{path}", headers=OFFICER)
        assert response.status_code == 404, (path, response.status_code)
    refused = api.post(
        f"/merchants/{b_shop}/purchases",
        json={"purchase_date": end.isoformat(), "amount_bdt": 100.0},
        headers=OFFICER,
    )
    assert refused.status_code == 404
    # ...and org B cannot read a benchmark merchant of the default organisation.
    benchmark = world.tables["merchants"]["merchant_id"].iloc[0]
    assert api.get(f"/merchants/{benchmark}", headers=OFFICER_B).status_code == 404

    # Lists, search and duplicate warnings stay inside each organisation.
    directory_b = api.get("/directory/merchants", headers=OFFICER_B).json()
    assert [i["merchant_id"] for i in directory_b["items"]] == [b_shop]
    assert directory_b["total"] == 1
    found = api.get("/search/merchants", params={"q": name}, headers=OFFICER).json()
    assert found == []
    shops_b = api.get("/field/shops", headers=OFFICER_B).json()
    assert [s["merchant"]["merchant_id"] for s in shops_b] == [b_shop]
    queue_b = api.get("/merchants", headers=OFFICER_B).json()
    assert all(item["merchant_id"] == b_shop for item in queue_b)
    same_name = api.post(
        "/merchants",
        json={"shop_name": name, "district": "Dhaka", "shop_type": "grocery"},
        headers=OFFICER,
    )
    assert same_name.status_code == 201  # no "possible duplicate" from another organisation
    overview_b = api.get("/overview", headers=OFFICER_B).json()
    assert overview_b["merchants_total"] == 1 and overview_b["issued_loans"] == 0
    assert overview_b["evidence"]["app_shops"] == 1  # only its own shop
    assert api.get("/decisions", headers=OFFICER_B).json() == []


def test_the_organisation_endpoint_names_the_callers_organisation(api, world, org_b):
    mine = api.get("/organization", headers=OFFICER).json()
    assert mine["organization_id"] == world.config["organization"]["id"]
    assert mine["environment"] == "benchmark" and mine["currency"] == "BDT"
    theirs = api.get("/organization", headers=OFFICER_B).json()
    assert theirs == {
        "organization_id": "org-b",
        "name": "Second Institution",
        "environment": "pilot",
        "country": "BD",
        "languages": ["en", "bn"],
        "currency": "BDT",
        "timezone": "Asia/Dhaka",
    }
    assert api.get("/organization").status_code == 401


# --- data sources and connectors (workstream C) --------------------------------------------

FEED_MAPPING = {
    "merchant_ref": "shop_code",
    "merchant_name": "shop_title",
    "district": "area_district",
    "record_kind": "event_type",
    "business_date": "event_date",
    "amount": "value",
    "delivery_status": "parcel_status",
    "source_reference": "txn_id",
}


def _source(api, feed="standard", **extra):
    body = {
        "connector_key": "sandbox_feed",
        "display_name": f"Feed {next(_shop_counter)}",
        "settings": {"feed": feed, **{k: v for k, v in extra.items() if k != "secret_ref"}},
    }
    if "secret_ref" in extra:
        body["secret_ref"] = extra["secret_ref"]
    response = api.post("/sources", json=body, headers=ADMIN)
    assert response.status_code == 201, response.text
    return response.json()["connection_id"]


def _feed_shop(api, name, district="Sylhet"):
    """A consented shop created in the app with the feed's shop name (the match candidate)."""
    merchant_id = new_shop(api, shop_name=name, district=district, confirm_new=True)
    consent(api, merchant_id)
    return merchant_id


def _rows_for(world, merchant_id):
    with Session(world.engine) as session:
        purchases = session.scalar(
            select(func.count())
            .select_from(db.Purchase)
            .where(db.Purchase.merchant_id == merchant_id)
        )
        deliveries = session.scalar(
            select(func.count())
            .select_from(db.Delivery)
            .where(db.Delivery.merchant_id == merchant_id)
        )
    return purchases, deliveries


def test_the_catalog_is_honest_and_only_available_sources_can_be_connected(api):
    catalog = {c["key"]: c for c in api.get("/sources/catalog", headers=VIEWER).json()}
    assert catalog["field_entry"]["availability"] == "builtin"
    assert catalog["spreadsheet"]["availability"] == "builtin"
    assert (
        catalog["sandbox_feed"]["availability"] == "available"
        and catalog["sandbox_feed"]["sandbox_only"]
    )
    for key in ("wholesale_platform", "shop_credit", "logistics", "retail_pos", "accounting"):
        assert catalog[key]["availability"] == "planned"
    planned = api.post(
        "/sources", json={"connector_key": "logistics", "display_name": "Couriers"}, headers=ADMIN
    )
    assert (
        planned.status_code == 409 and planned.json()["detail"]["code"] == "connector_not_available"
    )
    for headers in (OFFICER, VIEWER):
        refused = api.post(
            "/sources",
            json={
                "connector_key": "sandbox_feed",
                "display_name": "Test feed",
                "settings": {"feed": "standard"},
            },
            headers=headers,
        )
        assert refused.status_code == 403
    bad = api.post(
        "/sources",
        json={
            "connector_key": "sandbox_feed",
            "display_name": "Test feed",
            "settings": {"feed": "standard"},
            "secret_ref": "sk_live_123abc",
        },
        headers=ADMIN,
    )
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "invalid_secret_ref"
    unknown = api.post(
        "/sources",
        json={
            "connector_key": "sandbox_feed",
            "display_name": "Test feed",
            "settings": {"feed": "standard", "url": "x"},
        },
        headers=ADMIN,
    )
    assert unknown.json()["detail"]["code"] == "unknown_setting"
    missing = api.post(
        "/sources",
        json={"connector_key": "sandbox_feed", "display_name": "Test feed", "settings": {}},
        headers=ADMIN,
    )
    assert missing.json()["detail"]["code"] == "missing_setting"


def test_a_source_syncs_only_matched_merchants_with_lineage_and_is_idempotent(api, world):
    shop = _feed_shop(api, "Noor Traders")
    connection = _source(api)
    assert api.post(f"/sources/{connection}/test", headers=ADMIN).json()["status"] == "ok"
    fields = api.post(f"/sources/{connection}/discover", headers=OFFICER).json()
    assert fields["suggested"] == FEED_MAPPING

    preview = api.post(
        f"/sources/{connection}/preview", json={"mapping": FEED_MAPPING}, headers=OFFICER
    ).json()
    assert (
        preview["counts"]["add"] == 0 and preview["counts"]["unmatched"] == 15
    )  # nothing linked yet
    noor = next(u for u in preview["unmatched"] if u["external_ref"] == "SF-102")
    assert shop in [c["merchant_id"] for c in noor["candidates"]]  # a suggestion, not a link

    decided = api.post(
        f"/sources/{connection}/matches",
        json={"external_ref": "SF-102", "merchant_id": shop, "decision": "confirmed"},
        headers=OFFICER,
    )
    assert decided.status_code == 201
    run = api.post(
        f"/sources/{connection}/sync", json={"mapping": FEED_MAPPING}, headers=OFFICER
    ).json()
    assert run["status"] == "ok" and run["rows_added"] == 5 and run["rows_unmatched"] == 10
    assert _rows_for(world, shop) == (3, 2)
    with Session(world.engine) as session:
        lineage = session.scalars(
            select(db.SourceRecord).where(db.SourceRecord.merchant_id == shop)
        ).all()
        assert len(lineage) == 5 and {r.connection_id for r in lineage} == {connection}
        assert all(
            len(r.raw_sha256) == 64 and r.source_reference.startswith("SF-102") for r in lineage
        )
        kinds = {
            r.entry_method
            for r in session.scalars(
                select(db.RecordProvenance).where(
                    db.RecordProvenance.record_id.in_([x.record_id for x in lineage])
                )
            )
        }
        assert kinds == {"synthetic_demo"}
    assert "source_sync" in audit(world, shop)

    again = api.post(
        f"/sources/{connection}/sync", json={"mapping": FEED_MAPPING}, headers=OFFICER
    ).json()
    assert (
        again["rows_added"] == 0 and again["rows_skipped"] == 5 and _rows_for(world, shop) == (3, 2)
    )
    detail = api.get(f"/sources/{connection}", headers=VIEWER).json()
    assert [r["kind"] for r in detail["runs"]][:2] == ["sync", "sync"] and detail[
        "linked_merchants"
    ] == 1


def test_a_rejected_match_and_bad_rows_are_never_saved(api, world):
    shop = _feed_shop(api, "Rahman General Store")
    connection = _source(api, feed="with_problems")
    api.post(
        f"/sources/{connection}/matches",
        json={"external_ref": "SF-102", "decision": "rejected"},
        headers=OFFICER,
    )
    api.post(
        f"/sources/{connection}/matches",
        json={"external_ref": "SF-101", "merchant_id": shop, "decision": "confirmed"},
        headers=OFFICER,
    )
    preview = api.post(
        f"/sources/{connection}/preview", json={"mapping": FEED_MAPPING}, headers=OFFICER
    ).json()
    codes = {r["source_reference"]: r["code"] for r in preview["rows"]}
    assert codes["SF-101-X1"] == "bad_date" and codes["SF-101-X2"] == "bad_amount"
    assert codes["SF-101-X3"] == "date_after_calendar" and codes["SF-101-X4"] == "unsupported_kind"
    assert "reference_twice_in_source" in codes.values()
    assert {u["external_ref"]: u["decision"] for u in preview["unmatched"]}["SF-102"] == "rejected"
    run = api.post(
        f"/sources/{connection}/sync", json={"mapping": FEED_MAPPING}, headers=OFFICER
    ).json()
    assert run["rows_added"] == 5 and run["rows_rejected"] == 5
    assert _rows_for(world, shop) == (3, 2)


def test_consent_and_mapping_are_checked_before_anything_is_saved(api, world):
    no_consent = new_shop(api, shop_name="Karim Pharmacy", district="Dhaka", confirm_new=True)
    connection = _source(api)
    api.post(
        f"/sources/{connection}/matches",
        json={"external_ref": "SF-103", "merchant_id": no_consent, "decision": "confirmed"},
        headers=OFFICER,
    )
    preview = api.post(
        f"/sources/{connection}/preview", json={"mapping": FEED_MAPPING}, headers=OFFICER
    ).json()
    assert {r["code"] for r in preview["rows"] if r["external_ref"] == "SF-103"} == {
        "consent_required"
    }
    bad = api.post(
        f"/sources/{connection}/preview",
        json={"mapping": {**FEED_MAPPING, "source_reference": None}},
        headers=OFFICER,
    )
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "missing_column"
    twice = api.post(
        f"/sources/{connection}/sync",
        json={"mapping": {**FEED_MAPPING, "amount": "txn_id"}},
        headers=OFFICER,
    )
    assert twice.status_code == 422 and twice.json()["detail"]["code"] == "column_used_twice"
    benchmark = world.tables["merchants"]["merchant_id"].iloc[0]
    refused = api.post(
        f"/sources/{connection}/matches",
        json={"external_ref": "SF-101", "merchant_id": benchmark, "decision": "confirmed"},
        headers=OFFICER,
    )
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "benchmark_merchant"


def test_failures_are_recorded_and_recoverable_and_credentials_never_leave(api, world, monkeypatch):
    failing = _source(api, fail_at="sync")
    shop = _feed_shop(api, "Noor Traders")
    api.post(
        f"/sources/{failing}/matches",
        json={"external_ref": "SF-102", "merchant_id": shop, "decision": "confirmed"},
        headers=OFFICER,
    )
    run = api.post(
        f"/sources/{failing}/sync", json={"mapping": FEED_MAPPING}, headers=OFFICER
    ).json()
    assert run["status"] == "failed" and run["error_code"] == "source_unavailable"
    assert _rows_for(world, shop) == (0, 0)
    detail = api.get(f"/sources/{failing}", headers=OFFICER).json()
    assert detail["status"] == "error" and detail["runs"][0]["status"] == "failed"

    secured = _source(api, secret_ref="CREDLENS_TEST_FEED_KEY")
    monkeypatch.delenv("CREDLENS_TEST_FEED_KEY", raising=False)
    missing = api.post(f"/sources/{secured}/test", headers=ADMIN).json()
    assert missing["status"] == "failed" and missing["error_code"] == "secret_missing"
    monkeypatch.setenv("CREDLENS_TEST_FEED_KEY", "s3cret-value-xyz")
    assert api.post(f"/sources/{secured}/test", headers=ADMIN).json()["status"] == "ok"
    shown = api.get(f"/sources/{secured}", headers=ADMIN)
    assert shown.json()["secret_ref_set"] is True and "s3cret-value-xyz" not in shown.text
    assert "CREDLENS_TEST_FEED_KEY" not in api.get("/sources", headers=VIEWER).text

    revoked = api.post(f"/sources/{secured}/revoke", headers=ADMIN).json()
    assert revoked["status"] == "revoked" and revoked["secret_ref_set"] is False
    for path in ("test", "discover"):
        assert (
            api.post(f"/sources/{secured}/{path}", headers=ADMIN).json()["detail"]["code"]
            == "source_revoked"
        )
    assert api.post(f"/sources/{secured}/revoke", headers=OFFICER).status_code == 403


def test_sources_are_isolated_between_organisations(api, world, org_b):
    connection = _source(api)
    assert api.get(f"/sources/{connection}", headers=OFFICER_B).status_code == 404
    assert (
        api.post(
            f"/sources/{connection}/preview", json={"mapping": FEED_MAPPING}, headers=OFFICER_B
        ).status_code
        == 404
    )
    assert connection not in [
        s["connection_id"] for s in api.get("/sources", headers=OFFICER_B).json()
    ]
    b_shop = api.post(
        "/merchants",
        json={"shop_name": "Org B Store", "district": "Dhaka", "shop_type": "grocery"},
        headers=OFFICER_B,
    ).json()["merchant_id"]
    cross = api.post(
        f"/sources/{connection}/matches",
        json={"external_ref": "SF-103", "merchant_id": b_shop, "decision": "confirmed"},
        headers=OFFICER,
    )
    assert cross.status_code == 404


# --- data quality (workstream D) -------------------------------------------------------------


def _issues(api, headers=OFFICER, **params) -> dict[str, dict]:
    response = api.get("/quality/issues", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return {i["issue_key"]: i for i in response.json()["issues"]}


def _review(api, issue, outcome, note="Checked the paper memo with the owner.", headers=OFFICER):
    return api.post(
        "/quality/reviews",
        json={
            "issue_key": issue["issue_key"],
            "fingerprint": issue["fingerprint"],
            "outcome": outcome,
            "note": note,
        },
        headers=headers,
    )


def test_quality_finds_lookalikes_duplicates_and_gaps_and_changes_no_record(api, world, end):
    name = f"Quality Store {next(_shop_counter)}"
    first = new_shop(api, shop_name=name)
    second = new_shop(api, shop_name=name, confirm_new=True)
    consent(api, second)
    day = end - timedelta(days=6)
    purchase(api, second, day, 800.0, invoice_reference="Q-1")
    purchase(api, second, day, 800.0, invoice_reference="Q-2")
    apply(api, second)

    issues = _issues(api, merchant_id=second)
    kinds = {i["kind"]: i for i in issues.values()}
    pair = kinds["possible_same_shop"]
    assert {pair["merchant_id"], pair["other_merchant_id"]} == {first, second}
    duplicate = kinds["possible_duplicate_record"]
    assert duplicate["facts"]["records"] == 2
    assert {e["origin"] for e in duplicate["evidence"]} == {"staff_entered"}
    gap = kinds["missing_evidence"]
    assert gap["facts"]["missing"] == ["deliveries"] and gap["outcomes"] == []

    assert _review(api, pair, "different_shops", headers=VIEWER).status_code == 403
    assert _review(api, gap, "acknowledged").json()["detail"]["code"] == "not_reviewable"
    assert _review(api, pair, "merge").json()["detail"]["code"] == "invalid_outcome"
    short = _review(api, pair, "different_shops", note="ok")
    assert short.json()["detail"]["code"] == "note_too_short"
    stale = {**pair, "fingerprint": "0" * 64}
    assert _review(api, stale, "different_shops").json()["detail"]["code"] == "issue_changed"

    done = _review(api, pair, "different_shops")
    assert done.status_code == 201 and done.json()["status"] == "reviewed"
    assert pair["issue_key"] not in _issues(api, merchant_id=second)
    assert pair["issue_key"] in _issues(api, merchant_id=second, status="reviewed")
    assert "quality_different_shops" in audit(world, first)
    asks = [
        r["code"]
        for r in api.get(f"/merchants/{second}/review", headers=OFFICER).json()["evidence_requests"]
    ]
    assert "confirm_not_same_shop" not in asks and "confirm_possible_duplicate" in asks

    flagged = _review(api, duplicate, "duplicate").json()
    assert flagged["reviews"][0]["concern"] is True and flagged["status"] == "reviewed"
    purchase(api, second, day, 800.0, invoice_reference="Q-3")  # the evidence changes
    reopened = _issues(api, merchant_id=second)[duplicate["issue_key"]]
    assert reopened["status"] == "changed" and reopened["facts"]["records"] == 3
    assert reopened["reviews"][0]["current"] is False
    asks = [
        r["code"]
        for r in api.get(f"/merchants/{second}/review", headers=OFFICER).json()["evidence_requests"]
    ]
    assert "confirm_possible_duplicate" in asks  # changed records: asked again
    assert _purchases(world, second) == 3  # a review never removes or merges a record
    with Session(world.engine) as session:
        assert session.get(db.Merchant, first) and session.get(db.Merchant, second)


def test_quality_reports_stale_evidence_and_lapsed_consent(api, world, end):
    old = new_shop(api)
    consent(api, old)
    purchase(api, old, end - timedelta(days=150), 5000.0)
    apply(api, old)
    kinds = {i["kind"]: i for i in _issues(api, merchant_id=old).values()}
    assert kinds["stale_evidence"]["facts"]["days"] == 150
    assert "missing_evidence" in kinds  # no deliveries yet: a gap, never a judgement
    assert "consent_lapsed" not in kinds

    with Session(world.engine) as session:
        for row in session.scalars(select(db.Consent).where(db.Consent.merchant_id == old)):
            row.revoked_at = end - timedelta(days=1)
        session.commit()
    lapsed = {i["kind"]: i for i in _issues(api, merchant_id=old).values()}["consent_lapsed"]
    assert lapsed["facts"]["state"] == "expired_or_revoked" and lapsed["outcomes"] == []


def test_a_synced_record_counts_as_coming_from_a_data_source(api, world):
    shop = _feed_shop(api, "Noor Traders")
    connection = _source(api)
    api.post(
        f"/sources/{connection}/matches",
        json={"external_ref": "SF-102", "merchant_id": shop, "decision": "confirmed"},
        headers=OFFICER,
    )
    api.post(f"/sources/{connection}/sync", json={"mapping": FEED_MAPPING}, headers=OFFICER)
    review = api.get(f"/merchants/{shop}/review", headers=OFFICER).json()
    groups = {g["group"]: g["by_source"] for g in review["evidence"]}
    assert groups["purchases"] == {"data_source": 3} and groups["deliveries"] == {"data_source": 2}
    overview = api.get("/overview", headers=OFFICER).json()["evidence"]
    sources = {(r["record_type"], r["source"]) for r in overview["by_source"]}
    assert ("purchase", "data_source") in sources and ("delivery", "data_source") in sources


def test_a_withdrawn_source_link_keeps_its_records_and_asks_for_a_review(api, world):
    shop = _feed_shop(api, "Noor Traders")
    connection = _source(api)
    api.post(
        f"/sources/{connection}/matches",
        json={"external_ref": "SF-102", "merchant_id": shop, "decision": "confirmed"},
        headers=OFFICER,
    )
    api.post(f"/sources/{connection}/sync", json={"mapping": FEED_MAPPING}, headers=OFFICER)
    left = _issues(api)[f"source_rows:{connection}"]
    assert left["kind"] == "source_rows_left_out" and left["facts"]["unmatched"] == 10

    api.post(
        f"/sources/{connection}/matches",
        json={"external_ref": "SF-102", "decision": "rejected"},
        headers=OFFICER,
    )
    links = api.get(f"/sources/{connection}/matches", headers=VIEWER).json()
    history = [(x["decision"], x["current"]) for x in links]
    assert history == [("rejected", True), ("confirmed", False)]
    assert links[1]["records_saved"] == 5 and links[1]["merchant_id"] == shop

    withdrawn = _issues(api, merchant_id=shop)[f"withdrawn_link:{connection}|{shop}"]
    assert withdrawn["facts"]["records"] == 5 and len(withdrawn["evidence"]) == 5
    assert {e["origin"] for e in withdrawn["evidence"]} == {"data_source"}
    assert _rows_for(world, shop) == (3, 2)  # nothing removed
    reviewed = _review(api, withdrawn, "records_wrong").json()
    assert reviewed["reviews"][0]["concern"] is True
    assert _rows_for(world, shop) == (3, 2)

    failing = _source(api, fail_at="test")
    api.post(f"/sources/{failing}/test", headers=ADMIN)
    broken = _issues(api)[f"source_failing:{failing}"]
    assert broken["facts"]["error_code"] == "source_unavailable"
    assert _review(api, broken, "acknowledged").json()["detail"]["code"] == "not_reviewable"


def test_quality_issues_are_isolated_between_organisations(api, world, org_b):
    name = f"Isolated Store {next(_shop_counter)}"
    first = new_shop(api, shop_name=name)
    new_shop(api, shop_name=name, confirm_new=True)
    mine = _issues(api, merchant_id=first)
    assert mine
    theirs = _issues(api, headers=OFFICER_B, status="all")
    assert not set(mine) & set(theirs)
    assert all(i["merchant_id"] != first for i in theirs.values())
    issue = next(iter(mine.values()))
    assert _review(api, issue, "different_shops", headers=OFFICER_B).status_code == 404


def test_the_last_day_is_read_again_cheaply_after_an_app_save(api, world, end):
    """After a save only app-entered rows are re-read; the answer equals a full scan."""
    from src.api.state import _last_day

    services = world.services
    services.data_today(Session(world.engine))
    shop = new_shop(api)
    consent(api, shop)
    purchase(api, shop, end - timedelta(days=4), 3100.0)
    assert services._bulk_today is not None and services._data_today is None  # no full scan due
    with Session(world.engine) as session:
        assert services.data_today(session) == _last_day(session, app_only=False)
        assert _last_day(session, app_only=True) >= end - timedelta(days=4)


# --- real accounts: sign-in, roles from the server, SR scope (product recovery) -------------


def _client():
    from src.api.main import app

    return TestClient(app)


def _real_org(world, org_id: str, admin_login: str):
    """A real organisation and its first administrator, as `python -m src.accounts.cli` does."""
    from src.accounts import service

    with Session(world.engine) as session:
        if session.get(db.Organization, org_id) is None:
            service.create_organization(session, org_id, f"{org_id} Finance", "pilot")
        _, _, code = service.create_account(
            session, world.config, org_id, "First Admin", admin_login, "org_admin", None
        )
        session.commit()
    return code


def _sign_in(login: str, code: str, password: str = "correct horse battery"):
    client = _client()
    set_up = client.post(
        "/auth/password/setup", json={"identifier": login, "code": code, "password": password}
    )
    assert set_up.status_code == 204, set_up.text
    signed = client.post("/auth/login", json={"identifier": login, "password": password})
    assert signed.status_code == 200, signed.text
    return client, signed.json()


def _staff(admin, name, login, role):
    made = admin.post(
        "/org/accounts", json={"display_name": name, "identifier": login, "role": role}
    )
    assert made.status_code == 201, made.text
    body = made.json()
    return body["account"]["user_id"], body["setup_code"]




