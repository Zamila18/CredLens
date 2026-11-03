"""Admin data import: POST /admin/import/{table}.

Purpose: let an admin upload a CSV for one data-contract table, check it, and load the rows
    that pass. See src/api/importer.py for what is checked.
Owner role: D (full-stack).
Implements: PROJECT_BRIEF section 18, item 20.

The body of the request is the CSV file itself (Content-Type: text/csv), so no extra
upload library is needed. `?dry_run=true` only checks and reports; nothing is written and
the check itself is audited.

Only synthetic or fixture files may be imported in the demo. The database holds only the
synthetic data, so the endpoint is closed (409) when a public data mode is active.

What an import may not do (Phase 13 review, F1 and F10, adjusted Oct 17). The refusal is HTTP
409 `import_not_allowed`, loads nothing, and is written to the audit log as
`refused_import_<table>`: purchases, deliveries, payments, loans, questionnaire and consents rows
may not name a merchant of the original data. Their history comes from the source systems, and
their consent from the consent system: an added row would show on the timeline while the score
ignores it, or unlock a merchant who never agreed. A NEW merchant (imported with `merchants`)
may get all of them, consent included.

New merchants are scored after loading (src/api/imported.py): the same model and feature rules,
no retraining. `POST /admin/import-bundle` takes a zip of the files and checks them together,
in contract order, in one transaction, so a lender's batch is checked and loaded in one go.
"""

from __future__ import annotations

import csv
import io
import zipfile

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from src.api.auth import CurrentUser, add_audit, require_owner
from src.api.common import api_error
from src.api.imported import refresh_imported
from src.api.importer import (
    HISTORY_TABLES,
    MAX_IMPORT_BYTES,
    MODELS,
    ImportNotAllowed,
    check_csv,
    load_rows,
)
from src.api.schemas import BundleReport, ImportReport
from src.api.state import Services, get_services, get_session
from src.api.tenancy import default_org, org_of
from src.db.load import LOADABLE_MODES

router = APIRouter(tags=["admin"])

# How many merchant ids a refusal names (the rest are counted in the message, not listed).
MAX_LISTED_MERCHANTS = 20

LOADED_NOTE = (
    "Loaded. New merchants with a loan and a valid consent are now in the review queue, scored "
    "by the same model (nothing was retrained). A production system would pull this data from "
    "the source systems on a schedule instead of taking a file."
)
# The order a lender's files are checked and loaded in, so every id points at something loaded.
BUNDLE_ORDER = ("merchants", "loans", "purchases", "deliveries", "payments", "questionnaire",
                "consents")


@router.post("/admin/import/{table}", response_model=ImportReport)
async def import_table(
    table: str,
    request: Request,
    dry_run: bool = False,
    user: CurrentUser = Depends(require_owner),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ImportReport:
    """Check an uploaded CSV against the data contract and load the rows that pass.

    Send the file as the request body. The report lists the rows accepted and rejected,
    and why. With `dry_run=true` nothing is loaded. Admin only; audited.
    """
    if org_of(user, services.config) != default_org(services.config):
        # Contract files load into the default organisation only (tenancy.py).
        raise api_error(
            403, "role_not_allowed", "Data files load into the default organisation only."
        )
    mode = services.config["data"]["mode"]
    if mode not in LOADABLE_MODES:
        raise api_error(
            409,
            "import_not_available",
            f"Data mode '{mode}' is not loaded into the database, so nothing can be imported.",
        )
    if table not in MODELS:
        raise api_error(
            404, "unknown_table", f"'{table}' is not a data-contract table: {', '.join(MODELS)}."
        )
    body = await request.body()
    if len(body) > MAX_IMPORT_BYTES:
        megabytes = MAX_IMPORT_BYTES // (1024 * 1024)
        raise api_error(413, "file_too_large", f"The file is larger than {megabytes} MB.")

    scored = None
    if table in HISTORY_TABLES:
        if services.scorer is None:
            raise api_error(
                503,
                "scorer_not_ready",
                "Records for existing merchants must be checked against the scorer, "
                "which is not ready. Run: python -m src.api.preflight",
            )
        scored = services.scorer.source_merchant_ids()
    try:
        report, accepted = await run_in_threadpool(check_csv, session, table, body, scored)
    except ImportNotAllowed as refusal:
        # The refusal is itself worth a line in the audit log: who tried, and which table.
        add_audit(session, user, f"refused_import_{table}")
        session.commit()
        facts = {"merchants": refusal.merchants[:MAX_LISTED_MERCHANTS]} if refusal.merchants else {}
        raise api_error(409, "import_not_allowed", refusal.message, **facts) from None
    report.dry_run = dry_run
    if report.file_error:
        report.note = "The whole file was refused. Nothing was loaded."
    elif dry_run:
        report.note = "Check only: nothing was loaded."
    elif not accepted:
        report.note = "No row passed the check. Nothing was loaded."
    else:
        await run_in_threadpool(load_rows, session, table, accepted)
        report.loaded = True
        report.note = LOADED_NOTE
    add_audit(session, user, f"{'check_import' if dry_run else 'import'}_{table}")
    session.commit()
    services.forget_data_today(bulk=True)
    if report.loaded:
        await run_in_threadpool(refresh_imported, services, session)
    return report


def _bundle_files(body: bytes) -> dict[str, bytes]:
    """The CSV files of an uploaded zip, by table. Raises ValueError with a plain message."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(body))
    except zipfile.BadZipFile as error:
        raise ValueError("The upload is not a zip file.") from error
    files: dict[str, bytes] = {}
    for info in archive.infolist():
        if info.is_dir():
            continue
        name = info.filename.replace("\\", "/").rsplit("/", 1)[-1].lower()
        if not name.endswith(".csv") or name.startswith("."):
            continue
        table = name[: -len(".csv")]
        if table not in MODELS:
            raise ValueError(
                f"'{info.filename}' is not a data-contract table: name the files "
                f"{', '.join(t + '.csv' for t in BUNDLE_ORDER)}."
            )
        if info.file_size > MAX_IMPORT_BYTES:
            raise ValueError(f"'{info.filename}' is larger than the limit for one file.")
        files[table] = archive.read(info)
    if not files:
        raise ValueError("The zip holds no CSV file named after a data-contract table.")
    return files


@router.post("/admin/import-bundle", response_model=BundleReport)
async def import_bundle(
    request: Request,
    dry_run: bool = False,
    user: CurrentUser = Depends(require_owner),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> BundleReport:
    """Check a zip of contract CSVs together and load the rows that pass. Admin only; audited.

    The files are taken in contract order (merchants, loans, purchases, deliveries, payments,
    questionnaire, consents) in ONE transaction: each file is checked against what the files
    before it would add. With `dry_run=true`, or when any file is refused as a whole, nothing
    is kept. After a load, the new merchants are scored (same model, nothing retrained).
    """
    if org_of(user, services.config) != default_org(services.config):
        # Contract files load into the default organisation only (tenancy.py).
        raise api_error(
            403, "role_not_allowed", "Data files load into the default organisation only."
        )
    mode = services.config["data"]["mode"]
    if mode not in LOADABLE_MODES:
        raise api_error(
            409,
            "import_not_available",
            f"Data mode '{mode}' is not loaded into the database, so nothing can be imported.",
        )
    if services.scorer is None:
        message = services.scorer_error or "The scorer is not ready."
        raise api_error(503, "scorer_not_ready", message)
    body = await request.body()
    if len(body) > MAX_IMPORT_BYTES:
        megabytes = MAX_IMPORT_BYTES // (1024 * 1024)
        raise api_error(413, "file_too_large", f"The file is larger than {megabytes} MB.")
    try:
        files = _bundle_files(body)
    except ValueError as error:
        raise api_error(422, "bad_bundle", str(error)) from None

    source = services.scorer.source_merchant_ids()
    reports: list[ImportReport] = []

    def check_and_stage() -> None:
        for table in BUNDLE_ORDER:
            if table not in files:
                continue
            scored = source if table in HISTORY_TABLES else None
            report, accepted = check_csv(session, table, files[table], scored)
            report.dry_run = dry_run
            if accepted and not report.file_error:
                # Staged in the transaction, so the next file is checked against these rows.
                load_rows(session, table, accepted)
            reports.append(report)

    try:
        await run_in_threadpool(check_and_stage)
    except ImportNotAllowed as refusal:
        session.rollback()
        add_audit(session, user, "refused_import_bundle")
        session.commit()
        facts = {"merchants": refusal.merchants[:MAX_LISTED_MERCHANTS]} if refusal.merchants else {}
        raise api_error(409, "import_not_allowed", refusal.message, **facts) from None

    whole_file_refused = any(r.file_error for r in reports)
    keep = not dry_run and not whole_file_refused
    if keep:
        session.commit()
    else:
        session.rollback()
    for report in reports:
        report.loaded = keep and report.rows_accepted > 0
        report.note = (
            "Loaded." if report.loaded else
            "The whole file was refused." if report.file_error else
            "Check only: nothing was loaded." if dry_run else "Nothing was loaded."
        )
    add_audit(session, user, "import_bundle" if keep else "check_import_bundle")
    session.commit()
    services.forget_data_today(bulk=True)

    new_merchants: list[str] = []
    if keep:
        scored_now = await run_in_threadpool(refresh_imported, services, session)
        mentioned = _merchant_ids_in(files.get("merchants", b""))
        new_merchants = [m for m in scored_now if m in mentioned]
    if keep:
        note = LOADED_NOTE
    elif whole_file_refused:
        note = "A file was refused as a whole (see its report). Nothing was loaded."
    else:
        note = "Check only: nothing was loaded. Untick 'check only' to load the accepted rows."
    return BundleReport(
        dry_run=dry_run, loaded=keep, tables=reports, new_merchants=new_merchants, note=note
    )


def _merchant_ids_in(raw: bytes) -> set[str]:
    """The merchant ids named in a merchants.csv (for the report's list of new merchants)."""
    if not raw:
        return set()
    text = raw.decode("utf-8-sig", errors="replace")
    return {row.get("merchant_id", "").strip() for row in csv.DictReader(io.StringIO(text))}
