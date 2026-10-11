"""score: stub (Phase 5).

Purpose: turn a calibrated probability into score, coverage and band.
Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 7 and PROJECT_BRIEF section 18 (coverage is per data mode).

Nothing here has logic yet. Each function raises NotImplementedError until Phase 5.
"""

from __future__ import annotations

from typing import Any


def score_from_probability(probability: float, config: dict[str, Any]) -> int:
    """Return round(100 x probability). Never a bare 0/1."""
    raise NotImplementedError("score.score_from_probability is not implemented yet (Phase 5).")


def coverage_from_checklist(checklist: dict[str, bool], weights: dict[str, float]) -> float:
    """Return coverage between 0 and 1 from the weighted checklist of the data mode."""
    raise NotImplementedError("score.coverage_from_checklist is not implemented yet (Phase 5).")


def band_for(score: int, coverage: float, config: dict[str, Any]) -> str:
    """Return 'Needs more info' when coverage is low, whatever the score; else Strong or Review."""
    raise NotImplementedError("score.band_for is not implemented yet (Phase 5).")
