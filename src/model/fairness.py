"""fairness: stub (Phase 11).

Purpose: report metrics by audit group. Group columns are never model inputs.
Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 11 (bootstrap range per group; no claim of 'fair').

Nothing here has logic yet. Each function raises NotImplementedError until Phase 11.
"""

from __future__ import annotations

from typing import Any


def group_audit(probabilities: Any, labels: Any, audit: Any, config: dict[str, Any]) -> Any:
    """Return AUC, mean score, band shares and calibration per group, each with a range."""
    raise NotImplementedError("fairness.group_audit is not implemented yet (Phase 11).")
