"""Who is calling: a signed-in account (session cookie).

Purpose: decide the caller of every request on the server, and give each endpoint the role
    it may act with. Roles are never chosen by the browser.
Owner role: D (full-stack).
Implements: Phase 1 of the unified platform plan (one application, real accounts only).

The browser holds an HttpOnly session cookie after POST /auth/login. The account's role and
organisation come from the server: a platform administrator from `platform_admins`, everyone
else from their membership. There is no other way in: no header or parameter picks a user.

Roles:
- `platform_admin`: CredLens staff configured in the private .env. Platform-wide pages only;
  never an organisation's merchants, records or documents.
- `credit_officer`: an organisation's officer. The first officer who registered the company
  is its owner (`is_owner`) and also manages invitations, staff and assignments.
- `records_officer`: the Records Desk, which processes receipts for the company's shops.
- `merchant`: a shop owner, limited to their own shop.
- `auditor`: reads an organisation's records and audit log; changes nothing.

No caller: 401. A role that may not do the thing: 403.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

from fastapi import Request
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from src.api.common import api_error, utc_now
from src.db import models as db

SESSION_COOKIE = "credlens_session"
PLATFORM_ADMIN = "platform_admin"

# Roles of an organisation's people (memberships).
ACCOUNT_ROLES = db.STAFF_ROLES
# Every role that works inside an organisation: never the platform administrator.
EVERY_ROLE = ACCOUNT_ROLES
# The company's decision makers and reviewers.
READERS = ("credit_officer", "auditor")
# Every signed-in account, platform administrators included (who am I, change password).
ANY_ACCOUNT = ACCOUNT_ROLES + (PLATFORM_ADMIN,)

# True while serving a caller of the reserved benchmark organisation (or a caller-less public
# request). The intake rules read it (src/intake/policy.py): benchmark records are synthetic
# and use the benchmark calendar; a real company's records are real and use today's date.
# In a real deployment nobody belongs to the benchmark organisation.
BENCHMARK_REQUEST: ContextVar[bool] = ContextVar("credlens_benchmark_request", default=True)


@dataclass(frozen=True)
class CurrentUser:
    """Who is calling, with the role the server gave them."""

    user_id: str
    role: str
    organization_id: str | None = None  # empty: a platform admin, or the benchmark organisation
    display_name: str | None = None
    is_owner: bool = False
    merchant_id: str | None = None  # a merchant's own shop

    @property
    def is_platform(self) -> bool:
        return self.role == PLATFORM_ADMIN


def accounts_ready(session: Session) -> bool:
    """Whether the account tables exist. Without them nobody can sign in."""
    return inspect(session.get_bind()).has_table("user_credentials")


def _identify(session: Session, request: Request, config: dict) -> tuple[CurrentUser | None, str]:
    """(caller, problem), from the session cookie."""
    from src.accounts.service import resolve_session

    cookie = request.cookies.get(SESSION_COOKIE)
    if not cookie:
        return None, "missing_token"
    if not accounts_ready(session):
        return None, "missing_token"
    found = resolve_session(session, config, cookie)
    if found is None:
        return None, "session_expired"
    user, membership = found
    if membership is None:  # a platform administrator
        return (
            CurrentUser(
                user_id=user.user_id,
                role=PLATFORM_ADMIN,
                organization_id=None,
                display_name=user.display_name,
            ),
            "",
        )
    return (
        CurrentUser(
            user_id=user.user_id,
            role=membership.role,
            organization_id=membership.organization_id,
            display_name=user.display_name,
            is_owner=bool(membership.is_owner),
            merchant_id=membership.merchant_id,
        ),
        "",
    )


async def identify(request: Request) -> None:
    """App-wide first step of every request: find the caller and remember it on the request.

    Never refuses on its own (public endpoints need no caller); `require_roles` does.
    """
    request.state.user, request.state.auth_problem = None, "missing_token"
    services = getattr(request.app.state, "services", None)
    if services is None:
        request.state.auth_problem = "not_started"
        return
    if services.database_error:
        request.state.auth_problem = "database_not_ready"
        request.state.auth_detail = services.database_error
        return
    with Session(services.engine) as session:
        user, problem = _identify(session, request, services.config)
    request.state.user, request.state.auth_problem = user, problem
    default = services.config["organization"]["id"]
    BENCHMARK_REQUEST.set(
        user is None or (not user.is_platform and user.organization_id in (None, default))
    )


_PROBLEMS = {
    "missing_token": "Sign in first.",
    "session_expired": "Your session has ended. Sign in again.",
}


def _caller(request: Request) -> CurrentUser:
    user: CurrentUser | None = getattr(request.state, "user", None)
    if user is None:
        problem = getattr(request.state, "auth_problem", "missing_token") or "missing_token"
        if problem == "not_started":
            raise api_error(503, problem, "The API has not finished starting.")
        if problem == "database_not_ready":
            raise api_error(503, problem, getattr(request.state, "auth_detail", ""))
        raise api_error(401, problem, _PROBLEMS.get(problem, "Sign in first."))
    return user


def require_roles(*allowed: str):
    """A dependency that lets only the given roles through (401 without a caller, 403 for
    any other role)."""

    def dependency(request: Request) -> CurrentUser:
        user = _caller(request)
        if user.role not in allowed:
            raise api_error(
                403,
                "role_not_allowed",
                f"The {user.role} role cannot do this. Allowed: {', '.join(allowed)}.",
            )
        return user

    return dependency


def require_owner(request: Request) -> CurrentUser:
    """The company's owner: a Credit Officer who registered the company (or was made an owner)."""
    user = _caller(request)
    if user.role != "credit_officer" or not user.is_owner:
        raise api_error(403, "owner_only", "Only the company's owner Credit Officer can do this.")
    return user


def require_audit_access(request: Request) -> CurrentUser:
    """Who may read the organisation's audit log: its owner Credit Officer and its auditors."""
    user = _caller(request)
    if user.role == "auditor" or (user.role == "credit_officer" and user.is_owner):
        return user
    raise api_error(
        403, "role_not_allowed", "Only the company's owner or an auditor can read the audit log."
    )


def add_audit(
    session: Session, user: CurrentUser, action: str, merchant_id: str | None = None
) -> None:
    """Add one audit row (who, role, organisation, what, which merchant, when in UTC). The
    caller commits.

    The audit log is append-only: nothing in the API can change or remove a row.
    """
    session.add(
        db.AuditEntry(
            actor=user.user_id,
            role=user.role,
            action=action,
            merchant_id=merchant_id,
            timestamp=utc_now(),
            organization_id=user.organization_id,
        )
    )
