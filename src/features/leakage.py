"""A guard against leakage: features must not change when the future is erased.

Purpose: prove, by experiment, that no feature for a loan depends on anything that
    happened on or after that loan's cutoff date.
Owner role: B (data engineer), with C (ML engineer).
Implements: docs/MODEL_SPEC.md section 3 ("no feature may read any row dated on or after
    the cutoff") and PROJECT_BRIEF section 7.1 ("a test must fail the build if any
    feature uses data after the loan's cutoff date").

The idea in plain words: take one loan. Build its features from all the data. Then wipe
out everything dated on or after its cutoff day (later purchases, later parcels, later
payments, the loan's own outcome) and build the features again. If any number changes,
that feature was looking at the future.

tests/test_leakage.py runs this on real features (nothing may change) and on features
with a leak planted on purpose (the leak must be caught).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

FeatureBuilder = Callable[[dict[str, pd.DataFrame], dict[str, Any]], pd.DataFrame]
NOT_FEATURES = ("loan_id", "merchant_id", "cutoff_date")


def erase_future(tables: dict[str, pd.DataFrame], as_of: pd.Timestamp) -> dict[str, pd.DataFrame]:
    """Return a copy of the tables as they would have looked at the start of `as_of`.

    Everything dated on or after `as_of` is removed or blanked:
    - purchases, parcels, questionnaire answers and consents dated then or later: removed;
    - loans issued after `as_of`: removed (a loan issued on that day is the one being
      scored, so it stays), and every outcome label is blanked;
    - a payment made then or later: shown as not paid;
    - a parcel delivered then or later: no delivery time and no remittance flag;
    - a consent revoked then or later: shown as still valid.
    """
    as_of = pd.Timestamp(as_of)

    def before(frame: pd.DataFrame, column: str) -> pd.Series:
        return pd.to_datetime(frame[column]).dt.normalize() < as_of

    erased = {name: frame.copy() for name, frame in tables.items()}
    erased["purchases"] = erased["purchases"][before(erased["purchases"], "purchase_date")]
    answers = erased["questionnaire"]
    erased["questionnaire"] = answers[before(answers, "answered_at")]

    deliveries = erased["deliveries"]
    deliveries = deliveries[before(deliveries, "dispatched_at")].copy()
    arrived_later = pd.to_datetime(deliveries["delivered_at"]) >= as_of
    deliveries["delivered_at"] = deliveries["delivered_at"].astype(object).mask(arrived_later, None)
    deliveries["cod_remitted_on_time"] = (
        deliveries["cod_remitted_on_time"].astype(object).mask(arrived_later, None)
    )
    erased["deliveries"] = deliveries

    loans = erased["loans"]
    loans = loans[pd.to_datetime(loans["issued_at"]) <= as_of].copy()
    loans["outcome_label"] = None
    loans["label_observed_at"] = None
    erased["loans"] = loans

    payments = erased["payments"]
    payments = payments[payments["loan_id"].isin(loans["loan_id"])].copy()
    paid_later = pd.to_datetime(payments["paid_date"]) >= as_of
    payments["paid_date"] = payments["paid_date"].astype(object).mask(paid_later, None)
    payments["amount_paid_bdt"] = payments["amount_paid_bdt"].astype(float).mask(paid_later, 0.0)
    erased["payments"] = payments

    consents = erased["consents"]
    consents = consents[before(consents, "granted_at")].copy()
    revoked_later = pd.to_datetime(consents["revoked_at"]) >= as_of
    consents["revoked_at"] = consents["revoked_at"].astype(object).mask(revoked_later, None)
    erased["consents"] = consents
    return erased


def _one_merchant(tables: dict[str, pd.DataFrame], merchant_id: str) -> dict[str, pd.DataFrame]:
    """The tables cut down to one merchant (features use a merchant's own history only)."""
    return {name: frame[frame["merchant_id"] == merchant_id] for name, frame in tables.items()}


def future_dependent_columns(
    build: FeatureBuilder,
    tables: dict[str, pd.DataFrame],
    config: dict[str, Any],
    sample_size: int = 60,
    seed: int = 42,
) -> dict[str, int]:
    """Find feature columns that change when the future is erased.

    For a random sample of loans, builds each loan's features twice: from all of that
    merchant's data, and from the data with everything on or after the loan's cutoff
    erased. Returns {column: number of sampled loans where the value changed}. An empty
    result means no leakage was found in the sample.
    """
    loans = tables["loans"]
    sample = loans.sample(n=min(sample_size, len(loans)), random_state=seed)

    changed: dict[str, int] = {}
    for loan_id, merchant_id, issued_at in sample[["loan_id", "merchant_id", "issued_at"]].values:
        own = _one_merchant(tables, merchant_id)
        full = build(own, config).set_index("loan_id").loc[loan_id]
        past_only = build(erase_future(own, pd.Timestamp(issued_at)), config)
        past_only = past_only.set_index("loan_id").loc[loan_id]

        for column in full.index:
            if column in NOT_FEATURES:
                continue
            if not _same(full[column], past_only.get(column, np.nan)):
                changed[column] = changed.get(column, 0) + 1
    return changed


def _same(first: Any, second: Any) -> bool:
    """True when two feature values are equal, treating two empty values as equal."""
    if pd.isna(first) and pd.isna(second):
        return True
    if pd.isna(first) or pd.isna(second):
        return False
    return bool(np.isclose(float(first), float(second), rtol=1e-9, atol=1e-9))
