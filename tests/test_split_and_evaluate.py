"""Tests for the time split and the evaluation metrics.

Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md sections 4 (split by time) and 9 (evaluation).
"""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

from src.config import load_config
from src.model.evaluate import (
    baseline_metrics,
    bootstrap_ranges,
    calibration_error,
    calibration_table,
    evaluate,
    point_metrics,
)
from src.model.score import score_from_probability
from src.model.split import (
    RANDOM_SPLIT,
    TIME_SPLIT,
    WEAKER_SPLIT_NOTE,
    EmptySplitError,
    split_by_time,
    split_for_mode,
    split_settings,
    split_stratified_random,
)


@pytest.fixture(scope="module")
def config() -> dict:
    return load_config()


def fast(config: dict, resamples: int = 100) -> dict:
    """The config with fewer bootstrap resamples, so tests stay quick."""
    quicker = copy.deepcopy(config)
    quicker["model"]["bootstrap_resamples"] = resamples
    return quicker


# --- split by time -------------------------------------------------------------------


def monthly_loans(first_month: str = "2025-01-01", months: int = 20) -> pd.DataFrame:
    """One loan on the 15th of each month, 20 months from January 2025 by default."""
    dates = pd.date_range(first_month, periods=months, freq="MS") + pd.Timedelta(days=14)
    return pd.DataFrame(
        {"loan_id": [f"L{n}" for n in range(months)], "cutoff_date": dates, "label": 1}
    )


def test_time_split_uses_twelve_three_three_months(config):
    split = split_by_time(monthly_loans(), config, start="2025-01-01")
    assert split.sizes() == {"train": 12, "validation": 3, "test": 3}
    assert split.method == TIME_SPLIT
    assert split.boundaries == {
        "train_from": "2025-01-01",
        "validation_from": "2026-01-01",
        "test_from": "2026-04-01",
        "test_until": "2026-07-01",
    }


def test_every_training_loan_comes_before_every_validation_and_test_loan(config):
    split = split_by_time(monthly_loans(), config, start="2025-01-01")
    assert split.train["cutoff_date"].max() < split.validation["cutoff_date"].min()
    assert split.validation["cutoff_date"].max() < split.test["cutoff_date"].min()


def test_no_loan_is_in_two_parts_and_later_loans_are_left_out(config):
    loans = monthly_loans()
    split = split_by_time(loans, config, start="2025-01-01")
    used = pd.concat([split.train, split.validation, split.test])["loan_id"]
    assert used.is_unique
    left_out = set(loans["loan_id"]) - set(used)
    assert left_out == {"L18", "L19"}  # July and August 2026: after the test period


def test_the_split_says_how_many_loans_it_left_out(config):
    """Loans outside the three periods are counted, never dropped without a trace."""
    split = split_by_time(monthly_loans(), config, start="2025-03-01")
    assert split.left_out == {"before_train_period": 2, "after_test_period": 0, "no_date": 0}
    assert sum(split.sizes().values()) + sum(split.left_out.values()) == 20


def test_a_loan_on_a_boundary_day_belongs_to_the_later_part(config):
    loans = pd.DataFrame(
        {"loan_id": ["A", "B"], "cutoff_date": pd.to_datetime(["2025-12-31", "2026-01-01"])}
    )
    split = split_by_time(loans, config, start="2025-01-01", allow_empty=True)
    assert list(split.train["loan_id"]) == ["A"]
    assert list(split.validation["loan_id"]) == ["B"]


def test_without_a_start_date_the_split_begins_in_the_month_of_the_first_loan(config):
    split = split_by_time(monthly_loans(), config)
    assert split.boundaries["train_from"] == "2025-01-01"


def test_split_months_can_be_given(config):
    months = {"train_months": 6, "validation_months": 2, "test_months": 2}
    split = split_by_time(monthly_loans(), config, start="2025-01-01", months=months)
    assert split.sizes() == {"train": 6, "validation": 2, "test": 2}


def test_an_empty_part_stops_the_run_with_a_helpful_message(config):
    """Three months of loans cannot fill a 12/3/3 split: say so instead of going on."""
    three_months = monthly_loans(months=3)
    with pytest.raises(EmptySplitError, match="split_by_mode"):
        split_by_time(three_months, config)


# --- the right split for each data mode ----------------------------------------------


def test_synthetic_split_starts_on_the_generator_start_date(config):
    """The first synthetic loan is in February; the periods must still start in January."""
    loans = monthly_loans(first_month="2025-02-01", months=19)
    split = split_for_mode(loans, config, mode="synthetic_bd")
    assert split.boundaries["train_from"] == config["generator"]["start_date"]
    assert split.boundaries["test_until"] == "2026-07-01"
    assert split.sizes() == {"train": 11, "validation": 3, "test": 3}
    assert split.left_out["after_test_period"] == 2


def test_india_uses_its_own_month_counts(config):
    """India L&T covers August to October 2018: one month each."""
    assert split_settings(config, "india_ltfs")["months"] == {
        "train_months": 1,
        "validation_months": 1,
        "test_months": 1,
    }
    loans = monthly_loans(first_month="2018-08-01", months=3)
    split = split_for_mode(loans, config, mode="india_ltfs")
    assert split.sizes() == {"train": 1, "validation": 1, "test": 1}
    assert split.method == TIME_SPLIT


@pytest.mark.parametrize("mode", ["taiwan_cc", "homecredit"])
def test_modes_without_dates_get_the_weaker_random_split(config, mode):
    split = split_for_mode(labelled_rows(), config, mode=mode)
    assert split.method == RANDOM_SPLIT
    assert split.note == WEAKER_SPLIT_NOTE


# --- stratified random split (the marked exception) --------------------------------


def labelled_rows(n: int = 1800, share_repaid: float = 0.9) -> pd.DataFrame:
    labels = (np.arange(n) % 10 < share_repaid * 10).astype(int)
    return pd.DataFrame({"loan_id": np.arange(n), "label": labels})


def test_random_split_keeps_the_label_share_and_the_proportions(config):
    frame = labelled_rows()
    split = split_stratified_random(frame, config)
    assert split.sizes() == {"train": 1200, "validation": 300, "test": 300}
    for part in (split.train, split.validation, split.test):
        assert part["label"].mean() == pytest.approx(0.9, abs=0.005)


def test_random_split_is_marked_weaker_and_is_reproducible(config):
    frame = labelled_rows()
    first = split_stratified_random(frame, config)
    second = split_stratified_random(frame, config)
    assert first.method == RANDOM_SPLIT
    assert first.note == WEAKER_SPLIT_NOTE
    assert list(first.test["loan_id"]) == list(second.test["loan_id"])
    used = pd.concat([first.train, first.validation, first.test])["loan_id"]
    assert used.is_unique and len(used) == len(frame)


def test_random_split_copes_with_a_repeated_index(config):
    """Frames glued together often repeat index labels; every row must still be placed once."""
    frame = pd.concat([labelled_rows(900), labelled_rows(900)])
    frame["row"] = np.arange(len(frame))
    split = split_stratified_random(frame, config)
    placed = pd.concat([split.train, split.validation, split.test])["row"]
    assert sorted(placed) == list(range(1800))


# --- the score rounding used everywhere --------------------------------------------


def test_score_is_the_rounded_probability_times_one_hundred(config):
    assert score_from_probability(0.72, config) == 72
    assert score_from_probability(0.695, config) == 70
    assert score_from_probability(0.694, config) == 69
    assert list(score_from_probability([0.0, 0.5, 1.0], config)) == [0, 50, 100]
    assert isinstance(score_from_probability(0.3, config), int)


# --- metrics -------------------------------------------------------------------------


def test_perfect_and_useless_rankings(config):
    labels = np.array([0] * 20 + [1] * 80)
    perfect = np.where(labels == 1, 0.9, 0.1)
    assert point_metrics(labels, perfect, config)["roc_auc"] == pytest.approx(1.0)
    constant = np.full(100, 0.8)
    assert point_metrics(labels, constant, config)["roc_auc"] == pytest.approx(0.5)


def test_a_reversed_ranking_scores_below_a_coin_toss(config):
    labels = np.array([0] * 20 + [1] * 80)
    reversed_scores = np.where(labels == 1, 0.1, 0.9)
    assert point_metrics(labels, reversed_scores, config)["roc_auc"] == pytest.approx(0.0)


def test_brier_is_the_mean_squared_gap(config):
    labels = np.array([1, 1, 0, 0])
    probabilities = np.array([0.9, 0.6, 0.2, 0.5])
    expected = np.mean([0.1**2, 0.4**2, 0.2**2, 0.5**2])
    assert point_metrics(labels, probabilities, config)["brier"] == pytest.approx(expected)


def test_lowest_and_highest_scored_loans(config):
    # 100 loans scored 0.01 .. 1.00. The 10 lowest-scored are the only not-repaid ones.
    probabilities = np.arange(1, 101) / 100
    labels = (probabilities > 0.10).astype(int)
    metrics = point_metrics(labels, probabilities, config)
    assert metrics["precision_at_top_k"] == pytest.approx(1.0)
    assert metrics["not_repaid_rate_in_lowest_k"] == pytest.approx(10 / 20)
    assert metrics["not_repaid_caught_in_lowest"] == pytest.approx(1.0)  # all 10 in the lowest 20
    assert metrics["pr_auc_not_repaid"] == pytest.approx(1.0)


def test_the_lowest_scored_metric_separates_skill_from_no_skill(config):
    """With 90% repaid, top-k precision barely moves; the lowest-k rate does."""
    rng = np.random.default_rng(3)
    quality = rng.uniform(0.6, 0.999, 6000)
    labels = (rng.random(6000) < quality).astype(int)
    skilled = point_metrics(labels, quality, config)["not_repaid_rate_in_lowest_k"]
    unskilled = point_metrics(labels, rng.random(6000), config)["not_repaid_rate_in_lowest_k"]
    assert skilled > unskilled + 0.1


def test_share_at_the_strong_line_uses_the_rounded_score(config):
    """0.695 shows as a score of 70, so it counts as reaching a strong line of 70."""
    probabilities = np.array([0.695, 0.699, 0.70, 0.50])
    labels = np.array([1, 1, 1, 0])
    config = copy.deepcopy(config)
    config["score"]["band_strong_min_score"] = 70
    metrics = point_metrics(labels, probabilities, config)
    assert metrics["share_at_or_above_strong_line"] == pytest.approx(0.75)


def test_share_at_the_strong_line_uses_the_line_of_the_data_mode(config):
    probabilities = np.array([0.60, 0.40, 0.95, 0.70])
    labels = np.array([1, 0, 1, 1])
    config = copy.deepcopy(config)
    config["score"]["by_mode"] = {"taiwan_cc": {"band_strong_min_score": 50}}
    own = point_metrics(labels, probabilities, config, "taiwan_cc")
    default = point_metrics(labels, probabilities, config, "synthetic_bd")
    assert own["share_at_or_above_strong_line"] == pytest.approx(0.75)
    assert default["share_at_or_above_strong_line"] == pytest.approx(0.25)


def test_equal_width_calibration_table_compares_predicted_with_actual():
    probabilities = np.array([0.05, 0.05, 0.95, 0.95, 0.95, 0.95])
    labels = np.array([0, 0, 1, 1, 1, 0])
    table = calibration_table(labels, probabilities, bins=10, method="width")
    assert list(table["loans"]) == [2, 4]
    assert table.loc[0, "share_repaid"] == 0
    assert table.loc[1, "share_repaid"] == pytest.approx(0.75)
    # gaps: |0.05 - 0| and |0.95 - 0.75|, weighted 2 and 4
    expected = (2 * 0.05 + 4 * 0.20) / 6
    assert calibration_error(labels, probabilities, 10, "width") == pytest.approx(expected)


def test_quantile_bins_hold_the_same_number_of_loans():
    """Predictions bunched near 0.9 still fill every bin."""
    rng = np.random.default_rng(0)
    probabilities = np.clip(rng.normal(0.9, 0.05, 6000), 0.6, 0.999)
    labels = (rng.random(6000) < probabilities).astype(int)
    by_count = calibration_table(labels, probabilities, 10, "quantile")
    by_width = calibration_table(labels, probabilities, 10, "width")
    assert list(by_count["loans"]) == [600] * 10
    assert len(by_width) < 5
    assert (by_count["lowest"].diff().dropna() >= 0).all()


def test_well_calibrated_predictions_have_a_small_calibration_error():
    rng = np.random.default_rng(0)
    probabilities = rng.uniform(0.5, 1.0, size=20_000)
    labels = (rng.random(20_000) < probabilities).astype(int)
    overconfident = np.clip(probabilities + 0.15, 0, 1)
    assert calibration_error(labels, probabilities, 10) < 0.02
    assert calibration_error(labels, overconfident, 10) > 0.08


def test_unknown_binning_method_is_refused():
    with pytest.raises(ValueError, match="quantile"):
        calibration_table(np.array([0, 1]), np.array([0.2, 0.8]), 2, method="magic")


# --- inputs that must be refused -----------------------------------------------------


@pytest.mark.parametrize(
    ("labels", "probabilities", "message"),
    [
        ([0, 1, 2, 1], [0.1, 0.9, 0.8, 0.7], "0 .not repaid. or 1"),
        ([0, 1, 1, 1], [0.1, 1.7, 0.8, 0.7], "between 0 and 1"),
        ([0, 1, 1, 1], [0.1, -0.2, 0.8, 0.7], "between 0 and 1"),
        ([0, 1, 1, 1], [0.1, float("nan"), 0.8, 0.7], "missing"),
        ([0, 1, 1], [0.1, 0.9, 0.8, 0.7], "same length"),
    ],
)
def test_bad_inputs_are_refused_with_a_clear_message(config, labels, probabilities, message):
    with pytest.raises(ValueError, match=message):
        point_metrics(np.array(labels), np.array(probabilities), config)


def test_evaluation_needs_both_outcomes(config):
    with pytest.raises(ValueError, match="both outcomes"):
        evaluate(np.array([1, 1]), np.array([0.9, 0.8]), config)


def test_swapping_labels_and_probabilities_is_caught(config):
    """Labels first, probabilities second. The other way round must not pass quietly."""
    labels = np.array([0, 1, 1, 1])
    probabilities = np.array([0.2, 0.9, 0.8, 0.7])
    with pytest.raises(ValueError):
        evaluate(probabilities, labels, config)


# --- ranges, baselines, the full report ---------------------------------------------


def noisy(n: int, seed: int = 1) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    hidden = rng.normal(size=n)
    labels = (rng.random(n) < 1 / (1 + np.exp(-(2.2 + 1.2 * hidden)))).astype(int)
    noise = rng.normal(scale=0.8, size=n)
    probabilities = 1 / (1 + np.exp(-(2.2 + 0.8 * hidden + noise)))
    return labels, probabilities


def test_bootstrap_ranges_contain_the_point_estimate_and_repeat(config):
    labels, probabilities = noisy(4000)
    quick = fast(config, 200)
    ranges = bootstrap_ranges(labels, probabilities, quick)
    metrics = point_metrics(labels, probabilities, quick)
    for name in ("roc_auc", "pr_auc_not_repaid", "brier"):
        low, high = ranges[name]
        assert low <= metrics[name] <= high, name
        assert high > low, name
    assert ranges["resamples_used"] == 200
    assert ranges == bootstrap_ranges(labels, probabilities, quick)


def test_more_loans_give_a_narrower_range(config):
    labels, probabilities = noisy(4000)
    quick = fast(config, 200)
    wide = bootstrap_ranges(labels[:400], probabilities[:400], quick)["roc_auc"]
    narrow = bootstrap_ranges(labels, probabilities, quick)["roc_auc"]
    assert (narrow[1] - narrow[0]) < (wide[1] - wide[0])


def test_baseline_always_predicts_the_average_rate():
    labels = np.array([1] * 9 + [0])
    baseline = baseline_metrics(labels, 0.9)
    assert baseline["roc_auc"] == 0.5
    assert baseline["pr_auc_not_repaid"] == pytest.approx(0.1)
    assert baseline["brier"] == pytest.approx(0.9 * 0.01 + 0.1 * 0.81)
    assert baseline["calibration_error"] == pytest.approx(0.0)


def test_evaluate_reports_metrics_ranges_and_calibration(config):
    labels, probabilities = noisy(4000)
    report = evaluate(labels, probabilities, fast(config))
    assert report["loans"] == 4000
    assert report["not_repaid_loans"] == int((labels == 0).sum())
    assert {"roc_auc", "pr_auc_not_repaid", "brier", "calibration_error"} <= set(report["ranges"])
    assert sum(row["loans"] for row in report["calibration"]) == 4000
    assert report["warnings"] == []
    auc_low = report["ranges"]["roc_auc"][0]
    assert report["benchmark"]["point_estimate_reaches_it"] == (
        report["metrics"]["roc_auc"] >= 0.70
    )
    assert report["benchmark"]["whole_range_reaches_it"] == (auc_low >= 0.70)


def test_a_suspiciously_high_auc_raises_a_leakage_warning(config):
    labels = np.array([0] * 150 + [1] * 1350)
    leaked = np.where(labels == 1, 0.95, 0.05)
    report = evaluate(labels, leaked, fast(config, 50))
    assert any("leakage" in warning for warning in report["warnings"])


def test_scores_that_rank_the_wrong_way_raise_a_warning(config):
    labels = np.array([0] * 150 + [1] * 1350)
    upside_down = np.where(labels == 1, 0.2, 0.8)
    report = evaluate(labels, upside_down, fast(config, 50))
    assert any("wrong way" in warning for warning in report["warnings"])


def test_too_few_not_repaid_loans_raises_a_warning(config):
    """A result resting on a handful of not-repaid loans must say so."""
    labels, probabilities = noisy(400)
    assert (labels == 0).sum() < config["sanity"]["min_not_repaid_for_stable_metrics"]
    report = evaluate(labels, probabilities, fast(config))
    assert any("shaky" in warning for warning in report["warnings"])
