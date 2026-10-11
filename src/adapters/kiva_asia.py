"""Adapter for the `kiva_asia` data mode (public real-label check, small businesses).

Purpose: map the Kiva loan snapshot, filtered to Asia and Retail/Food/Services,
    into the data contract.
Owner role: B (data engineer).
Implements: docs/DATASET_PLAN.md sections 2.1 and 3; PROJECT_BRIEF section 18. Built in Phase 7.

Kiva has loans and outcomes but no purchase, delivery, payment or questionnaire
history. Those streams stay empty; nothing is generated to fill them. The raw
file is downloaded by a human into data/raw/kiva/ and is never committed.
"""

from __future__ import annotations

import pandas as pd

from src.adapters.base import DataAdapter, empty_frame

_NOT_YET = "kiva_asia adapter: {what} is not implemented yet (Phase 7, public-data adapters)."


class KivaAsiaAdapter(DataAdapter):
    """Reads the Kiva snapshot and returns Asian small-business loans."""

    mode = "kiva_asia"

    def load_merchants(self) -> pd.DataFrame:
        raise NotImplementedError(_NOT_YET.format(what="load_merchants"))

    def load_purchases(self) -> pd.DataFrame:
        """Kiva has no purchase history: empty by design."""
        return empty_frame("purchases")

    def load_deliveries(self) -> pd.DataFrame:
        """Kiva has no delivery history: empty by design."""
        return empty_frame("deliveries")

    def load_payments(self) -> pd.DataFrame:
        """Kiva has no pre-loan payment history: empty by design."""
        return empty_frame("payments")

    def load_loans(self) -> pd.DataFrame:
        raise NotImplementedError(_NOT_YET.format(what="load_loans"))

    def load_questionnaire(self) -> pd.DataFrame:
        """Kiva has no questionnaire: empty by design."""
        return empty_frame("questionnaire")

    def load_consents(self) -> pd.DataFrame:
        raise NotImplementedError(_NOT_YET.format(what="load_consents"))

    def audit_frame(self) -> pd.DataFrame:
        raise NotImplementedError(_NOT_YET.format(what="audit_frame"))
