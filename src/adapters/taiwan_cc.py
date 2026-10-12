"""Adapter for the `taiwan_cc` data mode (public real-label check, payment behaviour).

Purpose: map the UCI "Default of Credit Card Clients" data (Taiwan) into the
    data contract.
Owner role: B (data engineer).
Implements: docs/DATASET_PLAN.md sections 2.1 and 3; PROJECT_BRIEF section 18. Built in Phase 7.

The source has credit-card clients with repayment, bill and payment history and
a default label. It has no purchase, delivery or questionnaire data: those
streams stay empty; nothing is generated to fill them. The raw file is
downloaded by a human into data/raw/taiwan_cc/ and is never committed.
"""

from __future__ import annotations

import pandas as pd

from src.adapters.base import DataAdapter, empty_frame

_NOT_YET = "taiwan_cc adapter: {what} is not implemented yet (Phase 7, public-data adapters)."


class TaiwanCreditCardAdapter(DataAdapter):
    """Reads the Taiwan credit-card default file."""

    mode = "taiwan_cc"

    def load_merchants(self) -> pd.DataFrame:
        raise NotImplementedError(_NOT_YET.format(what="load_merchants"))

    def load_purchases(self) -> pd.DataFrame:
        """The source has no purchase history: empty by design."""
        return empty_frame("purchases")

    def load_deliveries(self) -> pd.DataFrame:
        """The source has no delivery history: empty by design."""
        return empty_frame("deliveries")

    def load_payments(self) -> pd.DataFrame:
        raise NotImplementedError(_NOT_YET.format(what="load_payments"))

    def load_loans(self) -> pd.DataFrame:
        raise NotImplementedError(_NOT_YET.format(what="load_loans"))

    def load_questionnaire(self) -> pd.DataFrame:
        """The source has no questionnaire: empty by design."""
        return empty_frame("questionnaire")

    def load_consents(self) -> pd.DataFrame:
        raise NotImplementedError(_NOT_YET.format(what="load_consents"))

    def audit_frame(self) -> pd.DataFrame:
        raise NotImplementedError(_NOT_YET.format(what="audit_frame"))
