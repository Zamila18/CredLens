"""ablation: stub (Phase 11).

Purpose: compare feature sets A to D at delivery signal strengths 0, 0.5 and 1.
Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 10 (including the zero-signal negative control).

Nothing here has logic yet. Each function raises NotImplementedError until Phase 11.
"""

from __future__ import annotations

from typing import Any


def run_ablation(config: dict[str, Any]) -> dict[str, Any]:
    """Return the AUC gain of each feature group at each signal strength."""
    raise NotImplementedError("ablation.run_ablation is not implemented yet (Phase 11).")
