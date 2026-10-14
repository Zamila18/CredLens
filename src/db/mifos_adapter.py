"""Export clients and loans in a Mifos X-style shape.

Purpose: show that the data model lines up with Mifos X (Apache Fineract) by writing
    the synthetic merchants and loans as client, loan, repayment-schedule and
    transaction files.
Owner role: B (data engineer).
Implements: PROJECT_BRIEF sections 13 and 18 (the export is the Mifos X deliverable).

What this is, stated plainly:
- A file export. Loading it into a running Mifos X is done by src/db/mifos_load.py.
- Checked on Oct 14, 2026 against a running Mifos X back end: Apache Fineract, Docker
  image `apache/fineract:724b0d742c`, started from tools/mifos/docker-compose.yml. The
  client fields (externalId, officeId, legalFormId, fullname, active, activationDate,
  dateFormat, locale) and the loan fields (productId, principal, loanTermFrequency,
  loanTermFrequencyType, numberOfRepayments, repaymentEvery, repaymentFrequencyType,
  interestRatePerPeriod, interestType, interestCalculationPeriodType, amortizationType,
  transactionProcessingStrategyCode, loanType, submittedOnDate, expectedDisbursementDate)
  were accepted as written here. That server rejected the first version of this export:
  clients lacked `legalFormId`, and loans lacked the five interest and amortisation
  fields. Both are added now. Other Mifos X versions may want more.
- `clientExternalId` and `loanExternalId` are not Fineract fields: they link the files,
  and the loader turns them into Fineract's own ids. The schedule file is our own plain
  layout; Fineract builds its own schedule from the loan terms.
- A merchant is a business, so it is sent as an entity (legal form 2) with one full
  name, not as a person with a first and last name.
- Values a real Mifos X would set itself (office, loan product) are the constants below.
  The office (1, "Head Office") exists in a fresh Fineract; the loader creates the loan
  product and uses its real id.
- Only synthetic data is exported. Merchants have no names; the name field carries the
  word "Merchant" and the merchant id.

Run it: python -m src.db.mifos_adapter
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select

from src.config import PROJECT_ROOT, get_database_url, load_config
from src.db.models import Base, make_engine

EXPORT_DIR = PROJECT_ROOT / "data" / "exports" / "mifos"
DATE_FORMAT = "yyyy-MM-dd"
LOCALE = "en"
# A real Mifos X defines its own offices and loan products. Office 1 ("Head Office")
# exists in a fresh Fineract; src/db/mifos_load.py creates the product and uses its id.
PLACEHOLDER_OFFICE_ID = 1
PLACEHOLDER_PRODUCT_ID = 1
# Fineract's codes, as accepted by the server on Oct 14, 2026.
FREQUENCY_TYPE_DAYS = 0  # loanTermFrequencyType / repaymentFrequencyType: 0 = days
LEGAL_FORM_ENTITY = 2  # 1 = person, 2 = entity (a business)
LOAN_CURRENCY = "BDT"
# Synthetic loans carry no interest: the generator models repayment, not pricing.
INTEREST_FREE = {
    "interestRatePerPeriod": 0,
    "interestType": 1,  # flat
    "interestCalculationPeriodType": 1,  # same as the repayment period
    "amortizationType": 1,  # equal instalments
    "transactionProcessingStrategyCode": "mifos-standard-strategy",
}


def _read(connection, name: str) -> pd.DataFrame:
    """Read one whole table from the database."""
    return pd.read_sql(select(Base.metadata.tables[name]), connection)


def _iso(values: pd.Series) -> pd.Series:
    """Dates as YYYY-MM-DD text, with None where there is no date."""
    as_dates = pd.to_datetime(values)
    return as_dates.dt.strftime("%Y-%m-%d").where(as_dates.notna(), None)


def build_export(database_url: str) -> dict[str, pd.DataFrame]:
    """Build the four Mifos X-style tables from the database."""
    engine = make_engine(database_url)
    try:
        with engine.connect() as connection:
            merchants = _read(connection, "merchants")
            loans = _read(connection, "loans")
            payments = _read(connection, "payments")
    finally:
        engine.dispose()

    clients = pd.DataFrame(
        {
            "externalId": merchants["merchant_id"],
            "officeId": PLACEHOLDER_OFFICE_ID,
            "legalFormId": LEGAL_FORM_ENTITY,
            "fullname": "Merchant " + merchants["merchant_id"],
            "active": True,
            "activationDate": _iso(merchants["onboarded_at"]),
            "dateFormat": DATE_FORMAT,
            "locale": LOCALE,
        }
    )

    schedule = loans.merge(payments, on=["loan_id", "merchant_id"], how="left")
    term_days = (
        pd.to_datetime(schedule["due_date"]) - pd.to_datetime(schedule["issued_at"])
    ).dt.days
    loan_export = pd.DataFrame(
        {
            "externalId": schedule["loan_id"],
            "clientExternalId": schedule["merchant_id"],
            "productId": PLACEHOLDER_PRODUCT_ID,
            "principal": schedule["amount_due_bdt"],
            "currency": LOAN_CURRENCY,
            "loanTermFrequency": term_days,
            "loanTermFrequencyType": FREQUENCY_TYPE_DAYS,
            "numberOfRepayments": 1,
            "repaymentEvery": term_days,
            "repaymentFrequencyType": FREQUENCY_TYPE_DAYS,
            **INTEREST_FREE,
            "loanType": "individual",
            "submittedOnDate": _iso(schedule["issued_at"]),
            "expectedDisbursementDate": _iso(schedule["issued_at"]),
            "dateFormat": DATE_FORMAT,
            "locale": LOCALE,
        }
    )

    repayment_schedule = pd.DataFrame(
        {
            "loanExternalId": schedule["loan_id"],
            "installmentNumber": 1,
            "dueDate": _iso(schedule["due_date"]),
            "principalDue": schedule["amount_due_bdt"],
            "currency": LOAN_CURRENCY,
        }
    )

    paid = schedule[schedule["paid_date"].notna()]
    transactions = pd.DataFrame(
        {
            "loanExternalId": paid["loan_id"],
            "transactionType": "REPAYMENT",
            "transactionDate": _iso(paid["paid_date"]),
            "transactionAmount": paid["amount_paid_bdt"],
            "currency": LOAN_CURRENCY,
            "dateFormat": DATE_FORMAT,
            "locale": LOCALE,
        }
    ).reset_index(drop=True)

    return {
        "clients": clients,
        "loans": loan_export,
        "repayment_schedule": repayment_schedule,
        "transactions": transactions,
    }


def export_mifos(database_url: str, out_dir: Path | None = None) -> dict[str, Path]:
    """Write Mifos X-style client and loan files (CSV and JSON) and return their paths."""
    folder = Path(out_dir) if out_dir is not None else EXPORT_DIR
    folder.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}
    for name, frame in build_export(database_url).items():
        csv_path = folder / f"{name}.csv"
        frame.to_csv(csv_path, index=False, lineterminator="\n")
        json_path = folder / f"{name}.json"
        records: list[dict[str, Any]] = json.loads(frame.to_json(orient="records"))
        json_path.write_text(json.dumps(records, indent=1) + "\n", encoding="utf-8")
        paths[f"{name}_csv"] = csv_path
        paths[f"{name}_json"] = json_path

    readme = folder / "README.txt"
    readme.write_text(
        "Mifos X export of SYNTHETIC data from CredLens. Not real merchants.\n"
        "Accepted by Apache Fineract (Docker image apache/fineract:724b0d742c) on Oct 14, 2026.\n"
        "Load it with: python -m src.db.mifos_load. See src/db/mifos_adapter.py.\n",
        encoding="utf-8",
    )
    paths["readme"] = readme
    return paths


def main() -> int:
    """Command line: export from the configured database."""
    paths = export_mifos(get_database_url(load_config()))
    print(f"Mifos X-style export written to {paths['readme'].parent}")
    for name, path in paths.items():
        print(f"  {name:<26}{path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
