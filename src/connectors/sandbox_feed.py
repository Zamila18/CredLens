"""The sandbox feed: a synthetic source that exercises the whole connector lifecycle.

It is not a provider and imitates none. Its rows are generated here, deterministically,
for three made-up shops, using its own field names. It exists so the shared machinery
(test, discovery, mapping, merchant matching, validation, duplicates, saving with
provenance, sync history, failure and recovery, revoking) can be used and tested end to
end before any real provider gives authorised access. It works only in a sandbox
organisation, and everything it saves is marked as synthetic.

Settings: `feed` picks the rows ("standard", or "with_problems" which adds rows that must
be refused), `fail_at` makes a step fail on purpose ("test" or "sync") to show recovery,
and an optional `secret_ref` shows how a credential is looked up without being stored.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from typing import Any

from src.connectors.base import Connector, ConnectorError, FetchContext, SettingField

FIELDS = [
    "shop_code",
    "shop_title",
    "area_district",
    "event_type",
    "event_date",
    "value",
    "parcel_status",
    "txn_id",
]

SHOPS = [
    ("SF-101", "Rahman General Store", "Sylhet"),
    ("SF-102", "Noor Traders", "Sylhet"),
    ("SF-103", "Karim Pharmacy", "Dhaka"),
]


def _rows(end: date, problems: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for code, title, district in SHOPS:
        seed = int(hashlib.sha256(code.encode()).hexdigest()[:6], 16)
        for i in range(3):
            day = end - timedelta(days=12 + 17 * i + seed % 5)
            rows.append(
                {
                    "shop_code": code,
                    "shop_title": title,
                    "area_district": district,
                    "event_type": "stock_order",
                    "event_date": day.isoformat(),
                    "value": f"{2500 + (seed % 900) + 610 * i:.2f}",
                    "parcel_status": "",
                    "txn_id": f"{code}-O{i + 1}",
                }
            )
        for i, status in enumerate(("delivered", "returned")):
            day = end - timedelta(days=8 + 21 * i)
            rows.append(
                {
                    "shop_code": code,
                    "shop_title": title,
                    "area_district": district,
                    "event_type": "parcel",
                    "event_date": day.isoformat(),
                    "value": "",
                    "parcel_status": status,
                    "txn_id": f"{code}-P{i + 1}",
                }
            )
    if problems:
        code, title, district = SHOPS[0]
        base = {
            "shop_code": code,
            "shop_title": title,
            "area_district": district,
            "parcel_status": "",
        }
        rows += [
            {
                **base,
                "event_type": "stock_order",
                "event_date": "not a date",
                "value": "100",
                "txn_id": f"{code}-X1",
            },
            {
                **base,
                "event_type": "stock_order",
                "event_date": end.isoformat(),
                "value": "-40",
                "txn_id": f"{code}-X2",
            },
            {
                **base,
                "event_type": "stock_order",
                "event_date": (end + timedelta(days=3)).isoformat(),
                "value": "300",
                "txn_id": f"{code}-X3",
            },
            {
                **base,
                "event_type": "stock_order",
                "event_date": end.isoformat(),
                "value": "120",
                "txn_id": f"{code}-O1",
            },
            {
                **base,
                "event_type": "refund",
                "event_date": end.isoformat(),
                "value": "50",
                "txn_id": f"{code}-X4",
            },
        ]
    return rows


class SandboxFeed(Connector):
    def _check(self, settings: dict[str, Any], context: FetchContext, step: str) -> None:
        if settings.get("secret_ref") and not context.secret:
            raise ConnectorError(
                "secret_missing",
                "The credential this connection points to is not set in the deployment.",
            )
        if settings.get("fail_at") == step:
            raise ConnectorError(
                "source_unavailable", f"The sandbox feed was set to fail at {step}."
            )

    def test(self, settings: dict[str, Any], context: FetchContext) -> None:
        self._check(settings, context, "test")

    def discover(self, settings: dict[str, Any], context: FetchContext) -> list[str]:
        self._check(settings, context, "discover")
        return list(FIELDS)

    def fetch(self, settings: dict[str, Any], context: FetchContext) -> list[dict[str, Any]]:
        self._check(settings, context, "sync")
        return _rows(
            date.fromisoformat(context.calendar_end), settings.get("feed") == "with_problems"
        )


SANDBOX_FEED = SandboxFeed(
    key="sandbox_feed",
    name="Sandbox test feed",
    name_bn="স্যান্ডবক্স পরীক্ষা-ফিড",
    category="test",
    description=(
        "Synthetic purchases and parcels for three made-up shops, to try the full connector "
        "lifecycle. Not a provider."
    ),
    description_bn=(
        "তিনটি বানানো দোকানের সিনথেটিক কেনাকাটা ও পার্সেল, "
        "সংযোগের পুরো প্রক্রিয়া পরীক্ষার জন্য। কোনো প্রোভাইডার নয়।"
    ),
    record_kinds=("purchase", "delivery"),
    auth="none",
    availability="available",
    sandbox_only=True,
    settings=(
        SettingField(
            "feed",
            "Rows to send",
            "কোন সারি পাঠাবে",
            "choice",
            True,
            ("standard", "with_problems"),
            "“with_problems” adds rows that must be refused.",
            "“with_problems” এমন সারি যোগ করে যা বাতিল হওয়ার কথা।",
        ),
        SettingField(
            "fail_at",
            "Fail on purpose at",
            "ইচ্ছে করে ব্যর্থ হবে",
            "choice",
            False,
            ("none", "test", "sync"),
            "To see how a failure is recorded and recovered.",
            "ব্যর্থতা কীভাবে রাখা ও সামলানো হয় দেখতে।",
        ),
        SettingField(
            "secret_ref",
            "Credential reference",
            "ক্রেডেনশিয়ালের রেফারেন্স",
            "secret_ref",
            False,
            (),
            "The name of an environment variable that holds a credential. "
            "The value is never stored or shown.",
            "যে এনভায়রনমেন্ট ভেরিয়েবলে ক্রেডেনশিয়াল আছে তার নাম। মান কখনো রাখা বা দেখানো হয় না।",
        ),
    ),
)
