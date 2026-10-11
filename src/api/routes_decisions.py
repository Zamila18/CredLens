"""Decision, model card and audit endpoints. Stub (Phase 9).

Purpose: POST /merchants/{id}/decision, GET /decisions, GET /model/card, GET /audit.
Owner role: D (full-stack).
Implements: PROJECT_BRIEF section 8. Request and response shapes are in src/api/schemas.py.

Rules for Phase 9: a decision is always an officer's action; an override needs a
written reason; decisions are append-only (no update, no delete); /audit is admin only.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["decisions"])
