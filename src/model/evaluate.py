"""evaluate: stub (Phase 4).

Purpose: measure the model on the test period and write reports.
Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 9 (AUC, PR-AUC, Brier, calibration, top-k, bootstrap
    ranges, baselines).

Nothing here has logic yet. Each function raises NotImplementedError until Phase 4.
"""

from __future__ import annotations

from typing import Any


def evaluate(probabilities: Any, labels: Any, config: dict[str, Any]) -> dict[str, Any]:
    """Return metrics with bootstrap ranges; warn when AUC looks too good to be true."""
    raise NotImplementedError("evaluate.evaluate is not implemented yet (Phase 4).")
