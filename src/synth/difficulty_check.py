"""A rough check of how hard the synthetic data is to predict. Not the real model.

Purpose: answer two questions right after generating data, long before the real
    feature builder and model exist:
    1. Is the prediction task about as hard as real merchant lending (test AUC around
       0.72 to 0.82), or is it far too easy or too hard?
    2. Does delivery data help only when the signal strength says it should?
Owner role: B (data engineer). The real model belongs to role C in src/model/.
Implements: docs/GENERATOR_SPEC.md ("Required self-checks") and PROJECT_BRIEF section 18,
    item 12 (model quality bar).

It builds a handful of crude features for each loan, using only events dated before
the loan was issued, fits a plain logistic regression on the first 12 months of loans
and scores the VALIDATION months (the 3 months after training). It never looks at the
test months, which are kept for the final report. The numbers are a sanity check on the
generator. They must not be quoted as model results.

History, stated openly: until Oct 13, 2026 this check scored the test months, and the
generator's difficulty was tuned with those numbers. That use is recorded in
reports/synthetic_bd/test_set_use.json.

Run it:
    python -m src.synth.difficulty_check
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.config import load_config
from src.model.split import split_for_mode
from src.synth.generate import ALL_STRENGTHS, build_tables

LOOKBACK_DAYS = 90

PURCHASE_FEATURES = ["purchases_90d", "purchase_value_90d", "main_supplier_share", "days_known"]
PAYMENT_FEATURES = ["prior_loans", "prior_mean_days_late", "prior_bad_share"]
DELIVERY_FEATURES = ["parcels_90d", "merchant_return_rate", "cod_ontime_rate"]


def _events_before_loan(
    loans: pd.DataFrame, events: pd.DataFrame, date_column: str
) -> pd.DataFrame:
    """Pair every loan with that merchant's events from the 90 days before the issue date."""
    paired = loans[["loan_id", "merchant_id", "issue_date"]].merge(events, on="merchant_id")
    age = (paired["issue_date"] - paired[date_column]).dt.days
    return paired[(age > 0) & (age <= LOOKBACK_DAYS)]


def build_check_features(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per labelled loan with crude features built only from earlier events."""
    loans = tables["loans"].copy()
    loans["issue_date"] = pd.to_datetime(loans["issued_at"])
    loans = loans[loans["outcome_label"].notna()].copy()
    loans["label"] = loans["outcome_label"].astype(int)

    merchants = tables["merchants"][["merchant_id", "onboarded_at"]]
    frame = loans[["loan_id", "merchant_id", "issue_date", "label"]].merge(merchants)
    frame["days_known"] = (frame["issue_date"] - pd.to_datetime(frame["onboarded_at"])).dt.days

    # Purchases in the 90 days before the loan.
    purchases = tables["purchases"][["merchant_id", "purchase_date", "amount_bdt", "supplier_id"]]
    purchases = purchases.assign(purchase_date=pd.to_datetime(purchases["purchase_date"]))
    recent = _events_before_loan(loans, purchases, "purchase_date")
    by_loan = recent.groupby("loan_id")
    top_supplier = recent.groupby(["loan_id", "supplier_id"]).size().groupby("loan_id").max()
    purchase_part = pd.DataFrame(
        {
            "purchases_90d": by_loan.size(),
            "purchase_value_90d": by_loan["amount_bdt"].sum(),
            "main_supplier_share": top_supplier / by_loan.size(),
        }
    )

    # Earlier loans of the same merchant whose outcome was already known at issue.
    payments = tables["payments"][["merchant_id", "due_date", "paid_date"]].copy()
    payments["due_date"] = pd.to_datetime(payments["due_date"])
    payments["paid_date"] = pd.to_datetime(payments["paid_date"])
    earlier = loans[["loan_id", "merchant_id", "issue_date"]].merge(payments, on="merchant_id")
    earlier = earlier[earlier["due_date"] < earlier["issue_date"]].copy()
    paid_before = earlier["paid_date"].notna() & (earlier["paid_date"] < earlier["issue_date"])
    days_late = (earlier["paid_date"] - earlier["due_date"]).dt.days.clip(lower=0)
    waited = (earlier["issue_date"] - earlier["due_date"]).dt.days
    earlier["days_late_so_far"] = np.where(paid_before, days_late, waited)
    earlier["bad_so_far"] = earlier["days_late_so_far"] > 30
    payment_part = earlier.groupby("loan_id").agg(
        prior_loans=("due_date", "size"),
        prior_mean_days_late=("days_late_so_far", "mean"),
        prior_bad_share=("bad_so_far", "mean"),
    )

    # Parcels in the 90 days before the loan.
    deliveries = tables["deliveries"][
        ["merchant_id", "dispatched_at", "status", "return_reason", "cod_remitted_on_time"]
    ].copy()
    deliveries["dispatched_at"] = pd.to_datetime(deliveries["dispatched_at"])
    parcels = _events_before_loan(loans, deliveries, "dispatched_at")
    merchant_return = parcels["status"].eq("returned") & parcels["return_reason"].isin(
        ["refused", "wrong_item", "other"]
    )
    parcels = parcels.assign(
        merchant_return=merchant_return,
        cod_on_time=parcels["cod_remitted_on_time"].astype("float"),
    )
    delivery_part = parcels.groupby("loan_id").agg(
        parcels_90d=("status", "size"),
        merchant_return_rate=("merchant_return", "mean"),
        cod_ontime_rate=("cod_on_time", "mean"),
    )

    frame = frame.set_index("loan_id").join([purchase_part, payment_part, delivery_part])
    frame["purchases_90d"] = frame["purchases_90d"].fillna(0)
    frame["purchase_value_90d"] = frame["purchase_value_90d"].fillna(0)
    frame["prior_loans"] = frame["prior_loans"].fillna(0)
    frame["parcels_90d"] = frame["parcels_90d"].fillna(0)
    return frame.reset_index()


def _split_by_time(
    frame: pd.DataFrame, config: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Train on the first months of loans, score the validation months. Never the test months."""
    split = split_for_mode(frame, config, mode="synthetic_bd", date_column="issue_date")
    return split.train, split.validation


def _auc(train: pd.DataFrame, test: pd.DataFrame, features: list[str]) -> float:
    """Fit a plain logistic regression on `features` and return the test AUC."""
    model = make_pipeline(
        SimpleImputer(strategy="median", add_indicator=True),
        StandardScaler(),
        LogisticRegression(max_iter=1000),
    )
    model.fit(train[features], train["label"])
    return float(roc_auc_score(test["label"], model.predict_proba(test[features])[:, 1]))


def check(config: dict[str, Any], strength: float) -> dict[str, Any]:
    """Generate data at one signal strength and measure how predictable it is."""
    tables, latent, facts = build_tables(config, strength)
    frame = build_check_features(tables)
    train, scored = _split_by_time(frame, config)

    set_a = PURCHASE_FEATURES
    set_b = set_a + PAYMENT_FEATURES
    set_c = set_b + DELIVERY_FEATURES
    auc_b = _auc(train, scored, set_b)
    auc_c = _auc(train, scored, set_c)

    # The best any model could do: predicting from the hidden reliability itself.
    truth = scored.merge(latent[["merchant_id", "reliability"]], on="merchant_id")
    return {
        "delivery_signal_strength": strength,
        "scored_on": "validation months",
        "train_loans": int(len(train)),
        "validation_loans": int(len(scored)),
        "validation_not_repaid_loans": int((scored["label"] == 0).sum()),
        "repaid_share_validation": round(float(scored["label"].mean()), 4),
        "auc_purchases_only": round(_auc(train, scored, set_a), 4),
        "auc_plus_payments": round(auc_b, 4),
        "auc_plus_deliveries": round(auc_c, 4),
        "delivery_gain": round(auc_c - auc_b, 4),
        "auc_ceiling_from_hidden_reliability": round(
            float(roc_auc_score(truth["label"], truth["reliability"])), 4
        ),
        "repaid_share_all_observed": round(facts["repaid_share_observed"], 4),
    }


def main() -> int:
    """Print the difficulty check for every signal strength."""
    config = load_config()
    results = [check(config, strength) for strength in ALL_STRENGTHS]
    print("Rough difficulty check on synthetic data. A generator sanity check, not model results.")
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
