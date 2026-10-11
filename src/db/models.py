"""models: stub (Phase 2).

Purpose: SQLAlchemy tables for the data contract plus users, decisions (append-only),
    audit_log and model_versions, shaped after Mifos X concepts.
Owner role: B (data engineer).
Implements: PROJECT_BRIEF sections 5, 13 and 18.

Nothing here has logic yet. Each function raises NotImplementedError until Phase 2.
"""

from __future__ import annotations


def create_tables(database_url: str) -> None:
    """Create every table in the database at the given URL (SQLite or Postgres)."""
    raise NotImplementedError("models.create_tables is not implemented yet (Phase 2).")
