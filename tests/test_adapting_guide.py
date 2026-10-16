"""Tests that docs/adapting.md tells the truth.

Owner role: D (full-stack).
Implements: Phase 12 (docs/adapting.md: how another lender adds a data adapter).

The page makes claims that code can check: the column lists equal the data contract; the adapter
it shows runs and gives the same tables as the synthetic adapter on the fixture files; a wrong
column is refused by name; a missing stream lowers coverage and makes up no features; every place
it says to change really exists. When one of these breaks, the page is out of date: fix the page.
"""

from __future__ import annotations

import copy
import inspect
import re
import shutil
from pathlib import Path
from typing import get_args

import numpy as np
import pandas as pd
import pytest

from src.adapters.base import CONTRACT, DataAdapter, empty_frame
from src.adapters.shopup_synthetic import ShopUpSyntheticAdapter
from src.api.schemas import DataMode
from src.config import VALID_MODES, load_config
from src.features import dictionary as dictionary_module
from src.features.build_features import CHECKLIST_ITEMS, DELIVERY_FEATURES
from src.model.dataset import build_dataset
from src.model.score import score_table
from src.synth.generate import build_tables

ROOT = Path(__file__).resolve().parent.parent
GUIDE = (ROOT / "docs" / "adapting.md").read_text(encoding="utf-8")
FIXTURES = ROOT / "tests" / "fixtures" / "contract"


def code_blocks(language: str) -> list[str]:
    return re.findall(rf"```{language}\n(.*?)```", GUIDE, flags=re.DOTALL)


# --- section 2: the contract -------------------------------------------------------------


def test_the_column_lists_in_the_guide_are_the_data_contract():
    listed = {}
    for line in code_blocks("text")[0].strip().splitlines():
        table, columns = line.split(":", 1)
        listed[table.strip()] = [name.strip() for name in columns.split(",")]
    assert listed == CONTRACT


# --- section 3: the adapter ---------------------------------------------------------------


@pytest.fixture()
def lender_adapter_class():
    """The class from the guide's code block, exactly as written."""
    namespace: dict = {}
    exec(compile(code_blocks("python")[0], "docs/adapting.md", "exec"), namespace)  # noqa: S102
    return namespace["LenderXAdapter"]


@pytest.fixture()
def export(tmp_path):
    """A lender's export folder: the fixture files, named like the tables."""
    folder = tmp_path / "export"
    shutil.copytree(FIXTURES, folder)
    return folder


def test_the_adapter_in_the_guide_is_a_data_adapter_with_a_mode(lender_adapter_class):
    assert issubclass(lender_adapter_class, DataAdapter)
    assert lender_adapter_class.mode == "lender_x"


def test_the_adapter_in_the_guide_gives_the_same_tables_as_the_synthetic_adapter(
    lender_adapter_class, export
):
    config = load_config()
    ours = lender_adapter_class(config, export).load_all()
    reference = ShopUpSyntheticAdapter(config, export).load_all()
    assert list(ours) == list(reference) == list(CONTRACT)
    for table in CONTRACT:
        pd.testing.assert_frame_equal(ours[table], reference[table], check_dtype=True)
    assert len(ours["loans"]) > 0
    audit = lender_adapter_class(config, export).audit_frame()
    assert list(audit.columns) == ["merchant_id", "town_tier", "shop_type", "has_trade_license"]


def test_a_stream_the_lender_does_not_have_stays_empty_with_the_right_columns(
    lender_adapter_class, export
):
    (export / "deliveries.csv").unlink()
    tables = lender_adapter_class(load_config(), export).load_all()
    assert tables["deliveries"].empty
    assert list(tables["deliveries"].columns) == CONTRACT["deliveries"]
    assert not tables["purchases"].empty  # the others are untouched


def test_a_wrong_column_is_refused_by_name(lender_adapter_class, export):
    path = export / "merchants.csv"
    text = path.read_text(encoding="utf-8").replace("town_tier", "tier_of_town", 1)
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError) as error:
        lender_adapter_class(load_config(), export).load_merchants()
    assert "town_tier" in str(error.value) and "tier_of_town" in str(error.value)
    assert "does not match the data contract" in str(error.value)


def test_a_column_that_is_not_in_the_contract_is_refused_too(lender_adapter_class, export):
    path = export / "loans.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    rows = [lines[0] + ",approved"] + [line + ",yes" for line in lines[1:]]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unexpected columns: \\['approved'\\]"):
        lender_adapter_class(load_config(), export).load_loans()


# --- a missing stream lowers coverage and makes up nothing --------------------------------


@pytest.fixture(scope="module")
def small_world():
    config = copy.deepcopy(load_config())
    config["data"]["n_merchants"] = 300
    tables = build_tables(config, 0.5)[0]
    return config, tables


def test_without_parcel_data_there_are_no_delivery_features_and_coverage_falls(small_world):
    config, tables = small_world
    with_parcels = build_dataset(tables, config)
    without = build_dataset({**tables, "deliveries": empty_frame("deliveries")}, config)
    assert len(with_parcels) == len(without)

    # nothing is made up: every delivery input is missing, not zero
    for name in DELIVERY_FEATURES:
        assert without[name].isna().all(), name
        assert with_parcels[name].notna().any(), name
    assert not without["cov_deliveries_present"].any()
    assert with_parcels["cov_deliveries_present"].any()

    # coverage falls by the weight of the item for the loans that had parcels, and by the weight of
    # "recent activity" too when a parcel was a merchant's only recent activity
    sure = np.full(len(with_parcels), 0.9)
    before = score_table(sure, with_parcels, config)["coverage"].to_numpy()
    after = score_table(sure, without, config)["coverage"].to_numpy()
    weights = config["coverage_weights"]
    weight = weights["deliveries_present"]
    had = with_parcels["cov_deliveries_present"].to_numpy()
    drops = np.round((before - after)[had], 4)
    assert set(drops) <= {round(weight, 4), round(weight + weights["recent_activity_30d"], 4)}
    assert (drops == round(weight, 4)).mean() > 0.9  # the usual case
    assert np.allclose((before - after)[~had], 0)
    assert (after <= before + 1e-12).all()
    # the probability given is the same: the score itself is not touched by the table's shape
    assert (score_table(sure, without, config)["score"] == 90).all()


def test_the_six_coverage_items_and_their_starting_weights_are_as_the_guide_says(small_world):
    config, _ = small_world
    for name in CHECKLIST_ITEMS:
        assert f"`{name}`" in GUIDE
    weights = config["coverage_weights"]
    assert set(weights) == set(CHECKLIST_ITEMS)
    order = ["history_6_months", "purchases_present", "payments_present"]
    order += ["deliveries_present", "questionnaire_done", "recent_activity_30d"]
    assert [weights[name] for name in order] == [0.25, 0.20, 0.20, 0.15, 0.10, 0.10]
    assert "0.25, 0.20, 0.20, 0.15, 0.10, 0.10" in GUIDE


# --- section 4: the places the guide names ------------------------------------------------

PLACES = [
    ("src/adapters/factory.py", "ADAPTERS"),
    ("src/config.py", "VALID_MODES"),
    ("src/config.py", "SOURCE_LABELS"),
    ("tasks.py", "VALID_MODES"),
    ("src/db/load.py", "LOADABLE_MODES"),
    ("src/model/model_card.py", "SOURCES"),
    ("src/model/model_card.py", "READING"),
    ("src/model/model_card.py", "MODE_LIMITS"),
    ("src/model/model_card.py", "TEST_READING"),
    ("src/features/dictionary.py", "features_for_mode"),
    ("src/model/inputs.py", "model_inputs"),
    ("src/model/inputs.py", "SIMPLER_MODELS"),
    ("src/features/source_features.py", "MODEL_INPUTS"),
    ("config/default.yaml", "coverage_weights_by_mode"),
    ("config/default.yaml", "audit_only_columns"),
    ("config/default.yaml", "split_by_mode"),
    ("config/default.yaml", "supplied_by_source"),
    ("web/src/lib/modes.ts", "MODE_ORDER"),
]


@pytest.mark.parametrize("path,name", PLACES)
def test_every_place_the_guide_says_to_change_exists_and_is_named_in_it(path, name):
    assert name in (ROOT / path).read_text(encoding="utf-8"), f"{name} is not in {path}"
    assert name in GUIDE, f"the guide never names {name}"
    assert path in GUIDE or Path(path).name in GUIDE, f"the guide never names {path}"


@pytest.mark.parametrize(
    "command,module",
    [
        ("python -m src.model.fairness --mode", "src/model/fairness.py"),
        ("python -m src.model.model_card --mode", "src/model/model_card.py"),
        ("python -m src.model.final_test --mode", "src/model/final_test.py"),
        ("python tasks.py train --mode", "tasks.py"),
    ],
)
def test_every_command_in_the_guide_exists_and_takes_a_mode(command, module):
    assert command in GUIDE
    assert '"--mode"' in (ROOT / module).read_text(encoding="utf-8")


def test_the_api_reads_its_data_modes_from_the_one_list():
    assert get_args(DataMode) == VALID_MODES


def test_the_known_gap_is_in_the_guide_for_as_long_as_it_is_in_the_code():
    """The shared feature path compares the mode with `synthetic_bd`. While it does, the guide
    says so; the day the code stops doing it, this test says the guide must be rewritten."""
    source = inspect.getsource(dictionary_module.features_for_mode)
    still_tied = "SYNTHETIC_MODE" in source
    assert ("Known gap" in GUIDE) == still_tied, (
        "docs/adapting.md section 4 ('Known gap') no longer matches src/features/dictionary.py: "
        "update the guide"
    )


def test_the_guide_never_claims_more_than_it_checked():
    assert "Oct 16" in GUIDE  # the date of the throwaway-adapter check it reports
    for claim in ("works for every lender", "plug and play", "no code changes"):
        assert claim not in GUIDE.lower()
