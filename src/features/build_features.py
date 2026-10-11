"""build_features: stub (Phase 3).

Purpose: compute every feature in docs/FEATURE_DICTIONARY.md as of each loan's
    cutoff date, using strictly earlier data, plus the coverage features.
Owner role: B (data engineer), with C for the model-facing columns.
Implements: PROJECT_BRIEF section 6 and docs/MODEL_SPEC.md section 3.

Nothing here has logic yet. Each function raises NotImplementedError until Phase 3.
"""

from __future__ import annotations

from typing import Any


def build_features(tables: dict[str, Any], config: dict[str, Any]) -> Any:
    """Return one row per loan with features built only from data before its cutoff."""
    raise NotImplementedError("build_features.build_features is not implemented yet (Phase 3).")
