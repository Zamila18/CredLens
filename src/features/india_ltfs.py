"""Features for the `india_ltfs` data mode (L&T vehicle loans, India, 2018).

Purpose: turn a loan application and its credit-bureau summary into behaviour features,
    one row per loan.
Owner role: B (data engineer), with C for the model-facing columns.
Implements: docs/DATASET_PLAN.md section 3; docs/FEATURE_DICTIONARY.md (source features);
    PROJECT_BRIEF section 18, item 30. Thresholds: `data.india_ltfs` in config/default.yaml.

What the source gives, per loan, as of the day it was disbursed (August to October 2018):
- the loan: amount, price of the vehicle, loan-to-value;
- a credit-bureau summary "at the time of disbursement" (the file's own dictionary says
  so for every bureau column): score, number of earlier loans, how many are overdue, new
  and delinquent loans in the last six months, enquiries, length of credit history;
- who and where: date of birth, employment type, state, branch, dealer, employee.
The outcome is whether the first monthly instalment was missed.

About half the borrowers have no bureau record at all ("No Bureau History Available").
They are real thin files. The same two rules as everywhere:
- Model inputs describe HOW the borrower behaves. Whether a bureau record exists, how
  long the credit history is and how many loans there were say how MUCH there is to go
  on: they are context and feed coverage, never the model.
- Empty is not zero. A borrower with no bureau record has no "share of loans overdue":
  the bureau features are empty (neutral for the model), and coverage is low.

What a feature may NOT read: the outcome; date of birth, employment type and state (kept
for the group audit only); and the branch, dealer, manufacturer, pin code and employee
identifiers, which describe the lender's organisation, not the borrower.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

MODE = "india_ltfs"

LOAN_COLUMNS = ["disbursed_amount", "asset_cost", "ltv"]
BUREAU_COLUMNS = [
    "PERFORM_CNS.SCORE",
    "PERFORM_CNS.SCORE.DESCRIPTION",
    "PRI.NO.OF.ACCTS",
    "PRI.OVERDUE.ACCTS",
    "SEC.NO.OF.ACCTS",
    "SEC.OVERDUE.ACCTS",
    "NEW.ACCTS.IN.LAST.SIX.MONTHS",
    "DELINQUENT.ACCTS.IN.LAST.SIX.MONTHS",
    "AVERAGE.ACCT.AGE",
    "CREDIT.HISTORY.LENGTH",
    "NO.OF_INQUIRIES",
]
DATE_COLUMN = "DisbursalDate"
# The only source columns a feature may read. All were known on the day of disbursement.
WHITELIST = [DATE_COLUMN, *LOAN_COLUMNS, *BUREAU_COLUMNS]

OUTCOME_COLUMN = "loan_default"
AUDIT_SOURCE_COLUMNS = ["Date.of.Birth", "Employment.Type", "State_ID"]
ORGANISATION_COLUMNS = [
    "branch_id",
    "supplier_id",
    "manufacturer_id",
    "Current_pincode_ID",
    "Employee_code_ID",
]
BLACKLIST = [OUTCOME_COLUMN, "UniqueID", *AUDIT_SOURCE_COLUMNS, *ORGANISATION_COLUMNS]

MODEL_INPUTS = [
    "down_payment_share",
    "bureau_score",
    "overdue_account_share",
    "delinquent_accounts_6m",
    "new_accounts_6m",
    "loan_enquiries",
]
CONTEXT_COLUMNS = [
    "loan_amount",
    "asset_cost",
    "earlier_loans",
    "credit_history_months",
    "average_account_age_months",
]
COVERAGE_COLUMNS = [
    "cov_loan_terms_present",
    "cov_bureau_record_present",
    "cov_credit_history_long_enough",
    "cov_bureau_score_available",
]
NO_BUREAU_RECORD = "No Bureau History Available"
NOT_SCORED_PREFIX = "Not Scored"


def months_from_text(text: pd.Series) -> pd.Series:
    """Turn "1yrs 11mon" into 23. The file writes durations this way."""
    parts = text.astype(str).str.extract(r"(\d+)\s*yrs\s*(\d+)\s*mon")
    return 12 * pd.to_numeric(parts[0], errors="coerce") + pd.to_numeric(parts[1], errors="coerce")


def india_features(records: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Return one row per loan: ids, model inputs, context and coverage columns.

    Args:
        records: the adapter's `source_records`: loan_id, merchant_id and the WHITELIST
            columns. Any other column is refused, so the outcome, a group column or an
            organisation identifier can never reach a feature by accident.
        config: the validated config.
    """
    unexpected = [c for c in records.columns if c not in ("loan_id", "merchant_id", *WHITELIST)]
    missing = [c for c in WHITELIST if c not in records.columns]
    if unexpected or missing:
        raise ValueError(
            f"india_ltfs features may read only the whitelisted columns. "
            f"Unexpected: {unexpected or 'none'}. Missing: {missing or 'none'}."
        )
    settings = config["data"][MODE]

    description = records["PERFORM_CNS.SCORE.DESCRIPTION"].astype(str)
    has_record = (description != NO_BUREAU_RECORD).to_numpy()
    is_scored = has_record & ~description.str.startswith(NOT_SCORED_PREFIX).to_numpy()
    earlier = (records["PRI.NO.OF.ACCTS"] + records["SEC.NO.OF.ACCTS"]).to_numpy(dtype=float)
    overdue = (records["PRI.OVERDUE.ACCTS"] + records["SEC.OVERDUE.ACCTS"]).to_numpy(dtype=float)
    history_months = months_from_text(records["CREDIT.HISTORY.LENGTH"]).to_numpy(dtype=float)
    account_age_months = months_from_text(records["AVERAGE.ACCT.AGE"]).to_numpy(dtype=float)
    ltv = records["ltv"].to_numpy(dtype=float)

    def with_record(values: Any) -> np.ndarray:
        """A bureau figure, or empty for a borrower who has no bureau record."""
        return np.where(has_record, np.asarray(values, dtype=float), np.nan)

    features = pd.DataFrame(index=records.index)
    features["loan_id"] = records["loan_id"].to_numpy()
    features["merchant_id"] = records["merchant_id"].to_numpy()
    features["cutoff_date"] = pd.to_datetime(records[DATE_COLUMN]).to_numpy()

    # --- the loan itself: known for every borrower, thin file or not ---
    features["down_payment_share"] = 1.0 - ltv / 100.0  # the part of the price paid up front

    # --- bureau behaviour: empty without a bureau record ---
    features["bureau_score"] = np.where(
        is_scored, records["PERFORM_CNS.SCORE"].to_numpy(dtype=float), np.nan
    )
    features["overdue_account_share"] = np.where(
        has_record & (earlier > 0), overdue / np.maximum(earlier, 1.0), np.nan
    )
    features["delinquent_accounts_6m"] = with_record(records["DELINQUENT.ACCTS.IN.LAST.SIX.MONTHS"])
    features["new_accounts_6m"] = with_record(records["NEW.ACCTS.IN.LAST.SIX.MONTHS"])
    features["loan_enquiries"] = with_record(records["NO.OF_INQUIRIES"])

    # --- context: how much there is to go on. Never model inputs. ---
    features["loan_amount"] = records["disbursed_amount"].to_numpy(dtype=float)
    features["asset_cost"] = records["asset_cost"].to_numpy(dtype=float)
    features["earlier_loans"] = earlier
    features["credit_history_months"] = history_months
    features["average_account_age_months"] = account_age_months

    # --- coverage checklist (weights: coverage_weights_by_mode.india_ltfs) ---
    features["cov_loan_terms_present"] = np.isfinite(ltv) & (features["loan_amount"] > 0)
    features["cov_bureau_record_present"] = has_record
    features["cov_credit_history_long_enough"] = has_record & (
        history_months >= settings["coverage_min_history_months"]
    )
    features["cov_bureau_score_available"] = is_scored

    return features.reset_index(drop=True)
