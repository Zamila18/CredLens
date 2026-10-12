"""load: stub (Phase 2).

Purpose: load the contract tables from an adapter into the database.
Owner role: B (data engineer).
Implements: PROJECT_BRIEF sections 4 and 18 (SQLite locally, Supabase Postgres via DATABASE_URL).

Nothing here has logic yet. Each function raises NotImplementedError until Phase 2.
"""

from __future__ import annotations

from typing import Any


def load_tables(tables: dict[str, Any], database_url: str) -> dict[str, int]:
    """Write each table to the database and return the row count per table."""
    raise NotImplementedError("load.load_tables is not implemented yet (Phase 2).")
