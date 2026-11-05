"""The officer workspace: review readiness, evidence with provenance, range guidance.

Purpose: tell a credit officer whether the evidence is in order for review, show what the
    records are and how each entered CredLens, and say whether range guidance exists.
Owner role: D (full-stack).
Implements: implementation pack, Phase 6 (6.3 evidence panels, 6.5 readiness, 6.6 range).

Readiness rules (deterministic, in this order; config `review`):
1. The assessment could not be updated after new records          -> "not_updated"
2. Any required check fails (consent, a current assessment,
   enough history: the band is not "Needs more info")              -> "more_info_needed"
3. Any check fails (a shop with an application has no field visit) -> "check_needed"
4. Otherwise                                                       -> "ready"
Deliveries are information only: missing delivery data never blocks review and never
lowers the score. No status means approval, eligibility or a level of risk; the score's
level is not an input to any rule.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.schemas import (
    EvidenceGroup,
    EvidenceRequest,
    RangeGuidance,
    ReadinessCheck,
    ReviewRecord,
)
from src.api.tenancy import default_org
from src.db import models as db

NEEDS_MORE_INFO = "Needs more info"


def readiness(checks: list[ReadinessCheck], assessment: str) -> str:
    """The review status from the checks (rules in the module docstring)."""
    if assessment == "not_updated":
        return "not_updated"
    if any(c.kind == "required" and not c.passed for c in checks):
        return "more_info_needed"
    if any(c.kind == "check" and not c.passed for c in checks):
        return "check_needed"
    return "ready"


def build_checks(
    config: dict[str, Any],
    *,
    consent_valid: bool,
    assessment: str,
    band: str | None,
    has_application: bool,
    visits: int,
    deliveries: int,
) -> list[ReadinessCheck]:
    """The checks for one merchant, from facts the caller read from the saved records."""
    checks = [
        ReadinessCheck(code="consent", kind="required", passed=consent_valid),
        ReadinessCheck(code="assessment", kind="required", passed=assessment == "current"),
        ReadinessCheck(
            code="history", kind="required", passed=band is not None and band != NEEDS_MORE_INFO
        ),
    ]
    if has_application and config["review"]["visit_needed_with_application"]:
        checks.append(ReadinessCheck(code="field_visit", kind="check", passed=visits > 0))
    checks.append(ReadinessCheck(code="deliveries", kind="info", passed=deliveries > 0))
    return checks


def range_guidance(
    config: dict[str, Any],
    session: Session,
    merchant_id: str,
    application: db.Application | None,
    assessment: str,
    band: str | None,
    today,
    org: str | None = None,
) -> RangeGuidance:
    """Range guidance from the company's approved range policy (src/assessment/).

    The band comes from the score, but the money comes from the shop's own verified
    purchases: the score is never turned into money. With no approved policy, no application,
    a band without multiples or too little verified evidence, there is no range.
    """
    from src.assessment import service

    if assessment != "current":
        return RangeGuidance(available=False, reason="assessment_not_current")
    policy, _, result = service.range_for(
        session, org or default_org(config), merchant_id, band, today
    )
    version = f"v{policy.version}" if policy else None
    if not result.available:
        return RangeGuidance(
            available=False,
            reason=result.reason,
            policy_version=version,
            band=band,
            missing=result.missing,
        )
    inputs = result.inputs
    return RangeGuidance(
        available=True,
        reason=None,
        policy_version=version,
        low_bdt=result.low_bdt,
        high_bdt=result.high_bdt,
        band=band,
        monthly_purchases_bdt=inputs.get("monthly_purchases_bdt"),
        window_days=inputs.get("window_days"),
        multiples=json.loads(policy.parameters)["multiples_by_band"].get(band),
        requested_bdt=inputs.get("requested_bdt"),
        capped=any("Capped" in step for step in result.steps)
        and result.high_bdt == inputs.get("requested_bdt"),
    )


def _provenance(session: Session, merchant_id: str) -> dict[tuple[str, str], db.RecordProvenance]:
    """The latest provenance row of each record of a merchant (a status change is a new row)."""
    rows = session.scalars(
        select(db.RecordProvenance)
        .where(db.RecordProvenance.merchant_id == merchant_id)
        .order_by(db.RecordProvenance.provenance_id)
    ).all()
    return {(row.record_type, row.record_id): row for row in rows}


# Where a record came from, in the words the workspace uses. A record with no entry
# (provenance) row is a generated benchmark row.
SOURCES = ("receipts", "typed_in", "spreadsheet", "data_source", "data_file", "generated")
_SOURCE_OF_METHOD = {
    "staff_entered": "typed_in",
    "imported_spreadsheet": "spreadsheet",
    "admin_import": "data_file",
    "synthetic_demo": "generated",
    "receipt_desk": "receipts",
}


def source_of(row: db.RecordProvenance | None, from_connector: bool) -> str:
    """One of SOURCES for a record, from its latest provenance row and its lineage."""
    if from_connector:
        return "data_source"
    return _SOURCE_OF_METHOD.get(row.entry_method, "generated") if row else "generated"


def connector_record_ids(session: Session, record_ids) -> set[str]:
    """The records (of the given ids) that a data source saved (src/connectors/)."""
    ids = list(record_ids)
    if not ids:
        return set()
    return set(
        session.scalars(
            select(db.SourceRecord.record_id).where(db.SourceRecord.record_id.in_(ids))
        )
    )


def _record(kind: str, record_id: str, day, amount, detail, known) -> ReviewRecord:
    row = known.get((kind, record_id))
    return ReviewRecord(
        record_type=kind,
        business_date=day.isoformat()[:10],
        amount_bdt=amount,
        detail=detail,
        entry_method=row.entry_method if row else None,
        status=row.status if row else None,
        entered_at=row.entered_at.isoformat(timespec="seconds") if row else None,
        entered_by=row.actor if row else None,
        simulated=row.simulated if row else None,
    )


def evidence_groups(
    session: Session, config: dict[str, Any], merchant_id: str, application_loan: str | None
) -> list[EvidenceGroup]:
    """Purchases, repayments, deliveries and visits: counts, provenance and the latest few.

    Repayments are payments on issued loans only: an application never has a repayment.
    """
    shown = config["review"]["recent_records_shown"]
    known = _provenance(session, merchant_id)

    def group(name, kind, model, id_col, date_col, amount, detail) -> EvidenceGroup:
        query = select(model).where(model.merchant_id == merchant_id)
        if application_loan is not None and kind == "payment":
            query = query.where(model.loan_id != application_loan)
        rows = session.scalars(query.order_by(date_col.desc())).all()
        ids = [getattr(r, id_col) for r in rows]
        from_source = connector_record_ids(session, [i for i in ids if (kind, i) in known])
        by_source: dict[str, int] = {}
        for i in ids:
            key = source_of(known.get((kind, i)), i in from_source)
            by_source[key] = by_source.get(key, 0) + 1
        latest = [
            _record(kind, getattr(r, id_col), getattr(r, date_col.key), amount(r), detail(r), known)
            for r in rows[:shown]
        ]
        # show who entered a record by name, not by account id
        wanted = {rec.entered_by for rec in latest if rec.entered_by}
        names = (
            dict(
                session.execute(
                    select(db.User.user_id, db.User.display_name).where(db.User.user_id.in_(wanted))
                ).all()
            )
            if wanted
            else {}
        )
        for rec in latest:
            rec.entered_by = names.get(rec.entered_by, rec.entered_by)
        return EvidenceGroup(
            group=name,
            total=len(rows),
            with_entry_record=sum((kind, i) in known for i in ids),
            by_source=by_source,
            latest=latest,
        )

    return [
        group("purchases", "purchase", db.Purchase, "purchase_id", db.Purchase.purchase_date,
              lambda r: r.amount_bdt, lambda r: r.category),
        group("repayments", "payment", db.Payment, "payment_id", db.Payment.due_date,
              lambda r: r.amount_paid_bdt, lambda r: "paid" if r.paid_date else "unpaid"),
        group("deliveries", "delivery", db.Delivery, "delivery_id", db.Delivery.dispatched_at,
              lambda r: None, lambda r: r.status),
        group("visits", "visit", db.Visit, "visit_id", db.Visit.business_date,
              lambda r: None, lambda r: r.outcome),
    ]


def evidence_requests(
    session: Session, config: dict[str, Any], merchant_id: str, has_application: bool
) -> list[EvidenceRequest]:
    """The smallest evidence worth asking for, by fixed rules, most important first.

    Only records entered in the app are looked at (a generated benchmark row has no paper
    behind it to ask for). Rules, in order:
    1. an application but no purchase record at all      -> add_purchase_records
    2. a shop created in the app whose name and district match another such shop
                                                          -> confirm_not_same_shop
    3. two purchases with the same date and amount        -> confirm_possible_duplicate
    4. a repayment that paid less than was due            -> clarify_part_payment
    5. a purchase at or above `material_purchase_bdt`     -> show_memo_for_large_purchase
    Rules 2 and 3 are not asked again once a person reviewed them under Data quality
    (src/api/quality.py), while the records stay as the reviewer saw them.
    At most `max_requests` are returned. None of them promises a better score.
    """
    from src.api.quality import settled
    from src.api.tenancy import merchant_in_org
    from src.intake.merchants import likely_duplicates

    rules = config["review"]["evidence_requests"]
    known = _provenance(session, merchant_id)
    asks: list[EvidenceRequest] = []

    purchases = session.scalars(
        select(db.Purchase).where(db.Purchase.merchant_id == merchant_id)
        .order_by(db.Purchase.purchase_date)
    ).all()
    entered = [p for p in purchases if ("purchase", p.purchase_id) in known]
    if has_application and not purchases:
        asks.append(EvidenceRequest(code="add_purchase_records"))

    profile = session.get(db.MerchantProfile, merchant_id)
    if profile is not None:
        merchant = session.get(db.Merchant, merchant_id)
        org = merchant.organization_id or config["organization"]["id"]
        scope = merchant_in_org(org, config)
        for other in likely_duplicates(session, profile.shop_name, merchant.district, scope):
            pair = tuple(sorted((merchant_id, other["merchant_id"])))
            if other["merchant_id"] != merchant_id and not settled(
                session, f"same_shop:{pair[0]}|{pair[1]}", pair
            ):
                asks.append(
                    EvidenceRequest(
                        code="confirm_not_same_shop", other_merchant_id=other["merchant_id"]
                    )
                )
                break

    seen: set[tuple] = set()
    for p in entered:
        value = (p.purchase_date, round(p.amount_bdt, 2))
        same = tuple(
            sorted(q.purchase_id for q in purchases
                   if (q.purchase_date, round(q.amount_bdt, 2)) == value)
        )
        key = f"duplicate:{merchant_id}|{value[0].isoformat()}|{value[1]:.2f}"
        if value in seen and not settled(session, key, same):
            asks.append(
                EvidenceRequest(
                    code="confirm_possible_duplicate",
                    business_date=p.purchase_date.isoformat(),
                    amount_bdt=p.amount_bdt,
                )
            )
            break
        seen.add(value)

    for pay in session.scalars(
        select(db.Payment).where(db.Payment.merchant_id == merchant_id)
        .order_by(db.Payment.due_date)
    ):
        if ("payment", pay.payment_id) in known and pay.amount_paid_bdt < pay.amount_due_bdt:
            asks.append(
                EvidenceRequest(
                    code="clarify_part_payment",
                    business_date=pay.due_date.isoformat(),
                    amount_bdt=pay.amount_due_bdt - pay.amount_paid_bdt,
                )
            )
            break

    large = [p for p in entered if p.amount_bdt >= rules["material_purchase_bdt"]]
    if large:
        biggest = max(large, key=lambda p: p.amount_bdt)
        asks.append(
            EvidenceRequest(
                code="show_memo_for_large_purchase",
                business_date=biggest.purchase_date.isoformat(),
                amount_bdt=biggest.amount_bdt,
            )
        )
    return asks[: rules["max_requests"]]
