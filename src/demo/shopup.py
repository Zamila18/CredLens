# ruff: noqa: E501  (the written guide and the sample data are prose; long lines are intended)
"""Build the ShopUp demonstration database: `python tasks.py demo`.

Purpose: a screen recording of an empty product shows nothing, so this script builds one believable
    story into its OWN database (data/credlens_demo.db; the real data/credlens.db is never
    touched): the lender ShopUp, its Credit and Records Desk staff, and nine shops with months of
    receipts, earlier loans, parcels, reports, applications and decisions.
Owner role: D (full-stack).
Implements: the demonstration database for the project video.

How it stays honest:
- Everything goes through the product's own code: sign-up, invitations, shop registration with
  the consent PDF, the Records Desk receipt workflow (check, correct, publish), merchant
  reports, applications and decisions are the real HTTP endpoints or the real service calls.
- Past dates come from a clock that goes back while seeding (every module's `now`), so the
  records, consents and audit lines carry the right dates. Nothing is edited after the fact.
- The score is whatever the real model says about the records. The data is tuned (see
  shopup_data.py); the model and the rules are not.
- Every name, number and address is invented. Passwords below are demonstration passwords.

Run from the project folder: python tasks.py demo [--fast] [--seed N]
"""

from __future__ import annotations

import argparse
import copy
import os
import random
import shutil
import sqlite3
import sys
import time as wallclock
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DEMO_DB = ROOT / "data" / "credlens_demo.db"
MAIN_DB = ROOT / "data" / "credlens.db"
DOC = ROOT / "docs" / "product" / "DEMO_SHOPUP.md"
SIGNED_NAME = "signed-consent-form.pdf"


# --- the clock ---------------------------------------------------------------------------------


class Clock:
    """The time the product believes it is. Off: the real time."""

    def __init__(self, tz: str) -> None:
        self.tz = ZoneInfo(tz)
        self.moment: datetime | None = None
        self.dates = True
        self._n = 0

    def set(self, day: date, dates: bool = True) -> None:
        """Be on `day`, a few minutes later than the last call. `dates=False` moves only entry
        times, not 'today' (used when a score must be read as of the real today)."""
        self._n += 1
        self.moment = datetime(day.year, day.month, day.day, 4, 0) + timedelta(
            minutes=(self._n * 3) % 420, seconds=self._n % 60
        )
        self.dates = dates

    def off(self) -> None:
        self.moment = None

    def now(self) -> datetime:
        return self.moment or datetime.now(timezone.utc).replace(tzinfo=None)

    def today(self, config: dict[str, Any] | None = None) -> date:
        if self.moment is not None and self.dates:
            return self.moment.date()
        return datetime.now(self.tz).date()


def install_clock(clock: Clock) -> list[tuple[Any, str, Any]]:
    """Point every module's own copy of the clock functions at `clock`. Returns the undo list.
    The per-record scoring check is switched off too: it rebuilds a shop's features on every
    save, which is a safety net for typed records and far too slow for a bulk seed."""
    from src.accounts import service as accounts
    from src.api import common
    from src.intake import policy, records

    swaps = [
        (accounts.now, clock.now),
        (common.utc_now, clock.now),
        (policy.utc_now, clock.now),
        (policy.real_today, clock.today),
        (records.check_scoring_inputs, lambda *args, **kwargs: None),
    ]
    undo = []
    for name, module in list(sys.modules.items()):
        if not name.startswith("src.") or module is None:
            continue
        for attr, value in list(vars(module).items()):
            for old, new in swaps:
                if value is old:
                    setattr(module, attr, new)
                    undo.append((module, attr, old))
    return undo


# --- small helpers -----------------------------------------------------------------------------


def log(text: str) -> None:
    print(f"  {text}", flush=True)


def ok(response, *codes: int):
    if response.status_code not in (codes or (200, 201)):
        raise SystemExit(
            f"\nThe demo seed stopped: {response.request.method} {response.request.url.path} "
            f"answered {response.status_code}: {response.text[:500]}"
        )
    return response


def clamp(day: date, low: date, high: date) -> date:
    return max(low, min(high, day))


def fake_boxes(plan, doubtful: bool = False) -> list:
    """What a reader would return for a printed memo (used by --fast instead of the real reader)."""
    from src.extraction.engine import Box

    def box(text, x, y, conf=0.95, w=90):
        return Box(text, conf, x, y, x + w, y + 20)

    boxes = [
        box(plan.supplier, 100, 10, w=200),
        box(f"Memo No: {plan.memo_no}", 20, 40, w=130),
        box(f"Date: {plan.day.strftime('%d/%m/%Y')}", 250, 40, w=140),
        box("Item", 20, 80),
        box("Qty", 170, 80),
        box("Rate", 250, 80),
        box("Amount", 330, 80),
    ]
    for i, line in enumerate(plan.lines):
        y = 110 + 30 * i
        sure = 0.58 if doubtful and i == 1 else 0.97
        boxes += [
            box(line["item"], 20, y, w=140),
            box(f"{line['quantity']:g} {line['unit']}", 170, y),
            box(f"{line['unit_price']:,}", 250, y),
            box(f"{line['amount_bdt']:,}", 330, y, conf=sure),
        ]
    y = 110 + 30 * len(plan.lines) + 20
    boxes += [box("Total:", 250, y), box(f"{plan.total:,}", 330, y)]
    return boxes


# --- the seed ----------------------------------------------------------------------------------


class Seed:
    def __init__(self, fast: bool, seed: int) -> None:
        self.fast = fast
        self.rng = random.Random(seed)
        self.results: dict[str, dict[str, Any]] = {}
        self.admin_emails: list[str] = []
        self.shop_ids: dict[str, str] = {}
        self.reg_ids: dict[str, str] = {}
        self.users: dict[str, Any] = {}
        self._sessions: dict[str, tuple[Any, datetime]] = {}

    # -- set-up ---------------------------------------------------------------------------------

    def prepare(self) -> None:
        from dotenv import load_dotenv

        os.chdir(ROOT)
        load_dotenv(ROOT / ".env")
        if DEMO_DB.resolve() == MAIN_DB.resolve():
            raise SystemExit("Refusing to touch the real database.")
        self._remove_old()
        url = "sqlite:///" + DEMO_DB.as_posix()
        os.environ["DATABASE_URL"] = url  # nothing in this run may reach any other database
        os.environ["CREDLENS_OCR_WORKER"] = "0"
        from src.config import load_config
        from src.db.models import create_tables, make_engine

        self.config = copy.deepcopy(load_config())
        for key in self.config["auth"]["rate_limit"]:
            if key != "window_minutes":
                self.config["auth"]["rate_limit"][key] = 1_000_000
        DEMO_DB.parent.mkdir(parents=True, exist_ok=True)
        create_tables(url)
        self.engine = make_engine(url)
        from src.api import auth
        from src.api.main import app
        from src.api.state import Services

        auth.BENCHMARK_REQUEST.set(
            False
        )  # direct calls here are a real company's, not the benchmark's
        self.app = app
        self.services = Services(config=self.config, engine=self.engine)
        app.state.services = self.services
        self.clock = Clock(self.config["organization"]["timezone"])
        self.undo = install_clock(self.clock)
        self.today = datetime.now(self.clock.tz).date()

    def _remove_old(self) -> None:
        """Delete the earlier demo database and the files it kept."""
        if DEMO_DB.exists():
            orgs = []
            old = sqlite3.connect(DEMO_DB)
            try:
                orgs = [r[0] for r in old.execute("select organization_id from organizations")]
            except sqlite3.Error:
                pass
            finally:
                old.close()  # Windows will not delete a file that is still open
            try:
                DEMO_DB.unlink()
            except PermissionError:
                raise SystemExit(
                    "The demonstration database is open in another program, most likely the API "
                    "started with `python tasks.py api --demo`. Stop it (Ctrl+C in its window), "
                    "then run `python tasks.py demo` again."
                ) from None
            for org in orgs:  # only after the database is gone: its files are no longer referenced
                shutil.rmtree(ROOT / "data" / "uploads" / org, ignore_errors=True)

    def finish_clock(self) -> None:
        for module, attr, old in self.undo:
            setattr(module, attr, old)
        self.clock.off()

    # -- who is acting --------------------------------------------------------------------------

    def api(self, person):
        """A signed-in client for this staff member, signed in again whenever the clock moved."""
        from fastapi.testclient import TestClient

        email = person.email
        cached = self._sessions.get(email)
        moment = self.clock.now()
        if cached and abs(moment - cached[1]) < timedelta(minutes=25):
            return cached[0]
        client = TestClient(self.app)
        ok(client.post("/auth/login", json={"identifier": email, "password": person.password}), 200)
        self._sessions[email] = (client, moment)
        if email not in self.users:
            from src.api.auth import CurrentUser

            me = client.get("/auth/me").json()
            self.users[email] = CurrentUser(
                user_id=me["user_id"],
                role=me["role"],
                organization_id=me["organization_id"],
                display_name=me["display_name"],
                is_owner=me["is_owner"],
            )
        return client

    def merchant_api(self, shop):
        from fastapi.testclient import TestClient

        key = f"merchant:{shop.key}"
        cached = self._sessions.get(key)
        moment = self.clock.now()
        if cached and abs(moment - cached[1]) < timedelta(minutes=25):
            return cached[0]
        client = TestClient(self.app)
        ok(
            client.post(
                "/auth/merchant-login",
                json={"merchant_id": "MR" + shop.portal, "owner_name": shop.owner},
            ),
            200,
        )
        self._sessions[key] = (client, moment)
        return client

    def user(self, person):
        if person.email not in self.users:
            self.api(person)
        return self.users[person.email]

    def desk_officer(self):
        return self.rng.choices(self.desk, weights=[5, 3, 2])[0]

    # -- the company and its people --------------------------------------------------------------

    def company(self) -> None:
        from fastapi.testclient import TestClient

        from src.accounts.bootstrap_platform_admins import bootstrap
        from src.demo import shopup_data as data

        self.data = data
        self.credit = [p for p in data.STAFF if p.role == "credit_officer"]
        self.desk = [p for p in data.STAFF if p.role == "records_officer"]
        start = self.today - timedelta(days=280)
        self.start = start
        from sqlalchemy.orm import Session

        self.clock.set(start - timedelta(days=3))
        env = {k: v for k, v in os.environ.items() if k.startswith("CREDLENS_PLATFORM_ADMIN_")}
        with Session(self.engine) as session:
            results = bootstrap(session, self.config, env)
            session.commit()
        self.admin_emails = [r.email for r in results if getattr(r, "email", None)]
        log(f"platform admins from .env: {len(self.admin_emails)}")

        anon = TestClient(self.app)
        owner = self.credit[0]
        c = data.COMPANY
        self.clock.set(start)
        body = {
            "full_name": owner.name,
            "email": owner.email,
            "mobile": owner.mobile,
            "department": owner.department,
            "password": owner.password,
            "confirm_password": owner.password,
            **c,
        }
        ok(anon.post("/auth/register/company", json=body), 201)
        log(f"company registered: {c['legal_name']}")
        boss = self.api(owner)
        self.org = self.users[owner.email].organization_id
        code_credit = ok(
            boss.post(
                "/org/invitations", json={"role": "credit_officer", "days": 60, "max_uses": 2}
            ),
            201,
        ).json()["code"]
        code_desk = ok(
            boss.post(
                "/org/invitations", json={"role": "records_officer", "days": 60, "max_uses": 3}
            ),
            201,
        ).json()["code"]
        for offset, person in enumerate(data.STAFF[1:], start=1):
            self.clock.set(start + timedelta(days=offset))
            ok(
                anon.post(
                    "/auth/register/join",
                    json={
                        "full_name": person.name,
                        "email": person.email,
                        "mobile": person.mobile,
                        "department": person.department,
                        "password": person.password,
                        "confirm_password": person.password,
                        "invitation_code": code_credit
                        if person.role == "credit_officer"
                        else code_desk,
                        "role": person.role,
                        "employee_id": person.employee_id,
                    },
                ),
                201,
            )
        log(
            f"team joined: {len(self.credit)} Credit Officers, {len(self.desk)} Records Desk officers"
        )
        # ShopUp's own range policy, written and approved by the owner
        self.clock.set(start + timedelta(days=12))
        boss = self.api(owner)
        policy = ok(
            boss.post(
                "/org/range-policies",
                json={
                    "parameters": data.POLICY,
                    "note": "ShopUp working-capital policy. Demonstration values, to be set by ShopUp's credit committee.",
                },
            ),
            201,
        ).json()
        ok(boss.post(f"/org/range-policies/{policy['policy_id']}/approve"), 200)
        log("range policy approved by the owner")

    # -- one shop: registration and consent -------------------------------------------------------

    def register_shop(self, shop) -> None:
        from fastapi.testclient import TestClient  # noqa: F401
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        from src.db import models as db
        from src.extraction.engine import FakeOcrEngine
        from src.extraction.service import process_job

        d0 = self.today - timedelta(days=shop.onboard_days_ago)
        creator, verifier = self.credit[shop.creator], self.credit[shop.verifier]
        self.clock.set(d0)
        c = self.api(creator)
        details = {
            "shop_name": shop.name,
            "owner_name": shop.owner,
            "owner_mobile": shop.mobile,
            "district": shop.district,
            "area": shop.area,
            "shop_type": shop.shop_type,
            "ownership_type": shop.ownership,
            "established_year": shop.established,
            "branches": shop.branches,
        }
        if shop.licence:
            details["trade_license_number"] = shop.licence
        reg = ok(c.post("/registrations", json=details), 201).json()
        rid, mid = reg["reg_id"], reg["merchant_id"]
        self.reg_ids[shop.key], self.shop_ids[shop.key] = rid, mid
        form = ok(c.get(f"/registrations/{rid}/consent.pdf"), 200).content
        self.clock.set(d0 + timedelta(days=1))
        c = self.api(creator)
        ok(
            c.post(
                f"/registrations/{rid}/signed",
                params={"name": SIGNED_NAME},
                content=form,
                headers={"Content-Type": "application/pdf"},
            ),
            200,
        )
        with Session(self.engine) as session:
            job = session.scalar(
                select(db.ExtractionJob).where(
                    db.ExtractionJob.registration_id == rid, db.ExtractionJob.status == "queued"
                )
            )
            process_job(session, self.config, FakeOcrEngine([[]]), job.job_id)
        with Session(self.engine) as session:  # the Merchant ID printed on the handover slip
            session.get(db.MerchantAccess, mid).portal_id = "MR" + shop.portal
            session.commit()
        if shop.registration_only:  # the ID is ready; the portal opens once consent is verified
            log(f"{shop.name}: signed form read, waiting for a second officer")
            return
        found = ok(c.get(f"/registrations/{rid}/extraction"), 200).json()["fields"]
        for field in found:
            if (
                field["key"] == "signer_name"
            ):  # the officer types the name written beside the signature
                ok(
                    c.patch(
                        f"/registrations/{rid}/fields/{field['field_id']}",
                        json={"value": shop.owner},
                    ),
                    200,
                )
        self.clock.set(d0 + timedelta(days=2))
        v = self.api(verifier)
        ok(
            v.post(
                f"/registrations/{rid}/verify",
                json={
                    "categories": ["purchases", "deliveries", "payments", "field_visits"],
                    "optional": ["questionnaire"] if shop.questionnaire else [],
                    "signer_name": shop.owner,
                    "signed_on": (d0 + timedelta(days=1)).isoformat(),
                    "signature_checked": True,
                    "reference_matches": True,
                },
            ),
            200,
        )
        if shop.questionnaire:
            self.clock.set(d0 + timedelta(days=3))
            c = self.api(creator)
            ok(c.post(f"/merchants/{mid}/questionnaire", json=shop.questionnaire), 200)
            with Session(self.engine) as session:
                session.get(db.Questionnaire, mid).answered_at = d0 + timedelta(days=3)
                session.commit()
        log(f"{shop.name}: registered, consent verified by {verifier.name}")

    # -- ShopUp's earlier loans -------------------------------------------------------------------

    def loans(self, shop) -> None:
        from sqlalchemy.orm import Session

        from src.db import models as db
        from src.intake import records

        if not shop.loans:
            return
        mid = self.shop_ids[shop.key]
        onboard = self.today - timedelta(days=shop.onboard_days_ago)
        enter = self.user(self.credit[1])
        for spec in shop.loans:
            issued, rows = self.data.instalment_schedule(spec, self.today)
            loan_id = f"LN-{uuid.uuid4().hex[:24]}"
            with Session(self.engine) as session:
                session.add(
                    db.Loan(
                        loan_id=loan_id,
                        merchant_id=mid,
                        issued_at=issued,
                        limit_bdt=float(spec.limit),
                        outcome_label=None,
                        label_observed_at=None,
                    )
                )
                session.commit()
            for due, paid, amount in rows:
                self.clock.set(
                    clamp(
                        max(paid or due, onboard + timedelta(days=3)),
                        onboard,
                        self.today - timedelta(days=1),
                    )
                )
                with Session(self.engine) as session:
                    records.record_repayment(
                        session,
                        self.config,
                        merchant_id=mid,
                        loan_id=loan_id,
                        due_date=due,
                        paid_date=paid,
                        amount_due_bdt=float(amount),
                        amount_paid_bdt=float(amount if paid else 0),
                        actor=enter,
                        protected_merchants=frozenset(),
                    )
            if all(paid for _due, paid, _amount in rows):  # fully repaid: the outcome is known
                with Session(self.engine) as session:
                    loan = session.get(db.Loan, loan_id)
                    loan.outcome_label = 1  # every instalment within 30 days of its due date
                    loan.label_observed_at = max(paid for _due, paid, _amount in rows)
                    session.commit()
        log(f"{shop.name}: {len(shop.loans)} earlier ShopUp loan(s) with their instalments")

    # -- receipts -----------------------------------------------------------------------------------

    def _parsed(self, plan, corrupt: bool):
        from src.receipts import parse
        from src.receipts.parse import Cell, ParsedLine

        rng = self.rng

        def c() -> float:
            return round(rng.uniform(0.9, 0.995), 3)

        parsed = parse.ParsedReceipt(kind=plan.kind)
        parsed.supplier = Cell(plan.supplier or None, c() if plan.supplier else None)
        parsed.receipt_date = Cell(plan.day, c())
        parsed.memo_no = Cell(plan.memo_no, c())
        parsed.stated_total = Cell(
            float(plan.total) if plan.total else None, c() if plan.total else None
        )
        for i, ln in enumerate(plan.lines, start=1):
            row = ParsedLine(row_no=i)
            if plan.kind == "purchase":
                row.item = Cell(ln["item"], c())
                row.quantity = Cell(float(ln["quantity"]), c())
                row.unit = Cell(ln["unit"], c())
                row.unit_price = Cell(float(ln["unit_price"]), c())
                row.amount = Cell(float(ln["amount_bdt"]), c())
            else:
                row.line_date = Cell(date.fromisoformat(ln["line_date"]), c())
                row.outcome = Cell(ln["outcome"], c())
                row.reference = Cell(ln["reference"], c())
                row.amount = Cell(float(ln["amount_bdt"]) if ln.get("amount_bdt") else None, c())
                if ln.get("due_date"):
                    row.due_date = Cell(date.fromisoformat(ln["due_date"]), c())
            parsed.lines.append(row)
        if corrupt and plan.kind == "purchase" and plan.lines:
            row = parsed.lines[rng.randrange(len(plan.lines))]
            good = int(row.amount.value)
            digits = str(good)
            wrong = (
                int(digits[:-1] + str((int(digits[-1]) + rng.randint(1, 8)) % 10))
                if good >= 100
                else good * 10
            )
            row.amount = Cell(float(wrong), 0.58)
        return parsed

    def _rows_for(self, plan) -> list[dict]:
        return [
            {k: ln[k] for k in ("item", "quantity", "unit", "unit_price", "amount_bdt")}
            if plan.kind == "purchase"
            else {
                "line_date": ln["line_date"],
                "outcome": ln["outcome"],
                "reference": ln["reference"],
                "amount_bdt": ln.get("amount_bdt"),
                "due_date": ln.get("due_date"),
            }
            for ln in plan.lines
        ]

    def publish_plan(self, shop, mid: str, plan, stamp: date, officer, picture: bytes) -> None:
        """One receipt, the way the Records Desk handles it: file, reading, check, publish."""
        from sqlalchemy.orm import Session

        from src.db import models as db
        from src.onboarding import registrations as docs
        from src.receipts import parse, service

        user = self.user(officer)
        low = float(self.config["ocr"]["low_confidence_below"])
        corrupt = plan.kind == "purchase" and self.rng.random() < 0.09
        self.clock.set(stamp)
        with Session(self.engine) as session:
            document = docs.store_document(
                session,
                self.config,
                user,
                self.org,
                picture,
                kind="receipt",
                original_name=f"{plan.kind}-{plan.day.isoformat()}-{plan.memo_no}.jpg",
                merchant_id=mid,
                registration_id=None,
            )
            receipt = service.create_receipt(session, user, self.org, mid, plan.kind, document)
            job = session.get(db.ExtractionJob, receipt.job_id)
            job.status, job.engine, job.engine_version, job.pages = "done", "easyocr", "1.7", 1
            job.started_at = job.finished_at = self.clock.now()
            parsed = self._parsed(plan, corrupt)
            parse.check(parsed, stamp, low)
            service.apply_parsed(session, receipt, parsed)
            session.flush()
            lines = service.lines_of(session, receipt.receipt_id)
            rows = [{"line_id": ln.line_id, **row} for ln, row in zip(lines, self._rows_for(plan))]
            service.save_edits(session, user, receipt, {}, rows, stamp, low)
            service.publish(session, self.config, user, receipt, frozenset(), True)
            receipt_id = receipt.receipt_id
            session.commit()
        if self.rng.random() < shop.confirm_share:
            self.clock.set(clamp(stamp + timedelta(days=self.rng.randint(1, 9)), stamp, self.today))
            with Session(self.engine) as session:
                service.confirm(session, session.get(db.Receipt, receipt_id))
                session.commit()

    def receipts(self, shop) -> None:
        from src.demo import pictures

        if shop.history_days <= 0:
            return
        mid = self.shop_ids[shop.key]
        onboard = self.today - timedelta(days=shop.onboard_days_ago)
        rng = self.rng
        plans = self.data.purchase_receipts(shop, self.today, rng)
        self.data.with_language(shop, plans, rng)
        slips = self.data.delivery_slips(shop, self.today, rng)
        every = sorted(plans + slips, key=lambda p: p.day)
        early = [p for p in every if p.day < onboard + timedelta(days=3)]
        started = wallclock.time()
        for plan in every:
            if plan.day < onboard + timedelta(days=3):  # older paper, uploaded in the first weeks
                stamp = onboard + timedelta(
                    days=3 + int(18 * early.index(plan) / max(1, len(early)))
                )
            else:
                stamp = plan.day + timedelta(days=rng.randint(1, 3))
            stamp = clamp(stamp, onboard + timedelta(days=3), self.today - timedelta(days=1))
            if plan.kind == "purchase":
                image = pictures.memo_image(plan, shop.name, rng)
                picture = pictures.photograph(image, rng, "photo" if rng.random() < 0.6 else "scan")
            else:
                picture = pictures.photograph(
                    pictures.slip_image(plan, shop.name, rng), rng, "scan"
                )
            self.publish_plan(shop, mid, plan, stamp, self.desk_officer(), picture)
        log(
            f"{shop.name}: {len(plans)} purchase memos and {len(slips)} parcel reports published "
            f"({wallclock.time() - started:.0f}s)"
        )

    # -- receipts still waiting at the Records Desk ---------------------------------------------------

    def pending(self, shop) -> None:
        from sqlalchemy.orm import Session

        from src.db import models as db
        from src.demo import pictures
        from src.extraction.engine import FakeOcrEngine, get_engine
        from src.extraction.service import process_job

        if not shop.pending:
            return
        mid = self.shop_ids[shop.key]
        uploader = self.desk[1] if shop.key == "bogura" else self.desk[2]
        engine = None
        for i in range(shop.pending):
            day = self.today - timedelta(days=shop.pending_day + (1 if i % 2 else 0))
            made = self.data.make_purchase(
                shop,
                day - timedelta(days=1),
                shop.month_base / 4.3 * 0.9,
                self.rng,
                str(5000 + 31 * i + len(shop.name)),
            )
            image = pictures.memo_image(made, shop.name, self.rng)
            jpeg = pictures.photograph(image, self.rng, "scan" if shop.key == "bogura" else "photo")
            self.clock.set(day)
            c = self.api(uploader)
            sent = ok(
                c.post(
                    f"/merchants/{mid}/receipts",
                    params={"kind": "purchase", "name": f"memo-{i + 1}.jpg"},
                    content=jpeg,
                    headers={"Content-Type": "application/octet-stream"},
                ),
                201,
            ).json()
            with Session(self.engine) as session:
                receipt = session.get(db.Receipt, sent["receipt_id"])
                if self.fast:
                    reader = FakeOcrEngine(
                        [fake_boxes(made, doubtful=(shop.key == "gazipur" and i == 0))]
                    )
                else:
                    engine = engine or get_engine(self.config)
                    reader = engine
                process_job(session, self.config, reader, receipt.job_id)
        log(f"{shop.name}: {shop.pending} receipt(s) read and waiting for the Records Desk")

    # -- visits and applications --------------------------------------------------------------------

    def activity(self, shop) -> None:
        mid = self.shop_ids[shop.key]
        creator = self.credit[shop.creator]
        notes = {
            "grocery": "Shop open and trading. Shelves well stocked; the owner showed this month's purchase memos.",
            "pharmacy": "Pharmacy open, licence on display. Stock register and purchase memos were in order.",
            "electronics": "Busy shop. Owner explained the slow weeks; the earlier loan was discussed.",
            "apparel": "Showroom open. Stock was lighter than in the festival season, as expected.",
            "other": "Shop open and trading. Owner cooperative and keeps purchase memos in a file.",
        }
        if shop.visit_days_ago is not None:
            d = self.today - timedelta(days=shop.visit_days_ago)
            self.clock.set(d)
            ok(
                self.api(creator).post(
                    f"/merchants/{mid}/visits",
                    json={
                        "business_date": d.isoformat(),
                        "outcome": "shop_open_trading",
                        "note": notes.get(shop.shop_type, notes["other"]),
                    },
                ),
                201,
            )
        if shop.application:
            amount, purpose, days_ago, via = shop.application
            d = self.today - timedelta(days=days_ago)
            self.clock.set(d)
            note = self.data.PURPOSE_NOTES.get(purpose) or None
            if via == "portal":
                ok(
                    self.merchant_api(shop).post(
                        "/portal/application",
                        json={
                            "requested_amount_bdt": float(amount),
                            "purpose": purpose,
                            "purpose_note": note,
                        },
                    ),
                    201,
                )
            else:
                ok(
                    self.api(creator).post(
                        f"/merchants/{mid}/application",
                        json={
                            "requested_amount_bdt": float(amount),
                            "purpose": purpose,
                            "purpose_note": note,
                            "business_date": d.isoformat(),
                        },
                    ),
                    201,
                )
            log(f"{shop.name}: application of {amount:,} BDT ({via})")

    # -- merchant reports -------------------------------------------------------------------------------

    def dispute(self, shop, days_ago: int, resolved: bool) -> None:
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        from src.db import models as db
        from src.demo import pictures
        from src.demo.shopup_data import ReceiptPlan

        mid = self.shop_ids[shop.key]
        day = self.today - timedelta(days=days_ago)
        before = datetime.combine(day, time(0, 0))
        with Session(self.engine) as session:
            receipt = session.scalars(
                select(db.Receipt)
                .where(
                    db.Receipt.merchant_id == mid,
                    db.Receipt.kind == "purchase",
                    db.Receipt.status == "published",
                    db.Receipt.published_at < before,
                )
                .order_by(db.Receipt.published_at.desc())
            ).first()
            lines = session.scalars(
                select(db.ReceiptLine)
                .where(db.ReceiptLine.receipt_id == receipt.receipt_id)
                .order_by(db.ReceiptLine.row_no)
            ).all()
            picked = max(lines, key=lambda ln: ln.amount_bdt or 0)
            rate = int(picked.unit_price or 0)
            claimed_rate = int(round(rate * 0.92))
            claimed = float(int(picked.quantity) * claimed_rate)
            line_id, recorded, item = picked.line_id, float(picked.amount_bdt), picked.item
            made = ReceiptPlan(
                "purchase",
                receipt.receipt_date,
                receipt.supplier or "",
                receipt.memo_no or "",
                "bn"
                if any(ord(ch) > 127 for ch in "".join(ln.item or "" for ln in lines))
                else "en",
                [
                    dict(
                        item=ln.item,
                        quantity=ln.quantity,
                        unit=ln.unit or "",
                        unit_price=claimed_rate
                        if ln.line_id == line_id
                        else int(ln.unit_price or 0),
                        amount_bdt=int(claimed if ln.line_id == line_id else (ln.amount_bdt or 0)),
                    )
                    for ln in lines
                ],
                0,
            )
            made.total = sum(ln["amount_bdt"] for ln in made.lines)
        proof = pictures.photograph(
            pictures.memo_image(made, shop.name, self.rng), self.rng, "photo"
        )
        self.clock.set(day)
        m = self.merchant_api(shop)
        doc = ok(
            m.post(
                "/portal/proof",
                params={"name": "my-copy-of-the-memo.jpg"},
                content=proof,
                headers={"Content-Type": "application/octet-stream"},
            ),
            201,
        ).json()["document_id"]
        report = ok(
            m.post(
                f"/portal/lines/{line_id}/report",
                json={
                    "note": f"The rate on my copy of this memo is {claimed_rate:,} for {item}, not {rate:,}. "
                    "I have attached a photo of my copy.",
                    "claimed_amount_bdt": claimed,
                    "proof_document_id": doc,
                },
            ),
            201,
        ).json()
        if resolved:
            self.clock.set(day + timedelta(days=2))
            desk = self.api(self.desk[0])
            ok(
                desk.post(
                    f"/merchant-reports/{report['flag_id']}/resolve",
                    json={
                        "accept": True,
                        "amount_bdt": claimed,
                        "note": "We compared your copy with the supplier's carbon copy. Your rate is right; "
                        "the line has been corrected.",
                    },
                ),
                200,
            )
        log(
            f"{shop.name}: merchant report on {item} ({'answered' if resolved else 'open'}): "
            f"recorded {recorded:,.0f}, merchant says {claimed:,.0f}"
        )

    # -- scores, decisions ----------------------------------------------------------------------------------

    def build_scorer(self) -> None:
        """The visit and application endpoints need the model loaded (they report on the
        assessment). Built once, before those steps; the records are read into it at the end."""
        from src.model.scoring import Scorer

        log("building the scorer (about half a minute) ...")
        self.services.scorer = Scorer(self.config)

    def score_and_decide(self) -> None:
        from sqlalchemy.orm import Session

        from src.api.imported import refresh_real

        self.clock.off()
        with Session(self.engine) as session:
            refresh_real(self.services, session)
        deciders = {"sylhet": self.credit[0], "bogura": self.credit[1]}
        for shop in self.data.SHOPS:
            if not shop.decision or shop.key not in deciders:
                continue
            _amount, _purpose, days_ago, _via = shop.application
            self.clock.set(self.today - timedelta(days=days_ago - 2), dates=False)
            officer = deciders[shop.key]
            action, reason = shop.decision
            ok(
                self.api(officer).post(
                    f"/merchants/{self.shop_ids[shop.key]}/decision",
                    json={"officer_action": action, "reason_text": reason},
                ),
                201,
            )
            log(f"{shop.name}: decision recorded by {officer.name} ({action})")
        self.clock.off()
        boss = self.api(self.credit[0])
        for shop in self.data.SHOPS:
            if shop.application:
                made = boss.post(f"/merchants/{self.shop_ids[shop.key]}/assessments")
                if made.status_code != 201:
                    log(f"{shop.name}: no assessment ({made.status_code} {made.text[:120]})")

    # -- tidy up and report ------------------------------------------------------------------------------

    def finish(self) -> None:
        from sqlalchemy import delete, select
        from sqlalchemy.orm import Session

        from src.db import models as db

        self.clock.off()
        with Session(self.engine) as session:
            old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=5)
            for note in session.scalars(
                select(db.Notification).where(
                    db.Notification.created_at < old, db.Notification.read_at.is_(None)
                )
            ):  # older messages were read at the time; only the recent ones wait on each bell
                note.read_at = note.created_at + timedelta(days=1)
            session.execute(delete(db.AuthSession))
            session.execute(delete(db.AuthAttempt))
            self.collect_results(session)
            session.commit()

    def collect_results(self, session) -> None:
        """What the model said about each shop and how many receipts it has (for the guide)."""
        import json

        from sqlalchemy import select

        from src.db import models as db

        for shop in self.data.SHOPS:
            mid = self.shop_ids[shop.key]
            row = session.scalar(
                select(db.Assessment).where(
                    db.Assessment.merchant_id == mid, db.Assessment.status == "current"
                )
            )
            receipts = session.scalars(
                select(db.Receipt).where(db.Receipt.merchant_id == mid)
            ).all()
            self.results[shop.key] = {
                "assessment": row,
                "published": sum(1 for r in receipts if r.status == "published"),
                "waiting": sum(1 for r in receipts if r.status in ("extracted", "checked")),
            }
            if row is not None:
                self.results[shop.key]["plain"] = json.loads(row.plain or "{}")
                session.expunge(row)

    def load_existing(self) -> None:
        """For --guide-only: read the finished demonstration database instead of building one."""
        from dotenv import load_dotenv
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        from src.db import models as db
        from src.demo import shopup_data as data

        load_dotenv(ROOT / ".env")
        if not DEMO_DB.exists():
            raise SystemExit("No demonstration database yet. Build it first: python tasks.py demo")
        self.data = data
        self.admin_emails = [
            os.environ[key].strip().lower()
            for key in sorted(os.environ)
            if key.startswith("CREDLENS_PLATFORM_ADMIN_")
            and key.endswith("_EMAIL")
            and os.environ[key].strip()
        ]
        engine = db.make_engine("sqlite:///" + DEMO_DB.as_posix())
        with Session(engine) as session:
            for shop in data.SHOPS:
                mid = session.scalar(
                    select(db.MerchantProfile.merchant_id).where(
                        db.MerchantProfile.shop_name == shop.name
                    )
                )
                if mid is None:
                    raise SystemExit(
                        f"{shop.name} is not in the demonstration database: rebuild it with "
                        "python tasks.py demo"
                    )
                self.shop_ids[shop.key] = mid
            self.collect_results(session)
        engine.dispose()


# --- the written guide -----------------------------------------------------------------------------------


def money(value: float | None) -> str:
    return "-" if value is None else f"{value:,.0f}"


def story(shop) -> str:
    return {
        "bhai": "The hero shop: nine steady months, growing purchases, two earlier ShopUp loans repaid on time, parcels, a questionnaire, a field visit and an open application from the owner's own portal. Nobody has decided yet.",
        "nirjhor": "A good pharmacy with a report open: the owner says one rate on a memo is wrong and attached a photo of their own copy. The line is out of the score until the Records Desk answers.",
        "rahman": "Earlier loans paid late, uneven weeks, returned parcels, and stock bought from many different wholesalers. One report was already answered and corrected. Expect a closer look and a lower range.",
        "sylhet": "Seasonal: purchases jump before Eid and come from many wholesalers. An officer already answered the application with 'needs more information'.",
        "khulna": "Seven calm months, first-time borrower, a few parcels, small amounts: a modest range.",
        "rajshahi": "Only about seven weeks of receipts. The summary says there are not enough receipts yet and lists what to add (the thin-history story).",
        "bogura": "An earlier application was decided (accepted) with a written reason. Two new receipts are waiting at the Records Desk.",
        "gazipur": "Registered twelve days ago. Three receipts are read and waiting; one has a cell the reader was unsure of. It has no application yet, so its summary says there is nothing to score.",
        "cumilla": "Registration in progress: the signed form is uploaded and read, waiting for a second officer to verify it.",
    }[shop.key]


def write_guide(seed: Seed) -> None:
    data = seed.data
    lines = [
        "# ShopUp demonstration: logins, stories and a suggested order",
        "",
        "Everything here is invented for the video: ShopUp's company details, its staff, the nine shops "
        "and every number. None of it is real data about ShopUp or anyone else. `shopup.com` belongs to a "
        "real company: the addresses below exist only inside this local demo database and no email is ever "
        "sent. The consent form still carries its draft watermark (the text has not had legal review).",
        "",
        "Rebuild it any time (about 5 to 10 minutes; `--fast` skips the slow receipt reader). Stop the demo API first: Windows will not delete an open database.",
        "",
        "```bash",
        "python tasks.py demo",
        "python tasks.py api --demo     # API on :8000 using data/credlens_demo.db",
        "python tasks.py app            # dashboard on :5173",
        "```",
        "",
        "Rebuild just before recording: the histories end a few days before the day you build, so scores "
        "and dates stay fresh. The real `data/credlens.db` is never touched.",
        "",
        "## Staff sign-in (card: Company, or Records Desk)",
        "",
        "| Person | Role | Email | Password | Card |",
        "|---|---|---|---|---|",
    ]
    for p in data.STAFF:
        role = "Owner, Head of Credit" if p.owner else p.title
        card = "I am a company" if p.role == "credit_officer" else "I am on the Records Desk"
        lines.append(f"| {p.name} | {role} | `{p.email}` | `{p.password}` | {card} |")
    lines += [
        "",
        "Platform administrators (card: I am a company) use the emails and passwords in your private "
        "`.env`: " + (", ".join(f"`{e}`" for e in seed.admin_emails) or "none are set") + ".",
        "",
        "## Merchant sign-in (card: I am a merchant)",
        "",
        "| Shop | Owner (type this name) | Merchant ID | Town |",
        "|---|---|---|---|",
    ]
    for s in data.SHOPS:
        shown = "MR-" + s.portal[:4] + "-" + s.portal[4:]
        note = "" if not s.registration_only else " (portal opens after verification)"
        lines.append(f"| {s.name} | {s.owner} | `{shown}`{note} | {s.area}, {s.district} |")
    lines += [
        "",
        "The owner's name may be typed in any case, and a first name alone also works. Merchant IDs in "
        "the product are random; these are made easy to type for the video.",
        "",
        "## The nine shops and what the model said when this guide was written",
        "",
        "| Shop | What the officer sees | Credit score (confidence, out of 100) | Suggested range (BDT) | Receipts published | Waiting |",
        "|---|---|---|---|---|---|",
    ]
    for s in data.SHOPS:
        r = seed.results[s.key]
        a = r["assessment"]
        plain = r.get("plain", {})
        outlook = {
            "strong": "Looks reliable",
            "moderate": "Needs a closer look",
            "not_enough": "Not enough receipts yet",
        }.get(
            plain.get("outlook"), "No application yet" if a is None else plain.get("outlook", "-")
        )
        # A shop with too few checked receipts shows no score on screen (a number would be a guess).
        scored = a is not None and a.band != "Needs more info"
        score = str(a.score) if scored else "no score yet"
        rng = (
            "-"
            if a is None or a.range_min_bdt is None
            else f"{money(a.range_min_bdt)} to {money(a.range_max_bdt)}"
        )
        lines.append(
            f"| {s.name} | {outlook} | {score} | {rng} | {r['published']} | {r['waiting']} |"
        )
    lines += ["", "### Stories", ""]
    for s in data.SHOPS:
        lines.append(f"- **{s.name}** ({s.owner}): {story(s)}")
    lines += [
        "",
        "## Suggested order for the video",
        "",
        "1. Landing page, then **Sign in**: show the three cards (company, Records Desk, merchant).",
        "2. **Jawad Hasan** (Company card): Overview with real numbers, Merchants list, Team and invitations.",
        "3. Open **Bhai Bhai General Store**: the credit score out of 100, the suggested loan range, what looks good "
        "and what to watch, then the decision buttons right under it; open 'Receipts, loans and consent' for the "
        "records and where each came from (names, not ids).",
        "4. Open **Rajshahi Agro and Grocery**: 'Not enough receipts yet' and what would help. Compare with Rahman and Sylhet.",
        "5. **Nusrat Jahan** (Records Desk card): receipts queue, open one of Gazipur's receipts (picture beside the "
        "table, the highlighted cell, the 'lines add up' check), correct and publish; then Merchant reports.",
        "6. **Abdul Karim** (Merchant card, Bhai Bhai): My records as tables, 'Looks right', Apply for a loan (already "
        "applied: show the status).",
        "7. **Farhana Yasmin** (Nirjhor Pharmacy): My reports shows the open report with the photo; back as Nusrat, "
        "answer it; back on Jawad's screen the line returns to the score.",
        "8. **Sadia Rahman**: verify Cumilla's consent form (the second officer must differ from the one who registered it).",
        "9. As Jawad, record a decision on Bhai Bhai's application (a person decides; nothing is automatic).",
        "10. A platform administrator: the Companies page with ShopUp.",
        "",
        "## What this demonstration is and is not",
        "",
        "- It shows what the product does with a believable set of records. It does not show how accurate the "
        "model is on real shops: the model learned from practice data and the credit summary says so in one line.",
        "- Receipts, wholesalers, parcels and amounts are generated. The pictures are drawn, not photographed.",
        "- The practice model leans hardest on how loyal a shop is to its suppliers (the share of repeat purchases "
        "from the same wholesalers). Shops that buy from many different wholesalers, like Rahman and Sylhet here, "
        "score lower for that reason alone; the credit summary lists it among the reasons.",
        "- Ranges follow ShopUp's demonstration policy (multiples of average monthly verified purchases, "
        "rounded and capped at the request); a real lender sets its own.",
    ]
    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_logins(seed: Seed) -> None:
    data = seed.data
    print("\nSIGN-IN DETAILS (also in docs/product/DEMO_SHOPUP.md)\n")
    for p in data.STAFF:
        print(
            f"  {p.name:<16} {p.email:<22} {p.password:<20} {'Company card' if p.role == 'credit_officer' else 'Records Desk card'}"
        )
    print()
    for s in data.SHOPS:
        shown = "MR-" + s.portal[:4] + "-" + s.portal[4:]
        print(f"  {s.name:<32} {shown}   owner: {s.owner}")
    print("\n  Platform admins: the emails and passwords in your .env")
    print(
        "\nStart it with: python tasks.py api --demo   (and in another window: python tasks.py app)"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the ShopUp demonstration database.")
    parser.add_argument(
        "--fast", action="store_true", help="skip the real receipt reader (scripted reading)"
    )
    parser.add_argument("--seed", type=int, default=5, help="random seed (same seed, same story)")
    parser.add_argument(
        "--guide-only",
        action="store_true",
        help="write docs/product/DEMO_SHOPUP.md from the existing demonstration database; build nothing",
    )
    args = parser.parse_args(argv)
    started = wallclock.time()
    seed = Seed(args.fast, args.seed)
    if args.guide_only:
        seed.load_existing()
        write_guide(seed)
        print(f"Wrote {DOC.relative_to(ROOT)} from the existing demonstration database.")
        return 0
    print("Building the ShopUp demonstration database (data/credlens_demo.db) ...")
    seed.prepare()
    try:
        seed.company()
        shops = sorted(seed.data.SHOPS, key=lambda s: -s.onboard_days_ago)
        for shop in shops:
            seed.register_shop(shop)
        for shop in shops:
            seed.loans(shop)
        for shop in shops:
            seed.receipts(shop)
        for shop in shops:
            seed.pending(shop)
        seed.build_scorer()
        for shop in shops:
            seed.activity(shop)
        by_key = {s.key: s for s in seed.data.SHOPS}
        seed.dispute(by_key["rahman"], 35, resolved=True)
        seed.dispute(by_key["nirjhor"], 2, resolved=False)
        seed.score_and_decide()
        seed.finish()
    finally:
        seed.finish_clock()
    write_guide(seed)
    print_logins(seed)
    print(f"\nDone in {wallclock.time() - started:.0f} seconds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
