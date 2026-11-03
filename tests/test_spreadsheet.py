"""Unit tests for reading purchase workbooks (src/intake/spreadsheet.py). No database needed.

The API journey (preview, commit, duplicates, repeat uploads) is in tests/test_api_intake.py.
"""

from __future__ import annotations

import copy
import io
from datetime import date, datetime

import pytest
from openpyxl import Workbook

from src.config import load_config
from src.intake import spreadsheet
from src.intake.policy import IntakeRefused


def xlsx(rows: list[list], title: str = "Purchases") -> bytes:
    book = Workbook()
    sheet = book.active
    sheet.title = title
    for row in rows:
        sheet.append(row)
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


@pytest.mark.parametrize(
    "value, expected",
    [
        (9500, 9500.0),
        ("9,500", 9500.0),
        ("৳ 9,500.50", 9500.5),
        ("Tk 12000/-", 12000.0),
        ("৯৫০০", 9500.0),
        ("nine", None),
        ("", None),
        (True, None),
    ],
)
def test_amounts_are_read_defensively(value, expected):
    assert spreadsheet.parse_amount(value) == expected


def test_dates_are_read_and_ambiguous_ones_are_not_guessed():
    assert spreadsheet.parse_date(datetime(2026, 8, 3, 10, 0), "auto") == (date(2026, 8, 3), False)
    assert spreadsheet.parse_date("2026-08-03", "auto") == (date(2026, 8, 3), False)
    assert spreadsheet.parse_date("25/07/2026", "auto") == (date(2026, 7, 25), False)
    assert spreadsheet.parse_date("07/25/2026", "auto") == (date(2026, 7, 25), False)
    assert spreadsheet.parse_date("03/04/2026", "auto") == (None, True)
    assert spreadsheet.parse_date("03/04/2026", "dmy") == (date(2026, 4, 3), False)
    assert spreadsheet.parse_date("03/04/2026", "mdy") == (date(2026, 3, 4), False)
    assert spreadsheet.parse_date("৩০/০৮/২০২৬", "auto") == (date(2026, 8, 30), False)
    assert spreadsheet.parse_date("12 Aug 2026", "auto") == (date(2026, 8, 12), False)
    assert spreadsheet.parse_date(46264, "auto")[0] is not None  # an unformatted Excel day number
    assert spreadsheet.parse_date("31/02/2026", "dmy") == (None, False)
    assert spreadsheet.parse_date("soon", "auto") == (None, False)


def test_columns_are_suggested_from_contract_names_then_common_words():
    header = ["Memo No", "Date", "Items", "Total Amount", "Wholesaler"]
    mapping = spreadsheet.suggest_mapping(header)
    assert mapping == {
        "purchase_date": "Date",
        "amount_bdt": "Total Amount",
        "category": "Items",
        "invoice_reference": "Memo No",
        "supplier_reference": "Wholesaler",
    }
    contract = spreadsheet.suggest_mapping(["purchase_date", "amount_bdt"])
    assert contract["purchase_date"] == "purchase_date" and contract["category"] is None


def test_a_workbook_is_read_sheet_by_sheet_and_bad_files_are_refused():
    config = load_config()
    book = spreadsheet.read_workbook(
        xlsx([[], ["Date", "Amount"], ["2026-08-01", 500], [None, None], ["2026-08-02", 600]]),
        config,
    )
    sheet = book.sheets["Purchases"]
    assert sheet.header == ["Date", "Amount"]
    assert [n for n, _ in sheet.rows] == [3, 5]  # Excel row numbers; blank rows skipped
    with pytest.raises(IntakeRefused) as error:
        spreadsheet.read_workbook(b"date,amount\n2026-08-01,500\n", config)
    assert error.value.code == "not_a_workbook"
    with pytest.raises(IntakeRefused) as error:
        spreadsheet.read_workbook(b"", config)
    assert error.value.code == "empty_file"
    small = copy.deepcopy(config)
    small["demo"]["purchase_import"]["max_rows"] = 1
    assert spreadsheet.read_workbook(
        xlsx([["Date", "Amount"], ["2026-08-01", 1], ["2026-08-02", 2]]), small
    ).sheets["Purchases"].truncated


def test_the_preview_token_changes_with_any_choice():
    base = ("CL-M-000001", "f" * 64, "Purchases", {"purchase_date": "Date"}, "auto")
    token = spreadsheet.preview_token(*base)
    assert token == spreadsheet.preview_token(*base)
    assert token != spreadsheet.preview_token("CL-M-000002", *base[1:])
    assert token != spreadsheet.preview_token(*base[:4], "dmy")
    assert token != spreadsheet.preview_token(*base[:3], {"purchase_date": "Bill date"}, "auto")
