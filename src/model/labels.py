"""labels: stub (Phase 4).

Purpose: turn loans and payments into training labels.
Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 2 (30-day rule, loans under 60 days excluded).

Nothing here has logic yet. Each function raises NotImplementedError until Phase 4.
"""

from __future__ import annotations

from typing import Any


def build_labels(loans: Any, payments: Any, config: dict[str, Any], as_of: Any) -> Any:
    """Return label 1 (repaid within the allowed days late) or 0; drop loans too young to judge."""
    raise NotImplementedError("labels.build_labels is not implemented yet (Phase 4).")
