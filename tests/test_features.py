"""Tests for the feature dictionary. The feature builder is tested in test_feature_builder.py.

Owner role: B (data engineer).
Implements: docs/FEATURE_DICTIONARY.md; PROJECT_BRIEF section 6.
"""

from __future__ import annotations

import pytest

from src.features.build_features import CONTEXT_COLUMNS, model_feature_names
from src.features.dictionary import (
    DIRECTIONAL_WORDS,
    expected_directions,
    load_dictionary,
    reason_sentence,
)

# Feature names listed in docs/FEATURE_DICTIONARY.md.
DOCUMENTED_FEATURES = {
    "purchases_90d",
    "purchase_value_90d",
    "basket_growth",
    "purchase_volatility",
    "purchase_regularity",
    "category_diversity",
    "supplier_repeat_share",
    "parcel_volume_90d",
    "avg_pay_delay_days",
    "late_pay_count_90d",
    "ontime_payment_rate",
    "credit_utilisation",
    "delivered_rate",
    "return_rate_90d",
    "failed_rate_90d",
    "cod_remit_ontime_rate",
    "dispatch_to_delivery_hours",
    "delivery_data_thin",
    "q_spend",
    "q_save",
    "q_borrow",
    "q_plan",
    "q_stress",
    "q_confidence",
}


@pytest.fixture(scope="module")
def dictionary():
    return load_dictionary()


def test_dictionary_has_every_documented_feature(dictionary):
    assert set(dictionary["features"]) == DOCUMENTED_FEATURES


def test_every_feature_has_a_known_group(dictionary):
    for name, entry in dictionary["features"].items():
        assert entry["group"] in dictionary["groups"], name


def test_every_sentence_exists_in_english_and_bangla(dictionary):
    for name, entry in dictionary["features"].items():
        assert entry["negative"]["en"] and entry["negative"]["bn"], name
        if entry["positive"] is not None:
            assert entry["positive"]["en"] and entry["positive"]["bn"], name


def test_only_the_thin_delivery_flag_lacks_a_positive_sentence(dictionary):
    without_positive = [n for n, e in dictionary["features"].items() if e["positive"] is None]
    assert without_positive == ["delivery_data_thin"]
    assert reason_sentence(dictionary, "delivery_data_thin", raised_score=True) is None


def test_questionnaire_sentences_are_marked_directional(dictionary):
    for name, entry in dictionary["features"].items():
        if entry["group"] != "D":
            continue
        for side in ("positive", "negative"):
            assert DIRECTIONAL_WORDS["en"] in entry[side]["en"], name
            assert DIRECTIONAL_WORDS["bn"] in entry[side]["bn"], name


def test_delivery_return_reasons_are_neutral_observations(dictionary):
    """Returns and failures may reflect delivery conditions, not the merchant."""
    assert "may reflect" in dictionary["features"]["return_rate_90d"]["negative"]["en"]
    assert "may reflect" in dictionary["features"]["failed_rate_90d"]["negative"]["en"]


def test_no_sales_or_repeat_customer_features(dictionary):
    """Mokam shows purchases only; the one sales proxy is REDX parcel volume."""
    for name in dictionary["features"]:
        assert "sales" not in name and "customer" not in name
    proxies = [n for n, e in dictionary["features"].items() if e.get("sales_proxy")]
    assert proxies == ["parcel_volume_90d"]


def test_reason_sentence_picks_side_and_language(dictionary):
    feature = "ontime_payment_rate"
    assert reason_sentence(dictionary, feature, True) == "Most payments arrive on time."
    assert reason_sentence(dictionary, feature, False, "bn") == "কম পেমেন্ট সময়মতো আসে।"


def test_dictionary_marks_exactly_the_context_columns_as_not_model_inputs(dictionary):
    """The dictionary and the code must agree on what the model may see."""
    marked = {n for n, e in dictionary["features"].items() if e.get("model_input") is False}
    assert marked == set(CONTEXT_COLUMNS)
    assert not marked & set(model_feature_names("ABC"))


def test_every_model_input_says_which_way_it_points(dictionary):
    """Training relies on this to stop a reason from contradicting the facts."""
    directions = expected_directions(dictionary)
    assert set(directions) == set(model_feature_names("ABC"))
    assert directions["supplier_repeat_share"] == 1
    assert directions["avg_pay_delay_days"] == -1
    assert directions["return_rate_90d"] == -1
    assert set(directions.values()) == {1, -1}


def test_sentences_agree_with_the_stated_direction(dictionary):
    """For a "higher is worse" input, the negative sentence must describe a high value."""
    entry = dictionary["features"]["avg_pay_delay_days"]
    assert entry["higher_is"] == "worse"
    assert "late" in entry["negative"]["en"]
    entry = dictionary["features"]["ontime_payment_rate"]
    assert entry["higher_is"] == "better"
    assert "on time" in entry["positive"]["en"]
