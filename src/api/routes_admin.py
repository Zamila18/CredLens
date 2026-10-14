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
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from src.api.auth import CurrentUser, add_audit, require_roles
from src.api.common import api_error
from src.api.importer import MAX_IMPORT_BYTES, MODELS, check_csv, load_rows
from src.api.schemas import ImportReport
from src.api.state import Services, get_services, get_session
from src.db.load import LOADABLE_MODES

router = APIRouter(tags=["admin"])

LOADED_NOTE = (
    "Loaded. New data changes no score until the model is trained again and the API is "
    "restarted (python tasks.py train). A production system would pull this data from the "
    "source systems on a schedule instead of taking a file."
)


@router.post("/admin/import/{table}", response_model=ImportReport)
async def import_table(
    table: str,
    request: Request,
    dry_run: bool = False,
    user: CurrentUser = Depends(require_roles("admin")),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> ImportReport:
    """Check an uploaded CSV against the data contract and load the rows that pass.

    Send the file as the request body. The report lists the rows accepted and rejected,
    and why. With `dry_run=true` nothing is loaded. Admin only; audited.
    """
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

    report, accepted = await run_in_threadpool(check_csv, session, table, body)
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
    services.forget_data_today()
    return report
