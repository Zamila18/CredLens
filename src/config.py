"""Load and validate the project configuration.

Purpose: one place that reads `config/default.yaml`, checks it, and answers
    small questions such as "which data mode is active" and "which database".
Owner role: A (lead). Other roles read config through this module only.
Implements: CLAUDE.md ("never hard-code tunable numbers"), PROJECT_BRIEF
    sections 7.6 (coverage weights, band lines) and 18 (data modes, database).

Every tunable number lives in the YAML file. Code must read it from there.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "default.yaml"

# The data modes that run through the same pipeline (PROJECT_BRIEF section 18).
# kiva_asia, taiwan_cc and india_ltfs are Asian sources. homecredit does not state its country.
VALID_MODES = ("synthetic_bd", "kiva_asia", "taiwan_cc", "india_ltfs", "homecredit")

# Environment variable that overrides data.mode for one run.
MODE_ENV_VAR = "CREDLENS_DATA_MODE"

# Every screen names its data source and says the tool only supports a decision.
DECISION_SUPPORT_NOTE = "Decision support only."
SOURCE_LABELS = {
    "synthetic_bd": "Synthetic demo data.",
    "kiva_asia": "Public data: Kiva (Asia), not ShopUp data.",
    "taiwan_cc": "Public data: Taiwan credit cards, not ShopUp data.",
    "india_ltfs": "Public data: India L&T vehicle loans, not ShopUp data.",
    "homecredit": "Public data: Home Credit (country not stated), not ShopUp data.",
}

# How far a list of weights may be from 1.0 before we call it wrong.
WEIGHT_SUM_TOLERANCE = 1e-6


class ConfigError(ValueError):
    """Raised when the configuration file is missing something or is inconsistent."""


def load_config(path: Path | str | None = None, validate: bool = True) -> dict[str, Any]:
    """Read the YAML config, apply the mode override from the environment, and check it.

    Args:
        path: config file to read. Defaults to `config/default.yaml`.
        validate: set False only in tests that build a broken config on purpose.
    """
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ConfigError(f"Config file is empty or not a mapping: {config_path}")

    mode_override = os.environ.get(MODE_ENV_VAR, "").strip()
    if mode_override:
        config.setdefault("data", {})["mode"] = mode_override

    if validate:
        validate_config(config)
    return config


def validate_config(config: dict[str, Any]) -> None:
    """Check the config and raise ConfigError listing every problem found."""
    problems: list[str] = []

    if not isinstance(config.get("seed"), int):
        problems.append("seed must be a whole number")

    data = config.get("data") or {}
    mode = data.get("mode")
    if mode not in VALID_MODES:
        problems.append(f"data.mode is {mode!r}; it must be one of {', '.join(VALID_MODES)}")

    for name in (
        "thin_file_share",
        "consent_rate",
        "questionnaire_rate",
        "no_delivery_data_share",
        "delivery_signal_strength",
        "logistics_noise_share",
    ):
        value = data.get(name)
        if not _is_number(value) or not 0 <= value <= 1:
            problems.append(f"data.{name} must be a number between 0 and 1")

    for name in ("n_merchants", "months"):
        if not _is_positive_int(data.get(name)):
            problems.append(f"data.{name} must be a positive whole number")

    split = config.get("split") or {}
    for name in ("train_months", "validation_months", "test_months"):
        if not _is_positive_int(split.get(name)):
            problems.append(f"split.{name} must be a positive whole number")

    labels = config.get("labels") or {}
    for name in ("good_if_days_late_at_most", "min_loan_age_days"):
        if not _is_positive_int(labels.get(name)):
            problems.append(f"labels.{name} must be a positive whole number")

    score = config.get("score") or {}
    if not _is_number(score.get("band_min_coverage")) or not 0 <= score["band_min_coverage"] <= 1:
        problems.append("score.band_min_coverage must be a number between 0 and 1")
    if not _is_number(score.get("band_strong_min_score")) or not (
        0 <= score["band_strong_min_score"] <= 100
    ):
        problems.append("score.band_strong_min_score must be a number between 0 and 100")
    if not _is_number(score.get("low_score_warning_below")) or not (
        0 <= score["low_score_warning_below"] <= 100
    ):
        problems.append("score.low_score_warning_below must be a number between 0 and 100")
    for line_mode, lines in (score.get("by_mode") or {}).items():
        if line_mode not in VALID_MODES:
            problems.append(f"score.by_mode.{line_mode} is not a known data mode")
        allowed = ("band_strong_min_score", "band_min_coverage", "low_score_warning_below")
        for name, value in (lines or {}).items():
            highest = 1 if name == "band_min_coverage" else 100
            if name not in allowed or not _is_number(value) or not 0 <= value <= highest:
                problems.append(
                    f"score.by_mode.{line_mode}.{name} is not a valid band line "
                    f"(a number between 0 and {highest})"
                )
    if not _is_positive_int(score.get("top_reasons_each_side")):
        problems.append("score.top_reasons_each_side must be a positive whole number")

    problems.extend(_check_weights("coverage_weights", config.get("coverage_weights")))
    by_mode = config.get("coverage_weights_by_mode") or {}
    for public_mode in VALID_MODES:
        if public_mode == "synthetic_bd":
            continue
        problems.extend(
            _check_weights(f"coverage_weights_by_mode.{public_mode}", by_mode.get(public_mode))
        )
    for extra in sorted(set(by_mode) - set(VALID_MODES)):
        problems.append(f"coverage_weights_by_mode.{extra} is not a known data mode")

    database = config.get("database") or {}
    if not database.get("url_env") or not database.get("default_url"):
        problems.append("database.url_env and database.default_url are required")

    problems.extend(
        _check_values(config, POSITIVE_WHOLE_NUMBERS, _is_positive_int, "a positive whole number")
    )
    problems.extend(_check_values(config, SHARES, _is_share, "a number between 0 and 1"))
    model = config.get("model") or {}
    if model.get("calibration") not in ("auto", "none", "platt", "isotonic"):
        problems.append("model.calibration must be 'auto', 'none', 'platt' or 'isotonic'")
    known = ("logistic_regression", "lightgbm")
    wanted = model.get("candidates")
    if not isinstance(wanted, list) or not wanted or any(name not in known for name in wanted):
        problems.append(f"model.candidates must be a non-empty list drawn from {list(known)}")
    grid = (model.get("lightgbm") or {}).get("grid")
    grid_keys = {"num_leaves", "learning_rate", "min_child_samples"}
    if not isinstance(grid, list) or not grid:
        problems.append("model.lightgbm.grid must be a non-empty list of settings")
    else:
        for number, entry in enumerate(grid, start=1):
            if not isinstance(entry, dict) or set(entry) != grid_keys:
                problems.append(
                    f"model.lightgbm.grid entry {number} must have exactly {sorted(grid_keys)}"
                )
            elif not all(_is_number(value) and value > 0 for value in entry.values()):
                problems.append(f"model.lightgbm.grid entry {number} must hold positive numbers")
    folds = model.get("calibration_folds")
    if not _is_positive_int(folds) or folds < 2:
        problems.append("model.calibration_folds must be a whole number of at least 2")
    binning = (config.get("evaluation") or {}).get("calibration_binning")
    if binning not in ("quantile", "width"):
        problems.append("evaluation.calibration_binning must be 'quantile' or 'width'")
    for mode, months in (config.get("split_by_mode") or {}).items():
        if mode not in VALID_MODES:
            problems.append(f"split_by_mode.{mode} is not a known data mode")
        for name in ("train_months", "validation_months", "test_months"):
            if not _is_positive_int((months or {}).get(name)):
                problems.append(f"split_by_mode.{mode}.{name} must be a positive whole number")

    if problems:
        raise ConfigError("Invalid configuration:\n- " + "\n- ".join(problems))


def coverage_weights_for_mode(config: dict[str, Any], mode: str | None = None) -> dict[str, float]:
    """Return the coverage checklist weights for a data mode.

    Coverage means "how much of what this source can provide is present", so
    each mode has its own list (PROJECT_BRIEF section 18, item 11).
    """
    mode = mode or config["data"]["mode"]
    if mode not in VALID_MODES:
        raise ConfigError(f"Unknown data mode: {mode!r}")
    if mode == "synthetic_bd":
        return dict(config["coverage_weights"])
    return dict(config["coverage_weights_by_mode"][mode])


def get_database_url(config: dict[str, Any], use_dotenv: bool = True) -> str:
    """Return the database connection string.

    The environment variable named in `database.url_env` wins (Supabase
    Postgres). When it is not set, the local SQLite default is used, which is
    what tests and CI rely on. The value is a secret: never print or log it.
    """
    if use_dotenv:
        load_dotenv(PROJECT_ROOT / ".env")
    database = config["database"]
    url = os.environ.get(database["url_env"], "").strip() or database["default_url"]

    # Make a relative SQLite path independent of the folder the command runs from.
    sqlite_prefix = "sqlite:///"
    if url.startswith(sqlite_prefix):
        location = url[len(sqlite_prefix):]
        if location != ":memory:" and not Path(location).is_absolute():
            url = sqlite_prefix + (PROJECT_ROOT / location).as_posix()
    return url


def banner_text(mode: str) -> str:
    """Return the sentence every screen must show for a data mode."""
    if mode not in SOURCE_LABELS:
        raise ConfigError(f"Unknown data mode: {mode!r}")
    return f"{SOURCE_LABELS[mode]} {DECISION_SUPPORT_NOTE}"


# Settings checked by kind. A typo or a missing section is reported when the config is
# loaded, not later as a confusing error deep inside a run.
POSITIVE_WHOLE_NUMBERS = (
    "model.bootstrap_resamples",
    "model.logistic_regression.max_iter",
    "model.lightgbm.tuning_months",
    "model.lightgbm.max_trees",
    "model.lightgbm.early_stopping_rounds",
    "evaluation.calibration_bins",
    "evaluation.top_k",
    "features.window_days",
    "features.weekly_window_weeks",
    "features.ontime_payment_days",
    "features.late_payment_days",
    "features.delivery_settle_days",
    "features.thin_delivery_parcels",
    "features.coverage_history_days",
    "features.coverage_purchase_months",
    "features.recent_activity_days",
    "generator.observation_tail_days",
    "generator.loans.term_days",
    "generator.loans.max_loans",
    "sanity.min_not_repaid_for_stable_metrics",
)
SHARES = (
    "evaluation.lowest_share",
    "evaluation.bootstrap_level",
    "features.coverage_purchase_month_share",
    "generator.repayment_share_target",
    "labels.paid_in_full_tolerance",
    "model.prefer_simple_if_auc_gain_below",
    "model.calibration_min_brier_gain",
    "model.lightgbm.tuning_share",
    "model.lightgbm.row_share_per_tree",
    "model.lightgbm.input_share_per_tree",
    "sanity.useful_auc_benchmark",
    "sanity.suspicious_auc",
    "sanity.zero_signal_max_auc_gain",
)


def _lookup(config: dict[str, Any], dotted: str) -> Any:
    """Return config["a"]["b"]["c"] for "a.b.c", or None if any part is missing."""
    value: Any = config
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _check_values(config: dict[str, Any], names: tuple[str, ...], is_valid, kind: str) -> list[str]:
    """One problem line for each setting that is missing or of the wrong kind."""
    return [f"{name} must be {kind}" for name in names if not is_valid(_lookup(config, name))]


def _is_share(value: Any) -> bool:
    """True for a number between 0 and 1."""
    return _is_number(value) and 0 <= value <= 1


def _is_number(value: Any) -> bool:
    """True for int or float, but not for True/False."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_positive_int(value: Any) -> bool:
    """True for whole numbers above zero, but not for True/False."""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _check_weights(name: str, weights: Any) -> list[str]:
    """Check that a weight list exists, has no negative entries and sums to 1.0."""
    if not isinstance(weights, dict) or not weights:
        return [f"{name} is missing or empty"]
    problems = []
    for key, value in weights.items():
        if not _is_number(value) or value < 0:
            problems.append(f"{name}.{key} must be a number of 0 or more")
    if not problems:
        total = sum(weights.values())
        if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
            problems.append(f"{name} must sum to 1.0 (it sums to {total:.4f})")
    return problems
