"""Load a sample of the CredLens export into a running Mifos X, and check it arrived.

Purpose: show, not just claim, that the data model lines up with Mifos X: merchants
    become Mifos X clients, loans become Mifos X loans, and repayments become Mifos X
    repayment transactions, after which Mifos X itself works out each loan's status.
Owner role: B (data engineer).
Implements: PROJECT_BRIEF sections 13 and 18 (Mifos X), item 35.

What it needs: a Mifos X back end (Apache Fineract) on this laptop, started with
    docker compose -f tools/mifos/docker-compose.yml --env-file tools/mifos/.env up -d
and the export files, written by `python -m src.db.mifos_adapter`.

What it does, for a sample of merchants (`--merchants`, default 50), in order:
1. lets the server hold amounts in Bangladeshi taka (BDT);
2. creates one interest-free loan product, "CredLens merchant credit", if it is missing;
3. creates each merchant as a client (a business), keeping our id as `externalId`;
4. for each of their loans: submits it, approves and disburses it on its issue date, and
   posts every repayment the export holds;
5. reads every loan back and compares Mifos X's own status with what CredLens expects
   (paid in full, or still running), and writes a report.

It only ever talks to the address given (`--url`, default https://localhost:8443, this
laptop). The server's certificate is self-signed, so certificate checks are off for that
address only. The login is Fineract's public demo login ("mifos" / "password"); use it
only on a local test server.

Only synthetic data is sent. Public data sources are never loaded into Mifos X.

Run it: python -m src.db.mifos_load --merchants 50
"""

from __future__ import annotations

import argparse
import base64
import json
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from src.db.mifos_adapter import EXPORT_DIR, LOAN_CURRENCY

DEFAULT_URL = "https://localhost:8443"
API_PATH = "/fineract-provider/api/v1"
TENANT = "default"
DEMO_LOGIN = ("mifos", "password")  # Fineract's published demo login, local servers only
PRODUCT = {
    "name": "CredLens merchant credit",
    "shortName": "CLMC",
    "currencyCode": LOAN_CURRENCY,
    "digitsAfterDecimal": 2,
    "inMultiplesOf": 0,
    "principal": 20000,
    "numberOfRepayments": 1,
    "repaymentEvery": 30,
    "repaymentFrequencyType": 0,
    "interestRatePerPeriod": 0,
    "interestRateFrequencyType": 2,
    "amortizationType": 1,
    "interestType": 1,
    "interestCalculationPeriodType": 1,
    "transactionProcessingStrategyCode": "mifos-standard-strategy",
    "accountingRule": 1,
    "daysInMonthType": 1,
    "daysInYearType": 1,
    "isInterestRecalculationEnabled": False,
    "locale": "en",
}
DATE_FIELDS = {"dateFormat": "yyyy-MM-dd", "locale": "en"}
REPORT_FILE = "load_report.json"


class MifosError(RuntimeError):
    """The server refused a request; the message carries its own explanation."""


class Fineract:
    """A small client for the parts of the Fineract REST API this loader uses."""

    def __init__(self, base_url: str = DEFAULT_URL, timeout: int = 60) -> None:
        self.base = base_url.rstrip("/") + API_PATH
        token = base64.b64encode(":".join(DEMO_LOGIN).encode()).decode()
        self.headers = {
            "Authorization": f"Basic {token}",
            "Fineract-Platform-TenantId": TENANT,
            "Content-Type": "application/json",
        }
        self.timeout = timeout
        # The local server's certificate is self-signed. Checks are off for it only.
        self.context = ssl._create_unverified_context()

    def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        """Send one request; return the parsed answer or raise MifosError."""
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            self.base + path, data=data, method=method, headers=self.headers
        )
        try:
            opened = urllib.request.urlopen(request, context=self.context, timeout=self.timeout)
            with opened as answer:
                return json.loads(answer.read() or b"{}")
        except urllib.error.HTTPError as error:
            raise MifosError(f"{method} {path}: {_explain(error.read())}") from None
        except urllib.error.URLError as error:
            raise MifosError(
                f"No Mifos X server answered at {self.base} ({error.reason}). Start it with: "
                "docker compose -f tools/mifos/docker-compose.yml --env-file tools/mifos/.env up -d"
            ) from None


def _explain(raw: bytes) -> str:
    """Fineract's own words for why it refused a request."""
    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        return raw[:200].decode(errors="replace")
    found = payload.get("errors") or []
    if found:
        return "; ".join(
            f"{item.get('parameterName')}: {item.get('defaultUserMessage')}" for item in found
        )
    return str(payload.get("defaultUserMessage") or payload)


def read_export(folder: Path = EXPORT_DIR) -> dict[str, list[dict[str, Any]]]:
    """The export files written by src/db/mifos_adapter.py."""
    files = {name: folder / f"{name}.json" for name in ("clients", "loans", "transactions")}
    missing = [str(path) for path in files.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            f"Export files not found: {missing}. Write them with: python -m src.db.mifos_adapter"
        )
    return {name: json.loads(path.read_text(encoding="utf-8")) for name, path in files.items()}


def pick_sample(export: dict[str, list[dict[str, Any]]], merchants: int) -> dict[str, Any]:
    """The first `merchants` merchants that have at least one loan, with all their loans."""
    loans_by_client: dict[str, list[dict[str, Any]]] = {}
    for loan in export["loans"]:
        loans_by_client.setdefault(loan["clientExternalId"], []).append(loan)
    clients = [c for c in export["clients"] if c["externalId"] in loans_by_client][:merchants]
    chosen = {client["externalId"] for client in clients}
    loans = [loan for loan in export["loans"] if loan["clientExternalId"] in chosen]
    loan_ids = {loan["externalId"] for loan in loans}
    repayments = [t for t in export["transactions"] if t["loanExternalId"] in loan_ids]
    return {"clients": clients, "loans": loans, "transactions": repayments}


def expected_status(loan: dict[str, Any], repayments: list[dict[str, Any]]) -> str:
    """What CredLens expects Mifos X to say: paid in full, or still running."""
    paid = sum(float(r["transactionAmount"]) for r in repayments)
    return "closed" if paid >= float(loan["principal"]) - 0.005 else "active"


def ensure_setup(server: Fineract) -> int:
    """Taka allowed, and the loan product present. Returns the product's id."""
    currencies = server.call("GET", "/currencies")
    selected = [c["code"] for c in currencies.get("selectedCurrencyOptions", [])]
    if LOAN_CURRENCY not in selected:
        server.call("PUT", "/currencies", {"currencies": [*selected, LOAN_CURRENCY]})
    for product in server.call("GET", "/loanproducts"):
        if product.get("shortName") == PRODUCT["shortName"]:
            return int(product["id"])
    return int(server.call("POST", "/loanproducts", PRODUCT)["resourceId"])


def load_sample(
    server: Fineract,
    sample: dict[str, Any],
    product_id: int,
    progress: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Send the sample to the server and compare what it reports with what we expect."""
    repayments_of: dict[str, list[dict[str, Any]]] = {}
    for repayment in sample["transactions"]:
        repayments_of.setdefault(repayment["loanExternalId"], []).append(repayment)

    client_ids: dict[str, int] = {}
    refused: list[dict[str, str]] = []
    for client in sample["clients"]:
        try:
            client_ids[client["externalId"]] = server.call("POST", "/clients", client)["clientId"]
        except MifosError as error:
            refused.append({"what": f"client {client['externalId']}", "why": str(error)})
    progress(f"  clients created: {len(client_ids)} of {len(sample['clients'])}")

    loans_out: list[dict[str, Any]] = []
    for loan in sample["loans"]:
        client_id = client_ids.get(loan["clientExternalId"])
        if client_id is None:
            continue
        repayments = repayments_of.get(loan["externalId"], [])
        body = {k: v for k, v in loan.items() if k not in ("clientExternalId", "currency")}
        body.update(clientId=client_id, productId=product_id)
        try:
            loan_id = server.call("POST", "/loans", body)["loanId"]
            server.call(
                "POST",
                f"/loans/{loan_id}?command=approve",
                {"approvedOnDate": loan["submittedOnDate"], **DATE_FIELDS},
            )
            server.call(
                "POST",
                f"/loans/{loan_id}?command=disburse",
                {"actualDisbursementDate": loan["expectedDisbursementDate"], **DATE_FIELDS},
            )
            for repayment in sorted(repayments, key=lambda r: r["transactionDate"]):
                server.call(
                    "POST",
                    f"/loans/{loan_id}/transactions?command=repayment",
                    {
                        "transactionDate": repayment["transactionDate"],
                        "transactionAmount": repayment["transactionAmount"],
                        **DATE_FIELDS,
                    },
                )
        except MifosError as error:
            refused.append({"what": f"loan {loan['externalId']}", "why": str(error)})
            continue
        state = server.call("GET", f"/loans/{loan_id}")
        status = state.get("status") or {}
        reported = "closed" if status.get("closedObligationsMet") else (
            "active" if status.get("active") else str(status.get("value"))
        )
        expected = expected_status(loan, repayments)
        loans_out.append(
            {
                "externalId": loan["externalId"],
                "mifosLoanId": loan_id,
                "kept_external_id": state.get("externalId") == loan["externalId"],
                "currency": (state.get("currency") or {}).get("code"),
                "expected": expected,
                "mifos_says": reported,
                "agrees": expected == reported,
                "outstanding": (state.get("summary") or {}).get("totalOutstanding"),
            }
        )
    progress(f"  loans loaded: {len(loans_out)} of {len(sample['loans'])}")

    return {
        "clients_sent": len(sample["clients"]),
        "clients_created": len(client_ids),
        "loans_sent": len(sample["loans"]),
        "loans_loaded": len(loans_out),
        "repayments_sent": len(sample["transactions"]),
        "status_agrees": sum(1 for loan in loans_out if loan["agrees"]),
        "external_ids_kept": sum(1 for loan in loans_out if loan["kept_external_id"]),
        "refused": refused,
        "loans": loans_out,
    }


def main(argv: list[str] | None = None) -> int:
    """Command line: load a sample into the local Mifos X and report."""
    parser = argparse.ArgumentParser(description="Load CredLens's export into a local Mifos X.")
    parser.add_argument("--merchants", type=int, default=50, help="how many merchants to load")
    parser.add_argument("--url", default=DEFAULT_URL, help="Mifos X server; default: this laptop")
    arguments = parser.parse_args(argv)

    started = time.time()
    sample = pick_sample(read_export(), arguments.merchants)
    server = Fineract(arguments.url)
    product_id = ensure_setup(server)
    print(f"Loading {len(sample['clients'])} merchants and {len(sample['loans'])} loans ...")
    report = load_sample(server, sample, product_id)
    report["seconds"] = round(time.time() - started, 1)
    report["server"] = arguments.url
    path = EXPORT_DIR / REPORT_FILE
    path.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")

    print(
        f"Done in {report['seconds']} s. Mifos X agrees with CredLens on "
        f"{report['status_agrees']} of {report['loans_loaded']} loan statuses; "
        f"{len(report['refused'])} requests refused."
    )
    for item in report["refused"][:5]:
        print(f"  refused: {item['what']}: {item['why']}")
    print(f"Report: {path}")
    return 0 if not report["refused"] and report["status_agrees"] == report["loans_loaded"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
