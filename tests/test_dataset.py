"""Tests for the modelling data set and the held-out test ledger.

Owner role: C (ML engineer).
Implements: PROJECT_BRIEF section 2 (no valid consent, no scoring and no training) and
    docs/MODEL_SPEC.md section 4 (the test period is touched once, and every look is counted).
"""

from __future__ import annotations

import copy

import pandas as pd
import pytest

from src.config import load_config
from src.features.build_features import CONTEXT_COLUMNS, COVERAGE_COLUMNS, model_feature_names
from src.model.dataset import (
    build_dataset,
    dataset_summary,
    merchants_with_valid_consent,
    modelling_rows,
)
from src.model.holdout_ledger import read_ledger, record_test_use
from src.synth.generate import build_tables


def consent(merchant_id: str, granted: str, expires: str, revoked: str | None = None) -> dict:
    return {
        "consent_id": f"C-{merchant_id}",
        "merchant_id": merchant_id,
        "purpose": "credit_readiness_assessment",
        "data_categories": "purchases",
        "granted_at": granted,
        "expires_at": expires,
        "revoked_at": revoked,
    }


def test_only_unrevoked_unexpired_consents_are_valid():
    consents = pd.DataFrame(
        [
            consent("OK", "2025-01-01", "2027-01-01"),
            consent("REVOKED", "2025-01-01", "2027-01-01", "2025-06-01"),
            consent("EXPIRED", "2023-01-01", "2025-01-01"),
            consent("NOT_YET", "2026-06-01", "2028-06-01"),
            consent("REVOKED_LATER", "2025-01-01", "2027-01-01", "2026-09-01"),
        ]
    )
    valid = merchants_with_valid_consent(consents, "2026-01-01")
    assert valid == {"OK", "REVOKED_LATER"}


@pytest.fixture(scope="module")
def dataset() -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    config = copy.deepcopy(load_config())
    config["data"]["n_merchants"] = 1500
    tables, _, _ = build_tables(config, 0.5)
    return build_dataset(tables, config), tables


def test_every_loan_has_a_row_with_label_and_consent(dataset):
    frame, tables = dataset
    assert len(frame) == len(tables["loans"])
    assert frame["loan_id"].is_unique
    for column in ("label", "label_status", "consent_valid"):
        assert column in frame.columns


def test_merchants_without_consent_are_never_used_for_modelling(dataset):
    """Their loans exist in the data, but no model may learn from them or be tested on them."""
    frame, tables = dataset
    merchants = tables["merchants"]
    refused = set(merchants.loc[~merchants["consent_data_use"], "merchant_id"])
    assert len(refused) > 0
    assert frame["merchant_id"].isin(refused).any(), "their loans are in the full data set"
    usable = modelling_rows(frame)
    assert not usable["merchant_id"].isin(refused).any()


def test_pending_loans_are_never_used_for_modelling(dataset):
    frame, _ = dataset
    usable = modelling_rows(frame)
    assert usable["label"].isin([0, 1]).all()
    assert (usable["label_status"] == "labelled").all()
    assert len(usable) < len(frame)


def test_the_summary_accounts_for_every_loan(dataset):
    frame, _ = dataset
    summary = dataset_summary(frame)
    assert summary["loans"] == len(frame)
    assert summary["used_for_modelling"] == len(modelling_rows(frame))
    left_out = summary["left_out_no_outcome_yet"] + summary["left_out_no_valid_consent"]
    assert summary["used_for_modelling"] + left_out == summary["loans"]
    assert summary["left_out_no_valid_consent"] > 0


def test_model_inputs_context_and_coverage_do_not_overlap(dataset):
    frame, _ = dataset
    inputs = set(model_feature_names("ABC"))
    assert len(inputs) == 10
    assert not inputs & set(CONTEXT_COLUMNS)
    assert not inputs & set(COVERAGE_COLUMNS)
    assert inputs | set(CONTEXT_COLUMNS) | set(COVERAGE_COLUMNS) <= set(frame.columns)


# --- the ledger of looks at the test period ----------------------------------------


def test_every_look_at_the_test_period_is_counted(tmp_path):
    assert read_ledger("synthetic_bd", tmp_path) == []
    assert record_test_use("synthetic_bd", "final report", "model v1", tmp_path) == 1
    assert record_test_use("synthetic_bd", "re-run after a fix", "model v2", tmp_path) == 2

    entries = read_ledger("synthetic_bd", tmp_path)
    assert [entry["number"] for entry in entries] == [1, 2]
    assert entries[0]["purpose"] == "final report"
    assert entries[1]["detail"] == "model v2"
    assert read_ledger("taiwan_cc", tmp_path) == [], "each data mode has its own ledger"
