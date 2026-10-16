"""Tests for the model cards (src/model/model_card.py).

The cards are built from the committed reports, so these tests also check that every
data mode has a card the API can serve, with numbers equal to the reports.
"""

from __future__ import annotations

import json

import pytest

from src.api import model_card_view
from src.api.schemas import ModelCard
from src.config import VALID_MODES, load_config
from src.model import model_card
from src.model.fairness import FLAGGED, NO_GAP, TOO_FEW

FORBIDDEN_WORDS = ("approved", "declined", "eligible", "is fair", "proven")


@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.fixture(scope="module")
def cards(config):
    return {mode: model_card.build_card(mode, config) for mode in VALID_MODES}


def _metrics(mode: str) -> dict:
    path = model_card.REPORTS_DIR / mode / "metrics.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_every_mode_has_a_card_the_api_can_serve(cards):
    for mode, card in cards.items():
        served = ModelCard.model_validate(card)
        assert served.data_mode == mode
        assert served.model_version == _metrics(mode)["model_version"]


def test_the_numbers_are_the_reports_numbers(cards):
    for mode, card in cards.items():
        validation = _metrics(mode)["validation"]
        assert card["metrics"]["roc_auc"] == round(validation["metrics"]["roc_auc"], 6)
        assert card["metrics"]["roc_auc_range"] == [
            round(value, 6) for value in validation["ranges"]["roc_auc"]
        ]


def test_officers_see_no_feature_names(cards):
    for mode, card in cards.items():
        inputs = card["metrics"]["inputs"]
        for name in _metrics(mode)["inputs_used"]:
            assert name not in inputs, f"{mode}: feature name {name} on the card"


def test_only_the_synthetic_model_is_meant_for_officers(cards):
    for mode, card in cards.items():
        if mode == "synthetic_bd":
            assert card["intended_use"] == model_card.INTENDED_USE
            assert card["ablation"], "the synthetic card carries the ablation"
        else:
            assert card["intended_use"] == model_card.PUBLIC_USE
            assert card["ablation"] == []


def test_every_card_names_its_source_and_says_decision_support_only(cards):
    for card in cards.values():
        assert card["metrics"]["banner"].endswith("Decision support only.")
        assert any("automatic approval or decline" in limit for limit in card["limitations"])


def test_no_card_overclaims(cards):
    for mode, card in cards.items():
        # The one allowed use of "fair" says the opposite of a claim.
        text = json.dumps(card).lower().replace("does not show that the model is fair", "")
        for word in FORBIDDEN_WORDS:
            assert word not in text, f"{mode}: '{word}' on the card"


def test_small_groups_stay_small_on_the_card(cards):
    for card in cards.values():
        for row in card["group_results"]:
            if row["ranking"] == TOO_FEW:
                assert set(row) == {"column", "group", "loans", "ranking", "calibration"}


def test_flagged_gaps_become_plain_sentences():
    fairness = {
        "seeds": [42],
        "groups": [
            {
                "column": "town_tier", "group": "small_town", "loans": 400,
                "share_repaid": 0.85, "roc_auc": 0.70, "rest_roc_auc": 0.71,
                "predicted_minus_actual": 0.10, "ranking": NO_GAP, "calibration": FLAGGED,
            }
        ],
    }
    fairness["groups"][0]["rest_predicted_minus_actual"] = -0.004
    (sentence,) = model_card.group_findings(fairness)
    assert sentence.startswith("Calibration differs for town tier 'small_town' (400 loans")
    assert "expects 10 points more repayment than happened for this group" in sentence
    assert model_card._points(0.012) == "1 point more repayment than happened"
    assert "about as much repayment as happened for everyone else" in sentence
    quiet = {"seeds": [42, 7, 123], "groups": []}
    assert model_card.group_findings(quiet) == [
        "No group gap was flagged in any of 3 seeds on these data."
    ]


def test_a_mode_without_a_training_report_gets_no_card(tmp_path, config):
    with pytest.raises(FileNotFoundError):
        model_card.build_card("taiwan_cc", config, reports_dir=tmp_path)


def test_cards_are_written_where_the_api_reads_them(tmp_path, config, monkeypatch):
    reports, docs = tmp_path / "reports", tmp_path / "docs"
    (reports / "synthetic_bd").mkdir(parents=True)
    docs.mkdir()
    for name in ("metrics.json", "fairness.json"):
        source = model_card.REPORTS_DIR / "synthetic_bd" / name
        (reports / "synthetic_bd" / name).write_text(source.read_text(encoding="utf-8"))
    json_path, page_path = model_card.write_card("synthetic_bd", config, reports, docs)
    assert page_path.read_text(encoding="utf-8").startswith("# Model card: synthetic_bd")

    monkeypatch.setattr(model_card_view, "PROJECT_ROOT", tmp_path)
    served = model_card_view.load_model_card("synthetic_bd", "ignored")
    written = json.loads(json_path.read_text(encoding="utf-8"))
    assert served.model_version == written["model_version"]
    assert served.group_results


def test_a_card_for_another_model_version_says_so(tmp_path, monkeypatch):
    folder = tmp_path / "reports" / "taiwan_cc"
    folder.mkdir(parents=True)
    source = model_card.REPORTS_DIR / "taiwan_cc" / model_card.CARD_FILE
    written = source.read_text(encoding="utf-8")
    (folder / model_card.CARD_FILE).write_text(written, encoding="utf-8")
    version = json.loads(written)["model_version"]
    monkeypatch.setattr(model_card_view, "PROJECT_ROOT", tmp_path)

    same = model_card_view.load_model_card("taiwan_cc", version)
    assert not same.limitations[0].startswith("This card was written")
    other = model_card_view.load_model_card("taiwan_cc", "a-newer-version")
    assert other.limitations[0] == model_card_view.stale_card_warning(version, "a-newer-version")


def test_an_audit_of_an_older_model_is_left_off_the_card(tmp_path, config):
    folder = tmp_path / "synthetic_bd"
    folder.mkdir()
    source = model_card.REPORTS_DIR / "synthetic_bd"
    (folder / "metrics.json").write_text((source / "metrics.json").read_text(encoding="utf-8"))
    fairness = json.loads((source / "fairness.json").read_text(encoding="utf-8"))
    fairness["model_version"] = "an-older-version"
    (folder / "fairness.json").write_text(json.dumps(fairness))
    card = model_card.build_card("synthetic_bd", config, reports_dir=tmp_path)
    assert card["group_results"] == []
    assert "No group audit has been run for this model version" in card["metrics"][
        "group_findings"
    ]


def test_the_card_uses_plain_words_and_clean_keys(cards):
    synthetic = cards["synthetic_bd"]
    assert set(synthetic["ablation"][0]) >= {"auc_A", "auc_B", "auc_C", "auc_D"}
    assert "ablation_runs" in synthetic["metrics"]
    for card in cards.values():
        assert card["metrics"]["model"] in {
            "logistic regression", "LightGBM (boosted decision trees)"
        }
        assert "_" not in card["metrics"]["split"] and "_" not in card["metrics"]["calibration"]
        assert card["metrics"]["auc_benchmark"] == load_config()["sanity"]["useful_auc_benchmark"]


def test_the_card_says_why_this_model_and_states_the_time_split_gap(cards):
    for mode, card in cards.items():
        choice = _metrics(mode)["model_choice"]
        said = card["metrics"]["model_choice"]
        assert "Not met" not in said
        lightgbm = choice["chosen"] == "lightgbm"
        assert said.endswith("LightGBM is used." if lightgbm else "logistic regression stays.")
        time_split = _metrics(mode)["split"]["method"] == "time"
        assert (model_card.TIME_SPLIT_LIMIT in card["limitations"]) == time_split


def test_every_sentence_on_a_card_has_a_bangla_twin(cards):
    for mode, card in cards.items():
        m = card["metrics"]
        sentences = [k for k, v in m.items() if isinstance(v, str) and not k.endswith("_bn")]
        for key in sentences:
            assert m.get(f"{key}_bn"), f"{mode}: no Bangla for {key}"
            same = m[f"{key}_bn"] == m[key]
            assert not same or key in ("split", "model"), f"{mode}: {key}_bn is English"
        assert len(card["limitations_bn"]) == len(card["limitations"])
        assert m["inputs_bn"].count(" | ") == m["inputs"].count(" | ")
        assert m["banner_bn"].endswith("শুধু সিদ্ধান্তে সহায়তা।")


def test_a_stale_card_warns_in_both_languages(tmp_path, monkeypatch):
    folder = tmp_path / "reports" / "taiwan_cc"
    folder.mkdir(parents=True)
    source = model_card.REPORTS_DIR / "taiwan_cc" / model_card.CARD_FILE
    written = source.read_text(encoding="utf-8")
    (folder / model_card.CARD_FILE).write_text(written, encoding="utf-8")
    monkeypatch.setattr(model_card_view, "PROJECT_ROOT", tmp_path)
    card = model_card_view.load_model_card("taiwan_cc", "a-newer-version")
    assert card.limitations[0].startswith("This card was written")
    assert card.limitations_bn[0].startswith("এই কার্ড মডেল সংস্করণ")

