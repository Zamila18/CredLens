"""Tests for the `homecredit` data mode: adapter, features, coverage and leakage guard.

Owner role: B (data engineer).
Implements: docs/DATASET_PLAN.md section 3 (map to the contract, nothing invented, only
    history dated before the application, audit columns kept apart) and the rule that
    this source is always labelled "country not stated".

The tests read tests/fixtures/homecredit/: six hand-made applicants with their earlier
instalments and monthly loan records. The last test reads the real files when they are
on the machine.
"""

from __future__ import annotations

import copy
import shutil
from pathlib import Path

import pandas as pd
import pytest

from src.adapters.base import CONTRACT, SOURCE_RECORDS, check_frame
from src.adapters.homecredit import (
    APPLICATION_FILE,
    DERIVED_FOLDER,
    INSTALMENT_FILE,
    POS_FILE,
    RAW_FOLDER,
    HomeCreditAdapter,
)
from src.config import banner_text, coverage_weights_for_mode, load_config
from src.features.dictionary import (
    detail_text,
    expected_directions,
    features_for_mode,
    load_dictionary,
)
from src.features.homecredit import (
    BLACKLIST,
    CONTEXT_COLUMNS,
    COVERAGE_COLUMNS,
    EXTERNAL_INPUTS,
    MODEL_INPUTS,
    OUTCOME_COLUMN,
    WHITELIST,
    homecredit_features,
)
from src.model.dataset import build_dataset, modelling_rows
from src.model.score import NEEDS_MORE_INFO, STRONG, band_for, coverage_for_rows
from src.model.split import RANDOM_SPLIT, split_for_mode

FIXTURE_FOLDER = Path(__file__).parent / "fixtures" / "homecredit"
MODE = "homecredit"
HISTORY_INPUTS = [name for name in MODEL_INPUTS if name.startswith(("inst_", "pos_"))]
ALL_FILES = (APPLICATION_FILE, INSTALMENT_FILE, POS_FILE)


@pytest.fixture(scope="module")
def config() -> dict:
    config = copy.deepcopy(load_config())
    config["data"]["mode"] = MODE
    return config


@pytest.fixture(scope="module")
def adapter(config) -> HomeCreditAdapter:
    return HomeCreditAdapter(config, folder=FIXTURE_FOLDER, use_cache=False)


@pytest.fixture(scope="module")
def tables(adapter) -> dict:
    return adapter.load_all()


@pytest.fixture(scope="module")
def records(tables) -> pd.DataFrame:
    return tables[SOURCE_RECORDS].set_index("merchant_id")


@pytest.fixture(scope="module")
def features(tables, config) -> pd.DataFrame:
    return homecredit_features(tables[SOURCE_RECORDS], config).set_index("merchant_id")


# --- the adapter fills the contract and invents nothing ----------------------------------


def test_the_seven_tables_match_the_contract(tables):
    for table in CONTRACT:
        check_frame(table, tables[table])
    assert len(tables["merchants"]) == len(tables["loans"]) == len(tables["consents"]) == 6
    assert tables["merchants"]["merchant_id"].tolist()[:2] == ["HC100001", "HC100002"]
    assert tables["loans"]["outcome_label"].tolist() == [1, 0, 1, 1, 0, 1], "1 = no difficulties"


def test_streams_the_source_lacks_stay_empty(tables):
    for table in ("purchases", "deliveries", "questionnaire", "payments"):
        assert tables[table].empty, table
    for column in ("district", "town_tier", "shop_type", "has_trade_license"):
        assert tables["merchants"][column].isna().all(), "the source has no such field"


def test_the_country_is_never_claimed():
    assert "country not stated" in banner_text(MODE)
    assert "Asia" not in banner_text(MODE)


def test_audit_columns_are_kept_apart(adapter, tables, features):
    audit = adapter.audit_frame().set_index("merchant_id")
    assert list(audit.columns) == load_config()["fairness"]["audit_only_columns"][MODE]
    assert list(audit.columns) == ["CODE_GENDER", "age_band", "REGION_RATING_CLIENT"]
    assert audit.loc["HC100001", "age_band"] == "30 to 39"  # 12,000 days is 32.9 years
    assert audit.loc["HC100003", "age_band"] == "under 30"
    assert audit.loc["HC100005", "age_band"] == "60 and over"
    for column in ("CODE_GENDER", "DAYS_BIRTH", "REGION_RATING_CLIENT", "age_band"):
        assert column not in tables[SOURCE_RECORDS].columns
        assert column not in features.columns


def test_other_descriptions_of_the_person_are_never_read(tables):
    """The file has occupation and many more; the adapter does not even load them."""
    assert "OCCUPATION_TYPE" not in tables[SOURCE_RECORDS].columns


# --- earlier instalments, counted by hand from the fixture ----------------------------------


def test_someone_else_s_history_is_ignored(records):
    """Client 999999 is in the history files but is not an applicant."""
    assert records["inst_count"].sum() == 3 + 4 + 1 + 14


def test_instalments_paid_on_time_and_in_full(records, features):
    assert records.loc["HC100001", "inst_count"] == 3
    row = features.loc["HC100001"]
    assert row["inst_ontime_rate"] == 1, "paying five days early is on time"
    assert row["inst_mean_days_late"] == 0
    assert row["inst_late_30d_share"] == 0 and row["inst_paid_short_share"] == 0
    assert row["inst_recent_ontime_rate"] == 1
    assert row["pos_months_overdue_share"] == 0


def test_late_unpaid_and_part_paid_instalments(records, features):
    """Four instalments: 10 days late; 40 days late; never paid (due 340 days ago); and
    one paid on time in two parts of 500, which is one instalment paid in full."""
    assert records.loc["HC100002", "inst_count"] == 4, "two part-payments are one instalment"
    row = features.loc["HC100002"]
    assert row["inst_ontime_rate"] == pytest.approx(1 / 4)
    assert row["inst_mean_days_late"] == pytest.approx((10 + 40 + 340 + 0) / 4)
    assert row["inst_late_30d_share"] == pytest.approx(2 / 4)
    assert row["inst_paid_short_share"] == pytest.approx(1 / 4), "only the unpaid one"
    # Due in the last 365 days: the unpaid one (340 days ago) and the last one.
    assert row["inst_recent_ontime_rate"] == pytest.approx(1 / 2)
    assert row["pos_months_overdue_share"] == pytest.approx(2 / 4)


def test_an_instalment_paid_short(features):
    row = features.loc["HC100004"]
    assert row["inst_paid_short_share"] == 1 and row["inst_ontime_rate"] == 1
    assert pd.isna(row["pos_months_overdue_share"]), "no monthly records for this applicant"


def test_an_applicant_with_no_earlier_loans_has_empty_history_features(features):
    """Nothing is known, so nothing is assumed: empty, never "100% on time"."""
    row = features.loc["HC100003"]
    assert row[HISTORY_INPUTS].isna().all()
    assert row["past_instalments"] == 0 and row["pos_months_recorded"] == 0
    assert pd.isna(row["external_score"]), "no outside score in the file either"
    assert row["annuity_to_income"] == pytest.approx(5000 / 80000)


def test_the_loan_terms_and_the_outside_score(features):
    assert features.loc["HC100001", "annuity_to_income"] == pytest.approx(0.10)
    assert features.loc["HC100002", "credit_to_goods_ratio"] == pytest.approx(90000 / 75000)
    assert features.loc["HC100001", "external_score"] == pytest.approx((0.6 + 0.7 + 0.8) / 3)
    assert features.loc["HC100002", "external_score"] == pytest.approx(0.3), "one of three known"
    assert features.loc["HC100004", "external_score"] == pytest.approx((0.5 + 0.4) / 2)
    assert pd.isna(features.loc["HC100005", "credit_to_goods_ratio"]), "no goods price"
    assert pd.isna(features.loc["HC100006", "annuity_to_income"]), "an income of zero"


# --- leakage guard ------------------------------------------------------------------------


def test_source_records_hold_only_whitelisted_columns(tables):
    expected = ["loan_id", "merchant_id", "cutoff_date", *WHITELIST]
    assert list(tables[SOURCE_RECORDS].columns) == expected
    assert not set(BLACKLIST) & set(tables[SOURCE_RECORDS].columns)


@pytest.mark.parametrize("planted", [*BLACKLIST, "OCCUPATION_TYPE"])
def test_a_blacklisted_column_is_refused_by_the_feature_builder(planted, tables, config):
    leaky = tables[SOURCE_RECORDS].copy()
    leaky[planted] = 1
    with pytest.raises(ValueError, match="whitelisted"):
        homecredit_features(leaky, config)


def copy_fixture(target: Path) -> None:
    for name in ALL_FILES:
        shutil.copy(FIXTURE_FOLDER / name, target / name)


def test_history_dated_after_the_application_stops_the_build(config, tmp_path):
    """A planted leak: an instalment row from the future of the application."""
    copy_fixture(tmp_path)
    rows = pd.read_csv(tmp_path / INSTALMENT_FILE)
    rows.loc[0, "DAYS_INSTALMENT"] = 15
    rows.to_csv(tmp_path / INSTALMENT_FILE, index=False)
    with pytest.raises(ValueError, match="on or after the application"):
        HomeCreditAdapter(config, folder=tmp_path, use_cache=False).load_all()


def test_monthly_records_dated_after_the_application_stop_the_build(config, tmp_path):
    copy_fixture(tmp_path)
    rows = pd.read_csv(tmp_path / POS_FILE)
    rows.loc[0, "MONTHS_BALANCE"] = 1
    rows.to_csv(tmp_path / POS_FILE, index=False)
    with pytest.raises(ValueError, match="on or after the application"):
        HomeCreditAdapter(config, folder=tmp_path, use_cache=False).load_all()


def test_working_through_the_applicants_in_batches_gives_the_same_counts(config, records):
    """With every applicant in use the history is built in several passes to bound memory."""
    batched = copy.deepcopy(config)
    batched["data"][MODE]["applicants_per_pass"] = 2
    again = HomeCreditAdapter(batched, folder=FIXTURE_FOLDER, use_cache=False).source_records()
    pd.testing.assert_frame_equal(again.set_index("merchant_id"), records)


def test_features_do_not_change_when_the_outcome_changes(config, tmp_path, features):
    copy_fixture(tmp_path)
    raw = pd.read_csv(tmp_path / APPLICATION_FILE)
    raw[OUTCOME_COLUMN] = 1 - raw[OUTCOME_COLUMN]
    raw.to_csv(tmp_path / APPLICATION_FILE, index=False)
    flipped = HomeCreditAdapter(config, folder=tmp_path, use_cache=False).load_all()
    again = homecredit_features(flipped[SOURCE_RECORDS], config).set_index("merchant_id")
    pd.testing.assert_frame_equal(again, features)
    assert flipped["loans"]["outcome_label"].tolist() == [0, 1, 0, 0, 1, 0]


def test_model_inputs_are_behaviour_only(features):
    assert not set(MODEL_INPUTS) & set(CONTEXT_COLUMNS)
    assert not set(MODEL_INPUTS) & set(COVERAGE_COLUMNS)
    assert "past_instalments" in CONTEXT_COLUMNS and "stated_income" in CONTEXT_COLUMNS
    assert EXTERNAL_INPUTS == ["external_score"], "kept apart so a run can leave it out"
    expected = ["loan_id", "cutoff_date", *MODEL_INPUTS, *CONTEXT_COLUMNS, *COVERAGE_COLUMNS]
    assert list(features.columns) == expected


# --- coverage, band, and the shared pipeline ------------------------------------------------


def test_coverage_columns_match_the_config_weights(config):
    weights = coverage_weights_for_mode(config, MODE)
    assert [f"cov_{name}" for name in weights] == COVERAGE_COLUMNS
    assert sum(weights.values()) == pytest.approx(1.0)


def test_little_history_means_low_coverage_and_needs_more_info(config, features):
    coverage = coverage_for_rows(features, config, MODE)
    assert coverage["HC100003"] == pytest.approx(0.20), "only the application is known"
    assert coverage["HC100001"] == pytest.approx(0.75), "history, but only three instalments"
    assert coverage["HC100005"] == 1.0, "fourteen earlier instalments"
    assert coverage["HC100006"] == 0, "not even a usable application: income is zero"
    assert band_for(95, coverage["HC100003"], config, MODE) == NEEDS_MORE_INFO
    assert band_for(95, coverage["HC100005"], config, MODE) == STRONG


def test_build_dataset_and_a_random_split_marked_weaker(tables, config):
    dataset = build_dataset(tables, config)
    assert (dataset["label_status"] == "labelled").all()
    assert (dataset["label_source"] == "source").all() and dataset["consent_valid"].all()
    split = split_for_mode(modelling_rows(dataset), config, MODE)
    assert split.method == RANDOM_SPLIT
    assert "Weaker split" in split.note, "this source has no calendar dates"


def test_every_model_input_has_a_direction_and_sentences_in_both_languages():
    dictionary = load_dictionary()
    entries = features_for_mode(dictionary, MODE)
    assert list(entries) == MODEL_INPUTS
    assert set(expected_directions(dictionary, MODE)) == set(MODEL_INPUTS)
    for name, entry in entries.items():
        sides = [entry["positive"], entry["negative"], *(entry.get("otherwise") or {}).values()]
        for sentences in sides:
            assert sentences["en"].strip() and sentences["bn"].strip(), name
        for sentences in (entry.get("otherwise") or {}).values():
            assert "similar applicants" in sentences["en"], name
        assert detail_text(entry, 0.5, 0.4), name
    assert entries["external_score"]["group"] == "X"


# --- reading the files ----------------------------------------------------------------------


def test_a_missing_file_says_where_to_put_it(config, tmp_path):
    with pytest.raises(FileNotFoundError, match="competition rules"):
        HomeCreditAdapter(config, folder=tmp_path, use_cache=False).load_merchants()


def test_reading_in_small_chunks_gives_the_same_counts(config, records):
    """The real files are read a million rows at a time; a chunk edge must change nothing."""
    tiny = copy.deepcopy(config)
    tiny["data"][MODE]["chunk_rows"] = 2
    again = HomeCreditAdapter(tiny, folder=FIXTURE_FOLDER, use_cache=False).source_records()
    pd.testing.assert_frame_equal(again.set_index("merchant_id"), records)


def test_a_sample_reads_only_the_sampled_applicants(config, tmp_path):
    copy_fixture(tmp_path)
    sampled = copy.deepcopy(config)
    sampled["data"][MODE]["sample_size"] = 3
    first = HomeCreditAdapter(sampled, folder=tmp_path, use_cache=False).source_records()
    second = HomeCreditAdapter(sampled, folder=tmp_path, use_cache=False).source_records()
    assert len(first) == 3
    pd.testing.assert_frame_equal(first, second)


def test_the_saved_history_counts_are_reused_and_equal(config, tmp_path, records):
    copy_fixture(tmp_path)
    first = HomeCreditAdapter(config, folder=tmp_path).source_records()
    saved = list((tmp_path / DERIVED_FOLDER).glob("history_*.csv"))
    assert len(saved) == 1
    # A second adapter finds the saved counts and must give exactly the same records.
    second_adapter = HomeCreditAdapter(config, folder=tmp_path)
    second = second_adapter.source_records()
    pd.testing.assert_frame_equal(first, second)
    pd.testing.assert_frame_equal(second.set_index("merchant_id"), records)


HAS_REAL_FILES = all((RAW_FOLDER / name).exists() for name in ALL_FILES)


@pytest.mark.skipif(not HAS_REAL_FILES, reason="the real Kaggle files are not here")
def test_the_real_files_read_as_documented(config):
    """Only on a machine that has the download: a seeded sample of 50,000 applicants."""
    tables = HomeCreditAdapter(config).load_all()
    assert len(tables["loans"]) == config["data"][MODE]["sample_size"]
    assert 1 - tables["loans"]["outcome_label"].mean() == pytest.approx(0.0807, abs=0.005)
    features = homecredit_features(tables[SOURCE_RECORDS], config)
    for name in ("inst_ontime_rate", "inst_late_30d_share", "pos_months_overdue_share"):
        assert features[name].dropna().between(0, 1).all(), name
    assert features["cov_instalment_history_present"].mean() == pytest.approx(0.948, abs=0.01)
