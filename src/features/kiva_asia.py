"""Features for the `kiva_asia` data mode (Kiva loans to small businesses in Asia).

Purpose: turn a Kiva loan and its field partner's track record into features, one row
    per loan.
Owner role: B (data engineer), with C for the model-facing columns.
Implements: docs/DATASET_PLAN.md section 3; docs/FEATURE_DICTIONARY.md (source features);
    PROJECT_BRIEF section 18, item 32. Thresholds: `data.kiva` in config/default.yaml.

What Kiva knows when a loan is posted: the loan's terms, its sector, the country, and
which field partner (the local lender who gives and collects the loan) stands behind it.
It knows nothing about how this borrower paid anyone before. So this mode has no
borrower-behaviour inputs at all, and that is said plainly wherever its results appear.

The three inputs, in two groups:
- group L, the loan: how many months it runs.
- group P, the field partner: the share of the partner's earlier loans that had defaulted
  by the day this loan was posted, and whether the partner (not the lender) carries the
  loss if the borrower does not pay.
Group P is kept apart so a run can be reported with and without it. On Kiva most
defaults come from a few partners failing, so a partner input says more about the
partner than about the shop.

The partner's track record is worked out "as of" the posting day by the adapter: an
earlier loan counts only if its outcome was already known that day (see
src/adapters/kiva_asia.py). A partner with fewer than `partner_min_known_loans` such
loans has no track record yet: the input is empty and coverage is low.

What a feature may NOT read:
- the outcome and everything that happened after posting (funding, payments, dates paid);
- the loan's description. Kiva removes the description from loans that defaulted (in the
  2016 snapshot every defaulted Asian loan has none and 99.8% of repaid ones have one),
  so "has a description" is the outcome in disguise. It is not used even for coverage;
- borrower names, pictures and gender, and the country (group audit only).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

MODE = "kiva_asia"

# The only columns a feature may read. All were known on the day the loan was posted.
WHITELIST = [
    "posted_date",
    "loan_amount",
    "repayment_term",
    "sector",
    "activity",
    "partner_known_loans",
    "partner_known_defaults",
    "partner_covers_nonpayment",
]
OUTCOME_COLUMN = "status"
AUDIT_SOURCE_COLUMNS = ["borrower_gender", "country"]
# After-the-fact or outcome-revealing fields of the source. Never read.
LEAKY_COLUMNS = ["paid_date", "description_length", "funded_amount", "lender_count", "delinquent"]
BLACKLIST = [OUTCOME_COLUMN, "id", *AUDIT_SOURCE_COLUMNS, *LEAKY_COLUMNS]

MODEL_INPUTS = ["repayment_term_months", "partner_past_default_rate", "partner_covers_default"]
PARTNER_INPUTS = ["partner_past_default_rate", "partner_covers_default"]
CONTEXT_COLUMNS = ["loan_amount_usd", "partner_known_loans"]
COVERAGE_COLUMNS = [
    "cov_loan_terms_present",
    "cov_sector_activity_present",
    "cov_partner_track_record",
]


def kiva_features(records: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Return one row per loan: ids, model inputs, context and coverage columns.

    Args:
        records: the adapter's `source_records`: loan_id, merchant_id and the WHITELIST
            columns. Any other column is refused, so the outcome, the description or a
            group column can never reach a feature by accident.
        config: the validated config.
    """
    unexpected = [c for c in records.columns if c not in ("loan_id", "merchant_id", *WHITELIST)]
    missing = [c for c in WHITELIST if c not in records.columns]
    if unexpected or missing:
        raise ValueError(
            f"kiva_asia features may read only the whitelisted columns. "
            f"Unexpected: {unexpected or 'none'}. Missing: {missing or 'none'}."
        )
    settings = config["data"]["kiva"]

    known = records["partner_known_loans"].to_numpy(dtype=float)
    defaults = records["partner_known_defaults"].to_numpy(dtype=float)
    has_record = known >= settings["partner_min_known_loans"]
    term = records["repayment_term"].to_numpy(dtype=float)
    amount = records["loan_amount"].to_numpy(dtype=float)

    features = pd.DataFrame(index=records.index)
    features["loan_id"] = records["loan_id"].to_numpy()
    features["merchant_id"] = records["merchant_id"].to_numpy()
    features["cutoff_date"] = pd.to_datetime(records["posted_date"]).to_numpy()

    features["repayment_term_months"] = term
    features["partner_past_default_rate"] = np.where(
        has_record, defaults / np.maximum(known, 1.0), np.nan
    )
    features["partner_covers_default"] = records["partner_covers_nonpayment"].to_numpy(dtype=float)

    # --- context: how much there is to go on. Never model inputs. ---
    features["loan_amount_usd"] = amount
    features["partner_known_loans"] = known

    # --- coverage checklist (weights: coverage_weights_by_mode.kiva_asia) ---
    features["cov_loan_terms_present"] = np.isfinite(term) & (term > 0) & (amount > 0)
    features["cov_sector_activity_present"] = (
        records["sector"].notna() & records["activity"].notna()
    ).to_numpy()
    features["cov_partner_track_record"] = has_record

    return features.reset_index(drop=True)
