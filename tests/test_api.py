"""Tests for the API: every endpoint, the roles, consent, audit and the questionnaire.

Owner role: D (full-stack).
Implements: PROJECT_BRIEF section 8 and docs/HANDOVER.md Part E.

Most tests run against `api_world` (tests/conftest.py): 2,000 synthetic merchants in a real
temporary SQLite database, a model trained on them, and the real scorer. Nothing here
needs the network, a trained model on disk, or `python tasks.py data`.

Because that database is shared by the whole run, a test that writes (a decision, an
audit row) compares counts before and after and uses a merchant of its own.
"""

from __future__ import annotations

import copy
import json
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api import model_card_view
from src.api.main import app
from src.api.schemas import (
    AuditEntry,
    Decision,
    HealthResponse,
    MerchantProfile,
    MerchantQueueItem,
    ModelCard,
    QuestionnaireSummary,
    ScoreResponse,
)
from src.api.state import Services
from src.config import MODE_ENV_VAR
from src.db import models as db
from tests.conftest import load_api_fixture

client = TestClient(app)

OFFICER = {"X-Demo-Token": "officer-1"}
OFFICER_2 = {"X-Demo-Token": "officer-2"}
ADMIN = {"X-Demo-Token": "admin-1"}
VIEWER = {"X-Demo-Token": "viewer-1"}
ANSWERS = dict.fromkeys(
    ["spend1", "spend2", "save1", "save2", "borrow1", "borrow2", "plan1", "plan2"], 3
) | {"stress": 2, "confidence": 4}


# --- helpers ----------------------------------------------------------------------------


def count(world, model, *conditions) -> int:
    """Rows of a table (optionally filtered), read straight from the database."""
    with Session(world.engine) as session:
        query = select(func.count()).select_from(model)
        for condition in conditions:
            query = query.where(condition)
        return session.scalar(query)


def loans_snapshot(world) -> list[tuple]:
    """Every loan with its outcome, to prove no endpoint changes a loan."""
    with Session(world.engine) as session:
        rows = session.execute(
            select(db.Loan.loan_id, db.Loan.limit_bdt, db.Loan.outcome_label).order_by(
                db.Loan.loan_id
            )
        )
        return [tuple(row) for row in rows]


@pytest.fixture(scope="module")
def queue(api_world):
    """The scorer's review queue (all pending merchants), as a table."""
    return api_world.services.scorer.queue()


@pytest.fixture(scope="module")
def merchants(api_world, queue) -> dict[str, list[str]]:
    """Lists of merchant ids for each case a test needs. Tests take them from the end,
    one test one merchant, so that tests do not disturb each other."""
    consents = api_world.tables["consents"]
    asked_questionnaire = set(
        consents.loc[consents["data_categories"].str.contains("questionnaire"), "merchant_id"]
    )
    consenting = queue[queue["consent_valid"]]["merchant_id"].tolist()
    return {
        "no_consent": queue[~queue["consent_valid"]]["merchant_id"].tolist(),
        "consenting": consenting,
        "with_questionnaire_consent": [m for m in consenting if m in asked_questionnaire],
        "without_questionnaire_consent": [m for m in consenting if m not in asked_questionnaire],
    }


# --- health and the published spec ------------------------------------------------------


def test_health_reports_the_mode_and_the_banner():
    response = client.get("/health")
    assert response.status_code == 200
    health = HealthResponse.model_validate(response.json())
    assert health.status == "ok"
    assert health.data_mode == "synthetic_bd"
    assert health.banner == "Synthetic demo data. Decision support only."


def test_health_banner_follows_the_data_mode(monkeypatch):
    monkeypatch.setenv(MODE_ENV_VAR, "kiva_asia")
    body = client.get("/health").json()
    assert body["data_mode"] == "kiva_asia"
    assert "not ShopUp data" in body["banner"]
    assert body["banner"].endswith("Decision support only.")


def test_openapi_spec_is_published():
    """The dashboard builds its types from this spec."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert set(paths) == {
        "/health",
        "/merchants",
        "/merchants/{merchant_id}",
        "/merchants/{merchant_id}/score",
        "/merchants/{merchant_id}/consent",
        "/merchants/{merchant_id}/decision",
        "/merchants/{merchant_id}/questionnaire",
        "/decisions",
        "/model/card",
        "/audit",
        "/admin/import/{table}",
    }


def test_the_api_offers_no_way_to_edit_or_delete(api):
    """Decisions and audit entries are append-only: the API has only GET and POST."""
    paths = api.get("/openapi.json").json()["paths"]
    methods = {method for operations in paths.values() for method in operations}
    assert methods == {"get", "post"}
    assert api.delete("/decisions", headers=ADMIN).status_code == 405
    assert api.put("/audit", headers=ADMIN).status_code == 405
    assert api.patch("/decisions", headers=ADMIN).status_code == 405


# --- who is calling ---------------------------------------------------------------------


def role_cases(merchant_id: str) -> list[tuple]:
    """(method, url, request body arguments, roles that may call it)."""
    everyone = {"officer", "admin", "viewer"}
    return [
        ("GET", "/merchants", {}, everyone),
        ("GET", f"/merchants/{merchant_id}", {}, everyone),
        ("GET", f"/merchants/{merchant_id}/score", {}, everyone),
        ("GET", "/decisions", {}, everyone),
        ("GET", "/model/card", {}, everyone),
        ("GET", f"/merchants/{merchant_id}/consent", {}, everyone),
        ("GET", "/audit", {}, {"admin"}),
        (
            "POST",
            f"/merchants/{merchant_id}/decision",
            {"json": {"officer_action": "accept"}},
            {"officer"},
        ),
        ("POST", f"/merchants/{merchant_id}/questionnaire", {"json": ANSWERS}, {"officer"}),
        ("POST", "/admin/import/merchants?dry_run=true", {"content": b""}, {"admin"}),
    ]


def test_every_endpoint_refuses_a_missing_or_unknown_token(api, merchants):
    merchant_id = merchants["with_questionnaire_consent"][0]
    for method, url, arguments, _ in role_cases(merchant_id):
        missing = api.request(method, url, **arguments)
        assert missing.status_code == 401, url
        assert missing.json()["detail"]["code"] == "missing_token", url
        unknown = api.request(method, url, headers={"X-Demo-Token": "nobody"}, **arguments)
        assert unknown.status_code == 401, url
        assert unknown.json()["detail"]["code"] == "unknown_token", url


@pytest.mark.parametrize(
    "role,headers", [("officer", OFFICER), ("admin", ADMIN), ("viewer", VIEWER)]
)
def test_each_role_can_do_exactly_what_the_brief_says(api, merchants, role, headers):
    # one merchant per role, so the writes of one role do not matter to another
    position = {"officer": -1, "admin": -2, "viewer": -3}[role]
    merchant_id = merchants["with_questionnaire_consent"][position]
    for method, url, arguments, allowed in role_cases(merchant_id):
        response = api.request(method, url, headers=headers, **arguments)
        if role in allowed:
            assert response.status_code in (200, 201), (role, url, response.text)
        else:
            assert response.status_code == 403, (role, url)
            assert response.json()["detail"]["code"] == "role_not_allowed", (role, url)


def test_a_viewer_can_never_post(api, merchants, api_world):
    merchant_id = merchants["with_questionnaire_consent"][-4]
    before = count(api_world, db.Decision), count(api_world, db.Questionnaire)
    for url, body in (
        (f"/merchants/{merchant_id}/decision", {"officer_action": "accept"}),
        (f"/merchants/{merchant_id}/questionnaire", ANSWERS),
    ):
        assert api.post(url, headers=VIEWER, json=body).status_code == 403
    assert api.post("/admin/import/merchants", headers=VIEWER, content=b"").status_code == 403
    assert (count(api_world, db.Decision), count(api_world, db.Questionnaire)) == before


# --- the review queue -------------------------------------------------------------------


def get_queue(api, params: str = "", headers=OFFICER) -> list[MerchantQueueItem]:
    response = api.get(f"/merchants{params}", headers=headers)
    assert response.status_code == 200, response.text
    return TypeAdapter(list[MerchantQueueItem]).validate_python(response.json())


def test_the_queue_is_the_scorers_queue_with_merchant_details(api, api_world, queue):
    items = get_queue(api)
    assert {item.merchant_id for item in items} == set(queue["merchant_id"])
    details = api_world.tables["merchants"].set_index("merchant_id")
    for item in items[:200]:
        row = details.loc[item.merchant_id]
        assert item.district == row["district"]
        assert item.town_tier == row["town_tier"]
        assert item.shop_type == row["shop_type"]
        assert item.onboarded_at == str(row["onboarded_at"])


def test_the_queue_matches_the_cards_and_hides_scores_without_consent(api, api_world, queue):
    items = {item.merchant_id: item for item in get_queue(api)}
    scorer = api_world.services.scorer
    assert any(not item.consent_valid for item in items.values()), "the data must have some"
    for item in items.values():
        if not item.consent_valid:
            assert item.score is None and item.coverage is None and item.band is None
        else:
            assert item.score is not None and item.coverage is not None and item.band
    for merchant_id in queue[queue["consent_valid"]]["merchant_id"].head(25):
        card = scorer.card(merchant_id)
        item = items[merchant_id]
        assert (item.score, item.band) == (card["score"], card["band"])
        assert item.coverage == pytest.approx(card["coverage"])


def test_the_queue_lists_pending_merchants_first_and_oldest_first(api):
    items = get_queue(api)
    statuses = [item.status for item in items]
    assert statuses == sorted(statuses, key=lambda status: status != "pending")
    pending_dates = [item.pending_since for item in items if item.status == "pending"]
    assert all(pending_dates) and pending_dates == sorted(pending_dates)


def test_the_queue_filters(api):
    everything = get_queue(api)
    bands = {item.band for item in everything if item.band}
    assert bands == {"Strong", "Review", "Needs more info"}
    for band in bands:
        chosen = get_queue(api, f"?band={band.replace(' ', '%20')}")
        assert chosen and all(item.band == band for item in chosen)
        assert len(chosen) == sum(item.band == band for item in everything)
    tiers = {item.town_tier for item in everything if item.town_tier}
    assert len(tiers) > 1
    for tier in tiers:
        chosen = get_queue(api, f"?town_tier={tier}")
        assert chosen and all(item.town_tier == tier for item in chosen)
    pending, decided = get_queue(api, "?status=pending"), get_queue(api, "?status=decided")
    assert all(item.status == "pending" for item in pending)
    assert all(item.status == "decided" for item in decided)
    assert len(pending) + len(decided) == len(everything)
    both = get_queue(api, "?status=pending&band=Review&town_tier=metro")
    assert all(i.band == "Review" and i.town_tier == "metro" for i in both)
    assert api.get("/merchants?status=approved", headers=OFFICER).status_code == 422
    assert api.get("/merchants?band=Excellent", headers=OFFICER).status_code == 422


def test_the_queue_of_a_mode_with_no_pending_loans_is_empty(api, api_world):
    """A public data mode has no pending loans: the queue is an empty list, not an error."""
    scorer = copy.copy(api_world.services.scorer)
    scorer.queue = lambda: api_world.services.scorer.queue().iloc[0:0]
    services = Services(config=api_world.config, engine=api_world.engine, scorer=scorer)
    app.state.services = services
    assert get_queue(api) == []


def test_a_queue_row_missing_from_the_database_is_an_error_not_a_gap(api, api_world):
    """If the scorer and the database hold different data, say so instead of hiding rows."""
    scorer = copy.copy(api_world.services.scorer)
    scorer.queue = lambda: api_world.services.scorer.queue().assign(merchant_id="M-NOT-LOADED")
    app.state.services = Services(config=api_world.config, engine=api_world.engine, scorer=scorer)
    response = api.get("/merchants", headers=OFFICER)
    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "data_mismatch"


# --- the score --------------------------------------------------------------------------


def test_the_score_card_follows_the_contract_and_matches_the_scorer(api, api_world, merchants):
    scorer = api_world.services.scorer
    for merchant_id in merchants["consenting"][:30]:
        response = api.get(f"/merchants/{merchant_id}/score", headers=VIEWER)
        assert response.status_code == 200, response.text
        body = response.json()
        score = ScoreResponse.model_validate(body)
        card = scorer.card(merchant_id)
        assert (score.score, score.band, score.model_version) == (
            card["score"],
            card["band"],
            "test-version",
        )
        assert score.probability == pytest.approx(card["probability"])
        assert score.score == round(100 * score.probability)
        # the banner comes from /health; it is not part of this response
        assert "banner" not in body
        # baseline + the reasons shown + all the others = the score
        shown = sum(r.contribution for r in score.reasons_positive + score.reasons_negative)
        total = score.baseline_score + shown + score.other_contribution
        assert total == pytest.approx(score.score, abs=0.05)
        assert len(score.reasons_positive) <= 3 and len(score.reasons_negative) <= 3
        assert all(r.contribution > 0 for r in score.reasons_positive)
        assert all(r.contribution < 0 for r in score.reasons_negative)
        assert all(r.sentence_en and r.sentence_bn for r in score.reasons_positive)


def test_low_coverage_always_means_needs_more_info_whatever_the_score(api, api_world, merchants):
    line = api_world.config["score"]["band_min_coverage"]
    seen_high_score_with_low_coverage = False
    for merchant_id in merchants["consenting"][:300]:
        score = api.get(f"/merchants/{merchant_id}/score", headers=OFFICER).json()
        if score["coverage"] < line:
            assert score["band"] == "Needs more info"
            seen_high_score_with_low_coverage |= score["score"] >= 90
        else:
            assert score["band"] in ("Strong", "Review")
        assert score["low_score_warning"] == (score["score"] < 70)
    assert seen_high_score_with_low_coverage, "the sample should include the case that matters"


def test_scoring_is_refused_without_valid_consent(api, api_world, merchants):
    """No valid, unexpired, unrevoked consent means no score, anywhere."""
    refused = merchants["no_consent"]
    assert len(refused) >= 5
    decisions_before = count(api_world, db.Decision)
    audit_before = count(api_world, db.AuditEntry, db.AuditEntry.action == "view_score")
    for merchant_id in refused[:25]:
        response = api.get(f"/merchants/{merchant_id}/score", headers=OFFICER)
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert detail["code"] == "consent_required"
        assert "consent" in detail["message"].lower()
        assert "score" not in response.json() and "probability" not in response.text
        decision = api.post(
            f"/merchants/{merchant_id}/decision", headers=OFFICER, json={"officer_action": "accept"}
        )
        assert decision.status_code == 403
        assert decision.json()["detail"]["code"] == "consent_required"
    assert count(api_world, db.Decision) == decisions_before
    # nothing was shown, so nothing is logged as shown
    assert count(api_world, db.AuditEntry, db.AuditEntry.action == "view_score") == audit_before


def test_an_unknown_merchant_is_a_404_everywhere(api):
    for method, url, arguments in (
        ("GET", "/merchants/NOBODY", {}),
        ("GET", "/merchants/NOBODY/score", {}),
        ("POST", "/merchants/NOBODY/decision", {"json": {"officer_action": "accept"}}),
        ("POST", "/merchants/NOBODY/questionnaire", {"json": ANSWERS}),
    ):
        response = api.request(method, url, headers=OFFICER, **arguments)
        assert response.status_code == 404, url
        assert response.json()["detail"]["code"] == "unknown_merchant", url


# --- the profile ------------------------------------------------------------------------


def get_profile(api, merchant_id: str, headers=OFFICER) -> MerchantProfile:
    response = api.get(f"/merchants/{merchant_id}", headers=headers)
    assert response.status_code == 200, response.text
    return MerchantProfile.model_validate(response.json())


def test_a_profile_follows_the_contract_and_agrees_with_the_data(api, api_world, merchants):
    tables, scorer = api_world.tables, api_world.services.scorer
    checked = 0
    for merchant_id in merchants["consenting"][:60]:
        profile = get_profile(api, merchant_id)
        assert profile.consent_valid and profile.data_mode == "synthetic_bd"
        row = scorer.feature_row(merchant_id)
        if profile.purchases:
            assert profile.purchases.n_purchases_90d == int(row["purchases_90d"])
            assert profile.purchases.n_categories == int(row["category_diversity"])
        for stream, table, column in (
            ("purchase", "purchases", "merchant_id"),
            ("delivery", "deliveries", "merchant_id"),
            ("payment", "payments", "merchant_id"),
        ):
            wanted = (tables[table][column] == merchant_id).sum()
            events = [e for e in profile.timeline if e.stream == stream]
            if stream == "payment":  # a payment not yet due is not listed
                assert len(events) <= wanted
            else:
                assert len(events) == wanted, (merchant_id, stream)
        assert len([e for e in profile.timeline if e.stream == "loan"]) == (
            tables["loans"]["merchant_id"] == merchant_id
        ).sum()
        dates = [e.date for e in profile.timeline]
        assert dates == sorted(dates)
        words = " ".join(e.label for e in profile.timeline).lower()
        assert "sales" not in words and "revenue" not in words
        checked += 1
    assert checked == 60


def test_a_stream_the_merchant_has_no_records_for_is_null(api, api_world, merchants):
    tables = api_world.tables
    with_parcels = set(tables["deliveries"]["merchant_id"])
    silent = [m for m in merchants["consenting"] if m not in with_parcels]
    assert silent, "about a quarter of merchants have no delivery data"
    profile = get_profile(api, silent[0])
    assert profile.deliveries is None
    assert not any(event.stream == "delivery" for event in profile.timeline)
    assert profile.purchases is not None or profile.payments is not None or profile.timeline


def test_a_profile_without_consent_shows_no_behaviour(api, merchants):
    profile = get_profile(api, merchants["no_consent"][0])
    assert profile.consent_valid is False
    assert profile.purchases is None and profile.deliveries is None
    assert profile.payments is None and profile.questionnaire is None
    assert profile.timeline == []
    assert profile.district  # who the shop is can still be shown


def test_every_profile_read_writes_an_audit_entry(api, api_world, merchants):
    for headers, user, role, merchant_id in (
        (OFFICER_2, "officer-2", "officer", merchants["consenting"][0]),
        (ADMIN, "admin-1", "admin", merchants["consenting"][1]),
        (VIEWER, "viewer-1", "viewer", merchants["no_consent"][1]),  # a refused one too
    ):
        condition = (
            db.AuditEntry.action == "view_profile",
            db.AuditEntry.merchant_id == merchant_id,
        )
        before = count(api_world, db.AuditEntry, *condition)
        total_before = count(api_world, db.AuditEntry)
        started = datetime.utcnow() - timedelta(seconds=1)
        get_profile(api, merchant_id, headers)
        assert count(api_world, db.AuditEntry, *condition) == before + 1
        assert count(api_world, db.AuditEntry) == total_before + 1
        with Session(api_world.engine) as session:
            entry = session.scalars(select(db.AuditEntry).order_by(db.AuditEntry.id.desc())).first()
        assert (entry.actor, entry.role, entry.merchant_id) == (user, role, merchant_id)
        assert started <= entry.timestamp <= datetime.utcnow() + timedelta(seconds=1)


def test_reading_a_score_is_audited_too(api, api_world, merchants):
    merchant_id = merchants["consenting"][2]
    condition = (db.AuditEntry.action == "view_score", db.AuditEntry.merchant_id == merchant_id)
    before = count(api_world, db.AuditEntry, *condition)
    assert api.get(f"/merchants/{merchant_id}/score", headers=OFFICER).status_code == 200
    assert count(api_world, db.AuditEntry, *condition) == before + 1


def test_a_failed_read_writes_no_audit_entry(api, api_world):
    before = count(api_world, db.AuditEntry)
    assert api.get("/merchants/NOBODY", headers=OFFICER).status_code == 404
    assert api.get("/merchants/NOBODY", headers={"X-Demo-Token": "nobody"}).status_code == 401
    assert api.get("/merchants/NOBODY", headers=VIEWER).status_code == 404
    assert count(api_world, db.AuditEntry) == before


def test_if_the_audit_entry_cannot_be_written_nothing_is_returned(
    api, merchants, monkeypatch
):
    """Audit first, then disclose: a profile or a score is never returned unrecorded."""
    from src.api import routes_merchants

    def broken(*args, **kwargs):
        raise RuntimeError("audit store is down")

    monkeypatch.setattr(routes_merchants, "add_audit", broken)
    quiet = TestClient(app, raise_server_exceptions=False)
    merchant_id = merchants["consenting"][3]
    for url in (f"/merchants/{merchant_id}", f"/merchants/{merchant_id}/score"):
        response = quiet.get(url, headers=OFFICER)
        assert response.status_code == 500
        assert "probability" not in response.text and "timeline" not in response.text


# --- decisions --------------------------------------------------------------------------


def post_decision(api, merchant_id: str, body: dict, headers=OFFICER):
    return api.post(f"/merchants/{merchant_id}/decision", headers=headers, json=body)


def test_an_officer_decision_is_stored_with_the_score_shown_and_the_model_version(
    api, api_world, merchants
):
    merchant_id = merchants["consenting"][4]
    card = api_world.services.scorer.card(merchant_id)
    before = count(api_world, db.Decision)
    audit_before = count(api_world, db.AuditEntry, db.AuditEntry.action == "record_decision")
    response = post_decision(
        api,
        merchant_id,
        {"officer_action": "override_up", "reason_text": "  Visited the shop.  ", "score_shown": 3},
        headers=OFFICER_2,
    )
    assert response.status_code == 201, response.text
    decision = Decision.model_validate(response.json())
    # the score and the version come from the server, not from the request
    assert decision.score_shown == card["score"] and decision.score_shown != 3
    assert decision.model_version == "test-version"
    assert decision.officer_id == "officer-2"
    assert decision.officer_action == "override_up"
    assert decision.reason_text == "Visited the shop."
    assert decision.merchant_id == merchant_id
    assert count(api_world, db.Decision) == before + 1
    assert count(api_world, db.AuditEntry, db.AuditEntry.action == "record_decision") == (
        audit_before + 1
    )
    listed = api.get(f"/decisions?merchant_id={merchant_id}", headers=VIEWER).json()
    assert [d["decision_id"] for d in listed] == [decision.decision_id]


def test_the_valid_sample_requests_are_accepted_and_the_invalid_ones_rejected(
    api, api_world, merchants
):
    samples = load_api_fixture("decision_requests")
    merchant_id = merchants["consenting"][5]
    before = count(api_world, db.Decision)
    for body in samples["valid"]:
        assert post_decision(api, merchant_id, body).status_code == 201, body
    assert count(api_world, db.Decision) == before + len(samples["valid"])
    for body in samples["invalid"]:
        assert post_decision(api, merchant_id, body).status_code == 422, body
    assert count(api_world, db.Decision) == before + len(samples["valid"])


def test_there_is_no_approve_or_decline_action(api, api_world, merchants):
    merchant_id = merchants["consenting"][6]
    before = count(api_world, db.Decision)
    for action in ("approve", "decline", "reject", "approved", "eligible", ""):
        response = post_decision(api, merchant_id, {"officer_action": action, "reason_text": "x"})
        assert response.status_code == 422, action
    assert post_decision(api, merchant_id, {}).status_code == 422
    assert count(api_world, db.Decision) == before


def test_an_override_needs_a_written_reason(api, api_world, merchants):
    merchant_id = merchants["consenting"][7]
    before = count(api_world, db.Decision)
    for action in ("override_up", "override_down"):
        for reason in (None, "", "   ", "\n\t"):
            body = {"officer_action": action, "reason_text": reason}
            assert post_decision(api, merchant_id, body).status_code == 422, (action, reason)
        assert post_decision(api, merchant_id, {"officer_action": action}).status_code == 422
    assert count(api_world, db.Decision) == before
    # the other two actions may be recorded without a reason
    for action in ("accept", "needs_more_info"):
        assert post_decision(api, merchant_id, {"officer_action": action}).status_code == 201


def test_only_an_officer_decides(api, api_world, merchants):
    merchant_id = merchants["consenting"][8]
    before = count(api_world, db.Decision)
    for headers in (ADMIN, VIEWER):
        response = post_decision(api, merchant_id, {"officer_action": "accept"}, headers)
        assert response.status_code == 403
    assert count(api_world, db.Decision) == before


def test_the_history_is_newest_first_and_can_be_narrowed(api, merchants):
    first, second = merchants["consenting"][9], merchants["consenting"][10]
    post_decision(api, first, {"officer_action": "accept"})
    post_decision(api, second, {"officer_action": "needs_more_info"})
    post_decision(api, first, {"officer_action": "override_down", "reason_text": "Shop closed."})
    everything = TypeAdapter(list[Decision]).validate_python(
        api.get("/decisions", headers=VIEWER).json()
    )
    stamps = [d.decided_at for d in everything]
    assert stamps == sorted(stamps, reverse=True)
    only_first = TypeAdapter(list[Decision]).validate_python(
        api.get(f"/decisions?merchant_id={first}", headers=ADMIN).json()
    )
    assert [d.officer_action for d in only_first] == ["override_down", "accept"]
    assert api.get("/decisions?merchant_id=NOBODY", headers=ADMIN).json() == []


def test_a_decision_moves_the_merchant_to_decided_in_the_queue(api, merchants):
    merchant_id = merchants["consenting"][11]
    before = next(i for i in get_queue(api) if i.merchant_id == merchant_id)
    assert before.status == "pending" and before.pending_since
    post_decision(api, merchant_id, {"officer_action": "accept"})
    after = next(i for i in get_queue(api) if i.merchant_id == merchant_id)
    assert after.status == "decided" and after.pending_since is None
    # the score on the card is what it was
    assert (after.score, after.band) == (before.score, before.band)


# --- the band lines are sent with the score and the model card ---------------------------


def test_the_score_and_the_model_card_carry_the_band_lines_from_the_config(
    api, api_world, merchants
):
    lines = api_world.config["score"]
    expected = {
        "strong_min_score": lines["band_strong_min_score"],
        "min_coverage": lines["band_min_coverage"],
        "low_score_warning_below": lines["low_score_warning_below"],
    }
    score = api.get(f"/merchants/{merchants['consenting'][0]}/score", headers=VIEWER).json()
    assert score["band_rules"] == expected
    for role in (OFFICER, ADMIN, VIEWER):
        assert api.get("/model/card", headers=role).json()["band_rules"] == expected


def test_a_mode_with_its_own_band_lines_sends_those(api, api_world, merchants):
    """`score.by_mode` wins over the defaults, for the score card and for another mode's card."""
    changed = copy.deepcopy(api_world.config)
    changed["score"]["by_mode"] = {
        "synthetic_bd": {"band_strong_min_score": 85},
        "taiwan_cc": {"band_strong_min_score": 77, "band_min_coverage": 0.3},
    }
    scorer = copy.copy(api_world.services.scorer)
    scorer.config = changed
    app.state.services = Services(config=changed, engine=api_world.engine, scorer=scorer)
    for merchant_id in merchants["consenting"][:40]:
        score = api.get(f"/merchants/{merchant_id}/score", headers=OFFICER).json()
        assert score["band_rules"]["strong_min_score"] == 85
        if score["coverage"] >= score["band_rules"]["min_coverage"]:
            assert score["band"] == ("Strong" if score["score"] >= 85 else "Review")
    taiwan = api.get("/model/card?mode=taiwan_cc", headers=OFFICER).json()
    assert taiwan["band_rules"]["strong_min_score"] == 77
    assert taiwan["band_rules"]["min_coverage"] == 0.3
    # a mode with no lines of its own gets the defaults
    kiva = api.get("/model/card?mode=kiva_asia", headers=OFFICER).json()
    assert kiva["band_rules"]["strong_min_score"] == changed["score"]["band_strong_min_score"]


# --- model card and audit log -----------------------------------------------------------


def test_the_model_card_is_for_every_role(api):
    for headers in (OFFICER, ADMIN, VIEWER):
        response = api.get("/model/card", headers=headers)
        assert response.status_code == 200
        card = ModelCard.model_validate(response.json())
        assert card.data_mode == "synthetic_bd"
        assert card.limitations
        if card.model_version != "test-version":
            # The written card belongs to the trained model, not to this test's model.
            assert card.limitations[0].startswith("This card was written for model version")


def test_the_model_card_placeholder_invents_no_numbers(tmp_path, monkeypatch):
    monkeypatch.setattr(model_card_view, "PROJECT_ROOT", tmp_path)
    card = model_card_view.load_model_card("synthetic_bd", "v1")
    assert card.model_version == "v1"
    assert list(card.metrics) == ["note"] and isinstance(card.metrics["note"], str)
    assert card.ablation == [] and card.group_results == []
    fixture = load_api_fixture("model_card")
    assert card.limitations == fixture["limitations"]


def test_a_written_model_card_is_served_as_written(tmp_path, monkeypatch):
    monkeypatch.setattr(model_card_view, "PROJECT_ROOT", tmp_path)
    folder = tmp_path / "reports" / "synthetic_bd"
    folder.mkdir(parents=True)
    written = load_api_fixture("model_card") | {"model_version": "written-by-phase-11"}
    (folder / "model_card.json").write_text(json.dumps(written), encoding="utf-8")
    card = model_card_view.load_model_card("synthetic_bd", "ignored")
    assert card.model_version == "written-by-phase-11"


def test_the_audit_log_is_admin_only_and_is_itself_audited(api, api_world, merchants):
    for headers in (OFFICER, VIEWER):
        assert api.get("/audit", headers=headers).status_code == 403
    get_profile(api, merchants["consenting"][12])
    before = count(api_world, db.AuditEntry, db.AuditEntry.action == "view_audit_log")
    response = api.get("/audit", headers=ADMIN)
    assert response.status_code == 200
    entries = TypeAdapter(list[AuditEntry]).validate_python(response.json())
    assert entries and entries[0].action == "view_audit_log" and entries[0].actor == "admin-1"
    assert [e.id for e in entries] == sorted((e.id for e in entries), reverse=True)
    assert count(api_world, db.AuditEntry, db.AuditEntry.action == "view_audit_log") == before + 1
    assert any(e.action == "view_profile" for e in entries)


def test_the_audit_log_can_be_limited_and_narrowed(api, merchants):
    merchant_id = merchants["consenting"][13]
    get_profile(api, merchant_id)
    assert len(api.get("/audit?limit=2", headers=ADMIN).json()) == 2
    for bad in ("0", "1001", "-1", "many"):
        assert api.get(f"/audit?limit={bad}", headers=ADMIN).status_code == 422
    narrowed = api.get(f"/audit?merchant_id={merchant_id}", headers=ADMIN).json()
    assert narrowed and all(entry["merchant_id"] == merchant_id for entry in narrowed)


# --- the questionnaire ------------------------------------------------------------------


def test_saving_the_questionnaire_updates_the_panel_but_not_the_score(api, api_world, merchants):
    merchant_id = merchants["with_questionnaire_consent"][0]
    score_before = api.get(f"/merchants/{merchant_id}/score", headers=OFFICER).json()
    audit_before = count(
        api_world, db.AuditEntry, db.AuditEntry.action == "record_questionnaire"
    )
    answers = ANSWERS | {"spend1": 5, "spend2": 4, "stress": 1}
    response = api.post(f"/merchants/{merchant_id}/questionnaire", headers=OFFICER, json=answers)
    assert response.status_code == 200, response.text
    summary = QuestionnaireSummary.model_validate(response.json())
    assert summary.spend == 4.5 and summary.save == 3.0 and summary.stress == 1
    assert summary.answered_at == date.today().isoformat()
    assert summary.directional is True
    # the panel next to the score shows it
    assert get_profile(api, merchant_id).questionnaire == summary
    # one row per merchant: saving again replaces the answers
    again = api.post(
        f"/merchants/{merchant_id}/questionnaire", headers=OFFICER, json=ANSWERS | {"spend1": 1}
    )
    assert again.json()["spend"] == 2.0
    assert count(api_world, db.Questionnaire, db.Questionnaire.merchant_id == merchant_id) == 1
    with Session(api_world.engine) as session:
        assert session.get(db.Merchant, merchant_id).questionnaire_done is True
    assert count(
        api_world, db.AuditEntry, db.AuditEntry.action == "record_questionnaire"
    ) == audit_before + 2
    # the score does not move
    score_after = api.get(f"/merchants/{merchant_id}/score", headers=OFFICER).json()
    assert score_after == score_before


@pytest.mark.parametrize(
    "change",
    [
        {"spend1": 0},
        {"spend1": 6},
        {"stress": -1},
        {"confidence": "4"},
        {"plan2": 3.5},
        {"plan2": True},
        {"save1": None},
        {"extra": 1},
    ],
)
def test_the_questionnaire_takes_ten_whole_numbers_from_one_to_five(
    api, api_world, merchants, change
):
    merchant_id = merchants["with_questionnaire_consent"][1]
    with Session(api_world.engine) as session:
        before = session.get(db.Questionnaire, merchant_id)
        snapshot = None if before is None else (before.spend1, before.answered_at)
    response = api.post(
        f"/merchants/{merchant_id}/questionnaire", headers=OFFICER, json=ANSWERS | change
    )
    assert response.status_code == 422
    with Session(api_world.engine) as session:
        after = session.get(db.Questionnaire, merchant_id)
        assert (None if after is None else (after.spend1, after.answered_at)) == snapshot


def test_the_questionnaire_needs_a_missing_answer_to_be_refused(api, merchants):
    merchant_id = merchants["with_questionnaire_consent"][2]
    short = {key: value for key, value in ANSWERS.items() if key != "borrow2"}
    response = api.post(f"/merchants/{merchant_id}/questionnaire", headers=OFFICER, json=short)
    assert response.status_code == 422


def test_the_questionnaire_needs_a_consent_that_covers_it(api, api_world, merchants):
    # Every generated consent covers the questionnaire, so make a merchant whose does not.
    with Session(api_world.engine) as session:
        as_of = api_world.services.data_today(session)
        session.add(db.Merchant(merchant_id="TEST-NOQ", onboarded_at=as_of - timedelta(days=200),
                                consent_data_use=True, questionnaire_done=False))
        session.flush()
        session.add(db.Consent(consent_id="TEST-C-NOQ", merchant_id="TEST-NOQ",
                               purpose="credit_readiness_assessment",
                               data_categories="purchases|deliveries|payments",
                               granted_at=as_of - timedelta(days=100),
                               expires_at=as_of + timedelta(days=300), revoked_at=None))
        session.commit()
    covered_elsewhere = ["TEST-NOQ"]
    before = count(api_world, db.Questionnaire)
    response = api.post(
        f"/merchants/{covered_elsewhere[0]}/questionnaire", headers=OFFICER, json=ANSWERS
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "consent_scope"
    response = api.post(
        f"/merchants/{merchants['no_consent'][0]}/questionnaire", headers=OFFICER, json=ANSWERS
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "consent_required"
    assert count(api_world, db.Questionnaire) == before


# --- no loan is ever changed ------------------------------------------------------------


def test_the_api_never_changes_a_loan(api, api_world, merchants):
    before = loans_snapshot(api_world)
    merchant_id = merchants["with_questionnaire_consent"][3]
    for method, url, arguments, _ in role_cases(merchant_id):
        for headers in (OFFICER, ADMIN, VIEWER):
            api.request(method, url, headers=headers, **arguments)
    assert loans_snapshot(api_world) == before


# --- how the API behaves when a part is missing -----------------------------------------


def test_the_api_without_services_says_it_has_not_started():
    response = TestClient(app).get("/merchants", headers=OFFICER)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "not_started"
    assert TestClient(app).get("/health").status_code == 200


def test_a_missing_scorer_gives_503_and_names_the_fix_but_health_and_audit_still_work(
    api, api_world
):
    app.state.services = Services(
        config=api_world.config,
        engine=api_world.engine,
        scorer=None,
        scorer_error="The scorer is not ready. Run: python tasks.py train",
    )
    for url in ("/merchants", "/merchants/X", "/merchants/X/score"):
        response = api.get(url, headers=OFFICER)
        assert response.status_code == 503, url
        assert response.json()["detail"]["code"] == "scorer_not_ready"
        assert "python tasks.py train" in response.json()["detail"]["message"]
    assert api.post(
        "/merchants/X/decision", headers=OFFICER, json={"officer_action": "accept"}
    ).status_code == 503
    assert api.get("/health").status_code == 200
    assert api.get("/audit", headers=ADMIN).status_code == 200
    card = api.get("/model/card", headers=ADMIN)
    assert card.status_code == 200 and card.json()["data_mode"] == "synthetic_bd"


def test_an_empty_database_gives_503(api, api_world):
    app.state.services = Services(
        config=api_world.config,
        engine=api_world.engine,
        scorer=api_world.services.scorer,
        database_error="The database is empty. Create it with: python tasks.py data",
    )
    response = api.get("/decisions", headers=ADMIN)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "database_not_ready"


def test_a_data_source_whose_rows_may_not_be_shown_has_no_merchant_pages(api, api_world, merchants):
    """Home Credit: totals only. No queue, no profile, no score, no decision."""
    hidden = copy.deepcopy(api_world.config)
    hidden["data"]["rows_never_shown"] = ["synthetic_bd"]
    scorer = copy.copy(api_world.services.scorer)
    scorer.config = hidden
    app.state.services = Services(config=hidden, engine=api_world.engine, scorer=scorer)
    merchant_id = merchants["consenting"][14]
    before = count(api_world, db.Decision), count(api_world, db.Questionnaire)
    for method, url, arguments in (
        ("GET", "/merchants", {}),
        ("GET", f"/merchants/{merchant_id}", {}),
        ("GET", f"/merchants/{merchant_id}/score", {}),
        ("POST", f"/merchants/{merchant_id}/decision", {"json": {"officer_action": "accept"}}),
        ("POST", f"/merchants/{merchant_id}/questionnaire", {"json": ANSWERS}),
    ):
        response = api.request(method, url, headers=OFFICER, **arguments)
        assert response.status_code == 403, url
        assert response.json()["detail"]["code"] == "rows_not_shown", url
    assert (count(api_world, db.Decision), count(api_world, db.Questionnaire)) == before


# --- the browser ------------------------------------------------------------------------


def test_the_dashboard_origin_may_call_the_api_and_others_may_not(api):
    preflight = {
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "x-demo-token,content-type",
    }
    allowed = api.options("/merchants", headers={"Origin": "http://localhost:5173", **preflight})
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    blocked = api.options("/merchants", headers={"Origin": "http://evil.example", **preflight})
    assert "access-control-allow-origin" not in blocked.headers
    plain = api.get("/health", headers={"Origin": "http://localhost:5173"})
    assert plain.headers["access-control-allow-origin"] == "http://localhost:5173"


# --- added in the Phase 9 review (Oct 15) ----------------------------------------------------


def test_every_consenting_merchant_may_be_asked_the_questionnaire(merchants):
    assert merchants["without_questionnaire_consent"] == []
    assert len(merchants["with_questionnaire_consent"]) == len(merchants["consenting"])


def test_the_score_card_carries_the_plain_summary(api, merchants):
    merchant_id = merchants["consenting"][0]
    card = api.get(f"/merchants/{merchant_id}/score", headers=OFFICER).json()
    assert card["summary_en"].startswith(f"Score {card['score']} ({card['band']})")
    assert card["summary_bn"].endswith("সিদ্ধান্ত আপনার।")


def test_the_queue_carries_the_low_score_warning(api, api_world, queue):
    rows = api.get("/merchants", headers=OFFICER).json()
    by_id = {row["merchant_id"]: row for row in rows}
    for item in queue.itertuples(index=False):
        row = by_id[item.merchant_id]
        if item.consent_valid:
            assert row["low_score_warning"] == bool(item.low_score_warning)
        else:
            assert row["low_score_warning"] is None


def test_the_consent_view_is_live_and_audited(api, api_world, merchants):
    from src.api.schemas import ConsentView

    merchant_id = merchants["consenting"][1]
    before = count(api_world, db.AuditEntry, db.AuditEntry.action == "view_consent")
    view = ConsentView.model_validate(
        api.get(f"/merchants/{merchant_id}/consent", headers=VIEWER).json()
    )
    assert view.valid and "questionnaire" in view.data_categories and view.records
    assert count(api_world, db.AuditEntry, db.AuditEntry.action == "view_consent") == before + 1
    refused = api.get(f"/merchants/{merchants['no_consent'][0]}/consent", headers=OFFICER).json()
    assert refused["valid"] is False and refused["data_categories"] == []
    assert api.get("/merchants/NOBODY/consent", headers=OFFICER).status_code == 404



def test_another_modes_model_card_can_be_read(api):
    response = api.get("/model/card?mode=taiwan_cc", headers=VIEWER)
    assert response.status_code == 200
    card = ModelCard.model_validate(response.json())
    assert card.data_mode == "taiwan_cc"
    assert api.get("/model/card?mode=nowhere", headers=VIEWER).status_code == 422
