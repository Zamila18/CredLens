"""Adapter for the `homecredit` data mode (public real-label check, large scale).

Purpose: map the Kaggle Home Credit Default Risk files (application_train,
    installments_payments, POS_CASH_balance) into the data contract.
Owner role: B (data engineer).
Implements: docs/DATASET_PLAN.md sections 2.1 and 3; PROJECT_BRIEF section 18. Built in Phase 7.

The data does not state which country it comes from, so every screen and model
card labels it "country not stated": it adds scale, it does not support an
Asian claim. It covers consumer loans with instalment history. It has no
purchase, delivery or questionnaire data: those streams stay empty; nothing is
generated to fill them. The raw files are downloaded by a human into
data/raw/homecredit/ under the Kaggle competition rules and are never
committed or redistributed.
"""

from __future__ import annotations

import pandas as pd

from src.adapters.base import DataAdapter, empty_frame

_NOT_YET = "homecredit adapter: {what} is not implemented yet (Phase 7, public-data adapters)."


class HomeCreditAdapter(DataAdapter):
    """Reads the Home Credit application and instalment files."""

    mode = "homecredit"

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
