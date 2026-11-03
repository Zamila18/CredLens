"""Build a merchant profile (GET /merchants/{id}) from the database.

Purpose: the summaries, questionnaire panel and unified timeline an officer sees.
Owner role: D (full-stack).
Implements: PROJECT_BRIEF sections 8 and 9; docs/HANDOVER.md Part C and E.

Two rules shape this file:
- Consent first. Without a valid consent nothing about the merchant's behaviour is shown:
  no summaries, no questionnaire, no timeline. Only who the shop is, and `consent_valid`.
- The 90-day numbers are the ones the score was computed from (the merchant's feature row
  on their most recent loan), not a second calculation that could disagree with the
  reasons the officer reads. A stream with no records at all is null.

Purchases are what the shop BUYS for stock. They are never called sales or revenue.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.schemas import (
    DeliveriesSummary,
    MerchantProfile,
    PaymentsSummary,
    PurchasesSummary,
    QuestionnaireSummary,
    TimelineEvent,
)
from src.db import models as db
from src.model.dataset import merchants_with_valid_consent

QUESTIONNAIRE_CONSENT_CATEGORY = "questionnaire"
STREAM_ORDER = {"purchase": 0, "delivery": 1, "loan": 2, "payment": 3}


def consent_state(session: Session, merchant_id: str, as_of: date) -> tuple[bool, set[str]]:
    """Is there a valid consent today, and which data categories do valid consents cover.

    "Valid" is decided by `merchants_with_valid_consent`, the rule the review queue uses:
    granted, not expired and not revoked on `as_of`.
    """
    rows = session.scalars(select(db.Consent).where(db.Consent.merchant_id == merchant_id)).all()
    categories: set[str] = set()
    for row in rows:
        frame = pd.DataFrame(
            [
                {
                    "merchant_id": row.merchant_id,
                    "granted_at": row.granted_at,
                    "expires_at": row.expires_at,
                    "revoked_at": row.revoked_at,
                }
            ]
        )
        if merchants_with_valid_consent(frame, pd.Timestamp(as_of)):
            categories.update(part for part in row.data_categories.split("|") if part)
    return bool(categories), categories


def _number(row: pd.Series, name: str) -> float | None:
    """A value of the feature row, or None when it is missing."""
    value = row.get(name)
    return None if value is None or pd.isna(value) else float(value)


def _words(code: str | None) -> str:
    """'rice_grain' -> 'rice grain'."""
    return (code or "").replace("_", " ")


def build_profile(
    session: Session,
    merchant: db.Merchant,
    data_mode: str,
    consent_valid: bool,
    feature_row: pd.Series | None,
    as_of: date,
) -> MerchantProfile:
    """The profile of one merchant. Behaviour is left out unless consent is valid.

    `as_of` is "today" for the data: a payment that is not yet due is not listed.
    """
    profile = MerchantProfile(
        merchant_id=merchant.merchant_id,
        data_mode=data_mode,
        onboarded_at=merchant.onboarded_at.isoformat(),
        district=merchant.district,
        town_tier=merchant.town_tier,
        shop_type=merchant.shop_type,
        has_trade_license=merchant.has_trade_license,
        consent_valid=consent_valid,
    )
    shop = session.get(db.MerchantProfile, merchant.merchant_id)
    if shop is not None:  # a shop created in the app has a name and an area
        profile.shop_name, profile.area = shop.shop_name, shop.area
    if not consent_valid:
        return profile

    if feature_row is not None:
        profile.purchases = _purchases(session, merchant.merchant_id, feature_row)
        profile.deliveries = _deliveries(feature_row)
        profile.payments = _payments(feature_row)
    profile.questionnaire = questionnaire_summary(session, merchant.merchant_id)
    profile.timeline = timeline(session, merchant.merchant_id, as_of)
    return profile


def _purchases(session: Session, merchant_id: str, row: pd.Series) -> PurchasesSummary | None:
    if not (_number(row, "n_purchases_total") or 0):
        return None
    cutoff = pd.Timestamp(row["cutoff_date"]).date()
    days = session.scalars(
        select(db.Purchase.purchase_date).where(
            db.Purchase.merchant_id == merchant_id, db.Purchase.purchase_date < cutoff
        )
    ).all()
    weeks = {tuple(day.isocalendar())[:2] for day in days}
    return PurchasesSummary(
        n_purchases_90d=int(_number(row, "purchases_90d") or 0),
        value_bdt_90d=round(_number(row, "purchase_value_90d") or 0.0, 0),
        n_categories=int(_number(row, "category_diversity") or 0),
        weeks_active=len(weeks),
    )


def _rate(row: pd.Series, name: str) -> float | None:
    value = _number(row, name)
    return None if value is None else round(value, 3)


def _deliveries(row: pd.Series) -> DeliveriesSummary | None:
    if not (_number(row, "n_deliveries_total") or 0):
        return None
    return DeliveriesSummary(
        n_parcels_90d=int(_number(row, "parcel_volume_90d") or 0),
        delivered_rate=_rate(row, "delivered_rate"),
        return_rate=_rate(row, "return_rate_90d"),
        failed_rate=_rate(row, "failed_rate_90d"),
        cod_remit_ontime_rate=_rate(row, "cod_remit_ontime_rate"),
    )


def _payments(row: pd.Series) -> PaymentsSummary | None:
    count = int(_number(row, "n_payments_total") or 0)
    if not count:
        return None
    delay = _number(row, "avg_pay_delay_days")
    return PaymentsSummary(
        n_payments=count,
        ontime_rate=_rate(row, "ontime_payment_rate"),
        avg_days_late=None if delay is None else round(delay, 1),
    )


def questionnaire_summary(session: Session, merchant_id: str) -> QuestionnaireSummary | None:
    """The four sub-scores (each the mean of two answers), stress and confidence."""
    row = session.get(db.Questionnaire, merchant_id)
    if row is None:
        return None
    return QuestionnaireSummary(
        answered_at=row.answered_at.isoformat(),
        spend=(row.spend1 + row.spend2) / 2,
        save=(row.save1 + row.save2) / 2,
        borrow=(row.borrow1 + row.borrow2) / 2,
        plan=(row.plan1 + row.plan2) / 2,
        stress=row.stress,
        confidence=row.confidence,
    )


# Bangla for the codes the timeline shows (purchase categories, delivery outcomes and
# return reasons). A code missing here is shown as it is, with spaces for underscores.
CATEGORY_BN = {
    "household": "গৃহস্থালি পণ্য",
    "spices": "মসলা",
    "beverages": "পানীয়",
    "cooking_oil": "রান্নার তেল",
    "rice_grain": "চাল ও শস্য",
    "snacks": "নাস্তা",
    "clothing": "পোশাক",
    "fabrics": "কাপড়",
    "footwear": "জুতা",
    "accessories": "অনুষঙ্গ",
    "lighting": "বাতি",
    "small_appliances": "ছোট যন্ত্রপাতি",
    "mobile_accessories": "মোবাইলের অনুষঙ্গ",
    "personal_care": "ব্যক্তিগত যত্ন",
    "batteries": "ব্যাটারি",
    "medicine": "ওষুধ",
    "baby_care": "শিশুর যত্ন",
    "health_devices": "স্বাস্থ্য সরঞ্জাম",
    "stationery": "স্টেশনারি",
    "hardware": "হার্ডওয়্যার",
    "toys": "খেলনা",
    "cosmetics": "প্রসাধনী",
}
DELIVERY_BN = {
    "delivered": "পার্সেল পৌঁছেছে",
    "returned": "পার্সেল ফেরত এসেছে",
    "failed": "পার্সেল পৌঁছানো যায়নি",
    "cancelled": "পার্সেল বাতিল",
}
REASON_BN = {
    "address_issue": "ঠিকানার সমস্যা",
    "rider_issue": "রাইডারের সমস্যা",
    "refused": "ক্রেতা নেননি",
    "wrong_item": "ভুল পণ্য",
    "other": "অন্যান্য",
}


def _bn(code: str | None, words: dict[str, str]) -> str:
    """The Bangla of a code, or the code in plain words when there is none."""
    return words.get(code or "", _words(code))


def _payment_label_bn(due: date, paid: date) -> str:
    late = (paid - due).days
    if late == 0:
        return "নির্ধারিত দিনে পেমেন্ট"
    return f"নির্ধারিত দিনের {abs(late)} দিন {'পরে' if late > 0 else 'আগে'} পেমেন্ট"


def _delivery_label_bn(status: str, reason: str | None) -> str:
    detail = f" ({_bn(reason, REASON_BN)})" if reason else ""
    return DELIVERY_BN.get(status, f"পার্সেল {status}") + detail


def _payment_label(due: date, paid: date) -> str:
    late = (paid - due).days
    if late == 0:
        return "Payment on the due date"
    unit = "day" if abs(late) == 1 else "days"
    return f"Payment {abs(late)} {unit} {'after' if late > 0 else 'before'} the due date"


def _delivery_label(status: str, reason: str | None) -> str:
    detail = f" ({_words(reason)})" if reason else ""
    names = {
        "delivered": "Parcel delivered",
        "returned": "Parcel returned",
        "failed": "Parcel delivery failed",
        "cancelled": "Parcel cancelled",
    }
    return names.get(status, f"Parcel {status}") + detail


def timeline(session: Session, merchant_id: str, as_of: date) -> list[TimelineEvent]:
    """Every purchase, parcel, loan and payment of the merchant, oldest first.

    An unpaid instalment is listed from the day it was due. One that is not due yet is not.
    """
    events: list[tuple[date, str, str, Any, str]] = []
    purchases = session.execute(
        select(db.Purchase.purchase_date, db.Purchase.category, db.Purchase.amount_bdt).where(
            db.Purchase.merchant_id == merchant_id
        )
    )
    for day, category, amount in purchases:
        label = f"Stock purchase: {_words(category)}" if category else "Stock purchase"
        label_bn = f"মাল কেনা: {_bn(category, CATEGORY_BN)}" if category else "মাল কেনা"
        events.append((day, "purchase", label, amount, label_bn))
    parcels = session.execute(
        select(db.Delivery.dispatched_at, db.Delivery.status, db.Delivery.return_reason).where(
            db.Delivery.merchant_id == merchant_id
        )
    )
    for moment, status, reason in parcels:
        events.append(
            (
                moment.date(),
                "delivery",
                _delivery_label(status, reason),
                None,
                _delivery_label_bn(status, reason),
            )
        )
    # An application is scored through a loan-shaped row, but it is a request, not a loan:
    # it is shown as one, with the amount asked for (the row itself carries no amount).
    requested = dict(
        session.execute(
            select(db.Application.loan_id, db.Application.requested_amount_bdt).where(
                db.Application.merchant_id == merchant_id
            )
        ).all()
    )
    loans = session.execute(
        select(db.Loan.loan_id, db.Loan.issued_at, db.Loan.limit_bdt).where(
            db.Loan.merchant_id == merchant_id
        )
    )
    for loan_id, day, limit in loans:
        if loan_id in requested:
            events.append(
                (
                    day,
                    "loan",
                    "Application received (amount requested, not a loan)",
                    requested[loan_id],
                    "আবেদন গ্রহণ করা হয়েছে (চাওয়া অঙ্ক, ঋণ নয়)",
                    "application",
                )
            )
        else:
            events.append((day, "loan", "Loan issued", limit, "ঋণ দেওয়া হয়েছে", "loan"))
    payments = session.execute(
        select(
            db.Payment.due_date,
            db.Payment.paid_date,
            db.Payment.amount_due_bdt,
            db.Payment.amount_paid_bdt,
        ).where(db.Payment.merchant_id == merchant_id)
    )
    for due, paid, amount_due, amount_paid in payments:
        if paid is not None:
            events.append(
                (
                    paid,
                    "payment",
                    _payment_label(due, paid),
                    amount_paid,
                    _payment_label_bn(due, paid),
                )
            )
        elif due <= as_of:
            events.append(
                (
                    due,
                    "payment",
                    "Payment due; no payment recorded",
                    amount_due,
                    "পেমেন্টের দিন পেরিয়েছে; কোনো পেমেন্ট নেই",
                )
            )
    events.sort(key=lambda event: (event[0], STREAM_ORDER[event[1]], event[2]))
    return [
        TimelineEvent(
            date=event[0].isoformat(),
            stream=event[1],
            label=event[2],
            label_bn=event[4],
            amount_bdt=None if event[3] is None else float(event[3]),
            kind=event[5] if len(event) > 5 else event[1],
        )
        for event in events
    ]
