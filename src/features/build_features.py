"""Build the features for each loan, using only data from before its cutoff date.

Purpose: turn the contract tables into one row per loan with the features described in
    docs/FEATURE_DICTIONARY.md.
Owner role: B (data engineer), with C for the model-facing columns.
Implements: PROJECT_BRIEF section 6 and docs/MODEL_SPEC.md section 3.

The one rule that matters most (no leakage): a loan's cutoff date is the day it was
issued. A feature for that loan may use an event only if the event happened strictly
before that day. An event on the cutoff day itself is not used. Every helper below goes
through `events_before_cutoff`, which applies that rule in one place, and
tests/test_leakage.py checks it.

All windows and thresholds come from the `features` section of config/default.yaml.

Feature groups (used later for the ablation: A, then A+B, then A+B+C):
    A  purchases   what the merchant buys (Mokam-style). Never sales.
    B  payments    how earlier credit was repaid (Baki-style)
    C  deliveries  outgoing parcels (REDX-style)
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

# Feature names per group, in the order of docs/FEATURE_DICTIONARY.md.
PURCHASE_FEATURES = [
    "purchases_90d",
    "purchase_value_90d",
    "basket_growth",
    "purchase_volatility",
    "purchase_regularity",
    "category_diversity",
    "supplier_repeat_share",
]
PAYMENT_FEATURES = [
    "avg_pay_delay_days",
    "late_pay_count_90d",
    "ontime_payment_rate",
    "credit_utilisation",
]
FEATURE_GROUPS: dict[str, list[str]] = {"A": PURCHASE_FEATURES, "B": PAYMENT_FEATURES}

KEY_COLUMNS = ["loan_id", "merchant_id", "cutoff_date"]


def loan_cutoffs(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per loan with its cutoff date (the issue date) and days since onboarding.

    Every loan is kept, including loans too young to have an outcome: those are the
    pending cases that still need a score.
    """
    loans = tables["loans"][["loan_id", "merchant_id", "issued_at"]].copy()
    loans["cutoff_date"] = pd.to_datetime(loans["issued_at"])
    merchants = tables["merchants"][["merchant_id", "onboarded_at"]]
    loans = loans.merge(merchants, on="merchant_id", how="left", validate="many_to_one")
    loans["days_known"] = (loans["cutoff_date"] - pd.to_datetime(loans["onboarded_at"])).dt.days
    return loans[[*KEY_COLUMNS, "days_known"]]


def events_before_cutoff(
    cutoffs: pd.DataFrame,
    events: pd.DataFrame,
    date_column: str,
    max_age_days: int | None = None,
) -> pd.DataFrame:
    """Pair each loan with its merchant's events dated strictly before the cutoff.

    This is the single place where the no-leakage rule is applied.

    Args:
        cutoffs: one row per loan with loan_id, merchant_id and cutoff_date.
        events: any event table with merchant_id and a date column.
        date_column: the column in `events` that says when the event happened.
        max_age_days: keep only events at most this many days old. None keeps all
            earlier events.

    Returns the paired rows with an extra `age_days` column: 1 means the day before
    the cutoff. An event on the cutoff day (age 0) or later is never returned.
    """
    paired = cutoffs[KEY_COLUMNS].merge(events, on="merchant_id", how="inner")
    event_day = pd.to_datetime(paired[date_column]).dt.normalize()
    paired["age_days"] = (paired["cutoff_date"] - event_day).dt.days
    keep = paired["age_days"] >= 1
    if max_age_days is not None:
        keep &= paired["age_days"] <= max_age_days
    return paired[keep]


def purchase_features(
    cutoffs: pd.DataFrame, purchases: pd.DataFrame, config: dict[str, Any]
) -> pd.DataFrame:
    """Group A: what the merchant bought before the cutoff. Indexed by loan_id."""
    settings = config["features"]
    window = settings["window_days"]
    n_weeks = settings["weekly_window_weeks"]

    # Was this supplier already used by this merchant in an earlier purchase? This looks
    # only backwards in time, so it is safe to compute once for the whole table.
    purchases = purchases.sort_values(["merchant_id", "purchase_date", "purchase_id"]).copy()
    purchases["amount_bdt"] = purchases["amount_bdt"].astype(float)
    purchases["supplier_seen_before"] = (
        purchases.groupby(["merchant_id", "supplier_id"]).cumcount() > 0
    )

    history = events_before_cutoff(cutoffs, purchases, "purchase_date", max_age_days=2 * window)
    recent = history[history["age_days"] <= window]
    previous = history[history["age_days"] > window]

    by_loan = recent.groupby("loan_id")
    features = pd.DataFrame(index=pd.Index(cutoffs["loan_id"], name="loan_id"))
    features["purchases_90d"] = by_loan.size()
    features["purchase_value_90d"] = by_loan["amount_bdt"].sum()
    features["category_diversity"] = by_loan["category"].nunique()
    features["supplier_repeat_share"] = by_loan["supplier_seen_before"].mean()

    # A merchant with no purchases in the window bought nothing: that is a real zero.
    for column in ("purchases_90d", "purchase_value_90d", "category_diversity"):
        features[column] = features[column].fillna(0)

    # Growth: value in the recent window against the window before it, in percent.
    # Unknown when there was nothing to compare with.
    previous_value = previous.groupby("loan_id")["amount_bdt"].sum().reindex(features.index)
    has_base = previous_value > 0
    features["basket_growth"] = np.where(
        has_base, 100.0 * (features["purchase_value_90d"] / previous_value - 1.0), np.nan
    )

    # Weekly statistics over the last whole weeks, limited to weeks the merchant existed.
    weeks_known = np.minimum(cutoffs.set_index("loan_id")["days_known"] // 7, n_weeks)
    weekly = recent[recent["age_days"] <= 7 * n_weeks].copy()
    weekly["week"] = (weekly["age_days"] - 1) // 7
    weekly_value = weekly.groupby(["loan_id", "week"])["amount_bdt"].sum()

    active_weeks = weekly_value.groupby("loan_id").size().reindex(features.index).fillna(0)
    features["purchase_regularity"] = np.where(
        weeks_known > 0, np.minimum(active_weeks / weeks_known.clip(lower=1), 1.0), np.nan
    )

    # Volatility: spread of weekly purchase value against its mean, counting the weeks
    # with no purchase as zero.
    total = weekly_value.groupby("loan_id").sum().reindex(features.index).fillna(0)
    total_squares = (weekly_value**2).groupby("loan_id").sum().reindex(features.index).fillna(0)
    weeks = weeks_known.clip(lower=1)
    mean = total / weeks
    variance = (total_squares / weeks - mean**2).clip(lower=0)
    features["purchase_volatility"] = np.where(
        (weeks_known >= 2) & (mean > 0), np.sqrt(variance) / mean.where(mean > 0), np.nan
    )
    return features[PURCHASE_FEATURES]


def payment_features(
    cutoffs: pd.DataFrame,
    loans: pd.DataFrame,
    payments: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    """Group B: how the merchant repaid earlier loans, as known on the cutoff day.

    Only loans issued before the cutoff count, so the loan being scored never describes
    itself. For each earlier payment, only what was already visible is used:
    - paid before the cutoff: the real number of days late (0 if early or on time);
    - not paid by the cutoff, and already due: late by the days since the due date so
      far. A payment made on or after the cutoff is treated as still unpaid, because on
      the cutoff day nobody could know it would arrive;
    - not paid and not yet due: nothing is known, so it is left out of the lateness
      features.
    A merchant with no earlier loans has no payment history: every feature is empty.
    Indexed by loan_id.
    """
    settings = config["features"]
    earlier_loans = loans[["loan_id", "issued_at", "limit_bdt"]].rename(
        columns={"loan_id": "earlier_loan_id"}
    )
    history = payments.rename(columns={"loan_id": "earlier_loan_id"}).merge(
        earlier_loans, on="earlier_loan_id", how="left", validate="many_to_one"
    )
    history = events_before_cutoff(cutoffs, history, "issued_at")

    due = pd.to_datetime(history["due_date"])
    paid = pd.to_datetime(history["paid_date"])
    cutoff = history["cutoff_date"]
    paid_before = paid.notna() & (paid < cutoff)
    already_due = due < cutoff

    days_late = np.where(
        paid_before, (paid - due).dt.days.clip(lower=0), (cutoff - due).dt.days
    ).astype(float)
    history = history.assign(
        days_late=days_late,
        known=paid_before | already_due,
        used_share=history["amount_due_bdt"] / history["limit_bdt"],
        # When the lateness became visible: the payment day, or the day before the cutoff.
        seen_days_ago=np.where(paid_before, (cutoff - paid).dt.days, 1),
    )

    features = pd.DataFrame(index=pd.Index(cutoffs["loan_id"], name="loan_id"))
    known = history[history["known"]]
    by_loan = known.groupby("loan_id")
    features["avg_pay_delay_days"] = by_loan["days_late"].mean()
    on_time = known["days_late"] <= settings["ontime_payment_days"]
    features["ontime_payment_rate"] = on_time.groupby(known["loan_id"]).mean()

    recent_late = known[
        (known["days_late"] > settings["late_payment_days"])
        & (known["seen_days_ago"] <= settings["window_days"])
    ]
    late_count = recent_late.groupby("loan_id").size().reindex(features.index).fillna(0)
    has_history = by_loan.size().reindex(features.index).fillna(0) > 0
    features["late_pay_count_90d"] = late_count.where(has_history)

    features["credit_utilisation"] = history.groupby("loan_id")["used_share"].mean()
    return features[PAYMENT_FEATURES]


def build_features(tables: dict[str, pd.DataFrame], config: dict[str, Any]) -> pd.DataFrame:
    """Return one row per loan with features built only from data before its cutoff.

    Columns: loan_id, merchant_id, cutoff_date, days_known, then every feature in
    FEATURE_GROUPS. A feature that cannot be computed is left empty (NaN); it is never
    filled in silently (docs/MODEL_SPEC.md section 1).
    """
    cutoffs = loan_cutoffs(tables)
    parts = [
        purchase_features(cutoffs, tables["purchases"], config),
        payment_features(cutoffs, tables["loans"], tables["payments"], config),
    ]
    features = cutoffs.set_index("loan_id").join(parts)
    return features.reset_index()
