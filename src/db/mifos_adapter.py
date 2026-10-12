"""mifos_adapter: stub (Phase 2).

Purpose: export synthetic clients and loans in a Mifos X-importable shape (CSV/JSON).
    This export is the Mifos X deliverable; no live Mifos integration is claimed.
Owner role: B (data engineer).
Implements: PROJECT_BRIEF sections 13 and 18.

Nothing here has logic yet. Each function raises NotImplementedError until Phase 2.
"""

from __future__ import annotations

from pathlib import Path


def export_mifos(database_url: str, out_dir: Path) -> dict[str, Path]:
    """Write Mifos X-style client and loan files and return their paths."""
    raise NotImplementedError("mifos_adapter.export_mifos is not implemented yet (Phase 2).")
