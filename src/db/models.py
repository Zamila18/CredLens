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
- The demo workflow adds five history tables (applications, record provenance, import
  batches, visits, consent events). They are append-only in the same two ways: a change of
  mind is a new row, never an edited one.
- An application is scored through a loan-shaped row in `loans` (the scorer's input), and
  `applications.loan_id` names that row. The database refuses an application whose loan
  row belongs to another merchant, a repayment recorded against an application's row, and
  any change to that row. The requested amount is kept only in `applications`.
"""

from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache

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
    UniqueConstraint,
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
# The demo workflow's history tables (implementation pack, Phase 2): append-only as well.
RECORD_HISTORY_TABLES = (
    "applications",
    "record_provenance",
    "import_batches",
    "visits",
    "consent_events",
    "quality_reviews",
)
PROTECTED_TABLES = APPEND_ONLY_TABLES + RECORD_HISTORY_TABLES

CONSENT_RESPONSES = ("granted", "refused")
# How a record entered the system. An import or a save never makes a record verified.
ENTRY_METHODS = (
    "synthetic_demo",
    "staff_entered",
    "imported_spreadsheet",
    "admin_import",
    "receipt_desk",
)
# What is known about a record (implementation pack, appendix A6). "reviewed" and
# "independently_verified" need a named person and a recorded procedure; nothing sets them yet.
RECORD_STATUSES = (
    "synthetic_demo",
    "staff_entered",
    "imported_spreadsheet",
    "format_checked",
    "reviewed",
    "independently_verified",
)
RECORD_TYPES = (
    "merchant",
    "purchase",
    "delivery",
    "payment",
    "loan",
    "application",
    "visit",
    "consent",
)
IMPORT_STATUSES = ("committed", "refused")

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
    # The organisation the merchant belongs to; empty means the default organisation
    # (config `organization`), which is where every benchmark merchant lives.
    organization_id: Mapped[str | None] = mapped_column(String(48), index=True)


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
    organization_id: Mapped[str | None] = mapped_column(String(48), index=True)  # empty: default

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


class LoadInfo(Base):
    """Small notes about what was loaded, for example a fingerprint of the data."""

    __tablename__ = "load_info"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


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
    # The band and the coverage that were on screen with the score (Oct 17). A score is never
    # shown without them, so the decision log shows all three. Empty on older decisions.
    band_shown: Mapped[str | None] = mapped_column(String(32))
    coverage_shown: Mapped[float | None] = mapped_column(Float)
    officer_action: Mapped[str] = mapped_column(String(32))
    reason_text: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    assessment_id: Mapped[str | None] = mapped_column(String(48), index=True)

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
    organization_id: Mapped[str | None] = mapped_column(String(48), index=True)
    detail: Mapped[str | None] = mapped_column(Text)  # short JSON: what the action touched


# --- records the demo workflow adds (implementation pack, Phases 2 and 3) ----------------


class Organization(Base):
    """A financial institution or business network using CredLens. Every merchant, and so
    every application, record and decision, belongs to exactly one organisation; the default
    organisation (config `organization`) needs no row here."""

    __tablename__ = "organizations"

    organization_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    environment: Mapped[str] = mapped_column(String(16))
    country: Mapped[str] = mapped_column(String(2))
    languages: Mapped[str] = mapped_column(String(64))  # "en|bn"
    currency: Mapped[str] = mapped_column(String(3))
    timezone: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    # Company details given at registration (src/accounts/registration.py). All optional in
    # the table so that older rows stay valid; the registration form requires the main ones.
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | suspended
    legal_name: Mapped[str | None] = mapped_column(String(160))
    trading_name: Mapped[str | None] = mapped_column(String(160))
    registration_number: Mapped[str | None] = mapped_column(String(64))
    # Upper-case letters and digits only: two spellings of one number cannot both register.
    registration_number_norm: Mapped[str | None] = mapped_column(String(64), unique=True)
    org_type: Mapped[str | None] = mapped_column(String(32))
    sector: Mapped[str | None] = mapped_column(String(80))
    official_email: Mapped[str | None] = mapped_column(String(254))
    contact_number: Mapped[str | None] = mapped_column(String(20))
    division: Mapped[str | None] = mapped_column(String(80))
    city: Mapped[str | None] = mapped_column(String(80))
    address: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(String(200))
    created_by: Mapped[str | None] = mapped_column(String(32))

    __table_args__ = (
        CheckConstraint("status IN ('active', 'suspended')", name="organization_status_is_known"),
    )


class SourceConnection(Base):
    """One organisation's connection to a data source (src/connectors/).

    Holds only settings that are not secret. A credential is never stored here: `secret_ref`
    names where the deployment keeps it (for example an environment variable), and the API
    never returns or logs the secret itself. A revoked connection is kept for its history.
    """

    __tablename__ = "source_connections"

    connection_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(48), index=True)
    connector_key: Mapped[str] = mapped_column(String(48))
    display_name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(16))  # not_tested | connected | error | revoked
    settings_json: Mapped[str] = mapped_column(Text)
    secret_ref: Mapped[str | None] = mapped_column(String(120))
    created_by: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_by: Mapped[str | None] = mapped_column(String(32))


class SourceRun(Base):
    """One action on a connection: a connection test, a field discovery or a sync.

    The sync history. A failed run is kept with its error; nothing it read was saved.
    """

    __tablename__ = "source_runs"

    run_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    connection_id: Mapped[str] = mapped_column(String(48), index=True)
    organization_id: Mapped[str] = mapped_column(String(48), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # test | discover | sync
    status: Mapped[str] = mapped_column(String(16))  # ok | failed
    actor: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime] = mapped_column(DateTime)
    rows_added: Mapped[int] = mapped_column(Integer, default=0)
    rows_skipped: Mapped[int] = mapped_column(Integer, default=0)
    rows_flagged: Mapped[int] = mapped_column(Integer, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0)
    rows_unmatched: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(48))
    error_message: Mapped[str | None] = mapped_column(Text)


class SourceRecord(Base):
    """Lineage: which source row a saved record came from.

    `record_type` + `record_id` name the saved purchase or delivery; `source_reference` is
    the source's own id for the row and `raw_sha256` a fingerprint of the row as received,
    so the normalised record never loses its origin.
    """

    __tablename__ = "source_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[str] = mapped_column(String(48), index=True)
    connection_id: Mapped[str] = mapped_column(String(48), index=True)
    run_id: Mapped[str] = mapped_column(String(48))
    record_type: Mapped[str] = mapped_column(String(32))
    record_id: Mapped[str] = mapped_column(String(64), index=True)
    merchant_id: Mapped[str] = mapped_column(String(32), index=True)
    source_reference: Mapped[str] = mapped_column(String(120))
    raw_sha256: Mapped[str] = mapped_column(String(64))
    received_at: Mapped[datetime] = mapped_column(DateTime)


class SourceMerchantLink(Base):
    """A person's decision that a source's merchant reference is (or is not) a CredLens merchant.

    Records are only imported for a confirmed link. Nothing is ever linked automatically:
    a likely match is shown to a person, who confirms or rejects it. A new decision is a new
    row, so mistaken links can be corrected and the history stays readable.
    """

    __tablename__ = "source_merchant_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[str] = mapped_column(String(48), index=True)
    connection_id: Mapped[str] = mapped_column(String(48), index=True)
    external_ref: Mapped[str] = mapped_column(String(120))
    merchant_id: Mapped[str | None] = mapped_column(String(32))
    decision: Mapped[str] = mapped_column(String(16))  # confirmed | rejected
    decided_by: Mapped[str] = mapped_column(String(32))
    decided_at: Mapped[datetime] = mapped_column(DateTime)


# --- accounts: real sign-in for an organisation's staff (src/accounts/) ----------------------
# A real account has a credential row, a membership that holds its role, and sessions.
# Roles of an organisation's people: the Credit Officer (the first one registers the company
# and is its owner), the Field Sales Representative (FSR) and the Auditor. Platform
# administrators belong to no organisation (`platform_admins`).

STAFF_ROLES = ("credit_officer", "records_officer", "merchant", "auditor")
MEMBERSHIP_STATUSES = ("active", "disabled")


class UserCredential(Base):
    """How a real account signs in: email or phone, and a password hash (never the password).

    The password is hashed with scrypt and a random salt (src/accounts/passwords.py).
    Repeated failures lock the account for a while.
    """

    __tablename__ = "user_credentials"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(254), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(256))  # empty until the user sets it
    password_set_at: Mapped[datetime | None] = mapped_column(DateTime)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Membership(Base):
    """A real account's role in one organisation. The server reads the role from here; the
    browser never chooses it."""

    __tablename__ = "memberships"

    membership_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), index=True)
    organization_id: Mapped[str] = mapped_column(String(48), index=True)
    role: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(16))
    is_owner: Mapped[bool] = mapped_column(Boolean, default=False)  # the company's first officer
    merchant_id: Mapped[str | None] = mapped_column(String(32))  # the one shop a merchant sees
    created_by: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime)

    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="one_membership_per_organization"),
        CheckConstraint(f"role IN {STAFF_ROLES}", name="membership_role_is_known"),
        CheckConstraint(f"status IN {MEMBERSHIP_STATUSES}", name="membership_status_is_known"),
    )


class AuthSession(Base):
    """A signed-in browser. Only a hash of the session token is stored: a copy of the
    database does not let anyone sign in. Ends at logout, after idle time or a fixed age."""

    __tablename__ = "auth_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), index=True)
    membership_id: Mapped[str | None] = mapped_column(String(48))  # none: a platform admin
    created_at: Mapped[datetime] = mapped_column(DateTime)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)


class PasswordSetupCode(Base):
    """A one-time code to set or reset a password, made by an administrator and shown to
    them once. Only its hash is stored. Used once, then dead; expires after a set time."""

    __tablename__ = "password_setup_codes"

    code_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), index=True)
    created_by: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)


class PlatformAdmin(Base):
    """One of the few CredLens staff accounts with platform-wide access. Created only by
    `python -m src.accounts.bootstrap_platform_admins` from the private .env; no screen or
    endpoint can add one. A platform admin has no organisation and no membership."""

    __tablename__ = "platform_admins"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), primary_key=True)
    slot: Mapped[int] = mapped_column(Integer, unique=True)  # which .env entry (1 to 4)
    source: Mapped[str] = mapped_column(String(16), default="env")
    created_at: Mapped[datetime] = mapped_column(DateTime)


class StaffProfile(Base):
    """What an organisation knows about its employee: job title, department and employee ID.
    The employee ID is unique within an organisation."""

    __tablename__ = "staff_profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(48), index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    job_title: Mapped[str | None] = mapped_column(String(80))
    department: Mapped[str | None] = mapped_column(String(80))
    employee_id: Mapped[str | None] = mapped_column(String(40))
    employee_id_norm: Mapped[str | None] = mapped_column(String(40))  # lower-case, no spaces
    mobile: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime)

    __table_args__ = (
        UniqueConstraint("organization_id", "employee_id_norm", name="one_employee_id_per_org"),
    )


INVITATION_ROLES = ("records_officer", "credit_officer")
INVITATION_STATUSES = ("active", "revoked")


class Invitation(Base):
    """A company invitation code that lets an employee join the organisation in a given role.
    Only a keyed hash of the code is stored (the code is shown once, when it is made); the
    last four characters are kept as a hint. A code works until it expires, is revoked, or
    has been used `max_uses` times."""

    __tablename__ = "invitations"

    invitation_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(48), index=True)
    role: Mapped[str] = mapped_column(String(24))
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    code_hint: Mapped[str] = mapped_column(String(8))
    label: Mapped[str | None] = mapped_column(String(80))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    max_uses: Mapped[int] = mapped_column(Integer)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_by: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_by: Mapped[str | None] = mapped_column(String(32))

    __table_args__ = (
        CheckConstraint(f"role IN {INVITATION_ROLES}", name="invitation_role_is_known"),
        CheckConstraint(f"status IN {INVITATION_STATUSES}", name="invitation_status_is_known"),
        CheckConstraint("max_uses >= 1", name="invitation_has_a_use"),
    )


class InvitationUse(Base):
    """Who joined with which invitation, and when (the registration history)."""

    __tablename__ = "invitation_uses"

    use_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    invitation_id: Mapped[str] = mapped_column(ForeignKey("invitations.invitation_id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), index=True)
    organization_id: Mapped[str] = mapped_column(String(48), index=True)
    used_at: Mapped[datetime] = mapped_column(DateTime)


class AuthAttempt(Base):
    """One try at a public, guessable action (sign-in, registration, checking an invitation
    code), kept to limit how fast one address or one identifier may try. No password or code
    is stored: the identifier is a hash."""

    __tablename__ = "auth_attempts"

    attempt_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)
    ip: Mapped[str] = mapped_column(String(64), index=True)
    identifier_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    succeeded: Mapped[bool] = mapped_column(Boolean, default=False)
    at: Mapped[datetime] = mapped_column(DateTime, index=True)


class QualityReview(Base):
    """A person's review of one data-quality issue (src/api/quality.py), with a written note.

    Issues are worked out from the records each time; only the review is stored. A review
    never changes or removes a record. `fingerprint` names the evidence the person looked
    at: when the evidence changes, the issue opens again. Append-only: a new review is a new
    row, and the latest one counts.
    """

    __tablename__ = "quality_reviews"

    review_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(48), index=True)
    issue_key: Mapped[str] = mapped_column(String(200), index=True)
    kind: Mapped[str] = mapped_column(String(48))
    merchant_id: Mapped[str | None] = mapped_column(String(32), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(32))
    note: Mapped[str] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String(32))
    decided_at: Mapped[datetime] = mapped_column(DateTime)


TEMPLATE_STATUSES = ("draft", "legal_review", "approved", "retired")
REGISTRATION_STATUSES = (
    "draft",  # details entered, no form yet
    "form_issued",  # the consent PDF was generated for printing
    "signed_uploaded",  # a scan or photo of the signed form is in
    "under_review",  # the text was read (OCR); a person must check it
    "needs_correction",  # the reviewer sent it back
    "verified",  # a person verified the signed form
    "active",  # consent recorded: the merchant can be assessed
    "rejected",
    "withdrawn",  # the merchant withdrew consent
)
JOB_STATUSES = ("queued", "running", "done", "failed")


class ConsentTemplate(Base):
    """A version of the consent document and where it stands in legal review. The wording lives
    in code (src/onboarding/consent_text.py) under this version name; the row records whether
    a lawyer reviewed it and a platform administrator approved it. In production only an
    approved version can be issued; any other is stamped DRAFT on every page."""

    __tablename__ = "consent_templates"

    version: Mapped[str] = mapped_column(String(32), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    legal_review_ref: Mapped[str | None] = mapped_column(String(200))
    approved_by: Mapped[str | None] = mapped_column(String(32))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    __table_args__ = (
        CheckConstraint(f"status IN {TEMPLATE_STATUSES}", name="template_status_is_known"),
    )


class MerchantRegistration(Base):
    """One merchant's registration and consent case (src/onboarding/registrations.py).

    `details` holds what the form says (JSON); the merchant row is made when the details are
    complete. The signed form is a `documents` row; what was read from it is in
    `extraction_fields`. Only after a person verifies the signed form is the consent recorded
    and the case `active`.
    """

    __tablename__ = "merchant_registrations"

    reg_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    reg_ref: Mapped[str] = mapped_column(String(16), unique=True)  # printed on the form
    organization_id: Mapped[str] = mapped_column(String(48), index=True)
    merchant_id: Mapped[str | None] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    method: Mapped[str] = mapped_column(String(16))  # manual | blank_form
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    template_version: Mapped[str] = mapped_column(String(32))
    details: Mapped[str] = mapped_column(Text, default="{}")
    optional_consents: Mapped[str] = mapped_column(String(200), default="")  # "a|b" ticked on paper
    form_serial: Mapped[str | None] = mapped_column(String(16))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    uploaded_by: Mapped[str | None] = mapped_column(String(32))
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime)
    signer_name: Mapped[str | None] = mapped_column(String(120))
    signed_on: Mapped[date | None] = mapped_column(Date)
    verified_by: Mapped[str | None] = mapped_column(String(32))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    verification_mode: Mapped[str | None] = mapped_column(String(16))  # distinct | self_verified
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    consent_id: Mapped[str | None] = mapped_column(ForeignKey("consents.consent_id"))

    __table_args__ = (
        CheckConstraint(f"status IN {REGISTRATION_STATUSES}", name="registration_status_is_known"),
        CheckConstraint("method IN ('manual', 'blank_form')", name="registration_method_is_known"),
    )


class BlankFormSerial(Base):
    """Each blank form a company downloads gets its own serial (printed on the page), so a
    form that comes back can be tied to the company and a reused sheet is noticed."""

    __tablename__ = "blank_form_serials"

    serial: Mapped[str] = mapped_column(String(16), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(48), index=True)
    template_version: Mapped[str] = mapped_column(String(32))
    issued_by: Mapped[str] = mapped_column(String(32))
    issued_at: Mapped[datetime] = mapped_column(DateTime)
    registration_id: Mapped[str | None] = mapped_column(String(48))  # set when a form returns


class Document(Base):
    """An uploaded file (a signed consent form, a scanned note, a spreadsheet). The bytes live
    outside the database (config `documents.upload_dir`, one folder per organisation); this
    row holds who, when, what and a SHA-256 so a changed file is noticed. Served only through
    authenticated, organisation-checked, audited requests."""

    __tablename__ = "documents"

    document_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(48), index=True)
    merchant_id: Mapped[str | None] = mapped_column(String(32), index=True)
    registration_id: Mapped[str | None] = mapped_column(String(48), index=True)
    kind: Mapped[str] = mapped_column(String(32))  # consent_signed | consent_filled_form | import
    original_name: Mapped[str] = mapped_column(String(200))
    mime: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    path: Mapped[str] = mapped_column(String(300))
    uploaded_by: Mapped[str] = mapped_column(String(32))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime)


class ExtractionJob(Base):
    """A request to read the text and fields of a document (src/extraction/). Run by the
    background worker; the engine and its version are recorded."""

    __tablename__ = "extraction_jobs"

    job_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    document_id: Mapped[str | None] = mapped_column(  # none: a file read in memory (CSV, Excel)
        ForeignKey("documents.document_id"), index=True
    )
    organization_id: Mapped[str] = mapped_column(String(48), index=True)
    registration_id: Mapped[str | None] = mapped_column(String(48), index=True)
    merchant_id: Mapped[str | None] = mapped_column(String(32), index=True)  # a table import
    purpose: Mapped[str] = mapped_column(String(16), default="consent")  # consent | table
    result: Mapped[str | None] = mapped_column(Text)  # a table import's rows, as JSON
    status: Mapped[str] = mapped_column(String(12), default="queued", index=True)
    engine: Mapped[str | None] = mapped_column(String(40))
    engine_version: Mapped[str | None] = mapped_column(String(40))
    pages: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    queued_at: Mapped[datetime] = mapped_column(DateTime)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (CheckConstraint(f"status IN {JOB_STATUSES}", name="job_status_is_known"),)


class ExtractionField(Base):
    """One value read from a document, with how sure the reader was and what a person did with
    it. `expected` is what was entered before (manual method); `state` says whether the value
    matches, is missing, differs, is low confidence, or was confirmed or corrected."""

    __tablename__ = "extraction_fields"

    field_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("extraction_jobs.job_id"), index=True)
    registration_id: Mapped[str | None] = mapped_column(String(48), index=True)
    key: Mapped[str] = mapped_column(String(40))
    raw_text: Mapped[str | None] = mapped_column(Text)
    value: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String(16))  # ocr | native_pdf | ink_check
    expected: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(16))
    reviewed_value: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(String(32))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    page: Mapped[int | None] = mapped_column(Integer)
    bbox: Mapped[str | None] = mapped_column(String(80))


RECEIPT_KINDS = ("purchase", "delivery", "repayment")
RECEIPT_STATUSES = ("extracted", "checked", "published", "rejected")
LINE_STATUSES = ("extracted", "checked", "published", "disputed", "void")
FLAG_STATUSES = ("open", "accepted", "rejected")


class MerchantAccess(Base):
    """How a merchant signs in to their own portal: a random Merchant ID printed on their
    handover slip, plus the owner's name. The ID is not the CredLens shop id (CL-M-...), which
    is sequential and easy to guess. Sign-in works only once the shop's consent is verified."""

    __tablename__ = "merchant_access"

    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(48), index=True)
    portal_id: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Receipt(Base):
    """One receipt (a photo, scan or PDF) that the Records Desk uploaded for a shop. The OCR
    reading and the Records Officer's corrections live in its lines; nothing here reaches the
    credit officers or the score until the receipt is published."""

    __tablename__ = "receipts"

    receipt_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(48), index=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    kind: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(12), default="extracted", index=True)
    document_id: Mapped[str | None] = mapped_column(String(48))
    job_id: Mapped[str | None] = mapped_column(String(48))
    method: Mapped[str] = mapped_column(String(8), default="ocr")  # ocr | typed
    supplier: Mapped[str | None] = mapped_column(String(120))
    receipt_date: Mapped[date | None] = mapped_column(Date)
    memo_no: Mapped[str | None] = mapped_column(String(60))
    stated_total: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)  # JSON list of plain-words remarks
    reject_reason: Mapped[str | None] = mapped_column(String(300))
    uploaded_by: Mapped[str] = mapped_column(String(32))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    checked_by: Mapped[str | None] = mapped_column(String(32))
    published_by: Mapped[str | None] = mapped_column(String(32))
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    merchant_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        CheckConstraint(f"kind IN {RECEIPT_KINDS}", name="receipt_kind_is_known"),
        CheckConstraint(f"status IN {RECEIPT_STATUSES}", name="receipt_status_is_known"),
    )


class ReceiptLine(Base):
    """One row of a receipt: an item bought, a parcel, or a repayment. Columns that do not
    apply to the receipt's kind stay empty. `flags` lists the cells that need a person's eye
    (JSON); `projected_record_id` is the purchase, delivery or payment written on publishing."""

    __tablename__ = "receipt_lines"

    line_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    receipt_id: Mapped[str] = mapped_column(ForeignKey("receipts.receipt_id"), index=True)
    organization_id: Mapped[str] = mapped_column(String(48), index=True)
    merchant_id: Mapped[str] = mapped_column(String(32), index=True)
    row_no: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12), default="extracted", index=True)
    item: Mapped[str | None] = mapped_column(String(120))
    quantity: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(24))
    unit_price: Mapped[float | None] = mapped_column(Float)
    amount_bdt: Mapped[float | None] = mapped_column(Float)
    line_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    outcome: Mapped[str | None] = mapped_column(String(16))  # delivery: delivered|returned|failed
    reference: Mapped[str | None] = mapped_column(String(60))
    confidence: Mapped[str | None] = mapped_column(Text)  # JSON: cell -> 0..1
    flags: Mapped[str | None] = mapped_column(Text)  # JSON: [{cell, code, text}]
    edited: Mapped[bool] = mapped_column(Boolean, default=False)
    projected_record_id: Mapped[str | None] = mapped_column(String(48))
    created_at: Mapped[datetime] = mapped_column(DateTime)

    __table_args__ = (CheckConstraint(f"status IN {LINE_STATUSES}", name="line_status_is_known"),)


class ReceiptFlag(Base):
    """A merchant's report that a published line is wrong, with the correct amount they claim
    and a photo of their own copy as proof. While open, the line is left out of the score."""

    __tablename__ = "receipt_flags"

    flag_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    line_id: Mapped[str] = mapped_column(ForeignKey("receipt_lines.line_id"), index=True)
    receipt_id: Mapped[str] = mapped_column(String(48), index=True)
    organization_id: Mapped[str] = mapped_column(String(48), index=True)
    merchant_id: Mapped[str] = mapped_column(String(32), index=True)
    note: Mapped[str] = mapped_column(Text)
    claimed_amount_bdt: Mapped[float | None] = mapped_column(Float)
    proof_document_id: Mapped[str | None] = mapped_column(String(48))
    status: Mapped[str] = mapped_column(String(10), default="open", index=True)
    raised_by: Mapped[str] = mapped_column(String(32))
    raised_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    resolved_by: Mapped[str | None] = mapped_column(String(32))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolution_note: Mapped[str | None] = mapped_column(String(300))

    __table_args__ = (CheckConstraint(f"status IN {FLAG_STATUSES}", name="flag_status_is_known"),)


class Notification(Base):
    """A short message for one person (a sheet returned, a sheet submitted, a registration to
    check). Read through the bell in the header; marking one read does not remove it."""

    __tablename__ = "notifications"

    notification_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), index=True)
    organization_id: Mapped[str] = mapped_column(String(48), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    text: Mapped[str] = mapped_column(String(300))
    link: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime)


POLICY_STATUSES = ("draft", "approved", "retired")


class RangePolicy(Base):
    """A company's rule for turning verified evidence into an indicative credit range. The
    parameters (JSON) are the company's own: window, minimum evidence, multiples by band,
    rounding and cap. One approved policy is in force at a time; a new approval retires the
    old one, which stays so that every stored assessment can be recomputed from its own
    policy. Nothing here is a default: the product ships no approved policy."""

    __tablename__ = "range_policies"

    policy_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(48), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12), default="draft")
    parameters: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(String(300))
    created_by: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    approved_by: Mapped[str | None] = mapped_column(String(32))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        UniqueConstraint("organization_id", "version", name="one_version_per_policy"),
        CheckConstraint(f"status IN {POLICY_STATUSES}", name="policy_status_is_known"),
    )


class Assessment(Base):
    """One stored assessment of a merchant: the model's score and reasons, the evidence it
    rested on, and the credit range (or why there is none). It holds what is needed to
    reproduce it: the model version, the exact inputs the model was given, the range policy
    row and the range inputs. A newer assessment supersedes an older one; the old one stays.
    Decision support only: a person decides, and the decision points at the assessment."""

    __tablename__ = "assessments"

    assessment_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(48), index=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    application_id: Mapped[str | None] = mapped_column(String(48))
    status: Mapped[str] = mapped_column(String(12), default="current", index=True)
    model_version: Mapped[str] = mapped_column(String(64))
    model_sha: Mapped[str | None] = mapped_column(String(64))
    probability: Mapped[float] = mapped_column(Float)
    score: Mapped[int] = mapped_column(Integer)
    band: Mapped[str] = mapped_column(String(32))
    coverage: Mapped[float] = mapped_column(Float)
    low_score_warning: Mapped[bool] = mapped_column(Boolean, default=False)
    input_snapshot: Mapped[str] = mapped_column(Text)  # JSON: the model's inputs, by name
    evidence_refs: Mapped[str] = mapped_column(Text)  # JSON: what the assessment rested on
    reasons_positive: Mapped[str] = mapped_column(Text)
    reasons_negative: Mapped[str] = mapped_column(Text)
    summary_en: Mapped[str | None] = mapped_column(Text)
    summary_bn: Mapped[str | None] = mapped_column(Text)
    range_policy_id: Mapped[str | None] = mapped_column(String(48))
    range_available: Mapped[bool] = mapped_column(Boolean, default=False)
    range_reason: Mapped[str | None] = mapped_column(String(32))
    range_min_bdt: Mapped[float | None] = mapped_column(Float)
    range_max_bdt: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="BDT")
    range_inputs: Mapped[str | None] = mapped_column(Text)  # JSON
    range_reasoning: Mapped[str | None] = mapped_column(Text)  # JSON: the steps, in words
    plain: Mapped[str | None] = mapped_column(Text)  # JSON: the plain-language summary
    assessed_by: Mapped[str] = mapped_column(String(32))
    assessed_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class MerchantProfile(Base):
    """How staff recognise a shop created in the app: its name and where it is.

    The contract table `merchants` has no name, so a merchant created in the app keeps its
    name here, beside its permanent server-made id. Benchmark merchants have no row here.
    The name is a label, never an identity: two shops may share a name, and nothing is ever
    merged because names look alike.
    """

    __tablename__ = "merchant_profiles"

    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"), primary_key=True)
    shop_name: Mapped[str] = mapped_column(String(80))
    area: Mapped[str | None] = mapped_column(String(80))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    entered_at: Mapped[datetime] = mapped_column(DateTime)
    # What the registration form collects (src/onboarding/registrations.py). Only what the
    # credit assessment needs: no national ID, no account numbers.
    legal_name: Mapped[str | None] = mapped_column(String(120))
    owner_name: Mapped[str | None] = mapped_column(String(120))
    owner_mobile: Mapped[str | None] = mapped_column(String(20))
    alternate_contact: Mapped[str | None] = mapped_column(String(20))
    ownership_type: Mapped[str | None] = mapped_column(String(24))
    established_year: Mapped[int | None] = mapped_column(Integer)
    trade_license_number: Mapped[str | None] = mapped_column(String(60))
    branches: Mapped[int | None] = mapped_column(Integer)
    representative_name: Mapped[str | None] = mapped_column(String(120))
    representative_mobile: Mapped[str | None] = mapped_column(String(20))
    declared_obligations: Mapped[str | None] = mapped_column(Text)  # voluntary, own consent

# Each table keeps two kinds of time apart: `business_date` is the simulated date in the
# synthetic world (never after `demo.calendar_end`), and `entered_at` / `recorded_at` /
# `uploaded_at` is the real moment, in UTC, that a person saved the row.


class Application(Base):
    """A working-capital request, and the loan-shaped row that lets the scorer read it.

    The existing scorer scores a loan row, so an application writes one to `loans`
    (`loan_id`, with no outcome and a limit of 0). That row is NOT an issued loan: every
    view must ask `applications` first. The requested amount lives only here. One
    application per merchant, ever, in this prototype (`merchant_id` is unique).
    """

    __tablename__ = "applications"

    application_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    loan_id: Mapped[str] = mapped_column(ForeignKey("loans.loan_id"), unique=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"), unique=True)
    requested_amount_bdt: Mapped[float] = mapped_column(Float)
    purpose: Mapped[str] = mapped_column(String(32))
    purpose_note: Mapped[str | None] = mapped_column(Text)
    business_date: Mapped[date] = mapped_column(Date)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    entered_at: Mapped[datetime] = mapped_column(DateTime)
    demo_synthetic: Mapped[bool] = mapped_column(Boolean)

    __table_args__ = (
        CheckConstraint("requested_amount_bdt > 0", name="request_is_positive"),
    )


class ImportBatch(Base):
    """One spreadsheet import: who, when, which file, and what happened to its rows.

    The file itself is not stored, only its fingerprint (SHA-256), so the same file can be
    recognised again without keeping a copy of it.
    """

    __tablename__ = "import_batches"

    batch_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    actor: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    merchant_id: Mapped[str | None] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    record_type: Mapped[str] = mapped_column(String(32))
    file_name: Mapped[str] = mapped_column(String(128))
    file_sha256: Mapped[str] = mapped_column(String(64))
    sheet_name: Mapped[str | None] = mapped_column(String(64))
    mapping_sha256: Mapped[str | None] = mapped_column(String(64))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime)
    rows_added: Mapped[int] = mapped_column(Integer)
    rows_skipped: Mapped[int] = mapped_column(Integer)
    rows_flagged: Mapped[int] = mapped_column(Integer)
    rows_rejected: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))

    __table_args__ = (
        CheckConstraint(f"status IN {IMPORT_STATUSES}", name="batch_status_is_known"),
    )


class RecordProvenance(Base):
    """Where a record came from, how it entered, and what is known about it.

    `record_type` + `record_id` name a row in another table (a purchase, a payment, a visit,
    an application ...). Because that row can be in any of several tables this is not a
    foreign key; the code that writes both rows writes them in one transaction. A change of
    status is a new row: the history of what was known stays readable.
    """

    __tablename__ = "record_provenance"

    provenance_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_type: Mapped[str] = mapped_column(String(32))
    record_id: Mapped[str] = mapped_column(String(64), index=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    source_category: Mapped[str] = mapped_column(String(32))
    entry_method: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"))
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("import_batches.batch_id"))
    business_date: Mapped[date | None] = mapped_column(Date)
    entered_at: Mapped[datetime] = mapped_column(DateTime)
    simulated: Mapped[bool] = mapped_column(Boolean)

    __table_args__ = (
        CheckConstraint(f"record_type IN {RECORD_TYPES}", name="record_type_is_known"),
        CheckConstraint(f"entry_method IN {ENTRY_METHODS}", name="entry_method_is_known"),
        CheckConstraint(f"status IN {RECORD_STATUSES}", name="record_status_is_known"),
    )


class Visit(Base):
    """A field visit to a shop: a short structured outcome and an optional note."""

    __tablename__ = "visits"

    visit_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    business_date: Mapped[date] = mapped_column(Date)
    outcome: Mapped[str] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    entered_at: Mapped[datetime] = mapped_column(DateTime)
    simulated: Mapped[bool] = mapped_column(Boolean)


class ConsentEvent(Base):
    """A merchant's answer to the consent explanation, as recorded by staff.

    A grant also creates the canonical row in `consents`, which the scorer and every
    consent check read; a refusal creates only this event. The event keeps what the
    merchant was shown (wording version, purpose, categories), how the answer was given,
    who recorded it and when. In this prototype every event is simulated.
    """

    __tablename__ = "consent_events"

    event_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    consent_id: Mapped[str | None] = mapped_column(ForeignKey("consents.consent_id"))
    response: Mapped[str] = mapped_column(String(16))
    wording_version: Mapped[str] = mapped_column(String(32))
    purpose: Mapped[str] = mapped_column(String(64))
    categories: Mapped[str] = mapped_column(String(256))
    method: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    business_date: Mapped[date] = mapped_column(Date)
    recorded_at: Mapped[datetime] = mapped_column(DateTime)
    simulated: Mapped[bool] = mapped_column(Boolean)

    __table_args__ = (
        CheckConstraint(f"response IN {CONSENT_RESPONSES}", name="response_is_known"),
        CheckConstraint(
            "(response = 'granted' AND consent_id IS NOT NULL) "
            "OR (response = 'refused' AND consent_id IS NULL)",
            name="only_a_grant_creates_a_consent",
        ),
    )


# --- append-only enforcement ---------------------------------------------------------

_APPEND_ONLY_MESSAGE = "{table} is append-only: rows cannot be changed or deleted"
_APPLICATION_MERCHANT_MESSAGE = "an application must point to a loan row of the same merchant"
_APPLICATION_PAYMENT_MESSAGE = "a repayment cannot be recorded against an application"
_APPLICATION_ROW_MESSAGE = "the scoring row of an application cannot be changed or deleted"


def _refuse_change(mapper, connection, target) -> None:
    """Application-level guard: stop an update or delete made through the ORM."""
    raise AppendOnlyError(_APPEND_ONLY_MESSAGE.format(table=target.__tablename__))


_PROTECTED_MODELS = (
    Decision,
    AuditEntry,
    Application,
    ImportBatch,
    RecordProvenance,
    Visit,
    ConsentEvent,
    QualityReview,
)
for _model in _PROTECTED_MODELS:
    event.listen(_model, "before_update", _refuse_change)
    event.listen(_model, "before_delete", _refuse_change)


@event.listens_for(Session, "do_orm_execute")
def _refuse_bulk_change(orm_execute_state) -> None:
    """Application-level guard: stop `update(...)` and `delete(...)` statements too."""
    if not (orm_execute_state.is_update or orm_execute_state.is_delete):
        return
    for mapper in orm_execute_state.all_mappers:
        if mapper.local_table.name in PROTECTED_TABLES:
            raise AppendOnlyError(_APPEND_ONLY_MESSAGE.format(table=mapper.local_table.name))


def sqlite_append_only_triggers(table: str) -> dict[str, str]:
    """The SQLite triggers that make one table append-only: name -> CREATE statement.

    "INSERT OR REPLACE" with an existing key would silently swap a row without firing an
    UPDATE or DELETE trigger, so an insert that reuses a key is refused as well.
    """
    message = _APPEND_ONLY_MESSAGE.format(table=table)
    key = Base.metadata.tables[table].primary_key.columns.keys()[0]
    triggers = {
        f"{table}_no_{action.lower()}": (
            f"CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()} BEFORE {action} ON {table} "
            f"BEGIN SELECT RAISE(ABORT, '{message}'); END"
        )
        for action in ("UPDATE", "DELETE")
    }
    triggers[f"{table}_no_replace"] = (
        f"CREATE TRIGGER IF NOT EXISTS {table}_no_replace BEFORE INSERT ON {table} "
        f"WHEN EXISTS (SELECT 1 FROM {table} WHERE {key} = NEW.{key}) "
        f"BEGIN SELECT RAISE(ABORT, '{message}'); END"
    )
    return triggers


def sqlite_application_guard_triggers() -> dict[str, str]:
    """The SQLite triggers that keep an application's loan-shaped row honest.

    - an application's loan row must belong to the same merchant;
    - no repayment may point at an application's row (it would become invented credit
      history for any later loan: tests/test_application_scoring_safety.py);
    - the row itself can never be changed or deleted (it must never gain an outcome).
    """
    no_application = "EXISTS (SELECT 1 FROM applications WHERE loan_id = {row}.loan_id)"
    return {
        "applications_match_loan_merchant": (
            "CREATE TRIGGER IF NOT EXISTS applications_match_loan_merchant "
            "BEFORE INSERT ON applications WHEN NOT EXISTS (SELECT 1 FROM loans "
            "WHERE loan_id = NEW.loan_id AND merchant_id = NEW.merchant_id) "
            f"BEGIN SELECT RAISE(ABORT, '{_APPLICATION_MERCHANT_MESSAGE}'); END"
        ),
        "payments_not_on_applications": (
            "CREATE TRIGGER IF NOT EXISTS payments_not_on_applications BEFORE INSERT ON payments "
            f"WHEN {no_application.format(row='NEW')} "
            f"BEGIN SELECT RAISE(ABORT, '{_APPLICATION_PAYMENT_MESSAGE}'); END"
        ),
        "payments_not_moved_to_applications": (
            "CREATE TRIGGER IF NOT EXISTS payments_not_moved_to_applications "
            f"BEFORE UPDATE OF loan_id ON payments WHEN {no_application.format(row='NEW')} "
            f"BEGIN SELECT RAISE(ABORT, '{_APPLICATION_PAYMENT_MESSAGE}'); END"
        ),
        "application_loans_no_update": (
            "CREATE TRIGGER IF NOT EXISTS application_loans_no_update BEFORE UPDATE ON loans "
            f"WHEN {no_application.format(row='OLD')} "
            f"BEGIN SELECT RAISE(ABORT, '{_APPLICATION_ROW_MESSAGE}'); END"
        ),
        "application_loans_no_delete": (
            "CREATE TRIGGER IF NOT EXISTS application_loans_no_delete BEFORE DELETE ON loans "
            f"WHEN {no_application.format(row='OLD')} "
            f"BEGIN SELECT RAISE(ABORT, '{_APPLICATION_ROW_MESSAGE}'); END"
        ),
    }


def expected_sqlite_triggers() -> dict[str, str]:
    """Every trigger a current SQLite database must have: name -> CREATE statement.

    Used when tables are created and by `src/db/upgrade.py`, which adds any that an older
    database lacks (triggers are otherwise only made when their table is first created).
    """
    triggers: dict[str, str] = {}
    for table in PROTECTED_TABLES:
        triggers.update(sqlite_append_only_triggers(table))
    triggers.update(sqlite_application_guard_triggers())
    return triggers


def _append_only_triggers(table: str) -> None:
    """Database-level guard: triggers that refuse UPDATE and DELETE on one table.

    Both sets are covered by tests: SQLite always, PostgreSQL by tests/test_postgres.py
    when a test database is given (checked on Oct 14, 2026 against PostgreSQL 18.3).
    On PostgreSQL a row trigger does not fire on TRUNCATE, which empties a table in one
    statement, so a statement trigger refuses TRUNCATE as well. (SQLite has no TRUNCATE.)

    What triggers cannot do: whoever owns the database can drop a trigger and then change
    a row. On the shared PostgreSQL database the application's own account must therefore
    also have UPDATE and DELETE on these tables revoked. Triggers stop mistakes and bugs;
    access rights stop a determined person.
    """
    message = _APPEND_ONLY_MESSAGE.format(table=table)
    target = Base.metadata.tables[table]
    for statement in sqlite_append_only_triggers(table).values():
        event.listen(target, "after_create", DDL(statement).execute_if(dialect="sqlite"))

    function = DDL(
        f"CREATE OR REPLACE FUNCTION {table}_append_only() RETURNS trigger AS $$ "
        f"BEGIN RAISE EXCEPTION '{message}'; END; $$ LANGUAGE plpgsql"
    )
    trigger = DDL(
        f"CREATE TRIGGER {table}_no_change BEFORE UPDATE OR DELETE ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION {table}_append_only()"
    )
    no_truncate = DDL(
        f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
        f"FOR EACH STATEMENT EXECUTE FUNCTION {table}_append_only()"
    )
    event.listen(target, "after_create", function.execute_if(dialect="postgresql"))
    event.listen(target, "after_create", trigger.execute_if(dialect="postgresql"))
    event.listen(target, "after_create", no_truncate.execute_if(dialect="postgresql"))


for _table in PROTECTED_TABLES:
    _append_only_triggers(_table)

# The application guards span several tables (applications, loans, payments), so they are
# made once every table exists. SQLite only for now: on PostgreSQL the same rules are kept
# by the application code (src/intake/), and these triggers are not yet written there.
for _statement in sqlite_application_guard_triggers().values():
    event.listen(Base.metadata, "after_create", DDL(_statement).execute_if(dialect="sqlite"))


# --- engine and table creation -------------------------------------------------------


@lru_cache(maxsize=1)
def configured_busy_timeout_seconds() -> int:
    """How long a SQLite call waits for another writer: `api.sqlite_busy_timeout_seconds`."""
    from src.config import load_config  # not at the top: this module is imported very early

    return int(load_config()["api"]["sqlite_busy_timeout_seconds"])


def make_engine(database_url: str, busy_timeout_seconds: int | None = None) -> Engine:
    """Create a database engine. On SQLite: foreign-key checks on, and a wait for the lock.

    Every audit entry and decision is a write, and SQLite lets one writer in at a time. With
    SQLite's own default (5 seconds) 24 callers at once got "database is locked" and an HTTP
    500 (Phase 13 review). The call now waits `api.sqlite_busy_timeout_seconds` (30) for its
    turn. The journal mode is left alone: write-ahead logging would put recent changes in a
    second file, and `python tasks.py backup` copies only the database file.

    `busy_timeout_seconds` is for tests; it has no effect on PostgreSQL.
    """
    engine = create_engine(database_url)
    if engine.dialect.name == "sqlite":
        wait = busy_timeout_seconds
        if wait is None:
            wait = configured_busy_timeout_seconds()

        @event.listens_for(engine, "connect")
        def _prepare_connection(dbapi_connection, _record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute(f"PRAGMA busy_timeout={int(wait * 1000)}")
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
            for table in PROTECTED_TABLES:
                connection.exec_driver_sql(f"DROP FUNCTION IF EXISTS {table}_append_only() CASCADE")
    Base.metadata.drop_all(engine)
    engine.dispose()
