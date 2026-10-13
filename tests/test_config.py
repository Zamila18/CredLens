"""Tests for src/config.py: the config loads, and bad configs are rejected.

Owner role: A (lead).
Implements: Phase 0 ("one real passing config test"); PROJECT_BRIEF sections 7.6 and 18.
"""

from __future__ import annotations

import copy

import pytest

from src.config import (
    MODE_ENV_VAR,
    PROJECT_ROOT,
    VALID_MODES,
    ConfigError,
    banner_text,
    coverage_weights_for_mode,
    get_database_url,
    load_config,
    validate_config,
)


def test_default_config_is_valid(config):
    assert config["seed"] == 42
    assert config["data"]["mode"] in VALID_MODES


def test_every_coverage_list_sums_to_one(config):
    for mode in VALID_MODES:
        weights = coverage_weights_for_mode(config, mode)
        assert sum(weights.values()) == pytest.approx(1.0), mode


def test_coverage_lists_differ_by_mode(config):
    """Coverage is per data mode: public modes use their own checklist."""
    synthetic = set(coverage_weights_for_mode(config, "synthetic_bd"))
    assert "deliveries_present" in synthetic
    for mode in ("kiva_asia", "taiwan_cc", "india_ltfs", "homecredit"):
        assert set(coverage_weights_for_mode(config, mode)) != synthetic


def test_questionnaire_is_not_in_the_model(config):
    assert config["data"]["questionnaire_in_model"] is False


def test_group_columns_are_listed_for_audit(config):
    assert config["fairness"]["group_columns"] == ["town_tier", "shop_type", "has_trade_license"]
    public_modes = {"kiva_asia", "taiwan_cc", "india_ltfs", "homecredit"}
    assert set(config["fairness"]["audit_only_columns"]) == public_modes


def test_coverage_weights_must_sum_to_one(config):
    broken = copy.deepcopy(config)
    broken["coverage_weights"]["history_6_months"] += 0.1
    with pytest.raises(ConfigError, match="coverage_weights must sum to 1.0"):
        validate_config(broken)


def test_public_mode_coverage_weights_are_checked(config):
    broken = copy.deepcopy(config)
    broken["coverage_weights_by_mode"]["kiva_asia"]["loan_terms_present"] = 0.9
    with pytest.raises(ConfigError, match="coverage_weights_by_mode.kiva_asia"):
        validate_config(broken)


def test_unknown_data_mode_is_rejected(config):
    broken = copy.deepcopy(config)
    broken["data"]["mode"] = "sba_us"
    with pytest.raises(ConfigError, match="data.mode"):
        validate_config(broken)


@pytest.mark.parametrize("name", ["train_months", "validation_months", "test_months"])
@pytest.mark.parametrize("bad_value", [0, -3, 1.5, None])
def test_split_months_must_be_positive_whole_numbers(config, name, bad_value):
    broken = copy.deepcopy(config)
    broken["split"][name] = bad_value
    with pytest.raises(ConfigError, match=f"split.{name}"):
        validate_config(broken)


def test_all_problems_are_reported_together(config):
    broken = copy.deepcopy(config)
    broken["data"]["mode"] = "nope"
    broken["split"]["test_months"] = 0
    with pytest.raises(ConfigError) as error:
        validate_config(broken)
    assert "data.mode" in str(error.value)
    assert "split.test_months" in str(error.value)


def test_mode_can_be_overridden_from_the_environment(monkeypatch):
    monkeypatch.setenv(MODE_ENV_VAR, "taiwan_cc")
    assert load_config()["data"]["mode"] == "taiwan_cc"


def test_bad_mode_from_the_environment_is_rejected(monkeypatch):
    monkeypatch.setenv(MODE_ENV_VAR, "not_a_mode")
    with pytest.raises(ConfigError):
        load_config()


def test_database_defaults_to_local_sqlite(config, monkeypatch):
    monkeypatch.delenv(config["database"]["url_env"], raising=False)
    url = get_database_url(config, use_dotenv=False)
    assert url == "sqlite:///" + (PROJECT_ROOT / "data" / "app.db").as_posix()


def test_database_url_comes_from_the_environment_when_set(config, monkeypatch):
    monkeypatch.setenv(config["database"]["url_env"], "postgresql+psycopg2://example/db")
    assert get_database_url(config, use_dotenv=False) == "postgresql+psycopg2://example/db"


def test_banner_names_the_source_and_says_decision_support():
    assert banner_text("synthetic_bd") == "Synthetic demo data. Decision support only."
    for mode in ("kiva_asia", "taiwan_cc", "india_ltfs", "homecredit"):
        banner = banner_text(mode)
        assert banner.startswith("Public data: ")
        assert "not ShopUp data" in banner
        assert banner.endswith("Decision support only.")


def test_home_credit_is_never_presented_as_asian_data():
    """The Home Credit files do not state their country, so the banner says so."""
    assert "country not stated" in banner_text("homecredit")
    assert "Asia" in banner_text("kiva_asia")
    assert "Taiwan" in banner_text("taiwan_cc")


# --- the newer sections are checked too ----------------------------------------------


@pytest.mark.parametrize(
    ("section", "key", "bad_value"),
    [
        ("evaluation", "top_k", -5),
        ("evaluation", "calibration_bins", 0),
        ("evaluation", "calibration_binning", "magic"),
        ("evaluation", "bootstrap_level", 95),
        ("features", "window_days", "ninety"),
        ("features", "delivery_settle_days", None),
        ("generator", "repayment_share_target", 3),
        ("labels", "paid_in_full_tolerance", -1),
        ("sanity", "min_not_repaid_for_stable_metrics", 0),
        ("model", "bootstrap_resamples", 0),
        ("model", "calibration", "magic"),
        ("model", "candidates", []),
        ("model", "candidates", ["logistic_regression", "magic_forest"]),
        ("model", "lightgbm", {"grid": []}),
        ("score", "low_score_warning_below", 150),
        ("labels", "supplied_by_source", ["synthetic_bd"]),
        ("labels", "supplied_by_source", ["mars"]),
        ("score", "min_reason_points", -1),
        ("score", "max_inputs_for_exact_reasons", 0),
        ("score", "by_mode", {"mars": {"band_min_coverage": 0.5}}),
        ("score", "by_mode", {"taiwan_cc": {"made_up_line": 5}}),
        ("score", "by_mode", {"taiwan_cc": {"band_min_coverage": 5}}),
        ("model", "calibration_folds", 1),
        ("model", "calibration_min_brier_gain", -0.1),
    ],
)
def test_a_wrong_setting_is_named_when_the_config_loads(config, section, key, bad_value):
    broken = copy.deepcopy(config)
    broken[section][key] = bad_value
    with pytest.raises(ConfigError, match=f"{section}.{key}"):
        validate_config(broken)


@pytest.mark.parametrize("section", ["evaluation", "features"])
def test_a_missing_section_is_reported(config, section):
    broken = copy.deepcopy(config)
    del broken[section]
    with pytest.raises(ConfigError, match=section):
        validate_config(broken)


def test_split_by_mode_is_checked(config):
    broken = copy.deepcopy(config)
    broken["split_by_mode"]["india_ltfs"]["test_months"] = 0
    with pytest.raises(ConfigError, match="split_by_mode.india_ltfs.test_months"):
        validate_config(broken)
    unknown = copy.deepcopy(config)
    unknown["split_by_mode"]["mars"] = {"train_months": 1, "validation_months": 1, "test_months": 1}
    with pytest.raises(ConfigError, match="split_by_mode.mars"):
        validate_config(unknown)
