"""Tests that the shared training code works for a public data mode.

Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 13 (the same pipeline for every data mode) and
    PROJECT_BRIEF section 18, items 29 and 33.

No real file is read here. A made-up table with the columns of the Taiwan source is
pushed through that mode's feature builder and then through `train_models`, so the test
runs anywhere. Its outcomes are drawn from the made-up behaviour, never from real people.
"""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

from src.config import VALID_MODES, load_config
from src.features.dictionary import features_for_mode, load_dictionary
from src.features.taiwan_cc import BILL_COLUMNS, PAID_COLUMNS, STATUS_COLUMNS, taiwan_features
from src.model.explain import RowsNotShown, explain_score, score_card
from src.model.inputs import input_groups, model_inputs, simpler_model
from src.model.split import RANDOM_SPLIT
from src.model.train import _fit_simpler_model, load_model, save_artifacts, train_models

MODE = "taiwan_cc"
PUBLIC_MODES = [mode for mode in VALID_MODES if mode != "synthetic_bd"]


def made_up_clients(n: int = 3000, seed: int = 7) -> pd.DataFrame:
    """Card statements that look like the Taiwan file, with a hidden tendency to pay late."""
    rng = np.random.default_rng(seed)
    careless = rng.normal(size=n)
    records = pd.DataFrame({"loan_id": [f"T{i}" for i in range(n)]})
    records["merchant_id"] = records["loan_id"].str.replace("T", "M")
    records["LIMIT_BAL"] = rng.choice([20000, 50000, 100000, 200000], size=n)
    for column in STATUS_COLUMNS:
        late = np.clip(np.round(careless + rng.normal(size=n)), -1, 6)
        unused = rng.random(n) < 0.08
        records[column] = np.where(unused, -2, late).astype(int)
    for column in BILL_COLUMNS:
        records[column] = np.round(records["LIMIT_BAL"] * rng.uniform(0, 0.9, size=n))
    for column in PAID_COLUMNS:
        records[column] = np.round(records["LIMIT_BAL"] * rng.uniform(0, 0.3, size=n))
    # One client in ten never used the card: a thin file with only a credit limit.
    thin = rng.random(n) < 0.10
    records.loc[thin, STATUS_COLUMNS] = -2
    records.loc[thin, [*BILL_COLUMNS, *PAID_COLUMNS]] = 0
    records.attrs["careless"] = careless
    return records


@pytest.fixture(scope="module")
def config() -> dict:
    config = copy.deepcopy(load_config())
    config["data"]["mode"] = MODE
    config["model"]["bootstrap_resamples"] = 50
    config["score"]["reasons_report_sample"] = 30
    return config


@pytest.fixture(scope="module")
def dataset(config) -> pd.DataFrame:
    records = made_up_clients()
    careless = records.attrs["careless"]
    features = taiwan_features(records, config)
    rng = np.random.default_rng(8)
    repaid = rng.random(len(features)) < 1 / (1 + np.exp(-(1.3 - 1.1 * careless)))
    features["label"] = repaid.astype(int)
    features["label_status"] = "labelled"
    features["label_source"] = "source"
    features["consent_valid"] = True
    return features


@pytest.fixture(scope="module")
def result(dataset, config) -> dict:
    return train_models(dataset, config, MODE)


# --- which inputs each mode trains on --------------------------------------------------------


@pytest.mark.parametrize("mode", VALID_MODES)
def test_every_mode_has_inputs_and_a_simpler_model(mode):
    inputs = model_inputs(mode)
    simpler = simpler_model(mode)
    assert inputs and len(inputs) == len(set(inputs))
    assert simpler["features"], "a simpler model needs at least one input"
    assert set(simpler["features"]) < set(inputs), "strictly fewer inputs than the full model"
    assert simpler["name"] and simpler["description"]
    groups = input_groups(mode, load_dictionary())
    assert sorted(name for names in groups.values() for name in names) == sorted(inputs)


def test_the_simpler_models_ask_the_questions_the_documents_promise():
    assert simpler_model("synthetic_bd")["name"] == "purchases_only"
    assert simpler_model("homecredit")["name"] == "without_outside_score"
    assert "external_score" not in simpler_model("homecredit")["features"]
    assert simpler_model("kiva_asia")["features"] == ["repayment_term_months"]
    assert simpler_model("india_ltfs")["features"] == ["down_payment_share"]


def test_an_unknown_mode_is_refused():
    with pytest.raises(ValueError, match="No model inputs"):
        model_inputs("a_mode_that_does_not_exist")


# --- training a public mode -------------------------------------------------------------------


def test_training_uses_that_mode_s_inputs_and_split(result):
    report = result["report"]
    assert report["data_mode"] == MODE
    assert report["split"]["method"] == RANDOM_SPLIT and "Weaker split" in report["split"]["note"]
    assert set(report["inputs_used"]) <= set(model_inputs(MODE))
    assert report["feature_groups"] == {"B": model_inputs(MODE)}
    assert report["validation"]["metrics"]["roc_auc"] > 0.65, "the made-up behaviour is learnable"
    assert "test" not in report


def test_the_simpler_model_is_named_and_beaten(result):
    report = result["report"]
    simpler = report["baselines"]["simpler_model"]
    assert simpler["name"] == "latest_month_only"
    assert simpler["features"] == ["latest_delay_months"]
    gain = report["gain_over_simpler_model"]
    assert gain["auc_gain"] > 0
    assert gain["range"][0] <= gain["auc_gain"] <= gain["range"][1]


def test_coverage_groups_are_reported_for_every_mode(result):
    table = result["report"]["validation_predicted_against_actual"]
    assert {"coverage_below_the_line", "coverage_at_or_above_the_line"} <= set(table)
    assert "first_loans" not in table, "this source cannot tell first loans from later ones"
    assert result["report"]["validation_by_history"] == {}


def test_reasons_use_that_mode_s_sentences(result, config):
    saved = {
        "model": result["model"],
        "calibrator": result["calibrator"],
        "features": result["features"],
        "data_mode": MODE,
        "version_id": "test",
    }
    entries = features_for_mode(load_dictionary(), MODE)
    rows = result["split"].validation
    seen = 0
    for _, row in rows.head(40).iterrows():
        explanation = explain_score(saved, row, config)
        for side in ("positive", "negative"):
            for reason in explanation[f"reasons_{side}"]:
                seen += 1
                entry = entries[reason["code"]]
                allowed = [entry[side], (entry.get("otherwise") or {}).get(side)]
                assert {"en": reason["sentence_en"], "bn": reason["sentence_bn"]} in allowed
                assert "shop" not in reason["sentence_en"].lower()
    assert seen > 40
    card = score_card(saved, rows.iloc[0], config, MODE)
    assert card["data_mode"] == MODE and "Taiwan" in card["banner"]
    assert result["report"]["reasons_check"]["largest_gap"] < 1e-6


def test_the_saved_model_remembers_its_data_mode(result, config, tmp_path):
    metadata = save_artifacts(result, config, artifacts_dir=tmp_path)
    saved = load_model(MODE, artifacts_dir=tmp_path)
    assert saved["data_mode"] == MODE == metadata["data_mode"]
    assert metadata["delivery_signal_strength"] is None, "only the synthetic data has one"
    assert metadata["version_id"].startswith("taiwan_cc-")
    # No mode passed: the reasons still come from the Taiwan entries.
    explanation = explain_score(saved, result["split"].validation.iloc[0], config)
    assert explanation["score"] >= 0


def test_a_simpler_model_that_cannot_be_fitted_does_not_stop_the_run(result, config):
    """Its only input pointing against its meaning: say so, and carry on."""
    split = result["split"]
    upside_down = {name: 1 for name in model_inputs(MODE)}  # "more months late is better"
    raw = result["candidates"][result["model_name"]]["raw"]
    simpler = _fit_simpler_model(config, split, upside_down, raw, MODE)
    assert simpler["gain"] is None
    assert simpler["baseline"]["metrics"] is None
    assert "Could not be fitted" in simpler["baseline"]["note"]


def test_a_band_line_nobody_reaches_is_pointed_out(dataset, config):
    harsh = copy.deepcopy(config)
    harsh["score"]["by_mode"] = {MODE: {"band_strong_min_score": 100}}
    notes = train_models(dataset, harsh, MODE)["report"]["notes"]
    assert any("Almost no validation loan" in note for note in notes)


def test_thin_files_get_their_own_auc(result):
    groups = result["report"]["validation_by_coverage"]
    assert set(groups) == {"coverage_below_the_line", "coverage_at_or_above_the_line"}
    total = sum(part["loans"] for part in groups.values())
    assert total == result["report"]["validation"]["loans"]
    for part in groups.values():
        assert part["roc_auc_range"][0] <= part["roc_auc"] <= part["roc_auc_range"][1]


def test_rows_of_a_source_that_forbids_showing_them_are_refused(result, config):
    """Home Credit's rules allow totals only: no single score card, whoever asks."""
    saved = {
        "model": result["model"],
        "calibrator": result["calibrator"],
        "features": result["features"],
        "data_mode": MODE,
        "version_id": "test",
    }
    hidden = copy.deepcopy(config)
    hidden["data"]["rows_never_shown"] = [MODE]
    with pytest.raises(RowsNotShown, match="never shown"):
        score_card(saved, result["split"].validation.iloc[0], hidden, MODE)
    assert load_config()["data"]["rows_never_shown"] == ["homecredit"]


def test_training_a_mode_whose_files_are_missing_says_so(monkeypatch, tmp_path, capsys):
    """A teammate without the public downloads gets a message and a known exit code."""
    from src.adapters import taiwan_cc as adapter_module
    from src.model import train

    monkeypatch.setattr(adapter_module, "RAW_FOLDER", tmp_path)
    assert train.main(["--mode", MODE]) == train.DATA_MISSING
    assert "Not trained 'taiwan_cc'" in capsys.readouterr().out

