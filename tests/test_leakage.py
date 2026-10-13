"""Leakage tests: no feature may use anything from the cutoff day or later.

Owner role: B (data engineer) with C (ML engineer).
Implements: docs/MODEL_SPEC.md section 3 and PROJECT_BRIEF section 7.1 ("a test must fail
    the build if any feature uses data after the loan's cutoff date").

How it works: for a sample of loans, the features are built twice. Once from all the
data, and once after everything dated on or after the loan's cutoff has been erased. If
a feature changes, it was looking at the future.

A check that never fails proves nothing, so this file also plants leaks on purpose and
makes sure each one is caught.
"""

from __future__ import annotations

import copy

import pandas as pd
import pytest

from src.config import load_config
from src.features.build_features import (
    COVERAGE_COLUMNS,
    KEY_COLUMNS,
    build_features,
    loan_cutoffs,
    model_feature_names,
)
from src.features.leakage import erase_future, future_dependent_columns
from src.synth.generate import build_tables


@pytest.fixture(scope="module")
def config() -> dict:
    small = copy.deepcopy(load_config())
    small["data"]["n_merchants"] = 1200
    return small


@pytest.fixture(scope="module")
def tables(config) -> dict[str, pd.DataFrame]:
    built, _, _ = build_tables(config, 1.0)
    return built


# --- the real feature builder --------------------------------------------------------


def test_no_feature_uses_data_on_or_after_the_cutoff(tables, config):
    """Features for a loan come only from events strictly before its issue date."""
    changed = future_dependent_columns(build_features, tables, config, sample_size=80)
    assert changed == {}, f"these features changed when the future was erased: {changed}"


def test_the_check_covers_every_model_input_and_coverage_column(tables, config):
    """The check compares every column except the three keys, so nothing is skipped."""
    columns = set(build_features(tables, config).columns) - set(KEY_COLUMNS)
    assert set(model_feature_names("ABC")) <= columns
    assert set(COVERAGE_COLUMNS) <= columns


def test_the_sample_includes_loans_with_a_future_to_erase(tables):
    """Otherwise the check above would be trivially true."""
    loans = tables["loans"].sample(n=80, random_state=42)
    purchases = tables["purchases"].merge(loans[["merchant_id", "issued_at"]], on="merchant_id")
    assert (purchases["purchase_date"] >= purchases["issued_at"]).any()
    payments = tables["payments"].merge(loans[["merchant_id", "issued_at"]], on="merchant_id")
    paid = payments.dropna(subset=["paid_date"])
    assert (paid["paid_date"] >= paid["issued_at"]).any()


# --- planted leaks: each one must be caught ------------------------------------------


def with_leak(leak):
    """A feature builder that adds one leaking column to the real features."""

    def build(tables: dict[str, pd.DataFrame], config: dict) -> pd.DataFrame:
        features = build_features(tables, config)
        cutoffs = loan_cutoffs(tables)
        leaked = leak(tables, cutoffs).reindex(features["loan_id"]).to_numpy()
        return features.assign(leaked_feature=leaked)

    return build


def purchases_including_the_cutoff_day(tables, cutoffs) -> pd.Series:
    """Leak 1: an off-by-one. Counts purchases up to AND INCLUDING the cutoff day."""
    paired = cutoffs.merge(tables["purchases"], on="merchant_id")
    kept = paired[pd.to_datetime(paired["purchase_date"]) <= paired["cutoff_date"]]
    return kept.groupby("loan_id").size().reindex(cutoffs["loan_id"]).fillna(0)


def purchases_in_the_next_month(tables, cutoffs) -> pd.Series:
    """Leak 2: plainly reads the 30 days after the cutoff."""
    paired = cutoffs.merge(tables["purchases"], on="merchant_id")
    days_after = (pd.to_datetime(paired["purchase_date"]) - paired["cutoff_date"]).dt.days
    kept = paired[(days_after >= 0) & (days_after < 30)]
    return kept.groupby("loan_id").size().reindex(cutoffs["loan_id"]).fillna(0)


def own_repayment_delay(tables, cutoffs) -> pd.Series:
    """Leak 3: uses the payment of the very loan being scored."""
    payments = tables["payments"].set_index("loan_id")
    delay = (pd.to_datetime(payments["paid_date"]) - pd.to_datetime(payments["due_date"])).dt.days
    return delay.reindex(cutoffs["loan_id"])


def own_outcome_label(tables, cutoffs) -> pd.Series:
    """Leak 4: the worst one. Uses the answer itself."""
    labels = tables["loans"].set_index("loan_id")["outcome_label"].astype("float")
    return labels.reindex(cutoffs["loan_id"])


def parcels_delivered_whenever(tables, cutoffs) -> pd.Series:
    """Leak 5: counts parcels as delivered even when they arrived after the cutoff."""
    deliveries = tables["deliveries"]
    paired = cutoffs.merge(deliveries, on="merchant_id")
    dispatched_before = pd.to_datetime(paired["dispatched_at"]) < paired["cutoff_date"]
    kept = paired[dispatched_before & paired["delivered_at"].notna()]
    return kept.groupby("loan_id").size().reindex(cutoffs["loan_id"]).fillna(0)


@pytest.mark.parametrize(
    "leak",
    [
        purchases_including_the_cutoff_day,
        purchases_in_the_next_month,
        own_repayment_delay,
        own_outcome_label,
        parcels_delivered_whenever,
    ],
)
def test_a_planted_future_row_is_caught(tables, config, leak):
    """A deliberately leaking feature must make the leakage check fail."""
    changed = future_dependent_columns(with_leak(leak), tables, config, sample_size=40)
    assert "leaked_feature" in changed, f"the check missed this leak: {leak.__name__}"
    assert set(changed) == {"leaked_feature"}, "only the planted column should be flagged"


# --- the eraser itself ---------------------------------------------------------------


def test_erase_future_removes_or_blanks_everything_from_the_cutoff_on(tables):
    as_of = pd.Timestamp("2026-01-01")
    erased = erase_future(tables, as_of)

    assert (pd.to_datetime(erased["purchases"]["purchase_date"]) < as_of).all()
    assert (pd.to_datetime(erased["deliveries"]["dispatched_at"]) < as_of).all()
    assert (pd.to_datetime(erased["deliveries"]["delivered_at"].dropna()) < as_of).all()
    assert (pd.to_datetime(erased["questionnaire"]["answered_at"]) < as_of).all()
    assert (pd.to_datetime(erased["loans"]["issued_at"]) <= as_of).all()
    assert erased["loans"]["outcome_label"].isna().all()
    assert (pd.to_datetime(erased["payments"]["paid_date"].dropna()) < as_of).all()
    assert set(erased["payments"]["loan_id"]) <= set(erased["loans"]["loan_id"])

    # It really removed something, and it did not touch the original tables.
    assert len(erased["purchases"]) < len(tables["purchases"])
    assert tables["loans"]["outcome_label"].notna().any()
