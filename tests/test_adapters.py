"""Tests for the adapter interface and the data contract.

Owner role: B (data engineer).
Implements: PROJECT_BRIEF sections 5 and 18; Phase 0 (interface) and Phase 7 (public adapters).
"""

from __future__ import annotations

import copy

import pandas as pd
import pytest

from src.adapters import CONTRACT, DataAdapter, check_frame, empty_frame, get_adapter
from src.adapters.homecredit import HomeCreditAdapter
from src.adapters.india_ltfs import IndiaLtfsAdapter
from src.adapters.kiva_asia import KivaAsiaAdapter
from src.adapters.shopup_real import ShopUpRealAdapter
from src.adapters.shopup_synthetic import ShopUpSyntheticAdapter
from src.adapters.taiwan_cc import TaiwanCreditCardAdapter
from src.config import VALID_MODES

EXPECTED_CLASS = {
    "synthetic_bd": ShopUpSyntheticAdapter,
    "kiva_asia": KivaAsiaAdapter,
    "taiwan_cc": TaiwanCreditCardAdapter,
    "india_ltfs": IndiaLtfsAdapter,
    "homecredit": HomeCreditAdapter,
}


def with_mode(config: dict, mode: str) -> dict:
    """Return a copy of the config with another data mode."""
    changed = copy.deepcopy(config)
    changed["data"]["mode"] = mode
    return changed


@pytest.mark.parametrize("mode", VALID_MODES)
def test_factory_returns_the_adapter_for_each_mode(config, mode):
    adapter = get_adapter(with_mode(config, mode))
    assert isinstance(adapter, EXPECTED_CLASS[mode])
    assert isinstance(adapter, DataAdapter)
    assert adapter.mode == mode


def test_factory_rejects_an_unknown_mode(config):
    with pytest.raises(ValueError, match="No adapter for data mode"):
        get_adapter(with_mode(config, "shopup_real"))


def test_contract_has_the_seven_tables():
    assert list(CONTRACT) == [
        "merchants",
        "purchases",
        "deliveries",
        "payments",
        "loans",
        "questionnaire",
        "consents",
    ]
    for table, columns in CONTRACT.items():
        assert "merchant_id" in columns, table
        assert len(columns) == len(set(columns)), table


def test_purchases_are_not_sales():
    """Mokam data is what the merchant buys. No sales or customer columns."""
    for column in CONTRACT["purchases"]:
        assert "sale" not in column and "customer" not in column


@pytest.mark.parametrize(
    ("mode", "missing_streams"),
    [
        ("kiva_asia", ["purchases", "deliveries", "payments", "questionnaire"]),
        ("taiwan_cc", ["purchases", "deliveries", "questionnaire"]),
        ("india_ltfs", ["purchases", "deliveries", "payments", "questionnaire"]),
        ("homecredit", ["purchases", "deliveries", "questionnaire"]),
    ],
)
def test_streams_a_public_source_lacks_are_empty_not_invented(config, mode, missing_streams):
    adapter = get_adapter(with_mode(config, mode))
    for table in missing_streams:
        frame = getattr(adapter, f"load_{table}")()
        assert frame.empty, table
        assert list(frame.columns) == CONTRACT[table], table


@pytest.mark.parametrize("adapter_class", [ShopUpRealAdapter])
def test_unbuilt_adapters_say_so_clearly(config, adapter_class):
    adapter = adapter_class(config)
    with pytest.raises(NotImplementedError, match="load_merchants"):
        adapter.load_merchants()


def test_check_frame_accepts_the_contract_and_orders_columns():
    frame = empty_frame("loans")[list(reversed(CONTRACT["loans"]))]
    assert list(check_frame("loans", frame).columns) == CONTRACT["loans"]


def test_check_frame_names_missing_and_unexpected_columns():
    frame = pd.DataFrame(columns=["loan_id", "merchant_id", "surprise"])
    with pytest.raises(ValueError) as error:
        check_frame("loans", frame)
    assert "issued_at" in str(error.value)
    assert "surprise" in str(error.value)


# The public adapters are tested in their own files (Phase 7): each checks that its seven
# tables match the contract and that its audit columns never reach the model inputs
# (tests/test_taiwan_cc.py, test_india_ltfs.py, test_homecredit.py, test_kiva_asia.py).
