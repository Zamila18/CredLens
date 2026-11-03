"""Bring an existing database up to the current tables, without losing anything.

Purpose: a database made by an older version of the code can lack a newer table, a newer
    column or a newer trigger. `create_all` only adds missing tables, and a trigger is only
    made when its table is first created, so an older database stays behind. The fix used
    to be `python tasks.py data --reset-db`, which erases every decision and audit entry.
    This step adds what is missing and changes nothing else.
Owner role: B (data engineer).
Implements: the implementation pack, Phase 2.6 (non-destructive database setup).

What it does, in one transaction:
1. creates every table the code knows and the database lacks (with its triggers);
2. adds every missing column that may be empty (an older row simply has no value);
3. on SQLite, adds every missing trigger (`expected_sqlite_triggers`).

What it never does: drop or rename anything, change a column's type, fill in values, or
touch a row. A missing column that must always hold a value cannot be added safely; the
step stops and names it instead of guessing. Running it again finds nothing to do.

On PostgreSQL it does steps 1 and 2 only; the triggers there are made with their tables,
and an older PostgreSQL database must be checked with tests/test_postgres.py.

Command line (a backup of a SQLite file is made first):

    python -m src.db.upgrade --dry-run     say what would change, change nothing
    python -m src.db.upgrade               back up, then upgrade the configured database
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from src.config import get_database_url, load_config
from src.db.models import Base, expected_sqlite_triggers, make_engine


class UnsafeUpgrade(RuntimeError):
    """A missing column cannot be added without inventing values for existing rows."""


@dataclass
class UpgradePlan:
    """What an upgrade adds. Empty lists: the database is already current."""

    tables: list[str] = field(default_factory=list)
    columns: list[tuple[str, str, str]] = field(default_factory=list)  # table, column, type
    triggers: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.tables or self.columns or self.triggers)

    def lines(self) -> list[str]:
        """The plan in plain words, one change per line."""
        if self.is_empty:
            return ["Nothing to do: the database already has every table, column and trigger."]
        return (
            [f"add table {name}" for name in self.tables]
            + [
                f"add column {table}.{column} ({kind}, may be empty)"
                for table, column, kind in self.columns
            ]
            + [f"add trigger {name}" for name in self.triggers]
        )


def plan_upgrade(connection: Connection) -> UpgradePlan:
    """Compare the database with the code and list what is missing. Changes nothing."""
    inspector = inspect(connection)
    existing = set(inspector.get_table_names())
    plan = UpgradePlan()
    for name, table in Base.metadata.tables.items():
        if name not in existing:
            plan.tables.append(name)
            continue
        present = {column["name"] for column in inspector.get_columns(name)}
        for column in table.columns:
            if column.name in present:
                continue
            if not column.nullable:
                raise UnsafeUpgrade(
                    f"{name}.{column.name} is missing and must always hold a value, so it "
                    "cannot be added to existing rows without inventing one. Nothing was "
                    "changed. This needs a migration written for it."
                )
            kind = column.type.compile(dialect=connection.dialect)
            plan.columns.append((name, column.name, kind))
    if connection.dialect.name == "sqlite":
        have = {
            row[0]
            for row in connection.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'trigger'")
            )
        }
        plan.triggers = [name for name in expected_sqlite_triggers() if name not in have]
    return plan


def apply_upgrade(connection: Connection, plan: UpgradePlan) -> None:
    """Make the changes in `plan` on an open connection (the caller owns the transaction).

    Tables first, so every trigger finds its table. A trigger that came with a new table
    already exists by then; every statement says IF NOT EXISTS, so making it again is
    harmless.
    """
    if plan.tables:
        Base.metadata.create_all(
            connection, tables=[Base.metadata.tables[name] for name in plan.tables]
        )
    for table, column, kind in plan.columns:
        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {kind}"))
    triggers = expected_sqlite_triggers()
    for name in plan.triggers:
        connection.execute(text(triggers[name]))


def upgrade_database(database_url: str, dry_run: bool = False) -> UpgradePlan:
    """Plan the upgrade and, unless `dry_run`, apply it in one transaction.

    Returns the plan. After a real run the database is checked again; anything still
    missing raises, so a half-done upgrade is never reported as done.
    """
    engine = make_engine(database_url)
    try:
        with engine.begin() as connection:
            plan = plan_upgrade(connection)
            if not dry_run and not plan.is_empty:
                apply_upgrade(connection, plan)
        if not dry_run:
            with engine.connect() as connection:
                left = plan_upgrade(connection)
            if not left.is_empty:
                raise RuntimeError("The upgrade did not finish: " + "; ".join(left.lines()))
    finally:
        engine.dispose()
    return plan


def main(argv: list[str] | None = None) -> int:
    """Command line: back up (SQLite) and upgrade the configured database."""
    parser = argparse.ArgumentParser(description="Add missing tables, columns and triggers.")
    parser.add_argument(
        "--dry-run", action="store_true", help="say what would change; change nothing"
    )
    parser.add_argument("--no-backup", action="store_true", help="skip the backup of a SQLite file")
    args = parser.parse_args(argv)

    url = get_database_url(load_config())
    if args.dry_run:
        plan = upgrade_database(url, dry_run=True)
        print("Dry run, nothing changed. The upgrade would:")
        print("\n".join(f"- {line}" for line in plan.lines()))
        return 0
    if url.startswith("sqlite") and not args.no_backup:
        from src.db.backup import backup_database

        print(f"Backup written to {backup_database(url)}")
    try:
        plan = upgrade_database(url)
    except UnsafeUpgrade as error:
        print(error)
        return 1
    print("Upgrade done:" if not plan.is_empty else "Checked:")
    print("\n".join(f"- {line}" for line in plan.lines()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
