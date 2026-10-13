"""Turn loans and payments into training labels.

Purpose: decide, for each loan, whether it was repaid in time (1), was not (0), or
    cannot be judged yet.
Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 2. Both numbers come from the `labels` section of
    config/default.yaml.

The rule:
- label 1: every payment that was due was made within `good_if_days_late_at_most` (30)
  days of its due date;
- label 0: a payment was made later than that, or is still unpaid more than that many
  days after its due date. A part payment does not count as paid: the amount paid must be
  at least 99% of the amount due (`paid_in_full_tolerance`);
- no label: the loan is younger than `min_loan_age_days` (60), or a payment is unpaid
  but not yet overdue by more than the limit. The outcome is unknown, so the loan is
  left out of training and testing. A young loan is never counted as a default.

Examples (docs/MODEL_SPEC.md): repaid 10 days late -> 1. Unpaid 60 days after the due
date -> 0. Issued 35 days ago -> excluded.

The labels are what the model learns from. They are never shown as a decision, and no
code approves or declines credit from them.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

LABELLED = "labelled"
TOO_YOUNG = "too_young"
NOT_YET_KNOWN = "not_yet_known"

LABEL_COLUMNS = ["loan_id", "merchant_id", "issued_at", "label", "label_status", "label_source"]


def latest_date(tables: dict[str, pd.DataFrame]) -> pd.Timestamp:
    """The last day anything happened in the data: "today" for judging loan outcomes."""
    candidates = [
        ("purchases", "purchase_date"),
        ("deliveries", "dispatched_at"),
        ("loans", "issued_at"),
        ("payments", "paid_date"),
    ]
    latest = [
        pd.to_datetime(tables[table][column]).max()
        for table, column in candidates
        if len(tables[table])
    ]
    return max(day for day in latest if pd.notna(day)).normalize()


def build_labels(
    loans: pd.DataFrame,
    payments: pd.DataFrame,
    config: dict[str, Any],
    as_of: pd.Timestamp | str,
    outcome_supplied: bool = False,
) -> pd.DataFrame:
    """Return one row per loan with its label and why it has (or lacks) one.

    Args:
        loans: the contract loans table.
        payments: the contract payments table. May be empty for a public data source
            that supplies outcomes directly.
        config: the validated config.
        as_of: "today" for the data. Loan age and overdue days are counted up to it.
        outcome_supplied: True for a public data source whose file states the outcome of
            every loan (the modes in `labels.supplied_by_source`). The label is then
            `outcome_label` as it is: payment records, if any, are history and not the
            repayment of this loan, and the "too young to judge" rule does not apply
            because the outcome is already known.

    Columns: loan_id, merchant_id, issued_at, label (1, 0 or empty), label_status
    (labelled / too_young / not_yet_known) and label_source ("payments" when the label
    was worked out from payment records, "source" when the data source supplied the
    outcome itself).
    """
    rules = config["labels"]
    limit = rules["good_if_days_late_at_most"]
    as_of = pd.Timestamp(as_of).normalize()

    result = loans[["loan_id", "merchant_id", "issued_at"]].copy()
    if outcome_supplied:
        supplied = pd.to_numeric(loans["outcome_label"], errors="coerce").astype("Int64")
        result["label"] = supplied.to_numpy()
        result["label_status"] = np.where(supplied.isna(), NOT_YET_KNOWN, LABELLED)
        result["label_source"] = "source"
        return result[LABEL_COLUMNS]
    age_days = (as_of - pd.to_datetime(result["issued_at"])).dt.days
    too_young = (age_days < rules["min_loan_age_days"]).to_numpy()

    # From payment records: how late was each payment, as far as is known today?
    due = pd.to_datetime(payments["due_date"])
    paid = pd.to_datetime(payments["paid_date"])
    # A payment counts only when (nearly) the full amount due was paid.
    enough = payments["amount_paid_bdt"].astype(float) >= (
        1 - rules["paid_in_full_tolerance"]
    ) * payments["amount_due_bdt"].astype(float)
    is_paid = paid.notna() & (paid <= as_of) & enough
    days_late = (paid - due).dt.days.where(is_paid, (as_of - due).dt.days)
    per_payment = pd.DataFrame(
        {
            "loan_id": payments["loan_id"].to_numpy(),
            "bad": (days_late > limit).to_numpy(),
            "settled": (is_paid & (days_late <= limit)).to_numpy(),
        }
    )
    by_loan = per_payment.groupby("loan_id").agg(
        any_bad=("bad", "any"), all_settled=("settled", "all")
    )
    by_loan = by_loan.reindex(result["loan_id"]).astype("boolean")
    has_payments = by_loan["any_bad"].notna().to_numpy()
    any_bad = by_loan["any_bad"].fillna(False).to_numpy(dtype=bool)
    all_settled = by_loan["all_settled"].fillna(False).to_numpy(dtype=bool)

    label = pd.Series(pd.NA, index=result.index, dtype="Int64")
    label[has_payments & any_bad] = 0
    label[has_payments & ~any_bad & all_settled] = 1
    source = pd.Series("payments", index=result.index).where(has_payments, "source")

    # A source without payment records supplies the outcome itself.
    supplied = pd.to_numeric(loans["outcome_label"], errors="coerce").astype("Int64")
    label = label.where(has_payments, supplied.to_numpy())

    label[too_young] = pd.NA
    status = pd.Series(LABELLED, index=result.index)
    status[label.isna().to_numpy()] = NOT_YET_KNOWN
    status[too_young] = TOO_YOUNG

    result["label"] = label
    result["label_status"] = status
    result["label_source"] = source
    return result[LABEL_COLUMNS]


def labelled_only(labels: pd.DataFrame) -> pd.DataFrame:
    """The loans that may be used for training and testing: those with a known outcome."""
    return labels[labels["label_status"] == LABELLED].copy()
