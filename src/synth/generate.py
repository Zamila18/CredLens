"""generate: stub (Phase 1).

Purpose: build the synthetic merchants, purchases, deliveries, payments, loans,
    questionnaire answers and consents for the `synthetic_bd` data mode.
Owner role: B (data engineer).
Implements: docs/GENERATOR_SPEC.md and PROJECT_BRIEF section 5.

Nothing here has logic yet. Each function raises NotImplementedError until Phase 1.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def generate(config: dict[str, Any], out_dir: Path | None = None) -> dict[str, Path]:
    """Generate every contract table as CSV and return the file paths. Same seed, same data."""
    raise NotImplementedError("generate.generate is not implemented yet (Phase 1).")
