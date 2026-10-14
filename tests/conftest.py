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


# --- the API with a real (small) scorer and a real (small) database -------------------


@pytest.fixture(scope="session")
def api_world(tmp_path_factory):
    """2,000 synthetic merchants loaded into a temporary SQLite database, a model trained
    on them, and the scorer built from the same tables.

    This is the whole API stack at a small size: real database, real scores, real reasons.
    It is built once for the whole test run. Tests that write (decisions, audit entries)
    must therefore compare counts before and after, never assume an empty table.
    """
    import copy
    from types import SimpleNamespace

    from src.api.state import Services
    from src.db.load import load_tables
    from src.db.models import make_engine
    from src.model.dataset import build_dataset
    from src.model.scoring import Scorer
    from src.model.train import train_models
    from src.synth.generate import build_tables

    config = copy.deepcopy(load_config())
    config["data"]["mode"] = "synthetic_bd"
    config["data"]["n_merchants"] = 2000
    config["model"]["bootstrap_resamples"] = 50
    config["model"]["candidates"] = ["logistic_regression"]
    config["score"]["reasons_report_sample"] = 20
    tables = build_tables(config, 0.5)[0]
    trained = train_models(build_dataset(tables, config), config)
    saved = {
        "model": trained["model"],
        "calibrator": trained["calibrator"],
        "features": trained["features"],
        "version_id": "test-version",
    }
    url = "sqlite:///" + (tmp_path_factory.mktemp("api_db") / "api.db").as_posix()
    load_tables(tables, url)
    engine = make_engine(url)
    services = Services(
        config=config, engine=engine, scorer=Scorer(config, tables=tables, saved=saved)
    )
    yield SimpleNamespace(
        services=services, tables=tables, saved=saved, config=config, engine=engine
    )
    engine.dispose()


@pytest.fixture()
def api(api_world):
    """A test client for the API, wired to `api_world` (no start-up: it is already built)."""
    from fastapi.testclient import TestClient

    from src.api.main import app

    app.state.services = api_world.services
    try:
        yield TestClient(app)
    finally:
        del app.state.services
