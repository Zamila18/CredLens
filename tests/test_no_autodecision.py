"""test_no_autodecision: the system never approves or declines credit; an officer decides.

Owner role: D (full-stack).
Implements: CLAUDE.md (no code path may approve or decline credit; overrides need a
    written reason; decisions are append-only) and PROJECT_BRIEF section 8.

The API contract has no approve or decline action either:
see tests/test_fixtures.py::test_api_contract_has_no_approve_or_decline_action.
These tests use the whole API stack of `api_world` (tests/conftest.py).
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.db import models as db
from tests.test_api import ADMIN, ANSWERS, OFFICER, VIEWER, count, loans_snapshot

FORBIDDEN_WORDS = ("approv", "declin", "reject", "eligib")


@pytest.fixture(scope="module")
def consenting(api_world) -> list[str]:
    queue = api_world.services.scorer.queue()
    return queue[queue["consent_valid"]]["merchant_id"].tolist()


def every_endpoint(merchant_id: str) -> list[tuple[str, str, dict]]:
    """Every method and path of the API, with a body where one is needed.

    The test below checks this list against the published spec, so a new endpoint cannot
    be added without being exercised here.
    """
    return [
        ("GET", "/health", {}),
        ("GET", "/ready", {}),
        ("GET", "/merchants", {}),
        ("GET", f"/merchants/{merchant_id}", {}),
        ("GET", f"/merchants/{merchant_id}/score", {}),
        ("GET", f"/merchants/{merchant_id}/consent", {}),
        ("POST", f"/merchants/{merchant_id}/consent-request", {}),
        ("GET", "/consents", {}),
        ("POST", f"/merchants/{merchant_id}/decision", {"json": {"officer_action": "accept"}}),
        ("POST", f"/merchants/{merchant_id}/questionnaire", {"json": ANSWERS}),
        ("GET", "/decisions", {}),
        ("GET", "/model/card", {}),
        ("GET", "/audit", {}),
        ("POST", "/admin/import/loans", {"content": b"loan_id\nL-X\n"}),
        ("POST", "/admin/import/loans?dry_run=true", {"content": b""}),
        ("POST", "/admin/import-bundle?dry_run=true", {"content": b"not a zip"}),
    ]


def test_every_endpoint_of_the_api_is_covered_by_this_file(api, consenting):
    covered = set()
    for method, url, _ in every_endpoint(consenting[0]):
        path = url.split("?")[0].replace(consenting[0], "{merchant_id}")
        path = path.replace("/loans", "/{table}")
        covered.add((method.lower(), path))
    published = {
        (method, path)
        for path, operations in api.get("/openapi.json").json()["paths"].items()
        for method in operations
    }
    assert published == covered, "a new endpoint must be added to every_endpoint()"


def test_no_endpoint_changes_a_loan_status(api, api_world, consenting):
    """Calling every endpoint, as every role, leaves every loan exactly as it was."""
    before = loans_snapshot(api_world)
    merchant_id = consenting[-20]
    for method, url, arguments in every_endpoint(merchant_id):
        for headers in (OFFICER, ADMIN, VIEWER, {}):
            api.request(method, url, headers=headers, **arguments)
    assert loans_snapshot(api_world) == before
    assert any(label is not None for _, _, label in before), "the loans table is not empty"


def test_scoring_never_writes_a_decision(api, api_world, consenting):
    """Reading a score records no decision. Only an officer action does."""
    before = count(api_world, db.Decision)
    api.get("/merchants", headers=OFFICER)
    for merchant_id in consenting[:40]:
        for url in (f"/merchants/{merchant_id}/score", f"/merchants/{merchant_id}"):
            for headers in (OFFICER, ADMIN, VIEWER):
                assert api.get(url, headers=headers).status_code == 200
    api.get("/model/card", headers=ADMIN)
    api.get("/decisions", headers=ADMIN)
    assert count(api_world, db.Decision) == before


def test_a_decision_is_only_ever_an_officers_reading(api, api_world, consenting):
    """Whatever the band, the only thing stored is the officer's own action and reason."""
    for merchant_id in consenting[-30:-25]:
        card = api.get(f"/merchants/{merchant_id}/score", headers=OFFICER).json()
        response = api.post(
            f"/merchants/{merchant_id}/decision", headers=OFFICER, json={"officer_action": "accept"}
        )
        assert response.status_code == 201
        stored = response.json()
        assert stored["officer_action"] == "accept"
        assert stored["officer_id"] == "officer-1"
        assert stored["score_shown"] == card["score"]
        assert set(stored) == {
            "decision_id",
            "merchant_id",
            "officer_id",
            "model_version",
            "score_shown",
            "band_shown",
            "coverage_shown",
            "officer_action",
            "reason_text",
            "decided_at",
        }
        # band and coverage are a copy of what was on screen, like the score: never a verdict
        assert (stored["band_shown"], stored["coverage_shown"]) == (card["band"], card["coverage"])


def test_override_requires_a_written_reason(api, api_world, consenting):
    """The API rejects an override that has no reason text, and the database does too."""
    merchant_id = consenting[-31]
    before = count(api_world, db.Decision)
    for action in ("override_up", "override_down"):
        for reason in (None, "", "   "):
            response = api.post(
                f"/merchants/{merchant_id}/decision",
                headers=OFFICER,
                json={"officer_action": action, "reason_text": reason},
            )
            assert response.status_code == 422, (action, reason)
    assert count(api_world, db.Decision) == before
    # second guard: even code that skipped the API could not store one
    with Session(api_world.engine) as session:
        row = {
            "decision_id": "DEC-DIRECT",
            "merchant_id": merchant_id,
            "officer_id": "officer-1",
            "model_version": "test-version",
            "score_shown": 50,
            "officer_action": "override_down",
            "reason_text": "  ",
            "decided_at": datetime(2026, 1, 1),
        }
        with pytest.raises(IntegrityError):
            session.execute(insert(db.Decision.__table__), [row])
            session.commit()


def test_decisions_and_audit_entries_cannot_be_changed_even_by_code(api_world):
    """Append-only: the application refuses an update or a delete of either table."""
    with Session(api_world.engine) as session:
        for model, column in ((db.Decision, "officer_action"), (db.AuditEntry, "action")):
            with pytest.raises(db.AppendOnlyError):
                session.execute(update(model).values({column: "changed"}))
        row = session.scalars(select(db.AuditEntry)).first()
        if row is not None:
            row.action = "changed"
            with pytest.raises(db.AppendOnlyError):
                session.flush()
            session.rollback()


def test_no_screen_text_says_approved_declined_or_eligible(api, api_world, consenting):
    """Nothing an officer reads beside a score says or implies approved or declined.

    (The model card is left out on purpose: its limits say, truthfully, that the tool must
    not be used for automatic approval or decline.)
    """
    texts = []
    for headers in (OFFICER, ADMIN):
        texts.append(api.get("/merchants", headers=headers).text)
    for merchant_id in consenting[:60]:
        texts.append(api.get(f"/merchants/{merchant_id}/score", headers=OFFICER).text)
        texts.append(api.get(f"/merchants/{merchant_id}", headers=OFFICER).text)
    texts.append(api.get("/health").text)
    joined = " ".join(texts).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in joined, word


def test_the_mifos_loader_that_says_approve_never_touches_a_score():
    """`approve` in src/db/mifos_load.py is the Fineract API command that replays an old, already
    issued synthetic loan on a local Mifos test server. It must not be reachable from a score:
    the file imports only the standard library and `src.db.mifos_adapter`, nothing from
    `src.model` or `src.api`, and its code never mentions a score, a probability or a band."""
    import ast
    import sys
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "src" / "db" / "mifos_load.py"
    source = path.read_text(encoding="utf-8")
    modules = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            modules.add(node.module)
    ours = {name for name in modules if name.split(".")[0] not in sys.stdlib_module_names}
    assert ours == {"src.db.mifos_adapter"}, ours
    assert not any(name.startswith(("src.model", "src.api")) for name in modules)
    code = "\n".join(
        line.split("#")[0] for line in source.splitlines() if not line.strip().startswith("#")
    ).lower()
    for word in ("score", "probability", "band", "scorer", "officer_action"):
        assert word not in code, word
    # the one place the word is used, and what it is
    assert source.count("command=approve") == 1
    notes = (path.parent.parent.parent / "docs" / "API_NOTES.md").read_text(encoding="utf-8")
    assert "mifos_load.py" in notes and "Fineract API command" in notes
