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


SYNTHETIC_MODE = "synthetic_bd"


def features_for_mode(dictionary: dict[str, Any], mode: str | None = None) -> dict[str, Any]:
    """The dictionary entries of one data mode.

    The synthetic data uses the main `features` section. Each public data mode has its
    own entries under `source_features`, built only from fields that source really has.
    """
    if mode is None or mode == SYNTHETIC_MODE:
        return dictionary["features"]
    entries = (dictionary.get("source_features") or {}).get(mode)
    if entries is None:
        raise KeyError(f"The feature dictionary has no entries for data mode {mode!r} yet.")
    return entries


def expected_directions(dictionary: dict[str, Any], mode: str | None = None) -> dict[str, int]:
    """For every model input: +1 if a higher value should raise the score, -1 if lower it.

    Read from `higher_is: better | worse` in the dictionary. Entries without it (context
    columns, questionnaire items) are not model inputs and are left out. `mode` picks the
    data mode; the default is the synthetic data.
    """
    meaning = {"better": 1, "worse": -1}
    return {
        name: meaning[entry["higher_is"]]
        for name, entry in features_for_mode(dictionary, mode).items()
        if entry.get("higher_is") in meaning
    }


CONDITIONS = {
    "above": lambda value, limit: value > limit,
    "below": lambda value, limit: value < limit,
    "at_least": lambda value, limit: value >= limit,
    "at_most": lambda value, limit: value <= limit,
}


def statement_holds(entry: dict[str, Any], raised_score: bool, value: float) -> bool:
    """True when the sentence for this direction is a true statement about the value.

    A contribution is measured against the average merchant, but some sentences make a
    plain claim: "No recent late payments" must mean none, and "purchases are growing"
    must mean growth above zero. `shown_when` in the dictionary holds those conditions.
    An entry without one has sentences that compare with similar shops, which are true
    whenever the contribution points that way.
    """
    conditions = (entry.get("shown_when") or {}).get("positive" if raised_score else "negative")
    if not conditions:
        return True
    return all(CONDITIONS[name](value, limit) for name, limit in conditions.items())


def reason_sentences(
    entry: dict[str, Any], raised_score: bool, value: float
) -> dict[str, str] | None:
    """The sentence to show for an input that raised or lowered the score, in both languages.

    The plain sentence if it is true for this value; else the comparing sentence under
    `otherwise`; else None (nothing truthful to say, so no reason is shown).
    """
    side = "positive" if raised_score else "negative"
    if entry.get(side) and statement_holds(entry, raised_score, value):
        return entry[side]
    return (entry.get("otherwise") or {}).get(side)


def _format_value(value: float, style: str) -> str:
    if style == "share":
        return f"{100 * value:.1f}%"
    if style == "percent_change":
        return f"{value:+.0f}%"
    if style == "days":
        return f"{value:.1f} days"
    if style == "hours":
        return f"{value:.0f} hours"
    if style == "months":
        return f"{value:.1f} months"
    if style == "months_change":
        return f"{value:+.1f} months"
    if style == "share_change":
        return f"{100 * value:+.1f}%"
    if style == "count":
        return f"{value:.0f}" if float(value).is_integer() else f"{value:.1f}"
    raise ValueError(f"Unknown detail format: {style!r}")


def detail_text(entry: dict[str, Any], value: float, average: float) -> str | None:
    """The number shown beside a reason, e.g. "Returns 7.5% vs average 7.0%".

    `average` is the training average of that input (the "average merchant" a score is
    explained against). Returns None for an entry with no `detail` in the dictionary.
    """
    detail = entry.get("detail")
    if not detail:
        return None
    style = detail["format"]
    shown, typical = _format_value(value, style), _format_value(average, style)
    return f"{detail['label']} {shown} vs average {typical}"
