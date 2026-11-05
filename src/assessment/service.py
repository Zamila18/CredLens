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
        plain=json.dumps(plain_summary(session, card, result, merchant_id), ensure_ascii=False),
        assessed_by=user_id,
        assessed_at=now(),
    )
    session.add(record)
    return record


OUTLOOK = {"Strong": "strong", "Review": "moderate"}


def _sentence(reason: Any, lang: str) -> str:
    if isinstance(reason, dict):
        return reason.get("sentence_bn" if lang == "bn" else "sentence_en") or ""
    return str(reason)


def plain_summary(
    session: Session, card: dict[str, Any], result: range_engine.RangeResult, merchant_id: str
) -> dict[str, Any]:
    """What an officer reads first: an outlook in one word, why, what it rests on, what would
    make it firmer. No percentages of coverage, no points: only things a person can check."""
    published = session.scalars(
        select(db.Receipt).where(
            db.Receipt.merchant_id == merchant_id, db.Receipt.status == "published"
        )
    ).all()
    confirmed = sum(1 for r in published if r.merchant_confirmed_at is not None)
    disputed = int(
        session.scalar(
            select(func.count())
            .select_from(db.ReceiptLine)
            .where(db.ReceiptLine.merchant_id == merchant_id, db.ReceiptLine.status == "disputed")
        )
        or 0
    )
    repayments = int(
        session.scalar(
            select(func.count())
            .select_from(db.Payment)
            .where(db.Payment.merchant_id == merchant_id)
        )
        or 0
    )
    inputs = result.inputs or {}
    basis = {
        "receipts": len(published),
        "receipts_confirmed": confirmed,
        "purchase_records": inputs.get("records", 0),
        "months_with_purchases": inputs.get("months_with_purchases", 0),
        "window_days": inputs.get("window_days"),
        "monthly_purchases_bdt": inputs.get("monthly_purchases_bdt"),
        "lines_disputed": disputed,
        "repayments_on_file": repayments,
    }
    outlook = OUTLOOK.get(card["band"], "not_enough")
    why = {"en": [], "bn": []}
    for lang in ("en", "bn"):
        for reason in card["reasons_positive"][:2] + card["reasons_negative"][:2]:
            sentence = _sentence(reason, lang).strip()
            if sentence:
                why[lang].append(sentence)
    improve = {"en": [], "bn": []}

    def ask(en: str, bn: str) -> None:
        improve["en"].append(en)
        improve["bn"].append(bn)

    if result.missing:
        ask(
            "Add more checked purchase receipts: " + "; ".join(result.missing) + ".",
            "আরও যাচাই করা ক্রয়ের রসিদ যোগ করুন: " + "; ".join(result.missing) + "।",
        )
    if card["band"] == "Needs more info":
        ask(
            "Add checked receipts for earlier months: the model rates a shop once it has about "
            "six months of purchases.",
            "আগের মাসগুলোর যাচাই করা রসিদ যোগ করুন: প্রায় ছয় মাসের ক্রয় থাকলে মডেল দোকানটিকে মূল্যায়ন করে।",
        )
    if disputed:
        ask(
            f"Answer the {disputed} line(s) the merchant reported; they are left out until then.",
            f"ব্যবসায়ীর জানানো {disputed}টি লাইনের উত্তর দিন; উত্তর না দেওয়া পর্যন্ত সেগুলো বাদ থাকবে।",
        )
    if published and confirmed < len(published):
        ask(
            "Ask the merchant to look over their receipts and press 'Looks right'.",
            "ব্যবসায়ীকে তাঁর রসিদগুলো দেখে 'ঠিক আছে' চাপতে বলুন।",
        )
    if not published:
        ask(
            "No receipts have been published yet: the Records Desk uploads and checks them first.",
            "এখনও কোনো রসিদ প্রকাশ হয়নি: আগে রেকর্ড ডেস্ক সেগুলো আপলোড ও যাচাই করবে।",
        )
    if repayments == 0:
        ask(
            "There is no repayment history yet; it appears after a first loan is repaid.",
            "এখনও পরিশোধের ইতিহাস নেই; প্রথম ঋণ শোধের পর তা দেখা যাবে।",
        )
    if result.available:
        line_en = (
            f"Suggested range to consider: {result.low_bdt:,.0f} to {result.high_bdt:,.0f} BDT."
        )
        line_bn = (
            f"বিবেচনার জন্য প্রস্তাবিত পরিসীমা: {result.low_bdt:,.0f} থেকে {result.high_bdt:,.0f} টাকা।"
        )
    else:
        reasons = {
            range_engine.NO_POLICY: (
                "No range yet: the company has not approved a range policy.",
                "এখনও পরিসীমা নেই: প্রতিষ্ঠান কোনো পরিসীমা-নীতি অনুমোদন করেনি।",
            ),
            range_engine.NOT_ENOUGH: (
                "No range yet: there are not enough checked purchases.",
                "এখনও পরিসীমা নেই: যথেষ্ট যাচাই করা ক্রয় নেই।",
            ),
            range_engine.NEEDS_MORE_INFO: (
                "No range yet: this shop has less purchase history than the model needs to rate "
                "it (about six months).",
                "এখনও পরিসীমা নেই: দোকানটিকে মূল্যায়নের জন্য মডেলের প্রয়োজনীয় ক্রয়ের ইতিহাস "
                "(প্রায় ছয় মাস) এখনও নেই।",
            ),
            range_engine.NO_APPLICATION: (
                "No range yet: the merchant has not applied for a loan.",
                "এখনও পরিসীমা নেই: ব্যবসায়ী ঋণের জন্য আবেদন করেননি।",
            ),
        }
        line_en, line_bn = reasons.get(result.reason or "", ("No range.", "পরিসীমা নেই।"))
    return {
        "outlook": outlook,
        "range_line": {"en": line_en, "bn": line_bn},
        "why": why,
        "basis": basis,
        "improve": improve,
    }


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
