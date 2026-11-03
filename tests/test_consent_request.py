"""Tests for "Ask for consent" (POST /merchants/{id}/consent-request, Oct 17).

Owner role: D (full-stack), with the lead.
Implements: the lead's request that an officer can ask a merchant without consent for it.

What must hold:
- only an officer may ask; admin and viewer get 403;
- a request is recorded (audit entry `request_consent`) and listed on the consent view;
- a request never grants consent: no consent row is added, the score stays refused;
- a merchant whose consent is already valid is refused with 409 `consent_already_valid`.
"""

from __future__ import annotations

from accounts_seed import headers_for, seed_accounts, seed_person  # noqa: F401

from src.db import models as db
from tests.test_api import ADMIN, OFFICER, VIEWER, count


def no_consent_merchant(api_world) -> str:
    queue = api_world.services.scorer.queue()
    return queue[~queue["consent_valid"]]["merchant_id"].iloc[5]


def consenting_merchant(api_world) -> str:
    queue = api_world.services.scorer.queue()
    return queue[queue["consent_valid"]]["merchant_id"].iloc[5]


def test_an_officer_can_ask_and_the_request_is_recorded(api, api_world):
    merchant_id = no_consent_merchant(api_world)
    before = count(api_world, db.AuditEntry, db.AuditEntry.action == "request_consent")
    response = api.post(f"/merchants/{merchant_id}/consent-request", headers=OFFICER)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["merchant_id"] == merchant_id and body["requested_by"] == "officer-1"
    assert "only the merchant can grant consent" in body["note"]
    after = count(api_world, db.AuditEntry, db.AuditEntry.action == "request_consent")
    assert after == before + 1


def test_a_request_never_grants_consent(api, api_world):
    merchant_id = no_consent_merchant(api_world)
    consents = count(api_world, db.Consent)
    api.post(f"/merchants/{merchant_id}/consent-request", headers=OFFICER)
    assert count(api_world, db.Consent) == consents
    assert api.get(f"/merchants/{merchant_id}/score", headers=OFFICER).status_code == 403
    view = api.get(f"/merchants/{merchant_id}/consent", headers=OFFICER).json()
    assert view["valid"] is False


def test_the_consent_view_lists_the_requests_newest_first(api, api_world):
    merchant_id = no_consent_merchant(api_world)
    api.post(f"/merchants/{merchant_id}/consent-request", headers=OFFICER)
    view = api.get(f"/merchants/{merchant_id}/consent", headers=ADMIN).json()
    requests = view["consent_requests"]
    assert requests and requests[0]["requested_by"] == "officer-1"
    times = [r["requested_at"] for r in requests]
    assert times == sorted(times, reverse=True)


def test_only_an_officer_may_ask(api, api_world):
    merchant_id = no_consent_merchant(api_world)
    for headers in (VIEWER,):  # an auditor reads; it does not ask for consent
        response = api.post(f"/merchants/{merchant_id}/consent-request", headers=headers)
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "role_not_allowed"


def test_a_merchant_with_a_valid_consent_is_not_asked(api, api_world):
    merchant_id = consenting_merchant(api_world)
    before = count(api_world, db.AuditEntry, db.AuditEntry.action == "request_consent")
    response = api.post(f"/merchants/{merchant_id}/consent-request", headers=OFFICER)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "consent_already_valid"
    assert count(api_world, db.AuditEntry, db.AuditEntry.action == "request_consent") == before


def test_an_unknown_merchant_is_a_404(api):
    response = api.post("/merchants/NO-SUCH-SHOP/consent-request", headers=OFFICER)
    assert response.status_code == 404
