"""model_card: stub (Phase 11).

Purpose: write one model card per data mode, with limitations in plain words.
Owner role: C (ML engineer) with A (lead) for wording.
Implements: docs/MODEL_SPEC.md section 12 and docs/WORDING_AND_QA.md.

Nothing here has logic yet. Each function raises NotImplementedError until Phase 11.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def write_model_card(results: dict[str, Any], config: dict[str, Any]) -> Path:
    """Write docs/model_card_<mode>.md and the JSON served at /model/card."""
    raise NotImplementedError("model_card.write_model_card is not implemented yet (Phase 11).")
