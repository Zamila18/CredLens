"""Data-quality issues: what in an organisation's records needs a person's attention.

Purpose: make problems with the evidence visible instead of hiding them in validation.
Owner role: D (full-stack).
Implements: Workstream D (matching and data quality) of the platform plan.

How it works:
- Issues are worked out from the records every time they are asked for; nothing here
  writes, changes or removes a record. Only a person's review is stored
  (`db.QualityReview`, append-only, with a written note).
- Every issue has a stable key and a fingerprint of the evidence behind it. A review
  counts only while the evidence is the same: if a new record changes the picture, the
  issue opens again and says so.
- Only records entered in the app are checked (field entry, spreadsheet imports, data
  sources). The read-only benchmark data is generated and has no paper behind it.
- Missing evidence is a gap to fill, never a sign of bad behaviour, and no issue changes
  a score. Nothing is merged, linked or deleted automatically.

The kinds, by group:
- identity:     possible_same_shop, withdrawn_link
- duplicates:   possible_duplicate_record
- sources:      source_rows_left_out, source_failing, import_rows_left_out
- completeness: missing_evidence, stale_evidence
- consent:      consent_lapsed
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.api.profile import consent_state
from src.connectors.service import confirmed_links
from src.db import models as db
from src.intake.merchants import normalised
from src.intake.policy import calendar_end

# kind -> (group, outcomes a person may record). No outcomes: fixed by adding evidence or
# by acting on the source, not by a review.
KINDS: dict[str, tuple[str, tuple[str, ...]]] = {
    "possible_same_shop": ("identity", ("different_shops", "same_shop")),
    "withdrawn_link": ("identity", ("records_correct", "records_wrong")),
    "possible_duplicate_record": ("duplicates", ("both_genuine", "duplicate")),
    "source_rows_left_out": ("sources", ("leave_as_is",)),
    "source_failing": ("sources", ()),
    "import_rows_left_out": ("sources", ("acknowledged",)),
    "missing_evidence": ("completeness", ()),
    "stale_evidence": ("completeness", ()),
    "consent_lapsed": ("consent", ()),
}
# Outcomes that confirm a problem. The issue is reviewed, but the merchant's review keeps
# showing it: CredLens does not merge shops or remove records by itself.
CONCERNS = frozenset({"same_shop", "records_wrong", "duplicate"})


@dataclass
class Evidence:
    """One record behind an issue, with where it came from."""

    record_type: str
    record_id: str
    merchant_id: str | None = None
    business_date: str | None = None
    amount: float | None = None
    detail: str | None = None
    origin: str | None = None  # entry method, e.g. staff_entered
    origin_name: str | None = None  # the file or the connection, when there is one


@dataclass
class Issue:
    key: str
    kind: str
    merchant_id: str | None = None
    other_merchant_id: str | None = None
    connection_id: str | None = None
    batch_id: str | None = None
    facts: dict[str, Any] = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)
    basis: tuple = ()  # what the fingerprint is made of

    @property
    def group(self) -> str:
        return KINDS[self.kind][0]

    @property
    def outcomes(self) -> tuple[str, ...]:
        return KINDS[self.kind][1]

    @property
    def fingerprint(self) -> str:
        text = "|".join(str(part) for part in self.basis)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _app_merchants(session: Session, scope) -> dict[str, tuple[db.Merchant, db.MerchantProfile]]:
    rows = session.execute(
        select(db.Merchant, db.MerchantProfile)
        .join(db.MerchantProfile, db.MerchantProfile.merchant_id == db.Merchant.merchant_id)
        .where(scope)
    ).all()
    return {merchant.merchant_id: (merchant, profile) for merchant, profile in rows}


def _origins(session: Session, record_ids: set[str]) -> dict[str, tuple[str, str | None]]:
    """record id -> (entry method, file or connection name) from provenance and lineage."""
    if not record_ids:
        return {}
    ids = list(record_ids)
    batches: dict[str, str] = {}
    out: dict[str, tuple[str, str | None]] = {}
    for row in session.scalars(
        select(db.RecordProvenance)
        .where(db.RecordProvenance.record_id.in_(ids))
        .order_by(db.RecordProvenance.provenance_id)
    ):
        name = None
        if row.batch_id:
            if row.batch_id not in batches:
                batch = session.get(db.ImportBatch, row.batch_id)
                batches[row.batch_id] = batch.file_name if batch else row.batch_id
            name = batches[row.batch_id]
        out[row.record_id] = (row.entry_method, name)
    names = {
        c.connection_id: c.display_name
        for c in session.scalars(
            select(db.SourceConnection).where(
                db.SourceConnection.connection_id.in_(
                    select(db.SourceRecord.connection_id).where(db.SourceRecord.record_id.in_(ids))
                )
            )
        )
    }
    for row in session.scalars(select(db.SourceRecord).where(db.SourceRecord.record_id.in_(ids))):
        out[row.record_id] = ("data_source", names.get(row.connection_id, row.connection_id))
    return out


def _same_shops(merchants) -> list[Issue]:
    groups: dict[tuple[str, str], list[str]] = {}
    for merchant_id, (merchant, profile) in merchants.items():
        groups.setdefault((normalised(profile.shop_name), merchant.district or ""), []).append(
            merchant_id
        )
    issues = []
    for (_, district), ids in groups.items():
        ids = sorted(ids)
        for i, first in enumerate(ids):
            for second in ids[i + 1 :]:
                issues.append(
                    Issue(
                        key=f"same_shop:{first}|{second}",
                        kind="possible_same_shop",
                        merchant_id=first,
                        other_merchant_id=second,
                        facts={
                            "shop_name": merchants[first][1].shop_name,
                            "other_shop_name": merchants[second][1].shop_name,
                            "district": district,
                            "area": merchants[first][1].area,
                            "other_area": merchants[second][1].area,
                        },
                        basis=(first, second),
                    )
                )
    return issues


def _duplicate_records(session: Session, merchants, origins) -> list[Issue]:
    groups: dict[tuple, list[db.Purchase]] = {}
    for p in session.scalars(
        select(db.Purchase)
        .where(db.Purchase.merchant_id.in_(list(merchants)))
        .order_by(db.Purchase.purchase_id)
    ):
        groups.setdefault((p.merchant_id, p.purchase_date, round(p.amount_bdt, 2)), []).append(p)
    issues = []
    for (merchant_id, day, amount), rows in groups.items():
        if len(rows) < 2:
            continue
        evidence = []
        for p in rows:
            method, name = origins.get(p.purchase_id, (None, None))
            evidence.append(
                Evidence(
                    "purchase",
                    p.purchase_id,
                    merchant_id,
                    day.isoformat(),
                    amount,
                    p.category,
                    method,
                    name,
                )
            )
        sources = {e.origin_name or e.origin for e in evidence}
        issues.append(
            Issue(
                key=f"duplicate:{merchant_id}|{day.isoformat()}|{amount:.2f}",
                kind="possible_duplicate_record",
                merchant_id=merchant_id,
                facts={
                    "business_date": day.isoformat(),
                    "amount": amount,
                    "records": len(rows),
                    "sources": len(sources),
                },
                evidence=evidence,
                basis=tuple(sorted(p.purchase_id for p in rows)),
            )
        )
    return issues


def _connections(session: Session, org: str) -> list[db.SourceConnection]:
    return list(
        session.scalars(
            select(db.SourceConnection)
            .where(db.SourceConnection.organization_id == org)
            .order_by(db.SourceConnection.created_at)
        )
    )


def _withdrawn_links(session: Session, connections, merchants) -> list[Issue]:
    issues = []
    for connection in connections:
        linked = {
            link.merchant_id
            for link in confirmed_links(session, connection).values()
            if link.decision == "confirmed"
        }
        saved: dict[str, list[db.SourceRecord]] = {}
        for row in session.scalars(
            select(db.SourceRecord)
            .where(db.SourceRecord.connection_id == connection.connection_id)
            .order_by(db.SourceRecord.id)
        ):
            saved.setdefault(row.merchant_id, []).append(row)
        for merchant_id, rows in saved.items():
            if merchant_id in linked:
                continue
            issues.append(
                Issue(
                    key=f"withdrawn_link:{connection.connection_id}|{merchant_id}",
                    kind="withdrawn_link",
                    merchant_id=merchant_id,
                    connection_id=connection.connection_id,
                    facts={
                        "connection_name": connection.display_name,
                        "records": len(rows),
                        "shop_name": merchants[merchant_id][1].shop_name
                        if merchant_id in merchants
                        else None,
                    },
                    evidence=[
                        Evidence(
                            r.record_type,
                            r.record_id,
                            merchant_id,
                            None,
                            None,
                            r.source_reference,
                            "data_source",
                            connection.display_name,
                        )
                        for r in rows
                    ],
                    basis=tuple(sorted(r.record_id for r in rows)),
                )
            )
    return issues


def _source_runs(session: Session, connections) -> list[Issue]:
    issues = []
    for connection in connections:
        if connection.status == "revoked":
            continue
        runs = session.scalars(
            select(db.SourceRun)
            .where(db.SourceRun.connection_id == connection.connection_id)
            .order_by(db.SourceRun.started_at.desc(), db.SourceRun.run_id)
        ).all()
        if connection.status == "error" and runs:
            issues.append(
                Issue(
                    key=f"source_failing:{connection.connection_id}",
                    kind="source_failing",
                    connection_id=connection.connection_id,
                    facts={
                        "connection_name": connection.display_name,
                        "error_code": runs[0].error_code,
                        "at": runs[0].finished_at.isoformat(timespec="seconds"),
                    },
                    basis=(runs[0].run_id,),
                )
            )
        sync = next((r for r in runs if r.kind == "sync" and r.status == "ok"), None)
        left_out = sync and sync.rows_unmatched + sync.rows_rejected + sync.rows_flagged
        if left_out:
            issues.append(
                Issue(
                    key=f"source_rows:{connection.connection_id}",
                    kind="source_rows_left_out",
                    connection_id=connection.connection_id,
                    facts={
                        "connection_name": connection.display_name,
                        "unmatched": sync.rows_unmatched,
                        "rejected": sync.rows_rejected,
                        "flagged": sync.rows_flagged,
                        "at": sync.finished_at.isoformat(timespec="seconds"),
                    },
                    basis=(sync.run_id,),
                )
            )
    return issues


def _imports(session: Session, merchants, org_users) -> list[Issue]:
    issues = []
    for batch in session.scalars(
        select(db.ImportBatch)
        .where(db.ImportBatch.record_type != "connector")
        .where(db.ImportBatch.rows_rejected + db.ImportBatch.rows_flagged > 0)
        .where(
            or_(
                db.ImportBatch.merchant_id.in_(list(merchants)),
                db.ImportBatch.merchant_id.is_(None) & db.ImportBatch.actor.in_(org_users),
            )
        )
        .order_by(db.ImportBatch.uploaded_at)
    ):
        issues.append(
            Issue(
                key=f"import:{batch.batch_id}",
                kind="import_rows_left_out",
                merchant_id=batch.merchant_id,
                batch_id=batch.batch_id,
                facts={
                    "file_name": batch.file_name,
                    "sheet_name": batch.sheet_name,
                    "record_type": batch.record_type,
                    "rejected": batch.rows_rejected,
                    "flagged": batch.rows_flagged,
                    "added": batch.rows_added,
                    "at": batch.uploaded_at.isoformat(timespec="seconds"),
                    "shop_name": merchants[batch.merchant_id][1].shop_name
                    if batch.merchant_id in merchants
                    else None,
                },
                basis=(batch.batch_id,),
            )
        )
    return issues


def _completeness(session: Session, config, merchants) -> list[Issue]:
    """Open applications without purchases or deliveries, or with only old purchases."""
    if not merchants:
        return []
    ids = list(merchants)
    end = calendar_end(config)
    stale_before = end - timedelta(days=int(config["quality"]["stale_after_days"]))
    applications = {
        a.merchant_id: a
        for a in session.scalars(select(db.Application).where(db.Application.merchant_id.in_(ids)))
    }
    decided: dict[str, Any] = {}
    for d in session.scalars(select(db.Decision).where(db.Decision.merchant_id.in_(ids))):
        decided[d.merchant_id] = max(decided.get(d.merchant_id, d.decided_at), d.decided_at)
    newest: dict[str, date] = {}
    for p in session.scalars(select(db.Purchase).where(db.Purchase.merchant_id.in_(ids))):
        if p.merchant_id not in newest or p.purchase_date > newest[p.merchant_id]:
            newest[p.merchant_id] = p.purchase_date
    has_delivery = set(
        session.scalars(select(db.Delivery.merchant_id).where(db.Delivery.merchant_id.in_(ids)))
    )
    issues = []
    for merchant_id, application in sorted(applications.items()):
        if merchant_id in decided and decided[merchant_id] >= application.entered_at:
            continue  # decided: the application is no longer open
        name = merchants[merchant_id][1].shop_name
        missing = [
            kind
            for kind, present in (
                ("purchases", merchant_id in newest),
                ("deliveries", merchant_id in has_delivery),
            )
            if not present
        ]
        if missing:
            issues.append(
                Issue(
                    key=f"missing:{merchant_id}",
                    kind="missing_evidence",
                    merchant_id=merchant_id,
                    facts={
                        "shop_name": name,
                        "missing": missing,
                        "application_id": application.application_id,
                    },
                    basis=tuple(missing),
                )
            )
        if merchant_id in newest and newest[merchant_id] < stale_before:
            issues.append(
                Issue(
                    key=f"stale:{merchant_id}",
                    kind="stale_evidence",
                    merchant_id=merchant_id,
                    facts={
                        "shop_name": name,
                        "newest": newest[merchant_id].isoformat(),
                        "days": (end - newest[merchant_id]).days,
                        "limit_days": int(config["quality"]["stale_after_days"]),
                    },
                    basis=(newest[merchant_id].isoformat(),),
                )
            )
    return issues


def _consent(session: Session, config, merchants) -> list[Issue]:
    """Shops with records entered in the app but no valid consent on the calendar's last day."""
    if not merchants:
        return []
    with_records = set(
        session.scalars(
            select(db.RecordProvenance.merchant_id)
            .where(db.RecordProvenance.merchant_id.in_(list(merchants)))
            .where(db.RecordProvenance.record_type.in_(("purchase", "delivery", "payment")))
        )
    )
    end = calendar_end(config)
    issues = []
    for merchant_id in sorted(with_records):
        valid, _ = consent_state(session, merchant_id, end)
        if valid:
            continue
        given = session.scalar(
            select(db.Consent.consent_id).where(db.Consent.merchant_id == merchant_id).limit(1)
        )
        issues.append(
            Issue(
                key=f"consent:{merchant_id}",
                kind="consent_lapsed",
                merchant_id=merchant_id,
                facts={
                    "shop_name": merchants[merchant_id][1].shop_name,
                    "state": "expired_or_revoked" if given else "none",
                },
                basis=("expired_or_revoked" if given else "none",),
            )
        )
    return issues


def find_issues(session: Session, config: dict[str, Any], org: str, scope) -> list[Issue]:
    """Every data-quality issue of one organisation. `scope` is its merchant condition."""
    merchants = _app_merchants(session, scope)
    connections = _connections(session, org)
    purchase_ids = set(
        session.scalars(
            select(db.Purchase.purchase_id).where(db.Purchase.merchant_id.in_(list(merchants)))
        )
    )
    origins = _origins(session, purchase_ids)
    default = config["organization"]["id"]
    org_users = select(db.User.user_id).where(
        db.User.organization_id == org
        if org != default
        else or_(db.User.organization_id.is_(None), db.User.organization_id == org)
    )
    return (
        _same_shops(merchants)
        + _withdrawn_links(session, connections, merchants)
        + _duplicate_records(session, merchants, origins)
        + _source_runs(session, connections)
        + _imports(session, merchants, org_users)
        + _completeness(session, config, merchants)
        + _consent(session, config, merchants)
    )


def latest_reviews(session: Session, org: str) -> dict[str, list[db.QualityReview]]:
    """issue key -> its reviews, oldest first."""
    out: dict[str, list[db.QualityReview]] = {}
    for row in session.scalars(
        select(db.QualityReview)
        .where(db.QualityReview.organization_id == org)
        .order_by(db.QualityReview.decided_at, db.QualityReview.review_id)
    ):
        out.setdefault(row.issue_key, []).append(row)
    return out


def status_of(issue: Issue, reviews: list[db.QualityReview]) -> str:
    """open | reviewed | changed (reviewed, but the evidence is no longer the same)."""
    if not reviews:
        return "open"
    return "reviewed" if reviews[-1].fingerprint == issue.fingerprint else "changed"


def settled(session: Session, key: str, basis: tuple) -> str | None:
    """The outcome of the latest review of an issue, if the evidence is still what the
    reviewer saw; otherwise None. Used so the workspace stops asking what a person answered."""
    latest = session.scalars(
        select(db.QualityReview)
        .where(db.QualityReview.issue_key == key)
        .order_by(db.QualityReview.decided_at.desc(), db.QualityReview.review_id.desc())
        .limit(1)
    ).first()
    if latest is None:
        return None
    current = Issue(key=key, kind=latest.kind, basis=basis).fingerprint
    return latest.outcome if latest.fingerprint == current else None


def summary(
    session: Session, config: dict[str, Any], org: str, scope
) -> tuple[int, int, dict[str, int]]:
    """(issues needing attention, problems confirmed, attention per group) for a dashboard."""
    reviews = latest_reviews(session, org)
    open_, concerns, by_group = 0, 0, {}
    for issue in find_issues(session, config, org, scope):
        mine = reviews.get(issue.key, [])
        if status_of(issue, mine) == "reviewed":
            concerns += mine[-1].outcome in CONCERNS
        else:
            open_ += 1
            by_group[issue.group] = by_group.get(issue.group, 0) + 1
    return open_, concerns, by_group
