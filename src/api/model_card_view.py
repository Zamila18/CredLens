"""What GET /model/card returns.

Purpose: serve the model card for the active data mode.
Owner role: D (full-stack). The card itself is written by the model-card writer (Phase 11).
Implements: PROJECT_BRIEF section 8 and docs/HANDOVER.md Part E ("fixture for now; Zamila
    fills it in Phase 11").

If `reports/<mode>/model_card.json` exists it is served as it is (checked against the
`ModelCard` shape). Until then a placeholder is served: it carries the real model version,
the plain-words limitations from the sample file, and a note that no results are shown
because the model card has not been written. No metric is invented here.
"""

from __future__ import annotations

import json

from src.api.schemas import ModelCard
from src.config import PROJECT_ROOT

CARD_FILE = "model_card.json"

PLACEHOLDER_NOTE = (
    "The model card for this data mode has not been written yet, so no results are shown here."
)
PLACEHOLDER_USE = "Decision support for credit officers. The officer decides and records why."
PLACEHOLDER_LIMITATIONS = [
    "All results use synthetic data. They show that the pipeline is sound, not that the model "
    "is accurate on ShopUp merchants.",
    "The delivery (REDX) signal is a hypothesis tested by ablation, including a zero-signal "
    "control. It is not an established predictor of repayment.",
    "Labels exist only for merchants who previously received credit. The model may not "
    "generalize to applicants who would have been declined under earlier policy.",
    "Scores are less certain for merchants with short history. A thin file is never treated "
    "as a bad file.",
    "Town tier, shop type and licence status are used only to audit results, never as model "
    "inputs.",
    "The tool supports a human decision. It must not be used for automatic approval or decline.",
]


def load_model_card(mode: str, model_version: str | None) -> ModelCard:
    """The written model card for `mode`, or the placeholder."""
    path = PROJECT_ROOT / "reports" / mode / CARD_FILE
    if path.exists():
        return ModelCard.model_validate(json.loads(path.read_text(encoding="utf-8")))
    return ModelCard(
        data_mode=mode,
        model_version=model_version or "no model loaded",
        intended_use=PLACEHOLDER_USE,
        metrics={"note": PLACEHOLDER_NOTE},
        limitations=PLACEHOLDER_LIMITATIONS,
    )
