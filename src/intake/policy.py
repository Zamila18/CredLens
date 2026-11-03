"""The rules of the synthetic demonstration, read from the `demo` section of the config.

Purpose: one place for the demo calendar, synthetic-only mode and the intake lists, so no
    other module copies a date or a list (implementation pack, appendix A3).
Owner role: D (full-stack), with the lead.

Two kinds of time are kept apart everywhere:
- a business date: the simulated date inside the synthetic world, never after
  `demo.calendar_end`;
- an entry time: the real moment, in UTC, that a person saved a record (`utc_now`).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.db import models as db


class IntakeRefused(Exception):
    """A record was refused before anything was written. `status` is the HTTP status."""

    def __init__(self, status: int, code: str, message: str, **facts: Any) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.facts = facts


def utc_now() -> datetime:
    """The real time in UTC, without a time zone, as the database stores it."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_id(prefix: str) -> str:
    """A new identifier made by the server, for example 'LA-3f2c...'. Never typed by a user."""
    return f"{prefix}-{uuid.uuid4().hex[:24]}"


def demo(config: dict[str, Any]) -> dict[str, Any]:
    """The `demo` section of the config."""
    return config["demo"]


def benchmark_request() -> bool:
    """True while serving the reserved benchmark organisation (offline synthetic data, tests)
    or a caller-less request; False for a real company's account. Set per request by
    src/api/auth.py. In a real deployment nobody belongs to the benchmark organisation."""
    from src.api.auth import BENCHMARK_REQUEST

    return BENCHMARK_REQUEST.get()


def real_today(config: dict[str, Any]) -> date:
    """Today's date where the organisation works (config organization.timezone)."""
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo(config["organization"]["timezone"])).date()


def calendar_end(config: dict[str, Any]) -> date:
    """The last business day records may carry, and "today" for consent and checks.

    For the benchmark organisation: the last day of the synthetic world
    (`demo.calendar_end`). For a real company: today's real date. A record can never be dated
    in the future.
    """
    if not benchmark_request():
        return real_today(config)
    return date.fromisoformat(demo(config)["calendar_end"])


def require_synthetic_mode(config: dict[str, Any]) -> None:
    """For the benchmark organisation, refuse every intake write unless synthetic-only mode is on.

    A real company's account writes real records (not synthetic, dated by the real date);
    this switch is about the benchmark organisation only.
    """
    if not benchmark_request():
        return
    if not demo(config)["synthetic_only"]:
        raise IntakeRefused(
            403,
            "intake_closed",
            "Entering records is available only in synthetic demo mode. This prototype has "
            "no path for real records.",
        )


def check_business_date(day: date, config: dict[str, Any], what: str = "The date") -> date:
    """Refuse a business date after the end of the demo calendar."""
    if not isinstance(day, date) or isinstance(day, datetime):
        raise IntakeRefused(422, "invalid_date", f"{what} must be a calendar date.")
    end = calendar_end(config)
    if day > end:
        raise IntakeRefused(
            422,
            "date_after_demo_calendar",
            f"{what} ({day.isoformat()}) is after the end of the demo calendar "
            f"({end.isoformat()}). Use a date on or before it.",
            calendar_end=end.isoformat(),
        )
    return day


def check_choice(value: Any, allowed: list[str], what: str) -> str:
    """Refuse a value that is not one of the configured choices."""
    if value not in allowed:
        raise IntakeRefused(
            422, "invalid_choice", f"{what} must be one of: {', '.join(allowed)}.", allowed=allowed
        )
    return value


def check_note(note: str | None, limit: int, what: str = "The note") -> str | None:
    """An optional short text: blank becomes empty, a long one is refused."""
    if note is None or not note.strip():
        return None
    note = note.strip()
    if len(note) > limit:
        raise IntakeRefused(422, "note_too_long", f"{what} is longer than {limit} characters.")
    return note


def live_merchant(
    session: Session, merchant_id: str, protected_merchants: frozenset[str] | set[str]
) -> db.Merchant:
    """The merchant, if it exists and is not one of the read-only benchmark merchants.

    The benchmark merchants' records come from the generated source files, which the scorer
    reads; a record added for them in the database would show on screen but never reach
    their score. So the workflow only adds records for merchants created in the app.
    """
    merchant = session.get(db.Merchant, merchant_id)
    if merchant is None:
        raise IntakeRefused(
            404, "unknown_merchant", f"No merchant {merchant_id!r} in the database."
        )
    if merchant_id in protected_merchants:
        raise IntakeRefused(
            409,
            "benchmark_merchant",
            f"{merchant_id} belongs to the read-only benchmark data; records can be added only "
            "for merchants created in the app.",
        )
    return merchant


def add_provenance(
    session: Session,
    *,
    record_type: str,
    record_id: str,
    merchant_id: str,
    source_category: str,
    entry_method: str,
    status: str,
    actor: str | None,
    entered_at: datetime,
    business_date: date | None = None,
    batch_id: str | None = None,
) -> None:
    """Add the provenance row of a record. The caller commits, together with the record."""
    session.add(
        db.RecordProvenance(
            record_type=record_type,
            record_id=record_id,
            merchant_id=merchant_id,
            source_category=source_category,
            entry_method=entry_method,
            status=status,
            actor=actor,
            batch_id=batch_id,
            business_date=business_date,
            entered_at=entered_at,
            simulated=benchmark_request(),
        )
    )
