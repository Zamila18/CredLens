"""explain: stub (Phase 6).

Purpose: explain a score as three reasons that raise it and three that lower it.
Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 8 and docs/FEATURE_DICTIONARY.md.

Nothing here has logic yet. Each function raises NotImplementedError until Phase 6.
"""

from __future__ import annotations

from typing import Any


def explain_score(model: Any, feature_row: Any, config: dict[str, Any]) -> dict[str, Any]:
    """Return top reasons as dictionary sentences (English and Bangla) that sum to the score."""
    raise NotImplementedError("explain.explain_score is not implemented yet (Phase 6).")
