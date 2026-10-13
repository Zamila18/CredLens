"""Turn a calibrated probability into score, coverage and band.

Purpose: the readiness score an officer sees, the coverage percentage beside it, and the
    band (Strong / Review / Needs more info).
Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 7 and PROJECT_BRIEF section 18 (coverage is per
    data mode). Settings: the `score` section and the coverage weights in
    config/default.yaml.

Three separate things, on purpose:
- score: round(100 x probability of repaying in time). What the model thinks.
- coverage: how much of the information this data source can provide is present for the
  merchant, from 0 to 1. How much the model had to go on. Missing delivery data lowers
  coverage and never the score.
- band: a label for the officer, from the two numbers above.
    coverage below `band_min_coverage`      -> "Needs more info", whatever the score
    else score at or above the Strong line  -> "Strong"
    else                                    -> "Review"

A band is a reading aid. It never approves or declines anything: an officer decides.

The lines are settings, not facts. They were set from the validation scores of the
synthetic data (PROJECT_BRIEF section 18, item 26) and must be set again for any real
data source. A data mode can have its own lines under `score.by_mode`.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.config import VALID_MODES, coverage_weights_for_mode
from src.features.build_features import CHECKLIST_PREFIX

STRONG = "Strong"
REVIEW = "Review"
NEEDS_MORE_INFO = "Needs more info"
BANDS = (STRONG, REVIEW, NEEDS_MORE_INFO)
LINE_NAMES = ("band_strong_min_score", "band_min_coverage", "low_score_warning_below")


def score_from_probability(probability: Any, config: dict[str, Any]) -> Any:
    """Return round(scale x probability): the 0-100 score. Never a bare 0/1.

    Works for one probability (returns an int) or many (returns an integer array).
    A value exactly halfway, such as 69.5, rounds to the nearest even number (70), the
    same rule Python's own `round` uses. Everything that compares a score with a band
    line must go through this function, so the comparison matches what is displayed.
    """
    scale = config["score"]["scale"]
    values = np.asarray(probability, dtype=float)
    if not np.isfinite(values).all() or (values < 0).any() or (values > 1).any():
        raise ValueError("A probability must be a number between 0 and 1; no score was made.")
    scores = np.rint(scale * values).astype(int)
    return int(scores) if scores.ndim == 0 else scores


def band_lines(config: dict[str, Any], mode: str | None = None) -> dict[str, float]:
    """The band settings for a data mode: its own under `score.by_mode`, else the defaults."""
    settings = config["score"]
    mode = mode or config["data"]["mode"]
    if mode not in VALID_MODES:
        raise ValueError(f"Unknown data mode: {mode!r}")
    own = (settings.get("by_mode") or {}).get(mode) or {}
    return {name: own.get(name, settings[name]) for name in LINE_NAMES}


def coverage_from_checklist(checklist: dict[str, Any], weights: dict[str, float]) -> float:
    """Return coverage between 0 and 1: the summed weights of the items that are present.

    Args:
        checklist: item name -> present or not. It must have exactly the items of
            `weights`; a missing or unknown item is an error, not a silent zero.
        weights: the checklist weights of the data mode (they sum to 1.0).
    """
    if set(checklist) != set(weights):
        missing = sorted(set(weights) - set(checklist))
        unknown = sorted(set(checklist) - set(weights))
        raise ValueError(
            f"Coverage checklist does not match the weights. Missing: {missing}. "
            f"Unknown: {unknown}."
        )
    total = sum(weight for name, weight in weights.items() if _is_present(name, checklist[name]))
    return round(float(total), 4)


def _is_present(name: str, value: Any) -> bool:
    """Read one checklist answer. Only a clear yes or no is accepted.

    An empty value (None or NaN) means "not known", which counts as not present. Anything
    else, such as the text "False", is refused: Python would read it as a yes.
    """
    if value is None or (isinstance(value, (float, np.floating)) and np.isnan(value)):
        return False
    if isinstance(value, (bool, np.bool_)) or value in (0, 1):
        return bool(value)
    raise ValueError(f"Coverage item {name!r} must be yes or no, got {value!r}.")


def coverage_for_rows(
    rows: pd.DataFrame, config: dict[str, Any], mode: str | None = None
) -> pd.Series:
    """Coverage for every row of a feature table, from its `cov_<item>` columns."""
    weights = coverage_weights_for_mode(config, mode)
    columns = [f"{CHECKLIST_PREFIX}{name}" for name in weights]
    absent = [column for column in columns if column not in rows.columns]
    if absent:
        raise ValueError(f"The feature table has no coverage column(s): {absent}.")
    present = np.column_stack(
        [[_is_present(column, value) for value in rows[column]] for column in columns]
    ).astype(float).reshape(len(rows), len(columns))
    # Rounded so that sums such as 0.25 + 0.20 compare equal to a line of 0.45.
    coverage = np.round(present @ np.array(list(weights.values())), 4)
    return pd.Series(coverage, index=rows.index, name="coverage")


def band_for(score: int, coverage: float, config: dict[str, Any], mode: str | None = None) -> str:
    """Return 'Needs more info' when coverage is low, whatever the score; else Strong or Review."""
    lines = band_lines(config, mode)
    scale = config["score"]["scale"]
    if coverage is None or not np.isfinite(coverage) or not 0 <= coverage <= 1:
        raise ValueError(f"Coverage must be a number between 0 and 1, got {coverage!r}.")
    if score is None or not np.isfinite(score) or not 0 <= score <= scale:
        raise ValueError(f"A score must be a number between 0 and {scale}, got {score!r}.")
    if round(float(coverage), 4) < lines["band_min_coverage"]:
        return NEEDS_MORE_INFO
    return STRONG if score >= lines["band_strong_min_score"] else REVIEW


def low_score_warning(score: int, config: dict[str, Any], mode: str | None = None) -> bool:
    """True when the score is low enough that the officer should be told so explicitly."""
    return bool(score < band_lines(config, mode)["low_score_warning_below"])


def score_table(
    probabilities: Any, rows: pd.DataFrame, config: dict[str, Any], mode: str | None = None
) -> pd.DataFrame:
    """Probability, score, coverage, band and low-score warning for every row.

    Args:
        probabilities: calibrated repayment probabilities, one per row of `rows`
            (from `src.model.train.predict_probability`).
        rows: the feature table rows the probabilities belong to.
    """
    table = pd.DataFrame(index=rows.index)
    table["probability"] = np.asarray(probabilities, dtype=float)
    table["score"] = score_from_probability(table["probability"].to_numpy(), config)
    table["coverage"] = coverage_for_rows(rows, config, mode)
    table["band"] = [
        band_for(score, coverage, config, mode)
        for score, coverage in zip(table["score"], table["coverage"])
    ]
    warn_below = band_lines(config, mode)["low_score_warning_below"]
    table["low_score_warning"] = table["score"] < warn_below
    return table


def band_summary(table: pd.DataFrame, labels: Any) -> dict[str, dict[str, Any]]:
    """For each band: how many loans it holds, its share, and the share that repaid."""
    labels = np.asarray(labels, dtype=float)
    summary = {}
    for band in BANDS:
        inside = (table["band"] == band).to_numpy()
        summary[band] = {
            "loans": int(inside.sum()),
            "share": float(inside.mean()),
            "share_repaid": float(labels[inside].mean()) if inside.any() else None,
        }
    return summary
