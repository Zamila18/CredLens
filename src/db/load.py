"""Load the data-contract tables into the database.

Purpose: take the seven tables from the active data adapter and write them to the
    database behind the API (SQLite locally, Supabase Postgres when DATABASE_URL is set).
Owner role: B (data engineer).
Implements: PROJECT_BRIEF sections 4, 5 and 18.

Safety rules:
- The loader never overwrites data silently. If the database already holds merchants,
  it stops and says so. To start again, pass `reset=True` (command line: --reset), which
  removes every table, including recorded decisions and the audit log.
- Only synthetic data is loaded here. Raw public files are never uploaded to the shared
  database (CLAUDE.md, non-negotiable rules).
- The database URL is a secret. This module never prints it.

Run it:
    python tasks.py data            (generates, then loads if the database is empty)
    python -m src.db.load --reset   (wipe and reload)
"""

from __future__ import annotations

import argparse
from typing import Any

import pandas as pd
from sqlalchemy import func, insert, select

from src.adapters import check_frame, get_adapter
from src.config import get_database_url, load_config
from src.db.models import CONTRACT_TABLES, Base, User, drop_tables, make_engine

CHUNK_ROWS = 50_000
LOADABLE_MODES = ("synthetic_bd",)

DATE_COLUMNS = {
    "merchants": ["onboarded_at"],
    "purchases": ["purchase_date"],
    "loans": ["issued_at", "label_observed_at"],
    "payments": ["due_date", "paid_date"],
    "questionnaire": ["answered_at"],
    "consents": ["granted_at", "expires_at", "revoked_at"],
}
TIMESTAMP_COLUMNS = {"deliveries": ["dispatched_at", "delivered_at"]}

DEMO_USERS = [
    {"user_id": "officer-1", "display_name": "Demo officer 1", "role": "officer"},
    {"user_id": "officer-2", "display_name": "Demo officer 2", "role": "officer"},
    {"user_id": "admin-1", "display_name": "Demo admin", "role": "admin"},
    {"user_id": "viewer-1", "display_name": "Demo viewer", "role": "viewer"},
]


class DataAlreadyLoaded(RuntimeError):
    """Raised when the database already holds data and no reset was asked for."""


def _to_records(table: str, frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Turn a contract table into rows the database accepts.

    Date text becomes real dates, and every kind of "missing" becomes None.
    """
    frame = check_frame(table, frame).copy()
    for column in DATE_COLUMNS.get(table, []):
        frame[column] = pd.to_datetime(frame[column]).dt.date
    for column in TIMESTAMP_COLUMNS.get(table, []):
        frame[column] = pd.to_datetime(frame[column])
    as_objects = frame.astype(object)
    return as_objects.where(frame.notna(), None).to_dict("records")


def load_tables(
    tables: dict[str, pd.DataFrame], database_url: str, reset: bool = False
) -> dict[str, int]:
    """Write each table to the database and return the row count per table.

    Args:
        tables: the seven contract tables, as returned by an adapter's `load_all()`.
        database_url: SQLite or Postgres connection string.
        reset: remove every existing table first, including decisions and the audit log.
    """
    if reset:
        drop_tables(database_url)
    engine = make_engine(database_url)
    Base.metadata.create_all(engine)

    counts: dict[str, int] = {}
    try:
        with engine.begin() as connection:
            existing = connection.execute(
                select(func.count()).select_from(Base.metadata.tables["merchants"])
            ).scalar_one()
            if existing:
                raise DataAlreadyLoaded(
                    f"The database already holds {existing} merchants. Nothing was changed. "
                    "To wipe everything (including decisions and the audit log) and reload, "
                    "run: python -m src.db.load --reset"
                )
            for name in CONTRACT_TABLES:
                target = Base.metadata.tables[name]
                frame = tables[name]
                for start in range(0, len(frame), CHUNK_ROWS):
                    records = _to_records(name, frame.iloc[start : start + CHUNK_ROWS])
                    connection.execute(insert(target), records)
                counts[name] = len(frame)
            connection.execute(insert(User.__table__), DEMO_USERS)
            counts["users"] = len(DEMO_USERS)
    finally:
        engine.dispose()
    return counts


def main(argv: list[str] | None = None) -> int:
    """Command line: load the active data mode into the configured database."""
    parser = argparse.ArgumentParser(description="Load the data-contract tables into the database.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="remove every table first, including decisions and the audit log",
    )
    args = parser.parse_args(argv)

    config = load_config()
    mode = config["data"]["mode"]
    if mode not in LOADABLE_MODES:
        print(f"Data mode '{mode}' is not loaded into the database. Only synthetic data is.")
        return 0

    database_url = get_database_url(config)
    kind = "SQLite (local file)" if database_url.startswith("sqlite") else "PostgreSQL (shared)"
    print(f"Loading '{mode}' into the database: {kind}")
    try:
        counts = load_tables(get_adapter(config).load_all(), database_url, reset=args.reset)
    except DataAlreadyLoaded as error:
        print(error)
        return 0
    for name, rows in counts.items():
        print(f"  {name:<14}{rows:>10,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
