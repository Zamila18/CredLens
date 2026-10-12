"""Tests for the feature builder (src/features/build_features.py).

Owner role: B (data engineer).
Implements: PROJECT_BRIEF section 6, docs/MODEL_SPEC.md section 3, docs/FEATURE_DICTIONARY.md.

Most tests use tiny hand-made tables where the right answer can be worked out by hand.
"""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

from src.adapters import CONTRACT, empty_frame
from src.config import load_config
from src.features.build_features import (
    DELIVERY_FEATURES,
    FEATURE_GROUPS,
    PAYMENT_FEATURES,
    PURCHASE_FEATURES,
    build_features,
    events_before_cutoff,
    loan_cutoffs,
)
from src.features.dictionary import load_dictionary
from src.synth.generate import build_tables

CUTOFF = "2025-07-01"


def make_tables(**frames: list[dict]) -> dict[str, pd.DataFrame]:
    """Contract tables from short lists of rows; tables not given are empty."""
    tables = {name: empty_frame(name) for name in CONTRACT}
    for name, rows in frames.items():
        tables[name] = pd.DataFrame(rows).reindex(columns=CONTRACT[name])
    return tables


def merchant(merchant_id: str, onboarded_at: str) -> dict:
    return {"merchant_id": merchant_id, "onboarded_at": onboarded_at}


def loan(loan_id: str, merchant_id: str, issued_at: str = CUTOFF) -> dict:
    return {"loan_id": loan_id, "merchant_id": merchant_id, "issued_at": issued_at}


def purchase(number: int, merchant_id: str, day: str, amount: float, category: str, supplier: str):
    return {
        "purchase_id": f"PU{number}",
        "merchant_id": merchant_id,
        "purchase_date": day,
        "amount_bdt": amount,
        "category": category,
        "supplier_id": supplier,
    }


@pytest.fixture(scope="module")
def config() -> dict:
    return load_config()


@pytest.fixture(scope="module")
def worked_example(config) -> pd.DataFrame:
    """Three merchants, each with one loan issued on 2025-07-01.

    M1 has a full purchase history, M2 has bought nothing, M3 joined three days earlier.
    """
    tables = make_tables(
        merchants=[
            merchant("M1", "2025-01-01"),
            merchant("M2", "2025-01-01"),
            merchant("M3", "2025-06-28"),
        ],
        loans=[loan("L1", "M1"), loan("L2", "M2"), loan("L3", "M3")],
        purchases=[
            purchase(1, "M1", "2025-03-01", 4000, "c", "S1"),  # 122 days before: previous window
            purchase(2, "M1", "2025-04-01", 700, "a", "S1"),  # 91 days before: previous window
            purchase(3, "M1", "2025-04-02", 500, "a", "S3"),  # 90 days before: recent window
            purchase(4, "M1", "2025-05-01", 3000, "a", "S2"),  # 61 days before
            purchase(5, "M1", "2025-06-20", 2000, "b", "S1"),  # 11 days before
            purchase(6, "M1", "2025-06-30", 1000, "a", "S1"),  # the day before the cutoff
            purchase(7, "M1", "2025-07-01", 9999, "z", "S9"),  # on the cutoff day: not used
            purchase(8, "M1", "2025-07-05", 9999, "z", "S9"),  # after the cutoff: not used
            purchase(9, "M3", "2025-06-29", 800, "a", "S1"),
        ],
    )
    return build_features(tables, config).set_index("loan_id")


# --- the no-leakage helper -----------------------------------------------------------


def test_events_on_or_after_the_cutoff_are_never_returned():
    cutoffs = pd.DataFrame(
        {"loan_id": ["L1"], "merchant_id": ["M1"], "cutoff_date": [pd.Timestamp(CUTOFF)]}
    )
    events = pd.DataFrame(
        {
            "merchant_id": ["M1"] * 4 + ["M2"],
            "when": ["2025-06-30", "2025-07-01", "2025-07-02", "2025-01-01", "2025-06-30"],
        }
    )
    paired = events_before_cutoff(cutoffs, events, "when")
    assert sorted(paired["when"]) == ["2025-01-01", "2025-06-30"]
    assert paired["age_days"].min() == 1

    recent = events_before_cutoff(cutoffs, events, "when", max_age_days=90)
    assert list(recent["when"]) == ["2025-06-30"]


def test_a_timestamp_late_on_the_day_before_still_counts_as_before():
    cutoffs = pd.DataFrame(
        {"loan_id": ["L1"], "merchant_id": ["M1"], "cutoff_date": [pd.Timestamp(CUTOFF)]}
    )
    events = pd.DataFrame(
        {"merchant_id": ["M1", "M1"], "when": ["2025-06-30T23:59:59", "2025-07-01T00:00:01"]}
    )
    paired = events_before_cutoff(cutoffs, events, "when")
    assert list(paired["when"]) == ["2025-06-30T23:59:59"]


def test_every_loan_gets_a_cutoff_including_pending_ones():
    tables = make_tables(
        merchants=[merchant("M1", "2025-01-01")],
        loans=[loan("L1", "M1", "2025-03-01"), loan("L2", "M1", "2025-07-01")],
    )
    cutoffs = loan_cutoffs(tables)
    assert list(cutoffs["loan_id"]) == ["L1", "L2"]
    assert list(cutoffs["days_known"]) == [59, 181]


# --- group A: purchases --------------------------------------------------------------


def test_purchase_counts_and_value_use_only_the_recent_window(worked_example):
    row = worked_example.loc["L1"]
    assert row["purchases_90d"] == 4
    assert row["purchase_value_90d"] == 6500
    assert row["category_diversity"] == 2


def test_basket_growth_compares_with_the_window_before(worked_example):
    # recent 6500 against previous 4700 (4000 + 700)
    assert worked_example.loc["L1", "basket_growth"] == pytest.approx(100 * (6500 / 4700 - 1))


def test_supplier_repeat_share_counts_suppliers_used_earlier(worked_example):
    # recent purchases: S3 (new), S2 (new), S1 (used before), S1 (used before)
    assert worked_example.loc["L1", "supplier_repeat_share"] == pytest.approx(0.5)


def test_purchase_regularity_is_the_share_of_weeks_with_a_purchase(worked_example):
    # three of the last twelve weeks have a purchase
    assert worked_example.loc["L1", "purchase_regularity"] == pytest.approx(3 / 12)


def test_purchase_volatility_counts_empty_weeks_as_zero(worked_example):
    weekly = np.array([1000, 2000, 3000] + [0] * 9, dtype=float)
    expected = weekly.std() / weekly.mean()
    assert worked_example.loc["L1", "purchase_volatility"] == pytest.approx(expected)


def test_a_merchant_with_no_purchases_gets_zeros_and_empty_ratios(worked_example):
    row = worked_example.loc["L2"]
    assert row["purchases_90d"] == 0
    assert row["purchase_value_90d"] == 0
    assert row["category_diversity"] == 0
    assert row["purchase_regularity"] == 0
    for ratio in ("basket_growth", "supplier_repeat_share", "purchase_volatility"):
        assert np.isnan(row[ratio]), ratio


def test_a_merchant_known_for_days_has_no_weekly_statistics(worked_example):
    row = worked_example.loc["L3"]
    assert row["days_known"] == 3
    assert row["purchases_90d"] == 1
    assert np.isnan(row["purchase_regularity"])
    assert np.isnan(row["purchase_volatility"])
    assert np.isnan(row["basket_growth"])


def test_purchase_features_are_never_filled_in_silently(worked_example):
    """Ratios that cannot be computed stay empty; counts are real zeros."""
    assert worked_example[["purchases_90d", "purchase_value_90d"]].notna().all().all()
    assert worked_example["basket_growth"].isna().sum() == 2


# --- group B: payments ---------------------------------------------------------------


def earlier_loan(
    loan_id: str,
    merchant_id: str,
    issued: str,
    limit: float,
    due: str,
    paid: str | None,
    used: float,
) -> tuple[dict, dict]:
    """A loan and its single payment, as two contract rows."""
    loan_row = {
        "loan_id": loan_id,
        "merchant_id": merchant_id,
        "issued_at": issued,
        "limit_bdt": limit,
    }
    payment_row = {
        "payment_id": f"P-{loan_id}",
        "merchant_id": merchant_id,
        "loan_id": loan_id,
        "due_date": due,
        "paid_date": paid,
        "amount_due_bdt": used,
        "amount_paid_bdt": used if paid else 0.0,
    }
    return loan_row, payment_row


@pytest.fixture(scope="module")
def payment_example(config) -> pd.DataFrame:
    """Four merchants whose current loan is issued on 2025-07-01.

    M1: one earlier loan paid on time, one paid 10 days late, one not yet due.
    M2: one earlier loan, due a month ago and still unpaid.
    M3: one earlier loan, due 10 days ago, paid only AFTER the cutoff.
    M4: no earlier loans.
    """
    history = [
        earlier_loan("LA", "M1", "2025-02-01", 10000, "2025-03-03", "2025-03-03", 5000),
        earlier_loan("LB", "M1", "2025-04-01", 20000, "2025-05-01", "2025-05-11", 15000),
        earlier_loan("LC", "M1", "2025-06-10", 10000, "2025-07-10", None, 4000),
        earlier_loan("LE", "M2", "2025-05-01", 10000, "2025-05-31", None, 9000),
        earlier_loan("LF", "M3", "2025-05-22", 10000, "2025-06-21", "2025-07-15", 6000),
    ]
    current = [
        earlier_loan(f"NOW{n}", f"M{n}", CUTOFF, 30000, "2025-07-31", "2025-07-31", 30000)
        for n in (1, 2, 3, 4)
    ]
    rows = history + current
    tables = make_tables(
        merchants=[merchant(f"M{n}", "2025-01-01") for n in (1, 2, 3, 4)],
        loans=[loan_row for loan_row, _ in rows],
        payments=[payment_row for _, payment_row in rows],
    )
    return build_features(tables, config).set_index("loan_id")


def test_payment_delay_and_on_time_rate_use_earlier_loans_only(payment_example):
    row = payment_example.loc["NOW1"]
    # LA was on time (0 days), LB was 10 days late; LC is not due yet, so it says nothing.
    assert row["avg_pay_delay_days"] == pytest.approx(5.0)
    assert row["ontime_payment_rate"] == pytest.approx(0.5)


def test_late_payment_count_looks_at_the_recent_window(payment_example):
    # LB's late payment was made 51 days before the cutoff; LA's on-time one does not count.
    assert payment_example.loc["NOW1", "late_pay_count_90d"] == 1


def test_credit_utilisation_averages_earlier_loans(payment_example):
    # 5000/10000, 15000/20000 and 4000/10000; the loan being scored is not included.
    expected = np.mean([0.5, 0.75, 0.4])
    assert payment_example.loc["NOW1", "credit_utilisation"] == pytest.approx(expected)


def test_an_unpaid_overdue_loan_is_late_by_the_days_so_far(payment_example):
    row = payment_example.loc["NOW2"]
    assert row["avg_pay_delay_days"] == 31  # due 2025-05-31, cutoff 2025-07-01
    assert row["ontime_payment_rate"] == 0
    assert row["late_pay_count_90d"] == 1


def test_a_payment_made_after_the_cutoff_is_not_known_yet(payment_example):
    """LF was paid on 2025-07-15. On the cutoff day it was simply 10 days overdue."""
    row = payment_example.loc["NOW3"]
    assert row["avg_pay_delay_days"] == 10  # not 24, the lateness only known later
    assert row["late_pay_count_90d"] == 1


def test_the_loan_being_scored_never_describes_itself(payment_example):
    """Each NOW loan was repaid on time, yet that must not appear in its own features."""
    assert payment_example.loc["NOW2", "ontime_payment_rate"] == 0
    assert payment_example.loc["NOW1", "credit_utilisation"] < 1.0


def test_no_earlier_loans_means_no_payment_features(payment_example):
    row = payment_example.loc["NOW4"]
    for name in PAYMENT_FEATURES:
        assert np.isnan(row[name]), name


def test_a_first_loan_has_no_payment_history(payment_example):
    for first_loan in ("LA", "LE", "LF"):
        assert payment_example.loc[first_loan, PAYMENT_FEATURES].isna().all(), first_loan


# --- group C: deliveries -------------------------------------------------------------


def parcel(
    number: int,
    dispatched: str,
    status: str,
    arrived: str | None = None,
    reason: str | None = None,
    cod: bool = False,
    remitted: bool | None = None,
    merchant_id: str = "M1",
) -> dict:
    return {
        "delivery_id": f"D{number}",
        "merchant_id": merchant_id,
        "dispatched_at": dispatched,
        "delivered_at": arrived,
        "status": status,
        "return_reason": reason,
        "is_cod": cod,
        "cod_remitted_on_time": remitted,
    }


@pytest.fixture(scope="module")
def delivery_example(config) -> pd.DataFrame:
    """M1 sends parcels before a loan issued on 2025-07-01; M2 sends none."""
    parcels = [
        parcel(1, "2025-06-01T10:00:00", "delivered", "2025-06-02T10:00:00", None, True, True),
        parcel(2, "2025-06-05T10:00:00", "delivered", "2025-06-07T10:00:00", None, True, False),
        parcel(3, "2025-06-10T10:00:00", "returned", None, "refused"),
        parcel(4, "2025-06-12T10:00:00", "returned", None, "address_issue"),
        parcel(5, "2025-06-15T10:00:00", "failed", None, "rider_issue"),
        parcel(6, "2025-06-18T10:00:00", "delivered", "2025-06-19T22:00:00"),
        parcel(7, "2025-06-20T10:00:00", "cancelled"),
        # Dispatched two days before the cutoff: too recent for its outcome to be known.
        parcel(8, "2025-06-29T10:00:00", "delivered", "2025-06-30T10:00:00", None, True, True),
        # Delivered only after the cutoff: still in transit on the cutoff day.
        parcel(9, "2025-06-25T10:00:00", "delivered", "2025-07-02T10:00:00", None, True, True),
        parcel(10, "2025-07-01T09:00:00", "returned", None, "refused"),  # on the cutoff day
        parcel(11, "2025-03-01T10:00:00", "returned", None, "refused"),  # outside the window
    ]
    tables = make_tables(
        merchants=[merchant("M1", "2025-01-01"), merchant("M2", "2025-01-01")],
        loans=[loan("L1", "M1"), loan("L2", "M2")],
        deliveries=parcels,
    )
    return build_features(tables, config).set_index("loan_id")


def test_parcel_volume_counts_dispatched_parcels_in_the_window(delivery_example):
    # parcels 1-6, 8 and 9. Not the cancelled one, the cutoff-day one or the old one.
    assert delivery_example.loc["L1", "parcel_volume_90d"] == 8


def test_delivery_rates_use_only_parcels_whose_outcome_was_known(delivery_example):
    # Settled parcels: 1, 2, 3, 4, 5, 6. Three delivered, two returned, one failed.
    row = delivery_example.loc["L1"]
    assert row["delivered_rate"] == pytest.approx(3 / 6)
    assert row["failed_rate_90d"] == pytest.approx(1 / 6)


def test_return_rate_leaves_out_address_and_rider_problems(delivery_example):
    # Two parcels came back, but one was an address problem: only "refused" counts.
    assert delivery_example.loc["L1", "return_rate_90d"] == pytest.approx(1 / 6)


def test_delivery_time_is_the_median_of_settled_delivered_parcels(delivery_example):
    # 24, 48 and 36 hours
    assert delivery_example.loc["L1", "dispatch_to_delivery_hours"] == pytest.approx(36.0)


def test_cod_remittance_rate_uses_settled_cash_on_delivery_parcels(delivery_example):
    # parcel 1 remitted on time, parcel 2 did not
    assert delivery_example.loc["L1", "cod_remit_ontime_rate"] == pytest.approx(0.5)


def test_few_parcels_are_flagged_as_thin(delivery_example, config):
    assert config["features"]["thin_delivery_parcels"] > 8
    assert delivery_example.loc["L1", "delivery_data_thin"] == 1


def test_no_parcels_means_no_delivery_features_not_zeros(delivery_example):
    """Missing delivery data must never look like bad delivery data."""
    row = delivery_example.loc["L2"]
    for name in DELIVERY_FEATURES:
        assert np.isnan(row[name]), name


# --- the whole table -----------------------------------------------------------------


@pytest.fixture(scope="module")
def synthetic_features(config) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    small = copy.deepcopy(config)
    small["data"]["n_merchants"] = 1500
    tables, _, _ = build_tables(small, 0.5)
    return build_features(tables, small), tables


def test_one_row_per_loan_with_every_feature(synthetic_features):
    features, tables = synthetic_features
    assert len(features) == len(tables["loans"])
    assert features["loan_id"].is_unique
    assert set(features["loan_id"]) == set(tables["loans"]["loan_id"])
    for group, names in FEATURE_GROUPS.items():
        for name in names:
            assert name in features.columns, f"{group}: {name}"


def test_every_feature_is_in_the_dictionary():
    """A feature without a dictionary entry could not be explained to an officer."""
    documented = set(load_dictionary()["features"])
    for group, names in FEATURE_GROUPS.items():
        assert set(names) <= documented, group


def test_purchase_features_stay_in_sensible_ranges(synthetic_features):
    features, _ = synthetic_features
    assert (features["purchases_90d"] >= 0).all()
    assert (features["purchase_value_90d"] >= 0).all()
    assert features["purchase_regularity"].dropna().between(0, 1).all()
    assert features["supplier_repeat_share"].dropna().between(0, 1).all()
    assert (features["purchase_volatility"].dropna() >= 0).all()
    assert set(PURCHASE_FEATURES) <= set(features.columns)


def test_delivery_features_stay_in_sensible_ranges(synthetic_features):
    features, tables = synthetic_features
    for name in ("delivered_rate", "return_rate_90d", "failed_rate_90d", "cod_remit_ontime_rate"):
        assert features[name].dropna().between(0, 1).all(), name
    assert (features["dispatch_to_delivery_hours"].dropna() > 0).all()
    assert set(features["delivery_data_thin"].dropna().unique()) <= {0.0, 1.0}

    # Merchants who never send parcels have no delivery features at all.
    senders = set(tables["deliveries"]["merchant_id"])
    no_parcels = ~features["merchant_id"].isin(senders)
    assert no_parcels.any()
    assert features.loc[no_parcels, DELIVERY_FEATURES].isna().all().all()


def test_payment_features_stay_in_sensible_ranges(synthetic_features):
    features, tables = synthetic_features
    assert (features["avg_pay_delay_days"].dropna() >= 0).all()
    assert features["ontime_payment_rate"].dropna().between(0, 1).all()
    assert (features["late_pay_count_90d"].dropna() >= 0).all()
    assert features["credit_utilisation"].dropna().between(0, 1.5).all()

    # A merchant's first loan can have no payment history; later loans usually do.
    order = tables["loans"].sort_values("issued_at").groupby("merchant_id").cumcount()
    first_loans = set(tables["loans"].loc[order[order == 0].index, "loan_id"])
    is_first = features["loan_id"].isin(first_loans)
    assert features.loc[is_first, PAYMENT_FEATURES].isna().all().all()
    assert features.loc[~is_first, "credit_utilisation"].notna().all()


def test_no_group_column_is_a_feature(synthetic_features):
    """Town tier, shop type and licence are audit columns, never model inputs."""
    features, _ = synthetic_features
    for column in ("town_tier", "shop_type", "has_trade_license", "district"):
        assert column not in features.columns
