"""Tests that the API waits for the database instead of answering HTTP 500 (finding F2).

Owner role: D (full-stack).
Implements: Phase 13 review; config `api.sqlite_busy_timeout_seconds`.

Before the fix, 24 callers at once got "database is locked" (HTTP 500) in about 2% of calls.
Here another program holds the database's write lock for 7 seconds, longer than SQLite's own
5-second default: a request that writes (an audit entry, a decision) must wait and then
succeed, not fail.
"""

from __future__ import annotations

import sqlite3
import threading
import time

import pytest
from accounts_seed import headers_for, seed_accounts, seed_person  # noqa: F401
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.main import app
from src.db import models as db

OFFICER = headers_for("officer-1")
VIEWER = headers_for("viewer-1")
LOCK_SECONDS = 7


def hold_the_write_lock(path: str, seconds: float) -> threading.Thread:
    ready = threading.Event()

    def hold():
        other = sqlite3.connect(path, isolation_level=None)
        other.execute("BEGIN IMMEDIATE")
        ready.set()
        time.sleep(seconds)
        other.execute("COMMIT")
        other.close()

    thread = threading.Thread(target=hold)
    thread.start()
    assert ready.wait(10)
    return thread


def count(world, model) -> int:
    with Session(world.engine) as session:
        return session.scalar(select(func.count()).select_from(model))


@pytest.fixture()
def consenting(api_world):
    queue = api_world.services.scorer.queue()
    return queue[queue["consent_valid"]]["merchant_id"].tolist()


def test_a_decision_made_while_the_database_is_busy_waits_and_is_recorded(
    api, api_world, consenting
):
    path = api_world.engine.url.database
    decisions, audit = count(api_world, db.Decision), count(api_world, db.AuditEntry)
    holder = hold_the_write_lock(path, LOCK_SECONDS)
    quiet = TestClient(app, raise_server_exceptions=False)
    started = time.monotonic()
    response = quiet.post(
        f"/merchants/{consenting[-40]}/decision",
        headers=OFFICER,
        json={"officer_action": "accept"},
    )
    waited = time.monotonic() - started
    holder.join()
    assert response.status_code == 201, response.text
    assert waited >= LOCK_SECONDS - 2, "the request really did wait for the other writer"
    assert count(api_world, db.Decision) == decisions + 1
    assert count(api_world, db.AuditEntry) == audit + 1


def test_a_profile_read_while_the_database_is_busy_waits_for_its_audit_entry(
    api, api_world, consenting
):
    """Audit first, then disclose: a read that cannot be recorded returns nothing. It must wait for
    its turn to be recorded, not fail the page."""
    path = api_world.engine.url.database
    audit = count(api_world, db.AuditEntry)
    holder = hold_the_write_lock(path, LOCK_SECONDS)
    quiet = TestClient(app, raise_server_exceptions=False)
    response = quiet.get(f"/merchants/{consenting[-41]}", headers=VIEWER)
    holder.join()
    assert response.status_code == 200, response.text
    assert count(api_world, db.AuditEntry) == audit + 1


def test_a_read_that_writes_nothing_is_not_held_up_by_a_busy_database(
    api, api_world, consenting
):
    """Reading the model card writes no audit entry, so another writer's lock does not matter."""
    holder = hold_the_write_lock(api_world.engine.url.database, 2)
    started = time.monotonic()
    assert api.get("/model/card", headers=VIEWER).status_code == 200
    assert time.monotonic() - started < 1.5
    holder.join()
