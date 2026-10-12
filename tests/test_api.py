"""Tests for the API. Phase 0 has GET /health; the rest arrive in Phase 9.

Owner role: D (full-stack).
Implements: PROJECT_BRIEF section 8.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.schemas import HealthResponse
from src.config import MODE_ENV_VAR

client = TestClient(app)


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
    assert client.get("/openapi.json").status_code == 200


@pytest.mark.skip(reason="Phase 9: review queue, profile, score, decisions, model card, audit")
def test_endpoints_follow_the_contract_and_roles():
    """Each endpoint returns its schema; roles are enforced; /audit is admin only."""


@pytest.mark.skip(reason="Phase 9: consent check in the scoring path")
def test_scoring_is_refused_without_valid_consent():
    """No valid, unexpired, unrevoked consent means no score."""


@pytest.mark.skip(reason="Phase 9: audit log")
def test_every_profile_read_writes_an_audit_entry():
    """Reading a merchant profile adds one audit row."""
