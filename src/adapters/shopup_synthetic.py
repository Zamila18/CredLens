"""Adapter for the `synthetic_bd` data mode (the main demo).

Purpose: serve the Bangladesh-calibrated synthetic tables written by the generator.
Owner role: B (data engineer).
Implements: PROJECT_BRIEF section 5 and docs/GENERATOR_SPEC.md.

All streams exist in this mode. The data is generated, never real. The tables are
read from data/raw/synthetic_bd/strength_<s>/, where <s> is the delivery signal
strength in the config. Create them with: python tasks.py data

The generator also writes a hidden-truth file next to the tables. This adapter never
reads it, so nothing downstream can see a merchant's hidden reliability.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.adapters.base import CONTRACT, DataAdapter, check_frame
from src.synth.paths import output_dir

# Columns that hold true/false values, and columns that may be empty.
BOOLEAN_COLUMNS = {
    "merchants": ["has_trade_license", "consent_data_use", "questionnaire_done"],
    "deliveries": ["is_cod"],
}
NULLABLE_BOOLEAN_COLUMNS = {"deliveries": ["cod_remitted_on_time"]}
NUMBER_COLUMNS = {
    "purchases": ["amount_bdt"],
    "payments": ["amount_due_bdt", "amount_paid_bdt"],
    "loans": ["limit_bdt"],
}
QUESTIONNAIRE_ITEMS = [
    column for column in CONTRACT["questionnaire"] if column not in ("merchant_id", "answered_at")
]
NULLABLE_INTEGER_COLUMNS = {"loans": ["outcome_label"], "questionnaire": QUESTIONNAIRE_ITEMS}
AUDIT_COLUMNS = ["town_tier", "shop_type", "has_trade_license"]


class ShopUpSyntheticAdapter(DataAdapter):
    """Reads the generated CSVs for the synthetic ShopUp-shaped data."""

    mode = "synthetic_bd"

    def __init__(self, config: dict[str, Any], folder: Path | str | None = None) -> None:
        """Use `folder` to read tables from somewhere other than the default location."""
        super().__init__(config)
        self.folder = Path(folder) if folder is not None else output_dir(config)

    def _read(self, table: str) -> pd.DataFrame:
        """Read one table. Ids and dates stay as text; numbers and flags get real types."""
        path = self.folder / f"{table}.csv"
        if not path.exists():
            raise FileNotFoundError(
                f"Synthetic table not found: {path}. Create it with: python tasks.py data"
            )
        frame = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
        for column in BOOLEAN_COLUMNS.get(table, []):
            frame[column] = frame[column] == "True"
        for column in NULLABLE_BOOLEAN_COLUMNS.get(table, []):
            frame[column] = frame[column].map({"True": True, "False": False}).astype("boolean")
        for column in NUMBER_COLUMNS.get(table, []):
            frame[column] = frame[column].astype(float)
        for column in NULLABLE_INTEGER_COLUMNS.get(table, []):
            frame[column] = pd.to_numeric(frame[column]).astype("Int64")
        return check_frame(table, frame)

    def load_merchants(self) -> pd.DataFrame:
        return self._read("merchants")

    def load_purchases(self) -> pd.DataFrame:
        return self._read("purchases")

    def load_deliveries(self) -> pd.DataFrame:
        return self._read("deliveries")

    def load_payments(self) -> pd.DataFrame:
        return self._read("payments")

    def load_loans(self) -> pd.DataFrame:
        return self._read("loans")

    def load_questionnaire(self) -> pd.DataFrame:
        return self._read("questionnaire")

    def load_consents(self) -> pd.DataFrame:
        return self._read("consents")

    def audit_frame(self) -> pd.DataFrame:
        """Group columns for fairness checks. They are never passed to the model."""
        return self.load_merchants()[["merchant_id", *AUDIT_COLUMNS]]
