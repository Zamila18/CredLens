"""Features for the public data modes: one small builder per source.

Purpose: the single place that knows which feature builder serves which public mode.
Owner role: B (data engineer).
Implements: docs/DATASET_PLAN.md section 3 and docs/MODEL_SPEC.md section 3 ("public modes
    use their own source-specific features").

The synthetic data has purchases, parcels and repayments, and `build_features.py` turns
those streams into features. A public data set has other fields (card statements, loan
applications), so each one has its own builder. Everything after the feature table is
shared: labels, split, training, calibration, score, coverage, bands and reasons.

How a public mode stays leak-free: its adapter hands over `source_records`, a table that
holds only the columns known at decision time (the source's whitelist). The outcome and
the group columns kept for the audit are not in it, so no builder can read them.
"""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from src.adapters.base import SOURCE_RECORDS  # noqa: F401  (re-exported for callers)
from src.features import homecredit, india_ltfs, kiva_asia, taiwan_cc

BUILDERS: dict[str, Callable[[pd.DataFrame, dict[str, Any]], pd.DataFrame]] = {
    taiwan_cc.MODE: taiwan_cc.taiwan_features,
    india_ltfs.MODE: india_ltfs.india_features,
    homecredit.MODE: homecredit.homecredit_features,
    kiva_asia.MODE: kiva_asia.kiva_features,
}
_SOURCES = (taiwan_cc, india_ltfs, homecredit, kiva_asia)
MODEL_INPUTS: dict[str, list[str]] = {source.MODE: source.MODEL_INPUTS for source in _SOURCES}
CONTEXT_COLUMNS: dict[str, list[str]] = {source.MODE: source.CONTEXT_COLUMNS for source in _SOURCES}
COVERAGE_COLUMNS: dict[str, list[str]] = {
    source.MODE: source.COVERAGE_COLUMNS for source in _SOURCES
}


def build_source_features(
    records: pd.DataFrame, config: dict[str, Any], mode: str
) -> pd.DataFrame:
    """Return the feature table of a public mode: one row per loan.

    Columns: loan_id, merchant_id, cutoff_date, then that mode's model inputs, context
    columns and coverage columns (`cov_<item>` for each item of its coverage weights).
    """
    if mode not in BUILDERS:
        raise ValueError(
            f"No feature builder for data mode {mode!r} yet. Built so far: {', '.join(BUILDERS)}."
        )
    return BUILDERS[mode](records, config)
