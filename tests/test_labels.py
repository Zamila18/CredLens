"""Tests for the training labels (src/model/labels.py).

Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 2 (the 30-day rule; loans under 60 days excluded).
"""

from __future__ import annotations

import copy

import pandas as pd
import pytest

from src.adapters import CONTRACT, empty_frame
from src.config import load_config
from src.model.labels import (
    LABELLED,
    NOT_YET_KNOWN,
    TOO_YOUNG,
    build_labels,
    labelled_only,
    latest_date,
)
from src.synth.generate import build_tables

AS_OF = "2026-01-01"


@pytest.fixture(scope="module")
def config() -> dict:
    return load_config()


def loan(loan_id: str, issued: str, outcome: int | None = None) -> dict:
    return {"loan_id": loan_id, "merchant_id": "M1", "issued_at": issued, "outcome_label": outcome}


def payment(
    loan_id: str, due: str, paid: str | None, number: int = 1, amount_paid: float | None = None
) -> dict:
    if amount_paid is None:
        amount_paid = 1000.0 if paid else 0.0
    return {
        "payment_id": f"P-{loan_id}-{number}",
        "merchant_id": "M1",
        "loan_id": loan_id,
        "due_date": due,
        "paid_date": paid,
        "amount_due_bdt": 1000.0,
        "amount_paid_bdt": amount_paid,
    }


def labels_for(loans: list[dict], payments: list[dict], config: dict) -> pd.DataFrame:
    loans_frame = pd.DataFrame(loans).reindex(columns=CONTRACT["loans"])
    payments_frame = (
        pd.DataFrame(payments).reindex(columns=CONTRACT["payments"])
        if payments
        else empty_frame("payments")
    )
    return build_labels(loans_frame, payments_frame, config, AS_OF).set_index("loan_id")


# --- the worked examples in docs/MODEL_SPEC.md ---------------------------------------


def test_repaid_ten_days_late_is_good(config):
    labels = labels_for(
        [loan("L1", "2025-06-01")], [payment("L1", "2025-07-01", "2025-07-11")], config
    )
    assert labels.loc["L1", "label"] == 1
    assert labels.loc["L1", "label_status"] == LABELLED


def test_unpaid_sixty_days_after_the_due_date_is_bad(config):
    labels = labels_for([loan("L1", "2025-10-03")], [payment("L1", "2025-11-02", None)], config)
    assert labels.loc["L1", "label"] == 0


def test_a_loan_issued_thirty_five_days_ago_is_excluded(config):
    labels = labels_for([loan("L1", "2025-11-27")], [payment("L1", "2025-12-27", None)], config)
    assert pd.isna(labels.loc["L1", "label"])
    assert labels.loc["L1", "label_status"] == TOO_YOUNG


# --- the edges of the rule -----------------------------------------------------------


@pytest.mark.parametrize(
    ("paid", "expected"),
    [("2025-06-25", 1), ("2025-07-01", 1), ("2025-07-31", 1), ("2025-08-01", 0)],
)
def test_thirty_days_late_is_still_good_and_thirty_one_is_not(config, paid, expected):
    labels = labels_for([loan("L1", "2025-06-01")], [payment("L1", "2025-07-01", paid)], config)
    assert labels.loc["L1", "label"] == expected


def test_a_young_loan_is_never_counted_as_a_default(config):
    """Even one already 31 days overdue: under 60 days old means no label at all."""
    labels = labels_for([loan("L1", "2025-11-10")], [payment("L1", "2025-11-20", None)], config)
    assert labels.loc["L1", "label_status"] == TOO_YOUNG
    assert pd.isna(labels.loc["L1", "label"])


def test_an_old_loan_not_yet_overdue_enough_has_no_label(config):
    """Unpaid, but only 12 days past due: the outcome is not known yet."""
    labels = labels_for([loan("L1", "2025-10-01")], [payment("L1", "2025-12-20", None)], config)
    assert labels.loc["L1", "label_status"] == NOT_YET_KNOWN
    assert pd.isna(labels.loc["L1", "label"])


def test_a_payment_dated_after_today_does_not_count_as_paid(config):
    labels = labels_for(
        [loan("L1", "2025-09-01")], [payment("L1", "2025-10-01", "2026-02-01")], config
    )
    assert labels.loc["L1", "label"] == 0  # 92 days past due and not paid as of today


def test_one_late_instalment_makes_the_whole_loan_bad(config):
    labels = labels_for(
        [loan("L1", "2025-03-01")],
        [
            payment("L1", "2025-04-01", "2025-04-01", number=1),
            payment("L1", "2025-05-01", "2025-06-15", number=2),
            payment("L1", "2025-06-01", "2025-06-01", number=3),
        ],
        config,
    )
    assert labels.loc["L1", "label"] == 0


def test_all_instalments_in_time_makes_the_loan_good(config):
    labels = labels_for(
        [loan("L1", "2025-03-01")],
        [
            payment("L1", "2025-04-01", "2025-04-05", number=1),
            payment("L1", "2025-05-01", "2025-05-20", number=2),
        ],
        config,
    )
    assert labels.loc["L1", "label"] == 1


@pytest.mark.parametrize(("amount_paid", "expected"), [(1000.0, 1), (995.0, 1), (100.0, 0)])
def test_a_part_payment_is_not_a_repayment(config, amount_paid, expected):
    """Paying 100 of 1000 on the due date does not make the loan good."""
    labels = labels_for(
        [loan("L1", "2025-06-01")],
        [payment("L1", "2025-07-01", "2025-07-01", amount_paid=amount_paid)],
        config,
    )
    assert labels.loc["L1", "label"] == expected


def test_the_rule_reads_its_numbers_from_the_config(config):
    strict = copy.deepcopy(config)
    strict["labels"]["good_if_days_late_at_most"] = 5
    rows = ([loan("L1", "2025-06-01")], [payment("L1", "2025-07-01", "2025-07-11")])
    assert labels_for(*rows, config).loc["L1", "label"] == 1
    assert labels_for(*rows, strict).loc["L1", "label"] == 0


# --- sources that supply the outcome themselves --------------------------------------


def test_without_payment_records_the_supplied_outcome_is_used(config):
    """Public sources such as Taiwan give the outcome directly."""
    labels = labels_for(
        [loan("L1", "2025-01-01", 1), loan("L2", "2025-01-01", 0), loan("L3", "2025-01-01")],
        [],
        config,
    )
    assert labels.loc["L1", "label"] == 1
    assert labels.loc["L2", "label"] == 0
    assert labels.loc["L1", "label_source"] == "source"
    assert labels.loc["L3", "label_status"] == NOT_YET_KNOWN


def test_payment_records_win_over_a_supplied_outcome(config):
    labels = labels_for(
        [loan("L1", "2025-06-01", 1)], [payment("L1", "2025-07-01", "2025-09-15")], config
    )
    assert labels.loc["L1", "label"] == 0
    assert labels.loc["L1", "label_source"] == "payments"


# --- on the synthetic data -----------------------------------------------------------


@pytest.fixture(scope="module")
def synthetic(config) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    small = copy.deepcopy(config)
    small["data"]["n_merchants"] = 2000
    tables, _, _ = build_tables(small, 0.5)
    labels = build_labels(tables["loans"], tables["payments"], small, latest_date(tables))
    return tables, labels


def test_labels_worked_out_from_payments_match_the_generator(synthetic):
    """Two independent routes to the label must agree: the generator's and the rule's."""
    tables, labels = synthetic
    generated = tables["loans"].set_index("loan_id")["outcome_label"]
    worked_out = labels.set_index("loan_id")["label"]
    both = pd.DataFrame({"generated": generated, "worked_out": worked_out})
    assert both["generated"].isna().equals(both["worked_out"].isna())
    known = both.dropna()
    assert (known["generated"].astype(int) == known["worked_out"].astype(int)).all()


def test_every_loan_keeps_a_row_and_only_labelled_ones_are_used(synthetic):
    tables, labels = synthetic
    assert len(labels) == len(tables["loans"])
    usable = labelled_only(labels)
    assert usable["label"].notna().all()
    assert set(usable["label"].unique()) == {0, 1}
    assert (labels["label_status"] == TOO_YOUNG).any(), "pending loans must exist"
    assert len(usable) < len(labels)


def test_latest_date_is_the_last_day_of_the_data(synthetic, config):
    tables, _ = synthetic
    start = pd.Timestamp(config["generator"]["start_date"])
    main_end = start + pd.DateOffset(months=config["data"]["months"])
    tail = pd.Timedelta(days=config["generator"]["observation_tail_days"] - 1)
    assert latest_date(tables) == main_end + tail
