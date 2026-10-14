"""Which inputs a model gets, per data mode, and the simpler model it must beat.

Purpose: the one place training asks "what are the model inputs of this data mode?".
Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md sections 3 and 9 (source-specific features; baselines to
    beat) and PROJECT_BRIEF section 18, items 29 to 32.

Every mode is trained by the same code. What differs is the list of inputs, and the
"simpler model": a model with only part of the inputs, fitted the same way, that shows
what the rest of the inputs add. For each mode the simpler model answers a question that
matters for reading its result:

- synthetic_bd: purchases only. What does a platform know before any credit or delivery
  history exists?
- taiwan_cc: the latest month only. Does six months of behaviour say more than whether
  the last bill was late?
- india_ltfs: the loan's terms only. That is all there is for the half of the borrowers
  who have no bureau record.
- homecredit: without the outside score. How much of the ranking is the applicant's own
  repayment behaviour, and how much is a score bought from elsewhere?
- kiva_asia: without the field partner. How much is about the loan, and how much is
  about the intermediary?
"""

from __future__ import annotations

from typing import Any

from src.features.build_features import model_feature_names
from src.features.dictionary import SYNTHETIC_MODE, features_for_mode
from src.features.homecredit import EXTERNAL_INPUTS
from src.features.kiva_asia import PARTNER_INPUTS
from src.features.source_features import MODEL_INPUTS

SIMPLER_MODELS: dict[str, dict[str, Any]] = {
    SYNTHETIC_MODE: {
        "name": "purchases_only",
        "description": (
            "purchases only: what a platform knows before any credit or delivery history"
        ),
        "features": lambda: model_feature_names("A"),
    },
    "taiwan_cc": {
        "name": "latest_month_only",
        "description": "only whether the most recent monthly bill was paid late",
        "features": lambda: ["latest_delay_months"],
    },
    "india_ltfs": {
        "name": "loan_terms_only",
        "description": (
            "only the loan's terms: all that exists for a borrower with no bureau record"
        ),
        "features": lambda: ["down_payment_share"],
    },
    "homecredit": {
        "name": "without_outside_score",
        "description": (
            "the applicant's own repayment behaviour and loan terms, without the outside score"
        ),
        "features": lambda: [n for n in MODEL_INPUTS["homecredit"] if n not in EXTERNAL_INPUTS],
    },
    "kiva_asia": {
        "name": "without_field_partner",
        "description": "the loan's terms only, without the two inputs about the field partner",
        "features": lambda: [n for n in MODEL_INPUTS["kiva_asia"] if n not in PARTNER_INPUTS],
    },
}


def model_inputs(mode: str) -> list[str]:
    """The model inputs of a data mode, in a fixed order."""
    if mode == SYNTHETIC_MODE:
        # Purchases, payments and deliveries. The questionnaire is never a model input.
        return model_feature_names("ABC")
    if mode not in MODEL_INPUTS:
        raise ValueError(f"No model inputs are defined for data mode {mode!r}.")
    return list(MODEL_INPUTS[mode])


def simpler_model(mode: str) -> dict[str, Any]:
    """The simpler model of a data mode: its name, what it means, and its inputs."""
    if mode not in SIMPLER_MODELS:
        raise ValueError(f"No simpler model is defined for data mode {mode!r}.")
    entry = SIMPLER_MODELS[mode]
    return {
        "name": entry["name"],
        "description": entry["description"],
        "features": list(entry["features"]()),
    }


def input_groups(mode: str, dictionary: dict[str, Any]) -> dict[str, list[str]]:
    """The model inputs of a mode, by the group letter the feature dictionary gives them."""
    entries = features_for_mode(dictionary, mode)
    groups: dict[str, list[str]] = {}
    for name in model_inputs(mode):
        groups.setdefault(entries[name]["group"], []).append(name)
    return groups
