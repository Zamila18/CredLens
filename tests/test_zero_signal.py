"""test_zero_signal: placeholders (Phase 11: ablation).

Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 10 (the negative control).

Each test below is skipped until its phase. The docstring says what it must prove.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Phase 11: ablation")
def test_delivery_features_add_nothing_at_signal_strength_zero():
    """At signal strength 0, feature set C beats B by no more than zero_signal_max_auc_gain."""
