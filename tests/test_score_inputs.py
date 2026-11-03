"""Tests for the score card's full list of inputs and its coverage checklist (Oct 17).

Owner role: C (ML), with the lead.
Implements: the lead's request that an officer sees where the whole score came from and
why coverage is what it is (PROJECT_BRIEF section 18, items 23 and 45).

What must hold, for every scored merchant:
- every model input is listed once, in model order;
- baseline + all points = the exact score (up to the 2-decimal rounding of each part);
- an input the merchant has no data for has 0 points: missing data never lowers a score;
- coverage is the sum of the weights of the checklist items that are present.
"""

from __future__ import annotations

import pytest
from accounts_seed import headers_for, seed_accounts, seed_person  # noqa: F401

from tests.test_api import OFFICER


@pytest.fixture(scope="module")
def cards(api_world):
    """The score cards of 40 consenting merchants of the API world."""
    from fastapi.testclient import TestClient

    from src.api.main import app

    queue = api_world.services.scorer.queue()
    ids = queue[queue["consent_valid"]]["merchant_id"].tolist()[:40]
    app.state.services = api_world.services
    try:
        client = TestClient(app)
        return [client.get(f"/merchants/{m}/score", headers=OFFICER).json() for m in ids]
    finally:
        del app.state.services


def test_every_input_is_listed_once_in_model_order(cards, api_world):
    features = api_world.saved["features"]
    for card in cards:
        assert [i["code"] for i in card["inputs"]] == features


def test_baseline_and_all_points_add_up_to_the_score(cards):
    for card in cards:
        total = card["baseline_score"] + sum(i["points"] for i in card["inputs"])
        # each part is rounded to 2 decimals, so allow half a cent per part
        allowed = 0.006 * (len(card["inputs"]) + 1)
        assert total == pytest.approx(100 * card["probability"], abs=allowed)
        assert abs(total - card["score"]) <= 0.5 + allowed


def test_missing_data_has_no_points(cards):
    missing = [i for card in cards for i in card["inputs"] if not i["has_data"]]
    assert missing, "the test merchants should include some missing inputs"
    assert all(i["points"] == 0 for i in missing)
    assert all(i["detail"] is None and i["sentence_en"] is None for i in missing)


def test_every_input_says_where_its_data_comes_from(cards):
    groups = {i["group"] for card in cards for i in card["inputs"]}
    assert groups <= {"purchases", "payments", "deliveries"}
    assert all(i["label"] for card in cards for i in card["inputs"])


def test_coverage_is_the_sum_of_the_present_checklist_items(cards, api_world):
    weights = api_world.config["coverage_weights"]
    for card in cards:
        items = card["coverage_items"]
        assert [x["item"] for x in items] == list(weights)
        assert sum(x["weight"] for x in items) == pytest.approx(1.0)
        present = sum(x["weight"] for x in items if x["present"])
        assert present == pytest.approx(card["coverage"], abs=1e-4)


def test_the_top_reasons_are_among_the_inputs_with_the_same_points(cards):
    for card in cards:
        points = {i["code"]: i["points"] for i in card["inputs"]}
        for reason in card["reasons_positive"] + card["reasons_negative"]:
            assert points[reason["code"]] == pytest.approx(reason["contribution"], abs=0.01)
