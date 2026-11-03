"""Data sources: the catalog, an organisation's connections, and the connector lifecycle.

Every route is scoped to the caller's organisation: another organisation's connection is
a 404. Who may do what:
- every role: read the catalog, the connections, their runs and matches;
- officer and admin: discover fields, preview, confirm or reject merchant matches, sync;
- admin only: create a connection, test it, revoke it.

Credentials: a connection stores only the NAME of the environment variable that holds a
credential (`secret_ref`). The value is read at the moment of use, is never stored, logged
or returned, and the API only says whether a reference is set.

Runs: a test, a discovery and a sync each leave a run in the history, failed or not. A
failed run saves no record. Writes go through src/connectors/service.py.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import READERS, CurrentUser, add_audit, require_owner, require_roles
from src.api.common import api_error, refuse_rows_not_shown
from src.api.routes_intake import _assessment, _protected
from src.api.schemas import (
    ConnectorInfo,
    MatchDecision,
    MatchOut,
    SourceConnectionOut,
    SourceCreate,
    SourceDetail,
    SourceFields,
    SourceLinkOut,
    SourceMapping,
    SourcePreview,
    SourcePreviewRow,
    SourceRunOut,
    UnmatchedMerchant,
)
from src.api.state import Services, get_services, get_session
from src.api.tenancy import merchant_in_org, org_of, organization_out
from src.connectors import service
from src.connectors.base import ConnectorError
from src.connectors.registry import CONNECTORS, connector
from src.db import models as db
from src.intake.policy import IntakeRefused, live_merchant, new_id, require_synthetic_mode, utc_now

router = APIRouter(tags=["data sources"])

ANY_ROLE = require_roles(*READERS)
STAFF = require_roles("credit_officer")
ADMIN = require_owner
SECRET_REF = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
PREVIEW_ROWS = 300


def _iso(value) -> str | None:
    return value.isoformat(timespec="seconds") if value else None


def _run_out(run: db.SourceRun) -> SourceRunOut:
    return SourceRunOut(
        run_id=run.run_id,
        kind=run.kind,
        status=run.status,
        actor=run.actor,
        started_at=_iso(run.started_at),
        finished_at=_iso(run.finished_at),
        rows_added=run.rows_added,
        rows_skipped=run.rows_skipped,
        rows_flagged=run.rows_flagged,
        rows_rejected=run.rows_rejected,
        rows_unmatched=run.rows_unmatched,
        error_code=run.error_code,
        error_message=run.error_message,
    )


def _runs(session: Session, connection_id: str, limit: int | None = None) -> list[db.SourceRun]:
    query = (
        select(db.SourceRun)
        .where(db.SourceRun.connection_id == connection_id)
        .order_by(db.SourceRun.started_at.desc(), db.SourceRun.run_id)
    )
    return list(session.scalars(query.limit(limit) if limit else query))


def _connection_out(session: Session, row: db.SourceConnection) -> dict[str, Any]:
    spec = connector(row.connector_key)
    last = _runs(session, row.connection_id, 1)
    return {
        "connection_id": row.connection_id,
        "connector_key": row.connector_key,
        "connector_name": spec.name if spec else row.connector_key,
        "display_name": row.display_name,
        "status": row.status,
        "settings": {k: str(v) for k, v in json.loads(row.settings_json or "{}").items()},
        "secret_ref_set": bool(row.secret_ref),
        "created_by": row.created_by,
        "created_at": _iso(row.created_at),
        "last_tested_at": _iso(row.last_tested_at),
        "last_error": row.last_error,
        "revoked_at": _iso(row.revoked_at),
        "last_run": _run_out(last[0]) if last else None,
    }


def _connection(
    session: Session, services: Services, user: CurrentUser, connection_id: str
) -> db.SourceConnection:
    """The connection, if it belongs to the caller's organisation; otherwise 404."""
    row = session.get(db.SourceConnection, connection_id)
    if row is None or row.organization_id != org_of(user, services.config):
        raise api_error(404, "unknown_source", f"No data source {connection_id!r}.")
    return row


def _usable(row: db.SourceConnection) -> None:
    if row.status == "revoked":
        raise api_error(
            409,
            "source_revoked",
            "This connection was revoked. Add a new connection to use the source again.",
        )


def _context(services: Services, row: db.SourceConnection):
    secret = os.environ.get(row.secret_ref) if row.secret_ref else None
    return service.context(services.config, row, secret)


def _new_run(row: db.SourceConnection, user: CurrentUser, kind: str) -> db.SourceRun:
    now = utc_now()
    return db.SourceRun(
        run_id=new_id("SR"),
        connection_id=row.connection_id,
        organization_id=row.organization_id,
        kind=kind,
        status="ok",
        actor=user.user_id,
        started_at=now,
        finished_at=now,
        rows_added=0,
        rows_skipped=0,
        rows_flagged=0,
        rows_rejected=0,
        rows_unmatched=0,
    )


def _fail(
    session: Session, row: db.SourceConnection, run: db.SourceRun, code: str, message: str
) -> SourceRunOut:
    """Record a failed run (nothing from it is saved) and mark the connection."""
    session.rollback()
    run.status, run.error_code, run.error_message, run.finished_at = (
        "failed",
        code,
        message,
        utc_now(),
    )
    row = session.merge(row)
    row.status, row.last_error = "error", message
    session.add(run)
    session.commit()
    return _run_out(run)


@router.get("/sources/catalog", response_model=list[ConnectorInfo])
def source_catalog(_: CurrentUser = Depends(ANY_ROLE)) -> list[ConnectorInfo]:
    """Every kind of source CredLens knows and whether it works in this build."""
    return [ConnectorInfo(**c.describe()) for c in CONNECTORS.values()]


@router.get("/sources", response_model=list[SourceConnectionOut])
def list_sources(
    user: CurrentUser = Depends(ANY_ROLE),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> list[SourceConnectionOut]:
    """The organisation's connections, newest first."""
    rows = session.scalars(
        select(db.SourceConnection)
        .where(db.SourceConnection.organization_id == org_of(user, services.config))
        .order_by(db.SourceConnection.created_at.desc())
    ).all()
    return [SourceConnectionOut(**_connection_out(session, r)) for r in rows]


@router.post("/sources", response_model=SourceConnectionOut, status_code=201)
def create_source(
    body: SourceCreate,
    user: CurrentUser = Depends(ADMIN),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> SourceConnectionOut:
    """Add a connection for a source that can be connected in this build. Admin only."""
    spec = connector(body.connector_key)
    if spec is None:
        raise api_error(422, "unknown_connector", "There is no such kind of source.")
    if spec.availability != "available":
        raise api_error(
            409,
            "connector_not_available",
            "This kind of source cannot be connected in this build: it needs authorised access "
            "and an implementation."
            if spec.availability == "planned"
            else "This source works without a connection; use its own screen.",
        )
    org = org_of(user, services.config)
    environment = organization_out(session, services.config, org)["environment"]
    if spec.sandbox_only and environment != "benchmark":
        raise api_error(
            409,
            "connector_not_available",
            "The synthetic feed works only in the benchmark organisation.",
        )
    allowed = {f.key: f for f in spec.settings if f.kind != "secret_ref"}
    unknown = sorted(set(body.settings) - set(allowed))
    if unknown:
        raise api_error(422, "unknown_setting", f"Unknown setting(s): {', '.join(unknown)}.")
    settings: dict[str, str] = {}
    for key, setting in allowed.items():
        value = (body.settings.get(key) or "").strip()
        if setting.required and not value:
            raise api_error(422, "missing_setting", f"{setting.label} is required.", setting=key)
        if value and setting.choices and value not in setting.choices:
            raise api_error(
                422,
                "invalid_setting",
                f"{setting.label} must be one of {', '.join(setting.choices)}.",
                setting=key,
            )
        if value:
            settings[key] = value
    secret_ref = (body.secret_ref or "").strip() or None
    if secret_ref and not SECRET_REF.match(secret_ref):
        raise api_error(
            422,
            "invalid_secret_ref",
            "A credential reference is the NAME of an environment variable (capital letters, "
            "digits, _), never the credential itself.",
        )
    row = db.SourceConnection(
        connection_id=new_id("SC"),
        organization_id=org,
        connector_key=spec.key,
        display_name=body.display_name.strip(),
        status="not_tested",
        settings_json=json.dumps(settings),
        secret_ref=secret_ref,
        created_by=user.user_id,
        created_at=utc_now(),
    )
    session.add(row)
    add_audit(session, user, "create_source")
    session.commit()
    return SourceConnectionOut(**_connection_out(session, row))


@router.get("/sources/{connection_id}", response_model=SourceDetail)
def source_detail(
    connection_id: str,
    user: CurrentUser = Depends(ANY_ROLE),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> SourceDetail:
    row = _connection(session, services, user, connection_id)
    links = service.confirmed_links(session, row)
    return SourceDetail(
        **_connection_out(session, row),
        runs=[_run_out(r) for r in _runs(session, connection_id, 30)],
        linked_merchants=sum(1 for link in links.values() if link.decision == "confirmed"),
    )


@router.post("/sources/{connection_id}/test", response_model=SourceRunOut)
def test_source(
    connection_id: str,
    user: CurrentUser = Depends(ADMIN),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> SourceRunOut:
    """Try the connection. The run (ok or failed) goes into the history. Admin only."""
    row = _connection(session, services, user, connection_id)
    _usable(row)
    run = _new_run(row, user, "test")
    spec = connector(row.connector_key)
    try:
        spec.test(service.settings_of(row), _context(services, row))
    except ConnectorError as error:
        add_audit(session, user, "test_source")
        return _fail(session, row, run, error.code, error.message)
    row.status, row.last_error, row.last_tested_at = "connected", None, utc_now()
    session.add(run)
    add_audit(session, user, "test_source")
    session.commit()
    return _run_out(run)


@router.post("/sources/{connection_id}/discover", response_model=SourceFields)
def discover_source(
    connection_id: str,
    user: CurrentUser = Depends(STAFF),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> SourceFields:
    """The fields the source sends, with a suggested mapping to CredLens's fields."""
    row = _connection(session, services, user, connection_id)
    _usable(row)
    run = _new_run(row, user, "discover")
    try:
        fields = connector(row.connector_key).discover(
            service.settings_of(row), _context(services, row)
        )
    except ConnectorError as error:
        failed = _fail(session, row, run, error.code, error.message)
        raise api_error(
            502, "source_failed", error.message, run_id=failed.run_id, source_code=error.code
        ) from None
    session.add(run)
    session.commit()
    return SourceFields(
        fields=fields,
        suggested=service.suggest_mapping(fields),
        required=list(service.REQUIRED),
        canonical=list(service.FIELDS),
        run=_run_out(run),
    )


def _fetch_and_plan(
    services: Services, session: Session, user: CurrentUser, row: db.SourceConnection, mapping: dict
):
    spec = connector(row.connector_key)
    rows = spec.fetch(service.settings_of(row), _context(services, row))
    fields = spec.discover(service.settings_of(row), _context(services, row))
    clean = service.check_mapping(mapping, fields)
    return spec, service.plan_rows(session, services.config, row, rows, clean)


def _unmatched(
    session: Session, services: Services, user: CurrentUser, row: db.SourceConnection, plan
) -> list[UnmatchedMerchant]:
    scope = merchant_in_org(org_of(user, services.config), services.config)
    links = service.confirmed_links(session, row)
    groups: dict[str, list] = {}
    for r in plan.rows:
        if r.outcome == "unmatched" and r.external_ref:
            groups.setdefault(r.external_ref, []).append(r)
    out = []
    for ref, rows in groups.items():
        first = rows[0]
        link = links.get(ref)
        out.append(
            UnmatchedMerchant(
                external_ref=ref,
                merchant_name=first.merchant_name,
                district=first.district,
                rows=len(rows),
                decision="rejected" if link and link.decision == "rejected" else None,
                candidates=service.candidates(
                    session, services.config, scope, first.merchant_name, first.district
                ),
            )
        )
    return out


@router.post("/sources/{connection_id}/preview", response_model=SourcePreview)
def preview_source(
    connection_id: str,
    body: SourceMapping,
    user: CurrentUser = Depends(STAFF),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> SourcePreview:
    """What a sync would do to every row, and which source merchants need matching.

    Saves nothing.
    """
    refuse_rows_not_shown(services.config)
    row = _connection(session, services, user, connection_id)
    _usable(row)
    try:
        _, plan = _fetch_and_plan(services, session, user, row, body.mapping)
    except ConnectorError as error:
        raise api_error(502, "source_failed", error.message, source_code=error.code) from None
    except IntakeRefused as refused:
        raise api_error(refused.status, refused.code, refused.message, **refused.facts) from None
    return SourcePreview(
        counts=plan.counts(),
        rows=[
            SourcePreviewRow(
                index=r.index,
                outcome=r.outcome,
                code=r.code,
                external_ref=r.external_ref,
                merchant_id=r.merchant_id,
                kind=r.kind,
                business_date=r.business_date.isoformat() if r.business_date else None,
                amount=r.amount,
                delivery_status=r.delivery_status,
                source_reference=r.source_reference,
            )
            for r in plan.rows[:PREVIEW_ROWS]
        ],
        unmatched=_unmatched(session, services, user, row, plan),
    )


@router.post("/sources/{connection_id}/matches", response_model=MatchOut, status_code=201)
def decide_match(
    connection_id: str,
    body: MatchDecision,
    user: CurrentUser = Depends(STAFF),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> MatchOut:
    """A person confirms that a source merchant is a CredLens merchant, or rejects a match.
    A new decision replaces the earlier one for that reference; the history stays."""
    row = _connection(session, services, user, connection_id)
    _usable(row)
    merchant_id = body.merchant_id if body.decision == "confirmed" else None
    if body.decision == "confirmed":
        if not merchant_id:
            raise api_error(422, "missing_merchant", "Choose the CredLens merchant to link.")
        merchant = session.get(db.Merchant, merchant_id)
        org = org_of(user, services.config)
        if (
            merchant is None
            or (merchant.organization_id or services.config["organization"]["id"]) != org
        ):
            raise api_error(
                404, "unknown_merchant", f"No merchant {merchant_id!r} in the database."
            )
        try:
            live_merchant(session, merchant_id, _protected(services))
        except IntakeRefused as refused:
            raise api_error(refused.status, refused.code, refused.message) from None
    link = db.SourceMerchantLink(
        organization_id=row.organization_id,
        connection_id=row.connection_id,
        external_ref=body.external_ref.strip(),
        merchant_id=merchant_id,
        decision=body.decision,
        decided_by=user.user_id,
        decided_at=utc_now(),
    )
    session.add(link)
    add_audit(session, user, f"source_match_{body.decision}", merchant_id)
    session.commit()
    return MatchOut(
        external_ref=link.external_ref,
        merchant_id=link.merchant_id,
        decision=link.decision,
        decided_by=link.decided_by,
        decided_at=_iso(link.decided_at),
    )


@router.get("/sources/{connection_id}/matches", response_model=list[SourceLinkOut])
def list_matches(
    connection_id: str,
    user: CurrentUser = Depends(ANY_ROLE),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> list[SourceLinkOut]:
    """Every match decision of this source, newest first; `current` marks the ones in force.
    A wrong link is corrected with a new decision (POST .../matches); records it already
    saved stay and show up as a data-quality issue for a person to review."""
    row = _connection(session, services, user, connection_id)
    links = session.scalars(
        select(db.SourceMerchantLink)
        .where(db.SourceMerchantLink.connection_id == row.connection_id)
        .order_by(db.SourceMerchantLink.id.desc())
    ).all()
    current = {link.id for link in service.confirmed_links(session, row).values()}
    ids = {link.merchant_id for link in links if link.merchant_id}
    names = {
        p.merchant_id: p.shop_name
        for p in session.scalars(
            select(db.MerchantProfile).where(db.MerchantProfile.merchant_id.in_(ids))
        )
    }
    saved: dict[str, int] = {}
    for merchant_id in session.scalars(
        select(db.SourceRecord.merchant_id).where(
            db.SourceRecord.connection_id == row.connection_id
        )
    ):
        saved[merchant_id] = saved.get(merchant_id, 0) + 1
    return [
        SourceLinkOut(
            id=link.id,
            external_ref=link.external_ref,
            merchant_id=link.merchant_id,
            shop_name=names.get(link.merchant_id),
            decision=link.decision,
            decided_by=link.decided_by,
            decided_at=_iso(link.decided_at),
            current=link.id in current,
            records_saved=saved.get(link.merchant_id, 0) if link.merchant_id else 0,
        )
        for link in links
    ]


@router.post("/sources/{connection_id}/sync", response_model=SourceRunOut)
def sync_source(
    connection_id: str,
    body: SourceMapping,
    user: CurrentUser = Depends(STAFF),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> SourceRunOut:
    """Read the source and save the rows that pass, all or nothing. Returns the run: a failed
    run saved nothing and says why. Rows of unmatched merchants wait for a person to match them."""
    refuse_rows_not_shown(services.config)
    row = _connection(session, services, user, connection_id)
    _usable(row)
    run = _new_run(row, user, "sync")
    try:
        require_synthetic_mode(services.config)
        spec, plan = _fetch_and_plan(services, session, user, row, body.mapping)
        counts = plan.counts()
        run.rows_added, run.rows_skipped, run.rows_flagged = (
            counts["add"],
            counts["skip"],
            counts["flag"],
        )
        run.rows_rejected, run.rows_unmatched = counts["reject"], counts["unmatched"]
        if counts["add"]:
            service.save(session, services.config, row, spec, plan, run, user)
    except ConnectorError as error:
        return _fail(session, row, run, error.code, error.message)
    except IntakeRefused as refused:
        if refused.code in ("unknown_field", "missing_column", "column_used_twice"):
            raise api_error(
                refused.status, refused.code, refused.message, **refused.facts
            ) from None
        return _fail(session, row, run, refused.code, refused.message)
    run.finished_at = utc_now()
    row.status, row.last_error = "connected", None
    session.add(run)
    session.commit()
    if run.rows_added:
        _assessment(services, session, next(r.merchant_id for r in plan.rows if r.outcome == "add"))
    return _run_out(run)


@router.post("/sources/{connection_id}/revoke", response_model=SourceConnectionOut)
def revoke_source(
    connection_id: str,
    user: CurrentUser = Depends(ADMIN),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> SourceConnectionOut:
    """Stop using a connection: it can no longer be tested, read or synced, and its credential
    reference is cleared. Records it saved stay, with their lineage. Admin only."""
    row = _connection(session, services, user, connection_id)
    _usable(row)
    row.status, row.secret_ref, row.revoked_at, row.revoked_by = (
        "revoked",
        None,
        utc_now(),
        user.user_id,
    )
    add_audit(session, user, "revoke_source")
    session.commit()
    return SourceConnectionOut(**_connection_out(session, row))
