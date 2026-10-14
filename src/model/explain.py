"""Explain a score: which of the merchant's inputs raised it and which lowered it.

Purpose: three reasons that raise the score and three that lower it, as plain sentences
    in English and Bangla, with numbers that add up to the score on the screen.
Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 8 and docs/FEATURE_DICTIONARY.md. Settings: the
    `score` section of config/default.yaml.

How a score is split into reasons, in plain words:

1. Start from the "average merchant": someone whose every input equals the training
   average. Their score is the baseline.
2. Switch on this merchant's real inputs one at a time and watch the score move. The
   order matters a little, so every possible order is tried and the moves of each input
   are averaged. That average is the input's contribution, in score points. (This is the
   Shapley value, the quantity "SHAP values" are named after, with the average merchant
   as the reference point. With about ten inputs it can be computed exactly, for any
   model and any calibrator. A test checks that the numbers equal those of the SHAP
   library's own exact explainer, for both models.)
3. Baseline + all contributions = the merchant's exact score, always.

What follows from this:
- An input the merchant does not have is already "average" for the model (missing data
  is neutral), so its contribution is exactly zero and it never becomes a reason.
- Because every input can only push the way its meaning says, a better-than-average
  value always gets a positive contribution and a worse one a negative contribution.
- A sentence is shown only when it is true for the merchant. "Credit use is close to the
  limit" needs use above 80%, not merely above average (`shown_when` in the feature
  dictionary). When the plain sentence is not true, a comparing one is shown instead
  ("Credit use is higher than at similar shops"), so a large contribution is never hidden.
- The parts shown add up to the score on the screen: baseline + the reasons shown +
  "all other inputs" = score. The last part also absorbs the rounding of the score to a
  whole number.

A reason is an observation about the data. It is never a cause and never an accusation.
"""

from __future__ import annotations

from math import factorial
from typing import Any

import numpy as np
import pandas as pd

from src.config import banner_text
from src.features.dictionary import (
    detail_text,
    features_for_mode,
    load_dictionary,
    reason_sentences,
)
from src.model.score import band_for, coverage_for_rows, low_score_warning, score_from_probability


def calibrated_probability(saved: dict[str, Any], rows: pd.DataFrame) -> np.ndarray:
    """Calibrated repayment probabilities from a saved model, for rows of inputs."""
    raw = saved["model"].predict_proba(rows[saved["features"]])[:, 1]
    return saved["calibrator"].predict(raw)


def average_inputs(saved: dict[str, Any]) -> dict[str, float]:
    """The "average merchant": the training average of every input, after clipping.

    These are the values the model itself puts in place of a missing input.
    """
    averages = saved["model"].named_steps["fill"].statistics_
    return {name: float(value) for name, value in zip(saved["features"], averages)}


def _shapley(present_values: np.ndarray, value_of: Any) -> tuple[np.ndarray, float, float]:
    """Exact contributions of the inputs that are present.

    Args:
        present_values: this merchant's values for the inputs it has.
        value_of: a function from a table of inputs (one row per combination, empty where
            an input is switched off) to the score of each row.

    Returns the contribution of each input, the baseline (all off) and the full value.
    """
    count = len(present_values)
    combos = np.arange(2**count)
    switched_on = ((combos[:, None] >> np.arange(count)) & 1).astype(bool)
    scores = value_of(np.where(switched_on, present_values, np.nan))
    sizes = switched_on.sum(axis=1)
    # Weight of a combination of size s when one more input joins it.
    weights = np.array(
        [factorial(s) * factorial(count - s - 1) / factorial(count) for s in range(count)]
    )
    contributions = np.zeros(count)
    for position in range(count):
        without = combos[~switched_on[:, position]]
        joined = without | (1 << position)
        moves = scores[joined] - scores[without]
        contributions[position] = np.sum(weights[sizes[without]] * moves)
    return contributions, float(scores[0]), float(scores[-1])


def contributions_for_row(
    saved: dict[str, Any], feature_row: Any, config: dict[str, Any]
) -> dict[str, Any]:
    """Split one merchant's exact score into a baseline and one contribution per input.

    Args:
        saved: a saved model (`src.model.train.load_model`): pipeline, calibrator, features.
        feature_row: the merchant's row of the feature table (a Series or a dict).

    Returns `probability` (calibrated), `baseline_score`, `exact_score` (before rounding)
    and `points` (input name -> score points; zero for an input the merchant does not
    have). They always satisfy baseline_score + sum(points) = exact_score.
    """
    features = saved["features"]
    scale = config["score"]["scale"]
    values = np.array([_as_number(feature_row.get(name)) for name in features], dtype=float)
    present = np.flatnonzero(~np.isnan(values))
    limit = config["score"]["max_inputs_for_exact_reasons"]
    if len(present) > limit:
        raise ValueError(
            f"This merchant has {len(present)} inputs; exact reasons are computed for at "
            f"most {limit} (`score.max_inputs_for_exact_reasons`)."
        )

    def value_of(present_table: np.ndarray) -> np.ndarray:
        table = np.full((len(present_table), len(features)), np.nan)
        table[:, present] = present_table
        rows = pd.DataFrame(table, columns=features)
        return calibrated_probability(saved, rows)

    # Worked out in probabilities and turned into score points at the end, so the
    # probability returned is exactly the one every other part of the system computes.
    contributions, baseline, probability = _shapley(values[present], value_of)
    points = dict.fromkeys(features, 0.0)
    for position, index in enumerate(present):
        points[features[index]] = float(scale * contributions[position])
    return {
        "probability": probability,
        "baseline_score": scale * baseline,
        "exact_score": scale * probability,
        "points": points,
    }


def _as_number(value: Any) -> float:
    """A missing value in any form (None, NaN, pandas NA) becomes NaN."""
    return float("nan") if value is None or pd.isna(value) else float(value)


def explain_score(
    saved: dict[str, Any],
    feature_row: Any,
    config: dict[str, Any],
    dictionary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the score with its top reasons, as sentences whose parts sum to the score.

    Returns a dict with `probability`, `score`, `baseline_score`, `reasons_positive`,
    `reasons_negative` (each reason: code, sentence_en, sentence_bn, contribution, detail)
    and `other_contribution`. `points` holds every input's contribution, for logs and
    tests; it is never shown to an officer.
    """
    dictionary = dictionary or load_dictionary()
    # Each data mode has its own inputs and sentences; a saved model says which mode it is.
    entries = features_for_mode(dictionary, saved.get("data_mode"))
    settings = config["score"]
    parts = contributions_for_row(saved, feature_row, config)
    probability = parts["probability"]
    score = score_from_probability(probability, config)
    averages = average_inputs(saved)

    candidates = {True: [], False: []}  # True: raised the score; False: lowered it
    for name, points in parts["points"].items():
        if abs(points) < settings["min_reason_points"]:
            continue
        raised = points > 0
        entry = entries[name]
        value = _as_number(feature_row.get(name))
        sentences = reason_sentences(entry, raised, value)
        if sentences is None:
            continue
        candidates[raised].append(
            {
                "code": name,
                "sentence_en": sentences["en"],
                "sentence_bn": sentences["bn"],
                "contribution": round(points, 2),
                "detail": detail_text(entry, value, averages[name]),
            }
        )

    wanted = settings["top_reasons_each_side"]
    positive = sorted(candidates[True], key=lambda r: -r["contribution"])[:wanted]
    negative = sorted(candidates[False], key=lambda r: r["contribution"])[:wanted]
    baseline = round(parts["baseline_score"], 2)
    shown = sum(reason["contribution"] for reason in positive + negative)
    return {
        "probability": float(probability),
        "score": score,
        "baseline_score": baseline,
        "reasons_positive": positive,
        "reasons_negative": negative,
        "other_contribution": round(score - baseline - shown, 2),
        "points": parts["points"],
        "exact_baseline_score": parts["baseline_score"],
    }


class ConsentRequired(PermissionError):
    """Raised instead of a score when the merchant has no valid consent."""


class RowsNotShown(PermissionError):
    """Raised instead of a score card for a data mode whose rows may never be shown."""


def refuse_hidden_rows(config: dict[str, Any], mode: str) -> None:
    """Stop if the data mode's individual rows may not be shown (`data.rows_never_shown`)."""
    if mode in config["data"]["rows_never_shown"]:
        raise RowsNotShown(
            f"Rows of '{mode}' are never shown one by one (the source's terms allow totals "
            "only). See its model card instead."
        )


def score_card(
    saved: dict[str, Any],
    feature_row: pd.Series,
    config: dict[str, Any],
    mode: str | None = None,
    dictionary: dict[str, Any] | None = None,
    consent_valid: bool | None = None,
) -> dict[str, Any]:
    """Everything an officer sees for one merchant: score, coverage, band and reasons.

    A data mode listed in `data.rows_never_shown` (Home Credit) raises `RowsNotShown`:
    its individual rows may never appear on a screen, only totals.

    No valid consent, no score: `consent_valid` must be True, given either as the
    argument or as the `consent_valid` column of the row (rows from
    `src.model.dataset.build_dataset` have it). If it is False or not known, this raises
    `ConsentRequired` and computes nothing.

    The result has the fields of `ScoreResponse` in src/api/schemas.py except
    `merchant_id`, plus the banner sentence of the data mode. Nothing here approves or
    declines anything.
    """
    if consent_valid is None and "consent_valid" in feature_row.index:
        consent_valid = feature_row["consent_valid"]
    if consent_valid is None or pd.isna(consent_valid) or not bool(consent_valid):
        raise ConsentRequired(
            "This merchant has no valid consent on record, so no score is computed."
        )
    mode = mode or config["data"]["mode"]
    refuse_hidden_rows(config, mode)
    explanation = explain_score(saved, feature_row, config, dictionary)
    coverage = float(coverage_for_rows(feature_row.to_frame().T, config, mode).iloc[0])
    score = explanation["score"]
    return {
        "data_mode": mode,
        "model_version": saved["version_id"],
        "probability": explanation["probability"],
        "score": score,
        "coverage": coverage,
        "band": band_for(score, coverage, config, mode),
        "low_score_warning": low_score_warning(score, config, mode),
        "baseline_score": explanation["baseline_score"],
        "reasons_positive": explanation["reasons_positive"],
        "reasons_negative": explanation["reasons_negative"],
        "other_contribution": explanation["other_contribution"],
        "banner": banner_text(mode),
    }


def reasons_summary(
    saved: dict[str, Any], rows: pd.DataFrame, config: dict[str, Any]
) -> dict[str, Any]:
    """Check the reasons on a sample of loans and count how often each input is shown.

    Used by the training report. `largest_gap` is the biggest difference found between
    the parts and the whole, both for what is on the screen (baseline + reasons shown +
    all other inputs against the score) and for the exact numbers behind it. It must be
    zero up to rounding.
    """
    sample_size = min(config["score"]["reasons_report_sample"], len(rows))
    sample = rows.sample(n=sample_size, random_state=config["seed"])
    dictionary = load_dictionary()
    shown: dict[str, dict[str, int]] = {}
    largest_gap, without_reasons, others = 0.0, 0, []
    for _, row in sample.iterrows():
        explanation = explain_score(saved, row, config, dictionary)
        reasons = explanation["reasons_positive"] + explanation["reasons_negative"]
        on_screen = (
            explanation["baseline_score"]
            + sum(reason["contribution"] for reason in reasons)
            + explanation["other_contribution"]
        )
        exact = config["score"]["scale"] * explanation["probability"]
        all_parts = explanation["exact_baseline_score"] + sum(explanation["points"].values())
        largest_gap = max(
            largest_gap, abs(on_screen - explanation["score"]), abs(all_parts - exact)
        )
        without_reasons += not reasons
        others.append(abs(explanation["other_contribution"]))
        for side in ("positive", "negative"):
            for reason in explanation[f"reasons_{side}"]:
                counts = shown.setdefault(reason["code"], {"positive": 0, "negative": 0})
                counts[side] += 1
    return {
        "loans_checked": int(sample_size),
        "largest_gap": float(largest_gap),
        "loans_with_no_reason": int(without_reasons),
        "size_of_all_other_inputs": {
            "median": float(np.median(others)) if others else None,
            "nine_in_ten_below": float(np.quantile(others, 0.9)) if others else None,
            "largest": float(max(others)) if others else None,
        },
        "times_each_input_was_a_top_reason": shown,
    }
