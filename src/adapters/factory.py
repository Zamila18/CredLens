"""Choose the adapter for the active data mode.

Purpose: the only place that knows which adapter class serves which mode, so
    the rest of the pipeline never names a data source.
Owner role: B (data engineer).
Implements: CLAUDE.md ("never hard-wire the pipeline to one source"); PROJECT_BRIEF section 18.
"""

from __future__ import annotations

from typing import Any

from src.adapters.base import DataAdapter
from src.adapters.homecredit import HomeCreditAdapter
from src.adapters.india_ltfs import IndiaLtfsAdapter
from src.adapters.kiva_asia import KivaAsiaAdapter
from src.adapters.shopup_synthetic import ShopUpSyntheticAdapter
from src.adapters.taiwan_cc import TaiwanCreditCardAdapter

ADAPTERS: dict[str, type[DataAdapter]] = {
    "synthetic_bd": ShopUpSyntheticAdapter,
    "kiva_asia": KivaAsiaAdapter,
    "taiwan_cc": TaiwanCreditCardAdapter,
    "india_ltfs": IndiaLtfsAdapter,
    "homecredit": HomeCreditAdapter,
}


def get_adapter(config: dict[str, Any]) -> DataAdapter:
    """Return the adapter for `config["data"]["mode"]`."""
    mode = config["data"]["mode"]
    if mode not in ADAPTERS:
        raise ValueError(f"No adapter for data mode {mode!r}. Known modes: {', '.join(ADAPTERS)}.")
    return ADAPTERS[mode](config)
