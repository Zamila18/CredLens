"""Tests for the `kiva_asia` data mode: adapter, features, coverage and leakage guard.

Owner role: B (data engineer).
Implements: docs/DATASET_PLAN.md section 3 (map to the contract, nothing invented, only
    what was known when the loan was posted, audit columns kept apart, personal data
    dropped).

A tiny zip with the shape of Kiva's snapshot is built for each test run (zip files are
not kept in git). Its loans are hand-made; the names and stories in it are the word
SECRET, so a test can check that none of it survives. The last test reads the real
archive when it is on the machine.
"""

from __future__ import annotations

import copy
import json
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from src.adapters.base import CONTRACT, SOURCE_RECORDS, check_frame
from src.adapters.kiva_asia import (
    ARCHIVE_NAME,
    DERIVED_FOLDER,
    RAW_FOLDER,
    KivaAsiaAdapter,
    partner_track_record,
)
from src.config import coverage_weights_for_mode, load_config
from src.features.dictionary import (
    detail_text,
    expected_directions,
    features_for_mode,
    load_dictionary,
)
from src.features.kiva_asia import (
    BLACKLIST,
    CONTEXT_COLUMNS,
    COVERAGE_COLUMNS,
    MODEL_INPUTS,
    PARTNER_INPUTS,
    WHITELIST,
    kiva_features,
)
from src.model.dataset import build_dataset, modelling_rows
from src.model.score import NEEDS_MORE_INFO, STRONG, band_for, coverage_for_rows
from src.model.split import TIME_SPLIT, split_for_mode

MODE = "kiva_asia"


PH, KH = "Philippines", "Cambodia"


def loan(number, status, posted, paid, disbursed, sector, country, partner, genders, covers="lender"):  # noqa: E501
    """One loan in the snapshot's shape, with personal fields that must never be kept."""
    return {
        "id": number,
        "name": "SECRET NAME",
        "status": status,
        "posted_date": f"{posted}T10:00:00Z",
        "paid_date": f"{paid}T10:00:00Z" if paid else None,
        "funded_amount": 500,
        "lender_count": 12,
        "delinquent": status == "defaulted",
        "sector": sector,
        "activity": "General Store",
        "use": "to buy stock",
        "loan_amount": 500,
        "partner_id": partner,
        "location": {"country": country, "country_code": "XX", "town": "SECRET TOWN"},
        "description": {"languages": ["en"], "texts": {"en": "SECRET STORY" if paid else ""}},
        "borrowers": [{"first_name": "SECRET", "gender": g, "pictured": True} for g in genders],
        "terms": {
            "disbursal_date": f"{disbursed}T07:00:00Z",
            "repayment_term": 6,
            "repayment_interval": "Monthly",
            "loss_liability": {"nonpayment": covers},
        },
    }


FIRST_FILE = [
    loan(1, "paid", "2009-08-01", "2010-02-01", "2009-07-20", "Retail", PH, 1, ["F"]),
    loan(2, "defaulted", "2009-09-01", None, "2009-08-20", "Food", PH, 1, ["F", "F"]),
    loan(3, "paid", "2010-03-01", "2010-09-01", "2010-02-20", "Services", PH, 1, ["M"]),
    loan(4, "paid", "2010-10-01", "2011-04-01", "2010-09-20", "Retail", PH, 1, ["F", "M"]),
    # Another sector: not a loan of this mode, but part of the partner's track record.
    loan(5, "paid", "2010-01-10", "2010-06-01", "2010-01-01", "Agriculture", PH, 1, ["F"]),
]
SECOND_FILE = [
    loan(6, "in_repayment", "2012-01-01", None, "2011-12-20", "Retail", PH, 1, ["F"]),
    loan(7, "paid", "2014-01-01", "2014-08-01", "2013-12-20", "Retail", PH, 1, ["F"]),
    loan(8, "paid", "2010-05-01", "2010-12-01", "2010-04-20", "Retail", "Kenya", 9, ["F"]),
    loan(9, "paid", "2011-05-01", "2011-12-01", "2011-04-20", "Retail", KH, 2, [], "partner"),
    FIRST_FILE[0],  # the snapshot repeats some loans; this is loan 1 again
]


def make_archive(folder: Path, first=FIRST_FILE, second=SECOND_FILE) -> Path:
    path = folder / ARCHIVE_NAME
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("loans/1.json", json.dumps({"header": {}, "loans": first}))
        archive.writestr("loans/2.json", json.dumps({"header": {}, "loans": second}))
        archive.writestr("loans/3.json", "")  # empty, like 17 files of the archived copy
        archive.writestr("lenders/1.json", json.dumps({"lenders": [{"name": "SECRET"}]}))
    return path


@pytest.fixture(scope="module")
def config() -> dict:
    config = copy.deepcopy(load_config())
    config["data"]["mode"] = MODE
    config["data"]["kiva"]["partner_min_known_loans"] = 2  # the fixture is tiny
    return config


@pytest.fixture(scope="module")
def folder(tmp_path_factory) -> Path:
    folder = tmp_path_factory.mktemp("kiva")
    make_archive(folder)
    return folder


@pytest.fixture(scope="module")
def adapter(config, folder) -> KivaAsiaAdapter:
    return KivaAsiaAdapter(config, folder=folder, use_cache=False)


@pytest.fixture(scope="module")
def tables(adapter) -> dict:
    return adapter.load_all()


@pytest.fixture(scope="module")
def records(tables) -> pd.DataFrame:
    return tables[SOURCE_RECORDS].set_index("merchant_id")


@pytest.fixture(scope="module")
def features(tables, config) -> pd.DataFrame:
    return kiva_features(tables[SOURCE_RECORDS], config).set_index("merchant_id")


# --- which loans are used ---------------------------------------------------------------


def test_only_asian_shop_loans_with_a_known_outcome_in_the_window_are_used(tables):
    """Left out: another sector (5), still being repaid (6), posted too late (7), Kenya (8)."""
    assert tables["loans"]["loan_id"].tolist() == ["KVL1", "KVL2", "KVL3", "KVL4", "KVL9"]
    assert tables["loans"]["outcome_label"].tolist() == [1, 0, 1, 1, 1], "1 = repaid"


def test_a_loan_repeated_in_the_snapshot_is_kept_once(tables):
    assert tables["loans"]["loan_id"].is_unique
    assert (tables["loans"]["loan_id"] == "KVL1").sum() == 1


def test_the_seven_tables_match_the_contract(tables):
    for table in CONTRACT:
        check_frame(table, tables[table])
    for table in ("purchases", "deliveries", "payments", "questionnaire"):
        assert tables[table].empty, table
    merchants = tables["merchants"].set_index("merchant_id")
    assert merchants.loc["KV2", "shop_type"] == "Food"
    assert tables["loans"].set_index("loan_id").loc["KVL1", "issued_at"] == "2009-08-01"


def test_no_name_story_or_town_survives(adapter, tables, folder):
    """The snapshot is full of personal data. None of it may be kept anywhere."""
    everything = [adapter._extracted(), adapter.audit_frame(), *tables.values()]
    for frame in everything:
        assert "SECRET" not in frame.to_csv()
        assert not any("name" in column.lower() for column in frame.columns)
    assert not list((folder / DERIVED_FOLDER).glob("*")), "nothing left on disk without a cache"


def test_audit_columns_are_kept_apart(adapter, tables, features):
    audit = adapter.audit_frame().set_index("merchant_id")
    assert list(audit.columns) == load_config()["fairness"]["audit_only_columns"][MODE]
    assert list(audit.columns) == ["borrower_genders", "country"]
    assert audit["borrower_genders"].to_dict() == {
        "KV1": "female", "KV2": "female", "KV3": "male", "KV4": "mixed", "KV9": "not stated",
    }  # fmt: skip
    assert audit.loc["KV9", "country"] == "Cambodia"
    for column in ("borrower_genders", "country", "borrowers", "female_borrowers"):
        assert column not in tables[SOURCE_RECORDS].columns
        assert column not in features.columns


# --- the partner's track record never looks ahead ------------------------------------------


def test_only_outcomes_known_on_the_posting_day_are_counted(records):
    """Partner 1's loans, in time order: 1 (repaid Feb 2010), 5 (repaid Jun 2010),
    3 (repaid Sep 2010), and 2, a default known only six months after its term ended."""
    assert records.loc["KV1", "partner_known_loans"] == 0, "the partner's first loan"
    assert records.loc["KV2", "partner_known_loans"] == 0, "loan 1 was not repaid yet"
    # Posted 1 March 2010: only loan 1 had ended. Loan 2 was already going bad, but
    # nobody knew that yet, and loan 5 was still running.
    assert records.loc["KV3", "partner_known_loans"] == 1
    assert records.loc["KV3", "partner_known_defaults"] == 0
    # Posted 1 October 2010: loans 1, 5 and 3 repaid, and the default of loan 2 is known.
    assert records.loc["KV4", "partner_known_loans"] == 4
    assert records.loc["KV4", "partner_known_defaults"] == 1


def test_a_default_becomes_known_only_after_the_lag(config):
    lag = config["data"]["kiva"]["default_known_lag_months"]
    loans = pd.DataFrame(
        {
            "partner_id": [1, 1, 1],
            "status": ["defaulted", "paid", "paid"],
            "posted_date": ["2010-01-01", "2010-12-01", "2011-03-01"],
            "paid_date": [None, "2011-05-01", "2011-09-01"],
            "disbursal_date": ["2010-01-01", "2010-12-01", "2011-03-01"],
            "repayment_term": [6, 6, 6],
        }
    )
    record = partner_track_record(loans, lag)
    # The first loan's term ended in July 2010; with a six-month lag it is known in January 2011.
    assert record["partner_known_defaults"].tolist() == [0, 0, 1]
    assert record["partner_known_loans"].tolist() == [0, 0, 1]


def test_a_loan_s_own_outcome_never_reaches_its_features(config, tmp_path, features):
    """Turn the last loan of partner 1 into a default: no feature of any loan may move."""
    changed = copy.deepcopy(FIRST_FILE)
    changed[3]["status"], changed[3]["paid_date"] = "defaulted", None
    make_archive(tmp_path, first=changed)
    tables = KivaAsiaAdapter(config, folder=tmp_path, use_cache=False).load_all()
    again = kiva_features(tables[SOURCE_RECORDS], config).set_index("merchant_id")
    pd.testing.assert_frame_equal(again, features)
    assert tables["loans"]["outcome_label"].tolist() == [1, 0, 1, 0, 1]


# --- leakage guard ------------------------------------------------------------------------


def test_source_records_hold_only_whitelisted_columns(tables):
    assert list(tables[SOURCE_RECORDS].columns) == ["loan_id", "merchant_id", *WHITELIST]
    assert not set(BLACKLIST) & set(tables[SOURCE_RECORDS].columns)


@pytest.mark.parametrize("planted", BLACKLIST)
def test_a_blacklisted_column_is_refused_by_the_feature_builder(planted, tables, config):
    """Among them the description: Kiva removes it from loans that defaulted."""
    leaky = tables[SOURCE_RECORDS].copy()
    leaky[planted] = 1
    with pytest.raises(ValueError, match="whitelisted"):
        kiva_features(leaky, config)


def test_the_description_is_not_used_even_for_coverage(config):
    assert "description_length" in BLACKLIST
    assert not any("description" in name for name in coverage_weights_for_mode(config, MODE))
    assert not any("description" in name for name in [*WHITELIST, *MODEL_INPUTS, *CONTEXT_COLUMNS])


# --- features, coverage and the shared pipeline -----------------------------------------------


def test_feature_values(features):
    assert features["repayment_term_months"].eq(6).all()
    assert pd.isna(features.loc["KV1", "partner_past_default_rate"]), "no track record yet"
    assert pd.isna(features.loc["KV3", "partner_past_default_rate"]), "one known loan is too few"
    assert features.loc["KV4", "partner_past_default_rate"] == pytest.approx(1 / 4)
    assert features.loc["KV9", "partner_covers_default"] == 1
    assert features.loc["KV1", "partner_covers_default"] == 0
    assert features.loc["KV4", "partner_known_loans"] == 4, "context, not a model input"
    assert "partner_known_loans" in CONTEXT_COLUMNS and "loan_amount_usd" in CONTEXT_COLUMNS
    assert PARTNER_INPUTS == ["partner_past_default_rate", "partner_covers_default"]
    expected = ["loan_id", "cutoff_date", *MODEL_INPUTS, *CONTEXT_COLUMNS, *COVERAGE_COLUMNS]
    assert list(features.columns) == expected


def test_a_partner_without_a_track_record_means_needs_more_info(config, features):
    weights = coverage_weights_for_mode(config, MODE)
    assert [f"cov_{name}" for name in weights] == COVERAGE_COLUMNS
    coverage = coverage_for_rows(features, config, MODE)
    assert coverage["KV1"] == pytest.approx(0.40) and coverage["KV4"] == 1.0
    assert band_for(95, coverage["KV1"], config, MODE) == NEEDS_MORE_INFO
    assert band_for(95, coverage["KV4"], config, MODE) == STRONG


def test_build_dataset_and_a_time_split_by_posting_date(tables, config):
    dataset = build_dataset(tables, config)
    assert (dataset["label_status"] == "labelled").all()
    assert (dataset["label_source"] == "source").all() and dataset["consent_valid"].all()
    short = copy.deepcopy(config)  # the fixture spans two years, not four
    short["split_by_mode"][MODE] = {"train_months": 12, "validation_months": 6, "test_months": 12}
    split = split_for_mode(modelling_rows(dataset), short, MODE)
    assert split.method == TIME_SPLIT
    assert split.boundaries["train_from"] == "2009-08-01", "the month of the first loan"
    assert sorted(split.train["merchant_id"]) == ["KV1", "KV2", "KV3"]
    assert split.validation["merchant_id"].tolist() == ["KV4"]
    assert split.test["merchant_id"].tolist() == ["KV9"]


def test_every_model_input_has_a_direction_and_sentences_in_both_languages():
    dictionary = load_dictionary()
    entries = features_for_mode(dictionary, MODE)
    assert list(entries) == MODEL_INPUTS
    assert set(expected_directions(dictionary, MODE)) == set(MODEL_INPUTS)
    for name, entry in entries.items():
        sides = [entry["positive"], entry["negative"], *(entry.get("otherwise") or {}).values()]
        for sentences in sides:
            assert sentences["en"].strip() and sentences["bn"].strip(), name
    assert entries["partner_past_default_rate"]["group"] == "P"
    assert detail_text(entries["repayment_term_months"], 8, 10.9) == (
        "Loan term 8.0 months vs average 10.9 months"
    )


# --- reading the archive ----------------------------------------------------------------------


def test_a_missing_archive_says_where_to_put_it(config, tmp_path):
    with pytest.raises(FileNotFoundError, match="unopened"):
        KivaAsiaAdapter(config, folder=tmp_path, use_cache=False).load_merchants()


def test_the_saved_extract_is_reused_and_holds_no_personal_data(config, tmp_path, tables):
    make_archive(tmp_path)
    first = KivaAsiaAdapter(config, folder=tmp_path).load_all()
    saved = list((tmp_path / DERIVED_FOLDER).glob("region_loans_*.csv"))
    assert len(saved) == 1
    assert "SECRET" not in saved[0].read_text(encoding="utf-8")
    second = KivaAsiaAdapter(config, folder=tmp_path).load_all()
    for name in first:
        pd.testing.assert_frame_equal(first[name], second[name])
        pd.testing.assert_frame_equal(first[name], tables[name])


def test_an_unknown_region_is_refused(config, tmp_path):
    make_archive(tmp_path)
    other = copy.deepcopy(config)
    other["data"]["kiva"]["regions"] = ["Atlantis"]
    with pytest.raises(ValueError, match="Atlantis"):
        KivaAsiaAdapter(other, folder=tmp_path, use_cache=False).load_merchants()


HAS_REAL_ARCHIVE = (RAW_FOLDER / ARCHIVE_NAME).exists()


@pytest.mark.skipif(not HAS_REAL_ARCHIVE, reason="the real Kiva archive is not here")
def test_the_real_archive_reads_as_documented():
    """Only on a machine that has the download (the first read takes about a minute)."""
    config = copy.deepcopy(load_config())
    config["data"]["mode"] = MODE
    adapter = KivaAsiaAdapter(config)
    tables = adapter.load_all()
    loans = tables["loans"]
    assert len(loans) == 65304 and loans["loan_id"].is_unique
    assert int((loans["outcome_label"] == 0).sum()) == 2512
    assert loans["issued_at"].min() >= "2009-07-01" and loans["issued_at"].max() <= "2013-06-30"
    assert "Bangladesh" not in set(adapter.audit_frame()["country"]), "the snapshot has none"
    split = split_for_mode(modelling_rows(build_dataset(tables, config)), config, MODE)
    for part in (split.train, split.validation, split.test):
        assert (part["label"] == 0).sum() >= 100, "enough defaults for stable numbers"
