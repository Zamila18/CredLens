"""Features for the `homecredit` data mode (Kaggle Home Credit Default Risk).

Purpose: turn an application and the applicant's earlier instalment history into
    behaviour features, one row per application.
Owner role: B (data engineer), with C for the model-facing columns.
Implements: docs/DATASET_PLAN.md section 3; docs/FEATURE_DICTIONARY.md (source features);
    PROJECT_BRIEF section 18, item 31. Thresholds: `data.homecredit` in config/default.yaml.

The country of this data is not stated by its publisher. Every screen and report says
"country not stated"; it adds scale and never supports a claim about Asia.

What the adapter hands over, per application (src/adapters/homecredit.py):
- from the application: income, loan amount, repayment amount, price of the goods, and up
  to three scores "from external data sources";
- from `installments_payments.csv`: counts over the applicant's EARLIER loans (how many
  instalments, how many on time, how many over 30 days late, how many paid short, the
  total days late; the same for the last year);
- from `POS_CASH_balance.csv`: how many monthly records of earlier store and cash loans
  there are, and in how many an amount was overdue.
Every history row in those files is dated before the application (the days are all
negative), and the adapter checks that. The outcome is whether the applicant had payment
difficulties on the new loan.

The same two rules as everywhere:
- Model inputs describe HOW the applicant behaves. How many earlier instalments there are
  says how MUCH there is to go on: context and coverage, never the model.
- Empty is not zero. An applicant with no earlier loans has no "share paid on time":
  those features are empty (neutral for the model), and coverage is low.

What a feature may NOT read: the outcome; gender, age and region rating (group audit
only); and the other descriptions of the person in the application (occupation, family,
housing, education, type of employer), which are not behaviour.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

MODE = "homecredit"

APPLICATION_COLUMNS = [
    "AMT_INCOME_TOTAL",
    "AMT_CREDIT",
    "AMT_ANNUITY",
    "AMT_GOODS_PRICE",
    "EXT_SOURCE_1",
    "EXT_SOURCE_2",
    "EXT_SOURCE_3",
]
# Counts the adapter works out from the two history files, per applicant.
HISTORY_COLUMNS = [
    "inst_count",
    "inst_ontime_count",
    "inst_late_count",
    "inst_short_count",
    "inst_days_late_sum",
    "inst_recent_count",
    "inst_recent_ontime_count",
    "pos_months",
    "pos_months_overdue",
]
# The only columns a feature may read. All describe the time before the application.
WHITELIST = [*APPLICATION_COLUMNS, *HISTORY_COLUMNS]

OUTCOME_COLUMN = "TARGET"
AUDIT_SOURCE_COLUMNS = ["CODE_GENDER", "DAYS_BIRTH", "REGION_RATING_CLIENT"]
BLACKLIST = [OUTCOME_COLUMN, "SK_ID_CURR", *AUDIT_SOURCE_COLUMNS]

MODEL_INPUTS = [
    "inst_ontime_rate",
    "inst_mean_days_late",
    "inst_late_30d_share",
    "inst_paid_short_share",
    "inst_recent_ontime_rate",
    "pos_months_overdue_share",
    "annuity_to_income",
    "credit_to_goods_ratio",
    "external_score",
]
# `external_score` comes from outside scoring sources, not from the applicant's own
# records. It is kept as its own group so a run can be reported with and without it.
EXTERNAL_INPUTS = ["external_score"]
CONTEXT_COLUMNS = ["loan_amount", "stated_income", "past_instalments", "pos_months_recorded"]
COVERAGE_COLUMNS = [
    "cov_application_data_present",
    "cov_instalment_history_present",
    "cov_enough_past_instalments",
    "cov_pos_cash_history_present",
]
EXTERNAL_SOURCES = ["EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3"]


def _share(part: np.ndarray, whole: np.ndarray) -> np.ndarray:
    """part / whole, empty where there is nothing to divide by."""
    return np.where(whole > 0, part / np.maximum(whole, 1.0), np.nan)


def homecredit_features(records: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Return one row per application: ids, model inputs, context and coverage columns.

    Args:
        records: the adapter's `source_records`: loan_id, merchant_id, cutoff_date and the
            WHITELIST columns. Any other column is refused, so the outcome or a group
            column can never reach a feature by accident.
        config: the validated config.
    """
    allowed = ("loan_id", "merchant_id", "cutoff_date", *WHITELIST)
    unexpected = [c for c in records.columns if c not in allowed]
    missing = [c for c in WHITELIST if c not in records.columns]
    if unexpected or missing:
        raise ValueError(
            f"homecredit features may read only the whitelisted columns. "
            f"Unexpected: {unexpected or 'none'}. Missing: {missing or 'none'}."
        )
    settings = config["data"][MODE]

    def number(column: str) -> np.ndarray:
        return records[column].to_numpy(dtype=float)

    instalments = np.nan_to_num(number("inst_count"))
    recent = np.nan_to_num(number("inst_recent_count"))
    pos_months = np.nan_to_num(number("pos_months"))
    income, credit = number("AMT_INCOME_TOTAL"), number("AMT_CREDIT")
    annuity, goods = number("AMT_ANNUITY"), number("AMT_GOODS_PRICE")

    features = pd.DataFrame(index=records.index)
    features["loan_id"] = records["loan_id"].to_numpy()
    features["merchant_id"] = records["merchant_id"].to_numpy()
    features["cutoff_date"] = pd.to_datetime(records["cutoff_date"]).to_numpy()

    def count(column: str) -> np.ndarray:
        """A history count; an applicant with no history has none, which counts as 0."""
        return np.nan_to_num(number(column))

    # --- how earlier instalments were paid: empty without earlier loans ---
    features["inst_ontime_rate"] = _share(count("inst_ontime_count"), instalments)
    features["inst_mean_days_late"] = _share(count("inst_days_late_sum"), instalments)
    features["inst_late_30d_share"] = _share(count("inst_late_count"), instalments)
    features["inst_paid_short_share"] = _share(count("inst_short_count"), instalments)
    features["inst_recent_ontime_rate"] = _share(count("inst_recent_ontime_count"), recent)
    features["pos_months_overdue_share"] = _share(count("pos_months_overdue"), pos_months)

    # --- the loan asked for: known for every applicant ---
    features["annuity_to_income"] = _share(annuity, income)
    features["credit_to_goods_ratio"] = _share(credit, goods)

    # --- outside scores: the average of those the file has; empty when it has none ---
    scores = records[EXTERNAL_SOURCES].to_numpy(dtype=float)
    known = ~np.isnan(scores)
    features["external_score"] = _share(np.where(known, scores, 0.0).sum(axis=1), known.sum(axis=1))

    # --- context: how much there is to go on. Never model inputs. ---
    features["loan_amount"] = credit
    features["stated_income"] = income
    features["past_instalments"] = instalments
    features["pos_months_recorded"] = pos_months

    # --- coverage checklist (weights: coverage_weights_by_mode.homecredit) ---
    features["cov_application_data_present"] = (income > 0) & (annuity > 0) & (credit > 0)
    features["cov_instalment_history_present"] = instalments > 0
    features["cov_enough_past_instalments"] = instalments >= settings["coverage_min_instalments"]
    features["cov_pos_cash_history_present"] = pos_months > 0

    return features.reset_index(drop=True)
