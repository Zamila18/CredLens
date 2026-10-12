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
