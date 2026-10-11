"""split: stub (Phase 4).

Purpose: split loans into train, validation and test periods by time.
Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 4 (never a random split, except taiwan_cc, marked weaker).

Nothing here has logic yet. Each function raises NotImplementedError until Phase 4.
"""

from __future__ import annotations

from typing import Any


def split_by_time(loans: Any, config: dict[str, Any]) -> dict[str, Any]:
    """Return the train, validation and test rows using the months in config."""
    raise NotImplementedError("split.split_by_time is not implemented yet (Phase 4).")
