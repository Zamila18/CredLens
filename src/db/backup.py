"""Back up the database.

Purpose: keep a dated copy of the database, so recorded decisions and the audit log
    survive a mistake.
Owner role: B (data engineer).
Implements: PROJECT_BRIEF section 13.5 ("add a backup task for the database").

- SQLite: copies the database file to data/backups/app_<timestamp>.db.
- PostgreSQL: writes one CSV per table to data/backups/<timestamp>/. This path follows
  the same logic but has not been run against Supabase yet.

Backups stay in data/backups/, which is gitignored. Run it: python tasks.py backup
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import select

from src.config import PROJECT_ROOT, get_database_url, load_config
from src.db.models import Base, make_engine

BACKUP_DIR = PROJECT_ROOT / "data" / "backups"
SQLITE_PREFIX = "sqlite:///"
EXPORT_CHUNK_ROWS = 100_000


def backup_database(database_url: str, backup_dir: Path | None = None) -> Path:
    """Back up the database and return the path of the copy (a file or a folder)."""
    folder = Path(backup_dir) if backup_dir is not None else BACKUP_DIR
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if database_url.startswith(SQLITE_PREFIX):
        source = Path(database_url[len(SQLITE_PREFIX):])
        if not source.exists():
            raise FileNotFoundError(
                f"No database file at {source}. Create it with: python tasks.py data"
            )
        target = folder / f"{source.stem}_{stamp}{source.suffix}"
        shutil.copy2(source, target)
        return target

    target = folder / stamp
    target.mkdir()
    engine = make_engine(database_url)
    try:
        with engine.connect() as connection:
            for name, table in Base.metadata.tables.items():
                chunks = pd.read_sql(select(table), connection, chunksize=EXPORT_CHUNK_ROWS)
                for number, chunk in enumerate(chunks):
                    chunk.to_csv(
                        target / f"{name}.csv",
                        mode="w" if number == 0 else "a",
                        header=number == 0,
                        index=False,
                    )
    finally:
        engine.dispose()
    return target


def main() -> int:
    """Command line: back up the configured database."""
    try:
        target = backup_database(get_database_url(load_config()))
    except FileNotFoundError as error:
        print(error)
        return 1
    print(f"Backup written to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
