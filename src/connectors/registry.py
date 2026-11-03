"""Every source CredLens knows, in one list.

- builtin: works today with no connection to set up (field entry, spreadsheets,
  institution files); each has its own screen.
- available: can be connected now (only the synthetic sandbox feed in this build).
- planned: the shape is known (category, records, how it would authenticate) but there is
  no authorised access and no implementation. Its test, discovery and fetch refuse with
  `not_available`; nothing here is a real API contract, credential or sample response.

Adding a provider: write a Connector subclass with its test, discover and fetch, set it to
"available" only after it has worked end to end with authorised access, and list it here.
"""

from __future__ import annotations

from src.connectors.base import Connector
from src.connectors.sandbox_feed import SANDBOX_FEED


def _builtin(
    key: str,
    name: str,
    name_bn: str,
    category: str,
    desc: str,
    desc_bn: str,
    kinds: tuple[str, ...],
) -> Connector:
    return Connector(
        key=key,
        name=name,
        name_bn=name_bn,
        category=category,
        description=desc,
        description_bn=desc_bn,
        record_kinds=kinds,
        availability="builtin",
    )


def _planned(
    key: str,
    name: str,
    name_bn: str,
    category: str,
    desc: str,
    desc_bn: str,
    kinds: tuple[str, ...],
    auth: str = "api_key",
    example: str | None = None,
) -> Connector:
    return Connector(
        key=key,
        name=name,
        name_bn=name_bn,
        category=category,
        description=desc,
        description_bn=desc_bn,
        record_kinds=kinds,
        auth=auth,
        availability="planned",
        example=example,
    )  # type: ignore[arg-type]


CONNECTORS: dict[str, Connector] = {
    c.key: c
    for c in [
        _builtin(
            "field_entry",
            "Field entry",
            "মাঠের এন্ট্রি",
            "manual",
            "Staff register shops and type in consent, purchases, deliveries, repayments "
            "and visits.",
            "কর্মী দোকান নিবন্ধন করে অনুমতি, কেনাকাটা, ডেলিভারি, পরিশোধ ও পরিদর্শন লেখেন।",
            ("merchant", "consent", "purchase", "delivery", "payment", "visit"),
        ),
        _builtin(
            "spreadsheet",
            "Spreadsheet import",
            "স্প্রেডশিট আমদানি",
            "file",
            "Excel purchase sheets for one shop: match the columns, check every row, then save.",
            "এক দোকানের এক্সেল কেনাকাটার শিট: কলাম মেলান, প্রতিটি সারি দেখুন, তারপর রাখুন।",
            ("purchase",),
        ),
        _builtin(
            "institution_files",
            "Institution files",
            "প্রতিষ্ঠানের ফাইল",
            "institutional",
            "An institution’s own merchant, loan and repayment files in the documented CSV format.",
            "নির্দিষ্ট CSV ফরম্যাটে প্রতিষ্ঠানের নিজস্ব মার্চেন্ট, ঋণ ও পরিশোধের ফাইল।",
            ("merchant", "loan", "payment", "purchase", "delivery"),
        ),
        SANDBOX_FEED,
        _planned(
            "wholesale_platform",
            "Wholesale and commerce platform",
            "পাইকারি ও কমার্স প্ল্যাটফর্ম",
            "platform",
            "Stock orders a shop places on a B2B platform.",
            "B2B প্ল্যাটফর্মে দোকানের মালের অর্ডার।",
            ("purchase",),
            "oauth2",
            "For example ShopUp / Mokam",
        ),
        _planned(
            "shop_credit",
            "Shop-credit service",
            "দোকান-ঋণ সেবা",
            "financial",
            "Earlier credit lines and their repayments.",
            "আগের ঋণ ও তার পরিশোধ।",
            ("loan", "payment"),
            "oauth2",
            "For example Baki",
        ),
        _planned(
            "logistics",
            "Logistics provider",
            "লজিস্টিকস প্রোভাইডার",
            "logistics",
            "Parcels a shop sends and cash collected on delivery.",
            "দোকানের পাঠানো পার্সেল ও ডেলিভারিতে নেওয়া টাকা।",
            ("delivery",),
            "api_key",
            "For example REDX",
        ),
        _planned(
            "retail_pos",
            "Retail POS",
            "রিটেইল POS",
            "pos",
            "Sales-side records from a point-of-sale system.",
            "পয়েন্ট-অফ-সেল সিস্টেমের বিক্রির রেকর্ড।",
            ("sale",),
        ),
        _planned(
            "distributor",
            "Distributor system",
            "ডিস্ট্রিবিউটর সিস্টেম",
            "distributor",
            "Orders and deliveries recorded by a distributor.",
            "ডিস্ট্রিবিউটরের রাখা অর্ডার ও ডেলিভারি।",
            ("purchase", "delivery"),
        ),
        _planned(
            "accounting",
            "Accounting software",
            "হিসাব-সফটওয়্যার",
            "accounting",
            "Books kept by the business or its accountant.",
            "ব্যবসা বা তার হিসাবরক্ষকের রাখা খাতা।",
            ("purchase", "payment"),
            "oauth2",
        ),
        _planned(
            "payments",
            "Payment records",
            "পেমেন্ট রেকর্ড",
            "financial",
            "Payments received and made through a provider.",
            "প্রোভাইডারের মাধ্যমে নেওয়া ও দেওয়া পেমেন্ট।",
            ("payment",),
        ),
    ]
}


def connector(key: str) -> Connector | None:
    return CONNECTORS.get(key)
