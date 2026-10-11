"""test_reasons: placeholders (Phase 6: SHAP reasons).

Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 8 and docs/FEATURE_DICTIONARY.md.

Each test below is skipped until its phase. The docstring says what it must prove.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Phase 6: SHAP reasons")
def test_three_reasons_up_and_three_down():
    """A score comes with the top 3 reasons that raise it and the top 3 that lower it."""

@pytest.mark.skip(reason="Phase 6: SHAP reasons")
def test_every_reason_maps_to_a_dictionary_sentence():
    """Each reason is a dictionary sentence in English and Bangla, never a feature name."""

@pytest.mark.skip(reason="Phase 6: SHAP reasons")
def test_reasons_sum_to_the_score():
    """Baseline, top reasons and all other features add up to the score shown."""

@pytest.mark.skip(reason="Phase 6: SHAP reasons")
def test_missing_features_produce_no_reason():
    """A feature the merchant does not have never appears as a reason."""
