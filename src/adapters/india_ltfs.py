"""Adapter for the `india_ltfs` data mode (public real-label check, Indian borrowers).

Purpose: map the L&T vehicle loan file (Kaggle, `train.csv`) into the data contract.
Owner role: B (data engineer).
Implements: docs/DATASET_PLAN.md and PROJECT_BRIEF section 18. Built in Phase 7.

What the file is (checked Oct 12, 2026): 233,154 vehicle loans disbursed in India
between August and October 2018, with bureau history at the time of disbursement.
The outcome is "payment default in the first EMI on due date": missing the first
monthly instalment, not the loan eventually going bad. About half the borrowers
have no bureau record, which makes this a real thin-file population.

It has no purchase, delivery, pre-loan payment or questionnaire data: those
streams stay empty; nothing is generated to fill them. The dataset states no
usage terms. The raw file is downloaded by a human into data/raw/india_ltfs/ and
is never committed or redistributed.
"""

from __future__ import annotations

import pandas as pd

from src.adapters.base import DataAdapter, empty_frame

_NOT_YET = "india_ltfs adapter: {what} is not implemented yet (Phase 7, public-data adapters)."


class IndiaLtfsAdapter(DataAdapter):
    """Reads the India L&T vehicle loan file."""

    mode = "india_ltfs"

    def load_merchants(self) -> pd.DataFrame:
        raise NotImplementedError(_NOT_YET.format(what="load_merchants"))

    def load_purchases(self) -> pd.DataFrame:
        """The source has no purchase history: empty by design."""
        return empty_frame("purchases")

    def load_deliveries(self) -> pd.DataFrame:
        """The source has no delivery history: empty by design."""
        return empty_frame("deliveries")

    def load_payments(self) -> pd.DataFrame:
        """The source has bureau summaries but no payment records: empty by design."""
        return empty_frame("payments")

    def load_loans(self) -> pd.DataFrame:
        raise NotImplementedError(_NOT_YET.format(what="load_loans"))

    def load_questionnaire(self) -> pd.DataFrame:
        """The source has no questionnaire: empty by design."""
        return empty_frame("questionnaire")

    def load_consents(self) -> pd.DataFrame:
        raise NotImplementedError(_NOT_YET.format(what="load_consents"))

    def audit_frame(self) -> pd.DataFrame:
        raise NotImplementedError(_NOT_YET.format(what="audit_frame"))
