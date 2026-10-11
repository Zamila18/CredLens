"""Stub adapter for a future ShopUp (or similar lender) data extract.

Purpose: the place where a partner's real extract would be mapped into the data
    contract, if one is ever shared.
Owner role: B (data engineer).
Implements: docs/REAL_DATA_SWITCH.md and docs/DATA_REQUEST_SHOPUP.md; PROJECT_BRIEF section 15.

This is not one of the three data modes and the factory does not offer it.
No partner data exists in this project. If an extract arrives, keep it outside
the repository and follow docs/REAL_DATA_SWITCH.md before writing any code here.
"""

from __future__ import annotations

import pandas as pd

from src.adapters.base import DataAdapter

_NOT_YET = (
    "shopup_real adapter: {what} is a stub. No partner data exists in this project. "
    "See docs/REAL_DATA_SWITCH.md."
)


class ShopUpRealAdapter(DataAdapter):
    """Placeholder for a partner extract. Every method is a stub."""

    mode = "shopup_real"

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
