"""Tests for the synthetic data generator (synthetic_bd mode).

Owner role: B (data engineer).
Implements: docs/GENERATOR_SPEC.md ("Required self-checks") and PROJECT_BRIEF section 5.

The tests build a smaller data set in memory (a few thousand merchants) so they stay
fast. The hidden-truth table is used here, and only here, to check the generator.
"""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

from src.adapters import CONTRACT
from src.adapters.shopup_synthetic import ShopUpSyntheticAdapter
from src.config import load_config
from src.synth.generate import ALL_STRENGTHS, build_tables, generate
from src.synth.paths import LATENT_FILE, META_FILE
from src.synth.seasonality import monthly_index

N_MERCHANTS = 4000
MERCHANT_RETURN_REASONS = ["refused", "wrong_item", "other"]
LOGISTICS_REASONS = ["address_issue", "rider_issue"]


def small_config(n_merchants: int = N_MERCHANTS, seed: int = 42) -> dict:
    """The default config with fewer merchants, so tests run quickly."""
    config = copy.deepcopy(load_config())
    config["data"]["n_merchants"] = n_merchants
    config["seed"] = seed
    return config


@pytest.fixture(scope="module")
def by_strength() -> dict[float, tuple[dict[str, pd.DataFrame], pd.DataFrame, dict]]:
    """Tables, hidden truth and run facts for each delivery signal strength."""
    config = small_config()
    return {strength: build_tables(config, strength) for strength in ALL_STRENGTHS}


@pytest.fixture(scope="module")
def tables(by_strength) -> dict[str, pd.DataFrame]:
    return by_strength[0.5][0]


@pytest.fixture(scope="module")
def latent(by_strength) -> pd.DataFrame:
    return by_strength[0.5][1]


@pytest.fixture(scope="module")
def facts(by_strength) -> dict:
    return by_strength[0.5][2]


def merchant_delivery_stats(tables: dict[str, pd.DataFrame], latent: pd.DataFrame) -> pd.DataFrame:
    """Per merchant: hidden reliability, parcel count and merchant-attributable return rate."""
    deliveries = tables["deliveries"]
    merchant_return = deliveries["status"].eq("returned") & deliveries["return_reason"].isin(
        MERCHANT_RETURN_REASONS
    )
    stats = (
        deliveries.assign(merchant_return=merchant_return)
        .groupby("merchant_id")
        .agg(parcels=("status", "size"), return_rate=("merchant_return", "mean"))
    )
    return stats.join(latent.set_index("merchant_id")["reliability"]).query("parcels >= 20")


# --- shape and reproducibility -----------------------------------------------------


def test_tables_match_the_data_contract(tables):
    assert list(tables) == list(CONTRACT)
    for name, frame in tables.items():
        assert list(frame.columns) == CONTRACT[name], name
        assert len(frame) > 0, name


def test_row_counts_and_reproducibility():
    """Same seed gives exactly the same data."""
    first, _, _ = build_tables(small_config(800), 0.5)
    second, _, _ = build_tables(small_config(800), 0.5)
    for name in CONTRACT:
        pd.testing.assert_frame_equal(first[name], second[name])


def test_a_different_seed_gives_different_data():
    first, _, _ = build_tables(small_config(800, seed=42), 0.5)
    second, _, _ = build_tables(small_config(800, seed=7), 0.5)
    assert not first["merchants"]["onboarded_at"].equals(second["merchants"]["onboarded_at"])


def test_signal_strength_changes_only_the_deliveries(by_strength):
    zero, one = by_strength[0.0][0], by_strength[1.0][0]
    for name in CONTRACT:
        if name == "deliveries":
            assert not zero[name].equals(one[name])
        else:
            pd.testing.assert_frame_equal(zero[name], one[name])


# --- master data ---------------------------------------------------------------------


def test_ids_are_unique(tables):
    assert tables["merchants"]["merchant_id"].is_unique
    assert len(tables["merchants"]) == N_MERCHANTS
    for name, key in [
        ("purchases", "purchase_id"),
        ("deliveries", "delivery_id"),
        ("payments", "payment_id"),
        ("loans", "loan_id"),
        ("consents", "consent_id"),
    ]:
        assert tables[name][key].is_unique, name
    assert tables["questionnaire"]["merchant_id"].is_unique


def test_every_foreign_key_resolves(tables):
    merchants = set(tables["merchants"]["merchant_id"])
    for name in CONTRACT:
        assert set(tables[name]["merchant_id"]) <= merchants, name
    assert set(tables["payments"]["loan_id"]) == set(tables["loans"]["loan_id"])


# --- dates ---------------------------------------------------------------------------


def test_dates_are_in_order(tables, facts):
    """No event before the merchant was onboarded and none after the window ends."""
    onboarded = pd.to_datetime(tables["merchants"].set_index("merchant_id")["onboarded_at"])
    window_end = pd.Timestamp(facts["window_end"]) + pd.Timedelta(days=1)
    for name, column in [
        ("purchases", "purchase_date"),
        ("deliveries", "dispatched_at"),
        ("loans", "issued_at"),
        ("questionnaire", "answered_at"),
    ]:
        frame = tables[name]
        when = pd.to_datetime(frame[column])
        started = onboarded.reindex(frame["merchant_id"]).to_numpy()
        assert (when.to_numpy() >= started).all(), name
        assert (when < window_end).all(), name


def test_merchants_are_onboarded_in_the_main_window(tables, facts):
    onboarded = pd.to_datetime(tables["merchants"]["onboarded_at"])
    assert onboarded.min() >= pd.Timestamp(facts["window_start"])
    assert onboarded.max() <= pd.Timestamp(facts["main_window_end"])


def test_parcels_arrive_after_they_are_dispatched(tables):
    delivered = tables["deliveries"].dropna(subset=["delivered_at"])
    arrived = pd.to_datetime(delivered["delivered_at"])
    assert (arrived >= pd.to_datetime(delivered["dispatched_at"])).all()


def test_first_loan_waits_after_onboarding(tables):
    config = load_config()
    loans = tables["loans"].merge(tables["merchants"][["merchant_id", "onboarded_at"]])
    waited = (pd.to_datetime(loans["issued_at"]) - pd.to_datetime(loans["onboarded_at"])).dt.days
    assert waited.min() >= config["generator"]["loans"]["min_days_after_onboarding"]


# --- shares the config promises ----------------------------------------------------


def test_thin_file_share_is_near_target(tables, facts):
    """About 35% of merchants have very few purchases in their first 30 days."""
    config = load_config()
    merchants = tables["merchants"][["merchant_id", "onboarded_at"]]
    purchases = tables["purchases"].merge(merchants)
    early = (
        pd.to_datetime(purchases["purchase_date"]) - pd.to_datetime(purchases["onboarded_at"])
    ).dt.days < 30
    count_30d = purchases[early].groupby("merchant_id").size()
    count_30d = count_30d.reindex(merchants["merchant_id"]).fillna(0)
    thin = count_30d <= config["generator"]["purchases"]["thin_file_max_purchases_30d"]
    assert thin.mean() == pytest.approx(config["data"]["thin_file_share"], abs=0.05)


def test_share_without_delivery_data_is_near_target(tables):
    config = load_config()
    with_parcels = tables["deliveries"]["merchant_id"].nunique() / len(tables["merchants"])
    assert 1 - with_parcels == pytest.approx(config["data"]["no_delivery_data_share"], abs=0.03)


def test_consent_and_questionnaire_shares_are_near_target(tables):
    config = load_config()
    merchants = tables["merchants"]
    assert merchants["consent_data_use"].mean() == pytest.approx(
        config["data"]["consent_rate"], abs=0.02
    )
    assert merchants["questionnaire_done"].mean() == pytest.approx(
        config["data"]["questionnaire_rate"], abs=0.03
    )


def test_repayment_share_is_in_range(tables, facts):
    """Repaid share is close to the target in the config (a team assumption)."""
    target = load_config()["generator"]["repayment_share_target"]
    observed = tables["loans"]["outcome_label"].dropna().astype(int)
    assert observed.mean() == pytest.approx(target, abs=0.02)
    assert facts["repaid_share_observed"] == pytest.approx(observed.mean())


# --- labels --------------------------------------------------------------------------


def test_labels_follow_the_thirty_day_rule(tables):
    """Label 1 means paid within the allowed days late; anything else is 0."""
    limit = load_config()["labels"]["good_if_days_late_at_most"]
    joined = tables["loans"].merge(tables["payments"], on=["loan_id", "merchant_id"])
    judged = joined.dropna(subset=["outcome_label"])
    days_late = (pd.to_datetime(judged["paid_date"]) - pd.to_datetime(judged["due_date"])).dt.days
    paid_in_time = judged["paid_date"].notna() & (days_late <= limit)
    assert (judged["outcome_label"].astype(int) == paid_in_time.astype(int)).all()


def test_young_loans_have_no_label(tables, facts):
    """A loan younger than the minimum age is left without an outcome."""
    minimum_age = load_config()["labels"]["min_loan_age_days"]
    loans = tables["loans"]
    age = (pd.Timestamp(facts["window_end"]) - pd.to_datetime(loans["issued_at"])).dt.days
    assert loans.loc[age < minimum_age, "outcome_label"].isna().all()
    assert (age < minimum_age).any(), "some pending loans must exist for the review queue"


def test_an_unpaid_loan_is_called_bad_only_once_it_is_overdue_enough(tables, facts):
    """A loan exactly 30 days past due could still be repaid in time today: no label yet."""
    limit = load_config()["labels"]["good_if_days_late_at_most"]
    joined = tables["loans"].merge(tables["payments"], on=["loan_id", "merchant_id"])
    overdue = (pd.Timestamp(facts["window_end"]) - pd.to_datetime(joined["due_date"])).dt.days
    unpaid = joined["paid_date"].isna()
    assert joined.loc[unpaid & (overdue <= limit), "outcome_label"].isna().all()
    assert (joined.loc[unpaid & (overdue > limit), "outcome_label"].dropna() == 0).all()


def test_every_loan_in_the_main_window_has_an_outcome(tables, facts):
    """So the last test months are fully labelled."""
    loans = tables["loans"]
    in_main = pd.to_datetime(loans["issued_at"]) <= pd.Timestamp(facts["main_window_end"])
    assert loans.loc[in_main, "outcome_label"].notna().all()


def test_unpaid_and_paid_amounts_are_consistent(tables):
    payments = tables["payments"]
    unpaid = payments["paid_date"].isna()
    assert (payments.loc[unpaid, "amount_paid_bdt"] == 0).all()
    paid = payments[~unpaid]
    assert (paid["amount_paid_bdt"] == paid["amount_due_bdt"]).all()


# --- the hidden signal ---------------------------------------------------------------


def test_purchases_reflect_hidden_reliability(tables, latent):
    per_merchant = tables["purchases"].groupby("merchant_id").size().rename("n_purchases")
    joined = latent.set_index("merchant_id").join(per_merchant).fillna({"n_purchases": 0})
    assert np.corrcoef(joined["reliability"], joined["n_purchases"])[0, 1] > 0.05


def test_delivery_signal_is_absent_at_strength_zero(by_strength):
    """At signal strength 0, delivery data does not track hidden reliability."""
    tables_zero, latent_zero, _ = by_strength[0.0]
    stats = merchant_delivery_stats(tables_zero, latent_zero)
    assert abs(np.corrcoef(stats["reliability"], stats["return_rate"])[0, 1]) < 0.06
    assert abs(np.corrcoef(stats["reliability"], stats["parcels"])[0, 1]) < 0.06


def test_delivery_signal_is_present_at_strength_one(by_strength):
    """At signal strength 1, reliable merchants have fewer merchant-attributable returns."""
    tables_one, latent_one, _ = by_strength[1.0]
    stats = merchant_delivery_stats(tables_one, latent_one)
    assert np.corrcoef(stats["reliability"], stats["return_rate"])[0, 1] < -0.15


def test_logistics_noise_returns_are_present(by_strength):
    """Part of returns and failures is tagged address_issue or rider_issue."""
    share = load_config()["data"]["logistics_noise_share"]
    deliveries = by_strength[0.0][0]["deliveries"]
    not_delivered = deliveries[deliveries["status"].isin(["returned", "failed"])]
    logistics = not_delivered["return_reason"].isin(LOGISTICS_REASONS)
    assert logistics.mean() == pytest.approx(share, abs=0.05)


def test_logistics_noise_does_not_depend_on_reliability(by_strength):
    """Even at full signal strength, address and rider problems are not the merchant's."""
    tables_one, latent_one, _ = by_strength[1.0]
    deliveries = tables_one["deliveries"]
    rate = (
        deliveries.assign(logistics=deliveries["return_reason"].isin(LOGISTICS_REASONS))
        .groupby("merchant_id")
        .agg(parcels=("logistics", "size"), logistics_rate=("logistics", "mean"))
        .join(latent_one.set_index("merchant_id")["reliability"])
        .query("parcels >= 20")
    )
    assert abs(np.corrcoef(rate["reliability"], rate["logistics_rate"])[0, 1]) < 0.06


# --- allowed values ------------------------------------------------------------------


def test_delivery_fields_use_allowed_values(tables):
    deliveries = tables["deliveries"]
    assert set(deliveries["status"]) <= {"delivered", "returned", "failed", "cancelled"}
    reasons = set(deliveries["return_reason"].dropna())
    assert reasons <= set(MERCHANT_RETURN_REASONS) | set(LOGISTICS_REASONS)
    delivered = deliveries["status"] == "delivered"
    assert deliveries.loc[delivered, "return_reason"].isna().all()
    assert deliveries.loc[delivered, "delivered_at"].notna().all()
    assert deliveries.loc[~delivered, "delivered_at"].isna().all()
    has_remit = deliveries["cod_remitted_on_time"].notna()
    assert (delivered & deliveries["is_cod"].astype(bool))[has_remit].all()


def test_merchant_fields_use_allowed_values(tables):
    generator = load_config()["generator"]
    merchants = tables["merchants"]
    assert set(merchants["town_tier"]) == set(generator["town_tier_shares"])
    assert set(merchants["shop_type"]) == set(generator["shop_type_shares"])
    for tier, names in generator["districts"].items():
        assert set(merchants.loc[merchants["town_tier"] == tier, "district"]) <= set(names)


def test_purchase_categories_belong_to_the_shop_type(tables):
    categories = load_config()["generator"]["categories"]
    purchases = tables["purchases"].merge(tables["merchants"][["merchant_id", "shop_type"]])
    for shop_type, names in categories.items():
        used = set(purchases.loc[purchases["shop_type"] == shop_type, "category"])
        assert used <= set(names), shop_type
    assert (purchases["amount_bdt"] > 0).all()


def test_questionnaire_answers_are_one_to_five_and_only_where_done(tables):
    questionnaire = tables["questionnaire"]
    items = [c for c in CONTRACT["questionnaire"] if c not in ("merchant_id", "answered_at")]
    assert questionnaire[items].min().min() >= 1
    assert questionnaire[items].max().max() <= 5
    done = tables["merchants"].loc[tables["merchants"]["questionnaire_done"], "merchant_id"]
    assert set(questionnaire["merchant_id"]) == set(done)


def test_only_consenting_merchants_have_a_valid_consent(tables):
    consents = tables["consents"]
    valid = set(consents.loc[consents["revoked_at"].isna(), "merchant_id"])
    merchants = tables["merchants"]
    consenting = set(merchants.loc[merchants["consent_data_use"], "merchant_id"])
    assert valid == consenting


# --- files and the adapter ---------------------------------------------------------


def test_generate_writes_files_the_adapter_can_read(tmp_path):
    config = small_config(600)
    paths = generate(config, out_dir=tmp_path, strength=0.5)
    assert set(paths) == set(CONTRACT)
    assert (tmp_path / META_FILE).exists()

    adapter = ShopUpSyntheticAdapter(config, folder=tmp_path)
    loaded = adapter.load_all()
    in_memory, _, _ = build_tables(config, 0.5)
    for name in CONTRACT:
        assert len(loaded[name]) == len(in_memory[name]), name
    assert loaded["merchants"]["consent_data_use"].dtype == bool
    assert loaded["loans"]["outcome_label"].isna().any()
    assert set(loaded["loans"]["outcome_label"].dropna().unique()) == {0, 1}

    audit = adapter.audit_frame()
    assert list(audit.columns) == ["merchant_id", "town_tier", "shop_type", "has_trade_license"]


def test_the_adapter_never_exposes_the_hidden_truth(tmp_path):
    """Reliability is known only to the generator and its tests."""
    config = small_config(300)
    generate(config, out_dir=tmp_path, strength=0.5)
    assert (tmp_path / LATENT_FILE).exists()
    adapter = ShopUpSyntheticAdapter(config, folder=tmp_path)
    for frame in [*adapter.load_all().values(), adapter.audit_frame()]:
        assert "reliability" not in frame.columns
        assert "thin_file" not in frame.columns


def test_the_adapter_says_how_to_create_missing_data(tmp_path):
    adapter = ShopUpSyntheticAdapter(small_config(300), folder=tmp_path / "nothing_here")
    with pytest.raises(FileNotFoundError, match="python tasks.py data"):
        adapter.load_merchants()


# --- seasonality ---------------------------------------------------------------------


def test_seasonality_has_twelve_months_averaging_one():
    purchases = load_config()["generator"]["purchases"]
    index = monthly_index(purchases["seasonality_file"], strength=1.0)
    assert sorted(index) == list(range(1, 13))
    assert np.mean(list(index.values())) == pytest.approx(1.0)
    assert index[7] < 1.0, "July is below trend in both source years"


def test_seasonality_strength_zero_means_no_seasonality():
    purchases = load_config()["generator"]["purchases"]
    index = monthly_index(purchases["seasonality_file"], strength=0.0)
    assert all(value == pytest.approx(1.0) for value in index.values())


# --- the planted-bias switch for the fairness audit ----------------------------------


def repaid_share_by_tier(config: dict) -> pd.Series:
    built, _, _ = build_tables(config, 0.5)
    loans = built["loans"].dropna(subset=["outcome_label"]).merge(
        built["merchants"][["merchant_id", "town_tier"]], on="merchant_id"
    )
    return loans.groupby("town_tier")["outcome_label"].apply(lambda s: s.astype(int).mean())


def test_by_default_repayment_does_not_depend_on_town_tier():
    share = repaid_share_by_tier(small_config())
    assert share.max() - share.min() < 0.04


def test_inject_group_bias_plants_a_gap_against_small_towns():
    """The switch exists so the fairness audit can be shown to catch a gap that is there."""
    biased = small_config()
    biased["generator"]["inject_group_bias"] = 1.5
    share = repaid_share_by_tier(biased)
    assert share["small_town"] < share["metro"] - 0.08
    assert share["small_town"] < share["city"] - 0.08


def test_every_consent_covers_the_questionnaire(tables):
    """So an officer can collect answers from a merchant who has not answered yet."""
    categories = tables["consents"]["data_categories"]
    assert categories.str.split("|").apply(lambda parts: "questionnaire" in parts).all()

