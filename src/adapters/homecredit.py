"""Adapter for the `homecredit` data mode (public real-label check at larger scale).

Purpose: map the Kaggle "Home Credit Default Risk" files into the data contract.
Owner role: B (data engineer).
Implements: docs/DATASET_PLAN.md section 3; PROJECT_BRIEF section 18, item 31. Source and
    competition rules: docs/DATA_SOURCES.md section 1.4.

The publisher does not state the country of this data. It is labelled "country not
stated" everywhere and never supports a claim about Asia.

Three files are read (of the competition's nine):
- application_train.csv: 307,511 applications with the outcome;
- installments_payments.csv: 13.6 million instalment payments on the applicants' EARLIER
  loans;
- POS_CASH_balance.csv: 10 million monthly records of earlier store and cash loans.

Reading them on a laptop. The two history files are 1.1 GB together. They are read in
chunks, only the columns needed and only the rows of the sampled applicants
(`data.homecredit.sample_size`) are kept, and the per-applicant result is saved in
data/raw/homecredit/_derived/ so the next run takes a second. Nothing needs a GPU.

What goes where:
- merchants, loans, consents: one row per sampled application. `outcome_label` = 1 when
  the applicant had NO payment difficulties. Amounts are in the file's own currency,
  which is not stated either.
- Dates: the source gives only days counted back from each application. `issued_at` is
  therefore one nominal date for every application (REFERENCE_DATE). There is no real
  calendar time in this data, which is why its split is random and marked weaker.
- purchases, deliveries, questionnaire: the source has none. Empty; nothing is generated.
- payments: left empty on purpose. The earlier instalments are used for the features
  (through `source_records`), but two million rows of them are not copied into the
  contract table: under the competition rules rows of this source are never shown on a
  screen, so the table would serve nothing.
- audit_frame: gender, age band and region rating. Audit only, never model inputs.
- source_records: per application, the whitelisted application columns and the counts
  worked out from the two history files (src/features/homecredit.py). The outcome and
  the audit columns are not in it.

The raw files are downloaded by a human into data/raw/homecredit/ after accepting the
competition rules, stay on that laptop, and are never committed or redistributed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.adapters.base import DataAdapter, empty_frame
from src.config import PROJECT_ROOT
from src.features.homecredit import (
    APPLICATION_COLUMNS,
    AUDIT_SOURCE_COLUMNS,
    HISTORY_COLUMNS,
    OUTCOME_COLUMN,
    WHITELIST,
)

RAW_FOLDER = PROJECT_ROOT / "data" / "raw" / "homecredit"
APPLICATION_FILE = "application_train.csv"
INSTALMENT_FILE = "installments_payments.csv"
POS_FILE = "POS_CASH_balance.csv"
DERIVED_FOLDER = "_derived"  # inside the raw folder, so it is gitignored with it
REFERENCE_DATE = "2018-01-01"  # nominal: the source has no calendar dates
CONSENT_PURPOSE = "public_dataset"
ID = "SK_ID_CURR"
INSTALMENT_COLUMNS = [
    "SK_ID_PREV",
    ID,
    "NUM_INSTALMENT_NUMBER",
    "DAYS_INSTALMENT",
    "DAYS_ENTRY_PAYMENT",
    "AMT_INSTALMENT",
    "AMT_PAYMENT",
]
POS_COLUMNS = [ID, "MONTHS_BALANCE", "SK_DPD"]


class HomeCreditAdapter(DataAdapter):
    """Reads the Home Credit application file and two history files.

    Args:
        config: the validated config.
        folder: where the three files are; defaults to data/raw/homecredit/. Tests pass
            a folder with tiny hand-made files that have the same columns.
        use_cache: keep the per-applicant history counts on disk between runs. Tests
            switch it off.
    """

    mode = "homecredit"

    def __init__(
        self, config: dict[str, Any], folder: Path | str | None = None, use_cache: bool = True
    ) -> None:
        super().__init__(config)
        self.folder = Path(folder) if folder is not None else RAW_FOLDER
        self.use_cache = use_cache
        self._raw: pd.DataFrame | None = None

    # --- reading -----------------------------------------------------------------------

    def _path(self, name: str) -> Path:
        path = self.folder / name
        if not path.exists():
            raise FileNotFoundError(
                f"No {name} in {self.folder}. Download the Home Credit Default Risk files "
                "from Kaggle after accepting the competition rules (docs/DATA_SOURCES.md, "
                "section 1.4) and save them there."
            )
        return path

    def _applications(self) -> pd.DataFrame:
        """The sampled applications: id, outcome, audit columns and application columns."""
        wanted = [ID, OUTCOME_COLUMN, *AUDIT_SOURCE_COLUMNS, *APPLICATION_COLUMNS]
        path = self._path(APPLICATION_FILE)
        present = list(pd.read_csv(path, nrows=0).columns)
        missing = [column for column in wanted if column not in present]
        if missing:
            raise ValueError(f"{path.name} is not the expected file. Missing columns: {missing}.")
        frame = pd.read_csv(path, usecols=wanted)[wanted]
        if frame[ID].duplicated().any():
            raise ValueError(f"{path.name} has repeated application ids.")
        sample_size = self.config["data"][self.mode]["sample_size"]
        if sample_size is not None and sample_size < len(frame):
            frame = frame.sample(n=sample_size, random_state=self.config["seed"])
        return frame.sort_values(ID).reset_index(drop=True)

    def _chunks(self, name: str, columns: list[str], ids: set[int]):
        """Rows of the sampled applicants, read a chunk at a time to keep memory small."""
        rows = self.config["data"][self.mode]["chunk_rows"]
        for chunk in pd.read_csv(self._path(name), usecols=columns, chunksize=rows):
            yield chunk[chunk[ID].isin(ids)]

    def _history(self, ids: set[int]) -> pd.DataFrame:
        """Per applicant: counts over earlier instalments and monthly loan records.

        The applicants are worked through `applicants_per_pass` at a time, each pass
        reading the two files once. So memory stays bounded even when every applicant is
        used (`sample_size: null`), at the price of a few more passes.
        """
        ordered = sorted(ids)
        size = self.config["data"][self.mode]["applicants_per_pass"]
        passes = [set(ordered[start : start + size]) for start in range(0, len(ordered), size)]
        return pd.concat([self._history_pass(batch) for batch in passes], ignore_index=True)

    def _history_pass(self, ids: set[int]) -> pd.DataFrame:
        """The history counts of one batch of applicants."""
        settings = self.config["data"][self.mode]
        tolerance = self.config["labels"]["paid_in_full_tolerance"]

        rows = pd.concat(self._chunks(INSTALMENT_FILE, INSTALMENT_COLUMNS, ids), ignore_index=True)
        if (rows["DAYS_INSTALMENT"] >= 0).any() or (rows["DAYS_ENTRY_PAYMENT"] >= 0).any():
            raise ValueError(
                f"{INSTALMENT_FILE} holds rows dated on or after the application. They would "
                "leak the future into the features, so nothing was built."
            )
        # One instalment can be paid in several parts: put the parts together first.
        each = rows.groupby([ID, "SK_ID_PREV", "NUM_INSTALMENT_NUMBER"], sort=False).agg(
            due_day=("DAYS_INSTALMENT", "max"),
            paid_day=("DAYS_ENTRY_PAYMENT", "max"),
            amount_due=("AMT_INSTALMENT", "max"),
            amount_paid=("AMT_PAYMENT", "sum"),
        )
        # Not paid by the day of the application: late by the days gone by since it was due.
        days_late = (each["paid_day"].fillna(0.0) - each["due_day"]).clip(lower=0)
        each["ontime"] = days_late == 0
        each["late"] = days_late > settings["late_days"]
        each["short"] = each["amount_paid"] < (1 - tolerance) * each["amount_due"]
        each["days_late"] = days_late
        each["recent"] = each["due_day"] >= -settings["recent_days"]
        each["recent_ontime"] = each["recent"] & each["ontime"]
        instalments = each.groupby(level=0).agg(
            inst_count=("ontime", "size"),
            inst_ontime_count=("ontime", "sum"),
            inst_late_count=("late", "sum"),
            inst_short_count=("short", "sum"),
            inst_days_late_sum=("days_late", "sum"),
            inst_recent_count=("recent", "sum"),
            inst_recent_ontime_count=("recent_ontime", "sum"),
        )

        months = pd.concat(self._chunks(POS_FILE, POS_COLUMNS, ids), ignore_index=True)
        if (months["MONTHS_BALANCE"] >= 0).any():
            raise ValueError(
                f"{POS_FILE} holds months on or after the application. They would leak the "
                "future into the features, so nothing was built."
            )
        months["overdue"] = months["SK_DPD"] > 0
        pos = months.groupby(ID).agg(
            pos_months=("overdue", "size"), pos_months_overdue=("overdue", "sum")
        )

        history = instalments.join(pos, how="outer").reindex(sorted(ids))
        history.index.name = ID
        return history[HISTORY_COLUMNS].astype(float).reset_index()

    def _cached_history(self, ids: set[int]) -> pd.DataFrame:
        """The history counts, from disk when the same sample was worked out before."""
        if not self.use_cache:
            return self._history(ids)
        settings = self.config["data"][self.mode]
        files = (INSTALMENT_FILE, POS_FILE)
        sizes = "-".join(str(self._path(name).stat().st_size) for name in files)
        tolerance = self.config["labels"]["paid_in_full_tolerance"]
        key = (
            f"history_n{len(ids)}_seed{self.config['seed']}_late{settings['late_days']}"
            f"_recent{settings['recent_days']}_tol{tolerance}_{sizes}.csv"
        )
        path = self.folder / DERIVED_FOLDER / key
        if path.exists():
            cached = pd.read_csv(path)
            if set(cached[ID]) == ids:
                return cached
        history = self._history(ids)
        path.parent.mkdir(parents=True, exist_ok=True)
        history.to_csv(path, index=False)
        return history

    def _read(self) -> pd.DataFrame:
        """Applications with their history counts and our ids, read once."""
        if self._raw is not None:
            return self._raw
        frame = self._applications()
        history = self._cached_history(set(frame[ID].astype(int)))
        frame = frame.merge(history, on=ID, how="left", validate="one_to_one")
        number = frame[ID].astype(int).astype(str)
        frame["merchant_id"] = "HC" + number
        frame["loan_id"] = "HCL" + number
        self._raw = frame
        return frame

    # --- the contract ------------------------------------------------------------------

    def load_merchants(self) -> pd.DataFrame:
        raw = self._read()
        merchants = empty_frame("merchants").reindex(range(len(raw)))
        merchants["merchant_id"] = raw["merchant_id"]
        merchants["onboarded_at"] = REFERENCE_DATE  # nominal; see the module text
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
        """Empty on purpose: earlier instalments feed the features, not this table."""
        return empty_frame("payments")

    def load_loans(self) -> pd.DataFrame:
        raw = self._read()
        return pd.DataFrame(
            {
                "loan_id": raw["loan_id"],
                "merchant_id": raw["merchant_id"],
                "issued_at": REFERENCE_DATE,
                "limit_bdt": raw["AMT_CREDIT"].astype(float),
                "outcome_label": 1 - raw[OUTCOME_COLUMN].astype(int),  # 1 = no difficulties
                "label_observed_at": REFERENCE_DATE,
            }
        )

    def load_questionnaire(self) -> pd.DataFrame:
        """The source has no questionnaire: empty by design."""
        return empty_frame("questionnaire")

    def load_consents(self) -> pd.DataFrame:
        """One row per application, marked as a public data set. Not a real consent record."""
        raw = self._read()
        return pd.DataFrame(
            {
                "consent_id": "HCC" + raw["merchant_id"].str[2:],
                "merchant_id": raw["merchant_id"],
                "purpose": CONSENT_PURPOSE,
                "data_categories": "loan_application,instalment_history",
                "granted_at": REFERENCE_DATE,
                "expires_at": "2099-12-31",
                "revoked_at": None,
            }
        )

    def audit_frame(self) -> pd.DataFrame:
        """Gender, age band and region rating: for the group audit only."""
        raw = self._read()
        edges = self.config["data"][self.mode]["age_band_edges"]
        labels = (
            [f"under {edges[0]}"]
            + [f"{low} to {high - 1}" for low, high in zip(edges, edges[1:])]
            + [f"{edges[-1]} and over"]
        )
        age_years = -raw["DAYS_BIRTH"] / 365.25  # the file counts days back from the application
        bands = pd.cut(age_years, bins=[-np.inf, *edges, np.inf], right=False, labels=labels)
        return pd.DataFrame(
            {
                "merchant_id": raw["merchant_id"],
                "CODE_GENDER": raw["CODE_GENDER"],
                "age_band": bands.astype(str),
                "REGION_RATING_CLIENT": raw["REGION_RATING_CLIENT"],
            }
        )

    def source_records(self) -> pd.DataFrame:
        """The application columns and history counts a feature may read, and nothing else."""
        raw = self._read()
        records = raw[["loan_id", "merchant_id", *WHITELIST]].copy()
        records.insert(2, "cutoff_date", REFERENCE_DATE)
        return records
