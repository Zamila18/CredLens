"""Adapter for the `india_ltfs` data mode (public real-label check, Indian borrowers).

Purpose: map the L&T vehicle loan file (Kaggle, `train.csv`) into the data contract.
Owner role: B (data engineer).
Implements: docs/DATASET_PLAN.md section 3; PROJECT_BRIEF section 18, item 30. Source and
    terms: docs/DATA_SOURCES.md section 1.2.

What the file is (checked Oct 12 and 13, 2026): 233,154 vehicle loans disbursed in India
between August and October 2018, with a credit-bureau summary as of the day of
disbursement. The outcome is "payment default in the first EMI on due date": missing the
first monthly instalment, not the loan eventually going bad. About half the borrowers
have no bureau record, which makes this a real thin-file population.

What goes where:
- merchants: one row per loan (the file has one loan per customer id). No district, town,
  shop type or licence in the source: those stay empty.
- loans: the loan, with the disbursal date as `issued_at`. `outcome_label` = 1 when the
  first instalment was NOT missed. `limit_bdt` holds the amount disbursed in Indian
  rupees (the contract's column names say "bdt"; the amounts are not converted).
  `label_observed_at` is one month after disbursal, a nominal date: the file does not
  give the due date of the first instalment.
- purchases, deliveries, payments, questionnaire: the source has none. Empty; nothing is
  generated.
- consents: public data has no consent records. Each loan gets one row marked
  "public_dataset" so the same consent check runs; it is not a real consent.
- audit_frame: age band, state and employment type. Audit only, never model inputs.
- source_records: the whitelisted loan and bureau columns the feature builder may read
  (src/features/india_ltfs.py). The outcome, the audit columns and the branch, dealer,
  manufacturer, pin code and employee identifiers are not in it.

The dataset states no usage terms. The raw file is downloaded by a human into
data/raw/india_ltfs/ and is never committed or redistributed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.adapters.base import DataAdapter, empty_frame
from src.config import PROJECT_ROOT
from src.features.india_ltfs import (
    AUDIT_SOURCE_COLUMNS,
    DATE_COLUMN,
    ORGANISATION_COLUMNS,
    OUTCOME_COLUMN,
    WHITELIST,
)

RAW_FOLDER = PROJECT_ROOT / "data" / "raw" / "india_ltfs"
FILE_NAME = "train.csv"
SOURCE_DATE_FORMAT = "%d-%m-%y"  # the file writes 03-08-18 for 3 August 2018
CONSENT_PURPOSE = "public_dataset"
EXPECTED_COLUMNS = [
    "UniqueID",
    *WHITELIST,
    *AUDIT_SOURCE_COLUMNS,
    *ORGANISATION_COLUMNS,
    OUTCOME_COLUMN,
]


class IndiaLtfsAdapter(DataAdapter):
    """Reads the L&T vehicle loan file.

    Args:
        config: the validated config.
        folder: where `train.csv` is; defaults to data/raw/india_ltfs/. Tests pass a
            folder with a tiny hand-made file that has the same columns.
    """

    mode = "india_ltfs"

    def __init__(self, config: dict[str, Any], folder: Path | str | None = None) -> None:
        super().__init__(config)
        self.folder = Path(folder) if folder is not None else RAW_FOLDER
        self._raw: pd.DataFrame | None = None

    def _read(self) -> pd.DataFrame:
        """Read the file once, check its columns, parse its dates and add our ids."""
        if self._raw is not None:
            return self._raw
        path = self.folder / FILE_NAME
        if not path.exists():
            raise FileNotFoundError(
                f"No {FILE_NAME} in {self.folder}. Download the L&T vehicle loan data from "
                "Kaggle (docs/DATA_SOURCES.md, section 1.2) and save train.csv there."
            )
        frame = pd.read_csv(path)
        missing = [column for column in EXPECTED_COLUMNS if column not in frame.columns]
        if missing:
            raise ValueError(f"{path.name} is not the expected file. Missing columns: {missing}.")
        frame = frame[EXPECTED_COLUMNS].copy()
        if frame["UniqueID"].duplicated().any():
            raise ValueError(f"{path.name} has repeated loan ids.")

        sample_size = self.config["data"][self.mode]["sample_size"]
        if sample_size is not None and sample_size < len(frame):
            frame = frame.sample(n=sample_size, random_state=self.config["seed"])
        frame = frame.sort_values("UniqueID").reset_index(drop=True)

        disbursed = pd.to_datetime(frame[DATE_COLUMN], format=SOURCE_DATE_FORMAT)
        born = pd.to_datetime(frame["Date.of.Birth"], format=SOURCE_DATE_FORMAT)
        # Two-digit years: "01-01-64" is read as 2064. Nobody is born after their loan.
        born = born.where(born <= disbursed, born - pd.DateOffset(years=100))
        frame[DATE_COLUMN] = disbursed.dt.strftime("%Y-%m-%d")
        frame["age_years"] = (disbursed - born).dt.days / 365.25

        number = frame["UniqueID"].astype(int).astype(str)
        frame["merchant_id"] = "IN" + number
        frame["loan_id"] = "INL" + number
        self._raw = frame
        return frame

    def load_merchants(self) -> pd.DataFrame:
        raw = self._read()
        merchants = empty_frame("merchants").reindex(range(len(raw)))
        merchants["merchant_id"] = raw["merchant_id"]
        merchants["onboarded_at"] = raw[DATE_COLUMN]  # first seen on the day of the loan
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
        """The source has no payment records, only the outcome: empty by design."""
        return empty_frame("payments")

    def load_loans(self) -> pd.DataFrame:
        raw = self._read()
        first_instalment = pd.to_datetime(raw[DATE_COLUMN]) + pd.DateOffset(months=1)
        return pd.DataFrame(
            {
                "loan_id": raw["loan_id"],
                "merchant_id": raw["merchant_id"],
                "issued_at": raw[DATE_COLUMN],
                "limit_bdt": raw["disbursed_amount"].astype(float),
                "outcome_label": 1 - raw[OUTCOME_COLUMN].astype(int),  # 1 = first EMI paid
                "label_observed_at": first_instalment.dt.strftime("%Y-%m-%d"),
            }
        )

    def load_questionnaire(self) -> pd.DataFrame:
        """The source has no questionnaire: empty by design."""
        return empty_frame("questionnaire")

    def load_consents(self) -> pd.DataFrame:
        """One row per loan, marked as a public data set. Not a real consent record."""
        raw = self._read()
        return pd.DataFrame(
            {
                "consent_id": "INC" + raw["merchant_id"].str[2:],
                "merchant_id": raw["merchant_id"],
                "purpose": CONSENT_PURPOSE,
                "data_categories": "loan_application,bureau_summary",
                "granted_at": raw[DATE_COLUMN].min(),
                "expires_at": "2099-12-31",
                "revoked_at": None,
            }
        )

    def audit_frame(self) -> pd.DataFrame:
        """Age band, state and employment type: for the group audit only."""
        raw = self._read()
        edges = self.config["data"][self.mode]["age_band_edges"]
        labels = (
            [f"under {edges[0]}"]
            + [f"{low} to {high - 1}" for low, high in zip(edges, edges[1:])]
            + [f"{edges[-1]} and over"]
        )
        bands = pd.cut(raw["age_years"], bins=[-np.inf, *edges, np.inf], right=False, labels=labels)
        return pd.DataFrame(
            {
                "merchant_id": raw["merchant_id"],
                "age_band": bands.astype(str),
                "State_ID": raw["State_ID"],
                "Employment.Type": raw["Employment.Type"].fillna("not stated"),
            }
        )

    def source_records(self) -> pd.DataFrame:
        """The loan and bureau columns a feature may read, and nothing else."""
        raw = self._read()
        return raw[["loan_id", "merchant_id", *WHITELIST]].copy()
