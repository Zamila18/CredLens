"""Tests for the `india_ltfs` data mode: adapter, features, coverage and leakage guard.

Owner role: B (data engineer).
Implements: docs/DATASET_PLAN.md section 3 (map to the contract, nothing invented, a
    whitelist of columns known at decision time, audit columns kept apart).

The tests read tests/fixtures/india_ltfs/train.csv: eight hand-made loans with the 41
columns of the real file. The last test reads the real file when it is on the machine.
"""

from __future__ import annotations

import copy
import shutil
from pathlib import Path

import pandas as pd
import pytest

from src.adapters.base import CONTRACT, SOURCE_RECORDS, check_frame
from src.adapters.india_ltfs import FILE_NAME, RAW_FOLDER, IndiaLtfsAdapter
from src.config import coverage_weights_for_mode, load_config
from src.features.dictionary import (
    detail_text,
    expected_directions,
    features_for_mode,
    load_dictionary,
)
from src.features.india_ltfs import (
    BLACKLIST,
    CONTEXT_COLUMNS,
    COVERAGE_COLUMNS,
    MODEL_INPUTS,
    OUTCOME_COLUMN,
    WHITELIST,
    india_features,
    months_from_text,
)
from src.model.dataset import build_dataset, modelling_rows
from src.model.score import NEEDS_MORE_INFO, STRONG, band_for, coverage_for_rows
from src.model.split import TIME_SPLIT, split_for_mode

FIXTURE_FOLDER = Path(__file__).parent / "fixtures" / "india_ltfs"
MODE = "india_ltfs"
BUREAU_INPUTS = [name for name in MODEL_INPUTS if name != "down_payment_share"]


@pytest.fixture(scope="module")
def config() -> dict:
    config = copy.deepcopy(load_config())
    config["data"]["mode"] = MODE
    return config


@pytest.fixture(scope="module")
def adapter(config) -> IndiaLtfsAdapter:
    return IndiaLtfsAdapter(config, folder=FIXTURE_FOLDER)


@pytest.fixture(scope="module")
def tables(adapter) -> dict:
    return adapter.load_all()


@pytest.fixture(scope="module")
def features(tables, config) -> pd.DataFrame:
    return india_features(tables[SOURCE_RECORDS], config).set_index("merchant_id")


# --- the adapter fills the contract and invents nothing ----------------------------------


def test_the_seven_tables_match_the_contract(tables):
    for table in CONTRACT:
        check_frame(table, tables[table])
    assert len(tables["merchants"]) == len(tables["loans"]) == len(tables["consents"]) == 8
    assert tables["merchants"]["merchant_id"].tolist()[:2] == ["IN1001", "IN1002"]
    assert tables["loans"]["loan_id"].tolist()[:2] == ["INL1001", "INL1002"]


def test_streams_the_source_lacks_stay_empty(tables):
    for table in ("purchases", "deliveries", "payments", "questionnaire"):
        assert tables[table].empty, table
    for column in ("district", "town_tier", "shop_type", "has_trade_license"):
        assert tables["merchants"][column].isna().all(), "the source has no such field"


def test_dates_are_read_day_first_and_the_label_is_one_minus_default(tables):
    loans = tables["loans"].set_index("merchant_id")
    assert loans.loc["IN1001", "issued_at"] == "2018-08-03"  # the file says 03-08-18
    assert loans.loc["IN1003", "issued_at"] == "2018-09-10"
    assert loans.loc["IN1003", "label_observed_at"] == "2018-10-10"
    assert loans["outcome_label"].tolist() == [1, 1, 0, 1, 0, 1, 0, 1]
    assert loans.loc["IN1002", "limit_bdt"] == 40000


def test_audit_columns_are_kept_apart(adapter, tables, features):
    audit = adapter.audit_frame().set_index("merchant_id")
    assert list(audit.columns) == load_config()["fairness"]["audit_only_columns"][MODE]
    assert list(audit.columns) == ["age_band", "State_ID", "Employment.Type"]
    assert audit.loc["IN1001", "age_band"] == "25 to 34"  # born 1990
    assert audit.loc["IN1005", "age_band"] == "under 25"  # born 1999
    assert audit.loc["IN1003", "age_band"] == "45 to 54", "born 31-12-64 means 1964, not 2064"
    assert audit.loc["IN1004", "Employment.Type"] == "not stated"
    for column in ("Date.of.Birth", "Employment.Type", "State_ID", "age_band", "age_years"):
        assert column not in tables[SOURCE_RECORDS].columns
        assert column not in features.columns


# --- leakage guard ------------------------------------------------------------------------


def test_source_records_hold_only_whitelisted_columns(tables):
    assert list(tables[SOURCE_RECORDS].columns) == ["loan_id", "merchant_id", *WHITELIST]
    assert not set(BLACKLIST) & set(tables[SOURCE_RECORDS].columns)


@pytest.mark.parametrize("planted", BLACKLIST)
def test_a_blacklisted_column_is_refused_by_the_feature_builder(planted, tables, config):
    """A planted leak: the outcome, a group column or a branch / employee identifier."""
    leaky = tables[SOURCE_RECORDS].copy()
    leaky[planted] = 1
    with pytest.raises(ValueError, match="whitelisted"):
        india_features(leaky, config)


def test_features_do_not_change_when_the_outcome_changes(config, tmp_path, features):
    raw = pd.read_csv(FIXTURE_FOLDER / FILE_NAME)
    raw[OUTCOME_COLUMN] = 1 - raw[OUTCOME_COLUMN]
    raw.to_csv(tmp_path / FILE_NAME, index=False)
    flipped = IndiaLtfsAdapter(config, folder=tmp_path).load_all()
    again = india_features(flipped[SOURCE_RECORDS], config).set_index("merchant_id")
    pd.testing.assert_frame_equal(again, features)
    assert flipped["loans"]["outcome_label"].tolist() == [0, 0, 1, 0, 1, 0, 1, 0]


def test_model_inputs_are_behaviour_only(features):
    assert not set(MODEL_INPUTS) & set(CONTEXT_COLUMNS)
    assert not set(MODEL_INPUTS) & set(COVERAGE_COLUMNS)
    for amount_of_data in ("earlier_loans", "credit_history_months", "loan_amount"):
        assert amount_of_data in CONTEXT_COLUMNS
    expected = ["loan_id", "cutoff_date", *MODEL_INPUTS, *CONTEXT_COLUMNS, *COVERAGE_COLUMNS]
    assert list(features.columns) == expected


# --- feature values, worked by hand from the fixture --------------------------------------


def test_durations_written_as_text_become_months():
    text = pd.Series(["0yrs 0mon", "1yrs 11mon", "8yrs 4mon"])
    assert months_from_text(text).tolist() == [0, 23, 100]


def test_a_borrower_with_no_bureau_record_has_empty_bureau_features(features):
    """Nothing is known, so nothing is assumed: empty, never "zero overdue loans"."""
    row = features.loc["IN1001"]
    assert row["down_payment_share"] == pytest.approx(0.20)  # loan-to-value 80%
    assert row[BUREAU_INPUTS].isna().all()
    assert row["earlier_loans"] == 0 and row["credit_history_months"] == 0


def test_a_clean_long_record(features):
    row = features.loc["IN1002"]
    assert row["down_payment_share"] == pytest.approx(0.50)
    assert row["bureau_score"] == 780
    assert row["overdue_account_share"] == 0
    assert row["delinquent_accounts_6m"] == 0 and row["new_accounts_6m"] == 0
    assert row["loan_enquiries"] == 0
    assert row["credit_history_months"] == 62 and row["average_account_age_months"] == 30


def test_a_record_with_overdue_loans(features):
    """Three own loans and one as guarantor; one of each is overdue."""
    row = features.loc["IN1003"]
    assert row["overdue_account_share"] == pytest.approx(2 / 4)
    assert row["delinquent_accounts_6m"] == 1 and row["new_accounts_6m"] == 2
    assert row["loan_enquiries"] == 3 and row["bureau_score"] == 350
    assert row["earlier_loans"] == 4


def test_a_record_the_bureau_could_not_score_has_no_score_feature(features):
    """The file carries small codes such as 15 for "not scored": they are not scores."""
    row = features.loc["IN1004"]
    assert pd.isna(row["bureau_score"])
    assert row["overdue_account_share"] == 0 and row["new_accounts_6m"] == 1


def test_a_record_without_earlier_loans_has_no_overdue_share(features):
    row = features.loc["IN1005"]
    assert pd.isna(row["overdue_account_share"]), "no earlier loans, so no share"
    assert row["loan_enquiries"] == 2, "the record exists, so the enquiries are known"


# --- coverage and band ---------------------------------------------------------------------


def test_coverage_columns_match_the_config_weights(config):
    weights = coverage_weights_for_mode(config, MODE)
    assert [f"cov_{name}" for name in weights] == COVERAGE_COLUMNS
    assert sum(weights.values()) == pytest.approx(1.0)


def test_thin_files_get_low_coverage_and_needs_more_info(config, features):
    coverage = coverage_for_rows(features, config, MODE)
    assert coverage["IN1001"] == pytest.approx(0.20), "only the loan terms are known"
    assert coverage["IN1002"] == 1.0
    assert coverage["IN1004"] == pytest.approx(0.60), "a record, but short and not scored"
    assert coverage["IN1006"] == 1.0, "a history of exactly 12 months is long enough"
    assert band_for(95, coverage["IN1001"], config, MODE) == NEEDS_MORE_INFO
    assert band_for(95, coverage["IN1002"], config, MODE) == STRONG


# --- the shared pipeline takes it from here -------------------------------------------------


def test_build_dataset_uses_the_source_features_and_the_stated_outcomes(tables, config):
    dataset = build_dataset(tables, config)
    assert len(dataset) == 8
    assert (dataset["label_status"] == "labelled").all()
    assert (dataset["label_source"] == "source").all()
    assert dataset["consent_valid"].all()
    usable = modelling_rows(dataset).set_index("merchant_id")
    assert usable.loc["IN1003", "label"] == 0 and usable.loc["IN1002", "label"] == 1


def test_the_split_is_by_month_of_disbursal(tables, config):
    """August trains, September validates, October is the held-back test month."""
    rows = modelling_rows(build_dataset(tables, config))
    split = split_for_mode(rows, config, MODE)
    assert split.method == TIME_SPLIT
    assert sorted(split.train["merchant_id"]) == ["IN1001", "IN1002", "IN1008"]
    assert sorted(split.validation["merchant_id"]) == ["IN1003", "IN1004"]
    assert sorted(split.test["merchant_id"]) == ["IN1005", "IN1006", "IN1007"]


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
            assert "shop" not in sentences["en"].lower(), "these are borrowers, not shops"
        for sentences in (entry.get("otherwise") or {}).values():
            assert "similar borrowers" in sentences["en"], name
        assert detail_text(entry, 0.5, 0.4), name


# --- reading the file -----------------------------------------------------------------------


def test_a_missing_file_says_where_to_put_it(config, tmp_path):
    with pytest.raises(FileNotFoundError, match="Kaggle"):
        IndiaLtfsAdapter(config, folder=tmp_path).load_merchants()


def test_a_file_with_the_wrong_columns_is_refused(config, tmp_path):
    pd.DataFrame({"UniqueID": [1], "ltv": [80]}).to_csv(tmp_path / FILE_NAME, index=False)
    with pytest.raises(ValueError, match="Missing columns"):
        IndiaLtfsAdapter(config, folder=tmp_path).load_merchants()


def test_a_sample_is_the_same_every_time(config, tmp_path):
    shutil.copy(FIXTURE_FOLDER / FILE_NAME, tmp_path / FILE_NAME)
    sampled = copy.deepcopy(config)
    sampled["data"][MODE]["sample_size"] = 3
    first = IndiaLtfsAdapter(sampled, folder=tmp_path).load_merchants()
    second = IndiaLtfsAdapter(sampled, folder=tmp_path).load_merchants()
    assert len(first) == 3
    assert first["merchant_id"].tolist() == second["merchant_id"].tolist()


HAS_REAL_FILE = (RAW_FOLDER / FILE_NAME).exists()


@pytest.mark.skipif(not HAS_REAL_FILE, reason="the real Kaggle file is not here")
def test_the_real_file_reads_as_documented(config):
    """Only on a machine that has the download: 233,154 loans, 21.7% missed the first EMI."""
    adapter = IndiaLtfsAdapter(config)
    tables = adapter.load_all()
    assert len(tables["loans"]) == 233154
    assert 1 - tables["loans"]["outcome_label"].mean() == pytest.approx(0.2171, abs=0.0001)
    assert tables["loans"]["issued_at"].min() == "2018-08-01"
    assert tables["loans"]["issued_at"].max() == "2018-10-31"
    features = india_features(tables[SOURCE_RECORDS], config)
    assert features["down_payment_share"].between(0, 1).all()
    assert features["cov_bureau_record_present"].mean() == pytest.approx(0.498, abs=0.002)
    assert "nan" not in set(adapter.audit_frame()["age_band"]), "every date of birth was read"
