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
    FEATURE_GROUPS,
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


def test_no_group_column_is_a_feature(synthetic_features):
    """Town tier, shop type and licence are audit columns, never model inputs."""
    features, _ = synthetic_features
    for column in ("town_tier", "shop_type", "has_trade_license", "district"):
        assert column not in features.columns
