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

Model inputs and context columns. Every group produces two kinds of columns:
- model inputs describe HOW a merchant behaves (growth, supplier loyalty, lateness, return
  rates). They are the only columns a model may use.
- context columns describe HOW MUCH data there is (number of purchases, total value,
  share of active weeks, number of parcels). They are shown on the profile and feed the
  coverage checklist, but they are not model inputs.
Why: a thin-file merchant has few purchases and parcels by definition. A model that used
those amounts scored thin-file merchants about three points lower although they repaid
just as well (measured on validation data, Oct 13). A thin file must lower coverage, not
the score (PROJECT_BRIEF section 2 and the model card limits).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

# Model inputs per group: how the merchant behaves.
PURCHASE_FEATURES = ["basket_growth", "supplier_repeat_share"]
PAYMENT_FEATURES = [
    "avg_pay_delay_days",
    "late_pay_count_90d",
    "ontime_payment_rate",
    "credit_utilisation",
]
DELIVERY_FEATURES = [
    "delivered_rate",
    "return_rate_90d",
    "failed_rate_90d",
    "cod_remit_ontime_rate",
    "dispatch_to_delivery_hours",
]
FEATURE_GROUPS: dict[str, list[str]] = {
    "A": PURCHASE_FEATURES,
    "B": PAYMENT_FEATURES,
    "C": DELIVERY_FEATURES,
}

# Context columns per group: how much data there is. Shown to the officer and used for
# coverage. Never model inputs, so a thin file cannot lower the score.
PURCHASE_CONTEXT = [
    "purchases_90d",
    "purchase_value_90d",
    "purchase_volatility",
    "purchase_regularity",
    "category_diversity",
]
DELIVERY_CONTEXT = ["parcel_volume_90d", "delivery_data_thin"]
CONTEXT_COLUMNS = PURCHASE_CONTEXT + DELIVERY_CONTEXT

# Coverage columns describe how much history a score rests on. They are never model
# inputs and never appear as reasons for a score.
COVERAGE_COUNTS = [
    "history_months",
    "n_purchases_total",
    "n_deliveries_total",
    "n_payments_total",
    "share_of_groups_present",
]
# One yes/no column per item of `coverage_weights` in the config, prefixed "cov_".
CHECKLIST_PREFIX = "cov_"
CHECKLIST_ITEMS = [
    "history_6_months",
    "purchases_present",
    "payments_present",
    "deliveries_present",
    "questionnaire_done",
    "recent_activity_30d",
]
CHECKLIST_COLUMNS = [CHECKLIST_PREFIX + item for item in CHECKLIST_ITEMS]
COVERAGE_COLUMNS = COVERAGE_COUNTS + CHECKLIST_COLUMNS

# Return reasons that are logistics problems, not the merchant's doing.
LOGISTICS_RETURN_REASONS = ("address_issue", "rider_issue")

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
    """Group A: what the merchant bought before the cutoff. Indexed by loan_id.

    Returns the model inputs (PURCHASE_FEATURES) and the context columns
    (PURCHASE_CONTEXT).
    """
    settings = config["features"]
    window = settings["window_days"]
    n_weeks = settings["weekly_window_weeks"]

    purchases = purchases.copy()
    purchases["amount_bdt"] = purchases["amount_bdt"].astype(float)

    history = events_before_cutoff(cutoffs, purchases, "purchase_date", max_age_days=2 * window)
    recent = history[history["age_days"] <= window]
    previous = history[history["age_days"] > window]

    by_loan = recent.groupby("loan_id")
    features = pd.DataFrame(index=pd.Index(cutoffs["loan_id"], name="loan_id"))
    features["purchases_90d"] = by_loan.size()
    features["purchase_value_90d"] = by_loan["amount_bdt"].sum()
    features["category_diversity"] = by_loan["category"].nunique()

    # Supplier loyalty: take two of the merchant's recent purchases at random. How likely
    # is it that both came from the same supplier? Counting pairs this way gives the same
    # answer on average whether the merchant made 5 purchases or 50, so a merchant with
    # little history is not marked down for it. Needs at least two purchases.
    per_supplier = recent.groupby(["loan_id", "supplier_id"]).size()
    same_supplier_pairs = (per_supplier * (per_supplier - 1)).groupby("loan_id").sum()
    count = by_loan.size()
    all_pairs = (count * (count - 1)).where(count >= 2)
    features["supplier_repeat_share"] = same_supplier_pairs / all_pairs

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
    return features[PURCHASE_FEATURES + PURCHASE_CONTEXT]


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
    A part payment is not a repayment: the same rule as the labels (labels config,
    `paid_in_full_tolerance`).
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
    paid_in_full = _paid_in_full(history, config)
    paid_before = paid.notna() & (paid < cutoff) & paid_in_full
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


def delivery_features(
    cutoffs: pd.DataFrame, deliveries: pd.DataFrame, config: dict[str, Any]
) -> pd.DataFrame:
    """Group C: the merchant's outgoing parcels before the cutoff. Indexed by loan_id.

    Two things keep this honest:
    - A parcel's outcome is used only once it could be known. A parcel dispatched in the
      last few days (`delivery_settle_days`), or delivered on or after the cutoff, is
      still "in transit" as far as the cutoff day is concerned: it counts towards the
      volume but not towards any rate.
    - Returns caused by address or rider problems are not counted against the merchant
      in `return_rate_90d`.

    A merchant with no parcels in the window has no delivery features at all (empty,
    not zero). Missing delivery data lowers coverage; it must never lower the score.

    Returns the model inputs (DELIVERY_FEATURES) and the context columns
    (DELIVERY_CONTEXT: the number of parcels and the "history is thin" flag).
    """
    settings = config["features"]
    parcels = events_before_cutoff(
        cutoffs, deliveries, "dispatched_at", max_age_days=settings["window_days"]
    )
    parcels = parcels[parcels["status"] != "cancelled"]

    dispatched = pd.to_datetime(parcels["dispatched_at"])
    arrived = pd.to_datetime(parcels["delivered_at"])
    delivered = parcels["status"] == "delivered"
    outcome_known = (parcels["age_days"] > settings["delivery_settle_days"]) & (
        ~delivered | (arrived < parcels["cutoff_date"])
    )
    merchant_return = (parcels["status"] == "returned") & ~parcels["return_reason"].isin(
        LOGISTICS_RETURN_REASONS
    )
    parcels = parcels.assign(
        delivered=delivered,
        merchant_return=merchant_return,
        failed=parcels["status"] == "failed",
        hours=(arrived - dispatched).dt.total_seconds() / 3600.0,
        cod_on_time=parcels["cod_remitted_on_time"].astype("float"),
    )
    settled = parcels[outcome_known]
    settled_delivered = settled[settled["delivered"]]

    features = pd.DataFrame(index=pd.Index(cutoffs["loan_id"], name="loan_id"))
    features["parcel_volume_90d"] = parcels.groupby("loan_id").size()
    by_loan = settled.groupby("loan_id")
    features["delivered_rate"] = by_loan["delivered"].mean()
    features["return_rate_90d"] = by_loan["merchant_return"].mean()
    features["failed_rate_90d"] = by_loan["failed"].mean()
    features["cod_remit_ontime_rate"] = settled_delivered.groupby("loan_id")["cod_on_time"].mean()
    features["dispatch_to_delivery_hours"] = settled_delivered.groupby("loan_id")["hours"].median()

    thin = (features["parcel_volume_90d"] < settings["thin_delivery_parcels"]).astype(float)
    features["delivery_data_thin"] = thin.where(features["parcel_volume_90d"].notna())
    return features[DELIVERY_FEATURES + DELIVERY_CONTEXT]


def coverage_features(
    cutoffs: pd.DataFrame,
    tables: dict[str, pd.DataFrame],
    model_features: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    """How much history each score rests on, as known on the cutoff day. Indexed by loan_id.

    Two kinds of columns:
    - counts (history_months, n_purchases_total, ...), for display;
    - the coverage checklist: one yes/no column per item of `coverage_weights` in the
      config. Phase 5 turns the checklist into the coverage percentage and the band.

    Nothing here is a model input. Missing delivery data makes `cov_deliveries_present`
    False, which lowers coverage; it does not touch the score.
    """
    settings = config["features"]
    index = pd.Index(cutoffs["loan_id"], name="loan_id")
    days_known = cutoffs.set_index("loan_id")["days_known"]

    def count_before(events: pd.DataFrame, date_column: str, max_age_days: int | None = None):
        paired = events_before_cutoff(cutoffs, events, date_column, max_age_days)
        return paired, paired.groupby("loan_id").size().reindex(index).fillna(0)

    purchases, n_purchases = count_before(tables["purchases"], "purchase_date")
    parcels = tables["deliveries"]
    parcels, n_parcels = count_before(parcels[parcels["status"] != "cancelled"], "dispatched_at")
    answered = events_before_cutoff(cutoffs, tables["questionnaire"], "answered_at")

    coverage = pd.DataFrame(index=index)
    coverage["history_months"] = days_known / 30.44
    coverage["n_purchases_total"] = n_purchases
    coverage["n_deliveries_total"] = n_parcels
    # Earlier payments whose status was known on the cutoff day (see payment_features).
    has_payments = model_features["avg_pay_delay_days"].notna()
    known_payments = _known_payment_counts(
        cutoffs, tables["loans"], tables["payments"], config
    )
    coverage["n_payments_total"] = known_payments.reindex(index).fillna(0)

    has_purchases = model_features["purchases_90d"] > 0
    has_parcels = model_features["parcel_volume_90d"].notna()
    present = pd.concat([has_purchases, has_payments, has_parcels], axis=1)
    coverage["share_of_groups_present"] = present.mean(axis=1)

    # Purchases "present for most months": more than half of the recent 30-day blocks
    # the merchant has existed for contain a purchase.
    blocks = settings["coverage_purchase_months"]
    recent = purchases[purchases["age_days"] <= 30 * blocks]
    block_number = (recent["age_days"] - 1) // 30
    active_blocks = (
        recent.assign(block=block_number).groupby("loan_id")["block"].nunique().reindex(index)
    ).fillna(0)
    blocks_known = np.minimum(np.ceil(days_known / 30), blocks).clip(lower=1)
    purchase_share = active_blocks / blocks_known

    activity = pd.concat([purchases[["loan_id", "age_days"]], parcels[["loan_id", "age_days"]]])
    is_recent = activity["age_days"] <= settings["recent_activity_days"]
    recently_active = activity.loc[is_recent, "loan_id"].unique()

    coverage["cov_history_6_months"] = days_known >= settings["coverage_history_days"]
    coverage["cov_purchases_present"] = purchase_share > settings["coverage_purchase_month_share"]
    coverage["cov_payments_present"] = has_payments
    coverage["cov_deliveries_present"] = has_parcels
    coverage["cov_questionnaire_done"] = index.isin(answered["loan_id"])
    coverage["cov_recent_activity_30d"] = index.isin(recently_active)
    return coverage[COVERAGE_COLUMNS]


def _paid_in_full(payments: pd.DataFrame, config: dict[str, Any]) -> pd.Series:
    """True where at least (nearly) the full amount due was paid."""
    tolerance = config["labels"]["paid_in_full_tolerance"]
    paid = payments["amount_paid_bdt"].astype(float)
    return paid >= (1 - tolerance) * payments["amount_due_bdt"].astype(float)


def _known_payment_counts(
    cutoffs: pd.DataFrame, loans: pd.DataFrame, payments: pd.DataFrame, config: dict[str, Any]
) -> pd.Series:
    """Number of earlier payments whose status was already known on the cutoff day."""
    earlier_loans = loans[["loan_id", "issued_at"]].rename(columns={"loan_id": "earlier_loan_id"})
    history = payments.rename(columns={"loan_id": "earlier_loan_id"}).merge(
        earlier_loans, on="earlier_loan_id", how="left"
    )
    history = events_before_cutoff(cutoffs, history, "issued_at")
    paid = pd.to_datetime(history["paid_date"])
    due = pd.to_datetime(history["due_date"])
    paid_before = paid.notna() & (paid < history["cutoff_date"]) & _paid_in_full(history, config)
    known = paid_before | (due < history["cutoff_date"])
    return history[known].groupby("loan_id").size()


def build_features(tables: dict[str, pd.DataFrame], config: dict[str, Any]) -> pd.DataFrame:
    """Return one row per loan with features built only from data before its cutoff.

    Columns: loan_id, merchant_id, cutoff_date, days_known, then the model inputs
    (FEATURE_GROUPS), the context columns (CONTEXT_COLUMNS) and the coverage columns
    (COVERAGE_COLUMNS). Only the model inputs may be given to a model.
    A feature that cannot be computed is left empty (NaN); it is never filled in
    silently (docs/MODEL_SPEC.md section 1).
    """
    cutoffs = loan_cutoffs(tables)
    parts = [
        purchase_features(cutoffs, tables["purchases"], config),
        payment_features(cutoffs, tables["loans"], tables["payments"], config),
        delivery_features(cutoffs, tables["deliveries"], config),
    ]
    model_features = pd.concat(parts, axis=1)
    coverage = coverage_features(cutoffs, tables, model_features, config)
    features = cutoffs.set_index("loan_id").join([model_features, coverage])
    return features.reset_index()


def model_feature_names(groups: str = "ABC") -> list[str]:
    """The model inputs for the given feature groups, for example "A" or "AB" or "ABC"."""
    return [name for group in groups for name in FEATURE_GROUPS[group]]
