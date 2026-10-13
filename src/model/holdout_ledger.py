"""Keep count of every time the held-out test period is looked at.

Purpose: the test period is meant to be touched once, for the final report. Nothing can
    physically stop a person from measuring on it again, so every look is written down
    and the model card reports the count. An honest count is better than a claim of
    "touched once" that nobody can check.
Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 4 ("touch test once for the final report").

The ledger is a small JSON file per data mode: reports/<mode>/test_set_use.json.
It is committed, so the history travels with the repository.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import PROJECT_ROOT

LEDGER_NAME = "test_set_use.json"


def ledger_path(mode: str, reports_dir: Path | None = None) -> Path:
    """Where the ledger of one data mode lives."""
    base = Path(reports_dir) if reports_dir is not None else PROJECT_ROOT / "reports"
    return base / mode / LEDGER_NAME


def read_ledger(mode: str, reports_dir: Path | None = None) -> list[dict[str, Any]]:
    """Every recorded look at the test period, oldest first. Empty if there were none."""
    path = ledger_path(mode, reports_dir)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def record_test_use(
    mode: str, purpose: str, detail: str = "", reports_dir: Path | None = None
) -> int:
    """Write down one look at the test period and return how many there have been.

    Args:
        mode: the data mode, for example "synthetic_bd".
        purpose: why the test period was used, in a few words.
        detail: anything that helps a reader judge it (model version, what was measured).
    """
    entries = read_ledger(mode, reports_dir)
    entries.append(
        {
            "number": len(entries) + 1,
            "when": datetime.now().isoformat(timespec="seconds"),
            "purpose": purpose,
            "detail": detail,
        }
    )
    path = ledger_path(mode, reports_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    return len(entries)
