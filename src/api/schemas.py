"""The API contract: the shape of every request and response.

Purpose: fix the JSON shapes early, so the React dashboard and the model can be
    built in parallel against the sample files in tests/fixtures/api/.
Owner role: D (full-stack). Created in Phase 0 by the lead; D owns it from the first handover.
Implements: PROJECT_BRIEF section 8 (API) and the non-negotiable rules in CLAUDE.md.

Rules built into these shapes:
- A score is always a calibrated probability shown as 0-100, together with its
  coverage, band, reasons and model version. There is no approve/decline field.
- The only actions are an officer's: accept, override_up, override_down,
  needs_more_info. An override must come with a written reason.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.config import VALID_MODES, load_config

# The data modes of the project: one list (src/config.py), so a new mode needs no change here.
DataMode = Literal[VALID_MODES]
Band = Literal["Strong", "Review", "Needs more info"]
Role = str  # credit_officer | fsr | auditor | platform_admin (older rows: officer, admin, viewer)
OfficerAction = Literal["accept", "override_up", "override_down", "needs_more_info"]

OVERRIDE_ACTIONS = ("override_up", "override_down")
# The longest written reason on a decision (config: api.reason_max_chars). Longer is refused.
REASON_MAX_CHARS = load_config(validate=False)["api"]["reason_max_chars"]


class HealthResponse(BaseModel):
    """GET /health"""

    status: Literal["ok"]
    data_mode: DataMode
    banner: str = Field(description="Sentence every screen must show for this data mode.")


class Reason(BaseModel):
    """One plain-language reason behind a score."""

    code: str = Field(description="Feature name. For logs and tests; never shown to officers.")
    sentence_en: str
    sentence_bn: str
    contribution: float = Field(description="Score points this reason added (+) or removed (-).")
    detail: str | None = Field(
        default=None, description="Number for context, e.g. 'Returns 7.5% vs average 7.0%'."
    )


class ReadyResponse(BaseModel):
    """GET /ready: can the API answer yet? (503 with the same body when it cannot.)"""

    ready: bool
    scorer: bool = Field(description="The scorer has been built.")
    database: bool = Field(description="The database is open and has its tables.")
    model_version: str | None = Field(default=None, description="The model the scores come from.")
    problems: list[str] = Field(default=[], description="Plain reasons, when not ready.")


class BandRules(BaseModel):
    """The lines that turn a score and a coverage into a band, for one data mode.

    They are settings (config/default.yaml, `score`), sent so a screen can show the
    numbers next to a band. A screen must still take the band itself from the API: it must
    never work a band out from these.
    """

    strong_min_score: float = Field(description="Score at or above this is Strong ...")
    min_coverage: float = Field(
        ge=0, le=1, description="... but only when coverage is at least this (0 to 1)."
    )
    low_score_warning_below: float = Field(description="A score below this gets a warning.")


class InputPoints(BaseModel):
    """One model input on a score card, whether or not it is among the top reasons."""

    code: str = Field(description="Feature name. For logs and tests; never shown to officers.")
    group: str = Field(description="Where the data comes from: purchases, payments, deliveries.")
    label: str = Field(description="Short English name of the input, e.g. 'Returns'.")
    has_data: bool = Field(description="False: the merchant has no data for this input.")
    points: float = Field(description="Score points this input added (+) or removed (-).")
    sentence_en: str | None = Field(
        default=None, description="The plain reason sentence, when one is true for the merchant."
    )
    sentence_bn: str | None = None
    detail: str | None = Field(
        default=None,
        description="The merchant's number against the average, e.g. 'Returns 5.9% vs 6.8%'.",
    )


class CoverageItem(BaseModel):
    """One item of the coverage checklist."""

    item: str = Field(description="Checklist item, e.g. 'deliveries_present'.")
    weight: float = Field(ge=0, le=1, description="Its share of coverage (weights sum to 1).")
    present: bool


class ScoreResponse(BaseModel):
    """GET /merchants/{id}/score"""

    merchant_id: str
    data_mode: DataMode
    model_version: str
    probability: float = Field(ge=0, le=1, description="Calibrated probability of good repayment.")
    score: int = Field(ge=0, le=100, description="round(100 x probability).")
    coverage: float = Field(ge=0, le=1, description="How much history the score rests on.")
    band: Band
    low_score_warning: bool = False
    baseline_score: float = Field(description="Average score that the reasons are measured from.")
    reasons_positive: list[Reason] = Field(description="Top reasons that raised the score.")
    reasons_negative: list[Reason] = Field(description="Top reasons that lowered the score.")
    other_contribution: float = Field(
        description="All other features together, so the parts sum to the score."
    )
    summary_en: str | None = Field(
        default=None,
        description="Plain-language paragraph built from this card (no language model). "
        "Show it above the reasons; it never recommends lending or not.",
    )
    summary_bn: str | None = Field(default=None, description="The same paragraph in Bangla.")
    band_rules: BandRules | None = Field(
        default=None, description="The band lines of this data mode, to show beside the band."
    )
    inputs: list[InputPoints] = Field(
        default=[],
        description="Every model input with its points, in model order (Oct 17). "
        "baseline_score + the sum of all points = the score before rounding. An input "
        "the merchant has no data for has 0 points: missing data never lowers a score.",
    )
    coverage_items: list[CoverageItem] = Field(
        default=[],
        description="The coverage checklist behind `coverage` (Oct 17): coverage is the "
        "sum of the weights of the items that are present.",
    )


class MerchantQueueItem(BaseModel):
    """One row of GET /merchants (the review queue)."""

    merchant_id: str
    district: str | None = None
    town_tier: str | None = None
    shop_type: str | None = None
    onboarded_at: str
    status: Literal["pending", "decided"]
    pending_since: str | None = None
    score: int | None = Field(default=None, ge=0, le=100)
    coverage: float | None = Field(default=None, ge=0, le=1)
    band: Band | None = None
    low_score_warning: bool | None = Field(
        default=None, description="Score under the warning line; null when there is no score."
    )
    consent_valid: bool
    assessment_status: Literal["current", "not_updated"] = Field(
        default="current",
        description="not_updated: the latest records are saved but could not be scored, so "
        "no score is shown (an older one never is).",
    )


class ConsentRequestOut(BaseModel):
    """POST /merchants/{id}/consent-request: an officer asked the merchant for consent."""

    merchant_id: str
    requested_by: str = Field(description="The officer's demo user id.")
    requested_at: str = Field(description="When, in UTC (ISO 8601, no zone suffix).")
    note: str = Field(description="What happens next, in plain words.")


class ConsentView(BaseModel):
    """GET /merchants/{id}/consent: the merchant's consent as the data stands today."""

    merchant_id: str
    valid: bool = Field(description="A consent that is granted, not expired and not revoked.")
    as_of: str = Field(description="The day the check is made for: the last day in the data.")
    data_categories: list[str] = Field(
        description="What the valid consents cover, e.g. purchases, deliveries, questionnaire."
    )
    records: list[dict[str, str | None]] = Field(
        description="Every consent record of the merchant: purpose, categories, granted, "
        "expires and revoked dates."
    )
    consent_requests: list[ConsentRequestOut] = Field(
        default=[],
        description="Officers' requests for consent, newest first (Oct 17). A request never "
        "grants consent: only the merchant can, in their own app.",
    )


ConsentStatus = Literal["valid", "expired", "revoked", "not_started"]


class ConsentListItem(BaseModel):
    """One consent record in GET /consents."""

    consent_id: str
    merchant_id: str
    purpose: str
    data_categories: list[str] = Field(description="What the consent covers, e.g. purchases.")
    granted_at: str
    expires_at: str
    revoked_at: str | None = None
    status: ConsentStatus = Field(
        description="As of the last day in the data: valid, expired, revoked, or not_started "
        "(granted after that day)."
    )


class ConsentList(BaseModel):
    """GET /consents: one page of consent records and how many there are."""

    as_of: str = Field(
        description="The day the statuses are worked out for: the last day in the data."
    )
    total: int = Field(description="Records matching the filters, over all pages.")
    limit: int
    offset: int
    counts: dict[str, int] = Field(
        description="Records per status for the merchant filter (the status filter is ignored)."
    )
    items: list[ConsentListItem]


class PurchasesSummary(BaseModel):
    """Mokam-style wholesale purchases: what the shop buys, never its sales."""

    n_purchases_90d: int
    value_bdt_90d: float
    n_categories: int
    weeks_active: int


class DeliveriesSummary(BaseModel):
    """REDX-style outgoing parcels."""

    n_parcels_90d: int
    delivered_rate: float | None = None
    return_rate: float | None = None
    failed_rate: float | None = None
    cod_remit_ontime_rate: float | None = None


class PaymentsSummary(BaseModel):
    """Baki-style repayments."""

    n_payments: int
    ontime_rate: float | None = None
    avg_days_late: float | None = None


class QuestionnaireSummary(BaseModel):
    """Shown beside the score as a directional signal; not part of the score."""

    answered_at: str
    spend: float
    save: float
    borrow: float
    plan: float
    stress: int
    confidence: int
    directional: Literal[True] = True


class TimelineEvent(BaseModel):
    """One event on the merchant's unified timeline."""

    date: str
    stream: Literal["purchase", "delivery", "payment", "loan"]
    label: str
    label_bn: str | None = Field(default=None, description="The same label in Bangla.")
    amount_bdt: float | None = None
    kind: Literal["purchase", "delivery", "payment", "loan", "application"] | None = Field(
        default=None,
        description="What the event is. An application is on the loan stream (it is scored "
        "through a loan-shaped row) but it is a request, not an issued loan; its amount is "
        "the amount requested.",
    )


class MerchantProfile(BaseModel):
    """GET /merchants/{id}. A stream the data source does not have is null."""

    merchant_id: str
    data_mode: DataMode
    onboarded_at: str
    shop_name: str | None = Field(
        default=None, description="Set only for a shop created in the app."
    )
    area: str | None = None
    district: str | None = None
    town_tier: str | None = None
    shop_type: str | None = None
    has_trade_license: bool | None = None
    consent_valid: bool
    purchases: PurchasesSummary | None = None
    deliveries: DeliveriesSummary | None = None
    payments: PaymentsSummary | None = None
    questionnaire: QuestionnaireSummary | None = None
    timeline: list[TimelineEvent] = []


class DecisionCreate(BaseModel):
    """POST /merchants/{id}/decision. The officer decides; the system never does."""

    officer_action: OfficerAction
    reason_text: str | None = Field(
        default=None,
        max_length=REASON_MAX_CHARS,
        description="The officer's written reason. Required for an override. "
        "At most `api.reason_max_chars` characters (2,000).",
    )

    @model_validator(mode="after")
    def override_needs_reason(self) -> DecisionCreate:
        """Reject an override that has no written reason."""
        if self.officer_action in OVERRIDE_ACTIONS and not (self.reason_text or "").strip():
            raise ValueError("A written reason is required when the action is an override.")
        return self


class Decision(BaseModel):
    """One row of GET /decisions. Decisions are append-only."""

    decision_id: str
    merchant_id: str
    officer_id: str
    model_version: str
    score_shown: int = Field(ge=0, le=100)
    band_shown: Band | None = Field(
        default=None, description="The band shown with the score; empty on older decisions."
    )
    coverage_shown: float | None = Field(
        default=None, ge=0, le=1, description="The coverage shown with the score (0 to 1)."
    )
    officer_action: OfficerAction
    reason_text: str | None = None
    decided_at: str = Field(description="When, in UTC (ISO 8601, no zone suffix).")
    assessment_id: str | None = Field(
        default=None, description="The stored assessment this decision was made on."
    )


class AuditEntry(BaseModel):
    """One row of GET /audit (admin only)."""

    id: int
    actor: str
    role: Role
    action: str
    merchant_id: str | None = None
    timestamp: str


class ModelCard(BaseModel):
    """GET /model/card. Filled by the model card writer in Phase 11."""

    data_mode: DataMode
    model_version: str
    intended_use: str
    metrics: dict[str, float | list[float] | str | None] = {}
    ablation: list[dict[str, float | str | None]] = []
    group_results: list[dict[str, float | str | None]] = []
    limitations: list[str]
    band_rules: BandRules | None = Field(
        default=None, description="The band lines of this data mode (set by the API)."
    )
    limitations_bn: list[str] = Field(
        default=[], description="The same limitations in Bangla, for the language switch."
    )


class QuestionnaireCreate(BaseModel):
    """POST /merchants/{id}/questionnaire: the ten answers, each a whole number from 1 to 5.

    Saving these never changes the score: the questionnaire is shown beside the score, not
    inside the model.
    """

    model_config = ConfigDict(extra="forbid")

    spend1: int = Field(strict=True, ge=1, le=5)
    spend2: int = Field(strict=True, ge=1, le=5)
    save1: int = Field(strict=True, ge=1, le=5)
    save2: int = Field(strict=True, ge=1, le=5)
    borrow1: int = Field(strict=True, ge=1, le=5)
    borrow2: int = Field(strict=True, ge=1, le=5)
    plan1: int = Field(strict=True, ge=1, le=5)
    plan2: int = Field(strict=True, ge=1, le=5)
    stress: int = Field(strict=True, ge=1, le=5)
    confidence: int = Field(strict=True, ge=1, le=5)


class ImportRejection(BaseModel):
    """One row of an uploaded file that was refused, and why."""

    line: int = Field(description="Line number in the file. The header is line 1.")
    record_id: str | None = Field(default=None, description="The row's id, when it has one.")
    reasons: list[str]


class BundleReport(BaseModel):
    """POST /admin/import-bundle: a zip of contract CSVs, checked (and loaded) together."""

    dry_run: bool = Field(description="True: the files were only checked, nothing was loaded.")
    loaded: bool = Field(description="True when the accepted rows of every file were written.")
    tables: list[ImportReport] = Field(description="One report per file, in contract order.")
    new_merchants: list[str] = Field(
        default=[], description="Merchants of this bundle that can now be scored (after a load)."
    )
    note: str


class ImportReport(BaseModel):
    """POST /admin/import/{table}: what the check found and what was loaded."""

    table: str
    dry_run: bool = Field(description="True: the file was only checked, nothing was loaded.")
    rows_received: int
    rows_accepted: int
    rows_rejected: int
    file_error: str | None = Field(
        default=None, description="Set when the whole file is refused (for example wrong columns)."
    )
    rejections: list[ImportRejection] = []
    rejections_truncated: bool = Field(
        default=False, description="True when more rows were rejected than are listed."
    )
    loaded: bool = Field(description="True when the accepted rows were written to the database.")
    note: str


# --- the demo workflow: merchants, consent, records, visits, applications (Phase 3) ------
# Dates named `*_date` are simulated business dates (never after the demo calendar's end);
# `entered_at` / `recorded_at` are the real moments a person saved the row, in UTC.

AssessmentStatus = Literal["refreshed", "not_updated", "no_application", "not_assessed"]


class DemoSettings(BaseModel):
    """GET /demo/settings: the demo's rules, read from the config, for the forms to use."""

    synthetic_only: bool
    calendar_end: str = Field(description="The last business day of the synthetic world.")
    calendar_matches_data: bool | None = Field(
        description="True when the database's last business day equals calendar_end."
    )
    consent_wording_version: str
    consent_purpose: str
    consent_categories: list[str]
    consent_methods: list[str]
    consent_valid_days: int
    application_purposes: list[str]
    max_requested_bdt: float
    application_note_max_chars: int
    visit_outcomes: list[str]
    visit_note_max_chars: int
    import_max_file_mb: float = Field(description="Largest workbook the purchase import reads.")
    import_max_rows: int = Field(description="Rows read from one sheet by the purchase import.")
    range_policy_enabled: bool = Field(
        default=False, description="Whether a credit-range policy is switched on (config `review`)."
    )
    districts: list[str]
    shop_types: list[str]
    delivery_statuses: list[str]
    return_reasons: list[str]


class MerchantCreate(BaseModel):
    """POST /merchants: a shop created in the app. The server makes its permanent id."""

    model_config = ConfigDict(extra="forbid")

    shop_name: str = Field(max_length=80)
    area: str | None = Field(default=None, max_length=80, description="Market or locality.")
    district: str
    shop_type: str
    has_trade_license: bool | None = None
    start_date: str | None = Field(
        default=None, description="Business date the shop joins (default: the calendar's end)."
    )
    confirm_new: bool = Field(
        default=False,
        description="True after staff checked the likely duplicates: this is a different shop.",
    )


class MerchantSummary(BaseModel):
    """A merchant as found by a search or just created."""

    merchant_id: str
    shop_name: str | None
    area: str | None
    district: str | None
    shop_type: str | None
    created_in_app: bool


class ConsentResponseCreate(BaseModel):
    """POST /merchants/{id}/consent-responses: the merchant's answer, recorded by staff."""

    model_config = ConfigDict(extra="forbid")

    response: Literal["granted", "refused"]
    categories: list[str]
    method: str
    business_date: str | None = Field(default=None, description="Default: the calendar's end.")


class ConsentEventOut(BaseModel):
    """A recorded consent answer. Every one is simulated in this prototype."""

    event_id: str
    merchant_id: str
    consent_id: str | None
    response: str
    categories: list[str]
    method: str
    wording_version: str
    business_date: str
    recorded_at: str
    recorded_by: str
    simulated: bool
    label: str = "Simulated consent (synthetic demo)"


class PurchaseCreate(BaseModel):
    """POST /merchants/{id}/purchases: a stock purchase (what the shop bought, not sold)."""

    model_config = ConfigDict(extra="forbid")

    purchase_date: str
    amount_bdt: float
    category: str | None = Field(default=None, max_length=64, description="Kind of stock.")
    supplier_reference: str | None = Field(default=None, max_length=32)
    invoice_reference: str | None = Field(
        default=None, max_length=32, description="The paper's own number, if any."
    )


class DeliveryCreate(BaseModel):
    """POST /merchants/{id}/deliveries: one of the shop's own parcels to a customer."""

    model_config = ConfigDict(extra="forbid")

    dispatched_at: str
    delivered_at: str | None = None
    status: str
    return_reason: str | None = None
    is_cod: bool
    cod_remitted_on_time: bool | None = None
    parcel_reference: str | None = Field(default=None, max_length=32)


class RepaymentCreate(BaseModel):
    """POST /merchants/{id}/repayments: an instalment of one of the shop's earlier loans."""

    model_config = ConfigDict(extra="forbid")

    loan_id: str
    due_date: str
    paid_date: str | None = None
    amount_due_bdt: float
    amount_paid_bdt: float


class VisitCreate(BaseModel):
    """POST /merchants/{id}/visits: a short structured note of a field visit."""

    model_config = ConfigDict(extra="forbid")

    business_date: str | None = Field(default=None, description="Default: the calendar's end.")
    outcome: str
    note: str | None = Field(default=None, max_length=500)


class ApplicationCreate(BaseModel):
    """POST /merchants/{id}/application: the working-capital request (one per merchant)."""

    model_config = ConfigDict(extra="forbid")

    requested_amount_bdt: float
    purpose: str
    purpose_note: str | None = Field(default=None, max_length=300)
    business_date: str | None = Field(default=None, description="Default: the calendar's end.")


class AssessmentOutcome(BaseModel):
    """What happened to the merchant's assessment after a save."""

    status: AssessmentStatus
    message: str


class RecordSaved(BaseModel):
    """The answer to every record, visit and application save."""

    record_type: str
    record_id: str
    merchant_id: str
    business_date: str
    entered_at: str | None
    entry_method: str
    status: str = Field(description="What is known about the record: staff_entered = typed in "
                        "by staff, not verified.")
    repeat: bool = Field(
        default=False, description="True: the same record was saved a moment ago; nothing added."
    )
    counts_for_assessment: bool | None = Field(
        default=None,
        description="Whether this record's date is before the application date, so the model "
        "can use it. Null: no application yet.",
    )
    assessment: AssessmentOutcome


class ApplicationOut(BaseModel):
    """The merchant's application. A request, never an issued loan."""

    application_id: str
    loan_id: str
    merchant_id: str
    requested_amount_bdt: float
    purpose: str
    purpose_note: str | None
    business_date: str
    entered_at: str
    created_by: str
    assessment_status: Literal["current", "not_updated", "not_scored"]
    note: str = "This is an application: the amount requested, not an issued loan."


class MerchantLoan(BaseModel):
    """One loan-shaped row of a merchant, said plainly: an issued loan or an application."""

    loan_id: str
    kind: Literal["loan", "application"]
    issued_at: str
    limit_bdt: float | None = Field(description="The issued limit; null for an application.")
    requested_amount_bdt: float | None = Field(description="Set only for an application.")
    has_outcome: bool
    repayment_allowed: bool


class WorkflowStatus(BaseModel):
    """GET /merchants/{id}/workflow: where the merchant is in the field workflow."""

    merchant: MerchantSummary
    consent: Literal["valid", "refused", "none"]
    consent_categories: list[str]
    records: dict[str, int] = Field(description="Saved purchases, deliveries, repayments, visits.")
    application: ApplicationOut | None
    next_step: Literal["record_consent", "add_records", "create_application", "await_review"]
    created_at: str | None = Field(
        default=None, description="When the shop was created in the app (real time, UTC)."
    )
    calendar_end: str | None = Field(
        default=None, description="The demo calendar's last business day: the latest date allowed."
    )


# --- officer workspace (Phase 6) -----------------------------------------------------------


class ReadinessCheck(BaseModel):
    """One evidence check behind the review status. Never about the score's level."""

    code: Literal["consent", "assessment", "history", "field_visit", "deliveries"]
    kind: Literal["required", "check", "info"] = Field(
        description="required: blocks review when it fails. check: one thing to look at. "
        "info: shown for context, never blocks and never lowers the score."
    )
    passed: bool


class ReviewRecord(BaseModel):
    """One saved record and what is known about how it entered CredLens."""

    record_type: Literal["purchase", "payment", "delivery", "visit"]
    business_date: str
    amount_bdt: float | None = None
    detail: str | None = Field(
        default=None, description="A code: purchase category, delivery status or visit outcome."
    )
    entry_method: str | None = Field(
        default=None, description="How it entered; null for generated benchmark rows."
    )
    status: str | None = Field(default=None, description="What is known about it (record status).")
    entered_at: str | None = Field(default=None, description="Real entry time (UTC).")
    entered_by: str | None = None
    simulated: bool | None = None


class EvidenceGroup(BaseModel):
    """A neutral source group: how many records, and the latest few."""

    group: Literal["purchases", "repayments", "deliveries", "visits"]
    total: int
    with_entry_record: int = Field(description="Records that have an entry (provenance) record.")
    by_source: dict[str, int] = Field(
        default={},
        description="Records per source: typed_in, spreadsheet, data_source, data_file, generated.",
    )
    latest: list[ReviewRecord]


class RangeGuidance(BaseModel):
    """Credit-range guidance: a separate policy, never the score turned into money."""

    available: bool
    reason: (
        Literal[
            "policy_not_configured",
            "no_application",
            "assessment_not_current",
            "needs_more_info",
            "not_enough_verified",
        ]
        | None
    )
    policy_version: str | None = None
    missing: list[str] = Field(
        default_factory=list, description="What verified evidence is still missing."
    )
    low_bdt: float | None = None
    high_bdt: float | None = None
    band: str | None = None
    monthly_purchases_bdt: float | None = Field(
        default=None, description="Average monthly wholesale purchases in the window."
    )
    window_days: int | None = None
    multiples: list[float] | None = None
    requested_bdt: float | None = None
    capped: bool = False


class EvidenceRequest(BaseModel):
    """The smallest piece of evidence worth asking for. Never a promise of a better score."""

    code: Literal[
        "add_purchase_records",
        "show_memo_for_large_purchase",
        "confirm_possible_duplicate",
        "clarify_part_payment",
        "confirm_not_same_shop",
    ]
    business_date: str | None = None
    amount_bdt: float | None = None
    other_merchant_id: str | None = Field(
        default=None, description="For confirm_not_same_shop: the shop that looks the same."
    )


class ReviewStatus(BaseModel):
    """GET /merchants/{id}/review: the officer's view of where a review stands.

    The readiness status says whether the evidence is in order for a person to review.
    It never means approval, eligibility or a level of risk.
    """

    merchant_id: str
    application: ApplicationOut | None
    assessment: Literal["current", "not_updated", "not_scored", "consent_required"]
    readiness: Literal["ready", "check_needed", "more_info_needed", "not_updated"]
    checks: list[ReadinessCheck]
    evidence: list[EvidenceGroup]
    range: RangeGuidance
    evidence_requests: list[EvidenceRequest] = Field(
        default=[], description="The smallest evidence to ask for, most important first."
    )


# --- Excel purchase import (Phase 7) -------------------------------------------------------


class ImportSheet(BaseModel):
    """One sheet of an uploaded workbook."""

    name: str
    columns: list[str] = Field(description="The header row, as written in the sheet.")
    rows: int = Field(description="Rows below the header that will be read.")
    truncated: bool = Field(description="The sheet has more rows than one import reads.")
    suggested: dict[str, str | None] = Field(
        description="For each field, the column that looks like it, or null."
    )


class ImportInspect(BaseModel):
    """POST .../purchase-import/inspect: what the workbook holds. Nothing is saved."""

    file_sha256: str
    sheets: list[ImportSheet]
    fields: list[str]
    required: list[str]


class ImportRow(BaseModel):
    """What would happen (or happened) to one row."""

    row_number: int = Field(description="The row number in Excel.")
    outcome: Literal["add", "skip", "flag", "reject"]
    code: str = Field(description="Why, as a code the screen words.")
    purchase_date: str | None = None
    amount_bdt: float | None = None
    category: str | None = None
    invoice_reference: str | None = None
    supplier_reference: str | None = None


class ImportPreview(BaseModel):
    """POST .../purchase-import/preview: every row and its outcome. Nothing is saved."""

    preview_token: str = Field(description="Binds a commit to this file, sheet and mapping.")
    file_sha256: str
    sheet: str
    date_order: str
    date_order_needed: bool
    truncated: bool
    counts: dict[str, int]
    rows: list[ImportRow]


class ImportResult(BaseModel):
    """POST .../purchase-import/commit: what was saved."""

    batch_id: str
    added: int
    skipped: int
    flagged_kept: int
    flagged_left: int
    rejected: int
    assessment: AssessmentOutcome


# --- merchant data receipt (Phase 8) -------------------------------------------------------


class ReceiptRecord(BaseModel):
    """One thing recorded about the shop, as the receipt shows it."""

    record_type: Literal["merchant", "purchase", "delivery", "payment", "visit", "application"]
    business_date: str | None
    amount_bdt: float | None = None
    detail: str | None = Field(default=None, description="A code: category, status or outcome.")
    source_category: str
    entry_method: str
    status: str
    entered_at: str = Field(description="Real time it was saved (UTC).")


class ReceiptConsent(BaseModel):
    """One consent answer, as recorded (always simulated in this demo)."""

    response: Literal["granted", "refused"]
    categories: list[str]
    method: str
    wording_version: str
    business_date: str
    recorded_at: str
    simulated: bool


class Receipt(BaseModel):
    """GET /merchants/{id}/receipt: what CredLens holds about one shop created in the app.

    No score, no decision, no officer note and nothing about any other shop.
    """

    merchant: MerchantSummary
    generated_at: str = Field(description="When this receipt was made (UTC).")
    calendar_end: str
    consent: list[ReceiptConsent]
    records: list[ReceiptRecord]


# --- workspace lists and overview (product redesign) ---------------------------------------


class ApplicationRow(BaseModel):
    """One application in the officers' list: a request, never an issued loan."""

    application_id: str
    merchant_id: str
    shop_name: str | None
    district: str | None
    area: str | None
    requested_amount_bdt: float
    purpose: str
    business_date: str
    entered_at: str
    assessment: Literal["current", "not_updated", "not_scored", "consent_required"]
    readiness: Literal["ready", "check_needed", "more_info_needed", "not_updated"]
    open_checks: int = Field(description="Required or check items that did not pass.")
    decision: OfficerAction | None = Field(
        default=None, description="The latest officer decision recorded after the application."
    )
    decided_at: str | None = None


class DirectoryRow(BaseModel):
    """One merchant in the directory."""

    merchant_id: str
    shop_name: str | None
    area: str | None
    district: str | None
    shop_type: str | None
    created_in_app: bool
    onboarded_at: str
    consent: Literal["valid", "refused", "none"]
    has_application: bool


class DirectoryPage(BaseModel):
    """GET /directory/merchants: one page of merchants, searched and paged on the server."""

    total: int
    offset: int
    limit: int
    items: list[DirectoryRow]


class ImportBatchOut(BaseModel):
    """One spreadsheet import, as it was saved. The file itself is never kept."""

    batch_id: str
    merchant_id: str | None
    shop_name: str | None
    record_type: str
    file_name: str
    file_sha256: str
    sheet_name: str | None
    uploaded_at: str
    actor: str
    rows_added: int
    rows_skipped: int
    rows_flagged: int
    rows_rejected: int
    status: str


class ImportBatchDetail(ImportBatchOut):
    """An import with the records it saved and how each is known."""

    records: list[ReviewRecord]


class ActivityItem(BaseModel):
    """One recent event: a saved record or a decision."""

    kind: Literal["record", "decision"]
    record_type: str | None = None
    merchant_id: str
    shop_name: str | None = None
    actor: str | None
    at: str = Field(description="Real time it happened (UTC).")
    business_date: str | None = Field(default=None, description="Simulated business date.")
    entry_method: str | None = None
    officer_action: OfficerAction | None = None


class SourceCount(BaseModel):
    record_type: Literal["purchase", "delivery", "payment", "visit"]
    source: str = Field(description="typed_in, spreadsheet, data_source, data_file or generated.")
    records: int


class MonthCount(BaseModel):
    month: str = Field(description="Business month, YYYY-MM.")
    source: str
    records: int


class EvidenceOverview(BaseModel):
    """The evidence behind the shops added in the app, counted from the records. The
    generated benchmark merchants are not in it (they are described on the Portfolio page)."""

    app_shops: int
    coverage: dict[str, int] = Field(
        description="Shops with each kind of evidence: consent (valid on the calendar's last "
        "day), purchases, deliveries, repayments, visits, application."
    )
    by_source: list[SourceCount]
    by_month: list[MonthCount] = Field(description="Records per business month, last 6 months.")
    quality_open: int
    quality_concerns: int
    quality_by_group: dict[str, int]


class Overview(BaseModel):
    """GET /overview: counts and recent activity for the dashboard. Every number is counted
    from the database; an application is never counted as an issued loan."""

    merchants_total: int
    shops_created_in_app: int
    applications_total: int
    applications_awaiting_decision: int
    assessments_not_updated: int
    issued_loans: int
    repayments: int
    decisions_total: int
    import_batches: int
    calendar_end: str
    recent: list[ActivityItem]
    # the company's field operation (counted from its own records)
    registrations_open: int = 0
    documents_to_review: int = 0
    fsrs_total: int = 0
    fsrs_active: int = 0
    merchants_unassigned: int = 0
    submissions_today: int = 0
    sheets_returned: int = 0
    sheets_with_drafts: int = 0
    evidence: EvidenceOverview | None = None


class OrganizationOut(BaseModel):
    """GET /organization: the caller's organisation and how it is set up."""

    organization_id: str
    name: str
    environment: Literal["benchmark", "pilot", "production"]
    country: str
    languages: list[str]
    currency: str
    timezone: str


# --- data sources and connectors (workstream C) --------------------------------------------


class ConnectorSetting(BaseModel):
    key: str
    label: str
    label_bn: str
    kind: Literal["text", "choice", "secret_ref"]
    required: bool
    choices: list[str]
    help: str
    help_bn: str


class ConnectorInfo(BaseModel):
    """A kind of source. `availability`: builtin (works without setup), available (can be
    connected now), planned (no authorised access and no implementation yet)."""

    key: str
    name: str
    name_bn: str
    category: str
    description: str
    description_bn: str
    record_kinds: list[str]
    auth: Literal["none", "api_key", "oauth2"]
    availability: Literal["builtin", "available", "planned"]
    sandbox_only: bool
    example: str | None
    settings: list[ConnectorSetting]


class SourceRunOut(BaseModel):
    run_id: str
    kind: Literal["test", "discover", "sync"]
    status: Literal["ok", "failed"]
    actor: str
    started_at: str
    finished_at: str
    rows_added: int
    rows_skipped: int
    rows_flagged: int
    rows_rejected: int
    rows_unmatched: int
    error_code: str | None
    error_message: str | None


class SourceConnectionOut(BaseModel):
    """One of the organisation's connections. A credential is never included: only whether
    a credential reference is set."""

    connection_id: str
    connector_key: str
    connector_name: str
    display_name: str
    status: Literal["not_tested", "connected", "error", "revoked"]
    settings: dict[str, str]
    secret_ref_set: bool
    created_by: str
    created_at: str
    last_tested_at: str | None
    last_error: str | None
    revoked_at: str | None
    last_run: SourceRunOut | None


class SourceDetail(SourceConnectionOut):
    runs: list[SourceRunOut]
    linked_merchants: int


class SourceCreate(BaseModel):
    connector_key: str
    display_name: str = Field(min_length=2, max_length=120)
    settings: dict[str, str] = {}
    secret_ref: str | None = Field(
        default=None, description="Name of the environment variable holding a credential."
    )


class SourceMapping(BaseModel):
    mapping: dict[str, str | None]


class SourceFields(BaseModel):
    fields: list[str]
    suggested: dict[str, str | None]
    required: list[str]
    canonical: list[str]
    run: SourceRunOut


class MatchCandidate(BaseModel):
    merchant_id: str
    shop_name: str | None
    area: str | None


class UnmatchedMerchant(BaseModel):
    external_ref: str
    merchant_name: str | None
    district: str | None
    rows: int
    decision: Literal["rejected"] | None
    candidates: list[MatchCandidate]


class SourcePreviewRow(BaseModel):
    index: int
    outcome: Literal["add", "skip", "flag", "reject", "unmatched"]
    code: str
    external_ref: str | None
    merchant_id: str | None
    kind: str | None
    business_date: str | None
    amount: float | None
    delivery_status: str | None
    source_reference: str | None


class SourcePreview(BaseModel):
    counts: dict[str, int]
    rows: list[SourcePreviewRow]
    unmatched: list[UnmatchedMerchant]


class MatchDecision(BaseModel):
    external_ref: str = Field(min_length=1, max_length=120)
    merchant_id: str | None = None
    decision: Literal["confirmed", "rejected"]


class MatchOut(BaseModel):
    external_ref: str
    merchant_id: str | None
    decision: Literal["confirmed", "rejected"]
    decided_by: str
    decided_at: str


class SourceLinkOut(BaseModel):
    """A merchant-match decision of a data source, current or replaced."""

    id: int
    external_ref: str
    merchant_id: str | None
    shop_name: str | None
    decision: Literal["confirmed", "rejected"]
    decided_by: str
    decided_at: str
    current: bool = Field(description="False when a later decision replaced this one.")
    records_saved: int = Field(description="Records saved for this merchant by this source.")


# --- data quality (src/api/quality.py) -----------------------------------------------


class QualityEvidence(BaseModel):
    record_type: str
    record_id: str
    merchant_id: str | None
    business_date: str | None
    amount: float | None
    detail: str | None
    origin: str | None = Field(description="How the record entered, e.g. staff_entered.")
    origin_name: str | None = Field(description="The file or data source, when there is one.")


class QualityReviewOut(BaseModel):
    review_id: str
    outcome: str
    note: str
    actor: str
    decided_at: str
    concern: bool = Field(description="The review confirmed a problem the record still has.")
    current: bool = Field(description="False when the evidence changed after this review.")


class QualityIssueOut(BaseModel):
    issue_key: str
    kind: str
    group: str
    status: Literal["open", "reviewed", "changed"]
    merchant_id: str | None
    other_merchant_id: str | None
    connection_id: str | None
    batch_id: str | None
    facts: dict
    evidence: list[QualityEvidence]
    fingerprint: str
    outcomes: list[str] = Field(description="What a person may record. Empty: fix the evidence.")
    reviews: list[QualityReviewOut]


class QualityReport(BaseModel):
    """An organisation's data-quality issues. Nothing here changes a score or a record."""

    as_of: str = Field(description="The last business day the checks use.")
    open: int
    reviewed: int
    concerns: int
    by_kind: dict[str, int] = Field(description="Open (or changed) issues per kind.")
    issues: list[QualityIssueOut]


class QualityReviewIn(BaseModel):
    issue_key: str = Field(min_length=3, max_length=200)
    fingerprint: str = Field(min_length=64, max_length=64)
    outcome: str = Field(min_length=2, max_length=32)
    note: str = Field(max_length=1000)


# --- accounts (src/accounts/, src/api/routes_auth.py, src/api/routes_org.py) -----------------


class LoginIn(BaseModel):
    identifier: str = Field(min_length=3, max_length=254, description="Email or mobile number.")
    password: str = Field(min_length=1, max_length=200)


class SetupPasswordIn(BaseModel):
    identifier: str = Field(min_length=3, max_length=254)
    code: str = Field(
        min_length=6, max_length=40, description="The one-time code from an administrator."
    )
    password: str = Field(min_length=1, max_length=200)


class ChangePasswordIn(BaseModel):
    current: str = Field(min_length=1, max_length=200)
    new: str = Field(min_length=1, max_length=200)


class MeOut(BaseModel):
    """GET /auth/me: who the server says the caller is."""

    user_id: str
    display_name: str | None
    role: str
    is_owner: bool = Field(default=False, description="The company's owner Credit Officer.")
    is_platform: bool = Field(default=False, description="A CredLens platform administrator.")
    organization_id: str | None = Field(description="None for a platform administrator.")
    organization_name: str | None
    environment: Literal["benchmark", "pilot", "production"] | None
    fsr_label: str | None = Field(
        default=None, description="What the company calls its Field Sales Representatives."
    )


class RegistrationPerson(BaseModel):
    """The personal part of both registration forms."""

    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(max_length=120)
    email: str = Field(max_length=254)
    mobile: str = Field(max_length=32)
    department: str = Field(default="", max_length=80)
    password: str = Field(max_length=200)
    confirm_password: str = Field(max_length=200)


class CompanyRegisterIn(RegistrationPerson):
    """POST /auth/register/company: a new company and its first Credit Officer."""

    legal_name: str = Field(max_length=160)
    trading_name: str = Field(default="", max_length=160)
    registration_number: str = Field(default="", max_length=64)
    org_type: str = Field(max_length=32)
    sector: str = Field(max_length=80)
    official_email: str = Field(max_length=254)
    contact_number: str = Field(max_length=32)
    country: str = Field(default="BD", max_length=2)
    division: str = Field(max_length=80)
    city: str = Field(max_length=80)
    address: str = Field(max_length=400)
    website: str = Field(default="", max_length=200)


class JoinRegisterIn(RegistrationPerson):
    """POST /auth/register/join: an employee joining with a company invitation code."""

    invitation_code: str = Field(max_length=40)
    role: Literal["fsr", "credit_officer"]
    employee_id: str = Field(default="", max_length=40)
    territory: str = Field(default="", max_length=120)


class RegisteredOut(BaseModel):
    """What a registration returns: nothing secret. The person then signs in."""

    registered: bool = True
    organization_name: str
    role: str


class InvitationPreviewOut(BaseModel):
    """GET /auth/invitations/preview: what a valid code opens (shown on the join form)."""

    organization_name: str
    role: str
    default_territory: str | None


class InvitationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["fsr", "credit_officer"]
    days: int | None = Field(default=None, ge=1, le=365)
    max_uses: int = Field(default=1, ge=1, le=1000)
    default_territory: str | None = Field(default=None, max_length=120)
    label: str | None = Field(default=None, max_length=80)


class InvitationUseOut(BaseModel):
    user_id: str
    display_name: str | None
    employee_id: str | None
    used_at: str


class InvitationOut(BaseModel):
    invitation_id: str
    role: str
    label: str | None
    default_territory: str | None
    code_hint: str = Field(description="The last four characters; the full code is shown once.")
    state: Literal["active", "revoked", "expired", "used_up"]
    expires_at: str
    max_uses: int
    use_count: int
    created_by: str
    created_at: str
    uses: list[InvitationUseOut] = []


class InvitationCreatedOut(BaseModel):
    """A new invitation with its code. The code is shown ONCE; only its hash is kept."""

    invitation: InvitationOut
    code: str


class EmployeeOut(BaseModel):
    user_id: str
    full_name: str
    email: str | None
    mobile: str | None
    role: str
    is_owner: bool
    status: Literal["active", "disabled"]
    job_title: str | None
    department: str | None
    employee_id: str | None
    territory: str | None
    registered_at: str
    assigned_shops: int


class SetupCodeOut(BaseModel):
    """A one-time code, shown once. Give it to the person; they set their own password."""

    employee: EmployeeOut
    setup_code: str
    expires_at: str


class OrganizationProfileOut(BaseModel):
    organization_id: str
    name: str
    legal_name: str | None
    trading_name: str | None
    registration_number: str | None
    org_type: str | None
    sector: str | None
    official_email: str | None
    contact_number: str | None
    country: str
    division: str | None
    city: str | None
    address: str | None
    website: str | None
    status: str
    environment: str
    fsr_label: str | None
    created_at: str


class OrganizationProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fsr_label: str | None = Field(default=None, max_length=48)
    contact_number: str | None = Field(default=None, max_length=32)
    website: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=400)


class PlatformOrgOut(BaseModel):
    organization_id: str
    name: str
    legal_name: str | None
    org_type: str | None
    city: str | None
    status: str
    environment: str
    created_at: str
    credit_officers: int
    fsrs: int
    merchants: int


class PlatformOrgStatusIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["active", "suspended"]


class ShopAssignmentOut(BaseModel):
    merchant_id: str
    shop_name: str | None
    area: str | None
    district: str | None
    fsr_user_id: str | None
    fsr_name: str | None
    assigned_at: str | None
    assigned_by: str | None


class AssignIn(BaseModel):
    merchant_id: str = Field(min_length=1, max_length=32)
    fsr_user_id: str = Field(min_length=1, max_length=32)


# --- merchant registration and paper consent (Phase 2) ------------------------------------


class RegistrationDetailsIn(BaseModel):
    """The merchant details of the registration form. Every field is text; the server checks
    and normalises them. `confirm_new` says staff checked the likely duplicates."""

    model_config = ConfigDict(extra="forbid")

    shop_name: str | None = Field(default=None, max_length=80)
    legal_name: str | None = Field(default=None, max_length=120)
    owner_name: str | None = Field(default=None, max_length=120)
    owner_mobile: str | None = Field(default=None, max_length=32)
    alternate_contact: str | None = Field(default=None, max_length=32)
    district: str | None = None
    area: str | None = Field(default=None, max_length=80)
    shop_type: str | None = None
    ownership_type: str | None = None
    established_year: str | int | None = None
    trade_license_number: str | None = Field(default=None, max_length=60)
    branches: str | int | None = None
    representative_name: str | None = Field(default=None, max_length=120)
    representative_mobile: str | None = Field(default=None, max_length=32)
    confirm_new: bool = False


class ExtractionJobOut(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "failed"]
    engine: str | None
    engine_version: str | None
    pages: int | None
    error: str | None
    queued_at: str
    finished_at: str | None


class ExtractionFieldOut(BaseModel):
    field_id: int
    key: str
    label_en: str
    label_bn: str
    value: str | None
    confidence: float | None
    method: str
    expected: str | None
    state: str
    reviewed_value: str | None
    page: int | None


class RegistrationOut(BaseModel):
    reg_id: str
    reg_ref: str
    merchant_id: str | None
    method: Literal["manual", "blank_form"]
    status: str
    template_version: str
    template_approved: bool
    shop_name: str | None
    details: dict[str, Any]
    optional_consents: list[str]
    form_serial: str | None
    created_by: str
    created_by_name: str | None
    created_at: str
    uploaded_by: str | None
    uploaded_at: str | None
    signer_name: str | None
    signed_on: str | None
    verified_by: str | None
    verified_at: str | None
    verification_mode: str | None
    reviewer_note: str | None
    has_document: bool
    can_verify: bool = Field(description="False when this officer uploaded it and others exist.")
    job: ExtractionJobOut | None


class ExtractionOut(BaseModel):
    job: ExtractionJobOut | None
    fields: list[ExtractionFieldOut]


class FieldReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str | None = Field(default=None, max_length=400, description="Empty: confirm as read.")


class VerifyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    categories: list[str]
    optional: list[str] = []
    signer_name: str = Field(max_length=120)
    signed_on: str | None = Field(default=None, description="YYYY-MM-DD; default today.")
    signature_checked: bool
    reference_matches: bool


class ReasonIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(max_length=500)


class ConsentTemplateOut(BaseModel):
    version: str
    status: Literal["draft", "legal_review", "approved", "retired"]
    legal_review_ref: str | None
    approved_by: str | None
    approved_at: str | None
    sections: int
    note: str


class ConsentTemplateStatusIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["draft", "legal_review", "approved", "retired"]
    legal_review_ref: str | None = Field(default=None, max_length=200)


# --- daily records, submissions, notifications (Phases 4 and 5) ---------------------------


class DailyRowIn(BaseModel):
    """One row of a daily sheet as the grid sends it. Dates are YYYY-MM-DD; numbers may be text."""

    model_config = ConfigDict(extra="forbid")

    entry_id: str | None = None
    entry_type: str
    txn_date: str | None = None
    category: str | None = None
    description: str | None = None
    quantity: str | float | None = None
    unit: str | None = None
    unit_price: str | float | None = None
    amount_bdt: str | float | None = None
    counterparty: str | None = None
    payment_method: str | None = None
    payment_status: str | None = None
    due_date: str | None = None
    note: str | None = None
    source: str | None = None
    extraction_confidence: float | None = None


class DailySaveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: list[DailyRowIn]
    delete_missing: bool = Field(default=True, description="Draft rows not sent are deleted.")


class AmendIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(max_length=300)
    txn_date: str | None = None
    category: str | None = None
    description: str | None = None
    quantity: str | float | None = None
    unit: str | None = None
    unit_price: str | float | None = None
    amount_bdt: str | float | None = None
    counterparty: str | None = None
    payment_method: str | None = None
    payment_status: str | None = None
    due_date: str | None = None
    note: str | None = None


class DailyEntryOut(BaseModel):
    entry_id: str
    sheet_id: str
    business_date: str
    row_no: int
    entry_type: str
    status: Literal["draft", "submitted", "superseded"]
    txn_date: str | None
    category: str | None
    description: str | None
    quantity: float | None
    unit: str | None
    unit_price: float | None
    amount_bdt: float | None
    counterparty: str | None
    payment_method: str | None
    payment_status: str | None
    due_date: str | None
    note: str | None
    source: str
    extraction_confidence: float | None
    supersedes_entry_id: str | None
    amend_reason: str | None
    scored: bool = Field(description="True when this kind of row is also used by the assessment.")
    created_by: str


class DailySheetOut(BaseModel):
    sheet_id: str
    merchant_id: str
    business_date: str
    fsr_user_id: str
    fsr_name: str | None
    status: Literal["draft", "submitted", "returned", "accepted"]
    submitted_at: str | None
    returned_reason: str | None
    drafts: int
    submitted: int
    totals: dict[str, float]


class DailyDayOut(BaseModel):
    """GET and PUT /merchants/{id}/daily/{date}: the sheet, its rows, and row problems."""

    sheet: DailySheetOut | None
    entries: list[DailyEntryOut]
    errors: dict[str, dict[str, str]] = {}


class EntryTypeOut(BaseModel):
    key: str
    en: str
    bn: str
    scored: bool
    fields: list[str]
    required: list[str]
    labels: dict[str, str]


class DailyListOut(BaseModel):
    sheets: list[DailySheetOut]
    entries: list[DailyEntryOut]


class SubmissionOut(BaseModel):
    sheet_id: str
    merchant_id: str
    shop_name: str | None
    business_date: str
    fsr_user_id: str
    fsr_name: str | None
    status: Literal["draft", "submitted", "returned", "accepted"]
    rows: int
    drafts: int
    totals: dict[str, float]
    submitted_at: str | None
    returned_reason: str | None


class FsrShopOut(BaseModel):
    merchant_id: str
    shop_name: str | None
    area: str | None
    district: str | None
    today_status: str | None
    today_drafts: int
    last_submitted: str | None


class FsrOverviewOut(BaseModel):
    territory: str | None
    employee_id: str | None
    today: str
    shops: list[FsrShopOut]
    returned: int
    pending_drafts: int
    submitted_today: int


class NotificationOut(BaseModel):
    notification_id: str
    kind: str
    text: str
    link: str | None
    created_at: str
    read: bool


class AssignmentHistoryOut(BaseModel):
    merchant_id: str
    shop_name: str | None
    fsr_user_id: str
    fsr_name: str | None
    assigned_at: str
    assigned_by: str
    ended_at: str | None
    ended_by: str | None


class BulkAssignIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    merchant_ids: list[str] = Field(min_length=1, max_length=200)
    fsr_user_id: str


class FsrDetailOut(BaseModel):
    employee: EmployeeOut
    shops: list[ShopAssignmentOut]
    recent_sheets: list[SubmissionOut]
    drafts_open: int
    returned_open: int


class ImportTableOut(BaseModel):
    """A table read from an uploaded file, for the FSR to map, correct and load as drafts."""

    job_id: str
    status: Literal["queued", "running", "done", "failed"]
    method: str | None = None
    headers: list[str] = []
    rows: list[list[str]] = []
    confidences: list[float] = []
    notes: list[str] = []
    suggested_mapping: dict[str, int] = {}
    error: str | None = None
