"""Split loans into train, validation and test periods.

Purpose: decide which loans the model learns from, which it is tuned on, and which are
    kept aside for the final report.
Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 4. The month counts come from the `split` and
    `split_by_mode` sections of config/default.yaml.

Two ways to split:
- By time (the rule): the first `train_months` of loans train the model, the next
  `validation_months` tune and calibrate it, the last `test_months` are touched once for
  the final report. A random split would let the model learn from loans issued after the
  ones it is tested on, which flatters the result.
- Stratified random (the exception): only for a data source with no usable dates
  (Taiwan, Home Credit). It keeps the share of good and bad loans equal in each part and
  is marked "weaker split" wherever results are shown.

Use `split_for_mode`: it picks the right method, start date and month counts for the
active data mode, so a caller cannot get them wrong by leaving an argument out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

TIME_SPLIT = "time"
RANDOM_SPLIT = "stratified_random"
WEAKER_SPLIT_NOTE = (
    "Weaker split: this data source has no usable dates, so loans were divided at random "
    "(keeping the same share of repaid loans in each part) instead of by time."
)
# Data modes whose rows carry no usable date (docs/MODEL_SPEC.md section 4: the only
# allowed exceptions to the time split).
RANDOM_SPLIT_MODES = ("taiwan_cc", "homecredit")
PART_NAMES = ("train", "validation", "test")


class EmptySplitError(ValueError):
    """Raised when a split would leave the training, validation or test part empty."""


@dataclass
class Split:
    """The three parts of a split, how it was made, and what was left out."""

    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame
    method: str
    note: str
    boundaries: dict[str, str]
    left_out: dict[str, int] = field(default_factory=dict)

    def sizes(self) -> dict[str, int]:
        """Number of rows in each part."""
        parts = {"train": self.train, "validation": self.validation, "test": self.test}
        return {name: len(frame) for name, frame in parts.items()}


def split_settings(config: dict[str, Any], mode: str | None = None) -> dict[str, Any]:
    """The month counts and start date for a data mode.

    A mode listed under `split_by_mode` uses its own month counts (for example India
    L&T, whose loans span three months). `synthetic_bd` starts on the generator's first
    day, so the periods match the 18-month window exactly; other modes start in the
    month of their first loan.
    """
    mode = mode or config["data"]["mode"]
    months = dict(config["split"])
    months.update((config.get("split_by_mode") or {}).get(mode, {}))
    start = config["generator"]["start_date"] if mode == "synthetic_bd" else None
    return {"months": months, "start": start}


def split_by_time(
    frame: pd.DataFrame,
    config: dict[str, Any],
    date_column: str = "cutoff_date",
    start: pd.Timestamp | str | None = None,
    months: dict[str, int] | None = None,
    allow_empty: bool = False,
) -> Split:
    """Split rows by date: first months train, next months validate, last months test.

    Args:
        frame: one row per loan, with a date column.
        config: the validated config.
        date_column: the loan's issue (cutoff) date.
        start: first day of the training period. Defaults to the first day of the month
            of the earliest loan.
        months: train/validation/test month counts. Defaults to the `split` section.
        allow_empty: accept a split with an empty part (for tests of the boundaries).

    Rows dated before the start or after the test period (for example pending loans in
    the observation tail) are in no part; `left_out` says how many of each.
    """
    months = months or config["split"]
    dates = pd.to_datetime(frame[date_column])
    first_day = pd.Timestamp(start) if start is not None else dates.min().to_period("M").start_time
    train_end = first_day + pd.DateOffset(months=months["train_months"])
    validation_end = train_end + pd.DateOffset(months=months["validation_months"])
    test_end = validation_end + pd.DateOffset(months=months["test_months"])

    def part(begin: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        return frame[(dates >= begin) & (dates < end)].copy()

    split = Split(
        train=part(first_day, train_end),
        validation=part(train_end, validation_end),
        test=part(validation_end, test_end),
        method=TIME_SPLIT,
        note="Split by loan issue date. Each period ends the day before the next begins.",
        boundaries={
            "train_from": str(first_day.date()),
            "validation_from": str(train_end.date()),
            "test_from": str(validation_end.date()),
            "test_until": str(test_end.date()),
        },
        left_out={
            "before_train_period": int((dates < first_day).sum()),
            "after_test_period": int((dates >= test_end).sum()),
            "no_date": int(dates.isna().sum()),
        },
    )
    if not allow_empty:
        _refuse_empty_parts(split, months)
    return split


def _refuse_empty_parts(split: Split, months: dict[str, int]) -> None:
    """Stop with a clear message when a part of the split has no loans."""
    sizes = split.sizes()
    empty = [name for name in PART_NAMES if sizes[name] == 0]
    if empty:
        raise EmptySplitError(
            f"The time split left no loans in: {', '.join(empty)}. Sizes: {sizes}. "
            f"Periods: {split.boundaries}. Month counts: {dict(months)}. If this data source "
            "covers less time than the split needs, give it its own month counts under "
            "`split_by_mode` in config/default.yaml."
        )


def split_stratified_random(
    frame: pd.DataFrame,
    config: dict[str, Any],
    label_column: str = "label",
    months: dict[str, int] | None = None,
) -> Split:
    """Split rows at random, keeping the share of each label equal in every part.

    Only for data sources with no usable dates. The parts have the same proportions as
    the month counts (12 : 3 : 3 by default). The seed comes from the config, so the
    same command gives the same split.
    """
    months = months or config["split"]
    total = months["train_months"] + months["validation_months"] + months["test_months"]
    train_share = months["train_months"] / total
    validation_share = months["validation_months"] / total

    # Work with row positions, so a repeated index label cannot confuse the assignment.
    rng = np.random.default_rng(config["seed"])
    labels = frame[label_column].to_numpy()
    part_of_row = np.full(len(frame), "test", dtype=object)
    for value in sorted(pd.unique(labels)):
        positions = rng.permutation(np.flatnonzero(labels == value))
        n_train = int(round(len(positions) * train_share))
        n_validation = int(round(len(positions) * validation_share))
        part_of_row[positions[:n_train]] = "train"
        part_of_row[positions[n_train : n_train + n_validation]] = "validation"

    return Split(
        train=frame[part_of_row == "train"].copy(),
        validation=frame[part_of_row == "validation"].copy(),
        test=frame[part_of_row == "test"].copy(),
        method=RANDOM_SPLIT,
        note=WEAKER_SPLIT_NOTE,
        boundaries={},
    )


def split_for_mode(
    frame: pd.DataFrame,
    config: dict[str, Any],
    mode: str | None = None,
    date_column: str = "cutoff_date",
    label_column: str = "label",
) -> Split:
    """Split the loans of a data mode the way that mode requires.

    Time split everywhere dates exist, with that mode's start date and month counts;
    stratified random split, marked weaker, for the modes without usable dates.
    """
    mode = mode or config["data"]["mode"]
    settings = split_settings(config, mode)
    if mode in RANDOM_SPLIT_MODES:
        return split_stratified_random(frame, config, label_column, settings["months"])
    return split_by_time(frame, config, date_column, settings["start"], settings["months"])
