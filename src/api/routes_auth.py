"""Sign-in, registration and passwords for real accounts.

Purpose: the entry point of the application (src/accounts/ does the work): login, logout,
    who am I, company registration, joining with an invitation code, set or change a password.
Owner role: D (full-stack).
Implements: Phase 1 of the unified platform plan (sections 4 to 6).

The session token is sent only as an HttpOnly, SameSite=Strict cookie (Secure on a production
server): page scripts cannot read it and other sites cannot send it. The response body never
contains it. Sign-in, registration and invitation checks are rate limited per address and per
identifier (src/accounts/ratelimit.py). Registration returns nothing secret: the person is
sent to the Sign In page.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from src.accounts import invitations, ratelimit, registration, service
from src.accounts.passwords import clean_code
from src.accounts.service import AccountError
from src.api.auth import (
    ANY_ACCOUNT,
    PLATFORM_ADMIN,
    SESSION_COOKIE,
    CurrentUser,
    accounts_ready,
    add_audit,
    require_roles,
)
from src.api.common import api_error
from src.api.schemas import (
    ChangePasswordIn,
    CompanyRegisterIn,
    InvitationPreviewOut,
    JoinRegisterIn,
    LoginIn,
    MeOut,
    RegisteredOut,
    SetupPasswordIn,
)
from src.api.state import Services, get_services, get_session
from src.api.tenancy import org_of, organization_out
from src.db import models as db

router = APIRouter(tags=["accounts"])

ANY_CALLER = require_roles(*ANY_ACCOUNT)


def _secure_cookies() -> bool:
    return os.environ.get("CREDLENS_ENV", "").strip().lower() == "production"


def refused(error: AccountError):
    return api_error(error.status, error.code, error.message, **error.facts)


def me_out(session: Session, services: Services, user: CurrentUser) -> MeOut:
    if user.is_platform:
        return MeOut(
            user_id=user.user_id,
            display_name=user.display_name,
            role=user.role,
            is_platform=True,
            organization_id=None,
            organization_name=None,
            environment=None,
        )
    org_id = org_of(user, services.config)
    org = organization_out(session, services.config, org_id)
    row = session.get(db.Organization, org_id)
    return MeOut(
        user_id=user.user_id,
        display_name=user.display_name,
        role=user.role,
        is_owner=user.is_owner,
        organization_id=org["organization_id"],
        organization_name=org["name"],
        environment=org["environment"],
        fsr_label=row.fsr_label if row is not None else None,
    )


def _limited(
    session: Session,
    services: Services,
    request: Request,
    kind: str,
    identifier: str | None,
    **keys,
) -> str:
    """Refuse when the address or identifier tried too often; returns the address."""
    ip = ratelimit.client_ip(request)
    try:
        ratelimit.check(session, services.config, kind, ip, identifier, **keys)
    except AccountError as error:
        raise refused(error) from None
    return ip


@router.post("/auth/login", response_model=MeOut)
def login(
    body: LoginIn,
    request: Request,
    response: Response,
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> MeOut:
    """Check the email/number and password; on success set the session cookie."""
    if not accounts_ready(session):
        raise api_error(503, "accounts_not_set_up", "Accounts are not set up on this server yet.")
    ip = _limited(
        session,
        services,
        request,
        "login",
        body.identifier,
        per_ip="login_per_ip",
        per_identifier="login_per_identifier",
        failures_only=True,
    )
    try:
        token, row, membership = service.login(
            session, services.config, body.identifier, body.password
        )
    except AccountError as error:
        ratelimit.record(session, "login", ip, body.identifier, False)
        session.commit()  # keeps the failed-attempt counts
        raise refused(error) from None
    ratelimit.record(session, "login", ip, body.identifier, True)
    user = session.get(db.User, row.user_id)
    if membership is None:
        caller = CurrentUser(
            user_id=user.user_id, role=PLATFORM_ADMIN, display_name=user.display_name
        )
    else:
        caller = CurrentUser(
            user_id=user.user_id,
            role=membership.role,
            organization_id=membership.organization_id,
            display_name=user.display_name,
            is_owner=bool(membership.is_owner),
        )
    add_audit(session, caller, "login")
    session.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(services.config["auth"]["session_max_hours"]) * 3600,
        httponly=True,
        samesite="strict",
        secure=_secure_cookies(),
        path="/",
    )
    return me_out(session, services, caller)


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, session: Session = Depends(get_session)) -> None:
    """End this browser's session (if any) and clear the cookie."""
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        service.logout(session, token)
        user = getattr(request.state, "user", None)
        if user is not None:
            add_audit(session, user, "logout")
        session.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/auth/me", response_model=MeOut)
def me(
    user: CurrentUser = Depends(ANY_CALLER),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> MeOut:
    """Who the server says the caller is: role and organisation come from the server."""
    return me_out(session, services, user)


@router.post("/auth/register/company", response_model=RegisteredOut, status_code=201)
def register_company(
    body: CompanyRegisterIn,
    request: Request,
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> RegisteredOut:
    """Register a new company; its first Credit Officer becomes the company's owner. Sign in
    afterwards: nothing is returned that could sign anyone in."""
    ip = _limited(session, services, request, "register", None, per_ip="register_per_ip")
    ratelimit.record(session, "register", ip, None, False)
    try:
        user, org = registration.register_company(session, services.config, body.model_dump())
    except AccountError as error:
        session.commit()
        raise refused(error) from None
    session.commit()
    return RegisteredOut(organization_name=org.name, role="credit_officer")


@router.post("/auth/register/join", response_model=RegisteredOut, status_code=201)
def register_join(
    body: JoinRegisterIn,
    request: Request,
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> RegisteredOut:
    """Join an organisation with a company invitation code. The organisation and the role
    come from the code, never from this form."""
    ip = _limited(
        session,
        services,
        request,
        "register",
        None,
        per_ip="register_per_ip",
    )
    code = clean_code(body.invitation_code)
    _limited(
        session,
        services,
        request,
        "invite_check",
        code,
        per_ip="invite_check_per_ip",
        per_identifier="invite_check_per_identifier",
    )
    ratelimit.record(session, "register", ip, None, False)
    ratelimit.record(session, "invite_check", ip, code, False)
    try:
        _, org, role = registration.register_join(session, services.config, body.model_dump())
    except AccountError as error:
        session.commit()
        raise refused(error) from None
    session.commit()
    return RegisteredOut(organization_name=org.name, role=role)


@router.get("/auth/invitations/preview", response_model=InvitationPreviewOut)
def preview_invitation(
    request: Request,
    code: str = Query(max_length=40),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> InvitationPreviewOut:
    """What a valid invitation code opens (company name and role), for the join form. Every
    problem with a code gets the same answer, and tries are rate limited."""
    cleaned = clean_code(code)
    ip = _limited(
        session,
        services,
        request,
        "invite_check",
        cleaned,
        per_ip="invite_check_per_ip",
        per_identifier="invite_check_per_identifier",
    )
    try:
        row = invitations.resolve(session, code)
    except AccountError as error:
        ratelimit.record(session, "invite_check", ip, cleaned, False)
        session.commit()
        raise refused(error) from None
    ratelimit.record(session, "invite_check", ip, cleaned, True)
    session.commit()
    org = session.get(db.Organization, row.organization_id)
    return InvitationPreviewOut(
        organization_name=org.name, role=row.role, default_territory=row.default_territory
    )


@router.post("/auth/password/setup", status_code=204)
def setup_password(
    body: SetupPasswordIn,
    request: Request,
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> None:
    """Set or reset a password with an owner's one-time code. Ends every session of the
    account; the person then signs in with the new password."""
    ip = _limited(
        session,
        services,
        request,
        "reset",
        body.identifier,
        per_ip="invite_check_per_ip",
        per_identifier="invite_check_per_identifier",
    )
    try:
        user = service.set_password_with_code(
            session, services.config, body.identifier, body.code, body.password
        )
    except AccountError as error:
        ratelimit.record(session, "reset", ip, body.identifier, False)
        session.commit()
        raise refused(error) from None
    membership = service.active_membership(session, user.user_id)
    add_audit(
        session,
        CurrentUser(
            user_id=user.user_id,
            role=membership.role if membership else "none",
            organization_id=membership.organization_id if membership else None,
        ),
        "password_set",
    )
    session.commit()


@router.post("/auth/password", status_code=204)
def change_password(
    body: ChangePasswordIn,
    response: Response,
    user: CurrentUser = Depends(ANY_CALLER),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> None:
    """Change one's own password. Ends every session, this one too."""
    try:
        service.change_password(session, services.config, user.user_id, body.current, body.new)
    except AccountError as error:
        raise refused(error) from None
    add_audit(session, user, "password_changed")
    session.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
