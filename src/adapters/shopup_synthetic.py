"""Adapter for the `synthetic_bd` data mode (the main demo).

Purpose: serve the Bangladesh-calibrated synthetic tables written by the generator.
Owner role: B (data engineer).
Implements: PROJECT_BRIEF section 5 and docs/GENERATOR_SPEC.md. Built in Phase 1.

All four streams exist in this mode. The data is generated, never real.
"""

from __future__ import annotations

import pandas as pd

from src.adapters.base import DataAdapter

_NOT_YET = "synthetic_bd adapter: {what} is not implemented yet (Phase 1, synthetic generator)."


class ShopUpSyntheticAdapter(DataAdapter):
    """Reads the generated CSVs for the synthetic ShopUp-shaped data."""

    mode = "synthetic_bd"

    def load_merchants(self) -> pd.DataFrame:
        raise NotImplementedError(_NOT_YET.format(what="load_merchants"))

    def load_purchases(self) -> pd.DataFrame:
        raise NotImplementedError(_NOT_YET.format(what="load_purchases"))

    def load_deliveries(self) -> pd.DataFrame:
        raise NotImplementedError(_NOT_YET.format(what="load_deliveries"))

    def load_payments(self) -> pd.DataFrame:
        raise NotImplementedError(_NOT_YET.format(what="load_payments"))

    def load_loans(self) -> pd.DataFrame:
        raise NotImplementedError(_NOT_YET.format(what="load_loans"))

    def load_questionnaire(self) -> pd.DataFrame:
        raise NotImplementedError(_NOT_YET.format(what="load_questionnaire"))

    def load_consents(self) -> pd.DataFrame:
        raise NotImplementedError(_NOT_YET.format(what="load_consents"))

    def audit_frame(self) -> pd.DataFrame:
        raise NotImplementedError(_NOT_YET.format(what="audit_frame"))
