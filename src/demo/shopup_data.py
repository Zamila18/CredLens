# ruff: noqa: E501  (the sample data and stories are prose; long lines are intended)
"""The made-up cast of the demonstration: the lender "ShopUp", its people and nine shops.

Purpose: one place for everything the demo shows, so a story can be changed without touching
    the code that builds it. Every name, number, address and registration here is invented for
    the demonstration; none of it is real data about ShopUp, its staff or any shop.
Owner role: D (full-stack).
Implements: the demonstration database for the project video.

Each shop is described by how it behaves (how much it buys, how steadily, from whom, how it
repaid earlier loans, how its parcels went), not by the score it should get. The real model
reads the records the seed writes; the data is tuned so the stories are believable, and the
scores are whatever the model says.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

DOMAIN = "shopup.com"
CREDIT_PASSWORD = "ShopUp@Credit2026"
DESK_PASSWORD = "ShopUp@Records2026"

COMPANY = {
    "legal_name": "ShopUp Finance Limited",
    "trading_name": "ShopUp",
    "registration_number": "C-231846/2023",
    "org_type": "fintech_lender",
    "sector": "Working-capital credit for retail shops",
    "official_email": f"credit@{DOMAIN}",
    "contact_number": "09612345600",
    "country": "BD",
    "division": "Dhaka",
    "city": "Dhaka",
    "address": "House 14, Road 11, Banani, Dhaka 1213",
    "website": "https://shopup.com",
}


@dataclass(frozen=True)
class Person:
    name: str
    email: str
    mobile: str
    role: str  # credit_officer | records_officer
    title: str
    department: str
    employee_id: str
    password: str
    owner: bool = False


STAFF = [
    Person(
        "Jawad Hasan",
        f"jawad@{DOMAIN}",
        "01712340101",
        "credit_officer",
        "Head of Credit",
        "Credit",
        "CR-001",
        CREDIT_PASSWORD,
        True,
    ),
    Person(
        "Sadia Rahman",
        f"sadia@{DOMAIN}",
        "01712340102",
        "credit_officer",
        "Senior Credit Officer",
        "Credit",
        "CR-002",
        CREDIT_PASSWORD,
    ),
    Person(
        "Tanvir Ahmed",
        f"tanvir@{DOMAIN}",
        "01712340103",
        "credit_officer",
        "Credit Officer",
        "Credit",
        "CR-003",
        CREDIT_PASSWORD,
    ),
    Person(
        "Nusrat Jahan",
        f"nusrat@{DOMAIN}",
        "01712340201",
        "records_officer",
        "Records Desk Lead",
        "Records",
        "RD-101",
        DESK_PASSWORD,
    ),
    Person(
        "Imran Hossain",
        f"imran@{DOMAIN}",
        "01712340202",
        "records_officer",
        "Records Officer",
        "Records",
        "RD-102",
        DESK_PASSWORD,
    ),
    Person(
        "Mahfuza Khatun",
        f"mahfuza@{DOMAIN}",
        "01712340203",
        "records_officer",
        "Records Officer",
        "Records",
        "RD-103",
        DESK_PASSWORD,
    ),
]

# ShopUp's range policy (demonstration values: a real lender sets its own).
POLICY = {
    "window_days": 180,
    "min_verified_months": 4,
    "min_purchase_records": 8,
    "multiples_by_band": {"Strong": [0.5, 1.0], "Review": [0.25, 0.5]},
    "round_to_bdt": 5000,
    "cap_at_requested": True,
}


@dataclass(frozen=True)
class Good:
    en: str
    bn: str
    unit: str
    low: int
    high: int


CATALOG: dict[str, list[Good]] = {
    "grocery": [
        Good("Miniket rice", "মিনিকেট চাল", "sack", 2900, 3400),
        Good("Soybean oil", "সয়াবিন তেল", "ltr", 160, 185),
        Good("Sugar", "চিনি", "kg", 118, 128),
        Good("Red lentil", "মসুর ডাল", "kg", 120, 150),
        Good("Wheat flour", "আটা", "kg", 52, 64),
        Good("Salt", "লবণ", "kg", 36, 44),
        Good("Tea leaf", "চা পাতা", "kg", 420, 520),
        Good("Turmeric powder", "হলুদ গুঁড়া", "kg", 260, 320),
        Good("Powder milk", "গুঁড়া দুধ", "kg", 780, 860),
        Good("Noodles carton", "নুডলস কার্টন", "carton", 1150, 1320),
    ],
    "pharmacy": [
        Good("Paracetamol 500mg", "প্যারাসিটামল ৫০০", "box", 380, 440),
        Good("Antacid syrup", "অ্যান্টাসিড সিরাপ", "box", 520, 610),
        Good("ORS saline", "খাবার স্যালাইন", "box", 310, 360),
        Good("Vitamin C tablets", "ভিটামিন সি", "box", 640, 760),
        Good("Surgical mask", "সার্জিক্যাল মাস্ক", "box", 180, 230),
        Good("Digital thermometer", "ডিজিটাল থার্মোমিটার", "pcs", 210, 260),
        Good("Baby diaper", "বেবি ডায়াপার", "pack", 540, 640),
        Good("Antiseptic liquid", "অ্যান্টিসেপটিক", "box", 290, 350),
    ],
    "electronics": [
        Good("Phone charger", "ফোন চার্জার", "pcs", 220, 290),
        Good("Earphones", "ইয়ারফোন", "pcs", 160, 230),
        Good("Power bank 10000mAh", "পাওয়ার ব্যাংক", "pcs", 980, 1250),
        Good("LED bulb 9W", "এলইডি বাল্ব", "pcs", 95, 130),
        Good("USB cable", "ইউএসবি ক্যাবল", "pcs", 60, 90),
        Good("AA battery pack", "ব্যাটারি প্যাক", "pack", 120, 160),
        Good("Phone cover", "ফোন কভার", "pcs", 70, 110),
    ],
    "apparel": [
        Good("Cotton fabric", "সুতি কাপড়", "yard", 190, 260),
        Good("Panjabi", "পাঞ্জাবি", "pcs", 780, 1150),
        Good("Saree", "শাড়ি", "pcs", 950, 1650),
        Good("Kids frock", "বাচ্চাদের ফ্রক", "pcs", 380, 520),
        Good("Salwar kameez set", "সালোয়ার কামিজ", "pcs", 920, 1300),
        Good("Ladies scarf", "স্কার্ফ", "pcs", 120, 190),
    ],
    "stationery": [
        Good("Exercise book dozen", "খাতা ডজন", "dozen", 520, 640),
        Good("Ball pen box", "বল পেন বক্স", "box", 110, 150),
        Good("A4 paper ream", "এ৪ কাগজ রিম", "ream", 460, 520),
        Good("File folder", "ফাইল ফোল্ডার", "pcs", 28, 40),
        Good("Marker pen box", "মার্কার বক্স", "box", 180, 240),
        Good("Geometry box", "জ্যামিতি বক্স", "pcs", 95, 140),
    ],
    "hardware": [
        Good("Cement bag", "সিমেন্ট ব্যাগ", "bag", 520, 580),
        Good("Wall paint 4 ltr", "দেয়ালের রং ৪ লি.", "can", 1650, 1950),
        Good("Nails", "পেরেক", "kg", 105, 130),
        Good("Electric wire coil", "বৈদ্যুতিক তার", "coil", 1750, 2150),
        Good("Door hinge", "দরজার কব্জা", "pcs", 38, 58),
        Good("Padlock", "তালা", "pcs", 160, 260),
    ],
    "cosmetics": [
        Good("Body lotion", "বডি লোশন", "pcs", 180, 260),
        Good("Shampoo bottle", "শ্যাম্পু", "pcs", 145, 215),
        Good("Baby powder", "বেবি পাউডার", "pcs", 130, 180),
        Good("Soap carton", "সাবান কার্টন", "carton", 720, 860),
        Good("Face wash", "ফেস ওয়াশ", "pcs", 150, 230),
        Good("Baby oil", "বেবি অয়েল", "pcs", 160, 210),
    ],
    "tea": [
        Good("Tea leaf", "চা পাতা", "kg", 420, 520),
        Good("Biscuit carton", "বিস্কুট কার্টন", "carton", 880, 1060),
        Good("Noodles carton", "নুডলস কার্টন", "carton", 1150, 1320),
        Good("Soft drink crate", "ড্রিংক ক্রেট", "crate", 640, 740),
        Good("Chanachur carton", "চানাচুর কার্টন", "carton", 760, 880),
        Good("Sugar", "চিনি", "kg", 118, 128),
    ],
}


@dataclass(frozen=True)
class LoanSpec:
    issued_days_ago: int
    limit: int
    instalments: int
    delays: tuple[int, ...]  # days after each due date that the instalment was paid


@dataclass(frozen=True)
class ParcelSpec:
    per_week: float
    returned: float
    failed: float
    cod_share: float = 0.6


@dataclass
class Shop:
    key: str
    name: str
    owner: str
    mobile: str
    district: str
    area: str
    shop_type: str  # grocery | pharmacy | apparel | electronics | other
    catalog: str
    portal: str  # the 8 characters after MR in the Merchant ID
    onboard_days_ago: int
    creator: int  # index into the credit team: who registers the shop
    verifier: int  # who verifies the consent form
    suppliers: list[str]
    established: int = 2018
    licence: str = ""
    history_days: int = 0  # receipts reach back this far (0: no receipts yet)
    month_base: int = 100_000  # purchases in a typical month, BDT
    growth: float = 0.0  # monthly growth of purchases
    volatility: float = 0.15  # week-to-week spread
    eid_spike: bool = False
    per_week: float = 0.9  # purchase receipts per week
    regularity: float = 0.95  # chance that a week has a receipt
    language: str = "en"  # en | bn | mixed (language printed on its receipts)
    parcels: ParcelSpec | None = None
    loans: list[LoanSpec] = field(default_factory=list)
    questionnaire: dict[str, int] | None = None
    application: tuple[int, str, int, str] | None = None  # (amount, purpose, days ago, via)
    decision: tuple[str, str] | None = None  # (action, written reason)
    visit_days_ago: int | None = None
    confirm_share: float = 0.7  # share of receipts the owner marked "looks right"
    pending: int = 0  # receipts waiting at the Records Desk (read by the reader, unchecked)
    pending_day: int = 1  # ... uploaded this many days ago
    dispute: str | None = None  # "open" | "resolved"
    registration_only: bool = False  # signed form read, waiting for verification
    ownership: str = "sole_proprietor"
    branches: int = 1


def _q(
    spend: int, save: int, borrow: int, plan: int, stress: int, confidence: int
) -> dict[str, int]:
    return dict(
        spend1=spend,
        spend2=spend,
        save1=save,
        save2=max(1, save - 1),
        borrow1=borrow,
        borrow2=borrow,
        plan1=plan,
        plan2=plan,
        stress=stress,
        confidence=confidence,
    )


SHOPS: list[Shop] = [
    Shop(
        key="bhai",
        name="Bhai Bhai General Store",
        owner="Abdul Karim",
        mobile="01811000101",
        district="Dhaka",
        area="Kawran Bazar",
        shop_type="grocery",
        catalog="grocery",
        portal="BHAI4K72",
        onboard_days_ago=250,
        creator=0,
        verifier=1,
        established=2014,
        licence="DNCC/TL/2019/48213",
        suppliers=["Hasan Traders", "Karim Wholesale Depot", "Metro Food Distribution"],
        history_days=285,
        month_base=200_000,
        growth=0.035,
        volatility=0.12,
        per_week=1.0,
        regularity=0.97,
        parcels=ParcelSpec(2.5, 0.04, 0.02, 0.6),
        loans=[LoanSpec(330, 100_000, 3, (0, 1, 0)), LoanSpec(190, 150_000, 3, (1, 0, 2))],
        questionnaire=_q(4, 4, 4, 4, 2, 4),
        application=(150_000, "inventory_restock", 3, "portal"),
        visit_days_ago=10,
        confirm_share=0.75,
        language="en",
    ),
    Shop(
        key="nirjhor",
        name="Nirjhor Pharmacy",
        owner="Farhana Yasmin",
        mobile="01811000102",
        district="Dhaka",
        area="Mirpur 10",
        shop_type="pharmacy",
        catalog="pharmacy",
        portal="NIRJ7H3K",
        onboard_days_ago=225,
        creator=1,
        verifier=0,
        established=2016,
        licence="DGDA/R/2021/9034",
        suppliers=["Mirpur Medical Supply", "Dhaka Pharma Traders", "Lifeline Distribution"],
        history_days=255,
        month_base=160_000,
        growth=0.015,
        volatility=0.14,
        per_week=0.9,
        regularity=0.95,
        loans=[LoanSpec(300, 80_000, 3, (0, 2, 1))],
        questionnaire=_q(4, 3, 4, 4, 2, 4),
        application=(120_000, "inventory_restock", 4, "portal"),
        visit_days_ago=14,
        dispute="open",
        language="mixed",
    ),
    Shop(
        key="rahman",
        name="Rahman Electronics",
        owner="Mizanur Rahman",
        mobile="01811000103",
        district="Chattogram",
        area="Agrabad",
        shop_type="electronics",
        catalog="electronics",
        portal="RAHM9T4N",
        onboard_days_ago=205,
        creator=2,
        verifier=1,
        established=2012,
        licence="CCC/TL/2020/17745",
        suppliers=[
            "Chawkbazar Electronics Hub",
            "Agrabad Trade Centre",
            "Station Road Mobile Mart",
            "Jamal Khan Road Traders",
            "Dewanhat Wholesale",
            "Patenga Import House",
            "Bahaddarhat Gadgets",
            "Reazuddin Bazar Supply",
        ],
        history_days=240,
        month_base=230_000,
        growth=0.0,
        volatility=0.38,
        per_week=0.8,
        regularity=0.8,
        parcels=ParcelSpec(3.0, 0.12, 0.07, 0.7),
        loans=[LoanSpec(300, 150_000, 3, (9, 14, 12)), LoanSpec(170, 200_000, 2, (16, 21))],
        questionnaire=_q(3, 2, 3, 3, 4, 3),
        application=(200_000, "inventory_restock", 6, "officer"),
        visit_days_ago=20,
        dispute="resolved",
        confirm_share=0.4,
        language="en",
        ownership="partnership",
    ),
    Shop(
        key="sylhet",
        name="Sylhet Fashion House",
        owner="Shamima Akter",
        mobile="01811000104",
        district="Sylhet",
        area="Zindabazar",
        shop_type="apparel",
        catalog="apparel",
        portal="SYLF2M8R",
        onboard_days_ago=195,
        creator=0,
        verifier=2,
        established=2017,
        licence="SCC/TL/2021/30912",
        suppliers=[
            "Narayanganj Cloth Mart",
            "Sylhet Garments Supply",
            "Mirpur Saree Palace",
            "Zindabazar Fabrics",
            "Dhaka Textile Hub",
            "Bongo Bazar Wholesale",
            "Eid Collection Traders",
            "Islampur Cloth House",
            "Bangla Saree Corner",
            "Mymensingh Fabric Depot",
            "Tangail Handloom Supply",
            "Gulshan Scarf Traders",
            "Chittagong Road Garments",
        ],
        history_days=230,
        month_base=150_000,
        growth=0.0,
        volatility=0.45,
        eid_spike=True,
        per_week=0.7,
        regularity=0.7,
        parcels=ParcelSpec(1.8, 0.1, 0.04, 0.5),
        loans=[LoanSpec(280, 70_000, 3, (3, 8, 5))],
        questionnaire=_q(3, 3, 3, 3, 3, 3),
        application=(100_000, "seasonal_stock", 75, "officer"),
        decision=(
            "needs_more_info",
            "Purchases swing a lot with the festival season. Asked for the next two months of receipts before deciding.",
        ),
        visit_days_ago=80,
        confirm_share=0.5,
        language="bn",
    ),
    Shop(
        key="khulna",
        name="Khulna Stationery Corner",
        owner="Rafiqul Islam",
        mobile="01811000105",
        district="Khulna",
        area="Sonadanga",
        shop_type="other",
        catalog="stationery",
        portal="KHUL6P2D",
        onboard_days_ago=170,
        creator=1,
        verifier=2,
        established=2019,
        suppliers=["Khulna Paper House", "Jessore Road Book Depot"],
        parcels=ParcelSpec(1.2, 0.03, 0.01, 0.5),
        history_days=205,
        month_base=65_000,
        growth=0.01,
        volatility=0.12,
        per_week=1.0,
        regularity=0.88,
        questionnaire=_q(4, 4, 3, 4, 2, 4),
        application=(60_000, "inventory_restock", 2, "portal"),
        visit_days_ago=12,
        language="en",
    ),
    Shop(
        key="rajshahi",
        name="Rajshahi Agro and Grocery",
        owner="Tanvir Hossain",
        mobile="01811000106",
        district="Rajshahi",
        area="Shaheb Bazar",
        shop_type="grocery",
        catalog="grocery",
        portal="RAJS8W5C",
        onboard_days_ago=55,
        creator=2,
        verifier=0,
        established=2024,
        suppliers=["Rajshahi Rice Depot", "Boalia Wholesale"],
        history_days=48,
        month_base=95_000,
        growth=0.0,
        volatility=0.14,
        per_week=1.0,
        regularity=0.95,
        application=(80_000, "inventory_restock", 1, "portal"),
        language="bn",
    ),
    Shop(
        key="bogura",
        name="Bogura Hardware and Paints",
        owner="Abul Kashem",
        mobile="01811000107",
        district="Bogura",
        area="Sherpur Road",
        shop_type="other",
        catalog="hardware",
        portal="BOGU3Y9F",
        onboard_days_ago=150,
        creator=0,
        verifier=1,
        established=2015,
        suppliers=["Bogura Cement Agency", "North Bengal Paints", "Sherpur Hardware Wholesale"],
        history_days=190,
        month_base=135_000,
        growth=0.02,
        volatility=0.16,
        per_week=0.8,
        regularity=0.9,
        loans=[LoanSpec(260, 90_000, 3, (2, 1, 3))],
        questionnaire=_q(4, 3, 4, 4, 2, 4),
        application=(110_000, "shop_equipment", 70, "officer"),
        decision=(
            "accept",
            "Steady purchases for six months and the earlier loan was repaid within days of each due date. Agreed to proceed.",
        ),
        visit_days_ago=75,
        pending=2,
        pending_day=1,
        language="mixed",
    ),
    Shop(
        key="gazipur",
        name="Gazipur Baby and Beauty Care",
        owner="Nasrin Sultana",
        mobile="01811000108",
        district="Gazipur",
        area="Tongi Bazar",
        shop_type="other",
        catalog="cosmetics",
        portal="GAZI5V7B",
        onboard_days_ago=12,
        creator=1,
        verifier=0,
        established=2022,
        suppliers=["Tongi Beauty Wholesale", "Gazipur Baby Mart"],
        history_days=24,
        month_base=70_000,
        per_week=1.6,
        regularity=1.0,
        pending=3,
        pending_day=1,
        language="en",
    ),
    Shop(
        key="cumilla",
        name="Cumilla Tea and Snacks",
        owner="Jahangir Alam",
        mobile="01811000109",
        district="Cumilla",
        area="Kandirpar",
        shop_type="grocery",
        catalog="tea",
        portal="CUMI4X6J",
        onboard_days_ago=3,
        creator=2,
        verifier=0,
        established=2020,
        suppliers=["Cumilla Tea Traders"],
        registration_only=True,
    ),
]

PURPOSE_NOTES = {
    "inventory_restock": "Restocking before the next trading season.",
    "seasonal_stock": "Stock for the festival season.",
    "shop_equipment": "New shelving and a display counter.",
    "other": "",
}


# --- generating what the shops did ---------------------------------------------------------


@dataclass
class ReceiptPlan:
    kind: str  # purchase | delivery
    day: date  # the date on the paper
    supplier: str
    memo_no: str
    language: str
    lines: list[
        dict
    ]  # item, quantity, unit, unit_price, amount_bdt (purchase) | line_date, outcome, ... (delivery)
    total: int = 0


def _month_factor(shop: Shop, day: date, today: date) -> float:
    months = (today - day).days / 30.0
    factor = (1 + shop.growth) ** (shop.history_days / 30.0 - months)
    if shop.eid_spike and day.month in (4, 5):
        factor *= 1.9
    if shop.eid_spike and day.month in (7, 8):
        factor *= 0.6
    return factor


def purchase_receipts(shop: Shop, today: date, rng: random.Random) -> list[ReceiptPlan]:
    """Purchase memos from the first day of history to a few days before today."""
    if shop.history_days <= 0:
        return []
    start = today - timedelta(days=shop.history_days)
    plans: list[ReceiptPlan] = []
    week = 0
    used: set[tuple] = set()
    memo = rng.randint(1200, 4800)
    while True:
        week_start = start + timedelta(days=7 * week)
        if week_start > today - timedelta(days=4):
            break
        week += 1
        if rng.random() > shop.regularity:
            continue
        count = 1 if shop.per_week <= 1 else 2
        if shop.per_week < 1 and rng.random() > shop.per_week:
            continue
        for _ in range(count):
            day = week_start + timedelta(days=rng.randint(0, 6))
            if day > today - timedelta(days=3):
                continue
            weekly = shop.month_base / 4.3 * _month_factor(shop, day, today)
            target = max(2500.0, weekly / count * rng.lognormvariate(0, shop.volatility))
            memo += rng.randint(3, 40)
            plan = make_purchase(shop, day, target, rng, str(memo))
            key = (day, plan.total)
            if key in used:
                continue
            used.add(key)
            plans.append(plan)
    return plans


def make_purchase(
    shop: Shop, day: date, target: float, rng: random.Random, memo_no: str
) -> ReceiptPlan:
    """One wholesale memo of about `target` BDT: three to five goods, each at a market rate."""
    chosen = rng.sample(CATALOG[shop.catalog], k=min(len(CATALOG[shop.catalog]), rng.randint(3, 5)))
    share = [rng.uniform(0.6, 1.4) for _ in chosen]
    scale = target / sum(share)
    lines, total = [], 0
    for good, s in zip(chosen, share):
        rate = rng.randint(good.low, good.high)
        qty = max(1, round(scale * s / rate))
        amount = qty * rate
        lines.append(
            dict(item=good.en, quantity=qty, unit=good.unit, unit_price=rate, amount_bdt=amount)
        )
        total += amount
    return ReceiptPlan("purchase", day, rng.choice(shop.suppliers), memo_no, "en", lines, total)


def with_language(shop: Shop, plans: list[ReceiptPlan], rng: random.Random) -> None:
    """Print some of a shop's receipts in Bangla (item names), as many wholesalers do."""
    share = {"en": 0.0, "mixed": 0.35, "bn": 0.8}[shop.language]
    goods = {g.en: g for g in CATALOG[shop.catalog]}
    for plan in plans:
        if plan.kind != "purchase" or rng.random() >= share:
            continue
        plan.language = "bn"
        for line in plan.lines:
            good = goods.get(line["item"])
            if good:
                line["item"] = good.bn


def delivery_slips(shop: Shop, today: date, rng: random.Random) -> list[ReceiptPlan]:
    """Fortnightly parcel reports with each parcel's outcome."""
    if shop.parcels is None or shop.history_days <= 0:
        return []
    spec = shop.parcels
    start = today - timedelta(days=min(shop.history_days, 150))
    plans, no = [], rng.randint(100000, 140000)
    day = start
    while day + timedelta(days=13) <= today - timedelta(days=3):  # the report is dated before today
        report_day = day + timedelta(days=13)
        lines = []
        for offset in range(14):
            if rng.random() < spec.per_week / 7:
                dispatched = day + timedelta(days=offset)
                roll = rng.random()
                outcome = (
                    "returned"
                    if roll < spec.returned
                    else "failed"
                    if roll < spec.returned + spec.failed
                    else "delivered"
                )
                no += rng.randint(1, 9)
                cod = rng.randint(7, 45) * 100 if rng.random() < spec.cod_share else None
                line = dict(
                    line_date=dispatched.isoformat(),
                    outcome=outcome,
                    amount_bdt=cod,
                    reference=f"SU-{no}",
                )
                if outcome == "delivered":
                    arrived = min(dispatched + timedelta(days=rng.randint(1, 3)), report_day)
                    line["due_date"] = arrived.isoformat()
                lines.append(line)
        if len(lines) >= 3:
            plans.append(
                ReceiptPlan(
                    "delivery",
                    report_day,
                    "",
                    f"D{rng.randint(1000, 9999)}",
                    "en",
                    lines,
                )
            )
        day += timedelta(days=14)
    return plans


def instalment_schedule(
    spec: LoanSpec, today: date
) -> tuple[date, list[tuple[date, date | None, int]]]:
    """(issued on, [(due, paid on, amount)]) for an earlier ShopUp loan."""
    issued = today - timedelta(days=spec.issued_days_ago)
    share = round(spec.limit / spec.instalments / 100) * 100
    rows = []
    for i in range(spec.instalments):
        due = issued + timedelta(days=30 * (i + 1))
        paid = due + timedelta(days=spec.delays[i])
        rows.append((due, paid if paid < today else None, share))
    return issued, rows
