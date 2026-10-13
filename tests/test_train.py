"""Tests for the training run (logistic regression baseline).

Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md sections 5, 9 and 12; PROJECT_BRIEF section 18, item 23.
"""

from __future__ import annotations

import copy
import json

import numpy as np
import pandas as pd
import pytest

from src.config import load_config
from src.features.build_features import CONTEXT_COLUMNS, COVERAGE_COLUMNS, DELIVERY_FEATURES
from src.features.dictionary import expected_directions, load_dictionary
from src.model.calibrate import fit_calibrator
from src.model.dataset import build_dataset
from src.model.evaluate import paired_auc_gain
from src.model.preprocess import QuantileClipper
from src.model.train import (
    fit_with_expected_directions,
    load_model,
    make_logistic_regression,
    predict_probability,
    save_artifacts,
    train_models,
    write_report,
)
from src.synth.generate import build_tables

GROUP_COLUMNS = ["town_tier", "shop_type", "has_trade_license", "district"]


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


# --- the preparation steps -----------------------------------------------------------


def test_clipper_learns_limits_from_training_data_only():
    train = pd.DataFrame({"x": np.arange(101, dtype=float)})  # 0 .. 100
    clipper = QuantileClipper(0.10, 0.90).fit(train)
    assert clipper.lower_limits_[0] == pytest.approx(10)
    assert clipper.upper_limits_[0] == pytest.approx(90)

    later = pd.DataFrame({"x": [-500.0, 50.0, 9999.0, np.nan]})
    clipped = clipper.transform(later)[:, 0]
    assert clipped[0] == pytest.approx(10) and clipped[2] == pytest.approx(90)
    assert clipped[1] == 50
    assert np.isnan(clipped[3]), "an empty value stays empty"


def test_missing_values_are_neutral_for_the_model(config):
    """A merchant with no delivery data gets exactly the score of an average-delivery one."""
    rng = np.random.default_rng(0)
    names = ["a", *DELIVERY_FEATURES]
    train = pd.DataFrame(rng.normal(size=(500, len(names))), columns=names)
    labels = (rng.random(500) < 0.8).astype(int)
    model = make_logistic_regression(config).fit(train, labels)

    clipped_means = np.nanmean(model.named_steps["clip"].transform(train), axis=0)
    one = train.iloc[[0]].copy()
    no_delivery = one.copy()
    no_delivery[DELIVERY_FEATURES] = np.nan
    average_delivery = one.copy()
    average_delivery[DELIVERY_FEATURES] = clipped_means[1:]

    assert model.predict_proba(no_delivery)[0, 1] == pytest.approx(
        model.predict_proba(average_delivery)[0, 1]
    )


def test_the_model_gets_no_missing_flag(result):
    """One weight per input: no extra 'was missing' columns."""
    weights = result["model"].named_steps["model"].coef_[0]
    assert len(weights) == len(result["features"])
    assert 1 <= len(result["features"]) <= 10


# --- what the model may see ----------------------------------------------------------


def test_only_behaviour_features_reach_the_model(result):
    used = set(result["features"])
    assert not used & set(CONTEXT_COLUMNS), "amounts of data must not be model inputs"
    assert not used & set(COVERAGE_COLUMNS)
    assert not used & set(GROUP_COLUMNS), "audit columns must not be model inputs"
    assert not any(name.startswith("q_") for name in used), "the questionnaire is not in the model"


def test_training_uses_only_consenting_merchants_with_known_outcomes(result):
    for part in (result["split"].train, result["split"].validation, result["split"].test):
        assert part["consent_valid"].all()
        assert part["label"].isin([0, 1]).all()
    summary = result["report"]["dataset"]
    assert summary["left_out_no_valid_consent"] > 0
    assert summary["left_out_no_outcome_yet"] > 0


def test_training_period_comes_before_validation_and_test(result):
    split = result["split"]
    assert split.train["cutoff_date"].max() < split.validation["cutoff_date"].min()
    assert split.validation["cutoff_date"].max() < split.test["cutoff_date"].min()


# --- the report ----------------------------------------------------------------------


def test_report_is_measured_on_validation_and_never_on_test(result):
    report = result["report"]
    assert "validation" in report["measured_on"]
    assert report["validation"]["loans"] == len(result["split"].validation)
    assert "test" not in report, "no test-period numbers may appear in a training report"


def test_model_beats_both_baselines_on_validation(result):
    report = result["report"]
    metrics = report["validation"]["metrics"]
    baselines = report["baselines"]
    assert metrics["roc_auc"] > baselines["purchases_only"]["metrics"]["roc_auc"] > 0.5
    assert metrics["brier"] < baselines["always_average_rate"]["brier"]


def test_probabilities_are_not_bare_zeros_and_ones(result):
    split, features = result["split"], result["features"]
    probabilities = result["model"].predict_proba(split.validation[features])[:, 1]
    assert ((probabilities > 0) & (probabilities < 1)).all()
    assert len(np.unique(np.round(probabilities, 3))) > 50


def test_auc_is_not_suspiciously_high(result, config):
    """A very high AUC on this data would mean leakage."""
    auc = result["report"]["validation"]["metrics"]["roc_auc"]
    assert 0.6 < auc < config["sanity"]["suspicious_auc"]
    assert not any("leakage" in w for w in result["report"]["validation"]["warnings"])


def test_every_weight_points_the_way_its_meaning_says(result):
    """So a reason sentence can never contradict what the merchant actually did."""
    directions = expected_directions(load_dictionary())
    weights = result["report"]["coefficients"]
    assert set(weights) == set(result["features"])
    for name, weight in weights.items():
        assert weight * directions[name] >= 0, name
    report = result["report"]
    used, removed = report["inputs_used"], report["inputs_removed_for_pointing_the_wrong_way"]
    assert not set(used) & set(removed)
    assert set(used) | set(removed) == set(directions)


def test_an_input_that_points_the_wrong_way_is_removed(config):
    """A noise column told to mean "higher is better" while the data says otherwise."""
    rng = np.random.default_rng(5)
    quality = rng.normal(size=4000)
    train = pd.DataFrame(
        {
            "good_sign": quality + rng.normal(scale=0.5, size=4000),
            "wrong_sign": -quality + rng.normal(scale=0.5, size=4000),
            "label": (rng.random(4000) < 1 / (1 + np.exp(-(2 + quality)))).astype(int),
        }
    )
    directions = {"good_sign": 1, "wrong_sign": 1}
    model, kept, removed = fit_with_expected_directions(
        config, train, ["good_sign", "wrong_sign"], directions
    )
    assert kept == ["good_sign"]
    assert removed == ["wrong_sign"]
    assert model.named_steps["model"].coef_[0][0] > 0


def test_if_every_input_points_the_wrong_way_training_stops(config):
    rng = np.random.default_rng(6)
    quality = rng.normal(size=2000)
    train = pd.DataFrame(
        {"x": quality, "label": (rng.random(2000) < 1 / (1 + np.exp(-quality))).astype(int)}
    )
    with pytest.raises(ValueError, match="expected direction"):
        fit_with_expected_directions(config, train, ["x"], {"x": -1})


def test_gain_over_the_baseline_is_measured_on_the_same_loans(result):
    gain = result["report"]["gain_over_purchases_only"]
    assert gain["range"][0] <= gain["auc_gain"] <= gain["range"][1]
    assert gain["clearly_better"] == (gain["range"][0] > 0)
    assert gain["auc_gain"] > 0


def test_paired_gain_tells_a_real_improvement_from_none(config):
    rng = np.random.default_rng(8)
    quality = rng.normal(size=3000)
    labels = (rng.random(3000) < 1 / (1 + np.exp(-(2 + quality)))).astype(int)
    weak = 1 / (1 + np.exp(-(quality + rng.normal(scale=2.0, size=3000))))
    strong = 1 / (1 + np.exp(-(quality + rng.normal(scale=0.3, size=3000))))
    assert paired_auc_gain(labels, weak, strong, config)["clearly_better"]
    same = paired_auc_gain(labels, weak, weak, config)
    assert same["auc_gain"] == 0 and not same["clearly_better"]


def test_first_loans_and_repeat_loans_are_reported_apart(result):
    """The hard case (no payment history) must not hide behind the easier one."""
    by_history = result["report"]["validation_by_history"]
    assert set(by_history) == {"first_loans", "repeat_loans"}
    total = by_history["first_loans"]["loans"] + by_history["repeat_loans"]["loans"]
    assert total == result["report"]["validation"]["loans"]
    for part in by_history.values():
        assert 0.5 < part["roc_auc"] < 1
        assert part["roc_auc_range"][0] <= part["roc_auc"] <= part["roc_auc_range"][1]


def test_a_band_line_that_separates_nobody_is_pointed_out(result, config):
    share = result["report"]["validation"]["metrics"]["share_at_or_above_strong_line"]
    notes = result["report"]["notes"]
    assert (share > 0.9) == any("Strong line" in note for note in notes)


def test_calibration_is_compared_out_of_fold_and_reported(result):
    calibration = result["report"]["calibration"]
    assert calibration["method"] in ("none", "platt", "isotonic")
    assert set(calibration["candidates"]) == {"none", "platt", "isotonic"}
    assert "validation period only" in calibration["fitted_on"]
    assert result["calibrator"].method == calibration["method"]
    chosen = calibration["candidates"][calibration["method"]]
    assert result["report"]["validation"]["metrics"]["brier"] == pytest.approx(chosen["brier"])


def test_the_calibrator_never_sees_training_or_test_loans(result, config):
    """Refitting it on the validation loans alone must give the same calibrator back."""
    split, features = result["split"], result["features"]
    raw = result["model"].predict_proba(split.validation[features])[:, 1]
    again = fit_calibrator(raw, split.validation["label"], result["calibrator"].method)
    np.testing.assert_allclose(again.predict(raw), result["calibrator"].predict(raw))


def test_training_twice_gives_the_same_model(config):
    tables, _, _ = build_tables(config, 1.0)
    dataset = build_dataset(tables, config)
    first = train_models(dataset, config)["report"]["coefficients"]
    second = train_models(dataset, config)["report"]["coefficients"]
    assert first == second


# --- saving and loading ------------------------------------------------------------


def test_saved_model_scores_exactly_like_the_trained_one(result, config, tmp_path):
    metadata = save_artifacts(result, config, artifacts_dir=tmp_path)
    saved = load_model("synthetic_bd", artifacts_dir=tmp_path)
    rows = result["split"].validation[result["features"]]
    np.testing.assert_allclose(
        saved["model"].predict_proba(rows)[:, 1], result["model"].predict_proba(rows)[:, 1]
    )
    assert saved["features"] == result["features"]
    assert saved["version_id"] == metadata["version_id"]
    assert metadata["calibrator"] == result["report"]["calibration"]["method"]

    # The probability a score is made from goes through the saved calibrator.
    calibrated = predict_probability(saved, result["split"].validation)
    expected = result["calibrator"].predict(result["model"].predict_proba(rows)[:, 1])
    np.testing.assert_allclose(calibrated, expected)
    assert ((calibrated > 0) & (calibrated < 1)).all()


def test_metadata_records_what_a_reader_needs(result, config, tmp_path):
    metadata = save_artifacts(result, config, artifacts_dir=tmp_path)
    on_disk = json.loads((tmp_path / "synthetic_bd" / "metadata.json").read_text(encoding="utf-8"))
    assert on_disk == metadata
    for key in (
        "version_id",
        "code_commit",
        "data_seed",
        "train_window",
        "feature_list",
        "calibrator",
        "validation_metrics",
    ):
        assert key in metadata, key
    assert metadata["version_id"].startswith("synthetic_bd-")
    assert metadata["data_seed"] == config["seed"]
    assert "Decision support only" in metadata["note"]


def test_report_files_are_written(result, config, tmp_path):
    metadata = save_artifacts(result, config, artifacts_dir=tmp_path)
    paths = write_report(result, metadata, reports_dir=tmp_path)
    report = json.loads(paths["metrics"].read_text(encoding="utf-8"))
    assert report["model_version"] == metadata["version_id"]
    assert report["validation"]["metrics"]["roc_auc"] > 0.6
    assert paths["calibration_plot"].stat().st_size > 1000


def test_loading_a_model_that_was_never_trained_says_what_to_do(tmp_path):
    with pytest.raises(FileNotFoundError, match="python tasks.py train"):
        load_model("synthetic_bd", artifacts_dir=tmp_path)
