"""test_no_autodecision: placeholders (Phase 9: API).

Owner role: D (full-stack).
Implements: CLAUDE.md (no code path may approve or decline credit) and PROJECT_BRIEF section 8.

Each test below is skipped until its phase. The docstring says what it must prove.
The API contract already has no approve or decline action: see
tests/test_fixtures.py::test_api_contract_has_no_approve_or_decline_action.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Phase 9: API")
def test_no_endpoint_changes_a_loan_status():
    """Calling every endpoint leaves loan statuses exactly as they were."""


@pytest.mark.skip(reason="Phase 9: API")
def test_scoring_never_writes_a_decision():
    """Reading a score records no decision. Only an officer action does."""


@pytest.mark.skip(reason="Phase 9: API")
def test_override_requires_a_written_reason():
    """The API rejects an override that has no reason text."""
