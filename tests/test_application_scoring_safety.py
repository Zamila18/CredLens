"""Can a new application be scored safely by the saved model? (Phase 1 safety checks.)

Purpose: before any application workflow is built, check that a loan-shaped application
    row can be scored by the existing model without its requested amount reaching the
    model, without counting as credit history, and with missing delivery data treated as
    average. Also pins down what the score means: the probability of label 1 (repaid
    within 30 days of the due date), so a higher score is better.
Owner role: C (ML engineer).
Implements: the implementation pack, Phase 1 (model risk audit) and the go/no-go for
    scoring applications (appendix A9).

Nothing here changes the model, the features or any data: features are built from small
generated tables, and the committed model is only read.
"""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

from src.config import load_config
from src.features.build_features import DELIVERY_FEATURES, build_features, model_feature_names
from src.features.dictionary import expected_directions, load_dictionary
from src.model.explain import average_inputs, calibrated_probability, contributions_for_row
from src.model.labels import LABELLED, build_labels, latest_date
from src.model.train import load_model
from src.synth.generate import build_tables

MODEL_INPUTS = model_feature_names("ABC")


@pytest.fixture(scope="module")
def config() -> dict:
    small = copy.deepcopy(load_config())
    small["data"]["n_merchants"] = 600
    return small


@pytest.fixture(scope="module")
def world(config) -> dict[str, pd.DataFrame]:
    return build_tables(config, 0.5)[0]


@pytest.fixture(scope="module")
def saved() -> dict:
    """The committed synthetic model: the one the API scores with."""
    return load_model("synthetic_bd")


def _copy(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    return {name: frame.copy() for name, frame in tables.items()}


def _inputs(tables: dict[str, pd.DataFrame], config: dict, loan_id: str) -> pd.Series:
    """The model inputs of one loan, as the scorer would build them."""
    features = build_features(tables, config).set_index("loan_id")
    return features.loc[loan_id, MODEL_INPUTS]


def _latest_loan_with_history(tables: dict[str, pd.DataFrame]) -> pd.Series:
    """The latest loan of a merchant who repaid earlier loans, so payment inputs exist."""
    loans = tables["loans"].sort_values(["issued_at", "loan_id"])
    repeat = loans.groupby("merchant_id").filter(lambda group: len(group) >= 2)
    return repeat.groupby("merchant_id").tail(1).iloc[0]


def _days(day: str, offset: int) -> str:
    return (pd.Timestamp(day) + pd.Timedelta(days=offset)).strftime("%Y-%m-%d")


# --- the requested amount ---------------------------------------------------------------


def test_the_saved_model_has_no_amount_or_limit_input(saved):
    """The score cannot see how much is asked for: no input is an amount or a limit."""
    assert len(saved["features"]) == 10
    for name in saved["features"]:
        assert "amount" not in name and "limit" not in name


def test_the_requested_amount_never_reaches_the_applications_own_inputs(world, config):
    """A thousand times the amount on the scored row gives exactly the same inputs.

    So the score says nothing about whether the amount asked for is affordable: that is
    a separate question for a documented range policy.
    """
    target = _latest_loan_with_history(world)
    before = _inputs(world, config, target["loan_id"])
    assert before[["ontime_payment_rate", "credit_utilisation"]].notna().all()

    changed = _copy(world)
    row = changed["loans"]["loan_id"] == target["loan_id"]
    changed["loans"].loc[row, "limit_bdt"] = target["limit_bdt"] * 1000
    pd.testing.assert_series_equal(before, _inputs(changed, config, target["loan_id"]))


# --- an application must not become credit history -----------------------------------


def test_an_earlier_loan_row_without_payments_adds_no_history(world, config):
    """An application row (no payments, no outcome) changes no later loan's inputs, and is
    never labelled as repaid or as a default."""
    target = _latest_loan_with_history(world)
    before = _inputs(world, config, target["loan_id"])

    changed = _copy(world)
    application = {
        "loan_id": "APPLICATION-TEST",
        "merchant_id": target["merchant_id"],
        "issued_at": _days(target["issued_at"], -20),
        "limit_bdt": 50000.0,
        "outcome_label": None,
        "label_observed_at": None,
    }
    changed["loans"] = pd.concat([changed["loans"], pd.DataFrame([application])], ignore_index=True)
    pd.testing.assert_series_equal(before, _inputs(changed, config, target["loan_id"]))

    labels = build_labels(
        changed["loans"], changed["payments"], config, latest_date(changed)
    ).set_index("loan_id")
    assert labels.loc["APPLICATION-TEST", "label_status"] != LABELLED
    assert pd.isna(labels.loc["APPLICATION-TEST", "label"])


def test_a_payment_on_the_scored_row_does_not_change_its_own_inputs(world, config):
    """The scored row's own payments fall after its cutoff, so they are never its inputs."""
    target = _latest_loan_with_history(world)
    before = _inputs(world, config, target["loan_id"])

    changed = _copy(world)
    payment = {
        "payment_id": "PAYMENT-TEST",
        "merchant_id": target["merchant_id"],
        "loan_id": target["loan_id"],
        "due_date": _days(target["issued_at"], 30),
        "paid_date": _days(target["issued_at"], 10),
        "amount_due_bdt": 1000.0,
        "amount_paid_bdt": 1000.0,
    }
    changed["payments"] = pd.concat(
        [changed["payments"], pd.DataFrame([payment])], ignore_index=True
    )
    pd.testing.assert_series_equal(before, _inputs(changed, config, target["loan_id"]))


def test_a_payment_on_an_application_would_become_history_for_a_later_loan(world, config):
    """Why the intake must refuse repayments against an application row.

    A payment attached to an earlier loan-shaped row is read as repayment history by
    every later loan of the merchant. If that row were an application, the payment
    would invent credit history.
    """
    loans = world["loans"].sort_values(["issued_at", "loan_id"])
    single = loans.groupby("merchant_id").filter(lambda group: len(group) == 1).iloc[0]
    changed = _copy(world)
    later = {
        "loan_id": "LATER-TEST",
        "merchant_id": single["merchant_id"],
        "issued_at": _days(single["issued_at"], 60),
        "limit_bdt": 40000.0,
        "outcome_label": None,
        "label_observed_at": None,
    }
    changed["loans"] = pd.concat([changed["loans"], pd.DataFrame([later])], ignore_index=True)
    without_payment = changed["payments"]["loan_id"] != single["loan_id"]
    changed["payments"] = changed["payments"][without_payment]
    assert pd.isna(_inputs(changed, config, "LATER-TEST")["ontime_payment_rate"])

    payment = {
        "payment_id": "PAYMENT-TEST",
        "merchant_id": single["merchant_id"],
        "loan_id": single["loan_id"],
        "due_date": _days(single["issued_at"], 30),
        "paid_date": _days(single["issued_at"], 25),
        "amount_due_bdt": 1000.0,
        "amount_paid_bdt": 1000.0,
    }
    changed["payments"] = pd.concat(
        [changed["payments"], pd.DataFrame([payment])], ignore_index=True
    )
    assert pd.notna(_inputs(changed, config, "LATER-TEST")["ontime_payment_rate"])


# --- missing delivery data ---------------------------------------------------------------


def test_missing_delivery_data_scores_exactly_like_average_delivery_data(saved, config):
    """No delivery records = the training average for every delivery input: the same
    probability, and zero points for each delivery input."""
    averages = average_inputs(saved)
    row = dict(averages)
    row.update({"ontime_payment_rate": 1.0, "avg_pay_delay_days": 0.0, "basket_growth": 0.3})
    with_average_delivery = pd.DataFrame([row])
    missing = dict(row, **{name: np.nan for name in DELIVERY_FEATURES})

    p_average = calibrated_probability(saved, with_average_delivery)[0]
    p_missing = calibrated_probability(saved, pd.DataFrame([missing]))[0]
    assert p_missing == pytest.approx(p_average, abs=1e-12)

    points = contributions_for_row(saved, pd.Series(missing), config)["points"]
    assert all(points[name] == 0 for name in DELIVERY_FEATURES)


# --- what the score means -------------------------------------------------------------


def test_the_score_is_the_probability_of_repaying_so_higher_is_better(saved):
    """The model predicts label 1 (repaid within 30 days). Every input pushes the way its
    meaning says, so a better behaviour can only raise the score."""
    model = saved["model"][-1]
    assert list(model.classes_) == [0, 1]
    directions = expected_directions(load_dictionary())
    for name, weight in zip(saved["features"], model.coef_[0]):
        assert np.sign(weight) in (0, directions[name]), name


def test_the_reasons_explain_the_distance_from_the_baseline(saved, config):
    """Baseline (the score of training-average inputs) + all points = 100 x probability.
    The points explain the difference from that baseline, not the score from zero."""
    row = dict(average_inputs(saved))
    row.update({"return_rate_90d": 0.2, "ontime_payment_rate": 0.5, "supplier_repeat_share": 0.9})
    parts = contributions_for_row(saved, pd.Series(row), config)
    probability = calibrated_probability(saved, pd.DataFrame([row]))[0]

    assert parts["exact_score"] == pytest.approx(100 * probability, abs=1e-9)
    total = parts["baseline_score"] + sum(parts["points"].values())
    assert total == pytest.approx(parts["exact_score"], abs=1e-9)
    average_probability = calibrated_probability(saved, pd.DataFrame([average_inputs(saved)]))[0]
    assert parts["baseline_score"] == pytest.approx(100 * average_probability, abs=1e-9)
