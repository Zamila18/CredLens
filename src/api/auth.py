"""Demo role check. Stub (Phase 9).

Purpose: a simple role switch (officer / admin / viewer) read from a header
    token, to show role-based access without a full login system.
Owner role: D (full-stack).
Implements: PROJECT_BRIEF sections 3 and 8 (roles).
"""

from __future__ import annotations

# officer: queue, score, decide. admin: plus audit and model card. viewer: read-only.
ROLES = ("officer", "admin", "viewer")


def role_from_token(token: str | None) -> str:
    """Return the role for a header token."""
    raise NotImplementedError("auth.role_from_token is not implemented yet (Phase 9).")
