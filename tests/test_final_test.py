"""Tests for the one look at the test period (src/model/final_test.py).

Everything here runs on a small synthetic world in a temporary folder, so the real
ledgers in reports/ are never touched.
"""

from __future__ import annotations

import copy
import json

import pytest

from src.config import load_config
from src.model import final_test
from src.model.dataset import build_dataset
from src.model.holdout_ledger import read_ledger
from src.model.model_card import build_card
from src.model.train import train_models
from src.synth.generate import build_tables

MODE = "synthetic_bd"


@pytest.fixture(scope="module")
def world():
    config = copy.deepcopy(load_config())
    config["data"]["n_merchants"] = 2000
    config["model"]["candidates"] = ["logistic_regression"]
    config["model"]["bootstrap_resamples"] = 50
    config["score"]["reasons_report_sample"] = 20
    tables = build_tables(config, 0.5)[0]
    trained = train_models(build_dataset(tables, config), config)
    saved = {
        "model": trained["model"],
        "calibrator": trained["calibrator"],
        "features": trained["features"],
        "version_id": "test-model-1",
    }
    report = dict(trained["report"], model_version="test-model-1")
    return config, tables, saved, report


def _reports(tmp_path, report):
    folder = tmp_path / MODE
    folder.mkdir(parents=True)
    (folder / "metrics.json").write_text(json.dumps(report), encoding="utf-8")
    return tmp_path


def _measure(world, reports, again=None):
    config, tables, saved, _ = world
    return final_test.measure_test_period(
        config, reports, again_reason=again, tables=tables, saved=saved
    )


def test_one_look_is_measured_and_written_down(world, tmp_path):
    reports = _reports(tmp_path, world[3])
    results = _measure(world, reports)
    assert results["measured_on"].startswith("test period")
    assert 0.5 < results["test"]["metrics"]["roc_auc"] < 0.95
    (look,) = read_ledger(MODE, reports)
    assert look["purpose"] == final_test.FINAL_PURPOSE
    assert "test-model-1" in look["detail"]
    assert results["ledger_look_number"] == 1


def test_a_second_look_at_the_same_model_is_refused(world, tmp_path):
    reports = _reports(tmp_path, world[3])
    _measure(world, reports)
    with pytest.raises(final_test.AlreadyMeasured):
        _measure(world, reports)
    with pytest.raises(final_test.AlreadyMeasured):
        _measure(world, reports, again="   ")
    assert len(read_ledger(MODE, reports)) == 1


def test_a_second_look_with_a_reason_is_allowed_and_recorded(world, tmp_path):
    reports = _reports(tmp_path, world[3])
    _measure(world, reports)
    _measure(world, reports, again="the test file was corrupted")
    looks = read_ledger(MODE, reports)
    assert len(looks) == 2
    assert "again: the test file was corrupted" in looks[1]["purpose"]


def test_nothing_is_measured_when_the_model_does_not_belong_to_the_data(world, tmp_path):
    report = copy.deepcopy(world[3])
    report["validation"]["metrics"]["roc_auc"] += 0.01
    reports = _reports(tmp_path, report)
    with pytest.raises(final_test.ModelDoesNotMatchData):
        _measure(world, reports)
    assert read_ledger(MODE, reports) == [], "a refused run is not a look"


def test_the_model_is_not_changed_by_the_look(world, tmp_path):
    _, _, saved, report = world
    before = (saved["calibrator"].method, list(saved["features"]), id(saved["model"]))
    _measure(world, _reports(tmp_path, report))
    assert (saved["calibrator"].method, list(saved["features"]), id(saved["model"])) == before


def test_the_model_card_shows_the_test_result(world, tmp_path):
    config, _, _, report = world
    reports = _reports(tmp_path, report)
    results = _measure(world, reports)
    final_test.write_results(results, reports)
    card = build_card(MODE, config, reports_dir=reports)
    assert card["metrics"]["test_roc_auc"] == round(results["test"]["metrics"]["roc_auc"], 6)
    assert card["metrics"]["test_period_looks"] == 1


def test_a_card_without_a_test_look_says_so(world, tmp_path):
    config, _, _, report = world
    card = build_card(MODE, config, reports_dir=_reports(tmp_path, report))
    assert "has not been used" in card["metrics"]["test_result"]
    assert card["metrics"]["test_period_looks"] == 0


def test_the_plot_is_drawn_without_looking_again(world, tmp_path):
    reports = _reports(tmp_path, world[3])
    results = _measure(world, reports)
    final_test.write_results(results, reports)
    assert (reports / MODE / final_test.PLOT_FILE).exists()
    looks = read_ledger(MODE, reports)
    final_test.draw_calibration(results, reports)
    assert read_ledger(MODE, reports) == looks
