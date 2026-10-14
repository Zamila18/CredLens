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

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DataMode = Literal["synthetic_bd", "kiva_asia", "taiwan_cc", "india_ltfs", "homecredit"]
Band = Literal["Strong", "Review", "Needs more info"]
Role = Literal["officer", "admin", "viewer"]
OfficerAction = Literal["accept", "override_up", "override_down", "needs_more_info"]

OVERRIDE_ACTIONS = ("override_up", "override_down")


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
    consent_valid: bool


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
    amount_bdt: float | None = None


class MerchantProfile(BaseModel):
    """GET /merchants/{id}. A stream the data source does not have is null."""

    merchant_id: str
    data_mode: DataMode
    onboarded_at: str
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
    reason_text: str | None = None

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
    officer_action: OfficerAction
    reason_text: str | None = None
    decided_at: str


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
