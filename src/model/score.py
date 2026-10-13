"""Turn a calibrated probability into score, coverage and band.

Purpose: the readiness score an officer sees, the coverage percentage beside it, and the
    band (Strong / Review / Needs more info).
Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 7 and PROJECT_BRIEF section 18 (coverage is per
    data mode).

`score_from_probability` is implemented. Coverage and band arrive in Phase 5.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def score_from_probability(probability: Any, config: dict[str, Any]) -> Any:
    """Return round(scale x probability): the 0-100 score. Never a bare 0/1.

    Works for one probability (returns an int) or many (returns an integer array).
    A value exactly halfway, such as 69.5, rounds to the nearest even number (70), the
    same rule Python's own `round` uses. Everything that compares a score with a band
    line must go through this function, so the comparison matches what is displayed.
    """
    scale = config["score"]["scale"]
    scores = np.rint(scale * np.asarray(probability, dtype=float)).astype(int)
    return int(scores) if scores.ndim == 0 else scores


def coverage_from_checklist(checklist: dict[str, bool], weights: dict[str, float]) -> float:
    """Return coverage between 0 and 1 from the weighted checklist of the data mode."""
    raise NotImplementedError("score.coverage_from_checklist is not implemented yet (Phase 5).")


def band_for(score: int, coverage: float, config: dict[str, Any]) -> str:
    """Return 'Needs more info' when coverage is low, whatever the score; else Strong or Review."""
    raise NotImplementedError("score.band_for is not implemented yet (Phase 5).")
