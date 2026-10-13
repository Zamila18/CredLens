"""Checks that hold for every public data mode at once.

Owner role: B (data engineer).
Implements: PROJECT_BRIEF section 18, item 29 (one design for all public modes) and the
    rule that group columns are audit-only.

Each mode has its own test file for its own details. The tests here guard what must be
the same everywhere, so a fifth source cannot quietly break a rule.
"""

from __future__ import annotations

import pytest

from src.adapters.base import SOURCE_RECORDS
from src.config import VALID_MODES, coverage_weights_for_mode, load_config
from src.features.dictionary import expected_directions, features_for_mode, load_dictionary
from src.features.source_features import (
    BUILDERS,
    CONTEXT_COLUMNS,
    COVERAGE_COLUMNS,
    MODEL_INPUTS,
)
from src.model.split import RANDOM_SPLIT_MODES

PUBLIC_MODES = [mode for mode in VALID_MODES if mode != "synthetic_bd"]


@pytest.fixture(scope="module")
def config() -> dict:
    return load_config()


def test_every_public_mode_has_a_feature_builder():
    assert set(BUILDERS) == set(PUBLIC_MODES)
    assert set(MODEL_INPUTS) == set(CONTEXT_COLUMNS) == set(COVERAGE_COLUMNS) == set(PUBLIC_MODES)


@pytest.mark.parametrize("mode", PUBLIC_MODES)
def test_inputs_context_and_coverage_never_overlap(mode, config):
    inputs, context = set(MODEL_INPUTS[mode]), set(CONTEXT_COLUMNS[mode])
    coverage = set(COVERAGE_COLUMNS[mode])
    assert not inputs & context and not inputs & coverage and not context & coverage
    audit = set(config["fairness"]["audit_only_columns"][mode])
    assert not inputs & audit, "a group column may never be a model input"
    assert len(inputs) <= config["score"]["max_inputs_for_exact_reasons"]


@pytest.mark.parametrize("mode", PUBLIC_MODES)
def test_coverage_columns_are_the_items_of_the_config_weights(mode, config):
    weights = coverage_weights_for_mode(config, mode)
    assert [f"cov_{name}" for name in weights] == COVERAGE_COLUMNS[mode]
    assert sum(weights.values()) == pytest.approx(1.0)


@pytest.mark.parametrize("mode", PUBLIC_MODES)
def test_the_dictionary_covers_exactly_the_model_inputs(mode):
    dictionary = load_dictionary()
    assert list(features_for_mode(dictionary, mode)) == MODEL_INPUTS[mode]
    assert set(expected_directions(dictionary, mode)) == set(MODEL_INPUTS[mode])
    groups = dictionary["groups"]
    for name, entry in features_for_mode(dictionary, mode).items():
        assert entry["group"] in groups, name
        assert entry["definition"].strip(), name


@pytest.mark.parametrize("mode", PUBLIC_MODES)
def test_every_public_mode_takes_its_labels_from_the_source(mode, config):
    assert mode in config["labels"]["supplied_by_source"]


def test_only_the_sources_without_dates_use_a_random_split():
    assert set(RANDOM_SPLIT_MODES) == {"taiwan_cc", "homecredit"}


def test_source_records_is_not_a_contract_table():
    from src.adapters.base import CONTRACT

    assert SOURCE_RECORDS not in CONTRACT
