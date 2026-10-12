"""Shared test helpers.

Purpose: give every test the validated config and the tiny fixture files.
Owner role: D (full-stack) keeps the tests folder; every role adds its own tests.
Implements: PROJECT_BRIEF section 4 (tests/fixtures: tiny hand-made files, never real data).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from src.adapters.base import CONTRACT
from src.config import MODE_ENV_VAR, load_config

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(autouse=True)
def _no_mode_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests always start from the mode in config/default.yaml, whatever the shell has set."""
    monkeypatch.delenv(MODE_ENV_VAR, raising=False)


@pytest.fixture()
def config() -> dict[str, Any]:
    """The validated default config."""
    return load_config()


@pytest.fixture()
def contract_tables() -> dict[str, pd.DataFrame]:
    """The fixture CSVs, one DataFrame per contract table. Ids stay as text."""
    return {
        table: pd.read_csv(FIXTURES / "contract" / f"{table}.csv", dtype=str)
        for table in CONTRACT
    }


def load_api_fixture(name: str) -> Any:
    """Read one sample API response from tests/fixtures/api/."""
    with (FIXTURES / "api" / f"{name}.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)
