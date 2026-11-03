"""Storing an assessment, and finding a company's approved range policy.

Purpose: one assessment = the model's card + the evidence it rested on + the range (or why
    none), written once so it can be shown again and recomputed. A new one supersedes the old
    one (which stays). Decision support only: nothing here approves or declines credit.
Owner role: C (assessment).
Implements: Phase 6 of the unified platform plan (section 15).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from src.accounts.service import now
from src.assessment import range_engine
from src.db import models as db
from src.model.explain import calibrated_probability


def approved_policy(session: Session, org: str) -> db.RangePolicy | None:
    return session.scalar(
        select(db.RangePolicy)
        .where(db.RangePolicy.organization_id == org, db.RangePolicy.status == "approved")
        .order_by(db.RangePolicy.version.desc())
    )


def verified_purchases(session: Session, merchant_id: str, today: date) -> list[tuple[date, float]]:
    """Purchases in the contract table. Drafts never get there, so these are verified."""
    rows = session.execute(
        select(db.Purchase.purchase_date, db.Purchase.amount_bdt).where(
            db.Purchase.merchant_id == merchant_id, db.Purchase.purchase_date <= today
        )
    ).all()
    return [(d, float(a)) for d, a in rows]


def requested_amount(session: Session, merchant_id: str) -> tuple[str | None, float | None]:
    app = session.scalar(select(db.Application).where(db.Application.merchant_id == merchant_id))
    return (app.loan_id, float(app.requested_amount_bdt)) if app else (None, None)


def range_for(session: Session, org: str, merchant_id: str, band: str | None, today: date):
    """(policy row or None, application id, RangeResult) for a merchant today."""
    policy = approved_policy(session, org)
    application_id, requested = requested_amount(session, merchant_id)
    params = json.loads(policy.parameters) if policy else None
    result = range_engine.compute(
        params, band, verified_purchases(session, merchant_id, today), requested, today
    )
    return policy, application_id, result


def evidence_refs(session: Session, merchant_id: str, today: date) -> dict[str, Any]:
    """Counts of what the model could see, plus a hash of the purchase ids."""
    out: dict[str, Any] = {"as_of": today.isoformat()}
    for name, model in (
        ("purchases", db.Purchase),
        ("payments", db.Payment),
        ("deliveries", db.Delivery),
    ):
        count = session.scalar(
            select(func.count()).select_from(model).where(model.merchant_id == merchant_id)
        )
        out[name] = {"count": int(count or 0)}
    ids = session.scalars(
        select(db.Purchase.purchase_id)
        .where(db.Purchase.merchant_id == merchant_id)
        .order_by(db.Purchase.purchase_id)
    ).all()
    out["purchase_ids_sha256"] = hashlib.sha256("|".join(ids).encode()).hexdigest()
    return out


def run_assessment(
    session: Session, scorer: Any, org: str, user_id: str, merchant_id: str, today: date
) -> db.Assessment:
    """Compute and store a new current assessment. Raises ConsentRequired / UnknownMerchant."""
    row = scorer.feature_row(merchant_id)
    card = scorer.card(merchant_id)
    names = list(scorer.saved["features"])
    snapshot = {n: (None if row[n] != row[n] else float(row[n])) for n in names}
    policy, application_id, result = range_for(session, org, merchant_id, card["band"], today)
    session.execute(
        update(db.Assessment)
        .where(db.Assessment.merchant_id == merchant_id, db.Assessment.status == "current")
        .values(status="superseded")
    )
    record = db.Assessment(
        assessment_id=f"AS-{uuid.uuid4().hex[:24]}",
        organization_id=org,
        merchant_id=merchant_id,
        application_id=application_id,
        status="current",
        model_version=card["model_version"],
        model_sha=str(scorer.saved.get("sha256") or "") or None,
        probability=float(card["probability"]),
        score=int(card["score"]),
        band=card["band"],
        coverage=float(card["coverage"]),
        low_score_warning=bool(card["low_score_warning"]),
        input_snapshot=json.dumps(snapshot),
        evidence_refs=json.dumps(evidence_refs(session, merchant_id, today)),
        reasons_positive=json.dumps(card["reasons_positive"], default=str),
        reasons_negative=json.dumps(card["reasons_negative"], default=str),
        summary_en=_summary(card, result, "en"),
        summary_bn=_summary(card, result, "bn"),
        range_policy_id=policy.policy_id if policy else None,
        range_available=result.available,
        range_reason=result.reason,
        range_min_bdt=result.low_bdt,
        range_max_bdt=result.high_bdt,
        range_inputs=json.dumps(result.inputs),
        range_reasoning=json.dumps(result.steps),
        assessed_by=user_id,
        assessed_at=now(),
    )
    session.add(record)
    return record


def _summary(card: dict[str, Any], result: range_engine.RangeResult, lang: str) -> str:
    if lang == "bn":
        base = f"স্কোর {card['score']} ({card['band']}), তথ্যের আওতা {card['coverage']:.0%}।"
        tail = (
            f" ইঙ্গিতমূলক সীমা {result.low_bdt:,.0f}–{result.high_bdt:,.0f} টাকা।"
            if result.available
            else " যাচাইকৃত তথ্য থেকে কোনো সীমা দেওয়া যায়নি।"
        )
        return base + tail + " সিদ্ধান্ত নেবেন একজন মানুষ।"
    base = f"Score {card['score']} ({card['band']}), evidence coverage {card['coverage']:.0%}."
    tail = (
        f" Indicative range {result.low_bdt:,.0f} to {result.high_bdt:,.0f} BDT."
        if result.available
        else " No range from verified information."
    )
    return base + tail + " A person decides."


def reproduce(session: Session, scorer: Any, row: db.Assessment) -> dict[str, Any]:
    """Recompute a stored assessment from its own snapshot and policy; report whether it matches."""
    import pandas as pd

    saved = scorer.saved
    frame = pd.DataFrame([json.loads(row.input_snapshot)])[list(saved["features"])]
    prob = float(calibrated_probability(saved, frame)[0])
    inputs = json.loads(row.range_inputs or "{}")
    again = None
    policy = session.get(db.RangePolicy, row.range_policy_id) if row.range_policy_id else None
    if policy and row.range_available:
        params = range_engine.check_parameters(json.loads(policy.parameters))
        multiples = params["multiples_by_band"].get(inputs.get("band") or "")
        monthly = inputs["total_bdt"] / inputs["window_days"] * 30

        def end(m: float) -> float:
            value = monthly * m
            if params["cap_at_requested"]:
                value = min(value, inputs["requested_bdt"])
            return float(int(value // params["round_to_bdt"]) * params["round_to_bdt"])

        again = (end(multiples[0]), end(multiples[1]))
    range_ok = (not row.range_available) or again == (row.range_min_bdt, row.range_max_bdt)
    return {
        "probability_matches": abs(prob - row.probability) < 1e-9,
        "range_matches": bool(range_ok),
        "recomputed_probability": prob,
        "recomputed_range": list(again) if again else None,
    }
