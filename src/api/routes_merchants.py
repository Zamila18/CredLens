"""Merchant endpoints: review queue, profile and score. Stub (Phase 9).

Purpose: GET /merchants, GET /merchants/{id}, GET /merchants/{id}/score.
Owner role: D (full-stack).
Implements: PROJECT_BRIEF section 8. Response shapes are in src/api/schemas.py and
    sample responses are in tests/fixtures/api/.

Rules for Phase 9: every profile read writes an audit entry; scoring is refused
without a valid consent; no endpoint changes a loan status.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["merchants"])
