"""The shared half of every connector: from a source's rows to saved, traceable evidence.

Steps, the same for every source:
1. Mapping: the person says which source field is which CredLens field (suggested from
   the field names). The mapping is checked: every required field must be chosen once.
2. Normalisation: dates and amounts are read defensively; the source's record kind is
   turned into CredLens's own kinds (purchase, delivery), never into one vague transaction.
3. Merchant matching: a row belongs to a merchant only through a link a person confirmed
   (source_merchant_links). Without one the row is "unmatched" and nothing is saved; the
   likely candidates (same name and district, inside the organisation) are shown for a
   person to confirm or reject. Nothing is ever linked automatically.
4. Validation: the business calendar, positive amounts, a known delivery status, and the
   merchant's consent for that kind of record.
5. Duplicates: a row's CredLens id comes from the connection and the source's own id, so a
   repeated sync adds nothing; the same source id twice in one fetch is refused; a purchase
   with the same date and amount as one already saved is flagged and left out.
6. Saving, all or nothing: the records, their provenance, their lineage (which source row,
   with a fingerprint of the row as received), an import batch, the run, and an audit entry.
   A failure at any point saves no record and leaves a failed run with its error.

Everything here is scoped to the connection's organisation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import CurrentUser, add_audit
from src.api.importer import DELIVERY_STATUSES
from src.connectors.base import Connector, ConnectorError, FetchContext
from src.db import models as db
from src.intake.consent import require_consent_for
from src.intake.merchants import likely_duplicates, normalised
from src.intake.policy import IntakeRefused, add_provenance, calendar_end, new_id, utc_now
from src.intake.records import check_scoring_inputs
from src.intake.spreadsheet import parse_amount, parse_date

FIELDS = (
    "merchant_ref",
    "merchant_name",
    "district",
    "record_kind",
    "business_date",
    "amount",
    "delivery_status",
    "source_reference",
)
REQUIRED = ("merchant_ref", "record_kind", "business_date", "source_reference")

SYNONYMS = {
    "merchant_ref": (
        "merchant_ref",
        "shop_code",
        "merchant_id",
        "store_id",
        "customer_id",
        "outlet_code",
    ),
    "merchant_name": (
        "merchant_name",
        "shop_title",
        "shop_name",
        "store_name",
        "business_name",
        "name",
    ),
    "district": ("district", "area_district", "city", "region", "location"),
    "record_kind": ("record_kind", "event_type", "type", "kind", "record_type"),
    "business_date": ("business_date", "event_date", "date", "order_date", "created_on"),
    "amount": ("amount", "value", "total", "amount_bdt", "order_value"),
    "delivery_status": ("delivery_status", "parcel_status", "status", "shipment_status"),
    "source_reference": ("source_reference", "txn_id", "order_id", "reference", "id"),
}

# How a source may name its record kinds -> CredLens's kinds. Anything else is refused.
KINDS = {
    "purchase": "purchase",
    "stock_order": "purchase",
    "order": "purchase",
    "purchase_order": "purchase",
    "delivery": "delivery",
    "parcel": "delivery",
    "shipment": "delivery",
}


def suggest_mapping(fields: list[str]) -> dict[str, str | None]:
    lowered = {f.lower(): f for f in fields}
    mapping: dict[str, str | None] = {}
    used: set[str] = set()
    for name in FIELDS:
        found = next(
            (lowered[w] for w in SYNONYMS[name] if w in lowered and lowered[w] not in used), None
        )
        mapping[name] = found
        if found:
            used.add(found)
    return mapping


def check_mapping(mapping: dict[str, str | None], fields: list[str]) -> dict[str, str | None]:
    unknown = sorted(k for k in mapping if k not in FIELDS)
    if unknown:
        raise IntakeRefused(422, "unknown_field", f"Unknown field(s): {', '.join(unknown)}.")
    clean = {k: (mapping.get(k) or None) for k in FIELDS}
    for name in REQUIRED:
        if not clean[name]:
            raise IntakeRefused(
                422,
                "missing_column",
                "Choose the source fields for every required item.",
                field=name,
            )
    chosen = [v for v in clean.values() if v]
    if any(v not in fields for v in chosen):
        raise IntakeRefused(422, "missing_column", "A chosen field is not sent by this source.")
    if len(set(chosen)) != len(chosen):
        raise IntakeRefused(
            422, "column_used_twice", "Each source field can be used for one item only."
        )
    return clean


def confirmed_links(
    session: Session, connection: db.SourceConnection
) -> dict[str, db.SourceMerchantLink]:
    """The latest decision per external reference (a later decision replaces an earlier one)."""
    latest: dict[str, db.SourceMerchantLink] = {}
    for row in session.scalars(
        select(db.SourceMerchantLink)
        .where(db.SourceMerchantLink.connection_id == connection.connection_id)
        .order_by(db.SourceMerchantLink.id)
    ):
        latest[row.external_ref] = row
    return latest


@dataclass
class Row:
    index: int
    outcome: str  # add | skip | flag | reject | unmatched
    code: str
    external_ref: str | None = None
    merchant_name: str | None = None
    district: str | None = None
    merchant_id: str | None = None
    kind: str | None = None
    business_date: date | None = None
    amount: float | None = None
    delivery_status: str | None = None
    source_reference: str | None = None
    record_id: str | None = None
    raw_sha256: str = ""


@dataclass
class Plan:
    rows: list[Row] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out = {"add": 0, "skip": 0, "flag": 0, "reject": 0, "unmatched": 0}
        for row in self.rows:
            out[row.outcome] += 1
        return out


def _text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def plan_rows(
    session: Session,
    config: dict[str, Any],
    connection: db.SourceConnection,
    raw: list[dict[str, Any]],
    mapping: dict[str, str | None],
) -> Plan:
    """What would happen to every fetched row. Writes nothing."""
    end = calendar_end(config)
    links = confirmed_links(session, connection)
    plan = Plan()
    seen_refs: set[str] = set()
    existing_values: dict[str, set[tuple[date, float]]] = {}

    def value(row: dict[str, Any], name: str) -> Any:
        column = mapping.get(name)
        return row.get(column) if column else None

    for index, source in enumerate(raw):
        row = Row(index=index, outcome="reject", code="")
        row.raw_sha256 = hashlib.sha256(
            json.dumps(source, sort_keys=True, default=str).encode()
        ).hexdigest()
        row.external_ref = _text(value(source, "merchant_ref"))
        row.merchant_name = _text(value(source, "merchant_name"))
        row.district = _text(value(source, "district"))
        row.source_reference = _text(value(source, "source_reference"))
        kind_text = (_text(value(source, "record_kind")) or "").lower()
        row.kind = KINDS.get(kind_text)
        row.business_date, _ = parse_date(value(source, "business_date"), "auto")
        row.amount = parse_amount(value(source, "amount"))
        row.delivery_status = (_text(value(source, "delivery_status")) or "").lower() or None
        plan.rows.append(row)

        if not row.external_ref or not row.source_reference:
            row.code = "missing_reference"
        elif row.kind is None:
            row.code = "unsupported_kind"
        elif row.business_date is None:
            row.code = "bad_date"
        elif row.business_date > end:
            row.code = "date_after_calendar"
        elif row.kind == "purchase" and (row.amount is None or row.amount <= 0):
            row.code = "bad_amount"
        elif row.kind == "delivery" and row.delivery_status not in DELIVERY_STATUSES:
            row.code = "bad_status"
        elif row.source_reference in seen_refs:
            row.code = "reference_twice_in_source"
        if row.code:
            continue
        seen_refs.add(row.source_reference)

        link = links.get(row.external_ref)
        if link is None or link.decision != "confirmed" or not link.merchant_id:
            row.outcome, row.code = (
                "unmatched",
                ("match_rejected" if link and link.decision == "rejected" else "needs_match"),
            )
            continue
        row.merchant_id = link.merchant_id
        try:
            require_consent_for(
                session,
                config,
                row.merchant_id,
                "purchases" if row.kind == "purchase" else "deliveries",
            )
        except IntakeRefused as refused:
            row.code = refused.code
            continue
        prefix = "PU" if row.kind == "purchase" else "DL"
        digest = hashlib.sha256(
            f"{connection.connection_id}|{row.source_reference}".encode()
        ).hexdigest()
        row.record_id = f"{prefix}-{digest[:24]}"
        model = db.Purchase if row.kind == "purchase" else db.Delivery
        if session.get(model, row.record_id) is not None:
            row.outcome, row.code = "skip", "already_synced"
            continue
        if row.kind == "purchase":
            if row.merchant_id not in existing_values:
                existing_values[row.merchant_id] = {
                    (p.purchase_date, round(p.amount_bdt, 2))
                    for p in session.scalars(
                        select(db.Purchase).where(db.Purchase.merchant_id == row.merchant_id)
                    )
                }
            key = (row.business_date, round(row.amount or 0, 2))
            if key in existing_values[row.merchant_id]:
                row.outcome, row.code = "flag", "possible_duplicate"
                continue
            existing_values[row.merchant_id].add(key)
        row.outcome, row.code = "add", "new"
    return plan


def candidates(
    session: Session, config: dict[str, Any], org_scope: Any, name: str | None, district: str | None
) -> list[dict[str, Any]]:
    """Merchants of the organisation that look like the source's merchant (same name and
    district, compared loosely). A suggestion for a person, never a link."""
    if not name or not district:
        return []
    return likely_duplicates(session, name, district, org_scope)


def save(
    session: Session,
    config: dict[str, Any],
    connection: db.SourceConnection,
    connector: Connector,
    plan: Plan,
    run: db.SourceRun,
    actor: CurrentUser,
) -> None:
    """Save the rows to add, with provenance, lineage, a batch and an audit entry.

    All or nothing.
    """
    keep = [r for r in plan.rows if r.outcome == "add"]
    now = utc_now()
    batch = db.ImportBatch(
        batch_id=new_id("IB"),
        actor=actor.user_id,
        merchant_id=None,
        record_type="connector",
        file_name=connection.display_name[:128],
        file_sha256=hashlib.sha256("".join(r.raw_sha256 for r in plan.rows).encode()).hexdigest(),
        sheet_name=connector.key,
        mapping_sha256=run.run_id,
        uploaded_at=now,
        rows_added=len(keep),
        rows_skipped=sum(r.outcome == "skip" for r in plan.rows),
        rows_flagged=sum(r.outcome == "flag" for r in plan.rows),
        rows_rejected=sum(r.outcome == "reject" for r in plan.rows),
        status="committed",
    )
    session.add(batch)
    session.flush()
    for row in keep:
        if row.kind == "purchase":
            session.add(
                db.Purchase(
                    purchase_id=row.record_id,
                    merchant_id=row.merchant_id,
                    purchase_date=row.business_date,
                    amount_bdt=float(row.amount),
                    category=None,
                    supplier_id=None,
                )
            )
        else:
            at = datetime.combine(row.business_date, time(10, 0))
            session.add(
                db.Delivery(
                    delivery_id=row.record_id,
                    merchant_id=row.merchant_id,
                    dispatched_at=at,
                    delivered_at=at if row.delivery_status == "delivered" else None,
                    status=row.delivery_status,
                    return_reason=None,
                    is_cod=False,
                    cod_remitted_on_time=None,
                )
            )
        # Only the synthetic sandbox feed can save today, so its records are synthetic.
        add_provenance(
            session,
            record_type=row.kind,
            record_id=row.record_id,
            merchant_id=row.merchant_id,
            source_category="purchases" if row.kind == "purchase" else "deliveries",
            entry_method="synthetic_demo",
            status="synthetic_demo",
            actor=actor.user_id,
            entered_at=now,
            business_date=row.business_date,
            batch_id=batch.batch_id,
        )
        session.add(
            db.SourceRecord(
                organization_id=connection.organization_id,
                connection_id=connection.connection_id,
                run_id=run.run_id,
                record_type=row.kind,
                record_id=row.record_id,
                merchant_id=row.merchant_id,
                source_reference=row.source_reference,
                raw_sha256=row.raw_sha256,
                received_at=now,
            )
        )
    session.flush()
    for merchant_id in sorted({r.merchant_id for r in keep}):
        check_scoring_inputs(session, config, merchant_id)
    for merchant_id in sorted({r.merchant_id for r in keep}):
        add_audit(session, actor, "source_sync", merchant_id)


def context(
    config: dict[str, Any], connection: db.SourceConnection, secret: str | None
) -> FetchContext:
    return FetchContext(
        organization_id=connection.organization_id,
        calendar_end=config["demo"]["calendar_end"],
        secret=secret,
    )


def settings_of(connection: db.SourceConnection) -> dict[str, Any]:
    settings = json.loads(connection.settings_json or "{}")
    if connection.secret_ref:
        settings["secret_ref"] = connection.secret_ref
    return settings


__all__ = [
    "FIELDS",
    "REQUIRED",
    "ConnectorError",
    "Plan",
    "Row",
    "candidates",
    "check_mapping",
    "confirmed_links",
    "context",
    "normalised",
    "plan_rows",
    "save",
    "settings_of",
    "suggest_mapping",
]
