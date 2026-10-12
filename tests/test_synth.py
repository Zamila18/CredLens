"""test_synth: placeholders (Phase 1: synthetic generator).

Owner role: B (data engineer).
Implements: docs/GENERATOR_SPEC.md (required self-checks).

Each test below is skipped until its phase. The docstring says what it must prove.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Phase 1: synthetic generator")
def test_row_counts_and_reproducibility():
    """Same seed gives the same row counts and the same data."""

@pytest.mark.skip(reason="Phase 1: synthetic generator")
def test_thin_file_share_is_near_target():
    """About 35% of new merchants have very few early purchases."""

@pytest.mark.skip(reason="Phase 1: synthetic generator")
def test_repayment_share_is_in_range():
    """Repaid share is roughly 75 to 85%."""

@pytest.mark.skip(reason="Phase 1: synthetic generator")
def test_dates_are_in_order():
    """No event is dated before the merchant was onboarded."""

@pytest.mark.skip(reason="Phase 1: synthetic generator")
def test_delivery_signal_is_absent_at_strength_zero():
    """At signal strength 0, delivery features do not track hidden reliability."""

@pytest.mark.skip(reason="Phase 1: synthetic generator")
def test_logistics_noise_returns_are_present():
    """Part of returns and failures is tagged address_issue or rider_issue."""
