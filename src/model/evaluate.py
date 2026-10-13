"""Measure how good a set of predicted repayment probabilities is.

Purpose: turn true outcomes and predictions into the numbers reported in the model card,
    each with a range that shows how certain it is.
Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 9 (AUC, PR-AUC, Brier, calibration, top-k,
    bootstrap ranges, baselines). Settings come from the `evaluation`, `model` and
    `sanity` sections of config/default.yaml.

Every function takes the true labels first and the predicted probabilities second.

What each number means, in plain words (label 1 = repaid in time, 0 = not):
- roc_auc: how well the scores rank repaid loans above not-repaid ones. 0.5 is a coin
  toss, 1.0 is perfect. About 0.70 is considered useful for this kind of lending (CGAP).
- pr_auc_not_repaid: how well the model picks out the not-repaid loans. Reported for the
  rarer class on purpose, because with 90% repaid loans the other direction always
  looks good.
- brier: the average squared gap between the probability and what happened. Lower is
  better. A model that always predicts the average repayment rate sets the bar.
- calibration_error: when the model says 80%, do about 80% repay? The average gap across
  the bins, weighted by how many loans are in each. Lower is better. Bins hold the same
  number of loans each (quantile bins), because with most loans repaid, equal-width bins
  would leave most bins empty.
- not_repaid_rate_in_lowest_k: of the k lowest-scored loans, the share that did not
  repay. Compare it with the overall not-repaid share: the higher above it, the better.
- not_repaid_caught_in_lowest: of all not-repaid loans, the share that sits in the
  lowest-scored 20%. With no skill it would be 20%.
- precision_at_top_k: of the k highest-scored loans, the share that repaid. Kept because
  the specification asks for it, but it says little here: when 90% of loans repay,
  even random scores give about 0.9.

Ranges are bootstrap ranges: the loans are resampled many times and the middle 95% of
the results is reported. Report ranges, not third decimals. The resampling treats loans
as independent; a merchant with several loans makes the true uncertainty a little wider.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from src.model.score import band_lines, score_from_probability

RANGED_METRICS = ("roc_auc", "pr_auc_not_repaid", "brier", "calibration_error")


def _checked(labels: Any, probabilities: Any) -> tuple[np.ndarray, np.ndarray]:
    """Return clean arrays, or stop with a clear message about what is wrong."""
    labels = np.asarray(labels, dtype=float)
    probabilities = np.asarray(probabilities, dtype=float)
    if labels.shape != probabilities.shape:
        raise ValueError("Labels and probabilities must have the same length.")
    if np.isnan(labels).any() or np.isnan(probabilities).any():
        raise ValueError("Labels and probabilities must not contain missing values.")
    if not np.isin(labels, (0, 1)).all():
        raise ValueError("Labels must be 0 (not repaid) or 1 (repaid) and nothing else.")
    if (probabilities < 0).any() or (probabilities > 1).any():
        raise ValueError("Probabilities must lie between 0 and 1.")
    return labels.astype(int), probabilities


def calibration_table(
    labels: np.ndarray, probabilities: np.ndarray, bins: int, method: str = "quantile"
) -> pd.DataFrame:
    """Group predictions into bins and compare predicted with actual.

    Args:
        method: "quantile" puts the same number of loans in each bin; "width" uses
            equal-width bins between 0 and 1.

    Returns one row per non-empty bin: the lowest and highest prediction in it, the
    number of loans, the mean predicted probability and the share that actually repaid.
    """
    if method == "quantile":
        ranks = pd.Series(probabilities).rank(method="first")
        bin_of = pd.qcut(ranks, q=min(bins, len(ranks)), labels=False).to_numpy()
    elif method == "width":
        edges = np.linspace(0.0, 1.0, bins + 1)
        bin_of = np.clip(np.digitize(probabilities, edges[1:-1]), 0, bins - 1)
    else:
        raise ValueError(f"Unknown binning method: {method!r}. Use 'quantile' or 'width'.")

    frame = pd.DataFrame({"bin": bin_of, "predicted": probabilities, "actual": labels})
    table = frame.groupby("bin").agg(
        lowest=("predicted", "min"),
        highest=("predicted", "max"),
        loans=("actual", "size"),
        mean_predicted=("predicted", "mean"),
        share_repaid=("actual", "mean"),
    )
    return table.reset_index(drop=True)


def calibration_error(
    labels: np.ndarray, probabilities: np.ndarray, bins: int, method: str = "quantile"
) -> float:
    """Average gap between predicted and actual repayment, weighted by loans per bin."""
    table = calibration_table(labels, probabilities, bins, method)
    gap = (table["mean_predicted"] - table["share_repaid"]).abs()
    return float((gap * table["loans"]).sum() / table["loans"].sum())


def point_metrics(
    labels: Any, probabilities: Any, config: dict[str, Any], mode: str | None = None
) -> dict[str, float]:
    """Every metric once, on the given loans. Needs both outcomes to be present.

    `mode` picks the Strong line of that data mode; it defaults to the mode in the config.
    """
    settings = config["evaluation"]
    labels, probabilities = _checked(labels, probabilities)

    highest_first = np.argsort(-probabilities, kind="stable")
    lowest_first = highest_first[::-1]
    k = min(settings["top_k"], len(labels))
    lowest_share = lowest_first[: max(1, int(round(len(labels) * settings["lowest_share"])))]
    not_repaid = labels == 0

    scores = score_from_probability(probabilities, config)
    return {
        "roc_auc": float(roc_auc_score(labels, probabilities)),
        "pr_auc_not_repaid": float(average_precision_score(not_repaid, 1.0 - probabilities)),
        "brier": float(brier_score_loss(labels, probabilities)),
        "calibration_error": calibration_error(
            labels, probabilities, settings["calibration_bins"], settings["calibration_binning"]
        ),
        "not_repaid_rate_in_lowest_k": float(not_repaid[lowest_first[:k]].mean()),
        "not_repaid_caught_in_lowest": float(
            not_repaid[lowest_share].sum() / max(not_repaid.sum(), 1)
        ),
        "precision_at_top_k": float(labels[highest_first[:k]].mean()),
        "share_at_or_above_strong_line": float(
            (scores >= band_lines(config, mode)["band_strong_min_score"]).mean()
        ),
    }


def bootstrap_ranges(labels: Any, probabilities: Any, config: dict[str, Any]) -> dict[str, Any]:
    """Resample the loans many times and return the middle range of each metric.

    The seed comes from the config, so the same command gives the same ranges. A
    resample that happens to contain only one outcome cannot be scored and is skipped;
    `resamples_used` says how many were scored.
    """
    labels, probabilities = _checked(labels, probabilities)
    settings = config["evaluation"]
    bins, method = settings["calibration_bins"], settings["calibration_binning"]
    rng = np.random.default_rng(config["seed"])

    draws: dict[str, list[float]] = {name: [] for name in RANGED_METRICS}
    for _ in range(config["model"]["bootstrap_resamples"]):
        rows = rng.integers(0, len(labels), size=len(labels))
        y, p = labels[rows], probabilities[rows]
        if y.min() == y.max():
            continue
        draws["roc_auc"].append(roc_auc_score(y, p))
        draws["pr_auc_not_repaid"].append(average_precision_score(y == 0, 1.0 - p))
        draws["brier"].append(brier_score_loss(y, p))
        draws["calibration_error"].append(calibration_error(y, p, bins, method))

    level = settings["bootstrap_level"]
    low, high = 100 * (1 - level) / 2, 100 * (1 + level) / 2
    ranges: dict[str, Any] = {
        name: [float(np.percentile(values, low)), float(np.percentile(values, high))]
        for name, values in draws.items()
    }
    ranges["resamples_used"] = len(draws["roc_auc"])
    return ranges


def baseline_metrics(labels: Any, average_rate: float) -> dict[str, float]:
    """The bar to beat: always predicting the average repayment rate seen in training."""
    labels = np.asarray(labels, dtype=int)
    constant = np.full(len(labels), average_rate, dtype=float)
    return {
        "predicted_rate": float(average_rate),
        "roc_auc": 0.5,
        "pr_auc_not_repaid": float((labels == 0).mean()),
        "brier": float(brier_score_loss(labels, constant)),
        "calibration_error": float(abs(average_rate - labels.mean())),
    }


def evaluate(
    labels: Any, probabilities: Any, config: dict[str, Any], mode: str | None = None
) -> dict[str, Any]:
    """Return metrics with bootstrap ranges, and warnings when a result needs care.

    Args:
        labels: 1 = repaid in time, 0 = not.
        probabilities: predicted probability of repaying in time, one per loan.
        config: the validated config.
        mode: the data mode whose Strong line is used; defaults to the one in the config.

    Warnings are raised for: an AUC too good to be true (possible leakage), an AUC below
    a coin toss, and too few not-repaid loans for the numbers to be stable.
    """
    labels, probabilities = _checked(labels, probabilities)
    if len(labels) == 0 or labels.min() == labels.max():
        raise ValueError("Evaluation needs loans with both outcomes (repaid and not repaid).")

    settings, sanity = config["evaluation"], config["sanity"]
    metrics = point_metrics(labels, probabilities, config, mode)
    ranges = bootstrap_ranges(labels, probabilities, config)
    table = calibration_table(
        labels, probabilities, settings["calibration_bins"], settings["calibration_binning"]
    )
    not_repaid = int((labels == 0).sum())
    auc = metrics["roc_auc"]

    warnings = []
    if auc > sanity["suspicious_auc"]:
        warnings.append(
            f"AUC {auc:.3f} is above {sanity['suspicious_auc']}: treat this as leakage until "
            "proven otherwise."
        )
    if auc < 0.5:
        warnings.append(f"AUC {auc:.3f} is below 0.5: the scores rank loans the wrong way round.")
    if not_repaid < sanity["min_not_repaid_for_stable_metrics"]:
        warnings.append(
            f"Only {not_repaid} not-repaid loans (fewer than "
            f"{sanity['min_not_repaid_for_stable_metrics']}): the numbers are shaky, read the "
            "ranges rather than the point values."
        )

    benchmark = sanity["useful_auc_benchmark"]
    return {
        "loans": int(len(labels)),
        "not_repaid_loans": not_repaid,
        "share_repaid": float(labels.mean()),
        "metrics": metrics,
        "ranges": ranges,
        "range_level": settings["bootstrap_level"],
        "calibration": table.round(4).to_dict("records"),
        "benchmark": {
            "useful_auc": benchmark,
            "point_estimate_reaches_it": bool(auc >= benchmark),
            "whole_range_reaches_it": bool(ranges["roc_auc"][0] >= benchmark),
        },
        "warnings": warnings,
    }


def paired_auc_gain(
    labels: Any, baseline_probabilities: Any, new_probabilities: Any, config: dict[str, Any]
) -> dict[str, Any]:
    """How much AUC a model adds over a baseline on the same loans, with a range.

    The two models are scored on the same resampled loans each time, so the range is for
    the difference itself. That is much sharper than comparing two separate ranges, which
    can overlap even when one model is reliably better. `clearly_better` is True when the
    whole range is above zero.
    """
    labels, baseline = _checked(labels, baseline_probabilities)
    _, new = _checked(labels, new_probabilities)
    rng = np.random.default_rng(config["seed"])

    gains = []
    for _ in range(config["model"]["bootstrap_resamples"]):
        rows = rng.integers(0, len(labels), size=len(labels))
        y = labels[rows]
        if y.min() == y.max():
            continue
        gains.append(roc_auc_score(y, new[rows]) - roc_auc_score(y, baseline[rows]))

    level = config["evaluation"]["bootstrap_level"]
    low, high = np.percentile(gains, [100 * (1 - level) / 2, 100 * (1 + level) / 2])
    return {
        "auc_gain": float(roc_auc_score(labels, new) - roc_auc_score(labels, baseline)),
        "range": [float(low), float(high)],
        "clearly_better": bool(low > 0),
        "resamples_used": len(gains),
    }
