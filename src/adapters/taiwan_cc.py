"""Adapter for the `taiwan_cc` data mode (public real-label check, payment behaviour).

Purpose: map the UCI "Default of Credit Card Clients" data (Taiwan, 2005) into the
    data contract.
Owner role: B (data engineer).
Implements: docs/DATASET_PLAN.md sections 2.1 and 3; PROJECT_BRIEF section 18, item 29.
    Source and licence (CC BY 4.0): docs/DATA_SOURCES.md section 1.1.

The file has 30,000 credit-card clients, each with a credit limit, six months of
statements (April to September 2005) and whether they defaulted in October 2005.

What goes where:
- merchants: one row per client. The source has no district, town, shop type or licence:
  those stay empty.
- loans: one row per client, the October 2005 decision. `outcome_label` = 1 when the
  client did NOT default. `limit_bdt` holds the credit limit in New Taiwan dollars (the
  contract's column names say "bdt"; the amounts are not converted).
- payments: the six monthly statements: the bill, the amount paid that month, and the
  last day of the month as the date. The source gives months only, so the day is nominal.
- purchases, deliveries, questionnaire: the source has none. Empty; nothing is generated.
- consents: public data has no consent records. Each client gets one row marked
  "public_dataset" so the same consent check runs; it is not a real consent.
- audit_frame: sex, education, marital status and age band. Audit only, never model inputs.
- source_records: the whitelisted statement columns the feature builder may read
  (src/features/taiwan_cc.py). The outcome and the audit columns are not in it.

The raw file is downloaded by a human into data/raw/taiwan_cc/ and is never committed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.adapters.base import DataAdapter, empty_frame
from src.config import PROJECT_ROOT
from src.features.taiwan_cc import (
    AUDIT_SOURCE_COLUMNS,
    BILL_COLUMNS,
    DECISION_DATE,
    LIMIT_COLUMN,
    OUTCOME_COLUMN,
    PAID_COLUMNS,
    WHITELIST,
)

RAW_FOLDER = PROJECT_ROOT / "data" / "raw" / "taiwan_cc"
FIRST_MONTH = "2005-04-01"  # the first statement month
OUTCOME_KNOWN = "2005-10-31"  # the end of the month the outcome describes
# Statement months, newest first, matching BILL_AMT1..6 and PAY_AMT1..6.
MONTH_ENDS = ["2005-09-30", "2005-08-31", "2005-07-31", "2005-06-30", "2005-05-31", "2005-04-30"]
CONSENT_PURPOSE = "public_dataset"
EXPECTED_COLUMNS = ["ID", *WHITELIST, *AUDIT_SOURCE_COLUMNS, OUTCOME_COLUMN]


class TaiwanCreditCardAdapter(DataAdapter):
    """Reads the Taiwan credit-card default file.

    Args:
        config: the validated config.
        folder: where the file is; defaults to data/raw/taiwan_cc/. Tests pass a folder
            with a tiny hand-made CSV that has the same columns.
    """

    mode = "taiwan_cc"

    def __init__(self, config: dict[str, Any], folder: Path | str | None = None) -> None:
        super().__init__(config)
        self.folder = Path(folder) if folder is not None else RAW_FOLDER
        self._raw: pd.DataFrame | None = None

    def _read(self) -> pd.DataFrame:
        """Read the file once, check its columns, and give every client our ids."""
        if self._raw is not None:
            return self._raw
        files = sorted(self.folder.glob("*.xls")) + sorted(self.folder.glob("*.csv"))
        if not files:
            raise FileNotFoundError(
                f"No Taiwan credit-card file in {self.folder}. Download 'default of credit "
                "card clients.xls' from the UCI page (docs/DATA_SOURCES.md, section 1.1) "
                "and save it there."
            )
        path = files[0]
        # The .xls has an extra first row (X1, X2, ...) above the real column names.
        frame = pd.read_excel(path, header=1) if path.suffix == ".xls" else pd.read_csv(path)
        missing = [column for column in EXPECTED_COLUMNS if column not in frame.columns]
        if missing:
            raise ValueError(f"{path.name} is not the expected file. Missing columns: {missing}.")
        frame = frame[EXPECTED_COLUMNS].copy()
        if frame["ID"].duplicated().any():
            raise ValueError(f"{path.name} has repeated client ids.")

        sample_size = self.config["data"][self.mode]["sample_size"]
        if sample_size is not None and sample_size < len(frame):
            frame = frame.sample(n=sample_size, random_state=self.config["seed"]).sort_values("ID")
        frame = frame.reset_index(drop=True)
        number = frame["ID"].astype(int).astype(str).str.zfill(6)
        frame["merchant_id"] = "TW" + number
        frame["loan_id"] = "TWL" + number
        self._raw = frame
        return frame

    def load_merchants(self) -> pd.DataFrame:
        raw = self._read()
        merchants = empty_frame("merchants").reindex(range(len(raw)))
        merchants["merchant_id"] = raw["merchant_id"]
        merchants["onboarded_at"] = FIRST_MONTH
        merchants["consent_data_use"] = True  # public data set; see load_consents
        merchants["questionnaire_done"] = False
        return merchants

    def load_purchases(self) -> pd.DataFrame:
        """The source has no purchase history: empty by design."""
        return empty_frame("purchases")

    def load_deliveries(self) -> pd.DataFrame:
        """The source has no delivery history: empty by design."""
        return empty_frame("deliveries")

    def load_payments(self) -> pd.DataFrame:
        """The six monthly statements of every client: bill, amount paid, month end."""
        raw = self._read()
        months = []
        for position, month_end in enumerate(MONTH_ENDS):
            paid = raw[PAID_COLUMNS[position]].astype(float)
            months.append(
                pd.DataFrame(
                    {
                        "payment_id": raw["loan_id"] + f"-{month_end[:7]}",
                        "merchant_id": raw["merchant_id"],
                        "loan_id": raw["loan_id"],
                        "due_date": month_end,
                        # A date only when something was paid that month.
                        "paid_date": np.where(paid > 0, month_end, None),
                        # A negative bill is a credit balance: nothing was due.
                        "amount_due_bdt": raw[BILL_COLUMNS[position]].astype(float).clip(lower=0),
                        "amount_paid_bdt": paid,
                    }
                )
            )
        payments = pd.concat(months, ignore_index=True)
        return payments.sort_values(["merchant_id", "due_date"]).reset_index(drop=True)

    def load_loans(self) -> pd.DataFrame:
        raw = self._read()
        return pd.DataFrame(
            {
                "loan_id": raw["loan_id"],
                "merchant_id": raw["merchant_id"],
                "issued_at": DECISION_DATE,
                "limit_bdt": raw[LIMIT_COLUMN].astype(float),
                "outcome_label": 1 - raw[OUTCOME_COLUMN].astype(int),  # 1 = did not default
                "label_observed_at": OUTCOME_KNOWN,
            }
        )

    def load_questionnaire(self) -> pd.DataFrame:
        """The source has no questionnaire: empty by design."""
        return empty_frame("questionnaire")

    def load_consents(self) -> pd.DataFrame:
        """One row per client, marked as a public data set. Not a real consent record."""
        raw = self._read()
        return pd.DataFrame(
            {
                "consent_id": "TWC" + raw["merchant_id"].str[2:],
                "merchant_id": raw["merchant_id"],
                "purpose": CONSENT_PURPOSE,
                "data_categories": "payments",
                "granted_at": FIRST_MONTH,
                "expires_at": "2099-12-31",
                "revoked_at": None,
            }
        )

    def audit_frame(self) -> pd.DataFrame:
        """Sex, education, marital status and age band: for the group audit only."""
        raw = self._read()
        edges = self.config["data"][self.mode]["age_band_edges"]
        labels = (
            [f"under {edges[0]}"]
            + [f"{low} to {high - 1}" for low, high in zip(edges, edges[1:])]
            + [f"{edges[-1]} and over"]
        )
        bands = pd.cut(raw["AGE"], bins=[-np.inf, *edges, np.inf], right=False, labels=labels)
        return pd.DataFrame(
            {
                "merchant_id": raw["merchant_id"],
                "SEX": raw["SEX"],
                "EDUCATION": raw["EDUCATION"],
                "MARRIAGE": raw["MARRIAGE"],
                "age_band": bands.astype(str),
            }
        )

    def source_records(self) -> pd.DataFrame:
        """The statement columns a feature may read, and nothing else."""
        raw = self._read()
        return raw[["loan_id", "merchant_id", *WHITELIST]].copy()
