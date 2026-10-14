"""Tests for loading the export into Mifos X, without a server.

Owner role: B (data engineer).
Implements: PROJECT_BRIEF section 18, item 35. Tests and CI run with no network, so a
    small fake server stands in for Fineract here; the real run against a local Fineract
    is recorded in the brief.
"""

from __future__ import annotations

import pytest

from src.db.mifos_load import (
    PRODUCT,
    MifosError,
    ensure_setup,
    expected_status,
    load_sample,
    pick_sample,
)


class FakeFineract:
    """Answers like Fineract for the calls the loader makes, and remembers them."""

    def __init__(self, refuse_client: str | None = None, bdt_enabled: bool = False) -> None:
        self.calls: list[tuple[str, str, dict | None]] = []
        self.refuse_client = refuse_client
        self.currencies = ["USD", "BDT"] if bdt_enabled else ["USD"]
        self.products: list[dict] = []
        self.loans: dict[int, dict] = {}

    def call(self, method, path, body=None):
        self.calls.append((method, path, body))
        if path == "/currencies":
            if method == "PUT":
                self.currencies = body["currencies"]
                return {}
            return {"selectedCurrencyOptions": [{"code": c} for c in self.currencies]}
        if path == "/loanproducts":
            if method == "POST":
                self.products.append({"id": 7, "shortName": body["shortName"]})
                return {"resourceId": 7}
            return self.products
        if path == "/clients":
            if body["externalId"] == self.refuse_client:
                raise MifosError("POST /clients: legalFormId: The parameter is mandatory.")
            return {"clientId": 100 + len([c for c in self.calls if c[1] == "/clients"])}
        if path == "/loans":
            loan_id = len(self.loans) + 1
            self.loans[loan_id] = {"body": body, "paid": 0.0}
            return {"loanId": loan_id}
        if "/transactions?command=repayment" in path:
            loan_id = int(path.split("/")[2])
            self.loans[loan_id]["paid"] += float(body["transactionAmount"])
            return {}
        if "?command=" in path:
            return {}
        if method == "GET" and path.startswith("/loans/"):
            loan = self.loans[int(path.split("/")[2])]
            closed = loan["paid"] >= loan["body"]["principal"]
            return {
                "externalId": loan["body"]["externalId"],
                "currency": {"code": "BDT"},
                "status": {"closedObligationsMet": closed, "active": not closed},
                "summary": {"totalOutstanding": loan["body"]["principal"] - loan["paid"]},
            }
        raise AssertionError(f"unexpected call {method} {path}")


def export() -> dict:
    clients = [
        {"externalId": f"M{i}", "officeId": 1, "legalFormId": 2, "fullname": f"Merchant M{i}"}
        for i in range(1, 5)
    ]
    loans = [
        {"externalId": "L1", "clientExternalId": "M1", "principal": 1000.0, "currency": "BDT",
         "submittedOnDate": "2026-01-05", "expectedDisbursementDate": "2026-01-05"},
        {"externalId": "L2", "clientExternalId": "M1", "principal": 500.0, "currency": "BDT",
         "submittedOnDate": "2026-03-01", "expectedDisbursementDate": "2026-03-01"},
        {"externalId": "L3", "clientExternalId": "M2", "principal": 800.0, "currency": "BDT",
         "submittedOnDate": "2026-02-01", "expectedDisbursementDate": "2026-02-01"},
    ]  # fmt: skip
    transactions = [
        {"loanExternalId": "L1", "transactionDate": "2026-02-01", "transactionAmount": 1000.0},
        {"loanExternalId": "L3", "transactionDate": "2026-03-01", "transactionAmount": 300.0},
    ]
    return {"clients": clients, "loans": loans, "transactions": transactions}


def test_the_sample_takes_merchants_with_loans_and_all_their_loans():
    sample = pick_sample(export(), merchants=5)
    assert [c["externalId"] for c in sample["clients"]] == ["M1", "M2"], "M3 and M4 have no loan"
    assert [loan["externalId"] for loan in sample["loans"]] == ["L1", "L2", "L3"]
    one = pick_sample(export(), merchants=1)
    assert [loan["externalId"] for loan in one["loans"]] == ["L1", "L2"]
    assert [t["loanExternalId"] for t in one["transactions"]] == ["L1"]


def test_expected_status_is_closed_only_when_paid_in_full():
    loan = {"principal": 1000.0}
    assert expected_status(loan, [{"transactionAmount": 1000.0}]) == "closed"
    two_parts = [{"transactionAmount": 600}, {"transactionAmount": 400}]
    assert expected_status(loan, two_parts) == "closed"
    assert expected_status(loan, [{"transactionAmount": 300.0}]) == "active"
    assert expected_status(loan, []) == "active"


def test_setup_allows_taka_and_creates_the_product_once():
    server = FakeFineract()
    assert ensure_setup(server) == 7
    assert "BDT" in server.currencies
    assert server.products[0]["shortName"] == PRODUCT["shortName"]
    assert ensure_setup(server) == 7, "found again, not created twice"
    assert sum(1 for m, p, _ in server.calls if (m, p) == ("POST", "/loanproducts")) == 1


def test_each_loan_is_submitted_approved_disbursed_and_repaid_in_that_order():
    server = FakeFineract(bdt_enabled=True)
    report = load_sample(server, pick_sample(export(), 5), product_id=7, progress=lambda _: None)
    assert report["loans_loaded"] == 3 and report["refused"] == []
    first = [path for _, path, _ in server.calls if path.startswith("/loans/1")]
    assert first == [
        "/loans/1?command=approve",
        "/loans/1?command=disburse",
        "/loans/1/transactions?command=repayment",
        "/loans/1",
    ]
    sent = server.loans[1]["body"]
    assert sent["clientId"] == 101 and sent["productId"] == 7
    assert "clientExternalId" not in sent, "our linking field is turned into Fineract's id"


def test_mifos_status_is_compared_with_what_credlens_expects():
    server = FakeFineract(bdt_enabled=True)
    report = load_sample(server, pick_sample(export(), 5), product_id=7, progress=lambda _: None)
    by_loan = {loan["externalId"]: loan for loan in report["loans"]}
    assert by_loan["L1"]["expected"] == by_loan["L1"]["mifos_says"] == "closed"
    assert by_loan["L2"]["mifos_says"] == "active", "no repayment"
    assert by_loan["L3"]["mifos_says"] == "active", "part paid"
    assert report["status_agrees"] == 3 and report["external_ids_kept"] == 3


def test_a_refused_client_is_reported_and_its_loans_skipped():
    server = FakeFineract(refuse_client="M1", bdt_enabled=True)
    report = load_sample(server, pick_sample(export(), 5), product_id=7, progress=lambda _: None)
    assert report["clients_created"] == 1
    assert report["loans_loaded"] == 1, "only M2's loan"
    assert "legalFormId" in report["refused"][0]["why"]


def test_reading_a_missing_export_says_how_to_make_it(tmp_path):
    from src.db.mifos_load import read_export

    with pytest.raises(FileNotFoundError, match="python -m src.db.mifos_adapter"):
        read_export(tmp_path)
