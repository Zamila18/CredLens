"""Tests for the pre-start check of a machine's files (src/api/preflight.py).

Owner role: D (full-stack).
Implements: docs/SERVER_FILES.md.

Each test builds a small, complete machine in a temporary folder (the hand-made contract
files, a database loaded from them, a fake model and five model cards) and then breaks one
thing at a time. No real data, no network.
"""

from __future__ import annotations

import copy
import json
import shutil

import pytest

from src.adapters.base import CONTRACT
from src.adapters.shopup_synthetic import ShopUpSyntheticAdapter
from src.api import preflight
from src.config import VALID_MODES, get_database_url, load_config
from src.db.load import load_tables
from src.db.models import create_tables
from tests.conftest import FIXTURES

VERSION = "synthetic_bd-test-1"


@pytest.fixture()
def machine(tmp_path, monkeypatch):
    """A complete machine: config, files, database, model, cards. Returns (config, root)."""
    config = copy.deepcopy(load_config())
    config["data"]["mode"] = "synthetic_bd"
    config["generator"]["out_dir"] = str(tmp_path / "data" / "raw" / "synthetic_bd")
    tables = tmp_path / "data" / "raw" / "synthetic_bd" / "strength_0.5"
    tables.mkdir(parents=True)
    for table in CONTRACT:
        shutil.copy(FIXTURES / "contract" / f"{table}.csv", tables / f"{table}.csv")
    url = "sqlite:///" + (tmp_path / "app.db").as_posix()
    load_tables(ShopUpSyntheticAdapter(config, tables).load_all(), url)
    monkeypatch.setenv(config["database"]["url_env"], url)
    artifacts = tmp_path / "src" / "model" / "artifacts" / "synthetic_bd"
    artifacts.mkdir(parents=True)
    (artifacts / "model.joblib").write_bytes(b"fake")
    (artifacts / "metadata.json").write_text(json.dumps({"version_id": VERSION}), encoding="utf-8")
    for mode in VALID_MODES:
        folder = tmp_path / "reports" / mode
        folder.mkdir(parents=True)
        card = {"model_version": VERSION if mode == "synthetic_bd" else "other"}
        (folder / "model_card.json").write_text(json.dumps(card), encoding="utf-8")
    return config, tmp_path


def levels(checks) -> dict[str, str]:
    return {check.name: check.level for check in checks}


def failed(checks) -> list:
    return [check for check in checks if check.level == "FAIL"]


def test_a_complete_machine_passes_every_check(machine):
    config, root = machine
    for server in (False, True):
        checks = preflight.run_checks(config, root, server=server)
        assert {c.level for c in checks} == {"OK"}, [c for c in checks if c.level != "OK"]
    report = preflight.format_report(preflight.run_checks(config, root, server=True))
    assert report.endswith("Ready: the API can be started.")


def test_the_report_never_prints_the_database_address(machine):
    config, root = machine
    address = get_database_url(config)
    report = preflight.format_report(preflight.run_checks(config, root))
    assert address not in report and address.split("///")[-1] not in report
    assert "SQLite" in report


@pytest.mark.parametrize("table", list(CONTRACT))
def test_a_missing_generated_table_fails_and_names_the_fix(machine, table):
    config, root = machine
    (root / "data" / "raw" / "synthetic_bd" / "strength_0.5" / f"{table}.csv").unlink()
    problems = failed(preflight.run_checks(config, root))
    assert [c.name for c in problems] == ["generated tables"]
    assert table in problems[0].detail and "python tasks.py data" in problems[0].detail


def test_a_missing_model_fails_and_says_not_to_train_on_the_server(machine):
    config, root = machine
    (root / "src" / "model" / "artifacts" / "synthetic_bd" / "model.joblib").unlink()
    problems = failed(preflight.run_checks(config, root, server=True))
    assert [c.name for c in problems] == ["trained model"]
    assert "model.joblib" in problems[0].detail
    assert "Do not run `train` on a server" in problems[0].detail


def test_a_model_card_for_another_model_warns_on_a_laptop_and_fails_on_the_server(machine):
    config, root = machine
    card = root / "reports" / "synthetic_bd" / "model_card.json"
    card.write_text(json.dumps({"model_version": "older"}), encoding="utf-8")
    name = "model card matches the model"
    assert levels(preflight.run_checks(config, root))[name] == "WARN"
    assert levels(preflight.run_checks(config, root, server=True))[name] == "FAIL"
    card.unlink()
    assert levels(preflight.run_checks(config, root))["model card of this mode"] == "FAIL"


def test_a_missing_card_of_any_mode_fails(machine):
    config, root = machine
    (root / "reports" / "taiwan_cc" / "model_card.json").unlink()
    problems = failed(preflight.run_checks(config, root))
    assert [c.name for c in problems] == ["model cards"] and "taiwan_cc" in problems[0].detail


def test_a_database_with_other_merchants_than_the_files_fails(machine):
    config, root = machine
    merchants = root / "data" / "raw" / "synthetic_bd" / "strength_0.5" / "merchants.csv"
    lines = merchants.read_text(encoding="utf-8").splitlines()
    merchants.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    assert levels(preflight.run_checks(config, root))["database matches files"] == "FAIL"


def test_an_empty_database_fails(machine, tmp_path, monkeypatch):
    config, root = machine
    url = "sqlite:///" + (tmp_path / "empty.db").as_posix()
    create_tables(url)
    monkeypatch.setenv(config["database"]["url_env"], url)
    assert levels(preflight.run_checks(config, root))["demo users"] == "FAIL"


def test_a_database_that_was_never_created_fails(machine, tmp_path, monkeypatch):
    config, root = machine
    monkeypatch.setenv(
        config["database"]["url_env"], "sqlite:///" + (tmp_path / "never.db").as_posix()
    )
    problems = failed(preflight.run_checks(config, root))
    assert "database" in [c.name for c in problems]
    assert "python tasks.py data" in problems[0].detail


def test_raw_public_data_on_a_server_fails_but_is_not_looked_for_on_a_laptop(machine):
    config, root = machine
    folder = root / "data" / "raw" / "kiva"
    folder.mkdir(parents=True)
    (folder / "kiva_ds_json.zip").write_bytes(b"x")
    assert "raw public data" not in levels(preflight.run_checks(config, root))
    problems = failed(preflight.run_checks(config, root, server=True))
    assert [c.name for c in problems] == ["raw public data"] and "kiva" in problems[0].detail
    (folder / "kiva_ds_json.zip").unlink()  # an empty folder is fine
    assert levels(preflight.run_checks(config, root, server=True))["raw public data"] == "OK"


def test_the_hidden_truth_file_on_a_server_is_a_warning(machine):
    config, root = machine
    truth = root / "data" / "raw" / "synthetic_bd" / "strength_0.5" / "_latent_truth.csv"
    truth.write_text("x", encoding="utf-8")
    assert levels(preflight.run_checks(config, root, server=True))["hidden-truth file"] == "WARN"


@pytest.mark.parametrize("mode", [m for m in VALID_MODES if m != "synthetic_bd"])
def test_a_public_data_mode_fails_on_a_server_and_warns_on_a_laptop(machine, mode):
    config, root = machine
    config["data"]["mode"] = mode
    assert levels(preflight.run_checks(config, root))["data mode"] == "WARN"
    assert levels(preflight.run_checks(config, root, server=True))["data mode"] == "FAIL"


def test_the_exit_code_is_1_only_when_something_fails(machine, monkeypatch, capsys):
    config, root = machine
    real = preflight.run_checks
    monkeypatch.setattr(preflight, "load_config", lambda: config)
    monkeypatch.setattr(preflight, "run_checks", lambda cfg, server=False: real(cfg, root, server))
    assert preflight.main([]) == 0
    (root / "src" / "model" / "artifacts" / "synthetic_bd" / "metadata.json").unlink()
    assert preflight.main([]) == 1
    assert "NOT READY" in capsys.readouterr().out
