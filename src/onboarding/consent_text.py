# ruff: noqa: E501  (the consent wording is long prose; it is not wrapped so it stays easy to review)
"""The merchant consent document: eleven sections, English and Bangla, version `paper-consent-v1`.

Purpose: the exact wording a merchant reads and signs on paper before any record about the
    shop is used for a credit assessment.
Owner role: D (full-stack).
Implements: Phase 2 of the unified platform plan (section 9).

IMPORTANT: this text is a DRAFT prepared for review by Bangladesh counsel. It is built from
the structure of the Personal Data Protection Act, 2026 (Act No. 63 of 2026) but has NOT been
legally reviewed, and nothing here claims that using it makes a company compliant. The
Bangla has not been reviewed by a native speaker either. Section 8 (retention) deliberately
holds a placeholder: the period is set by regulation and by the company's legal advice, and
must not be invented here. In production only a version a platform administrator has marked
`approved` (after recording who reviewed it) can be issued; every other version is stamped
DRAFT on every page (src/onboarding/pdf.py).

Optional purposes are separate boxes that start empty (`OPTIONAL_PURPOSES`): nothing is
pre-ticked and nothing optional is bundled with the core consent.
"""

from __future__ import annotations

from typing import Any

VERSION = "paper-consent-v1"

# What the merchant may tick, one box each, none pre-ticked. `core` ones are the kinds of
# records the assessment can use; the optional purposes need their own agreement.
CATEGORIES: dict[str, tuple[str, str]] = {
    "purchases": ("Wholesale purchases from suppliers", "সরবরাহকারীর কাছ থেকে পাইকারি কেনাকাটা"),
    "deliveries": ("Parcel deliveries", "পার্সেল ডেলিভারি"),
    "payments": ("Loan repayments", "ঋণ পরিশোধ"),
    "field_visits": ("Notes from staff visits", "কর্মীদের পরিদর্শনের নোট"),
}
OPTIONAL_PURPOSES: dict[str, tuple[str, str]] = {
    "questionnaire": (
        "Answers to a short questionnaire about my business (optional)",
        "আমার ব্যবসা নিয়ে ছোট প্রশ্নমালার উত্তর (ঐচ্ছিক)",
    ),
    "declared_obligations": (
        "Record the existing loans or debts I choose to tell you about (optional)",
        "আমার থাকা যে ঋণ বা দেনা আমি জানাতে চাই তা রাখা (ঐচ্ছিক)",
    ),
    "share_other_providers": (
        "Share my assessment with other financial providers I name in writing (optional)",
        "আমার লিখিতভাবে উল্লেখ করা অন্য আর্থিক প্রতিষ্ঠানের সাথে আমার মূল্যায়ন ভাগ করা (ঐচ্ছিক)",
    ),
}

# Merchant details on the form, in order: key, English label, Bangla label, required.
DETAIL_FIELDS: list[tuple[str, str, str, bool]] = [
    ("shop_name", "Business name", "ব্যবসার নাম", True),
    ("legal_name", "Legal or trading name", "আইনি বা ট্রেডিং নাম", False),
    ("owner_name", "Owner's full name", "মালিকের পুরো নাম", True),
    ("owner_mobile", "Primary mobile number", "প্রধান মোবাইল নম্বর", True),
    ("alternate_contact", "Alternate contact number", "বিকল্প যোগাযোগ নম্বর", False),
    ("district", "District", "জেলা", True),
    ("area", "Market or area", "বাজার বা এলাকা", True),
    ("shop_type", "Business category", "ব্যবসার ধরন", True),
    ("ownership_type", "Ownership type", "মালিকানার ধরন", True),
    ("established_year", "Year established", "প্রতিষ্ঠার বছর", False),
    ("trade_license_number", "Trade licence number", "ট্রেড লাইসেন্স নম্বর", False),
    ("branches", "Number of outlets", "দোকানের সংখ্যা", False),
    ("representative_name", "Authorised representative", "অনুমোদিত প্রতিনিধি", False),
    ("representative_mobile", "Representative's mobile", "প্রতিনিধির মোবাইল", False),
]

# The signature block: key, English label, Bangla label.
SIGNATURE_FIELDS: list[tuple[str, str, str]] = [
    ("signer_name", "Name of person signing", "যিনি সই করছেন তাঁর নাম"),
    ("signature", "Signature or thumbprint", "সই বা টিপসই"),
    ("signed_on", "Date signed", "সইয়ের তারিখ"),
]

REFERENCE_LABEL = ("Registration reference", "নিবন্ধন নম্বর")
SERIAL_LABEL = ("Form serial", "ফর্মের ক্রমিক নম্বর")

# Each section: number, titles, paragraphs. {org}, {org_contact}, {retention}, {valid_days}
# are filled from the company and the configuration.
SECTIONS: list[dict[str, Any]] = [
    {
        "title": (
            "Who is asking and why you can trust who holds it",
            "কে চাইছে, এবং তথ্য কার কাছে থাকবে",
        ),
        "en": [
            '{org} ("we") asks for and keeps the information on this form. We decide why and how it is used. You can reach us at: {org_contact}.',
        ],
        "bn": [
            '{org} ("আমরা") এই ফর্মের তথ্য চাইছে এবং রাখবে। কেন ও কীভাবে ব্যবহার হবে তা আমরা ঠিক করি। যোগাযোগ: {org_contact}।',
        ],
    },
    {
        "title": (
            "What information about you and your business we collect",
            "আপনার ও আপনার ব্যবসার কোন তথ্য আমরা নিই",
        ),
        "en": [
            "Your business name, your name and mobile number, where the shop is, the kind of business and who owns it, and the records you agree to in the boxes below: purchases from suppliers, parcel deliveries, loan repayments, and notes from staff visits.",
            "We do not ask for your national ID number or your bank or mobile-money account numbers.",
        ],
        "bn": [
            "আপনার ব্যবসার নাম, আপনার নাম ও মোবাইল নম্বর, দোকান কোথায়, ব্যবসার ধরন ও মালিকানা, এবং নিচের বাক্সে আপনি যে রেকর্ডে রাজি: সরবরাহকারীর কাছ থেকে কেনা, পার্সেল ডেলিভারি, ঋণ পরিশোধ, এবং কর্মীদের পরিদর্শনের নোট।",
            "আমরা আপনার জাতীয় পরিচয়পত্র নম্বর বা ব্যাংক বা মোবাইল-মানি অ্যাকাউন্ট নম্বর চাই না।",
        ],
    },
    {
        "title": ("How we collect it", "আমরা কীভাবে সংগ্রহ করি"),
        "en": [
            "Our staff may type it in, write it down during a visit, copy it from your business papers, or read it from a spreadsheet, a photo or a scan of your notes. A person checks what a machine reads from a document before it is used.",
        ],
        "bn": [
            "আমাদের কর্মী তথ্য টাইপ করতে পারেন, পরিদর্শনের সময় লিখে নিতে পারেন, আপনার ব্যবসার কাগজ থেকে তুলতে পারেন, বা স্প্রেডশিট, ছবি বা স্ক্যান থেকে পড়তে পারেন। কোনো নথি থেকে যন্ত্র যা পড়ে, তা ব্যবহারের আগে একজন মানুষ যাচাই করেন।",
        ],
    },
    {
        "title": ("Why we use it", "কেন ব্যবহার করি"),
        "en": [
            "To register your business with us, to keep your business records in order, and to help us decide whether, and how much, working capital could suit your shop.",
        ],
        "bn": [
            "আমাদের কাছে আপনার ব্যবসা নিবন্ধন করতে, আপনার ব্যবসার রেকর্ড গুছিয়ে রাখতে, এবং আপনার দোকানের জন্য কার্যকরী মূলধন উপযুক্ত কি না ও কত, তা বুঝতে সাহায্য করতে।",
        ],
    },
    {
        "title": (
            "How a computer model is used, and who decides",
            "কম্পিউটার মডেল কীভাবে ব্যবহার হয়, আর সিদ্ধান্ত কে নেয়",
        ),
        "en": [
            "We may use your records to calculate figures and to run a statistical model that gives a readiness score and the reasons behind it. The model does not approve or refuse credit. A person at {org} makes every credit decision and can overrule the score. Giving consent does not promise you credit.",
        ],
        "bn": [
            "আমরা আপনার রেকর্ড দিয়ে হিসাব করতে এবং এমন একটি পরিসংখ্যান মডেল চালাতে পারি যা একটি প্রস্তুতির স্কোর ও তার কারণ দেয়। মডেল ঋণ অনুমোদন বা প্রত্যাখ্যান করে না। {org}-এর একজন মানুষ প্রতিটি ঋণ-সিদ্ধান্ত নেন এবং স্কোর বদলাতে পারেন। সম্মতি দিলে ঋণ পাওয়ার প্রতিশ্রুতি হয় না।",
        ],
    },
    {
        "title": ("Who can see it", "কারা দেখতে পারবে"),
        "en": [
            "Only the people at {org} whose work needs it (field staff for your shop, credit officers, auditors), and companies that handle data for us under a written contract. We share your assessment with other providers only if you tick the optional box below.",
        ],
        "bn": [
            "শুধু {org}-এর যে কর্মীদের কাজের জন্য দরকার (আপনার দোকানের মাঠকর্মী, ক্রেডিট অফিসার, অডিটর), এবং লিখিত চুক্তির অধীনে আমাদের হয়ে তথ্য সামলানো প্রতিষ্ঠান। নিচের ঐচ্ছিক বাক্সে টিক দিলেই কেবল আমরা আপনার মূল্যায়ন অন্য প্রতিষ্ঠানের সাথে ভাগ করব।",
        ],
    },
    {
        "title": ("Where it is kept", "কোথায় রাখা হয়"),
        "en": [
            "The information is stored in the CredLens system used by {org}, on servers run for that purpose. If it is ever stored or processed by a company in another country, we will tell you and ask first.",
        ],
        "bn": [
            "তথ্য {org}-এর ব্যবহৃত CredLens ব্যবস্থায়, এই কাজের জন্য চালানো সার্ভারে রাখা হয়। কখনও অন্য দেশের কোনো প্রতিষ্ঠান তা রাখলে বা প্রক্রিয়া করলে আমরা আপনাকে জানাব এবং আগে জিজ্ঞাসা করব।",
        ],
    },
    {
        "title": ("How long we keep it", "কতদিন রাখি"),
        "en": [
            "Retention period: {retention}. This consent lasts {valid_days} days from the date you sign, unless you withdraw it earlier. After that, or when the purpose ends, we delete the information unless the law requires us to keep it.",
        ],
        "bn": [
            "সংরক্ষণের সময়: {retention}। এই সম্মতি আপনার সইয়ের তারিখ থেকে {valid_days} দিন থাকবে, যদি না আপনি আগে তুলে নেন। এরপর, বা উদ্দেশ্য শেষ হলে, আইন রাখতে বাধ্য না করলে আমরা তথ্য মুছে ফেলব।",
        ],
    },
    {
        "title": ("Your rights", "আপনার অধিকার"),
        "en": [
            "You may ask what we hold about you, ask us to correct or complete it, and dispute something you think is wrong. We answer correction requests within 30 days and, if we refuse, we tell you why in writing. Ask at: {org_contact}.",
        ],
        "bn": [
            "আপনি জানতে চাইতে পারেন আমরা আপনার কী তথ্য রেখেছি, তা সংশোধন বা সম্পূর্ণ করতে বলতে পারেন, এবং ভুল মনে হলে আপত্তি জানাতে পারেন। সংশোধনের অনুরোধের উত্তর আমরা ৩০ দিনের মধ্যে দিই, আর না করলে লিখিতভাবে কারণ জানাই। যোগাযোগ: {org_contact}।",
        ],
    },
    {
        "title": ("How to take your consent back", "সম্মতি কীভাবে তুলে নেবেন"),
        "en": [
            "You may withdraw this consent, fully or in part, at any time by telling {org} ({org_contact}). From then we stop using your records for new assessments. What we already did lawfully stays valid. We may keep some information if the law requires it, and we will tell you which and why.",
        ],
        "bn": [
            "আপনি যেকোনো সময় {org}-কে ({org_contact}) জানিয়ে এই সম্মতি সম্পূর্ণ বা আংশিক তুলে নিতে পারেন। তখন থেকে নতুন মূল্যায়নে আপনার রেকর্ড ব্যবহার বন্ধ হবে। আগে আইনসম্মতভাবে যা করা হয়েছে তা বৈধ থাকবে। আইন চাইলে কিছু তথ্য আমরা রাখতে পারি, তখন কোনটি ও কেন তা জানাব।",
        ],
    },
    {
        "title": ("Your free choice and signature", "আপনার স্বাধীন সিদ্ধান্ত ও সই"),
        "en": [
            "I have read (or had read to me) this document in a language I understand. I know why my information is collected, who can see it, how long it is kept, and how to ask questions or withdraw. I have not been promised credit. I sign of my own free will.",
        ],
        "bn": [
            "আমি এই নথি আমার বোঝা ভাষায় পড়েছি (বা পড়ে শোনানো হয়েছে)। আমার তথ্য কেন নেওয়া হচ্ছে, কারা দেখবে, কতদিন থাকবে, এবং কীভাবে প্রশ্ন করব বা সম্মতি তুলে নেব তা আমি জানি। আমাকে ঋণের প্রতিশ্রুতি দেওয়া হয়নি। আমি স্বেচ্ছায় সই করছি।",
        ],
    },
]


def render_sections(*, org: str, org_contact: str, retention: str, valid_days: int) -> list[dict]:
    """The sections with the company's details filled in."""
    values = {
        "org": org,
        "org_contact": org_contact,
        "retention": retention,
        "valid_days": valid_days,
    }
    return [
        {
            "no": number,
            "title": section["title"],
            "en": [text.format(**values) for text in section["en"]],
            "bn": [text.format(**values) for text in section["bn"]],
        }
        for number, section in enumerate(SECTIONS, start=1)
    ]
