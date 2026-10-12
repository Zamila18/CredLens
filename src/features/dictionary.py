"""Load the feature dictionary (reason sentences in English and Bangla).

Purpose: give the rest of the code one way to read `dictionary.yaml`.
Owner role: B (data engineer) for features, A (lead) for wording.
Implements: docs/FEATURE_DICTIONARY.md ("code must load these from src/features/dictionary.yaml").
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DICTIONARY_PATH = Path(__file__).resolve().parent / "dictionary.yaml"

# Words that every questionnaire sentence must carry (docs/FEATURE_DICTIONARY.md, Rules).
DIRECTIONAL_WORDS = {"en": "directional", "bn": "ইঙ্গিতমাত্র"}


def load_dictionary(path: Path | str | None = None) -> dict[str, Any]:
    """Return the dictionary as a plain dict with `groups`, `features`, `coverage_only`."""
    dictionary_path = Path(path) if path is not None else DICTIONARY_PATH
    with dictionary_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def reason_sentence(
    dictionary: dict[str, Any], feature: str, raised_score: bool, language: str = "en"
) -> str | None:
    """Return the sentence for a feature that raised or lowered the score.

    Returns None when the dictionary has no sentence for that direction
    (for example `delivery_data_thin` has no positive sentence).
    """
    entry = dictionary["features"][feature]
    sentences = entry["positive" if raised_score else "negative"]
    if sentences is None:
        return None
    return sentences[language]
