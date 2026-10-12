"""Tests that the fixture files still match the data contract and the API shapes.

Owner role: D (full-stack) for the API fixtures, B (data engineer) for the contract CSVs.
Implements: Phase 0 (fixtures let the ML and full-stack work start early); PROJECT_BRIEF
    sections 5, 7.6 and 8.
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from src.adapters import CONTRACT, check_frame
from src.api.schemas import (
    AuditEntry,
    Decision,
    DecisionCreate,
    HealthResponse,
    MerchantProfile,
    MerchantQueueItem,
    ModelCard,
    ScoreResponse,
)
from src.config import banner_text
from src.features.dictionary import load_dictionary
from tests.conftest import load_api_fixture

SCORE_FIXTURES = ["score_strong", "score_needs_more_info"]


# --- contract CSVs -----------------------------------------------------------


def test_contract_fixtures_match_the_data_contract(contract_tables):
    for table in CONTRACT:
        check_frame(table, contract_tables[table])
        assert not contract_tables[table].empty, table


def test_fixture_ids_are_marked_as_fixtures(contract_tables):
    for table, frame in contract_tables.items():
        assert frame["merchant_id"].str.startswith("FIX-").all(), table


def test_fixture_merchant_ids_are_unique(contract_tables):
    assert contract_tables["merchants"]["merchant_id"].is_unique


def test_every_fixture_foreign_key_resolves(contract_tables):
    merchants = set(contract_tables["merchants"]["merchant_id"])
    for table in CONTRACT:
        assert set(contract_tables[table]["merchant_id"]) <= merchants, table
    loans = set(contract_tables["loans"]["loan_id"])
    assert set(contract_tables["payments"]["loan_id"]) <= loans


def test_fixtures_cover_the_cases_the_product_must_handle(contract_tables):
    merchants = contract_tables["merchants"].set_index("merchant_id")
    delivery_merchants = set(contract_tables["deliveries"]["merchant_id"])
    loans = contract_tables["loans"]

    assert "FIX-M002" not in delivery_merchants, "a merchant with no delivery data"
    assert merchants.loc["FIX-M005", "consent_data_use"] == "False", "a merchant without consent"
    assert loans["outcome_label"].isna().any(), "a loan too young to have an outcome"
    assert set(loans["outcome_label"].dropna()) == {"0", "1"}, "both labels"


# --- API samples ---------------------------------------------------------------


def test_health_fixture_matches_the_schema_and_the_banner():
    health = HealthResponse.model_validate(load_api_fixture("health"))
    assert health.banner == banner_text(health.data_mode)


@pytest.mark.parametrize(
    ("name", "model"),
    [
        ("queue", list[MerchantQueueItem]),
        ("profile", MerchantProfile),
        ("decisions", list[Decision]),
        ("audit", list[AuditEntry]),
        ("model_card", ModelCard),
    ],
)
def test_api_fixtures_match_their_schema(name, model):
    TypeAdapter(model).validate_python(load_api_fixture(name))


@pytest.mark.parametrize("name", SCORE_FIXTURES)
def test_score_is_the_rounded_probability(name):
    score = ScoreResponse.model_validate(load_api_fixture(name))
    assert score.score == round(100 * score.probability)


@pytest.mark.parametrize("name", SCORE_FIXTURES)
def test_score_parts_sum_to_the_score(name):
    """Baseline + reasons + everything else must add up to the score shown."""
    score = ScoreResponse.model_validate(load_api_fixture(name))
    reasons = score.reasons_positive + score.reasons_negative
    total = score.baseline_score + sum(r.contribution for r in reasons) + score.other_contribution
    assert total == pytest.approx(score.score)
    assert all(reason.contribution > 0 for reason in score.reasons_positive)
    assert all(reason.contribution < 0 for reason in score.reasons_negative)


@pytest.mark.parametrize("name", SCORE_FIXTURES)
def test_score_band_follows_the_config_rules(name, config):
    """Low coverage gives 'Needs more info' whatever the score (docs/MODEL_SPEC.md section 7)."""
    score = ScoreResponse.model_validate(load_api_fixture(name))
    if score.coverage < config["score"]["band_min_coverage"]:
        expected = "Needs more info"
    elif score.score >= config["score"]["band_strong_min_score"]:
        expected = "Strong"
    else:
        expected = "Review"
    assert score.band == expected


def test_strong_score_fixture_has_three_reasons_each_side(config):
    score = ScoreResponse.model_validate(load_api_fixture("score_strong"))
    wanted = config["score"]["top_reasons_each_side"]
    assert len(score.reasons_positive) == wanted
    assert len(score.reasons_negative) == wanted


@pytest.mark.parametrize("name", SCORE_FIXTURES)
def test_score_reasons_use_the_dictionary_sentences(name):
    dictionary = load_dictionary()["features"]
    score = ScoreResponse.model_validate(load_api_fixture(name))
    sides = (("positive", score.reasons_positive), ("negative", score.reasons_negative))
    for side, reasons in sides:
        for reason in reasons:
            sentences = dictionary[reason.code][side]
            assert reason.sentence_en == sentences["en"]
            assert reason.sentence_bn == sentences["bn"]


def test_queue_never_shows_a_score_without_coverage_and_band():
    for item in TypeAdapter(list[MerchantQueueItem]).validate_python(load_api_fixture("queue")):
        shown = [item.score is not None, item.coverage is not None, item.band is not None]
        assert all(shown) or not any(shown), item.merchant_id
        if not item.consent_valid:
            assert item.score is None, "no score without consent"


# --- decisions: the officer decides ------------------------------------------------


def test_valid_decision_requests_are_accepted():
    for body in load_api_fixture("decision_requests")["valid"]:
        DecisionCreate.model_validate(body)


def test_override_without_reason_and_unknown_actions_are_rejected():
    for body in load_api_fixture("decision_requests")["invalid"]:
        with pytest.raises(ValidationError):
            DecisionCreate.model_validate(body)


def test_api_contract_has_no_approve_or_decline_action():
    actions = DecisionCreate.model_json_schema()["properties"]["officer_action"]["enum"]
    assert actions == ["accept", "override_up", "override_down", "needs_more_info"]
