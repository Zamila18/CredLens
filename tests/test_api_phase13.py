"""Tests for the Phase 13 review fixes F3, F4 and F5.

Owner role: D (full-stack).
Implements: docs/API_NOTES.md.

F3: reading the queue is audited (`view_queue`), and so is a refused attempt on a merchant without
    consent (`refused_score`, `refused_decision`, `refused_questionnaire`).
F4: a written reason is at most `api.reason_max_chars` (2,000) characters; GET /decisions can be
    paged with `limit` and `offset`, and gives the total in the header `X-Total-Count`.
F5: no decision on a merchant with no loan waiting (409 `no_pending_loan`); pressing the button
    twice records one decision.
"""

from __future__ import annotations

import copy
import time

import pytest
from accounts_seed import headers_for, seed_accounts, seed_person  # noqa: F401
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api import routes_merchants, scoring_access
from src.api.main import app
from src.api.schemas import REASON_MAX_CHARS
from src.api.state import Services
from src.config import load_config
from src.db import models as db
from tests.test_api import ADMIN, ANSWERS, OFFICER, OFFICER_2, VIEWER, count


@pytest.fixture(scope="module")
def merchants(api_world) -> dict[str, list[str]]:
    scorer = api_world.services.scorer
    queue = scorer.queue()
    pending = set(queue["merchant_id"])
    closed = [
        m
        for m in scorer.merchant_ids()
        if m not in pending and bool(scorer.feature_row(m)["consent_valid"])
    ]
    return {
        "no_consent": queue[~queue["consent_valid"]]["merchant_id"].tolist(),
        "consenting": queue[queue["consent_valid"]]["merchant_id"].tolist(),
        "closed": closed,
    }


def audit_rows(world, action: str, merchant_id: str | None = None) -> int:
    conditions = [db.AuditEntry.action == action]
    if merchant_id is not None:
        conditions.append(db.AuditEntry.merchant_id == merchant_id)
    return count(world, db.AuditEntry, *conditions)


def last_audit(world) -> db.AuditEntry:
    with Session(world.engine) as session:
        return session.scalars(select(db.AuditEntry).order_by(db.AuditEntry.id.desc())).first()


# --- F3: the queue ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "headers,actor,role",
    [
        (OFFICER, "officer-1", "credit_officer"),
        (ADMIN, "admin-1", "credit_officer"),
        (VIEWER, "viewer-1", "auditor"),
    ],
)
def test_every_read_of_the_queue_writes_one_audit_entry(api, api_world, headers, actor, role):
    before = audit_rows(api_world, "view_queue")
    total = count(api_world, db.AuditEntry)
    assert api.get("/merchants", headers=headers).status_code == 200
    assert audit_rows(api_world, "view_queue") == before + 1
    assert count(api_world, db.AuditEntry) == total + 1
    entry = last_audit(api_world)
    assert (entry.action, entry.actor, entry.role, entry.merchant_id) == (
        "view_queue",
        actor,
        role,
        None,
    )


def test_a_filtered_queue_is_one_entry_too_and_a_bad_request_is_none(api, api_world):
    before = audit_rows(api_world, "view_queue")
    assert api.get("/merchants?band=Strong&town_tier=metro", headers=OFFICER).status_code == 200
    assert audit_rows(api_world, "view_queue") == before + 1
    assert api.get("/merchants?band=Excellent", headers=OFFICER).status_code == 422
    assert api.get("/merchants", headers={"Cookie": "credlens_session=nobody"}).status_code == 401
    assert audit_rows(api_world, "view_queue") == before + 1


def test_a_queue_that_cannot_be_recorded_is_not_returned(api, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("audit store is down")

    monkeypatch.setattr(routes_merchants, "add_audit", broken)
    quiet = TestClient(app, raise_server_exceptions=False)
    response = quiet.get("/merchants", headers=OFFICER)
    assert response.status_code == 500
    assert "merchant_id" not in response.text and "score" not in response.text


def test_an_empty_queue_is_read_and_audited_too(api, api_world):
    scorer = copy.copy(api_world.services.scorer)
    scorer.queue = lambda: api_world.services.scorer.queue().iloc[0:0]
    app.state.services = Services(config=api_world.config, engine=api_world.engine, scorer=scorer)
    before = audit_rows(api_world, "view_queue")
    assert api.get("/merchants", headers=OFFICER).json() == []
    assert audit_rows(api_world, "view_queue") == before + 1


# --- F3: refused attempts --------------------------------------------------------------------


def test_a_refused_score_is_written_down_with_who_and_which_merchant(api, api_world, merchants):
    merchant_id = merchants["no_consent"][0]
    before = audit_rows(api_world, "refused_score", merchant_id)
    shown = audit_rows(api_world, "view_score", merchant_id)
    response = api.get(f"/merchants/{merchant_id}/score", headers=OFFICER_2)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "consent_required"
    assert audit_rows(api_world, "refused_score", merchant_id) == before + 1
    entry = last_audit(api_world)
    entry_ = (entry.action, entry.actor, entry.role)
    assert entry_ == ("refused_score", "officer-2", "credit_officer")
    assert audit_rows(api_world, "view_score", merchant_id) == shown  # nothing was shown


def test_a_refused_decision_is_written_down_and_nothing_is_recorded(api, api_world, merchants):
    merchant_id = merchants["no_consent"][1]
    decisions = count(api_world, db.Decision)
    refused = audit_rows(api_world, "refused_decision", merchant_id)
    recorded = audit_rows(api_world, "record_decision", merchant_id)
    response = api.post(
        f"/merchants/{merchant_id}/decision", headers=OFFICER, json={"officer_action": "accept"}
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "consent_required"
    assert count(api_world, db.Decision) == decisions
    assert audit_rows(api_world, "refused_decision", merchant_id) == refused + 1
    assert audit_rows(api_world, "record_decision", merchant_id) == recorded


def test_a_refused_questionnaire_without_consent_is_written_down(api, api_world, merchants):
    merchant_id = merchants["no_consent"][2]
    before = audit_rows(api_world, "refused_questionnaire", merchant_id)
    questionnaire = count(api_world, db.Questionnaire)
    response = api.post(f"/merchants/{merchant_id}/questionnaire", headers=OFFICER, json=ANSWERS)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "consent_required"
    assert audit_rows(api_world, "refused_questionnaire", merchant_id) == before + 1
    assert count(api_world, db.Questionnaire) == questionnaire


def test_a_consent_that_does_not_cover_the_questionnaire_is_refused_and_written_down(
    api, api_world, merchants
):
    """Since Oct 15 every consent in the data covers the questionnaire, so one is narrowed here."""
    merchant_id = merchants["consenting"][-200]
    with Session(api_world.engine) as session:
        consent = session.scalars(
            select(db.Consent).where(db.Consent.merchant_id == merchant_id)
        ).first()
        original, consent_id = consent.data_categories, consent.consent_id
        consent.data_categories = "purchases|deliveries|payments"
        session.commit()
    try:
        before = audit_rows(api_world, "refused_questionnaire", merchant_id)
        response = api.post(
            f"/merchants/{merchant_id}/questionnaire", headers=OFFICER, json=ANSWERS
        )
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "consent_scope"
        assert audit_rows(api_world, "refused_questionnaire", merchant_id) == before + 1
    finally:
        with Session(api_world.engine) as session:
            session.get(db.Consent, consent_id).data_categories = original
            session.commit()


def test_only_a_real_refusal_of_a_known_merchant_is_written_down(api, api_world, merchants):
    """An unknown id, a wrong role and a missing token leave no entry: there is no merchant to name,
    or no known actor."""
    total = count(api_world, db.AuditEntry)
    assert api.get("/merchants/NOBODY/score", headers=OFFICER).status_code == 404
    assert (
        api.post(
            f"/merchants/{merchants['no_consent'][3]}/decision",
            headers=VIEWER,
            json={"officer_action": "accept"},
        ).status_code
        == 403
    )
    assert api.get(f"/merchants/{merchants['no_consent'][3]}/score").status_code == 401
    assert count(api_world, db.AuditEntry) == total


def test_a_refusal_stays_a_refusal_even_if_it_cannot_be_written_down(
    api, api_world, merchants, monkeypatch, caplog
):
    def broken(*args, **kwargs):
        raise RuntimeError("audit store is down")

    monkeypatch.setattr(scoring_access, "add_audit", broken)
    quiet = TestClient(app, raise_server_exceptions=False)
    response = quiet.get(f"/merchants/{merchants['no_consent'][4]}/score", headers=OFFICER)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "consent_required"
    assert "could not be written" in caplog.text


# --- F4: the reason ----------------------------------------------------------------------------


def decide(api, merchant_id, body, headers=OFFICER):
    return api.post(f"/merchants/{merchant_id}/decision", headers=headers, json=body)


def test_the_limit_is_the_one_in_the_config_and_in_the_published_spec(api, api_world):
    assert REASON_MAX_CHARS == load_config()["api"]["reason_max_chars"] == 2000
    spec = api.get("/openapi.json").json()
    reason = spec["components"]["schemas"]["DecisionCreate"]["properties"]["reason_text"]
    assert any(option.get("maxLength") == 2000 for option in reason["anyOf"])


def test_a_reason_of_exactly_the_limit_is_kept_and_one_more_character_is_refused(
    api, api_world, merchants
):
    decisions = count(api_world, db.Decision)
    ok = decide(
        api,
        merchants["consenting"][-50],
        {"officer_action": "override_up", "reason_text": "x" * 2000},
    )
    assert ok.status_code == 201 and len(ok.json()["reason_text"]) == 2000
    too_long = decide(
        api,
        merchants["consenting"][-51],
        {"officer_action": "override_up", "reason_text": "x" * 2001},
    )
    assert too_long.status_code == 422
    assert too_long.json()["detail"][0]["loc"][-1] == "reason_text"
    assert "2000" in too_long.json()["detail"][0]["msg"]
    assert count(api_world, db.Decision) == decisions + 1


def test_a_huge_reason_is_refused_before_it_is_stored_or_listed(api, api_world, merchants):
    decisions = count(api_world, db.Decision)
    huge = "x" * (3 * 1024 * 1024)
    for action in ("override_down", "accept", "needs_more_info"):
        response = decide(
            api, merchants["consenting"][-52], {"officer_action": action, "reason_text": huge}
        )
        assert response.status_code == 422
    assert count(api_world, db.Decision) == decisions
    assert len(api.get("/decisions", headers=VIEWER).content) < 1024 * 1024 * 3


def test_a_long_string_of_spaces_is_not_a_reason(api, api_world, merchants):
    response = decide(
        api,
        merchants["consenting"][-53],
        {"officer_action": "override_up", "reason_text": " " * 100},
    )
    assert response.status_code == 422  # an override still needs words


# --- F4: paging the decisions --------------------------------------------------------------------


def test_decisions_without_limit_are_all_of_them_as_before(api, api_world, merchants):
    for n in range(4):  # make sure there are several
        decide(api, merchants["consenting"][-60 - n], {"officer_action": "accept"})
    everything = api.get("/decisions", headers=VIEWER)
    assert len(everything.json()) == count(api_world, db.Decision)
    assert everything.headers["X-Total-Count"] == str(count(api_world, db.Decision))


def test_limit_and_offset_page_through_the_same_list_newest_first(api, api_world, merchants):
    for n in range(5):
        decide(api, merchants["consenting"][-70 - n], {"officer_action": "needs_more_info"})
    full = [d["decision_id"] for d in api.get("/decisions", headers=ADMIN).json()]
    total = len(full)
    assert total >= 5
    first = api.get("/decisions?limit=2", headers=ADMIN)
    assert [d["decision_id"] for d in first.json()] == full[:2]
    assert first.headers["X-Total-Count"] == str(total)  # the total, not the page
    second = api.get("/decisions?limit=2&offset=2", headers=ADMIN)
    assert [d["decision_id"] for d in second.json()] == full[2:4]
    assert [d["decision_id"] for d in api.get("/decisions?offset=3", headers=ADMIN).json()] == full[
        3:
    ]
    assert api.get(f"/decisions?offset={total}", headers=ADMIN).json() == []
    assert (
        api.get(f"/decisions?limit=5&offset={total - 1}", headers=ADMIN).json()
        == [d for d in api.get("/decisions", headers=ADMIN).json()][-1:]
    )


def test_the_total_follows_the_merchant_filter_and_a_bad_page_is_refused(api, api_world, merchants):
    merchant_id = merchants["consenting"][-80]
    decide(api, merchant_id, {"officer_action": "accept"})
    decide(api, merchant_id, {"officer_action": "needs_more_info"})
    page = api.get(f"/decisions?merchant_id={merchant_id}&limit=1", headers=VIEWER)
    assert len(page.json()) == 1 and page.headers["X-Total-Count"] == "2"
    assert api.get("/decisions?merchant_id=NOBODY", headers=VIEWER).headers["X-Total-Count"] == "0"
    for bad in ("limit=0", "limit=-3", "offset=-1", "limit=many"):
        assert api.get(f"/decisions?{bad}", headers=VIEWER).status_code == 422, bad


def test_a_browser_on_another_origin_may_read_the_total(api):
    reply = api.get(
        "/decisions?limit=1",
        headers={**VIEWER, "Origin": "http://localhost:5173"},
    )
    assert reply.headers["access-control-expose-headers"] == "X-Total-Count"


# --- F5: no loan waiting, and the double click ----------------------------------------------


def test_no_decision_on_a_merchant_whose_loan_is_already_settled(api, api_world, merchants):
    assert merchants["closed"], "the data holds merchants whose latest loan has an outcome"
    merchant_id = merchants["closed"][0]
    decisions = count(api_world, db.Decision)
    refused = audit_rows(api_world, "refused_decision", merchant_id)
    recorded = audit_rows(api_world, "record_decision", merchant_id)
    score = api.get(f"/merchants/{merchant_id}/score", headers=OFFICER)
    assert score.status_code == 200  # the score card can still be read
    response = decide(api, merchant_id, {"officer_action": "accept"})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "no_pending_loan"
    assert "no loan waiting" in response.json()["detail"]["message"]
    assert count(api_world, db.Decision) == decisions
    assert audit_rows(api_world, "refused_decision", merchant_id) == refused + 1
    assert audit_rows(api_world, "record_decision", merchant_id) == recorded


def test_a_merchant_in_the_queue_can_still_be_decided_on(api, merchants):
    assert (
        decide(api, merchants["consenting"][-90], {"officer_action": "accept"}).status_code == 201
    )


def test_the_same_decision_twice_in_a_row_is_recorded_once(api, api_world, merchants):
    merchant_id = merchants["consenting"][-91]
    decisions = count(api_world, db.Decision)
    audit = audit_rows(api_world, "record_decision", merchant_id)
    body = {"officer_action": "override_down", "reason_text": "Shop closed on two visits."}
    first, second = decide(api, merchant_id, body), decide(api, merchant_id, body)
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json() == second.json()  # the earlier decision, not a new one
    assert count(api_world, db.Decision) == decisions + 1
    assert audit_rows(api_world, "record_decision", merchant_id) == audit + 1


@pytest.mark.parametrize(
    "index,body,headers",
    [
        (0, {"officer_action": "needs_more_info", "reason_text": "x"}, OFFICER),  # another action
        (1, {"officer_action": "override_up", "reason_text": "A different reason."}, OFFICER),
        (2, {"officer_action": "override_up", "reason_text": "x"}, OFFICER_2),  # another officer
    ],
)
def test_a_different_action_reason_or_officer_is_a_new_decision(
    api, api_world, merchants, index, body, headers
):
    merchant_id = merchants["consenting"][-(100 + index)]
    decide(api, merchant_id, {"officer_action": "override_up", "reason_text": "x"})
    before = count(api_world, db.Decision)
    response = decide(api, merchant_id, body, headers)
    assert response.status_code == 201
    assert count(api_world, db.Decision) == before + 1


def test_after_the_window_the_same_decision_is_a_new_one(api, api_world, merchants):
    config = copy.deepcopy(api_world.config)
    config["api"]["duplicate_decision_seconds"] = 1
    app.state.services = Services(
        config=config, engine=api_world.engine, scorer=api_world.services.scorer
    )
    merchant_id = merchants["consenting"][-150]
    before = count(api_world, db.Decision)
    assert decide(api, merchant_id, {"officer_action": "accept"}).status_code == 201
    assert decide(api, merchant_id, {"officer_action": "accept"}).status_code == 200
    time.sleep(1.3)
    assert decide(api, merchant_id, {"officer_action": "accept"}).status_code == 201
    assert count(api_world, db.Decision) == before + 2


def test_the_decision_rows_of_a_merchant_stay_only_the_officers_own_words(
    api, api_world, merchants
):
    merchant_id = merchants["consenting"][-151]
    decide(api, merchant_id, {"officer_action": "accept"})
    with Session(api_world.engine) as session:
        rows = session.scalars(
            select(db.Decision).where(db.Decision.merchant_id == merchant_id)
        ).all()
        assert {row.officer_action for row in rows} <= {"accept"}
        assert session.scalar(select(func.count()).select_from(db.Loan)) > 0  # loans untouched
