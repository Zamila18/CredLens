"""Tests for the `taiwan_cc` data mode: adapter, features, coverage and leakage guard.

Owner role: B (data engineer).
Implements: docs/DATASET_PLAN.md section 3 (map to the contract, nothing invented, a
    whitelist of columns known at decision time, audit columns kept apart).

The tests read tests/fixtures/taiwan_cc/sample.csv: eight hand-made clients with the
columns of the real file. The last test reads the real file when it is on the machine.
"""

from __future__ import annotations

import copy
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.adapters.base import CONTRACT, SOURCE_RECORDS, check_frame
from src.adapters.taiwan_cc import RAW_FOLDER, TaiwanCreditCardAdapter
from src.config import coverage_weights_for_mode, load_config
from src.features.dictionary import (
    detail_text,
    expected_directions,
    features_for_mode,
    load_dictionary,
)
from src.features.source_features import build_source_features
from src.features.taiwan_cc import (
    BLACKLIST,
    CONTEXT_COLUMNS,
    COVERAGE_COLUMNS,
    MODEL_INPUTS,
    OUTCOME_COLUMN,
    WHITELIST,
    taiwan_features,
)
from src.model.dataset import build_dataset, modelling_rows
from src.model.labels import build_labels
from src.model.score import NEEDS_MORE_INFO, band_for, coverage_for_rows

FIXTURE_FOLDER = Path(__file__).parent / "fixtures" / "taiwan_cc"
MODE = "taiwan_cc"


@pytest.fixture(scope="module")
def config() -> dict:
    config = copy.deepcopy(load_config())
    config["data"]["mode"] = MODE
    return config


@pytest.fixture(scope="module")
def adapter(config) -> TaiwanCreditCardAdapter:
    return TaiwanCreditCardAdapter(config, folder=FIXTURE_FOLDER)


@pytest.fixture(scope="module")
def tables(adapter) -> dict:
    return adapter.load_all()


@pytest.fixture(scope="module")
def features(tables, config) -> pd.DataFrame:
    return taiwan_features(tables[SOURCE_RECORDS], config).set_index("merchant_id")


# --- the adapter fills the contract and invents nothing ----------------------------------


def test_the_seven_tables_match_the_contract(tables):
    for table in CONTRACT:
        check_frame(table, tables[table])
    assert len(tables["merchants"]) == len(tables["loans"]) == len(tables["consents"]) == 8
    assert tables["merchants"]["merchant_id"].tolist()[:2] == ["TW000001", "TW000002"]
    assert tables["loans"]["loan_id"].is_unique


def test_streams_the_source_lacks_stay_empty(tables):
    for table in ("purchases", "deliveries", "questionnaire"):
        assert tables[table].empty, table
    merchants = tables["merchants"]
    for column in ("district", "town_tier", "shop_type", "has_trade_license"):
        assert merchants[column].isna().all(), "the source has no such field"


def test_the_label_is_one_minus_default(tables):
    loans = tables["loans"].set_index("merchant_id")
    assert loans.loc["TW000001", "outcome_label"] == 1  # did not default
    assert loans.loc["TW000002", "outcome_label"] == 0  # defaulted
    assert loans["outcome_label"].tolist() == [1, 0, 1, 1, 1, 0, 1, 0]
    assert loans.loc["TW000002", "limit_bdt"] == 50000


def test_payments_are_the_six_monthly_statements(tables):
    payments = tables["payments"]
    assert len(payments) == 8 * 6
    assert payments.groupby("merchant_id").size().eq(6).all()
    assert set(payments["loan_id"]) <= set(tables["loans"]["loan_id"])
    second = payments[payments["merchant_id"] == "TW000002"].set_index("due_date")
    assert second.loc["2005-09-30", "amount_due_bdt"] == 40000
    assert second.loc["2005-04-30", "amount_due_bdt"] == 10000
    assert second.loc["2005-07-31", "amount_paid_bdt"] == 1000
    assert second.loc["2005-07-31", "paid_date"] == "2005-07-31"
    assert pd.isna(second.loc["2005-09-30", "paid_date"]), "nothing was paid that month"
    fourth = payments[payments["merchant_id"] == "TW000004"].set_index("due_date")
    assert fourth.loc["2005-07-31", "amount_due_bdt"] == 0, "a credit balance is not a bill"


def test_audit_columns_are_kept_apart(adapter, tables, features):
    audit = adapter.audit_frame().set_index("merchant_id")
    assert list(audit.columns) == load_config()["fairness"]["audit_only_columns"][MODE]
    assert list(audit.columns) == ["SEX", "EDUCATION", "MARRIAGE", "age_band"]
    assert audit.loc["TW000001", "age_band"] == "under 30"
    assert audit.loc["TW000005", "age_band"] == "30 to 39"
    assert audit.loc["TW000008", "age_band"] == "50 and over"
    for column in ("SEX", "EDUCATION", "MARRIAGE", "AGE", "age_band"):
        assert column not in tables[SOURCE_RECORDS].columns
        assert column not in features.columns


# --- leakage guard ------------------------------------------------------------------------


def test_source_records_hold_only_whitelisted_columns(tables):
    assert list(tables[SOURCE_RECORDS].columns) == ["loan_id", "merchant_id", *WHITELIST]
    assert not set(BLACKLIST) & set(tables[SOURCE_RECORDS].columns)


@pytest.mark.parametrize("planted", BLACKLIST)
def test_a_blacklisted_column_is_refused_by_the_feature_builder(planted, tables, config):
    """A planted leak: the outcome or a group column slipped into the records."""
    leaky = tables[SOURCE_RECORDS].copy()
    leaky[planted] = 1
    with pytest.raises(ValueError, match="whitelisted"):
        taiwan_features(leaky, config)


def test_features_do_not_change_when_the_outcome_changes(config, tmp_path, features):
    """Flip every outcome in the file: no feature may move."""
    raw = pd.read_csv(FIXTURE_FOLDER / "sample.csv")
    raw[OUTCOME_COLUMN] = 1 - raw[OUTCOME_COLUMN]
    raw.to_csv(tmp_path / "sample.csv", index=False)
    flipped = TaiwanCreditCardAdapter(config, folder=tmp_path).load_all()
    again = taiwan_features(flipped[SOURCE_RECORDS], config).set_index("merchant_id")
    pd.testing.assert_frame_equal(again, features)
    assert flipped["loans"]["outcome_label"].tolist() == [0, 1, 0, 0, 0, 1, 0, 1]


def test_model_inputs_are_behaviour_only(features):
    assert not set(MODEL_INPUTS) & set(CONTEXT_COLUMNS)
    assert not set(MODEL_INPUTS) & set(COVERAGE_COLUMNS)
    assert "credit_limit" in CONTEXT_COLUMNS, "the limit is the lender's view, not behaviour"
    expected = ["loan_id", "cutoff_date", *MODEL_INPUTS, *CONTEXT_COLUMNS, *COVERAGE_COLUMNS]
    assert list(features.columns) == expected


# --- feature values, worked by hand from the fixture --------------------------------------


def test_a_client_who_always_pays_in_full(features):
    row = features.loc["TW000001"]
    assert row["ontime_share_6m"] == 1
    assert row["worst_delay_6m"] == 0 and row["latest_delay_months"] == 0
    assert row["delay_trend_6m"] == 0
    assert row["pay_to_bill_ratio"] == pytest.approx(1.0)  # 50,000 paid against 50,000 billed
    assert row["limit_utilisation"] == pytest.approx(0.10)
    assert row["balance_growth_6m"] == 0
    assert row["no_payment_month_share"] == 0


def test_a_client_whose_payments_are_getting_later(features):
    """Status 0, 0, 0 in April to June, then 1, 2, 2 months late."""
    row = features.loc["TW000002"]
    assert row["ontime_share_6m"] == pytest.approx(3 / 6)
    assert row["worst_delay_6m"] == 2 and row["latest_delay_months"] == 2
    assert row["delay_trend_6m"] == pytest.approx(5 / 3)
    assert row["pay_to_bill_ratio"] == pytest.approx(5000 / 110000)
    assert row["limit_utilisation"] == pytest.approx(25000 / 50000)
    assert row["balance_growth_6m"] == pytest.approx((40000 - 10000) / 50000)
    assert row["no_payment_month_share"] == pytest.approx(2 / 5)


def test_a_client_who_is_improving_has_a_negative_trend(features):
    row = features.loc["TW000005"]
    assert row["delay_trend_6m"] == pytest.approx(0 - (1 + 2 + 3) / 3)
    assert row["worst_delay_6m"] == 3 and row["latest_delay_months"] == 0


def test_a_card_that_was_never_used_gives_empty_features_not_perfect_ones(features):
    """Nothing was due, so there is nothing to be on time with: empty, never "100% on time"."""
    row = features.loc["TW000003"]
    assert row[MODEL_INPUTS].isna().all()
    assert row["months_card_used"] == 0 and row["months_with_bill"] == 0
    assert row["credit_limit"] == 200000


def test_months_without_use_and_credit_balances_are_left_out(features):
    """Used in August and September only; July shows a credit balance of 200."""
    row = features.loc["TW000004"]
    assert row["months_card_used"] == 2 and row["months_with_bill"] == 2
    assert row["ontime_share_6m"] == 1
    assert np.isnan(row["delay_trend_6m"]), "no used month among the three oldest"
    assert row["pay_to_bill_ratio"] == pytest.approx(3000 / 3000)
    assert row["limit_utilisation"] == pytest.approx((5000 + 3000) / 6 / 20000)
    assert row["no_payment_month_share"] == 0


def test_shares_stay_between_zero_and_one(features):
    for name in ("ontime_share_6m", "no_payment_month_share"):
        assert features[name].dropna().between(0, 1).all(), name
    assert (features["worst_delay_6m"].dropna() >= features["latest_delay_months"].dropna()).all()


# --- coverage and band ---------------------------------------------------------------------


def test_coverage_columns_match_the_config_weights(config, features):
    weights = coverage_weights_for_mode(config, MODE)
    assert [f"cov_{name}" for name in weights] == COVERAGE_COLUMNS
    assert sum(weights.values()) == pytest.approx(1.0)


def test_little_history_means_low_coverage_and_needs_more_info(config, features):
    coverage = coverage_for_rows(features, config, MODE)
    assert coverage["TW000001"] == 1.0
    assert coverage["TW000003"] == pytest.approx(0.15), "only the credit limit is known"
    assert coverage["TW000004"] == pytest.approx(0.40), "limit and one payment; two months of use"
    for client in ("TW000003", "TW000004"):
        assert band_for(95, coverage[client], config, MODE) == NEEDS_MORE_INFO


# --- the shared pipeline takes it from here -------------------------------------------------


def test_build_dataset_uses_the_source_features_and_the_stated_outcomes(tables, config):
    dataset = build_dataset(tables, config)
    assert len(dataset) == 8
    assert (dataset["label_status"] == "labelled").all(), "a stated outcome is never 'too young'"
    assert (dataset["label_source"] == "source").all()
    assert dataset["consent_valid"].all()
    assert set(MODEL_INPUTS) <= set(dataset.columns)
    usable = modelling_rows(dataset).set_index("merchant_id")
    assert usable.loc["TW000002", "label"] == 0 and usable.loc["TW000001", "label"] == 1


def test_statement_records_never_change_a_stated_outcome(tables, config):
    """The six statements are history. They must not be read as repayments of this loan."""
    supplied = build_labels(tables["loans"], tables["payments"], config, "2005-10-01", True)
    assert supplied["label"].tolist() == tables["loans"]["outcome_label"].tolist()


def test_an_unknown_mode_has_no_feature_builder(tables, config):
    with pytest.raises(ValueError, match="No feature builder"):
        build_source_features(tables[SOURCE_RECORDS], config, "a_mode_that_does_not_exist")


# --- dictionary entries ---------------------------------------------------------------------


def test_every_model_input_has_a_direction_and_sentences_in_both_languages():
    dictionary = load_dictionary()
    entries = features_for_mode(dictionary, MODE)
    assert list(entries) == MODEL_INPUTS
    assert set(expected_directions(dictionary, MODE)) == set(MODEL_INPUTS)
    for name, entry in entries.items():
        sides = [entry["positive"], entry["negative"], *(entry.get("otherwise") or {}).values()]
        for sentences in sides:
            assert sentences["en"].strip() and sentences["bn"].strip(), name
            assert "shop" not in sentences["en"].lower(), "these are card clients, not shops"
        for sentences in (entry.get("otherwise") or {}).values():
            assert "similar clients" in sentences["en"], name
        assert detail_text(entry, 0.5, 0.4), name


def test_the_synthetic_dictionary_is_untouched_by_the_public_entries():
    dictionary = load_dictionary()
    assert not set(MODEL_INPUTS) & set(dictionary["features"])
    synthetic = expected_directions(dictionary, "synthetic_bd")
    assert expected_directions(dictionary) == synthetic
    with pytest.raises(KeyError, match="no entries"):
        features_for_mode(dictionary, "a_mode_that_does_not_exist")


# --- reading the file -----------------------------------------------------------------------


def test_a_missing_file_says_where_to_put_it(config, tmp_path):
    with pytest.raises(FileNotFoundError, match="UCI"):
        TaiwanCreditCardAdapter(config, folder=tmp_path).load_merchants()


def test_a_file_with_the_wrong_columns_is_refused(config, tmp_path):
    pd.DataFrame({"ID": [1], "LIMIT_BAL": [1000]}).to_csv(tmp_path / "wrong.csv", index=False)
    with pytest.raises(ValueError, match="Missing columns"):
        TaiwanCreditCardAdapter(config, folder=tmp_path).load_merchants()


def test_a_sample_is_the_same_every_time(config, tmp_path):
    shutil.copy(FIXTURE_FOLDER / "sample.csv", tmp_path / "sample.csv")
    sampled = copy.deepcopy(config)
    sampled["data"][MODE]["sample_size"] = 3
    first = TaiwanCreditCardAdapter(sampled, folder=tmp_path).load_merchants()
    second = TaiwanCreditCardAdapter(sampled, folder=tmp_path).load_merchants()
    assert len(first) == 3
    assert first["merchant_id"].tolist() == second["merchant_id"].tolist()


@pytest.mark.skipif(not any(RAW_FOLDER.glob("*.xls")), reason="the real UCI file is not here")
def test_the_real_file_reads_as_documented(config):
    """Only on a machine that has the download: 30,000 clients, 22.1% defaulted."""
    tables = TaiwanCreditCardAdapter(config).load_all()
    assert len(tables["loans"]) == 30000
    assert 1 - tables["loans"]["outcome_label"].mean() == pytest.approx(0.2212, abs=0.0001)
    features = taiwan_features(tables[SOURCE_RECORDS], config)
    assert features["loan_id"].is_unique and len(features) == 30000
    assert features["ontime_share_6m"].dropna().between(0, 1).all()
