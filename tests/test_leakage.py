"""test_leakage: placeholders (Phase 3: feature builder).

Owner role: B (data engineer) with C (ML engineer).
Implements: docs/MODEL_SPEC.md section 3 (no feature may read a row dated on or after the cutoff).

Each test below is skipped until its phase. The docstring says what it must prove.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Phase 3: feature builder")
def test_no_feature_uses_data_on_or_after_the_cutoff():
    """Features for a loan come only from events strictly before its issue date."""

@pytest.mark.skip(reason="Phase 3: feature builder")
def test_a_planted_future_row_is_caught():
    """A deliberately future-dated row must make the leakage check fail."""
