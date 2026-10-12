"""Where the synthetic tables live on disk.

Purpose: one place that knows the folder for each delivery signal strength, shared by
    the generator (which writes) and the synthetic adapter (which reads).
Owner role: B (data engineer).
Implements: docs/GENERATOR_SPEC.md (one data set per signal strength: 0, 0.5 and 1).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.config import PROJECT_ROOT

# File that holds the hidden truth (reliability and other generator-only facts).
# Tests use it to check the generator. The pipeline must never read it.
LATENT_FILE = "_latent_truth.csv"
META_FILE = "_meta.json"


def strength_folder(strength: float) -> str:
    """Folder name for one delivery signal strength, for example 'strength_0.5'."""
    return f"strength_{strength:g}"


def output_dir(config: dict[str, Any], strength: float | None = None) -> Path:
    """Where the tables for one signal strength are written and read."""
    if strength is None:
        strength = config["data"]["delivery_signal_strength"]
    base = Path(config["generator"]["out_dir"])
    if not base.is_absolute():
        base = PROJECT_ROOT / base
    return base / strength_folder(float(strength))
