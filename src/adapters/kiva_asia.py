"""Adapter for the `kiva_asia` data mode (public real-label check, small businesses).

Purpose: map Kiva's loan snapshot, filtered to Asia and to retail, food and services,
    into the data contract.
Owner role: B (data engineer).
Implements: docs/DATASET_PLAN.md sections 2.1 and 3; PROJECT_BRIEF section 18, item 32.
    Source and terms: docs/DATA_SOURCES.md section 1.3.

The file: Kiva's own JSON snapshot of 2 May 2016, as saved by the Internet Archive
(`kiva_ds_json.zip`, 1.16 GB, about a million loans in 2,123 files of 500; 17 of those
files are empty in the archived copy). It is read straight from the zip, one small file
at a time, so memory stays low; the first read takes about a minute, and the result is
saved in data/raw/kiva/_derived/ for the next run.

Personal data. The snapshot holds borrower names, pictures and life stories. This
adapter never keeps them: of each loan it reads only the terms, sector, country, partner,
dates and status, plus the number of borrowers and their gender for the group audit.

Which loans are used (`data.kiva` in the config):
- countries in Asia and the Pacific; sectors Retail, Food and Services;
- posted between `posted_from` and `posted_until`. The end date matters: of loans posted
  after mid-2013 a growing share was still being repaid when the snapshot was taken.
  Keeping only the finished ones from those years would keep the quick payers and hide
  late defaults. Up to mid-2013 about 1% were still running; they are left out because
  their outcome is not known;
- outcome known: `paid` (label 1) or `defaulted` (label 0).

The field partner's track record, without looking ahead. For each loan the adapter counts
the partner's earlier Asian loans (any sector) whose outcome was known on the day this
loan was posted: a repaid loan from its `paid_date`; a defaulted loan from the end of its
term plus `default_known_lag_months`, because the snapshot does not say when a default
was declared and Kiva declared one only months after a loan fell due.

What goes where:
- merchants, loans, consents: one row per loan. `outcome_label` = 1 when it was repaid.
  `issued_at` is the posting date. `limit_bdt` holds the loan amount in US dollars (the
  contract's column names say "bdt"; the amounts are not converted). The sector goes to
  `shop_type`, which is audit-only everywhere.
- purchases, deliveries, payments, questionnaire: Kiva has no history of the borrower.
  Empty; nothing is generated.
- consents: one row per loan marked "public_dataset"; not a real consent.
- audit_frame: borrower gender and country. Audit only, never model inputs.
- source_records: the whitelisted columns the feature builder may read
  (src/features/kiva_asia.py).

The raw file is downloaded by a human into data/raw/kiva/ and is never committed.
"""

from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.adapters.base import DataAdapter, empty_frame
from src.config import PROJECT_ROOT
from src.features.kiva_asia import WHITELIST

RAW_FOLDER = PROJECT_ROOT / "data" / "raw" / "kiva"
ARCHIVE_NAME = "kiva_ds_json.zip"
DERIVED_FOLDER = "_derived"  # inside the raw folder, so it is gitignored with it
CONSENT_PURPOSE = "public_dataset"
PAID, DEFAULTED = "paid", "defaulted"
# Countries of Asia and the Pacific that appear in the snapshot (docs/DATA_SOURCES.md).
# The loans carry a country, not a region, so the region is this list.
REGION_COUNTRIES = {
    "Asia": (
        "Afghanistan", "Bangladesh", "Cambodia", "China", "India", "Indonesia", "Kyrgyzstan",
        "Lao PDR", "Mongolia", "Myanmar (Burma)", "Nepal", "Pakistan", "Papua New Guinea",
        "Philippines", "Samoa", "Solomon Islands", "Sri Lanka", "Tajikistan", "Thailand",
        "Timor-Leste", "Vietnam",
    )
}  # fmt: skip
# The fields kept from each loan. No name, picture, story or description is among them.
EXTRACT_COLUMNS = [
    "id",
    "status",
    "posted_date",
    "paid_date",
    "disbursal_date",
    "sector",
    "activity",
    "country",
    "partner_id",
    "loan_amount",
    "repayment_term",
    "partner_covers_nonpayment",
    "borrowers",
    "female_borrowers",
]


def _day(value: Any) -> str:
    """The date part of a time stamp such as 2012-06-30T15:00:11Z; empty when missing."""
    return (value or "")[:10]


def extract_loans(archive_path: Path, countries: set[str], target: Path) -> None:
    """Write the kept fields of every loan in the given countries to a CSV file.

    Reads the zip one inner file at a time. A file that is empty or broken in the archive
    is skipped (17 are, in the archived copy).
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive, target.open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(EXTRACT_COLUMNS)
        names = [n for n in archive.namelist() if n.startswith("loans/") and n.endswith(".json")]
        for name in sorted(names):
            try:
                loans = json.loads(archive.read(name))["loans"]
            except (json.JSONDecodeError, KeyError):
                continue
            for loan in loans:
                country = (loan.get("location") or {}).get("country")
                if country not in countries:
                    continue
                terms = loan.get("terms") or {}
                people = loan.get("borrowers") or []
                liability = (terms.get("loss_liability") or {}).get("nonpayment")
                writer.writerow(
                    [
                        loan.get("id"),
                        loan.get("status"),
                        _day(loan.get("posted_date")),
                        _day(loan.get("paid_date")),
                        _day(terms.get("disbursal_date")),
                        loan.get("sector"),
                        loan.get("activity"),
                        country,
                        loan.get("partner_id"),
                        loan.get("loan_amount"),
                        terms.get("repayment_term"),
                        int(liability == "partner"),
                        len(people),
                        sum(1 for person in people if person.get("gender") == "F"),
                    ]
                )


def partner_track_record(loans: pd.DataFrame, lag_months: int) -> pd.DataFrame:
    """For every loan: how many of its partner's loans had a known outcome before it was posted.

    Args:
        loans: all the region's loans (any sector, any status) with `partner_id`,
            `status`, `posted_date`, `paid_date`, `disbursal_date`, `repayment_term`.
        lag_months: months after the end of the term at which a default counts as known.

    Returns the columns `partner_known_loans` and `partner_known_defaults`, in the order
    of `loans`. Only outcomes known strictly before the posting day are counted.
    """
    posted = pd.to_datetime(loans["posted_date"])
    paid_on = pd.to_datetime(loans["paid_date"], errors="coerce")
    term = pd.to_numeric(loans["repayment_term"], errors="coerce").fillna(0)
    disbursed = pd.to_datetime(loans["disbursal_date"], errors="coerce").fillna(posted)
    # 30.44 days is the average month; exact month arithmetic row by row would be slow.
    default_known = disbursed + pd.to_timedelta((term + lag_months) * 30.44, unit="D")
    is_default = loans["status"] == DEFAULTED
    known_on = paid_on.where(loans["status"] == PAID, default_known.where(is_default))

    result = pd.DataFrame(
        {"partner_known_loans": 0, "partner_known_defaults": 0}, index=loans.index, dtype=float
    )
    for _, rows in loans.groupby("partner_id").groups.items():
        events = pd.DataFrame(
            {"known_on": known_on.loc[rows], "bad": is_default.loc[rows].astype(int)}
        ).dropna(subset=["known_on"]).sort_values("known_on")
        when = events["known_on"].to_numpy()
        defaults_so_far = np.concatenate([[0], events["bad"].cumsum().to_numpy()])
        before = np.searchsorted(when, posted.loc[rows].to_numpy(), side="left")
        result.loc[rows, "partner_known_loans"] = before
        result.loc[rows, "partner_known_defaults"] = defaults_so_far[before]
    return result


class KivaAsiaAdapter(DataAdapter):
    """Reads the Kiva snapshot and returns Asian small-business loans.

    Args:
        config: the validated config.
        folder: where `kiva_ds_json.zip` is; defaults to data/raw/kiva/. Tests pass a
            folder with a tiny hand-made zip of the same shape.
        use_cache: keep the extracted loan fields on disk between runs. Tests switch it off.
    """

    mode = "kiva_asia"

    def __init__(
        self, config: dict[str, Any], folder: Path | str | None = None, use_cache: bool = True
    ) -> None:
        super().__init__(config)
        self.folder = Path(folder) if folder is not None else RAW_FOLDER
        self.use_cache = use_cache
        self._raw: pd.DataFrame | None = None

    def _countries(self) -> set[str]:
        regions = self.config["data"]["kiva"]["regions"]
        unknown = [region for region in regions if region not in REGION_COUNTRIES]
        if unknown:
            raise ValueError(f"No country list for Kiva region(s) {unknown}.")
        return {country for region in regions for country in REGION_COUNTRIES[region]}

    def _extracted(self) -> pd.DataFrame:
        """Every loan of the region with the kept fields, from the zip or from the saved copy."""
        archive = self.folder / ARCHIVE_NAME
        if not archive.exists():
            raise FileNotFoundError(
                f"No {ARCHIVE_NAME} in {self.folder}. Download Kiva's archived JSON snapshot "
                "(docs/DATA_SOURCES.md, section 1.3) and save the zip there, unopened."
            )
        # The regions are part of the name, so a changed region list is never answered
        # from a file extracted for another one.
        regions = "-".join(sorted(self.config["data"]["kiva"]["regions"]))
        name = f"region_loans_{regions}_{archive.stat().st_size}.csv"
        target = self.folder / DERIVED_FOLDER / name
        if not (self.use_cache and target.exists()):
            extract_loans(archive, self._countries(), target)
        frame = pd.read_csv(target)
        if not self.use_cache:
            target.unlink()
        missing = [column for column in EXTRACT_COLUMNS if column not in frame.columns]
        if missing:
            raise ValueError(f"The extracted Kiva loans lack columns: {missing}.")
        # The snapshot repeats some loans (about 27,000 Asian ones appear two or three
        # times, as identical copies). Each loan is kept once. Counting them twice would
        # also inflate the partners' track records.
        frame = frame.drop_duplicates().reset_index(drop=True)
        if frame["id"].duplicated().any():
            raise ValueError("The Kiva snapshot has loans whose repeated copies differ.")
        return frame

    def _read(self) -> pd.DataFrame:
        """The loans this mode uses, with the partner's track record and our ids."""
        if self._raw is not None:
            return self._raw
        settings = self.config["data"]["kiva"]
        everything = self._extracted()
        record = partner_track_record(everything, settings["default_known_lag_months"])
        everything = pd.concat([everything, record], axis=1)

        posted = pd.to_datetime(everything["posted_date"])
        keep = (
            everything["sector"].isin(settings["sectors"])
            & everything["status"].isin([PAID, DEFAULTED])
            & (posted >= pd.Timestamp(settings["posted_from"]))
            & (posted <= pd.Timestamp(settings["posted_until"]))
        )
        frame = everything[keep].sort_values("id").reset_index(drop=True)
        number = frame["id"].astype(int).astype(str)
        frame["merchant_id"] = "KV" + number
        frame["loan_id"] = "KVL" + number
        self._raw = frame
        return frame

    def load_merchants(self) -> pd.DataFrame:
        raw = self._read()
        merchants = empty_frame("merchants").reindex(range(len(raw)))
        merchants["merchant_id"] = raw["merchant_id"]
        merchants["onboarded_at"] = raw["posted_date"]  # first seen when the loan was posted
        merchants["shop_type"] = raw["sector"]  # audit only, as everywhere
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
        """Kiva knows nothing of how the borrower paid before: empty by design."""
        return empty_frame("payments")

    def load_loans(self) -> pd.DataFrame:
        raw = self._read()
        return pd.DataFrame(
            {
                "loan_id": raw["loan_id"],
                "merchant_id": raw["merchant_id"],
                "issued_at": raw["posted_date"],
                "limit_bdt": raw["loan_amount"].astype(float),
                "outcome_label": (raw["status"] == PAID).astype(int),  # 1 = repaid
                "label_observed_at": raw["paid_date"].where(raw["status"] == PAID),
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
                "consent_id": "KVC" + raw["merchant_id"].str[2:],
                "merchant_id": raw["merchant_id"],
                "purpose": CONSENT_PURPOSE,
                "data_categories": "loan_terms",
                "granted_at": raw["posted_date"].min() if len(raw) else None,
                "expires_at": "2099-12-31",
                "revoked_at": None,
            }
        )

    def audit_frame(self) -> pd.DataFrame:
        """Borrower gender and country: for the group audit only."""
        raw = self._read()
        women, people = raw["female_borrowers"], raw["borrowers"]
        gender = np.select(
            [people == 0, women == people, women == 0], ["not stated", "female", "male"], "mixed"
        )
        return pd.DataFrame(
            {
                "merchant_id": raw["merchant_id"],
                "borrower_genders": gender,
                "country": raw["country"],
            }
        )

    def source_records(self) -> pd.DataFrame:
        """The columns a feature may read, and nothing else."""
        raw = self._read()
        return raw[["loan_id", "merchant_id", *WHITELIST]].copy()
