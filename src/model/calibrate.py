"""calibrate: stub (Phase 5).

Purpose: make the model's number mean a probability (Platt or isotonic).
Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 6 (fitted on validation only, then frozen).

Nothing here has logic yet. Each function raises NotImplementedError until Phase 5.
"""

from __future__ import annotations

from typing import Any


def fit_calibrator(scores: Any, labels: Any, config: dict[str, Any]) -> Any:
    """Fit the calibrator on the validation period only and return it."""
    raise NotImplementedError("calibrate.fit_calibrator is not implemented yet (Phase 5).")
