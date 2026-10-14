"""The same database code on PostgreSQL, the engine behind Supabase.

Owner role: B (data engineer).
Implements: docs/ACCEPTANCE_CHECKLIST.md ("the same loader works against Supabase
    Postgres via DATABASE_URL") and PROJECT_BRIEF section 18, item 36.

These tests need a PostgreSQL database that may be emptied: they drop and create every
table in it. They are skipped unless one is named in the environment variable
CREDLENS_TEST_POSTGRES_URL, so CI (no network) and normal runs use SQLite only. Never
point it at Supabase or any database holding real decisions.

A throwaway database on this laptop, with Docker:
    docker run -d --name credlens-pgcheck -e POSTGRES_PASSWORD=<choose> -e POSTGRES_DB=credlens
        -p 127.0.0.1:5433:5432 postgres:18.3
    set CREDLENS_TEST_POSTGRES_URL=postgresql+psycopg2://postgres:<choose>@127.0.0.1:5433/credlens
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import insert, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from src.adapters.base import CONTRACT
from src.db.backup import backup_database
from src.db.load import load_tables
from src.db.models import Base, make_engine

URL = os.environ.get("CREDLENS_TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(
    not URL.startswith("postgresql"), reason="no throwaway PostgreSQL database named"
)
FIXTURES = Path(__file__).parent / "fixtures" / "contract"


@pytest.fixture(scope="module")
def engine():
    tables = {name: pd.read_csv(FIXTURES / f"{name}.csv") for name in CONTRACT}
    load_tables(tables, URL, reset=True)
    engine = make_engine(URL)
    yield engine
    engine.dispose()


def add_decision(connection, decision_id: str, merchant_id: str = "FIX-M001") -> None:
    connection.execute(
        insert(Base.metadata.tables["decisions"]).values(
            decision_id=decision_id,
            merchant_id=merchant_id,
            officer_id="officer-1",
            model_version="test",
            score_shown=90,
            officer_action="accept",
            reason_text=None,
            decided_at=datetime(2026, 10, 14, 12, 0),
        )
    )


def test_the_loader_writes_every_contract_table(engine):
    with engine.connect() as connection:
        for name in CONTRACT:
            rows = connection.execute(text(f"SELECT count(*) FROM {name}")).scalar()
            expected = len(pd.read_csv(FIXTURES / f"{name}.csv"))
            assert rows == expected, name


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE decisions SET officer_action = 'override_up'",
        "DELETE FROM decisions",
        "TRUNCATE decisions",
        "UPDATE audit_log SET action = 'changed'",
        "DELETE FROM audit_log",
        "TRUNCATE audit_log",
    ],
)
def test_decisions_and_the_audit_log_cannot_be_changed_or_emptied(engine, statement):
    """TRUNCATE included: a row trigger alone does not stop it on PostgreSQL."""
    with engine.begin() as connection:
        add_decision(connection, f"D-{abs(hash(statement))}")
        connection.execute(
            text(
                "INSERT INTO audit_log (actor, role, action, merchant_id, timestamp) "
                "VALUES ('officer-1', 'officer', 'read_profile', 'FIX-M001', now())"
            )
        )
    with pytest.raises(DBAPIError, match="append-only"):
        with engine.begin() as connection:
            connection.execute(text(statement))
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM decisions")).scalar() > 0
        assert connection.execute(text("SELECT count(*) FROM audit_log")).scalar() > 0


def test_a_decision_about_an_unknown_merchant_is_refused(engine):
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            add_decision(connection, "D-NOBODY", merchant_id="NOBODY")


def test_backup_writes_one_csv_per_table(engine, tmp_path):
    folder = backup_database(URL, tmp_path)
    written = {path.stem for path in folder.glob("*.csv")}
    assert set(CONTRACT) <= written
    assert {"decisions", "audit_log"} <= written
