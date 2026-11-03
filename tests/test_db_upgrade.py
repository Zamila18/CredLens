"""Tests for the non-destructive database upgrade (src/db/upgrade.py).

Owner role: B (data engineer).
Implements: the implementation pack, Phase 2.6: an older database gains the newer tables,
    columns and triggers; nothing is dropped or changed; a second run finds nothing to do;
    a column that would need invented values stops the upgrade before any change.

Each test builds its own small SQLite file in a temporary folder.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

import pytest

from src.db import models as db
from src.db.upgrade import UnsafeUpgrade, upgrade_database

NEW_TABLES = ("load_info", *db.RECORD_HISTORY_TABLES)


def _url(path) -> str:
    return "sqlite:///" + path.as_posix()


def make_old_database(path) -> None:
    """A database shaped like one made before Oct 17: no new tables, no `band_shown` or
    `coverage_shown`, and no "no replace" triggers. It holds one merchant and one decision."""
    db.create_tables(_url(path))
    connection = sqlite3.connect(path)
    for name in db.expected_sqlite_triggers():
        connection.execute(f"DROP TRIGGER IF EXISTS {name}")
    for name in reversed(NEW_TABLES):
        connection.execute(f"DROP TABLE {name}")
    connection.execute("ALTER TABLE decisions DROP COLUMN band_shown")
    connection.execute("ALTER TABLE decisions DROP COLUMN coverage_shown")
    for table in ("decisions", "audit_log"):  # the two triggers the old code did make
        for action in ("UPDATE", "DELETE"):
            connection.execute(
                db.sqlite_append_only_triggers(table)[f"{table}_no_{action.lower()}"]
            )
    connection.execute(
        "INSERT INTO users (user_id, display_name, role) VALUES ('officer-1', 'Officer', 'officer')"
    )
    connection.execute(
        "INSERT INTO merchants (merchant_id, onboarded_at, consent_data_use, questionnaire_done) "
        "VALUES ('M1', '2026-01-01', 1, 0)"
    )
    connection.execute(
        "INSERT INTO decisions (decision_id, merchant_id, officer_id, model_version, score_shown, "
        "officer_action, reason_text, decided_at) "
        "VALUES ('D1', 'M1', 'officer-1', 'v1', 80, 'accept', NULL, :at)",
        {"at": datetime(2026, 10, 1, 9, 0).isoformat(sep=" ")},
    )
    connection.commit()
    connection.close()


def schema(path) -> dict[str, set[str]]:
    connection = sqlite3.connect(path)
    tables = {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        if not row[0].startswith("sqlite_")
    }
    result = {
        name: {row[1] for row in connection.execute(f"PRAGMA table_info({name})")}
        for name in tables
    }
    result["__triggers__"] = {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'trigger'")
    }
    connection.close()
    return result


def test_an_old_database_gains_what_it_lacks_and_keeps_its_rows(tmp_path):
    path = tmp_path / "old.db"
    make_old_database(path)
    plan = upgrade_database(_url(path))

    assert set(plan.tables) == set(NEW_TABLES)
    assert set(plan.columns) == {
        ("decisions", "band_shown", "VARCHAR(32)"),
        ("decisions", "coverage_shown", "FLOAT"),
    }
    assert "decisions_no_replace" in plan.triggers and "audit_log_no_replace" in plan.triggers

    after = schema(path)
    for name, table in db.Base.metadata.tables.items():
        assert {column.name for column in table.columns} <= after[name], name
    assert set(db.expected_sqlite_triggers()) <= after["__triggers__"]

    connection = sqlite3.connect(path)
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    row = connection.execute(
        "SELECT decision_id, score_shown, band_shown, coverage_shown FROM decisions"
    ).fetchall()
    assert row == [("D1", 80, None, None)]  # kept, and the new columns are simply empty
    connection.close()


def test_a_second_run_finds_nothing_to_do(tmp_path):
    path = tmp_path / "old.db"
    make_old_database(path)
    upgrade_database(_url(path))
    before = schema(path)
    plan = upgrade_database(_url(path))
    assert plan.is_empty
    assert plan.lines() == [
        "Nothing to do: the database already has every table, column and trigger."
    ]
    assert schema(path) == before


def test_a_dry_run_changes_nothing(tmp_path):
    path = tmp_path / "old.db"
    make_old_database(path)
    before = schema(path)
    plan = upgrade_database(_url(path), dry_run=True)
    assert not plan.is_empty
    assert schema(path) == before


def test_after_the_upgrade_a_decision_can_no_longer_be_swapped(tmp_path):
    """The old database let INSERT OR REPLACE overwrite a decision; the upgrade closes that."""
    path = tmp_path / "old.db"
    make_old_database(path)
    replace = (
        "INSERT OR REPLACE INTO decisions (decision_id, merchant_id, officer_id, model_version, "
        "score_shown, officer_action, reason_text, decided_at) "
        "VALUES ('D1', 'M1', 'officer-1', 'v1', 80, 'accept', 'REPLACED', '2026-10-01 09:00:00')"
    )
    connection = sqlite3.connect(path)
    connection.execute(replace)  # the gap, as it was
    connection.commit()
    connection.close()

    upgrade_database(_url(path))
    connection = sqlite3.connect(path)
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        connection.execute(replace)
    for statement in ("UPDATE decisions SET reason_text = 'x'", "DELETE FROM decisions"):
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            connection.execute(statement)
    connection.close()


def test_a_current_database_needs_nothing(tmp_path):
    path = tmp_path / "new.db"
    db.create_tables(_url(path))
    assert upgrade_database(_url(path), dry_run=True).is_empty


def test_a_missing_column_that_needs_a_value_stops_everything(tmp_path):
    """users.display_name may never be empty: adding it would mean inventing names."""
    path = tmp_path / "old.db"
    make_old_database(path)
    connection = sqlite3.connect(path)
    connection.execute("ALTER TABLE users DROP COLUMN display_name")
    connection.commit()
    connection.close()
    before = schema(path)
    with pytest.raises(UnsafeUpgrade, match="users.display_name"):
        upgrade_database(_url(path))
    assert schema(path) == before  # not even the safe parts were applied
