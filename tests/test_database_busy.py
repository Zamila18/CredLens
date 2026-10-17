"""Tests for the wait-for-the-lock setting of the SQLite engine (Phase 13 review, finding F2).

Owner role: D (full-stack) with the lead's approval to change `make_engine`.
Implements: config `api.sqlite_busy_timeout_seconds`.

The problem it fixes: every audit entry and decision is a write, SQLite lets one writer in at a
time, and SQLite's own default is to give up after 5 seconds. With 24 callers at once about 2%
of calls got an HTTP 500, "database is locked". The tests hold the database's write lock on
purpose, from another connection, and check what a caller does.
"""

from __future__ import annotations

import sqlite3
import threading
import time

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from src.config import load_config
from src.db import models as db
from src.db.models import configured_busy_timeout_seconds, create_tables, make_engine

SETTING = "sqlite_busy_timeout_seconds"


@pytest.fixture()
def url(tmp_path):
    url = "sqlite:///" + (tmp_path / "busy.db").as_posix()
    create_tables(url)
    return url


def hold_the_write_lock(path: str, seconds: float) -> threading.Thread:
    """Another program has the database's write lock for `seconds`."""
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


def write_one_audit_row(engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO audit_log (actor, role, action, merchant_id, timestamp) "
                "VALUES ('officer-1', 'officer', 'test', NULL, '2026-01-01 00:00:00')"
            )
        )


def test_the_wait_comes_from_the_config_and_foreign_keys_stay_on(url):
    config_value = load_config()["api"][SETTING]
    assert config_value == 30 == configured_busy_timeout_seconds()
    engine = make_engine(url)
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA busy_timeout")).scalar() == config_value * 1000
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert connection.execute(text("PRAGMA journal_mode")).scalar() == "delete"  # not WAL
    engine.dispose()


def test_the_wait_can_be_chosen_by_a_test_and_does_not_apply_to_postgres(url):
    engine = make_engine(url, busy_timeout_seconds=2)
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA busy_timeout")).scalar() == 2000
    engine.dispose()
    # no connection is made here; the setting is simply not used for another kind of database
    postgres = make_engine("postgresql+psycopg2://user:password@localhost:5432/none")
    assert postgres.dialect.name == "postgresql"
    postgres.dispose()


def test_a_caller_waits_for_the_lock_and_then_writes(url, tmp_path):
    engine = make_engine(url, busy_timeout_seconds=10)
    holder = hold_the_write_lock(str(tmp_path / "busy.db"), 1.5)
    started = time.monotonic()
    write_one_audit_row(engine)  # waits for the other program's turn, then succeeds
    waited = time.monotonic() - started
    holder.join()
    assert waited >= 1.0
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM audit_log")).scalar() == 1
    engine.dispose()


def test_without_the_wait_the_same_call_fails_at_once(url, tmp_path):
    """The control: this is what a caller used to get when the lock was held a moment."""
    engine = make_engine(url, busy_timeout_seconds=0)
    holder = hold_the_write_lock(str(tmp_path / "busy.db"), 1.5)
    started = time.monotonic()
    with pytest.raises(OperationalError, match="database is locked"):
        write_one_audit_row(engine)
    assert time.monotonic() - started < 1.0
    holder.join()
    engine.dispose()


def test_a_wait_shorter_than_the_lock_still_ends_in_an_error_not_a_hang(url, tmp_path):
    engine = make_engine(url, busy_timeout_seconds=1)
    holder = hold_the_write_lock(str(tmp_path / "busy.db"), 3)
    started = time.monotonic()
    with pytest.raises(OperationalError, match="database is locked"):
        write_one_audit_row(engine)
    assert 0.8 <= time.monotonic() - started < 2.5
    holder.join()
    engine.dispose()


def test_the_decisions_and_the_audit_log_are_still_append_only(url):
    """The new setting touches nothing else of the engine: the triggers and the guards stay."""
    engine = make_engine(url)
    write_one_audit_row(engine)
    with engine.begin() as connection:
        with pytest.raises(Exception, match="append-only"):
            connection.execute(text("UPDATE audit_log SET action = 'changed'"))
    with engine.begin() as connection:
        with pytest.raises(Exception, match="append-only"):
            connection.execute(text("DELETE FROM audit_log"))
    assert db.APPEND_ONLY_TABLES == ("decisions", "audit_log")
    engine.dispose()
