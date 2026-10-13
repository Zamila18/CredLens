"""Tests for score, coverage and band.

Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 7 (with its worked examples) and the rule that
    missing delivery data lowers coverage, never the score.
"""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

from src.config import coverage_weights_for_mode, load_config
from src.features.build_features import COVERAGE_COLUMNS
from src.model.score import (
    BANDS,
    NEEDS_MORE_INFO,
    REVIEW,
    STRONG,
    band_for,
    band_lines,
    band_summary,
    coverage_for_rows,
    coverage_from_checklist,
    low_score_warning,
    score_from_probability,
    score_table,
)


@pytest.fixture(scope="module")
def config() -> dict:
    return load_config()


@pytest.fixture(scope="module")
def weights(config) -> dict:
    return coverage_weights_for_mode(config, "synthetic_bd")


def checklist(weights: dict, **present: bool) -> dict:
    """Every item absent unless named."""
    return {name: present.get(name, False) for name in weights}


def coverage_rows(weights: dict, rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{f"cov_{name}": row.get(name, False) for name in weights} for row in rows])


# --- the worked examples of docs/MODEL_SPEC.md section 7 ------------------------------


def test_worked_example_strong(config):
    """Probability 0.92 with 85% coverage: score 92, band Strong."""
    score = score_from_probability(0.92, config)
    assert score == 92
    assert band_for(score, 0.85, config) == STRONG
    assert not low_score_warning(score, config)


def test_worked_example_review(config):
    """Probability 0.84 with 85% coverage: score 84, band Review."""
    score = score_from_probability(0.84, config)
    assert score == 84
    assert band_for(score, 0.85, config) == REVIEW


def test_worked_example_needs_more_info(config):
    """Probability 0.93 with 35% coverage: a high score, but too little to go on."""
    score = score_from_probability(0.93, config)
    assert score == 93
    assert band_for(score, 0.35, config) == NEEDS_MORE_INFO


def test_worked_example_low_score_warning(config):
    """Probability 0.62 with 85% coverage: Review, with an explicit low-score warning."""
    score = score_from_probability(0.62, config)
    assert band_for(score, 0.85, config) == REVIEW
    assert low_score_warning(score, config)


# --- band rules -----------------------------------------------------------------------


@pytest.mark.parametrize("score", [0, 40, 89, 90, 100])
def test_low_coverage_always_gives_needs_more_info(score, config):
    assert band_for(score, 0.44, config) == NEEDS_MORE_INFO
    assert band_for(score, 0.0, config) == NEEDS_MORE_INFO


def test_the_lines_themselves_are_inside_the_better_band(config):
    lines = band_lines(config)
    strong, coverage = lines["band_strong_min_score"], lines["band_min_coverage"]
    assert band_for(strong, coverage, config) == STRONG
    assert band_for(strong - 1, coverage, config) == REVIEW
    assert band_for(strong, coverage - 0.01, config) == NEEDS_MORE_INFO


def test_band_uses_the_displayed_score(config):
    """0.895 is shown as 90, so it is Strong; 0.894 is shown as 89, so it is Review."""
    assert band_for(score_from_probability(0.895, config), 0.9, config) == STRONG
    assert band_for(score_from_probability(0.894, config), 0.9, config) == REVIEW


def test_a_band_is_always_one_of_the_three_labels(config):
    for score in range(0, 101, 5):
        for coverage in (0.0, 0.3, 0.45, 0.7, 1.0):
            assert band_for(score, coverage, config) in BANDS


def test_no_band_says_approve_or_decline():
    """The system never decides: the labels are reading aids."""
    for band in BANDS:
        assert not any(word in band.lower() for word in ("approve", "decline", "reject", "accept"))


def test_a_data_mode_can_have_its_own_lines(config):
    own = copy.deepcopy(config)
    own["score"]["by_mode"] = {"taiwan_cc": {"band_strong_min_score": 80}}
    assert band_for(85, 0.9, own, "taiwan_cc") == STRONG
    assert band_for(85, 0.9, own, "synthetic_bd") == REVIEW
    # A line the mode does not set falls back to the default.
    assert band_lines(own, "taiwan_cc")["band_min_coverage"] == config["score"]["band_min_coverage"]


# --- coverage -------------------------------------------------------------------------


def test_coverage_is_the_sum_of_the_weights_present(weights):
    assert coverage_from_checklist(checklist(weights), weights) == 0
    assert coverage_from_checklist({name: True for name in weights}, weights) == 1
    some = checklist(weights, purchases_present=True, deliveries_present=True)
    expected = weights["purchases_present"] + weights["deliveries_present"]
    assert coverage_from_checklist(some, weights) == pytest.approx(expected)


def test_a_checklist_that_does_not_match_the_weights_is_refused(weights):
    with pytest.raises(ValueError, match="Missing"):
        coverage_from_checklist({"purchases_present": True}, weights)
    wrong = {**checklist(weights), "made_up_item": True}
    with pytest.raises(ValueError, match="made_up_item"):
        coverage_from_checklist(wrong, weights)


def test_missing_delivery_data_lowers_coverage_and_not_the_score(config, weights):
    """The same probability, with and without delivery data: same score, lower coverage."""
    everything = {name: True for name in weights}
    rows = coverage_rows(weights, [everything, {**everything, "deliveries_present": False}])
    table = score_table([0.93, 0.93], rows, config, "synthetic_bd")
    assert table["score"].tolist() == [93, 93]
    assert table["coverage"].iloc[0] == 1
    assert table["coverage"].iloc[1] == pytest.approx(1 - weights["deliveries_present"])


def test_coverage_exactly_on_the_line_counts_as_enough(config, weights):
    """Sums of weights such as 0.20 + 0.15 + 0.10 must not fall a hair below the line."""
    row = {"purchases_present": True, "deliveries_present": True, "recent_activity_30d": True}
    rows = coverage_rows(weights, [row])
    coverage = coverage_for_rows(rows, config, "synthetic_bd").iloc[0]
    assert coverage == config["score"]["band_min_coverage"] == 0.45
    assert band_for(95, coverage, config) == STRONG


def test_a_new_merchant_with_purchases_and_deliveries_can_be_scored(config, weights):
    """The thin-file merchant the project is for must not be locked out by design."""
    no_deliveries = {"purchases_present": True, "recent_activity_30d": True}
    first_loan = {**no_deliveries, "deliveries_present": True}
    with_questionnaire = {**no_deliveries, "questionnaire_done": True, "history_6_months": True}
    rows = coverage_rows(weights, [first_loan, no_deliveries, with_questionnaire])
    table = score_table([0.93, 0.93, 0.93], rows, config, "synthetic_bd")
    assert table["band"].tolist() == [STRONG, NEEDS_MORE_INFO, STRONG]


def test_the_feature_table_has_a_column_for_every_checklist_item(weights):
    assert {f"cov_{name}" for name in weights} <= set(COVERAGE_COLUMNS)


def test_a_feature_table_without_coverage_columns_is_refused(config):
    with pytest.raises(ValueError, match="no coverage column"):
        coverage_for_rows(pd.DataFrame({"x": [1]}), config, "synthetic_bd")


# --- the table and its summary --------------------------------------------------------


def test_score_table_has_one_complete_row_per_loan(config, weights):
    everything = {name: True for name in weights}
    rows = coverage_rows(weights, [everything, everything, {}])
    table = score_table([0.95, 0.60, 0.95], rows, config, "synthetic_bd")
    assert table["band"].tolist() == [STRONG, REVIEW, NEEDS_MORE_INFO]
    assert table["low_score_warning"].tolist() == [False, True, False]
    assert table["probability"].between(0, 1).all()
    assert list(table.columns) == ["probability", "score", "coverage", "band", "low_score_warning"]


def test_band_summary_counts_every_loan_once(config, weights):
    everything = {name: True for name in weights}
    rows = coverage_rows(weights, [everything] * 4 + [{}] * 2)
    table = score_table([0.95, 0.95, 0.60, 0.60, 0.9, 0.9], rows, config, "synthetic_bd")
    summary = band_summary(table, np.array([1, 1, 1, 0, 1, 0]))
    assert sum(part["loans"] for part in summary.values()) == 6
    assert summary[STRONG]["share_repaid"] == 1
    assert summary[REVIEW]["share_repaid"] == 0.5
    assert summary[NEEDS_MORE_INFO]["share"] == pytest.approx(2 / 6)


# --- bad values are refused, never guessed -------------------------------------------


@pytest.mark.parametrize("coverage", [float("nan"), None, -0.1, 1.5, 85])
def test_a_band_is_never_made_from_a_bad_coverage(coverage, config):
    """A missing coverage once came out as 'Strong'. It must stop instead."""
    with pytest.raises(ValueError, match="Coverage"):
        band_for(95, coverage, config)


@pytest.mark.parametrize("score", [float("nan"), None, -1, 101])
def test_a_band_is_never_made_from_a_bad_score(score, config):
    with pytest.raises(ValueError, match="score"):
        band_for(score, 0.9, config)


@pytest.mark.parametrize("probability", [float("nan"), -0.1, 1.4, [0.5, float("nan")]])
def test_a_score_is_never_made_from_a_bad_probability(probability, config):
    with pytest.raises(ValueError, match="probability"):
        score_from_probability(probability, config)


def test_an_unknown_checklist_answer_counts_as_not_present(weights):
    answers = {**checklist(weights), "history_6_months": float("nan"), "payments_present": None}
    assert coverage_from_checklist(answers, weights) == 0


@pytest.mark.parametrize("value", ["False", "yes", 2, 0.5])
def test_a_checklist_answer_that_is_not_yes_or_no_is_refused(value, weights, config):
    """The text "False" would be read as a yes by Python."""
    answers = {**checklist(weights), "history_6_months": value}
    with pytest.raises(ValueError, match="history_6_months"):
        coverage_from_checklist(answers, weights)
    rows = pd.DataFrame([{f"cov_{name}": answer for name, answer in answers.items()}])
    with pytest.raises(ValueError, match="history_6_months"):
        coverage_for_rows(rows, config, "synthetic_bd")


def test_coverage_columns_stored_as_zero_and_one_are_read_correctly(config, weights):
    """A database hands booleans back as 0 and 1."""
    rows = pd.DataFrame([{f"cov_{name}": flag for name in weights} for flag in (1, 0)])
    assert coverage_for_rows(rows, config, "synthetic_bd").tolist() == [1.0, 0.0]


def test_coverage_of_an_empty_table_is_empty(config, weights):
    rows = pd.DataFrame({f"cov_{name}": pd.Series(dtype=bool) for name in weights})
    assert len(coverage_for_rows(rows, config, "synthetic_bd")) == 0


def test_band_lines_of_an_unknown_mode_are_refused(config):
    with pytest.raises(ValueError, match="Unknown data mode"):
        band_lines(config, "mars")
