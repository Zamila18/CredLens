"""Tests for the LightGBM candidate and the rule that chooses between the two models.

Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 5 (prefer the simple model unless the flexible one
    is clearly better) and the rules that hold for every model: an input only pushes the
    way its meaning says, and missing data is neutral.
"""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

from src.config import load_config
from src.features.build_features import DELIVERY_FEATURES, PAYMENT_FEATURES, model_feature_names
from src.features.dictionary import expected_directions, load_dictionary
from src.model.boosted import make_lightgbm, tune_lightgbm, tuning_parts
from src.model.dataset import build_dataset
from src.model.split import RANDOM_SPLIT, TIME_SPLIT
from src.model.train import LIGHTGBM, LOGISTIC_REGRESSION, choose_model, train_models
from src.synth.generate import build_tables


@pytest.fixture(scope="module")
def config() -> dict:
    small = copy.deepcopy(load_config())
    small["data"]["n_merchants"] = 5000
    small["data"]["delivery_signal_strength"] = 1.0
    small["model"]["bootstrap_resamples"] = 100
    return small


@pytest.fixture(scope="module")
def result(config) -> dict:
    tables, _, _ = build_tables(config, 1.0)
    return train_models(build_dataset(tables, config), config)


@pytest.fixture(scope="module")
def boosted(result) -> dict:
    return result["candidates"][LIGHTGBM]


# --- the rules every model must keep ---------------------------------------------------


def test_each_input_only_pushes_the_way_its_meaning_says(boosted, result):
    """Move one input from low to high, the rest fixed: the probability never turns back."""
    directions = expected_directions(load_dictionary())
    features, model = boosted["features"], boosted["model"]
    sample = result["split"].validation[features].head(40)
    for name in features:
        low, high = result["split"].train[name].quantile([0.02, 0.98])
        for _, row in sample.iterrows():
            ladder = pd.DataFrame([row] * 25)
            ladder[name] = np.linspace(low, high, 25)
            steps = np.diff(model.predict_proba(ladder)[:, 1]) * directions[name]
            assert (steps >= -1e-9).all(), name


@pytest.mark.parametrize("group", [DELIVERY_FEATURES, PAYMENT_FEATURES])
def test_missing_data_is_neutral_for_lightgbm(group, boosted, result):
    """A merchant with no delivery (or payment) data scores exactly like an average one."""
    features, model = boosted["features"], boosted["model"]
    rows = result["split"].validation[features].dropna().head(50)
    missing = rows.copy()
    missing[group] = np.nan
    clipped_means = np.nanmean(
        model.named_steps["clip"].transform(result["split"].train[features]), axis=0
    )
    average = rows.copy()
    for name in group:
        average[name] = clipped_means[features.index(name)]
    np.testing.assert_allclose(
        model.predict_proba(missing)[:, 1], model.predict_proba(average)[:, 1]
    )


def test_lightgbm_sees_only_behaviour_inputs(boosted):
    assert boosted["features"] == model_feature_names("ABC")
    assert not any(name.startswith(("cov_", "q_")) for name in boosted["features"])


def test_new_merchants_are_not_scored_below_what_they_repay(result):
    """Thin-file check on the model in use: predicted is not clearly under actual."""
    table = result["report"]["validation_predicted_against_actual"]
    for group in ("first_loans", "under_6_months_history"):
        assert table[group]["predicted_minus_actual"] > -0.02, group


# --- tuning ----------------------------------------------------------------------------


def test_tuning_uses_the_last_months_of_training_and_never_validation(result, config):
    split = result["split"]
    fit_part, tune_part, how = tuning_parts(split.train, config, TIME_SPLIT)
    assert len(fit_part) + len(tune_part) == len(split.train)
    assert fit_part["cutoff_date"].max() < tune_part["cutoff_date"].min()
    assert tune_part["cutoff_date"].max() < split.validation["cutoff_date"].min()
    assert "training period" in how


def test_without_dates_the_tuning_part_is_a_random_share(result, config):
    train = result["split"].train
    fit_part, tune_part, how = tuning_parts(train, config, RANDOM_SPLIT)
    share = config["model"]["lightgbm"]["tuning_share"]
    assert len(tune_part) == pytest.approx(share * len(train), abs=2)
    assert tune_part["label"].mean() == pytest.approx(fit_part["label"].mean(), abs=0.01)
    assert not set(fit_part.index) & set(tune_part.index)
    assert "random" in how


def test_a_training_period_too_short_to_cut_by_time_falls_back_to_a_random_share(result, config):
    """India has one training month: holding back three months would leave nothing to fit on."""
    train = result["split"].train
    last_weeks = train[train["cutoff_date"] >= train["cutoff_date"].max() - pd.DateOffset(days=40)]
    fit_part, tune_part, how = tuning_parts(last_weeks, config, TIME_SPLIT)
    assert len(fit_part) + len(tune_part) == len(last_weeks)
    assert len(fit_part) > len(tune_part) > 0
    assert fit_part["label"].nunique() == tune_part["label"].nunique() == 2
    assert "too short" in how


def test_tuning_report_says_what_was_tried(boosted, config):
    tuning = boosted["tuning"]
    assert len(tuning["tried"]) == len(config["model"]["lightgbm"]["grid"])
    lowest = min(entry["tuning_log_loss"] for entry in tuning["tried"])
    assert tuning["chosen"]["tuning_log_loss"] == lowest
    assert 1 <= tuning["chosen"]["trees"] <= config["model"]["lightgbm"]["max_trees"]
    assert boosted["model"].named_steps["model"].n_estimators == tuning["chosen"]["trees"]
    assert "validation period was not used" in tuning["note"]


def test_lightgbm_does_not_memorise_the_training_loans(result):
    """A large gap between training and validation AUC would mean overfitting."""
    candidate = result["report"]["candidates"][LIGHTGBM]
    assert candidate["train_roc_auc"] - candidate["validation_metrics"]["roc_auc"] < 0.08


def test_a_tuning_part_with_one_outcome_is_refused(config):
    dates = pd.date_range("2025-01-01", periods=400, freq="D")
    train = pd.DataFrame({"cutoff_date": dates, "label": 1, "x": 1.0})
    with pytest.raises(ValueError, match="only one outcome"):
        tune_lightgbm(config, train, ["x"], {"x": 1}, TIME_SPLIT)


def test_make_lightgbm_is_built_from_the_config(config):
    setting = config["model"]["lightgbm"]["grid"][0]
    model = make_lightgbm(config, ["a", "b"], {"a": 1, "b": -1}, setting, 7)
    booster = model.named_steps["model"]
    assert booster.n_estimators == 7
    assert list(booster.monotone_constraints) == [1, -1]
    assert booster.num_leaves == setting["num_leaves"]
    assert [name for name, _ in model.steps] == ["clip", "fill", "model"]


# --- choosing between the two ----------------------------------------------------------


def candidate(probabilities: np.ndarray, labels: np.ndarray) -> dict:
    brier = float(np.mean((probabilities - labels) ** 2))
    return {"probabilities": probabilities, "evaluation": {"metrics": {"brier": brier}}}


def make_choice(noise_simple: float, noise_flexible: float, config: dict) -> dict:
    rng = np.random.default_rng(11)
    quality = rng.normal(size=4000)
    labels = (rng.random(4000) < 1 / (1 + np.exp(-(2 + quality)))).astype(int)

    def predict(noise: float) -> np.ndarray:
        return 1 / (1 + np.exp(-(2 + quality + rng.normal(scale=noise, size=4000))))

    fitted = {
        LOGISTIC_REGRESSION: candidate(predict(noise_simple), labels),
        LIGHTGBM: candidate(predict(noise_flexible), labels),
    }
    return choose_model(fitted, labels, config)


def test_a_clearly_better_lightgbm_is_chosen(config):
    choice = make_choice(noise_simple=2.0, noise_flexible=0.2, config=config)
    assert choice["chosen"] == LIGHTGBM
    assert all(choice["checks"].values())


def test_an_equal_lightgbm_does_not_replace_the_simple_model(config):
    choice = make_choice(noise_simple=0.5, noise_flexible=0.5, config=config)
    assert choice["chosen"] == LOGISTIC_REGRESSION
    assert choice["reason"].endswith("so the logistic regression stays.")
    assert "Not met" not in choice["reason"], "the old wording read backwards"


def test_a_small_gain_that_may_be_chance_does_not_replace_the_simple_model(config):
    """Slightly better on average, but the range of the gain dips under the threshold."""
    choice = make_choice(noise_simple=0.60, noise_flexible=0.50, config=config)
    gain = choice["auc_gain_of_lightgbm"]
    assert gain["auc_gain"] > 0
    assert gain["range"][0] < config["model"]["prefer_simple_if_auc_gain_below"]
    assert choice["chosen"] == LOGISTIC_REGRESSION


def test_a_worse_lightgbm_does_not_replace_the_simple_model(config):
    choice = make_choice(noise_simple=0.2, noise_flexible=2.0, config=config)
    assert choice["chosen"] == LOGISTIC_REGRESSION


def test_with_one_candidate_there_is_nothing_to_choose(config):
    labels = np.array([1, 0, 1, 1])
    fitted = {LOGISTIC_REGRESSION: candidate(np.array([0.9, 0.4, 0.8, 0.7]), labels)}
    assert choose_model(fitted, labels, config)["chosen"] == LOGISTIC_REGRESSION


def test_the_report_shows_both_candidates_and_follows_the_rule(result, config):
    report = result["report"]
    assert set(report["candidates"]) == {LOGISTIC_REGRESSION, LIGHTGBM}
    choice = report["model_choice"]
    assert report["model"] == choice["chosen"] == result["model_name"]
    expected = LIGHTGBM if all(choice["checks"].values()) else LOGISTIC_REGRESSION
    assert choice["chosen"] == expected
    needed = config["model"]["prefer_simple_if_auc_gain_below"]
    lowest_gain = choice["auc_gain_of_lightgbm"]["range"][0]
    assert choice["checks"]["whole_gain_range_reaches_the_threshold"] == (lowest_gain >= needed)
    chosen = report["candidates"][choice["chosen"]]
    assert report["validation"]["metrics"] == chosen["validation_metrics"]
    assert report["inputs_used"] == chosen["inputs_used"] == result["features"]


def test_only_the_simple_model_can_be_asked_for(config):
    only = copy.deepcopy(config)
    only["model"]["candidates"] = ["logistic_regression"]
    only["data"]["n_merchants"] = 1500
    tables, _, _ = build_tables(only, 1.0)
    result = train_models(build_dataset(tables, only), only)
    assert result["model_name"] == LOGISTIC_REGRESSION
    assert set(result["report"]["candidates"]) == {LOGISTIC_REGRESSION}
