"""Tests for the live import: a lender's file of NEW merchants is loaded and scored.

Owner role: D (full-stack), with the lead.
Implements: PROJECT_BRIEF section 18, item 45 (live import demo); docs/API_NOTES.md ("Import").

What must hold:
- An imported merchant gets exactly the score, coverage, band and reasons it would get had
  it been in the original data (same model, same rules, same "today"; nothing retrained).
- `POST /admin/import-bundle` checks a zip of contract files in order, in one transaction:
  a check-only run keeps nothing; a load puts the new merchants in the review queue.
- A consent (or any history row) for a merchant of the original data is refused as a whole.
- A decision keeps the band and the coverage that were on screen.
"""

from __future__ import annotations

import copy
import io
import shutil
import zipfile

import pandas as pd
import pytest
from accounts_seed import headers_for, seed_accounts, seed_person  # noqa: F401
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.api.imported import refresh_imported
from src.api.main import app
from src.api.state import Services
from src.config import PROJECT_ROOT
from src.db import models as db
from src.db.load import load_tables
from src.model.labels import latest_date
from src.model.scoring import Scorer
from src.synth.demo_batch import ORDER, bundle_zip, rename_merchants
from src.synth.generate import build_tables
from tests.test_api import ADMIN, OFFICER, VIEWER, count

NEW_WORLD_SEED = 7
NEW_WORLD_SIZE = 300
NEW_MERCHANTS = 40


@pytest.fixture(scope="module")
def batch(api_world):
    """New merchants from another generated world, renamed D00001.., and the scorer that
    would have seen them in the original data (the reference for every comparison)."""
    config = copy.deepcopy(api_world.config)
    config["seed"] = NEW_WORLD_SEED
    config["data"]["n_merchants"] = NEW_WORLD_SIZE
    world = build_tables(config, 0.5)[0]
    first = sorted(world["merchants"]["merchant_id"])[:NEW_MERCHANTS]
    new = rename_merchants(world, first)
    combined = {
        name: pd.concat([api_world.tables[name], new[name]], ignore_index=True) for name in ORDER
    }
    reference = Scorer(api_world.config, tables=combined, saved=api_world.saved)
    queue = reference.queue()
    waiting = queue[queue["merchant_id"].str.startswith("D")]
    return {"tables": new, "reference": reference, "waiting": waiting}


@pytest.fixture(scope="module")
def template(api_world, tmp_path_factory):
    """A loaded database file and a built scorer, copied by every test (loading is slow)."""
    path = tmp_path_factory.mktemp("live") / "template.db"
    load_tables(api_world.tables, "sqlite:///" + path.as_posix())
    from src.db.models import make_engine

    seed_accounts(make_engine("sqlite:///" + path.as_posix()), api_world.config)
    return path, Scorer(api_world.config, tables=api_world.tables, saved=api_world.saved)


@pytest.fixture()
def live(api_world, template, tmp_path):
    """A fresh copy of the API stack (own database, own scorer), so imports stay here."""
    path, scorer = template
    shutil.copyfile(path, tmp_path / "live.db")
    engine = db.make_engine("sqlite:///" + (tmp_path / "live.db").as_posix())
    # `set_imported` replaces the scorer's tables, never changes them, so a shallow copy is
    # a scorer of its own.
    services = Services(config=api_world.config, engine=engine, scorer=copy.copy(scorer))
    app.state.services = services
    try:
        yield TestClient(app), services
    finally:
        del app.state.services
        engine.dispose()


def post_bundle(api, content: bytes, params: str = "", headers=ADMIN):
    return api.post(
        f"/admin/import-bundle{params}",
        headers={**headers, "Content-Type": "application/zip"},
        content=content,
    )


def card_facts(card: dict) -> tuple:
    reasons = [
        (r["code"], round(r["contribution"], 6))
        for r in card["reasons_positive"] + card["reasons_negative"]
    ]
    return card["score"], round(card["coverage"], 6), card["band"], reasons


# --- the scorer -----------------------------------------------------------------------------


def test_the_new_world_shares_the_same_today(api_world, batch):
    """Otherwise the comparison below would not be fair: "today" decides pending and consent."""
    assert latest_date(batch["tables"]) <= latest_date(api_world.tables)
    assert batch["reference"].as_of == latest_date(api_world.tables)


def test_an_imported_merchant_scores_as_if_it_had_been_in_the_data(api_world, batch):
    scorer = Scorer(api_world.config, tables=api_world.tables, saved=api_world.saved)
    added = scorer.set_imported(batch["tables"])
    consenting = batch["waiting"][batch["waiting"]["consent_valid"]]["merchant_id"].tolist()
    assert len(consenting) >= 5, "the test world needs pending merchants with consent"
    assert set(consenting) <= set(added)
    for merchant_id in consenting:
        assert card_facts(scorer.card(merchant_id)) == card_facts(
            batch["reference"].card(merchant_id)
        ), merchant_id
    # the queue is the reference queue: the same merchants, scores and bands
    columns = ["merchant_id", "loan_id", "pending_since", "consent_valid", "score", "band"]
    pd.testing.assert_frame_equal(
        scorer.queue()[columns].reset_index(drop=True),
        batch["reference"].queue()[columns].reset_index(drop=True),
    )


def test_setting_nothing_removes_the_imported_merchants(api_world, batch):
    scorer = Scorer(api_world.config, tables=api_world.tables, saved=api_world.saved)
    before = len(scorer.merchant_ids())
    scorer.set_imported(batch["tables"])
    assert scorer.imported_merchant_ids()
    assert scorer.set_imported(None) == []
    assert len(scorer.merchant_ids()) == before and scorer.imported_merchant_ids() == []


def test_a_merchant_of_the_original_data_is_never_replaced(api_world, batch):
    scorer = Scorer(api_world.config, tables=api_world.tables, saved=api_world.saved)
    known = api_world.services.scorer.queue()
    merchant_id = known[known["consent_valid"]]["merchant_id"].iloc[0]
    before = card_facts(scorer.card(merchant_id))
    # the same merchant's rows again, with every loan id changed
    tables = {name: frame[frame["merchant_id"] == merchant_id].copy()
              for name, frame in api_world.tables.items()}
    tables["loans"]["loan_id"] = "X-" + tables["loans"]["loan_id"].astype(str)
    assert merchant_id not in scorer.set_imported(tables)
    assert card_facts(scorer.card(merchant_id)) == before


# --- the bundle endpoint --------------------------------------------------------------------


def test_a_check_only_run_reports_every_file_and_keeps_nothing(live, batch):
    api, services = live
    merchants = count(services, db.Merchant)
    response = post_bundle(api, bundle_zip(batch["tables"]), "?dry_run=true")
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["dry_run"] is True and report["loaded"] is False
    assert report["new_merchants"] == []
    assert [t["table"] for t in report["tables"]] == list(ORDER)
    for table in report["tables"]:
        assert table["rows_rejected"] == 0, table
        assert table["rows_accepted"] == len(batch["tables"][table["table"]])
    assert count(services, db.Merchant) == merchants
    assert services.scorer.imported_merchant_ids() == []
    assert count(services, db.AuditEntry, db.AuditEntry.action == "check_import_bundle") == 1


def test_a_load_puts_the_new_merchants_in_the_queue_with_their_scores(live, batch):
    api, services = live
    response = post_bundle(api, bundle_zip(batch["tables"]))
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["loaded"] is True and "nothing was retrained" in report["note"]
    waiting = batch["waiting"]
    assert set(waiting["merchant_id"]) <= set(report["new_merchants"])
    assert count(services, db.AuditEntry, db.AuditEntry.action == "import_bundle") == 1

    listed = api.get("/merchants", headers=OFFICER).json()
    queue = {row["merchant_id"]: row for row in listed}
    for row in waiting.itertuples():
        shown = queue[row.merchant_id]
        assert shown["consent_valid"] is row.consent_valid
        if row.consent_valid:
            assert (shown["score"], shown["band"]) == (row.score, row.band)
            card = api.get(f"/merchants/{row.merchant_id}/score", headers=OFFICER).json()
            assert card_facts(card) == card_facts(batch["reference"].card(row.merchant_id))
            profile = api.get(f"/merchants/{row.merchant_id}", headers=OFFICER).json()
            assert profile["consent_valid"] is True and profile["timeline"]
        else:
            assert shown["score"] is None
            score = api.get(f"/merchants/{row.merchant_id}/score", headers=OFFICER)
            assert score.status_code == 403


def test_imported_merchants_are_scored_again_after_a_restart(live, api_world, batch):
    api, services = live
    post_bundle(api, bundle_zip(batch["tables"]))
    fresh = Scorer(api_world.config, tables=api_world.tables, saved=api_world.saved)
    restarted = Services(config=api_world.config, engine=services.engine, scorer=fresh)
    with Session(services.engine) as session:
        added = refresh_imported(restarted, session)
    assert set(batch["waiting"]["merchant_id"]) <= set(added)


def test_a_consent_for_a_known_merchant_refuses_the_whole_bundle(live, batch):
    api, services = live
    known = services.scorer.queue()
    merchant_id = known[~known["consent_valid"]]["merchant_id"].iloc[0]
    tables = {name: frame.copy() for name, frame in batch["tables"].items()}
    extra = tables["consents"].iloc[[0]].copy()
    extra["consent_id"], extra["merchant_id"] = "D-UNLOCK", merchant_id
    tables["consents"] = pd.concat([tables["consents"], extra], ignore_index=True)
    merchants, consents = count(services, db.Merchant), count(services, db.Consent)

    response = post_bundle(api, bundle_zip(tables))
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "import_not_allowed"
    assert response.json()["detail"]["merchants"] == [merchant_id]
    # nothing at all was kept, not even the new merchants of the earlier files
    assert (count(services, db.Merchant), count(services, db.Consent)) == (merchants, consents)
    assert count(services, db.AuditEntry, db.AuditEntry.action == "refused_import_bundle") == 1
    assert api.get(f"/merchants/{merchant_id}/score", headers=OFFICER).status_code == 403


def test_bad_rows_are_rejected_and_the_rest_loads(live, batch, api_world):
    api, services = live
    tables = {name: frame.copy() for name, frame in batch["tables"].items()}
    repeat = api_world.tables["merchants"].iloc[[0]]
    tables["merchants"] = pd.concat([tables["merchants"], repeat], ignore_index=True)
    bad = tables["purchases"].iloc[[0]].copy()
    bad["purchase_id"], bad["purchase_date"] = "D-BAD-DATE", "2026-13-40"
    tables["purchases"] = pd.concat([tables["purchases"], bad], ignore_index=True)
    report = post_bundle(api, bundle_zip(tables)).json()
    rejected = {t["table"]: t["rows_rejected"] for t in report["tables"]}
    assert rejected["merchants"] == 1 and rejected["purchases"] == 1
    assert report["loaded"] is True and report["new_merchants"]


def test_a_file_with_wrong_columns_keeps_nothing(live, batch):
    api, services = live
    tables = {name: frame.copy() for name, frame in batch["tables"].items()}
    tables["loans"] = tables["loans"].drop(columns=["limit_bdt"])
    merchants = count(services, db.Merchant)
    report = post_bundle(api, bundle_zip(tables)).json()
    assert report["loaded"] is False and "Nothing was loaded" in report["note"]
    assert count(services, db.Merchant) == merchants


def test_the_committed_demo_file_reports_exactly_its_three_mistakes(live):
    """data/demo/credlens_demo_bundle.zip: the file the lead uploads in front of the judges."""
    api, _ = live
    content = (PROJECT_ROOT / "data" / "demo" / "credlens_demo_bundle.zip").read_bytes()
    report = post_bundle(api, content, "?dry_run=true").json()
    rejected = {t["table"]: t["rows_rejected"] for t in report["tables"]}
    assert rejected == {name: 0 for name in ORDER} | {
        "merchants": 1, "purchases": 1, "deliveries": 1
    }
    assert all(t["file_error"] is None for t in report["tables"])


def zip_of(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, text in files.items():
            archive.writestr(name, text)
    return buffer.getvalue()


@pytest.mark.parametrize(
    "content",
    [b"not a zip at all", zip_of({"readme.txt": "hello"}), zip_of({"sales.csv": "a\n1\n"})],
    ids=["not-a-zip", "no-csv", "unknown-table"],
)
def test_a_bad_upload_is_a_clear_422(live, content):
    api, _ = live
    response = post_bundle(api, content)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "bad_bundle"


def test_files_inside_a_folder_of_the_zip_are_found(live, batch):
    api, _ = live
    files = {f"export/{name}.csv": frame.to_csv(index=False)
             for name, frame in batch["tables"].items()}
    report = post_bundle(api, zip_of(files), "?dry_run=true").json()
    assert [t["table"] for t in report["tables"]] == list(ORDER)


@pytest.mark.parametrize("headers", [OFFICER, VIEWER, {}])
def test_only_an_admin_may_import(live, batch, headers):
    api, services = live
    response = post_bundle(api, bundle_zip(batch["tables"]), headers=headers)
    assert response.status_code in (401, 403)
    assert services.scorer.imported_merchant_ids() == []


# --- the decision keeps what was on screen --------------------------------------------------


def test_a_decision_keeps_the_band_and_coverage_shown(live, batch):
    api, _ = live
    post_bundle(api, bundle_zip(batch["tables"]))
    waiting = batch["waiting"]
    merchant_id = waiting[waiting["consent_valid"]]["merchant_id"].iloc[0]
    card = api.get(f"/merchants/{merchant_id}/score", headers=OFFICER).json()
    response = api.post(
        f"/merchants/{merchant_id}/decision",
        headers=OFFICER,
        json={"officer_action": "accept"},
    )
    assert response.status_code == 201, response.text
    decision = response.json()
    assert (decision["score_shown"], decision["band_shown"]) == (card["score"], card["band"])
    assert decision["coverage_shown"] == pytest.approx(card["coverage"])
    logged = api.get("/decisions", headers=OFFICER).json()
    mine = [row for row in logged if row["merchant_id"] == merchant_id]
    assert mine and mine[0]["band_shown"] == card["band"]
