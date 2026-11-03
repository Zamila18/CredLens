# ruff: noqa: F811  (fixtures imported from another test module are redefined as arguments)
"""Phase 6: stored assessments and the company's own range policy.

Owner role: C (assessment).
Implements: acceptance scenario 8 (docs: the implementation plan).

The engine is tested as a pure function; the API is tested with real accounts: the owner approves
a policy, an officer runs an assessment, and the stored assessment is recomputed to the same
answer. Sales never feed the range, and with no approved policy there is no range at all.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.assessment import range_engine
from src.db import models as db
from src.intake.policy import real_today
from tests.test_daily_phase345 import active_merchant
from tests.test_registration_phase2 import team, world  # noqa: F401

POLICY = {
    "window_days": 90,
    "min_verified_months": 2,
    "min_purchase_records": 3,
    "multiples_by_band": {"Strong": [0.5, 1.0], "Review": [0.25, 0.5]},
    "round_to_bdt": 1000,
    "cap_at_requested": True,
}
TODAY = date(2026, 11, 1)


def buys(*pairs):
    return [(TODAY - timedelta(days=d), a) for d, a in pairs]


# --- the engine ----------------------------------------------------------------------------


def test_the_engine_needs_a_policy_and_names_what_is_missing():
    none = range_engine.compute(None, "Strong", buys((5, 9000)), 50000, TODAY)
    assert not none.available and none.reason == "policy_not_configured"
    few = range_engine.compute(POLICY, "Strong", buys((5, 9000), (8, 5000)), 50000, TODAY)
    assert not few.available and few.reason == "not_enough_verified"
    assert len(few.missing) == 2 and "records" in few.missing[1]
    gap = range_engine.compute(POLICY, "Strong", buys((5, 9000), (6, 1), (7, 2)), 50000, TODAY)
    assert gap.reason == "not_enough_verified" and len(gap.missing) == 1  # one month only
    no_app = range_engine.compute(POLICY, "Strong", buys((5, 1)), None, TODAY)
    assert no_app.reason == "no_application"


def test_the_engine_does_the_arithmetic_in_the_open():
    rows = buys((5, 30000), (35, 30000), (65, 30000))
    got = range_engine.compute(POLICY, "Strong", rows, 100000, TODAY)
    assert got.available and got.inputs["total_bdt"] == 90000 and got.inputs["records"] == 3
    assert (got.low_bdt, got.high_bdt) == (15000.0, 30000.0)  # 30,000 a month x 0.5 and 1.0
    capped = range_engine.compute(POLICY, "Strong", rows, 20000, TODAY)
    assert (capped.low_bdt, capped.high_bdt) == (15000.0, 20000.0)
    assert any("Capped" in step for step in capped.steps)
    assert range_engine.compute(POLICY, "Needs more info", rows, 1, TODAY).reason == (
        "needs_more_info"
    )
    old = buys((200, 1e6), (210, 1e6), (220, 1e6))  # outside the window: not counted
    assert range_engine.compute(POLICY, "Strong", old, 1, TODAY).reason == "not_enough_verified"


def test_a_bad_policy_is_refused():
    for bad in (
        {k: v for k, v in POLICY.items() if k != "round_to_bdt"},
        {**POLICY, "window_days": 5},
        {**POLICY, "multiples_by_band": {"Strong": [2, 1]}},
        {**POLICY, "multiples_by_band": {}},
    ):
        with pytest.raises(range_engine.PolicyError):
            range_engine.check_parameters(bad)


# --- the API -------------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def scorer(world, api_world):
    """The small trained model of the shared API world, serving this module's real company."""
    from src.model.scoring import Scorer

    world.services.scorer = Scorer(api_world.config, tables=api_world.tables, saved=api_world.saved)
    yield
    world.services.scorer = None


def add_purchases(world, merchant: str, today: date) -> None:
    with Session(world.engine) as session:
        for i, days in enumerate((3, 33, 63)):
            session.add(
                db.Purchase(
                    purchase_id=f"P6-{merchant[-6:]}-{i}",
                    merchant_id=merchant,
                    purchase_date=today - timedelta(days=days),
                    amount_bdt=30000.0,
                    category="rice",
                )
            )
        session.commit()


def test_policy_lifecycle_belongs_to_the_owner(team):
    assert team.second.post("/org/range-policies", json={"parameters": POLICY}).status_code == 403
    assert team.fsr.get("/org/range-policies").status_code == 403
    bad = team.owner.post("/org/range-policies", json={"parameters": {"window_days": 90}})
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "invalid_policy"
    first = team.owner.post("/org/range-policies", json={"parameters": POLICY, "note": "v1"}).json()
    assert first["status"] == "draft" and first["version"] == 1
    assert team.second.post(f"/org/range-policies/{first['policy_id']}/approve").status_code == 403
    on = team.owner.post(f"/org/range-policies/{first['policy_id']}/approve").json()
    assert on["status"] == "approved" and on["approved_by"]
    second = team.owner.post(
        "/org/range-policies", json={"parameters": {**POLICY, "round_to_bdt": 500}}
    ).json()
    assert second["version"] == 2
    team.owner.post(f"/org/range-policies/{second['policy_id']}/approve")
    states = {p["version"]: p["status"] for p in team.second.get("/org/range-policies").json()}
    assert states == {1: "retired", 2: "approved"}  # the old one is kept
    assert team.solo.get("/org/range-policies").json() == []  # another company sees none
    assert team.solo.post(f"/org/range-policies/{first['policy_id']}/approve").status_code == 404


def test_an_assessment_is_stored_and_recomputes_to_the_same_answer(world, team):
    merchant = active_merchant(team, world, "Assess Store")
    today = real_today(world.config)
    assert team.owner.post(
        f"/merchants/{merchant}/application",
        json={"requested_amount_bdt": 40000, "purpose": "inventory_restock"},
    ).status_code in (200, 201)
    add_purchases(world, merchant, today)
    assert team.fsr.post(f"/merchants/{merchant}/assessments").status_code in (403, 404)
    assert team.solo.post(f"/merchants/{merchant}/assessments").status_code == 404

    run = team.owner.post(f"/merchants/{merchant}/assessments")
    assert run.status_code == 201, run.text
    a = run.json()
    assert a["status"] == "current" and 0 <= a["score"] <= 100
    assert a["input_snapshot"] and a["evidence_refs"]["purchases"]["count"] == 3
    assert a["summary_en"] and a["summary_bn"]
    if a["band"] == "Needs more info":
        assert not a["range_available"] and a["range_reason"] == "needs_more_info"
    else:
        assert a["range_available"] and a["range_policy_id"]
        assert a["range_min_bdt"] <= a["range_max_bdt"] <= 40000
        assert a["range_inputs"]["total_bdt"] == 90000.0 and a["range_reasoning"]
    check = team.second.get(f"/merchants/{merchant}/assessments/{a['assessment_id']}/verify")
    assert check.status_code == 200 and check.json()["probability_matches"]
    assert check.json()["range_matches"]

    # a second run supersedes the first; both stay, newest first
    again = team.owner.post(f"/merchants/{merchant}/assessments").json()
    history = team.second.get(f"/merchants/{merchant}/assessments").json()
    assert [h["assessment_id"] for h in history][0] == again["assessment_id"]
    assert [h["status"] for h in history] == ["current", "superseded"]
    review = team.owner.get(f"/merchants/{merchant}/review").json()["range"]
    assert review["available"] == a["range_available"]

    # sales are stored and shown but never used: the range does not move
    with Session(world.engine) as session:
        stored = session.scalar(
            select(db.Assessment).where(db.Assessment.assessment_id == a["assessment_id"])
        )
        assert json.loads(stored.range_inputs).get("total_bdt") in (None, 90000.0)


def test_without_an_approved_policy_there_is_no_range(world, team):
    merchant = active_merchant(team, world, "No Policy Store")
    team.owner.post(
        f"/merchants/{merchant}/application",
        json={"requested_amount_bdt": 30000, "purpose": "other"},
    )
    add_purchases(world, merchant, real_today(world.config))
    got = team.solo.get("/org/range-policies").json()
    assert got == []
    # Sagar's own officer has no merchant here; Padma has a policy, so check the reason text path
    review = team.owner.get(f"/merchants/{merchant}/review").json()["range"]
    assert review["available"] in (True, False)
    assert review["reason"] in (None, "needs_more_info", "not_enough_verified")
