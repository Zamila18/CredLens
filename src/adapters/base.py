"""The data contract and the abstract adapter every data source implements.

Purpose: define the seven tables (names and columns) the whole pipeline uses,
    and the interface an adapter must provide to fill them.
Owner role: B (data engineer).
Implements: PROJECT_BRIEF section 5 (data contract) and section 18 (no invented
    history on real rows: a stream a source does not have stays empty).

Rules for every adapter:
- Each `load_*` method returns a pandas DataFrame with exactly the contract columns.
- A stream the source does not have returns an empty frame with the right
  columns. Nothing is generated to fill it.
- Group columns used only for fairness checks come back from `audit_frame()`
  and must never be passed to the model.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

# Table name -> column names, in order. All ids are strings; dates are ISO text.
CONTRACT: dict[str, list[str]] = {
    "merchants": [
        "merchant_id",
        "onboarded_at",
        "district",
        "town_tier",
        "shop_type",
        "has_trade_license",
        "consent_data_use",
        "questionnaire_done",
    ],
    # Mokam-style wholesale purchases: what the merchant BUYS. Never sales.
    "purchases": [
        "purchase_id",
        "merchant_id",
        "purchase_date",
        "amount_bdt",
        "category",
        "supplier_id",
    ],
    # REDX-style outgoing parcels to the merchant's own customers.
    "deliveries": [
        "delivery_id",
        "merchant_id",
        "dispatched_at",
        "delivered_at",
        "status",
        "return_reason",
        "is_cod",
        "cod_remitted_on_time",
    ],
    # Baki-style repayments.
    "payments": [
        "payment_id",
        "merchant_id",
        "loan_id",
        "due_date",
        "paid_date",
        "amount_due_bdt",
        "amount_paid_bdt",
    ],
    "loans": [
        "loan_id",
        "merchant_id",
        "issued_at",
        "limit_bdt",
        "outcome_label",
        "label_observed_at",
    ],
    # FinHealth-style items, 1 to 5. Shown beside the score, not inside the model.
    "questionnaire": [
        "merchant_id",
        "spend1",
        "spend2",
        "save1",
        "save2",
        "borrow1",
        "borrow2",
        "plan1",
        "plan2",
        "stress",
        "confidence",
        "answered_at",
    ],
    "consents": [
        "consent_id",
        "merchant_id",
        "purpose",
        "data_categories",
        "granted_at",
        "expires_at",
        "revoked_at",
    ],
}


def empty_frame(table: str) -> pd.DataFrame:
    """Return an empty DataFrame with the contract columns for one table."""
    return pd.DataFrame(columns=CONTRACT[table])


def check_frame(table: str, frame: pd.DataFrame) -> pd.DataFrame:
    """Check that a frame has exactly the contract columns and return them in order.

    Raises ValueError naming the missing and unexpected columns.
    """
    expected = CONTRACT[table]
    missing = [column for column in expected if column not in frame.columns]
    unexpected = [column for column in frame.columns if column not in expected]
    if missing or unexpected:
        raise ValueError(
            f"Table '{table}' does not match the data contract. "
            f"Missing columns: {missing or 'none'}. Unexpected columns: {unexpected or 'none'}."
        )
    return frame[expected]


class DataAdapter(ABC):
    """Base class for a data source. Subclasses set `mode` and fill the methods."""

    #: The data mode this adapter serves, for example "synthetic_bd".
    mode: str = ""

    def __init__(self, config: dict[str, Any]) -> None:
        """Keep the validated config (see src/config.py) for the subclass to read."""
        self.config = config

    @abstractmethod
    def load_merchants(self) -> pd.DataFrame:
        """One row per merchant: the single master table."""

    @abstractmethod
    def load_purchases(self) -> pd.DataFrame:
        """Wholesale purchases made by the merchant."""

    @abstractmethod
    def load_deliveries(self) -> pd.DataFrame:
        """Outgoing parcels sent by the merchant."""

    @abstractmethod
    def load_payments(self) -> pd.DataFrame:
        """Repayments against loans."""

    @abstractmethod
    def load_loans(self) -> pd.DataFrame:
        """Loans with their outcome label (1 = repaid fine, 0 = late or default)."""

    @abstractmethod
    def load_questionnaire(self) -> pd.DataFrame:
        """Questionnaire answers, where they exist."""

    @abstractmethod
    def load_consents(self) -> pd.DataFrame:
        """Consent records; scoring is refused without a valid one."""

    @abstractmethod
    def audit_frame(self) -> pd.DataFrame:
        """Group columns for fairness checks, keyed by merchant_id. Never model inputs."""

    def load_all(self) -> dict[str, pd.DataFrame]:
        """Load every contract table and check each one against the contract."""
        loaders = {
            "merchants": self.load_merchants,
            "purchases": self.load_purchases,
            "deliveries": self.load_deliveries,
            "payments": self.load_payments,
            "loans": self.load_loans,
            "questionnaire": self.load_questionnaire,
            "consents": self.load_consents,
        }
        return {table: check_frame(table, loader()) for table, loader in loaders.items()}
