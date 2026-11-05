"""The ShopUp demonstration roster: logins that work and stories that have what they need.

Owner role: D (full-stack).
Implements: the demonstration database for the project video (src/demo/).

These tests read the cast only (src/demo/shopup_data.py); they do not build the database, which
takes minutes (`python tasks.py demo`). They catch the mistakes that would waste a recording:
two people with one email, a password the product would refuse, a Merchant ID that clashes, or a
story (a decision, a report, a pending receipt) with nothing behind it.
"""

from __future__ import annotations

import random
import re
from collections import Counter
from datetime import date

import pytest

from src.accounts.service import check_password_rules, normalise_identifier
from src.config import load_config
from src.demo import shopup_data as data

TODAY = date(2026, 11, 6)


def test_people_are_distinct_and_their_passwords_pass_the_products_own_rules():
    config = load_config()
    for field in ("email", "employee_id", "mobile", "name"):
        counts = Counter(getattr(p, field) for p in data.STAFF)
        assert max(counts.values()) == 1, field
    assert sum(1 for p in data.STAFF if p.owner) == 1 and data.STAFF[0].owner
    for person in data.STAFF:
        assert person.email.endswith("@" + data.DOMAIN) and person.email == person.email.lower()
        assert normalise_identifier(person.email)[0] == person.email
        assert normalise_identifier(person.mobile)[1]
        check_password_rules(config, person.password, email=person.email, names=(person.name,))
    roles = Counter(p.role for p in data.STAFF)
    assert roles == {"credit_officer": 3, "records_officer": 3}


def test_the_company_has_what_registration_asks_for():
    for key in (
        "legal_name",
        "registration_number",
        "org_type",
        "address",
        "official_email",
        "country",
    ):
        assert data.COMPANY[key]
    assert data.COMPANY["org_type"] in {
        "bank",
        "nbfi",
        "mfi",
        "cooperative",
        "fintech_lender",
        "distributor_lender",
        "other",
    }


def test_shops_have_unique_names_owners_mobiles_and_merchant_ids():
    for field in ("name", "mobile", "portal"):
        counts = Counter(getattr(s, field) for s in data.SHOPS)
        assert max(counts.values()) == 1, field
    assert len(data.SHOPS) == 9
    for shop in data.SHOPS:
        assert re.fullmatch(r"[A-Z0-9]{8}", shop.portal), shop.name
        assert normalise_identifier(shop.mobile)[1], shop.name
        assert shop.creator != shop.verifier or shop.registration_only
        assert 0 <= shop.creator < 3 and 0 <= shop.verifier < 3
        assert shop.catalog in data.CATALOG and len(data.CATALOG[shop.catalog]) >= 5
        assert shop.suppliers


def test_every_story_has_the_evidence_it_needs():
    for shop in data.SHOPS:
        if shop.registration_only:  # waiting to be verified: nothing else can exist yet
            assert not (shop.history_days or shop.loans or shop.application or shop.pending), (
                shop.name
            )
            continue
        assert shop.onboard_days_ago >= 10, shop.name
        if shop.application:
            amount, purpose, days_ago, via = shop.application
            assert via in ("portal", "officer") and purpose in data.PURPOSE_NOTES and amount > 0
            assert days_ago < shop.onboard_days_ago - 2, shop.name  # consent was checked before
            assert all(spec.issued_days_ago > days_ago for spec in shop.loans), shop.name
        if shop.decision:
            assert shop.application and shop.decision[0] in ("accept", "needs_more_info")
            assert len(shop.decision[1]) >= 20
        if shop.dispute:
            assert shop.dispute in ("open", "resolved") and shop.history_days >= 60
        if shop.pending:
            assert shop.history_days > 0 and shop.pending <= 3
        if shop.visit_days_ago is not None:
            assert shop.visit_days_ago < shop.onboard_days_ago, shop.name
        for spec in shop.loans:
            assert (
                len(spec.delays) == spec.instalments
                and spec.issued_days_ago < shop.onboard_days_ago + 120
            )


@pytest.mark.parametrize("shop", data.SHOPS, ids=[s.key for s in data.SHOPS])
def test_generated_history_is_plausible(shop):
    rng = random.Random(5)
    plans = data.purchase_receipts(shop, TODAY, rng)
    slips = data.delivery_slips(shop, TODAY, rng)
    if shop.history_days <= 0:
        assert not plans and not slips
        return
    assert plans, shop.name
    for slip in slips:  # a parcel report is dated before today and never mentions a later day
        assert slip.day <= TODAY.fromordinal(TODAY.toordinal() - 3)
        assert all(ln["line_date"] <= slip.day.isoformat() for ln in slip.lines)
        assert all(ln.get("due_date", ln["line_date"]) <= slip.day.isoformat() for ln in slip.lines)
    assert all(p.day < TODAY and p.total == sum(ln["amount_bdt"] for ln in p.lines) for p in plans)
    assert all(
        ln["amount_bdt"] == ln["quantity"] * ln["unit_price"] for p in plans for ln in p.lines
    )
    assert len({(p.day, p.total) for p in plans}) == len(plans)
    assert min(p.day for p in plans) >= TODAY.fromordinal(TODAY.toordinal() - shop.history_days - 7)
    assert bool(slips) == bool(shop.parcels) or shop.history_days < 30
    expected = {
        "bhai": 30,
        "nirjhor": 25,
        "rahman": 15,
        "sylhet": 12,
        "khulna": 15,
        "bogura": 15,
        "gazipur": 3,
    }
    assert len(plans) >= expected.get(shop.key, 2), (shop.key, len(plans))


def test_the_thin_history_shop_is_thin_and_the_long_ones_are_long():
    by_key = {s.key: s for s in data.SHOPS}
    assert by_key["rajshahi"].history_days < 60 and not by_key["rajshahi"].loans
    assert by_key["gazipur"].history_days <= 30
    assert by_key["bhai"].history_days >= 270 and len(by_key["bhai"].loans) == 2
    assert by_key["rahman"].loans and max(max(s.delays) for s in by_key["rahman"].loans) > 10


def test_every_earlier_loan_was_repaid_within_the_labelling_limit():
    """The seed records these loans as repaid in time (label 1): that is only true while no
    instalment is more than the model's own limit late."""
    limit = load_config()["labels"]["good_if_days_late_at_most"]
    for shop in data.SHOPS:
        for spec in shop.loans:
            assert max(spec.delays) <= limit, shop.name
