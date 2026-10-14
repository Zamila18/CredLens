"""Make the model's number mean a probability.

Purpose: check, and if needed correct, how well a predicted probability matches what
    happens ("when the model says 90%, do about 90% repay?").
Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 6. Settings: `model.calibration`,
    `model.calibration_folds` and `model.calibration_min_brier_gain` in config/default.yaml.

Three choices:
- "none": use the model's probability as it is. A logistic regression is often already
  well calibrated, and then any correction only adds noise.
- "platt": a two-number correction (a stretch and a shift) of the model's log-odds. It
  keeps the order of the loans exactly.
- "isotonic": a free step-shaped correction. More flexible, needs more data, and gives
  several loans the same probability (ties).

How the choice is made honestly. The calibrator may only learn from the validation
period (never training, never test). But a correction measured on the same loans it
learned from always looks good. So the validation loans are cut into folds; each fold is
corrected by a calibrator fitted on the other folds, and the three choices are compared
on those out-of-fold probabilities. A more flexible choice wins only if it lowers the
Brier score by at least `calibration_min_brier_gain`; otherwise the simpler one stays.
The calibrator that is saved is then fitted on all validation loans and frozen. The test
period re-checks it once, in the final report.

Calibration fixes the meaning of the number. It must not change the ranking.

That last rule is enforced, because isotonic can break it. Where the model ranks a
stretch of loans the wrong way round, isotonic flattens that stretch into one value, and
the AUC goes up. The gain would come from the validation period's own outcomes, not from
anything the model learned in training: on the Kiva data it lifted the AUC from 0.64 to
0.76. So a method whose out-of-fold AUC is HIGHER than the uncalibrated AUC by more than
`model.calibration_max_auc_gain` is not eligible in "auto". (A small loss of AUC is
normal for isotonic, which gives several loans the same value, and is not a problem.)
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold

from src.model.evaluate import calibration_error

METHODS = ("none", "platt", "isotonic")  # simplest first
EDGE = 1e-6  # keeps log-odds finite, and calibrated probabilities off exactly 0 and 1


def _log_odds(probabilities: np.ndarray) -> np.ndarray:
    clipped = np.clip(probabilities, EDGE, 1 - EDGE)
    return np.log(clipped / (1 - clipped))


class Calibrator:
    """A fitted correction from the model's probability to a calibrated probability."""

    def __init__(self, method: str):
        if method not in METHODS:
            raise ValueError(f"Unknown calibration method: {method!r}. Use one of {METHODS}.")
        self.method = method
        self.fitted_ = None

    def fit(self, probabilities: Any, labels: Any) -> Calibrator:
        """Learn the correction from predicted probabilities and true outcomes."""
        probabilities = np.asarray(probabilities, dtype=float)
        labels = np.asarray(labels, dtype=int)
        if self.method == "platt":
            # A very large C means "no regularisation": only the two numbers are fitted.
            self.fitted_ = LogisticRegression(C=1e6, max_iter=1000).fit(
                _log_odds(probabilities).reshape(-1, 1), labels
            )
        elif self.method == "isotonic":
            self.fitted_ = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip").fit(
                probabilities, labels
            )
        return self

    def predict(self, probabilities: Any) -> np.ndarray:
        """Return calibrated probabilities, one per input, each between 0 and 1."""
        probabilities = np.asarray(probabilities, dtype=float)
        if self.method == "none":
            return probabilities.copy()
        if self.fitted_ is None:
            raise ValueError("This calibrator has not been fitted yet.")
        if not np.isfinite(probabilities).all():
            raise ValueError("Cannot calibrate a missing probability.")
        if self.method == "platt":
            result = self.fitted_.predict_proba(_log_odds(probabilities).reshape(-1, 1))[:, 1]
        else:
            result = self.fitted_.predict(probabilities)
        # Isotonic steps can land on exactly 0 or 1. No loan is ever certain, so the
        # result is kept just inside.
        return np.clip(result, EDGE, 1 - EDGE)


def fit_calibrator(probabilities: Any, labels: Any, method: str) -> Calibrator:
    """Fit one calibrator. Pass validation-period loans only."""
    return Calibrator(method).fit(probabilities, labels)


def out_of_fold(probabilities: Any, labels: Any, method: str, config: dict[str, Any]) -> np.ndarray:
    """Calibrated probabilities where no loan is corrected by a calibrator that saw it."""
    probabilities = np.asarray(probabilities, dtype=float)
    labels = np.asarray(labels, dtype=int)
    folds = config["model"]["calibration_folds"]
    rarest = int(min((labels == 0).sum(), (labels == 1).sum()))
    if rarest < folds:
        raise ValueError(
            f"Calibration needs at least {folds} loans of each outcome in the validation "
            f"period; the rarer outcome has {rarest}."
        )
    cutter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=config["seed"])
    result = np.empty(len(labels), dtype=float)
    for learn, apply in cutter.split(probabilities.reshape(-1, 1), labels):
        calibrator = fit_calibrator(probabilities[learn], labels[learn], method)
        result[apply] = calibrator.predict(probabilities[apply])
    return result


def choose_calibrator(probabilities: Any, labels: Any, config: dict[str, Any]) -> dict[str, Any]:
    """Compare the calibration choices on the validation period and fit the chosen one.

    Args:
        probabilities: the model's probabilities for the validation loans.
        labels: 1 = repaid in time, 0 = not, for the same loans.
        config: the validated config. `model.calibration` is "auto" (compare and choose)
            or the name of one method (use it, but still report the comparison).

    Returns a dict with:
        method: the chosen method.
        calibrator: that method fitted on ALL the given loans (the one to save).
        out_of_fold: the chosen method's out-of-fold probabilities (the honest ones to
            measure on).
        candidates: Brier, calibration error and AUC of every method, out of fold, and
            whether the method keeps the ranking (`keeps_ranking`).
        chosen_by: one sentence saying why.
    """
    probabilities = np.asarray(probabilities, dtype=float)
    labels = np.asarray(labels, dtype=int)
    settings, evaluation = config["model"], config["evaluation"]
    bins, binning = evaluation["calibration_bins"], evaluation["calibration_binning"]

    corrected = {m: out_of_fold(probabilities, labels, m, config) for m in METHODS}
    candidates = {
        m: {
            "brier": float(brier_score_loss(labels, p)),
            "calibration_error": calibration_error(labels, p, bins, binning),
            "roc_auc": float(roc_auc_score(labels, p)),
        }
        for m, p in corrected.items()
    }

    # A calibrator is there to fix the number. If it makes the ranking better, it has
    # learned the order from the validation outcomes, which is not its job.
    max_gain = settings["calibration_max_auc_gain"]
    untouched = candidates["none"]["roc_auc"]
    for numbers in candidates.values():
        numbers["keeps_ranking"] = bool(numbers["roc_auc"] - untouched <= max_gain)

    wanted = settings["calibration"]
    if wanted == "auto":
        min_gain = settings["calibration_min_brier_gain"]
        method = METHODS[0]
        for candidate in METHODS[1:]:
            better = candidates[method]["brier"] - candidates[candidate]["brier"] >= min_gain
            if better and candidates[candidate]["keeps_ranking"]:
                method = candidate
        chosen_by = (
            f"auto: the simplest method is kept unless a more flexible one lowers the "
            f"out-of-fold Brier score by at least {min_gain} without improving the ranking "
            f"(AUC at most {max_gain} above the uncalibrated model)"
        )
        refused = [m for m, numbers in candidates.items() if not numbers["keeps_ranking"]]
        if refused:
            chosen_by += f". Not eligible because it changed the ranking: {', '.join(refused)}"
    else:
        method = wanted
        chosen_by = f"set in the config (model.calibration = {wanted})"

    return {
        "method": method,
        "calibrator": fit_calibrator(probabilities, labels, method),
        "out_of_fold": corrected[method],
        "candidates": candidates,
        "chosen_by": chosen_by,
    }
