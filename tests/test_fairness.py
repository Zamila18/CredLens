"""Tests for the group audit (src/model/fairness.py).

The audit must catch a gap that was planted on purpose, and must not invent one when
there is none. The planted gap: the generator's `inject_group_bias` lowers the repayment
of small-town merchants without changing anything the model can see, so the model
expects more repayment from them than they show.
"""

from __future__ import annotations

import copy
import json

import numpy as np
import pandas as pd
import pytest

from src.config import load_config
from src.model import fairness
from src.model.dataset import build_dataset
from src.model.train import train_models
from src.synth.generate import build_tables

MODE = "synthetic_bd"


def _small_world_audit(bias: float) -> list[dict]:
    """Generate 4,000 merchants with this planted bias, train, and audit the validation months."""
    config = copy.deepcopy(load_config())
    config["data"]["n_merchants"] = 4000
    config["generator"]["inject_group_bias"] = bias
    config["model"]["candidates"] = ["logistic_regression"]
    config["model"]["bootstrap_resamples"] = 50
    config["fairness"]["bootstrap_resamples"] = 100
    tables = build_tables(config, 0.5)[0]
    trained = train_models(build_dataset(tables, config), config)
    audit = tables["merchants"][["merchant_id", *fairness.audit_columns(config, MODE)]]
    return fairness._validation_audit(trained, tables, audit, config, MODE)[0]


def _row(rows: list[dict], column: str, group: str) -> dict:
    return next(r for r in rows if r["column"] == column and r["group"] == group)


@pytest.fixture(scope="module")
def planted():
    return _small_world_audit(bias=1.5)


@pytest.fixture(scope="module")
def clean():
    return _small_world_audit(bias=0.0)


def test_the_audit_catches_a_planted_gap(planted):
    small_town = _row(planted, "town_tier", "small_town")
    assert small_town["calibration"] == fairness.FLAGGED
    # Positive: the model expects more repayment from small towns than they show.
    assert small_town["calibration_gap"] > load_config()["fairness"]["flag_gap_points"]


def test_the_audit_invents_no_gap_when_there_is_none(clean):
    flagged = [
        (r["column"], r["group"], check)
        for r in clean
        for check in fairness.CHECKS
        if r[check] == fairness.FLAGGED
    ]
    assert flagged == []


def test_every_audit_column_is_reported(clean):
    columns = {r["column"] for r in clean}
    assert columns == set(load_config()["fairness"]["group_columns"])
    for row in clean:
        assert row["loans"] > 0
        if row["ranking"] != fairness.TOO_FEW:
            assert 0 <= row["share_repaid"] <= 1


def test_audit_columns_are_never_model_inputs():
    config = load_config()
    with pytest.raises(fairness.GroupColumnIsAnInput):
        fairness._refuse_group_inputs(["town_tier"], ["purchase_regularity", "town_tier"])
    fairness._refuse_group_inputs(fairness.audit_columns(config, MODE), ["purchase_regularity"])


def _toy(config, labels, probabilities, groups):
    scored = pd.DataFrame({"score": np.round(100 * probabilities), "band": "Review"})
    return fairness.group_audit(labels, probabilities, scored, pd.DataFrame(groups), config)


def test_a_small_group_is_listed_but_not_measured():
    config = copy.deepcopy(load_config())
    config["fairness"]["bootstrap_resamples"] = 20
    rng = np.random.default_rng(0)
    labels = (rng.random(1000) < 0.8).astype(int)
    probabilities = np.full(1000, 0.8)
    groups = {"g": ["big"] * 990 + ["tiny"] * 10}
    rows = _toy(config, labels, probabilities, groups)
    tiny = next(r for r in rows if r["group"] == "tiny")
    assert tiny["loans"] == 10
    assert tiny["ranking"] == tiny["calibration"] == fairness.TOO_FEW
    # Only its size: the outcomes or scores of a few people are never reported.
    assert set(tiny) == {"column", "group", "loans", "ranking", "calibration"}


def test_a_missing_group_value_is_its_own_group():
    config = copy.deepcopy(load_config())
    config["fairness"]["bootstrap_resamples"] = 20
    rng = np.random.default_rng(1)
    labels = (rng.random(600) < 0.7).astype(int)
    rows = _toy(config, labels, np.full(600, 0.7), {"g": ["a"] * 300 + [None] * 300})
    assert {r["group"] for r in rows} == {"a", fairness.NOT_STATED}


def test_a_gap_in_every_seed_is_flagged_even_within_the_ranges():
    config = load_config()
    line = config["fairness"]["flag_gap_points"]
    row = {"column": "c", "group": "g", "ranking_gap": None, "ranking": fairness.TOO_FEW}
    seeds = [
        [{**row, "calibration_gap": line + 0.01, "calibration": fairness.CANDIDATE}],
        [{**row, "calibration_gap": line + 0.02, "calibration": fairness.CANDIDATE}],
        [{**row, "calibration_gap": line + 0.03, "calibration": fairness.NO_GAP}],
    ]
    fairness.persistent_gaps(seeds, config)
    assert seeds[0][0]["calibration"] == fairness.FLAGGED
    assert seeds[0][0]["calibration_seeds_with_gap"] == "3 of 3"

    mixed = [
        [{**row, "calibration_gap": line + 0.01, "calibration": fairness.CANDIDATE}],
        [{**row, "calibration_gap": -(line + 0.01), "calibration": fairness.CANDIDATE}],
    ]
    fairness.persistent_gaps(mixed, config)
    assert mixed[0][0]["calibration"] == fairness.CANDIDATE


def test_reports_are_written(tmp_path, clean):
    report = {
        "data_mode": MODE,
        "model_version": "test",
        "validation_loans": 1,
        "seeds": [42],
        "rules": {"gap_line": 0.05},
        "flagged": [],
        "groups": clean,
    }
    path = fairness.write_report(report, tmp_path)
    assert json.loads(path.read_text(encoding="utf-8"))["data_mode"] == MODE
    summary = fairness.write_summary(tmp_path).read_text(encoding="utf-8")
    assert "## synthetic_bd" in summary and "small_town" in summary
    assert "does not show that the model is fair" in summary


def test_a_measured_group_has_ranges_for_score_and_bands(clean):
    row = _row(clean, "town_tier", "city")
    for name in ("mean_score", "share_strong", "share_needs_more_info", "roc_auc"):
        low, high = row[f"{name}_range"]
        assert low <= row[name] <= high


def test_the_audit_stops_when_the_model_does_not_belong_to_the_data(tmp_path):
    folder = tmp_path / MODE
    folder.mkdir()
    report = {"validation": {"metrics": {"roc_auc": 0.71}}}
    (folder / "metrics.json").write_text(json.dumps(report), encoding="utf-8")
    fairness.check_against_training(0.71, MODE, tmp_path)
    with pytest.raises(fairness.ModelDoesNotMatchData):
        fairness.check_against_training(0.70, MODE, tmp_path)

