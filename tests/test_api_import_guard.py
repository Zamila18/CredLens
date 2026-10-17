"""Tests for what an import may not do (Phase 13 review, findings F1 and F10).

Owner role: D (full-stack).
Implements: docs/API_NOTES.md ("Import").

F1: a consent for a merchant of the original data can never be imported. Before the fix an
    admin could upload a `consents` row for a merchant who had none, and the merchant's whole
    timeline appeared on the profile (0 events became 79) while the queue and the score still
    said "no consent". Since Oct 17 a NEW merchant (added by the same import) may bring its
    consent records: that is a lender bringing its own customers (live import demo).
F10: purchases, deliveries, payments, loans or questionnaire rows for a merchant the scorer
    already knows put events on the timeline that the score ignores, so "the same numbers the
    score was computed from" stopped being true. Only a merchant the scorer has never seen may
    get such rows.

Both are refused with HTTP 409 `import_not_allowed`, load nothing, and leave an audit entry.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert
from sqlalchemy.orm import Session

from src.api.importer import MODELS
from src.api.main import app
from src.api.state import Services
from src.config import load_config
from src.db import models as db
from src.db.load import DEMO_USERS
from tests.conftest import FIXTURES
from tests.test_api import ADMIN, OFFICER, VIEWER, count

HISTORY = ["purchases", "deliveries", "payments", "loans", "questionnaire", "consents"]
MESSAGE = "imports may only add new merchants"
CONSENT_HEADER = "consent_id,merchant_id,purpose,data_categories,granted_at,expires_at,revoked_at\n"


def fixture_csv(table: str) -> bytes:
    return (FIXTURES / "contract" / f"{table}.csv").read_bytes()


def upload(api, table: str, content: bytes | str, params: str = "", headers=ADMIN):
    if isinstance(content, str):
        content = content.encode("utf-8")
    return api.post(
        f"/admin/import/{table}{params}",
        headers={**headers, "Content-Type": "text/csv"},
        content=content,
    )


class Scorer:
    """Stands in for the scorer: it knows the merchants it is given."""

    def __init__(self, known):
        self.known = list(known)

    def merchant_ids(self):
        return self.known

    def source_merchant_ids(self):
        return frozenset(self.known)

    def set_imported(self, tables):
        return []


@pytest.fixture()
def site(tmp_path):
    """An empty database, and a way to say which merchants the scorer knows."""
    url = "sqlite:///" + (tmp_path / "guard.db").as_posix()
    db.create_tables(url)
    engine = db.make_engine(url)
    with engine.begin() as connection:
        connection.execute(insert(db.User.__table__), DEMO_USERS)

    def serve(known=(), scorer=True):
        app.state.services = Services(
            config=load_config(), engine=engine, scorer=Scorer(known) if scorer else None
        )
        return TestClient(app)

    world = type("World", (), {"engine": engine})
    try:
        yield serve, world
    finally:
        if hasattr(app.state, "services"):
            del app.state.services
        engine.dispose()


def refused(response, code="import_not_allowed"):
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == code
    return response.json()["detail"]


# --- F1: a known merchant's consent is never imported ------------------------------------


@pytest.mark.parametrize("params", ["", "?dry_run=true"])
def test_a_consent_for_a_known_merchant_is_refused_not_even_checked(site, params):
    serve, world = site
    api = serve(known=["FIX-M001"])
    detail = refused(upload(api, "consents", fixture_csv("consents"), params))
    assert MESSAGE in detail["message"]
    assert count(world, db.Consent) == 0


def test_a_consent_for_a_new_merchant_is_loaded(site):
    serve, world = site
    api = serve(known=["SOME-OTHER-MERCHANT"])
    assert upload(api, "merchants", fixture_csv("merchants")).status_code == 200
    row = "C-NEW-1,FIX-M001,credit_readiness,purchases,2025-01-01,2030-01-01,\n"
    report = upload(api, "consents", CONSENT_HEADER + row).json()
    assert report["loaded"] is True and count(world, db.Consent) == 1


def test_a_consent_that_ends_before_it_starts_is_rejected(site):
    serve, world = site
    api = serve(known=["SOME-OTHER-MERCHANT"])
    upload(api, "merchants", fixture_csv("merchants"))
    row = "C-BAD,FIX-M001,credit_readiness,purchases,2026-01-01,2025-01-01,\n"
    report = upload(api, "consents", CONSENT_HEADER + row).json()
    assert report["rows_accepted"] == 0 and count(world, db.Consent) == 0


def test_a_refused_consent_import_is_in_the_audit_log_and_loads_nothing(site):
    serve, world = site
    api = serve(known=["FIX-M001"])
    upload(api, "consents", CONSENT_HEADER + "C1,FIX-M001,x,purchases,2025-01-01,2030-01-01,\n")
    assert count(world, db.AuditEntry, db.AuditEntry.action == "refused_import_consents") == 1
    assert count(world, db.AuditEntry, db.AuditEntry.action == "import_consents") == 0
    assert count(world, db.Consent) == 0
    with Session(world.engine) as session:
        entry = session.query(db.AuditEntry).one()
        assert (entry.actor, entry.role) == ("admin-1", "admin")


def test_other_roles_still_get_403_not_the_reason(site):
    serve, _ = site
    api = serve()
    for headers in (OFFICER, VIEWER):
        response = upload(api, "consents", fixture_csv("consents"), headers=headers)
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "role_not_allowed"


# --- F10: a scored merchant's history is not imported ------------------------------------


@pytest.mark.parametrize("table", HISTORY)
def test_rows_for_a_merchant_the_scorer_knows_are_refused_whole(site, table):
    serve, world = site
    api = serve(known=["FIX-M001"])
    assert upload(api, "merchants", fixture_csv("merchants")).status_code == 200
    before = {name: count(world, model) for name, model in MODELS.items()}
    detail = refused(upload(api, table, fixture_csv(table)))
    assert MESSAGE in detail["message"] and "Nothing was loaded" in detail["message"]
    assert detail["merchants"] == ["FIX-M001"]
    # nothing was loaded: not even the rows of merchants the scorer does not know
    after = {name: count(world, model) for name, model in MODELS.items()}
    assert after == before
    assert count(world, db.AuditEntry, db.AuditEntry.action == f"refused_import_{table}") == 1


@pytest.mark.parametrize("table", HISTORY)
def test_a_dry_run_is_refused_the_same_way(site, table):
    serve, _ = site
    api = serve(known=["FIX-M001"])
    upload(api, "merchants", fixture_csv("merchants"))
    refused(upload(api, table, fixture_csv(table), "?dry_run=true"))


def test_every_merchant_named_is_listed_up_to_a_limit(site, monkeypatch):
    from src.api import routes_admin

    serve, _ = site
    monkeypatch.setattr(routes_admin, "MAX_LISTED_MERCHANTS", 2)
    api = serve(known=["FIX-M001", "FIX-M002", "FIX-M003"])
    upload(api, "merchants", fixture_csv("merchants"))
    detail = refused(upload(api, "loans", fixture_csv("loans")))
    assert detail["merchants"] == ["FIX-M001", "FIX-M002"]


@pytest.mark.parametrize("table", HISTORY)
def test_a_new_merchant_may_get_its_records_as_before(site, table):
    """The scorer knows other merchants; the file's merchants are new to it."""
    serve, world = site
    api = serve(known=["SOME-OTHER-MERCHANT"])
    for earlier in ("merchants", "loans"):
        assert upload(api, earlier, fixture_csv(earlier)).status_code == 200
    if table in ("merchants", "loans"):
        return  # loaded just above
    body = upload(api, table, fixture_csv(table))
    assert body.status_code == 200 and body.json()["loaded"] is True, body.text


def test_adding_new_merchants_is_still_allowed_whoever_the_scorer_knows(site):
    serve, world = site
    api = serve(known=["FIX-M001"])  # an existing id is refused as a repeat, not as protected
    report = upload(api, "merchants", fixture_csv("merchants")).json()
    assert report["loaded"] and report["rows_accepted"] == 6
    assert count(world, db.Merchant) == 6


def test_a_file_with_wrong_columns_is_reported_as_before_not_refused(site):
    serve, _ = site
    api = serve(known=["FIX-M001"])
    response = upload(api, "loans", "loan_id,merchant_id\nL1,FIX-M001\n")
    assert response.status_code == 200 and response.json()["file_error"]


def test_a_row_for_a_scored_merchant_is_refused_even_if_it_also_has_a_bad_value(site):
    serve, world = site
    api = serve(known=["FIX-M001"])
    header = "purchase_id,merchant_id,purchase_date,amount_bdt,category,supplier_id\n"
    refused(upload(api, "purchases", header + "P1,FIX-M001,not-a-date,10,,\n"))
    assert count(world, db.Purchase) == 0


def test_without_a_scorer_history_cannot_be_checked_so_it_is_not_imported(site):
    serve, world = site
    api = serve(scorer=False)
    response = upload(api, "purchases", fixture_csv("purchases"))
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "scorer_not_ready"
    assert count(world, db.Purchase) == 0
    # adding merchants needs no scorer: a repeat id is the only thing it checks
    assert upload(api, "merchants", fixture_csv("merchants")).status_code == 200


# --- the real thing: real merchants, real profile -----------------------------------------


def timeline_length(api, merchant_id: str) -> int:
    return len(api.get(f"/merchants/{merchant_id}", headers=ADMIN).json()["timeline"])


def test_an_upload_cannot_unlock_the_data_of_a_merchant_without_consent(api, api_world):
    """The exact attack of the review: no consent, then an uploaded consent row."""
    queue = api_world.services.scorer.queue()
    merchant_id = queue[~queue["consent_valid"]]["merchant_id"].iloc[3]
    before = api.get(f"/merchants/{merchant_id}", headers=ADMIN).json()
    assert before["consent_valid"] is False and before["timeline"] == []
    consents = count(api_world, db.Consent)
    row = f"IMPORTED-1,{merchant_id},credit,purchases|deliveries,2026-01-01,2030-01-01,\n"
    refused(upload(api, "consents", CONSENT_HEADER + row))
    after = api.get(f"/merchants/{merchant_id}", headers=ADMIN).json()
    assert after["consent_valid"] is False and after["timeline"] == []
    assert api.get(f"/merchants/{merchant_id}/score", headers=ADMIN).status_code == 403
    assert count(api_world, db.Consent) == consents


def test_an_upload_cannot_add_events_to_the_timeline_of_a_scored_merchant(api, api_world):
    queue = api_world.services.scorer.queue()
    merchant_id = queue[queue["consent_valid"]]["merchant_id"].iloc[3]
    events = timeline_length(api, merchant_id)
    purchases = count(api_world, db.Purchase)
    header = "purchase_id,merchant_id,purchase_date,amount_bdt,category,supplier_id\n"
    rows = "".join(f"IMPORTED-{n},{merchant_id},2026-08-0{n},1,rice_grain,S1\n" for n in (1, 2, 3))
    refused(upload(api, "purchases", header + rows))
    assert timeline_length(api, merchant_id) == events
    assert count(api_world, db.Purchase) == purchases


def test_new_merchants_can_still_be_added_on_the_real_stack(api, api_world):
    header = (
        "merchant_id,onboarded_at,district,town_tier,shop_type,has_trade_license,"
        "consent_data_use,questionnaire_done\n"
    )
    row = "NEW-IMPORTED-1,2026-08-01,Dhaka,metro,grocery,True,False,False\n"
    before = count(api_world, db.Merchant)
    report = upload(api, "merchants", header + row).json()
    assert report["loaded"] and count(api_world, db.Merchant) == before + 1
    profile = api.get("/merchants/NEW-IMPORTED-1", headers=ADMIN).json()
    assert profile["consent_valid"] is False and profile["timeline"] == []  # no consent, no data
