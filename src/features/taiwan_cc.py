"""Features for the `taiwan_cc` data mode (UCI credit-card clients, Taiwan, 2005).

Purpose: turn six months of card statements into behaviour features, one row per client.
Owner role: B (data engineer), with C for the model-facing columns.
Implements: docs/DATASET_PLAN.md sections 2 and 3; docs/FEATURE_DICTIONARY.md (source
    features); PROJECT_BRIEF section 18, item 29. Thresholds: `data.taiwan_cc` in
    config/default.yaml.

What the source gives, per client, for April to September 2005:
- a repayment status per month (`PAY_0` = September ... `PAY_6` = April):
    -2 = the card was not used, -1 = paid in full, 0 = the minimum was paid (revolving),
    1 to 8 = payment late by that many months (the UCI page documents -1 and 1 to 9; the
    meaning of -2 and 0 comes from the data set's author and is widely used);
- the bill amount per month (`BILL_AMT1` = September ... `BILL_AMT6` = April);
- the amount paid per month (`PAY_AMT1` = September ... `PAY_AMT6` = April);
- the credit limit (`LIMIT_BAL`). Amounts are in New Taiwan dollars.
The outcome is whether the client defaulted in October 2005, so everything above was
known before the decision. Nothing else may be used: see WHITELIST.

The same two rules as for the synthetic data:
- Model inputs describe HOW the client behaves (lateness, how much of the bill is paid,
  how much of the limit is used). The credit limit itself and the number of months with
  activity say how MUCH there is to go on: they are context and feed coverage, never the
  model.
- Empty is not zero. A client who never used the card has nothing to be late with, so
  their lateness features are empty (neutral for the model) and their coverage is low.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

MODE = "taiwan_cc"

# Newest month first, exactly as in the file (there is no PAY_1).
STATUS_COLUMNS = ["PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6"]
BILL_COLUMNS = [f"BILL_AMT{month}" for month in range(1, 7)]
PAID_COLUMNS = [f"PAY_AMT{month}" for month in range(1, 7)]
LIMIT_COLUMN = "LIMIT_BAL"

# The only source columns a feature may read. All were known at the end of September.
WHITELIST = [LIMIT_COLUMN, *STATUS_COLUMNS, *BILL_COLUMNS, *PAID_COLUMNS]
# Never model inputs: the outcome, the row id, and the group columns kept for the audit.
OUTCOME_COLUMN = "default payment next month"
AUDIT_SOURCE_COLUMNS = ["SEX", "EDUCATION", "MARRIAGE", "AGE"]
BLACKLIST = [OUTCOME_COLUMN, "ID", *AUDIT_SOURCE_COLUMNS]

MODEL_INPUTS = [
    "ontime_share_6m",
    "worst_delay_6m",
    "latest_delay_months",
    "delay_trend_6m",
    "pay_to_bill_ratio",
    "limit_utilisation",
    "balance_growth_6m",
    "no_payment_month_share",
]
CONTEXT_COLUMNS = ["credit_limit", "months_card_used", "months_with_bill"]
COVERAGE_COLUMNS = [
    "cov_credit_limit_present",
    "cov_repayment_status_history",
    "cov_bill_history",
    "cov_payment_history",
]
NOT_USED = -2  # status code: no consumption that month
DECISION_DATE = "2005-10-01"  # the outcome is default in October 2005


def _row_mean(values: np.ndarray, keep: np.ndarray) -> np.ndarray:
    """Mean of each row over the kept cells; empty when a row keeps none."""
    count = keep.sum(axis=1)
    total = np.where(keep, values, 0.0).sum(axis=1)
    return np.where(count > 0, total / np.maximum(count, 1), np.nan)


def taiwan_features(records: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Return one row per client: ids, model inputs, context and coverage columns.

    Args:
        records: the adapter's `source_records`: loan_id, merchant_id and the WHITELIST
            columns. Any other column is refused, so the outcome or a group column can
            never reach a feature by accident.
        config: the validated config.
    """
    unexpected = [c for c in records.columns if c not in ("loan_id", "merchant_id", *WHITELIST)]
    missing = [c for c in WHITELIST if c not in records.columns]
    if unexpected or missing:
        raise ValueError(
            f"taiwan_cc features may read only the whitelisted columns. "
            f"Unexpected: {unexpected or 'none'}. Missing: {missing or 'none'}."
        )
    settings = config["data"][MODE]

    status = records[STATUS_COLUMNS].to_numpy(dtype=float)  # newest month first
    bills = np.clip(records[BILL_COLUMNS].to_numpy(dtype=float), 0.0, None)  # credit balances -> 0
    paid = records[PAID_COLUMNS].to_numpy(dtype=float)
    limit = records[LIMIT_COLUMN].to_numpy(dtype=float)

    used = status > NOT_USED  # months in which something was due
    delay = np.clip(status, 0.0, None)  # months late; 0 for paid in full or minimum paid
    months_used = used.sum(axis=1)
    has_bill = bills > 0
    months_with_bill = has_bill.sum(axis=1)
    any_use = months_used > 0
    any_bill = months_with_bill > 0
    safe_limit = np.where(limit > 0, limit, np.nan)

    features = pd.DataFrame(index=records.index)
    features["loan_id"] = records["loan_id"].to_numpy()
    features["merchant_id"] = records["merchant_id"].to_numpy()
    features["cutoff_date"] = pd.Timestamp(DECISION_DATE)

    # --- lateness: only months in which the card was used count ---
    features["ontime_share_6m"] = _row_mean((delay == 0).astype(float), used)
    features["worst_delay_6m"] = np.where(any_use, np.where(used, delay, 0.0).max(axis=1), np.nan)
    features["latest_delay_months"] = np.where(used[:, 0], delay[:, 0], np.nan)
    # Mean delay of the three newest months minus that of the three oldest.
    features["delay_trend_6m"] = _row_mean(delay[:, :3], used[:, :3]) - _row_mean(
        delay[:, 3:], used[:, 3:]
    )

    # --- amounts ---
    # What is paid in a month goes towards the bill of the month before, so five pairs:
    # paid in May..September against the bills of April..August.
    earlier_bills, later_paid = bills[:, 1:], paid[:, :5]
    billed = earlier_bills.sum(axis=1)
    features["pay_to_bill_ratio"] = np.where(
        billed > 0, later_paid.sum(axis=1) / np.maximum(billed, 1.0), np.nan
    )
    features["limit_utilisation"] = np.where(any_bill, bills.mean(axis=1) / safe_limit, np.nan)
    features["balance_growth_6m"] = np.where(
        any_bill, (bills[:, 0] - bills[:, -1]) / safe_limit, np.nan
    )
    features["no_payment_month_share"] = _row_mean(
        (later_paid == 0).astype(float), earlier_bills > 0
    )

    # --- context: how much there is to go on. Never model inputs. ---
    features["credit_limit"] = limit
    features["months_card_used"] = months_used
    features["months_with_bill"] = months_with_bill

    # --- coverage checklist (weights: coverage_weights_by_mode.taiwan_cc) ---
    enough = settings["coverage_min_months"]
    features["cov_credit_limit_present"] = limit > 0
    features["cov_repayment_status_history"] = months_used >= enough
    features["cov_bill_history"] = months_with_bill >= enough
    features["cov_payment_history"] = (paid > 0).any(axis=1)

    return features.reset_index(drop=True)
