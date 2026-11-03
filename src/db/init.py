"""Create the operational database: `python -m src.db.init` (or `python tasks.py init-db`).

Purpose: the application's own database starts empty. A company registers, and everything that
    follows (people, merchants, records, assessments) is written for that company only. The
    synthetic benchmark used to train and check the model is never loaded here (it lives in
    data/benchmark.db or in the CSV files, see src/db/load.py).
Owner role: D (full-stack).

Safe to run again: existing tables and rows are left alone (`create_all` only adds what is
missing). To change an existing database later, use `python -m src.db.upgrade` (additive).
"""

from __future__ import annotations

from src.config import get_database_url, load_config
from src.db.models import create_tables


def main() -> int:
    url = get_database_url(load_config())
    create_tables(url)
    kind = "SQLite file" if url.startswith("sqlite") else "PostgreSQL database"
    print(f"The operational database is ready ({kind}).")
    print("No merchants are loaded: each company adds its own after registering.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
