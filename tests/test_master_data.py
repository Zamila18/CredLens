"""Tests for the database: master data, loading, append-only decisions, backup, export.

Owner role: B (data engineer).
Implements: PROJECT_BRIEF section 13.5 (merchants is the single master table; no
    duplicate merchant ids; every foreign key resolves) and CLAUDE.md (decisions are
    append-only; overrides need a written reason).

Every test uses a small SQLite file in a temporary folder. No network, no secrets.
"""

from __future__ import annotations

import copy
import json
from datetime import date, datetime

import pandas as pd
import pytest
from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.config import load_config
from src.db.backup import backup_database
from src.db.load import DEMO_USERS, DataAlreadyLoaded, DataMismatch, data_fingerprint, load_tables
from src.db.mifos_adapter import export_mifos
from src.db.models import (
    APPEND_ONLY_TABLES,
    CONTRACT_TABLES,
    AppendOnlyError,
    AuditEntry,
    Base,
    Decision,
    Loan,
    Merchant,
    make_engine,
)
from src.synth.generate import build_tables

N_MERCHANTS = 300


@pytest.fixture(scope="module")
def tables() -> dict[str, pd.DataFrame]:
    """A small synthetic data set."""
    config = copy.deepcopy(load_config())
    config["data"]["n_merchants"] = N_MERCHANTS
    built, _, _ = build_tables(config, 0.5)
    return built


@pytest.fixture()
def database_url(tmp_path, tables) -> str:
    """A fresh SQLite database loaded with the small data set."""
    url = "sqlite:///" + (tmp_path / "test.db").as_posix()
    load_tables(tables, url)
    return url


@pytest.fixture()
def engine(database_url):
    engine = make_engine(database_url)
    yield engine
    engine.dispose()


def a_decision(merchant_id: str, **changes) -> dict:
    """A valid decision row; pass keyword arguments to change fields."""
    row = {
        "decision_id": "DEC-1",
        "merchant_id": merchant_id,
        "officer_id": "officer-1",
        "model_version": "test-0",
        "score_shown": 72,
        "officer_action": "accept",
        "reason_text": None,
        "decided_at": datetime(2026, 8, 1, 10, 0, 0),
    }
    row.update(changes)
    return row


def count(engine, table: str) -> int:
    with engine.connect() as connection:
        query = select(func.count()).select_from(Base.metadata.tables[table])
        return connection.execute(query).scalar_one()


# --- loading -------------------------------------------------------------------------


def test_every_table_is_loaded_with_all_its_rows(engine, tables):
    for name in CONTRACT_TABLES:
        assert count(engine, name) == len(tables[name]), name
    assert count(engine, "users") == len(DEMO_USERS)
    for name in APPEND_ONLY_TABLES:
        assert count(engine, name) == 0, name


def test_dates_and_missing_values_survive_the_load(engine, tables):
    with Session(engine) as session:
        merchant = session.get(Merchant, tables["merchants"]["merchant_id"].iloc[0])
        assert isinstance(merchant.onboarded_at, date)
        assert merchant.onboarded_at.isoformat() == tables["merchants"]["onboarded_at"].iloc[0]
        assert isinstance(merchant.consent_data_use, bool)

        unlabelled = tables["loans"][tables["loans"]["outcome_label"].isna()]
        assert len(unlabelled) > 0
        loan = session.get(Loan, unlabelled["loan_id"].iloc[0])
        assert loan.outcome_label is None
        assert loan.label_observed_at is None


def test_loading_twice_changes_nothing_and_says_why(database_url, tables, engine):
    with pytest.raises(DataAlreadyLoaded, match="--reset"):
        load_tables(tables, database_url)
    assert count(engine, "merchants") == N_MERCHANTS


def test_loading_different_data_over_existing_data_is_an_error(database_url, tables, engine):
    """If the files changed but the database did not, pages and scores would disagree."""
    changed = {name: frame.copy() for name, frame in tables.items()}
    changed["loans"] = changed["loans"].iloc[:-5]
    changed["payments"] = changed["payments"][
        changed["payments"]["loan_id"].isin(changed["loans"]["loan_id"])
    ]
    assert data_fingerprint(changed) != data_fingerprint(tables)
    with pytest.raises(DataMismatch, match="DIFFERENT data"):
        load_tables(changed, database_url)
    assert count(engine, "loans") == len(tables["loans"]), "nothing was changed"


def test_the_fingerprint_is_stable_and_sensitive(tables):
    assert data_fingerprint(tables) == data_fingerprint({k: v.copy() for k, v in tables.items()})
    edited = {name: frame.copy() for name, frame in tables.items()}
    edited["loans"].loc[edited["loans"].index[0], "limit_bdt"] += 1
    assert data_fingerprint(edited) != data_fingerprint(tables)


def test_reset_wipes_and_reloads(database_url, tables, engine):
    with engine.begin() as connection:
        merchant_id = tables["merchants"]["merchant_id"].iloc[0]
        connection.execute(insert(Decision.__table__), [a_decision(merchant_id)])
    engine.dispose()

    counts = load_tables(tables, database_url, reset=True)
    assert counts["merchants"] == N_MERCHANTS
    fresh = make_engine(database_url)
    try:
        assert count(fresh, "decisions") == 0
        assert count(fresh, "merchants") == N_MERCHANTS
    finally:
        fresh.dispose()


# --- master data ---------------------------------------------------------------------


def test_no_duplicate_merchant_ids(engine, tables):
    """Every merchant_id appears once in the master table, and the database insists on it."""
    with engine.connect() as connection:
        distinct = connection.execute(
            select(func.count(func.distinct(Merchant.merchant_id)))
        ).scalar_one()
    assert distinct == count(engine, "merchants") == N_MERCHANTS

    duplicate = {
        "merchant_id": tables["merchants"]["merchant_id"].iloc[0],
        "onboarded_at": date(2025, 1, 1),
        "consent_data_use": True,
        "questionnaire_done": False,
    }
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(insert(Merchant.__table__), [duplicate])


def test_every_foreign_key_resolves(engine):
    """Every purchase, delivery, payment, loan and consent points to a real merchant."""
    with engine.connect() as connection:
        for name in CONTRACT_TABLES:
            if name == "merchants":
                continue
            orphans = connection.execute(
                text(
                    f"SELECT COUNT(*) FROM {name} t LEFT JOIN merchants m "
                    "ON t.merchant_id = m.merchant_id WHERE m.merchant_id IS NULL"
                )
            ).scalar_one()
            assert orphans == 0, name
        orphan_payments = connection.execute(
            text(
                "SELECT COUNT(*) FROM payments p LEFT JOIN loans l ON p.loan_id = l.loan_id "
                "WHERE l.loan_id IS NULL"
            )
        ).scalar_one()
        assert orphan_payments == 0


def test_a_row_for_an_unknown_merchant_is_refused(engine):
    orphan = {
        "purchase_id": "PU-ORPHAN",
        "merchant_id": "M-DOES-NOT-EXIST",
        "purchase_date": date(2025, 6, 1),
        "amount_bdt": 1000.0,
    }
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(insert(Base.metadata.tables["purchases"]), [orphan])


# --- decisions: append-only, and always an officer's action ------------------------


def test_decisions_are_append_only(engine, tables):
    """A decision row can be added, but never updated or deleted."""
    merchant_id = tables["merchants"]["merchant_id"].iloc[0]
    with Session(engine) as session:
        session.add(Decision(**a_decision(merchant_id)))
        session.commit()

        decision = session.get(Decision, "DEC-1")
        decision.reason_text = "changed afterwards"
        with pytest.raises(AppendOnlyError):
            session.commit()
        session.rollback()

        with pytest.raises(AppendOnlyError):
            session.delete(session.get(Decision, "DEC-1"))
            session.commit()
        session.rollback()

        with pytest.raises(AppendOnlyError):
            session.execute(update(Decision).values(score_shown=1))
        with pytest.raises(AppendOnlyError):
            session.execute(delete(Decision))
    assert count(engine, "decisions") == 1


def test_the_database_itself_refuses_to_change_a_decision(engine, tables):
    """Even plain SQL that bypasses the application cannot update or delete."""
    merchant_id = tables["merchants"]["merchant_id"].iloc[0]
    with engine.begin() as connection:
        connection.execute(insert(Decision.__table__), [a_decision(merchant_id)])

    for statement in ("UPDATE decisions SET score_shown = 1", "DELETE FROM decisions"):
        with pytest.raises(IntegrityError, match="append-only"):
            with engine.begin() as connection:
                connection.execute(text(statement))

    with engine.connect() as connection:
        shown = connection.execute(text("SELECT score_shown FROM decisions")).scalar_one()
    assert shown == 72


def test_insert_or_replace_cannot_overwrite_a_decision(engine, tables):
    """Reusing a decision id to swap in a new row is refused, like an update would be."""
    merchant_id = tables["merchants"]["merchant_id"].iloc[0]
    with engine.begin() as connection:
        connection.execute(insert(Decision.__table__), [a_decision(merchant_id)])

    overwrite = text(
        "INSERT OR REPLACE INTO decisions (decision_id, merchant_id, officer_id, model_version, "
        "score_shown, officer_action, reason_text, decided_at) VALUES "
        "('DEC-1', :merchant, 'officer-1', 'test-0', 5, 'accept', NULL, '2026-08-02 00:00:00')"
    )
    with pytest.raises(IntegrityError, match="append-only"):
        with engine.begin() as connection:
            connection.execute(overwrite, {"merchant": merchant_id})

    with engine.connect() as connection:
        shown = connection.execute(text("SELECT score_shown FROM decisions")).scalar_one()
    assert shown == 72
    assert count(engine, "decisions") == 1


def test_a_second_decision_with_a_new_id_is_still_accepted(engine, tables):
    """Append-only means rows can be added: a later decision does not replace an earlier one."""
    merchant_id = tables["merchants"]["merchant_id"].iloc[0]
    with engine.begin() as connection:
        connection.execute(insert(Decision.__table__), [a_decision(merchant_id)])
        connection.execute(
            insert(Decision.__table__),
            [a_decision(merchant_id, decision_id="DEC-2", officer_action="needs_more_info")],
        )
    assert count(engine, "decisions") == 2


def test_the_audit_log_is_append_only_too(engine):
    entry = {
        "actor": "officer-1",
        "role": "officer",
        "action": "view_profile",
        "merchant_id": "M000001",
        "timestamp": datetime(2026, 8, 1, 9, 0, 0),
    }
    with engine.begin() as connection:
        connection.execute(insert(AuditEntry.__table__), [entry])
    for statement in ("UPDATE audit_log SET actor = 'someone-else'", "DELETE FROM audit_log"):
        with pytest.raises(IntegrityError, match="append-only"):
            with engine.begin() as connection:
                connection.execute(text(statement))
    assert count(engine, "audit_log") == 1


@pytest.mark.parametrize("reason", [None, "", "   "])
@pytest.mark.parametrize("action", ["override_up", "override_down"])
def test_an_override_without_a_written_reason_is_refused(engine, tables, action, reason):
    merchant_id = tables["merchants"]["merchant_id"].iloc[0]
    row = a_decision(merchant_id, officer_action=action, reason_text=reason)
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(insert(Decision.__table__), [row])


def test_an_override_with_a_reason_is_accepted(engine, tables):
    merchant_id = tables["merchants"]["merchant_id"].iloc[0]
    row = a_decision(merchant_id, officer_action="override_up", reason_text="Visited the shop.")
    with engine.begin() as connection:
        connection.execute(insert(Decision.__table__), [row])
    assert count(engine, "decisions") == 1


@pytest.mark.parametrize("action", ["approve", "decline", "auto_approve", ""])
def test_there_is_no_approve_or_decline_action(engine, tables, action):
    """The database accepts only an officer's four actions."""
    merchant_id = tables["merchants"]["merchant_id"].iloc[0]
    row = a_decision(merchant_id, officer_action=action, reason_text="any")
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(insert(Decision.__table__), [row])


def test_a_decision_needs_a_known_officer_and_merchant(engine, tables):
    merchant_id = tables["merchants"]["merchant_id"].iloc[0]
    for row in (
        a_decision(merchant_id, officer_id="the-model"),
        a_decision("M-DOES-NOT-EXIST"),
    ):
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(insert(Decision.__table__), [row])


def test_a_loan_label_can_only_be_zero_one_or_empty(engine, tables):
    loan = {
        "loan_id": "L-BAD",
        "merchant_id": tables["merchants"]["merchant_id"].iloc[0],
        "issued_at": date(2025, 6, 1),
        "limit_bdt": 10000.0,
        "outcome_label": 2,
    }
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(insert(Loan.__table__), [loan])


# --- backup and export -------------------------------------------------------------


def test_backup_copies_the_database_file(database_url, tmp_path, engine):
    target = backup_database(database_url, tmp_path / "backups")
    assert target.exists()
    assert target.suffix == ".db"
    copy_engine = make_engine("sqlite:///" + target.as_posix())
    try:
        assert count(copy_engine, "merchants") == count(engine, "merchants")
    finally:
        copy_engine.dispose()


def test_backup_says_when_there_is_no_database(tmp_path):
    with pytest.raises(FileNotFoundError, match="python tasks.py data"):
        backup_database("sqlite:///" + (tmp_path / "missing.db").as_posix(), tmp_path)


def test_mifos_style_export_has_clients_loans_schedule_and_transactions(
    database_url, tmp_path, tables
):
    paths = export_mifos(database_url, tmp_path / "mifos")
    clients = json.loads(paths["clients_json"].read_text(encoding="utf-8"))
    loans = pd.read_csv(paths["loans_csv"])
    schedule = pd.read_csv(paths["repayment_schedule_csv"])
    transactions = pd.read_csv(paths["transactions_csv"])

    assert len(clients) == N_MERCHANTS
    assert {"officeId", "firstname", "lastname", "active", "activationDate"} <= set(clients[0])
    assert clients[0]["firstname"] == "Merchant"
    assert len(loans) == len(schedule) == len(tables["loans"])
    assert set(loans["clientExternalId"]) <= {client["externalId"] for client in clients}
    assert {"principal", "numberOfRepayments", "expectedDisbursementDate"} <= set(loans.columns)
    assert len(transactions) == int(tables["payments"]["paid_date"].notna().sum())
    assert "SYNTHETIC" in paths["readme"].read_text(encoding="utf-8")
