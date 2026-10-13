"""Tests for calibration: does the predicted probability mean what it says?

Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 6 (validation only, then frozen; ranking kept).
"""

from __future__ import annotations

import copy

import numpy as np
import pytest
from sklearn.metrics import brier_score_loss, roc_auc_score

from src.config import load_config
from src.model.calibrate import (
    METHODS,
    Calibrator,
    choose_calibrator,
    fit_calibrator,
    out_of_fold,
)
from src.model.evaluate import calibration_error


@pytest.fixture(scope="module")
def config() -> dict:
    return load_config()


def make_loans(n: int = 6000, seed: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """True repayment probabilities (mostly high, like our data) and outcomes drawn from them."""
    rng = np.random.default_rng(seed)
    true_probability = 1 / (1 + np.exp(-(2.2 + rng.normal(size=n))))
    labels = (rng.random(n) < true_probability).astype(int)
    return true_probability, labels


def overconfident(probabilities: np.ndarray) -> np.ndarray:
    """Push probabilities away from the middle: the classic miscalibration."""
    log_odds = np.log(probabilities / (1 - probabilities))
    return 1 / (1 + np.exp(-2.5 * log_odds))


def error(labels: np.ndarray, probabilities: np.ndarray) -> float:
    return calibration_error(labels, probabilities, 10, "quantile")


# --- one calibrator -------------------------------------------------------------------


def test_none_returns_the_probabilities_unchanged():
    probabilities = np.array([0.2, 0.9, 0.55])
    result = fit_calibrator(probabilities, [0, 1, 1], "none").predict(probabilities)
    np.testing.assert_array_equal(result, probabilities)


@pytest.mark.parametrize("method", ["platt", "isotonic"])
def test_a_calibrator_repairs_overconfident_probabilities(method):
    true_probability, labels = make_loans()
    wrong = overconfident(true_probability)
    learn, check = slice(0, 3000), slice(3000, None)  # learn on one half, check on the other

    calibrator = fit_calibrator(wrong[learn], labels[learn], method)
    repaired = calibrator.predict(wrong[check])

    assert error(labels[check], repaired) < error(labels[check], wrong[check]) / 2
    assert brier_score_loss(labels[check], repaired) < brier_score_loss(labels[check], wrong[check])
    assert ((repaired >= 0) & (repaired <= 1)).all()


def test_platt_keeps_the_order_of_the_loans():
    """So the ranking, and with it the AUC, is the same before and after."""
    true_probability, labels = make_loans()
    wrong = overconfident(true_probability)
    repaired = fit_calibrator(wrong, labels, "platt").predict(wrong)
    in_order = repaired[np.argsort(wrong, kind="stable")]
    assert (np.diff(in_order) >= 0).all()
    assert roc_auc_score(labels, repaired) == pytest.approx(roc_auc_score(labels, wrong))


def test_isotonic_never_reverses_the_order():
    true_probability, labels = make_loans()
    wrong = overconfident(true_probability)
    repaired = fit_calibrator(wrong, labels, "isotonic").predict(wrong)
    in_order = repaired[np.argsort(wrong, kind="stable")]
    assert (np.diff(in_order) >= 0).all()


def test_probabilities_of_exactly_zero_or_one_do_not_break_platt():
    probabilities = np.array([0.0, 1.0, 0.5, 0.9, 0.1, 0.8] * 20)
    labels = np.array([0, 1, 1, 1, 0, 1] * 20)
    repaired = fit_calibrator(probabilities, labels, "platt").predict(probabilities)
    assert np.isfinite(repaired).all()


def test_unknown_method_and_unfitted_calibrator_are_refused():
    with pytest.raises(ValueError, match="Unknown calibration method"):
        Calibrator("magic")
    with pytest.raises(ValueError, match="not been fitted"):
        Calibrator("platt").predict([0.5])


# --- choosing honestly ----------------------------------------------------------------


def test_out_of_fold_is_harder_than_checking_on_the_same_loans(config):
    """Isotonic fitted and checked on the same loans flatters itself; out of fold it cannot."""
    rng = np.random.default_rng(3)
    probabilities = rng.random(600)
    labels = (rng.random(600) < 0.9).astype(int)  # outcomes unrelated to the probabilities
    same_loans = fit_calibrator(probabilities, labels, "isotonic").predict(probabilities)
    honest = out_of_fold(probabilities, labels, "isotonic", config)
    assert brier_score_loss(labels, honest) > brier_score_loss(labels, same_loans)


def test_already_calibrated_probabilities_are_left_alone(config):
    true_probability, labels = make_loans()
    chosen = choose_calibrator(true_probability, labels, config)
    assert chosen["method"] == "none"
    np.testing.assert_array_equal(chosen["out_of_fold"], true_probability)
    assert set(chosen["candidates"]) == set(METHODS)


def test_overconfident_probabilities_get_a_calibrator(config):
    true_probability, labels = make_loans()
    wrong = overconfident(true_probability)
    chosen = choose_calibrator(wrong, labels, config)
    assert chosen["method"] in ("platt", "isotonic")
    candidates = chosen["candidates"]
    assert candidates[chosen["method"]]["brier"] < candidates["none"]["brier"]
    assert error(labels, chosen["out_of_fold"]) < error(labels, wrong)
    assert chosen["calibrator"].method == chosen["method"]


def test_a_method_set_in_the_config_is_used_but_all_are_still_compared(config):
    forced = copy.deepcopy(config)
    forced["model"]["calibration"] = "isotonic"
    true_probability, labels = make_loans()
    chosen = choose_calibrator(true_probability, labels, forced)
    assert chosen["method"] == "isotonic"
    assert "config" in chosen["chosen_by"]
    assert set(chosen["candidates"]) == set(METHODS)


def test_choosing_twice_gives_the_same_answer(config):
    true_probability, labels = make_loans()
    wrong = overconfident(true_probability)
    first = choose_calibrator(wrong, labels, config)
    second = choose_calibrator(wrong, labels, config)
    assert first["candidates"] == second["candidates"]
    np.testing.assert_array_equal(first["out_of_fold"], second["out_of_fold"])


def test_too_few_loans_of_one_outcome_gives_a_clear_message(config):
    probabilities = np.linspace(0.1, 0.9, 50)
    labels = np.ones(50, dtype=int)
    labels[:2] = 0
    with pytest.raises(ValueError, match="at least 5 loans of each outcome"):
        choose_calibrator(probabilities, labels, config)
