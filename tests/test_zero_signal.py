"""The negative control: deliveries must add nothing when they carry no signal.

Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 10 and `sanity.zero_signal_max_auc_gain`.

The generator can make deliveries unrelated to whether a merchant repays (signal
strength 0). A pipeline that still found a gain there would be finding signal that does
not exist. The positive control checks the opposite: with full signal, the gain shows.
"""

from __future__ import annotations

import copy

import pytest

from src.config import load_config
from src.model.ablation import RUNS, ablation_on_tables, summarise
from src.synth.generate import build_tables


@pytest.fixture(scope="module")
def config() -> dict:
    small = copy.deepcopy(load_config())
    small["data"]["n_merchants"] = 6000
    small["model"]["bootstrap_resamples"] = 100
    return small


def run_at(config: dict, strength: float) -> dict:
    local = copy.deepcopy(config)
    local["data"]["delivery_signal_strength"] = strength
    tables, _, _ = build_tables(local, strength)
    return ablation_on_tables(tables, local)


@pytest.fixture(scope="module")
def no_signal(config) -> dict:
    return run_at(config, 0.0)


@pytest.fixture(scope="module")
def full_signal(config) -> dict:
    return run_at(config, 1.0)


def test_delivery_features_add_nothing_at_signal_strength_zero(no_signal, config):
    """At signal strength 0, feature set C beats B by no more than zero_signal_max_auc_gain."""
    gain = no_signal["gains"]["C"]
    assert gain["auc_gain"] <= config["sanity"]["zero_signal_max_auc_gain"]
    assert not gain["clearly_better"], "the range of the gain must include zero"


def test_with_full_signal_the_delivery_gain_shows(full_signal, config):
    """The positive control: the same check is able to see a real gain."""
    gain = full_signal["gains"]["C"]
    assert gain["auc_gain"] > 2 * config["sanity"]["zero_signal_max_auc_gain"]
    assert gain["clearly_better"]


def test_every_run_adds_its_group_and_keeps_the_ones_before(no_signal):
    runs = no_signal["runs"]
    assert set(runs) == set(RUNS)
    assert not any(name.startswith("q_") for name in runs["C"]["inputs"]), (
        "the headline inputs never include the questionnaire"
    )
    assert any(name.startswith("q_") for name in runs["D"]["inputs"])
    for before, after in zip("ABC", "BCD"):
        assert set(runs[before]["inputs"]) <= set(runs[after]["inputs"]) | set(
            runs[after]["removed_for_pointing_the_wrong_way"]
        )


def test_the_summary_averages_over_seeds(no_signal, full_signal):
    results = [dict(no_signal, strength=0.0, seed=1), dict(full_signal, strength=1.0, seed=1)]
    summary = summarise(results)
    assert set(summary) == {"0.0", "1.0"}
    expected = full_signal["gains"]["C"]["auc_gain"]
    assert summary["1.0"]["gain"]["C"]["mean"] == pytest.approx(expected)
    assert summary["0.0"]["seeds"] == 1
