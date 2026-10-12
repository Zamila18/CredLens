"""Database tables.

Purpose: the tables behind the API: the seven data-contract tables plus the tables the
    application itself writes (users, decisions, audit log, model versions).
Owner role: B (data engineer).
Implements: PROJECT_BRIEF sections 5, 13 and 18. Works on SQLite (local work, tests, CI)
    and PostgreSQL (the shared Supabase database), chosen by the connection URL.

How the tables line up with Mifos X (Apache Fineract) ideas, so the data can be exported
in that shape (src/db/mifos_adapter.py):

    merchants   -> client
    loans       -> loan
    payments    -> repayment schedule (what was due) and transaction (what was paid)
    purchases, deliveries, questionnaire, consents: no Mifos X equivalent; they are the
        platform data this project adds around the loan.

Rules built into the tables:
- `merchants` is the single master table. Every other row points to a merchant.
- `decisions` and `audit_log` are append-only: a row can be added, never changed or
  removed. This is enforced twice: in the application (the session refuses) and in the
  database (triggers refuse).
- A decision is always an officer's action. There is no approve or decline value, and an
  override without a written reason is rejected by the database itself.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    DDL,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

# Tables that hold the data contract, in the order they must be loaded (parents first).
CONTRACT_TABLES = (
    "merchants",
    "purchases",
    "deliveries",
    "loans",
    "payments",
    "questionnaire",
    "consents",
)
# Tables where a row, once written, can never be changed or removed.
APPEND_ONLY_TABLES = ("decisions", "audit_log")

OFFICER_ACTIONS = ("accept", "override_up", "override_down", "needs_more_info")
ROLES = ("officer", "admin", "viewer")


class AppendOnlyError(RuntimeError):
    """Raised when code tries to change or delete a decision or an audit entry."""


class Base(DeclarativeBase):
    """Base class for every table."""


# --- data contract tables ------------------------------------------------------------


class Merchant(Base):
    """One row per merchant: the master table (Mifos X: client)."""

    __tablename__ = "merchants"

    merchant_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    onboarded_at: Mapped[date] = mapped_column(Date, index=True)
    district: Mapped[str | None] = mapped_column(String(64))
    # The next three are audit columns: used for fairness checks, never as model inputs.
    town_tier: Mapped[str | None] = mapped_column(String(32))
    shop_type: Mapped[str | None] = mapped_column(String(32))
    has_trade_license: Mapped[bool | None] = mapped_column(Boolean)
    consent_data_use: Mapped[bool] = mapped_column(Boolean)
    questionnaire_done: Mapped[bool] = mapped_column(Boolean)


class Purchase(Base):
    """A wholesale purchase the merchant made. Never the merchant's sales."""

    __tablename__ = "purchases"

    purchase_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    purchase_date: Mapped[date] = mapped_column(Date)
    amount_bdt: Mapped[float] = mapped_column(Float)
    category: Mapped[str | None] = mapped_column(String(64))
    supplier_id: Mapped[str | None] = mapped_column(String(32))


class Delivery(Base):
    """A parcel the merchant sent to one of its own customers."""

    __tablename__ = "deliveries"

    delivery_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    dispatched_at: Mapped[datetime] = mapped_column(DateTime)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16))
    return_reason: Mapped[str | None] = mapped_column(String(32))
    is_cod: Mapped[bool] = mapped_column(Boolean)
    cod_remitted_on_time: Mapped[bool | None] = mapped_column(Boolean)


class Loan(Base):
    """A loan and its outcome label (Mifos X: loan).

    No code may change `outcome_label` as a result of a score: the label records what
    happened, it is not a decision.
    """

    __tablename__ = "loans"

    loan_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    issued_at: Mapped[date] = mapped_column(Date, index=True)
    limit_bdt: Mapped[float] = mapped_column(Float)
    outcome_label: Mapped[int | None] = mapped_column(Integer)
    label_observed_at: Mapped[date | None] = mapped_column(Date)

    __table_args__ = (
        CheckConstraint("outcome_label IS NULL OR outcome_label IN (0, 1)", name="label_is_0_or_1"),
    )


class Payment(Base):
    """What was due on a loan and what was paid (Mifos X: schedule and transaction)."""

    __tablename__ = "payments"

    payment_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    loan_id: Mapped[str] = mapped_column(ForeignKey("loans.loan_id"), index=True)
    due_date: Mapped[date] = mapped_column(Date)
    paid_date: Mapped[date | None] = mapped_column(Date)
    amount_due_bdt: Mapped[float] = mapped_column(Float)
    amount_paid_bdt: Mapped[float] = mapped_column(Float)


class Questionnaire(Base):
    """FinHealth-style answers, 1 to 5. Shown beside the score, never inside the model."""

    __tablename__ = "questionnaire"

    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"), primary_key=True)
    spend1: Mapped[int] = mapped_column(Integer)
    spend2: Mapped[int] = mapped_column(Integer)
    save1: Mapped[int] = mapped_column(Integer)
    save2: Mapped[int] = mapped_column(Integer)
    borrow1: Mapped[int] = mapped_column(Integer)
    borrow2: Mapped[int] = mapped_column(Integer)
    plan1: Mapped[int] = mapped_column(Integer)
    plan2: Mapped[int] = mapped_column(Integer)
    stress: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[int] = mapped_column(Integer)
    answered_at: Mapped[date] = mapped_column(Date)


class Consent(Base):
    """A consent record. Scoring is refused without a valid, unexpired, unrevoked one."""

    __tablename__ = "consents"

    consent_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    purpose: Mapped[str] = mapped_column(String(64))
    data_categories: Mapped[str] = mapped_column(String(128))
    granted_at: Mapped[date] = mapped_column(Date)
    expires_at: Mapped[date] = mapped_column(Date)
    revoked_at: Mapped[date | None] = mapped_column(Date)


# --- tables the application writes ---------------------------------------------------


class User(Base):
    """A demo user with a role. Not a real login system."""

    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(16))

    __table_args__ = (CheckConstraint(f"role IN {ROLES}", name="role_is_known"),)


class ModelVersion(Base):
    """One trained model: what it was trained on and how it scored."""

    __tablename__ = "model_versions"

    version_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    data_mode: Mapped[str] = mapped_column(String(32))
    code_commit: Mapped[str | None] = mapped_column(String(64))
    data_seed: Mapped[int | None] = mapped_column(Integer)
    model_name: Mapped[str | None] = mapped_column(String(64))
    calibrator: Mapped[str | None] = mapped_column(String(32))
    train_window: Mapped[str | None] = mapped_column(String(64))
    feature_list_json: Mapped[str | None] = mapped_column(Text)
    metrics_json: Mapped[str | None] = mapped_column(Text)
    config_json: Mapped[str | None] = mapped_column(Text)
    artifact_path: Mapped[str | None] = mapped_column(String(256))


class Decision(Base):
    """An officer's decision on a merchant. Append-only.

    The system never writes a row here by itself: `officer_id` is always a person, and
    the only actions are accept, override up or down, and needs more info.
    """

    __tablename__ = "decisions"

    decision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    officer_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    model_version: Mapped[str] = mapped_column(String(64))
    score_shown: Mapped[int] = mapped_column(Integer)
    officer_action: Mapped[str] = mapped_column(String(32))
    reason_text: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(DateTime, index=True)

    __table_args__ = (
        CheckConstraint(f"officer_action IN {OFFICER_ACTIONS}", name="action_is_known"),
        CheckConstraint("score_shown BETWEEN 0 AND 100", name="score_is_0_to_100"),
        CheckConstraint(
            "officer_action NOT IN ('override_up', 'override_down') "
            "OR (reason_text IS NOT NULL AND length(trim(reason_text)) > 0)",
            name="override_needs_reason",
        ),
    )


class AuditEntry(Base):
    """Who did what, and when. Append-only. Every profile read adds a row."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String(32))
    role: Mapped[str] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(64))
    merchant_id: Mapped[str | None] = mapped_column(String(32), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)


# --- append-only enforcement ---------------------------------------------------------

_APPEND_ONLY_MESSAGE = "{table} is append-only: rows cannot be changed or deleted"


def _refuse_change(mapper, connection, target) -> None:
    """Application-level guard: stop an update or delete made through the ORM."""
    raise AppendOnlyError(_APPEND_ONLY_MESSAGE.format(table=target.__tablename__))


for _model in (Decision, AuditEntry):
    event.listen(_model, "before_update", _refuse_change)
    event.listen(_model, "before_delete", _refuse_change)


@event.listens_for(Session, "do_orm_execute")
def _refuse_bulk_change(orm_execute_state) -> None:
    """Application-level guard: stop `update(...)` and `delete(...)` statements too."""
    if not (orm_execute_state.is_update or orm_execute_state.is_delete):
        return
    for mapper in orm_execute_state.all_mappers:
        if mapper.local_table.name in APPEND_ONLY_TABLES:
            raise AppendOnlyError(_APPEND_ONLY_MESSAGE.format(table=mapper.local_table.name))


def _append_only_triggers(table: str) -> None:
    """Database-level guard: triggers that refuse UPDATE and DELETE on one table.

    The SQLite triggers are covered by tests. The PostgreSQL ones follow the same idea
    but have not been run yet: check them when the Supabase database is first created.
    """
    message = _APPEND_ONLY_MESSAGE.format(table=table)
    target = Base.metadata.tables[table]
    for action in ("UPDATE", "DELETE"):
        name = f"{table}_no_{action.lower()}"
        sqlite = DDL(
            f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE {action} ON {table} "
            f"BEGIN SELECT RAISE(ABORT, '{message}'); END"
        )
        event.listen(target, "after_create", sqlite.execute_if(dialect="sqlite"))

    function = DDL(
        f"CREATE OR REPLACE FUNCTION {table}_append_only() RETURNS trigger AS $$ "
        f"BEGIN RAISE EXCEPTION '{message}'; END; $$ LANGUAGE plpgsql"
    )
    trigger = DDL(
        f"CREATE TRIGGER {table}_no_change BEFORE UPDATE OR DELETE ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION {table}_append_only()"
    )
    event.listen(target, "after_create", function.execute_if(dialect="postgresql"))
    event.listen(target, "after_create", trigger.execute_if(dialect="postgresql"))


for _table in APPEND_ONLY_TABLES:
    _append_only_triggers(_table)


# --- engine and table creation -------------------------------------------------------


def make_engine(database_url: str) -> Engine:
    """Create a database engine. On SQLite, switch foreign-key checks on."""
    engine = create_engine(database_url)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_tables(database_url: str) -> None:
    """Create every table in the database at the given URL (SQLite or Postgres)."""
    engine = make_engine(database_url)
    Base.metadata.create_all(engine)
    engine.dispose()


def drop_tables(database_url: str) -> None:
    """Remove every table, including decisions and the audit log. For a fresh start only."""
    engine = make_engine(database_url)
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            for table in APPEND_ONLY_TABLES:
                connection.exec_driver_sql(f"DROP FUNCTION IF EXISTS {table}_append_only() CASCADE")
    Base.metadata.drop_all(engine)
    engine.dispose()
