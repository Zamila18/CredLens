"""test_master_data: placeholders (Phase 2: database).

Owner role: B (data engineer).
Implements: PROJECT_BRIEF section 13.5 (merchants is the single master table).

Each test below is skipped until its phase. The docstring says what it must prove.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Phase 2: database")
def test_no_duplicate_merchant_ids():
    """Every merchant_id appears once in the master table."""

@pytest.mark.skip(reason="Phase 2: database")
def test_every_foreign_key_resolves():
    """Every purchase, delivery, payment, loan and consent points to a real merchant."""

@pytest.mark.skip(reason="Phase 2: database")
def test_decisions_are_append_only():
    """A decision row cannot be updated or deleted."""
