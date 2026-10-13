"""Synthetic data generator for the `synthetic_bd` data mode.

Purpose: build the seven contract tables (merchants, purchases, deliveries, payments,
    loans, questionnaire, consents) for ShopUp-shaped synthetic merchants.
Owner role: B (data engineer).
Implements: docs/GENERATOR_SPEC.md and PROJECT_BRIEF section 5. Every number comes from
    the `generator`, `data` and `labels` sections of config/default.yaml.

The core idea (docs/GENERATOR_SPEC.md): each merchant has one hidden "reliability"
number. The system never sees it. Purchases, payments, deliveries and the loan outcome
are noisy reflections of it.

The negative control: `delivery_signal_strength` (0, 0.5 or 1) decides how much the
delivery data reflects reliability. At 0 the delivery data is pure noise, so a model
must gain nothing from it. Changing the strength changes only the deliveries table;
all other tables stay identical.

Run it:
    python tasks.py data                      (strength from the config)
    python -m src.synth.generate --strength 0
    python -m src.synth.generate --all-strengths

Nothing here is real data. The output goes to data/raw/synthetic_bd/ (gitignored).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.adapters.base import CONTRACT, check_frame
from src.config import load_config
from src.synth.paths import LATENT_FILE, META_FILE, output_dir
from src.synth.seasonality import monthly_index

ALL_STRENGTHS = (0.0, 0.5, 1.0)
RETURN_REASONS_MERCHANT = ("refused", "wrong_item", "other")
RETURN_REASON_SHARES_MERCHANT = (0.5, 0.3, 0.2)
RETURN_REASONS_LOGISTICS = ("address_issue", "rider_issue")
DAYS_PER_MONTH = 30.44


def sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    """The logistic function: turns any number into a probability between 0 and 1."""
    return 1.0 / (1.0 + np.exp(-x))


# --- helpers -------------------------------------------------------------------------


def _ids(prefix: str, count: int, width: int) -> np.ndarray:
    """Text ids such as M000001, M000002, ..."""
    numbers = pd.Series(np.arange(1, count + 1)).astype(str).str.zfill(width)
    return (prefix + numbers).to_numpy()


def _dates(start: np.datetime64, day_offsets: np.ndarray) -> np.ndarray:
    """ISO date text (YYYY-MM-DD) for day offsets from the window start."""
    return (start + day_offsets.astype("timedelta64[D]")).astype("datetime64[D]").astype(str)


def _choose(rng: np.random.Generator, shares: dict[str, float], size: int) -> np.ndarray:
    """Pick labels at random according to their shares."""
    labels = list(shares)
    weights = np.array([shares[label] for label in labels], dtype=float)
    return rng.choice(labels, size=size, p=weights / weights.sum())


def _window(config: dict[str, Any]) -> tuple[np.datetime64, int, int]:
    """Return the first day, the total length in days, and the length of the main window.

    The main window is `data.months` long: merchants are onboarded in it, and loans
    issued in it are old enough to have an outcome. After it comes a short tail
    (`generator.observation_tail_days`) in which activity continues. Loans issued in
    the tail are too young to judge: they are the pending cases an officer would review.
    """
    start = pd.Timestamp(config["generator"]["start_date"])
    main_end = start + pd.DateOffset(months=config["data"]["months"])
    main_days = int((main_end - start).days)
    tail_days = config["generator"]["observation_tail_days"]
    labels = config["labels"]
    judgeable_after = (
        config["generator"]["loans"]["term_days"] + labels["good_if_days_late_at_most"] + 1
    )
    needed = max(labels["min_loan_age_days"], judgeable_after)
    if tail_days < needed:
        raise ValueError(
            f"generator.observation_tail_days must be at least {needed}: the loan term plus "
            "the allowed days late plus one, and no less than labels.min_loan_age_days. "
            "Otherwise a loan issued on the last day of the main window could not be judged."
        )
    return np.datetime64(start.date(), "D"), main_days + tail_days, main_days


def _expand_weekly_counts(
    rng: np.random.Generator, counts: np.ndarray, onboard_day: np.ndarray, n_days: int
) -> tuple[np.ndarray, np.ndarray]:
    """Turn a merchants-by-weeks table of counts into one row per event.

    Returns the merchant position and the day offset of every event. Each event gets
    a random day inside its week, never before onboarding and never after the window.
    """
    n_weeks = counts.shape[1]
    flat = np.repeat(np.arange(counts.size), counts.ravel())
    merchant = flat // n_weeks
    week_start = (flat % n_weeks) * 7
    first_day = np.maximum(week_start, onboard_day[merchant])
    last_day = np.minimum(week_start + 6, n_days - 1)
    day = first_day + np.floor(rng.random(flat.size) * (last_day - first_day + 1)).astype(int)
    return merchant, day


def _weekly_exposure(onboard_day: np.ndarray, n_days: int) -> tuple[np.ndarray, np.ndarray]:
    """For every merchant and week: share of the week the merchant was active, and
    days since onboarding at the middle of the week (0 before onboarding)."""
    n_weeks = int(np.ceil(n_days / 7))
    week_start = np.arange(n_weeks) * 7
    week_end = np.minimum(week_start + 6, n_days - 1)
    active_from = np.maximum(week_start[None, :], onboard_day[:, None])
    active_days = np.clip(week_end[None, :] - active_from + 1, 0, 7)
    days_since = np.clip(week_start[None, :] + 3 - onboard_day[:, None], 0, None)
    return active_days / 7.0, days_since.astype(float)


# --- tables --------------------------------------------------------------------------


def _make_merchants(
    rng: np.random.Generator, config: dict[str, Any], start: np.datetime64, main_days: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Merchants (the master table) plus the hidden facts only the generator knows."""
    data, gen = config["data"], config["generator"]
    count = data["n_merchants"]

    reliability = rng.standard_normal(count)
    onboard_day = rng.integers(0, main_days, size=count)
    town_tier = _choose(rng, gen["town_tier_shares"], count)
    shop_type = _choose(rng, gen["shop_type_shares"], count)

    district = np.empty(count, dtype=object)
    licence_rate = np.empty(count)
    for tier, names in gen["districts"].items():
        in_tier = town_tier == tier
        district[in_tier] = rng.choice(names, size=int(in_tier.sum()))
        licence_rate[in_tier] = gen["trade_license_rate"][tier]

    trend = rng.normal(
        gen["purchases"]["trend_per_month_per_reliability"] * reliability,
        gen["purchases"]["trend_per_month_sd"],
    )

    merchants = pd.DataFrame(
        {
            "merchant_id": _ids("M", count, 6),
            "onboarded_at": _dates(start, onboard_day),
            "district": district,
            "town_tier": town_tier,
            "shop_type": shop_type,
            "has_trade_license": rng.random(count) < licence_rate,
            "consent_data_use": rng.random(count) < data["consent_rate"],
            "questionnaire_done": rng.random(count) < data["questionnaire_rate"],
        }
    )
    latent = pd.DataFrame(
        {
            "merchant_id": merchants["merchant_id"],
            "reliability": reliability,
            "onboard_day": onboard_day,
            "thin_file": rng.random(count) < data["thin_file_share"],
            "has_delivery_data": rng.random(count) >= data["no_delivery_data_share"],
            "purchase_trend_per_month": trend,
        }
    )
    return merchants, latent


def _make_purchases(
    rng: np.random.Generator,
    config: dict[str, Any],
    merchants: pd.DataFrame,
    latent: pd.DataFrame,
    start: np.datetime64,
    n_days: int,
) -> pd.DataFrame:
    """Mokam-style wholesale purchases: what the merchant buys. Never sales."""
    gen = config["generator"]
    p = gen["purchases"]
    count = len(merchants)
    reliability = latent["reliability"].to_numpy()
    onboard_day = latent["onboard_day"].to_numpy()
    tier = merchants["town_tier"].to_numpy()
    shop = merchants["shop_type"].to_numpy()

    exposure, days_since = _weekly_exposure(onboard_day, n_days)
    n_weeks = exposure.shape[1]

    # Seasonality: one multiplier per week, from the real Bangladesh monthly shape.
    season_by_month = monthly_index(p["seasonality_file"], p["seasonality_strength"])
    week_middle = start + (np.arange(n_weeks) * 7 + 3).astype("timedelta64[D]")
    week_month = pd.DatetimeIndex(week_middle).month
    season = np.array([season_by_month[m] for m in week_month])

    tier_effect = np.array([p["tier_effect"][t] for t in tier])
    log_rate = (
        np.log(p["base_weekly_rate"])
        + tier_effect[:, None]
        + p["reliability_effect"] * reliability[:, None]
        + latent["purchase_trend_per_month"].to_numpy()[:, None] * days_since / DAYS_PER_MONTH
        + np.log(season)[None, :]
        + rng.normal(0.0, p["weekly_noise_sd"], size=(count, n_weeks))
    )

    # Thin-file merchants start slowly and reach their normal rate after a ramp.
    ramp = np.clip(days_since / p["thin_file_ramp_days"], 0.0, 1.0)
    low = p["thin_file_rate_multiplier"]
    thin_multiplier = np.where(latent["thin_file"].to_numpy()[:, None], low + (1 - low) * ramp, 1)

    counts = rng.poisson(np.exp(log_rate) * thin_multiplier * exposure)
    merchant, day = _expand_weekly_counts(rng, counts, onboard_day, n_days)
    n_rows = merchant.size

    # Amount depends on the shop type, a little on reliability, and on chance.
    median = np.array([p["amount_median_bdt"][s] for s in shop])
    amount = np.exp(
        np.log(median[merchant])
        + p["amount_reliability_effect"] * reliability[merchant]
        + p["amount_sigma"] * rng.standard_normal(n_rows)
    )
    amount = np.maximum(np.round(amount, -1), 100.0)

    # Category: each merchant buys from its own subset of the shop type's categories.
    category = np.empty(n_rows, dtype=object)
    pick = rng.random(n_rows)
    for shop_type, names in gen["categories"].items():
        in_type = np.flatnonzero(shop == shop_type)
        if in_type.size == 0:
            continue
        order = np.argsort(rng.random((in_type.size, len(names))), axis=1)
        n_used = rng.integers(1, len(names) + 1, size=in_type.size)
        position = np.full(count, -1)
        position[in_type] = np.arange(in_type.size)
        rows = np.flatnonzero(position[merchant] >= 0)
        local = position[merchant[rows]]
        chosen = order[local, np.floor(pick[rows] * n_used[local]).astype(int)]
        category[rows] = np.array(names, dtype=object)[chosen]

    # Supplier: reliable merchants return to their main suppliers more often.
    main = rng.integers(0, p["n_suppliers"], size=(count, p["main_suppliers_per_merchant"]))
    stays = rng.random(n_rows) < sigmoid(
        p["supplier_repeat_intercept"] + p["supplier_repeat_effect"] * reliability[merchant]
    )
    which_main = rng.integers(0, p["main_suppliers_per_merchant"], size=n_rows)
    supplier = np.where(
        stays, main[merchant, which_main], rng.integers(0, p["n_suppliers"], size=n_rows)
    )

    order_rows = np.lexsort((day, merchant))
    purchases = pd.DataFrame(
        {
            "purchase_id": _ids("PU", n_rows, 8),
            "merchant_id": merchants["merchant_id"].to_numpy()[merchant[order_rows]],
            "purchase_date": _dates(start, day[order_rows]),
            "amount_bdt": amount[order_rows],
            "category": category[order_rows],
            "supplier_id": ("S" + pd.Series(supplier[order_rows] + 1).astype(str).str.zfill(4)),
        }
    )
    return purchases


def _make_deliveries(
    rng: np.random.Generator,
    config: dict[str, Any],
    merchants: pd.DataFrame,
    latent: pd.DataFrame,
    start: np.datetime64,
    n_days: int,
    strength: float,
) -> pd.DataFrame:
    """REDX-style outgoing parcels. `strength` sets how much they reflect reliability."""
    d = config["generator"]["deliveries"]
    logistics_share = config["data"]["logistics_noise_share"]
    count = len(merchants)
    reliability = latent["reliability"].to_numpy()
    onboard_day = latent["onboard_day"].to_numpy()
    sells_online = latent["has_delivery_data"].to_numpy()

    volume_noise = rng.standard_normal(count)
    return_noise = rng.normal(0.0, d["merchant_noise_sd"], count)
    failed_noise = rng.normal(0.0, d["merchant_noise_sd"], count)
    remit_noise = rng.normal(0.0, d["merchant_noise_sd"], count)

    exposure, _ = _weekly_exposure(onboard_day, n_days)
    log_volume = (
        np.log(d["base_weekly_parcels"])
        + strength * d["volume_signal_effect"] * reliability
        + d["volume_merchant_sd"] * volume_noise
    )
    weekly_mean = np.exp(log_volume)[:, None] * exposure * sells_online[:, None]
    counts = rng.poisson(weekly_mean)
    merchant, day = _expand_weekly_counts(rng, counts, onboard_day, n_days)
    n_rows = merchant.size

    outcome_draw = rng.random(n_rows)
    cancel_draw = rng.random(n_rows)
    logistics_kind = rng.random(n_rows)
    logistics_reason = rng.choice(RETURN_REASONS_LOGISTICS, size=n_rows)
    merchant_reason = rng.choice(
        RETURN_REASONS_MERCHANT, size=n_rows, p=RETURN_REASON_SHARES_MERCHANT
    )
    hours_noise = rng.standard_normal(n_rows)
    second_of_day = rng.integers(8 * 3600, 20 * 3600, size=n_rows)
    is_cod = rng.random(n_rows) < d["cod_share"]
    remit_draw = rng.random(n_rows)

    r = reliability[merchant]
    base_return = sigmoid(d["return_intercept"])
    base_failed = sigmoid(d["failed_intercept"])

    # Logistics events (address or rider problems) never depend on the merchant.
    p_logistics = logistics_share * (base_return + base_failed)
    # Merchant-attributable events depend on reliability only through `strength`.
    p_return = (1 - logistics_share) * sigmoid(
        d["return_intercept"] - strength * d["return_signal_effect"] * r + return_noise[merchant]
    )
    p_failed = (1 - logistics_share) * sigmoid(
        d["failed_intercept"] - strength * d["failed_signal_effect"] * r + failed_noise[merchant]
    )

    status = np.full(n_rows, "delivered", dtype=object)
    reason = np.full(n_rows, None, dtype=object)

    is_logistics = outcome_draw < p_logistics
    logistics_return = is_logistics & (logistics_kind < base_return / (base_return + base_failed))
    status[logistics_return] = "returned"
    status[is_logistics & ~logistics_return] = "failed"
    reason[is_logistics] = logistics_reason[is_logistics]

    is_return = ~is_logistics & (outcome_draw < p_logistics + p_return)
    status[is_return] = "returned"
    reason[is_return] = merchant_reason[is_return]

    is_failed = ~is_logistics & ~is_return & (outcome_draw < p_logistics + p_return + p_failed)
    status[is_failed] = "failed"
    reason[is_failed] = "other"

    is_cancelled = cancel_draw < d["cancelled_rate"]
    status[is_cancelled] = "cancelled"
    reason[is_cancelled] = None

    delivered = status == "delivered"
    hours = np.exp(
        d["hours_log_mean"] - strength * d["hours_signal_effect"] * r
        + d["hours_log_sigma"] * hours_noise
    )
    dispatched = (
        start.astype("datetime64[s]")
        + (day * 86400 + second_of_day).astype("timedelta64[s]")
    )
    window_end = start.astype("datetime64[s]") + np.timedelta64(n_days * 86400 - 1, "s")
    arrived = np.minimum(dispatched + (hours * 3600).astype("timedelta64[s]"), window_end)

    remitted = remit_draw < sigmoid(
        d["cod_remit_intercept"] + strength * d["cod_remit_signal_effect"] * r
        + remit_noise[merchant]
    )
    cod_on_time = np.full(n_rows, None, dtype=object)
    has_remit = delivered & is_cod
    cod_on_time[has_remit] = remitted[has_remit]

    delivered_at = np.full(n_rows, None, dtype=object)
    delivered_at[delivered] = np.datetime_as_string(arrived[delivered], unit="s")

    order_rows = np.lexsort((dispatched, merchant))
    deliveries = pd.DataFrame(
        {
            "delivery_id": _ids("D", n_rows, 8),
            "merchant_id": merchants["merchant_id"].to_numpy()[merchant[order_rows]],
            "dispatched_at": np.datetime_as_string(dispatched[order_rows], unit="s"),
            "delivered_at": delivered_at[order_rows],
            "status": status[order_rows],
            "return_reason": reason[order_rows],
            "is_cod": is_cod[order_rows],
            "cod_remitted_on_time": cod_on_time[order_rows],
        }
    )
    return deliveries


def _solve_outcome_intercept(score_without_intercept: np.ndarray, target: float) -> float:
    """Find the intercept that makes the average repayment probability hit the target."""
    low, high = -10.0, 10.0
    for _ in range(60):
        middle = (low + high) / 2
        if sigmoid(score_without_intercept + middle).mean() < target:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def _make_loans_and_payments(
    rng: np.random.Generator,
    config: dict[str, Any],
    merchants: pd.DataFrame,
    latent: pd.DataFrame,
    start: np.datetime64,
    n_days: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    """Baki-style loans, each with one repayment, and the outcome label."""
    lo = config["generator"]["loans"]
    labels = config["labels"]
    good_limit = labels["good_if_days_late_at_most"]
    count = len(merchants)
    last_day = n_days - 1
    reliability = latent["reliability"].to_numpy()
    onboard_day = latent["onboard_day"].to_numpy()
    tier = merchants["town_tier"].to_numpy()

    wanted_loans = rng.integers(1, lo["max_loans"] + 1, size=count)
    limit_median = np.array([lo["limit_median_bdt"][t] for t in tier])
    small_town = tier == "small_town"

    # Pass 1: lay out every candidate loan and its pre-intercept outcome score.
    issue = onboard_day + lo["min_days_after_onboarding"] + np.round(
        rng.exponential(lo["first_loan_delay_mean_days"], count)
    ).astype(int)
    candidates = []
    for loan_number in range(lo["max_loans"]):
        gap = np.round(rng.exponential(lo["gap_between_loans_mean_days"], count)).astype(int)
        candidates.append(
            {
                "loan_number": loan_number,
                "issue": issue.copy(),
                "noise": rng.standard_normal(count),
                "outcome_draw": rng.random(count),
                "late_draw": rng.gamma(lo["late_days_shape"], 1.0 / lo["late_days_shape"], count),
                "bad_extra": rng.gamma(2.0, lo["bad_extra_days_mean"] / 2.0, count),
                "never_paid_draw": rng.random(count),
                "limit_noise": rng.standard_normal(count),
                "utilisation_noise": rng.standard_normal(count),
            }
        )
        issue = issue + lo["term_days"] + np.maximum(gap, 7)

    def score_of(candidate: dict[str, Any]) -> np.ndarray:
        return (
            lo["outcome_reliability_effect"] * reliability
            + lo["outcome_noise_sd"] * candidate["noise"]
            - config["generator"]["inject_group_bias"] * small_town
        )

    in_window = [
        (c["issue"] <= last_day) & (wanted_loans > c["loan_number"]) for c in candidates
    ]
    pooled = np.concatenate([score_of(c)[keep] for c, keep in zip(candidates, in_window)])
    intercept = _solve_outcome_intercept(pooled, config["generator"]["repayment_share_target"])

    # Pass 2: decide outcomes loan by loan. A merchant who never repaid gets no new loan,
    # and the next loan cannot start before the previous one was paid.
    can_borrow = np.ones(count, dtype=bool)
    earliest_next = np.zeros(count, dtype=int)
    rows = []
    for candidate, keep in zip(candidates, in_window):
        issue = np.maximum(candidate["issue"], earliest_next)
        active = keep & can_borrow & (issue <= last_day)

        good = candidate["outcome_draw"] < sigmoid(score_of(candidate) + intercept)
        mean_late = np.exp(
            lo["late_days_log_mean"] - lo["late_days_reliability_effect"] * reliability
        )
        late_if_good = np.clip(np.round(candidate["late_draw"] * mean_late), 0, good_limit)
        late_if_bad = good_limit + 1 + np.round(candidate["bad_extra"])
        never_paid = ~good & (candidate["never_paid_draw"] < lo["bad_never_paid_share"])
        days_late = np.where(good, late_if_good, late_if_bad).astype(int)

        due = issue + lo["term_days"]
        paid_day = due + days_late
        is_paid = ~never_paid & (paid_day <= last_day)

        limit = limit_median * (1 + lo["limit_growth_per_loan"] * candidate["loan_number"])
        limit = limit * np.exp(lo["limit_sigma"] * candidate["limit_noise"])
        limit = np.maximum(np.round(limit, -3), 5000)
        mean_used = sigmoid(lo["utilisation_intercept"] - lo["utilisation_effect"] * reliability)
        spread = 2.0 / np.sqrt(lo["utilisation_concentration"])
        used = sigmoid(
            np.log(mean_used / (1 - mean_used)) + spread * candidate["utilisation_noise"]
        )
        amount_due = np.maximum(np.round(limit * used, -2), 500)

        rows.append(
            pd.DataFrame(
                {
                    "position": np.flatnonzero(active),
                    "issue": issue[active],
                    "due": due[active],
                    "paid_day": np.where(is_paid, paid_day, -1)[active],
                    "good": good[active],
                    "limit": limit[active],
                    "amount_due": amount_due[active],
                }
            )
        )
        can_borrow = can_borrow & ~(active & never_paid)
        earliest_next = np.where(active, np.maximum(earliest_next, paid_day + 7), earliest_next)

    all_loans = pd.concat(rows, ignore_index=True).sort_values(["position", "issue"])
    all_loans = all_loans.reset_index(drop=True)
    n_loans = len(all_loans)
    merchant_id = merchants["merchant_id"].to_numpy()[all_loans["position"].to_numpy()]
    issue_day = all_loans["issue"].to_numpy()
    due_day = all_loans["due"].to_numpy()
    paid_day = all_loans["paid_day"].to_numpy()
    good = all_loans["good"].to_numpy()

    # A loan has a label only when its outcome can be known today (docs/MODEL_SPEC.md
    # section 2): it is old enough, and it was either repaid in time or is by now more
    # than the allowed days past due. This is the same rule as src/model/labels.py.
    old_enough = (last_day - issue_day) >= labels["min_loan_age_days"]
    observed = old_enough & (good | ((last_day - due_day) > good_limit))
    label = np.full(n_loans, None, dtype=object)
    label[observed] = good[observed].astype(int)
    observed_at = np.full(n_loans, None, dtype=object)
    observed_at[observed] = _dates(start, (due_day + good_limit)[observed])

    loan_ids = _ids("L", n_loans, 7)
    loans = pd.DataFrame(
        {
            "loan_id": loan_ids,
            "merchant_id": merchant_id,
            "issued_at": _dates(start, issue_day),
            "limit_bdt": all_loans["limit"].to_numpy(),
            "outcome_label": label,
            "label_observed_at": observed_at,
        }
    )

    paid = paid_day >= 0
    paid_date = np.full(n_loans, None, dtype=object)
    paid_date[paid] = _dates(start, paid_day[paid])
    payments = pd.DataFrame(
        {
            "payment_id": _ids("P", n_loans, 7),
            "merchant_id": merchant_id,
            "loan_id": loan_ids,
            "due_date": _dates(start, due_day),
            "paid_date": paid_date,
            "amount_due_bdt": all_loans["amount_due"].to_numpy(),
            "amount_paid_bdt": np.where(paid, all_loans["amount_due"].to_numpy(), 0.0),
        }
    )
    facts = {
        "outcome_intercept": float(intercept),
        "repaid_share_observed": float(good[observed].mean()) if observed.any() else float("nan"),
        "loans_observed": int(observed.sum()),
        "loans_too_young": int((~observed).sum()),
    }
    return loans, payments, facts


def _make_questionnaire(
    rng: np.random.Generator,
    config: dict[str, Any],
    merchants: pd.DataFrame,
    latent: pd.DataFrame,
    start: np.datetime64,
    n_days: int,
) -> pd.DataFrame:
    """FinHealth-style answers (1 to 5). Shown beside the score, never inside the model."""
    q = config["generator"]["questionnaire"]
    answered = merchants["questionnaire_done"].to_numpy()
    reliability = latent["reliability"].to_numpy()[answered]
    onboard_day = latent["onboard_day"].to_numpy()[answered]
    items = [c for c in CONTRACT["questionnaire"] if c not in ("merchant_id", "answered_at")]

    answers = {}
    for item in items:
        raw = q["item_mean"] + q["reliability_effect"] * reliability
        raw = raw + rng.normal(0.0, q["item_noise_sd"], reliability.size)
        value = np.clip(np.round(raw), 1, 5).astype(int)
        # Stress is reverse-coded: a reliable merchant reports low stress.
        answers[item] = 6 - value if item == "stress" else value

    answered_day = np.minimum(
        onboard_day + rng.integers(0, q["answered_within_days"] + 1, size=reliability.size),
        n_days - 1,
    )
    frame = pd.DataFrame({"merchant_id": merchants["merchant_id"].to_numpy()[answered], **answers})
    frame["answered_at"] = _dates(start, answered_day)
    return frame[CONTRACT["questionnaire"]]


def _make_consents(
    rng: np.random.Generator,
    config: dict[str, Any],
    merchants: pd.DataFrame,
    latent: pd.DataFrame,
    start: np.datetime64,
    n_days: int,
) -> pd.DataFrame:
    """Platform consent records. No valid record means no scoring."""
    c = config["generator"]["consent"]
    count = len(merchants)
    consenting = merchants["consent_data_use"].to_numpy()
    onboard_day = latent["onboard_day"].to_numpy()

    # Non-consenting merchants either withdrew a consent or never gave one.
    withdrew = ~consenting & (rng.random(count) < c["revoked_share_of_non_consenting"])
    has_record = consenting | withdrew
    revoked_day = np.minimum(onboard_day + rng.integers(1, 91, size=count), n_days - 1)

    granted = pd.to_datetime(_dates(start, onboard_day[has_record]))
    expires = (granted + pd.DateOffset(years=c["valid_years"])).strftime("%Y-%m-%d")
    revoked_at = np.full(count, None, dtype=object)
    revoked_at[withdrew] = _dates(start, revoked_day[withdrew])

    answered = merchants["questionnaire_done"].to_numpy()[has_record]
    categories = np.where(
        answered, "purchases|deliveries|payments|questionnaire", "purchases|deliveries|payments"
    )
    return pd.DataFrame(
        {
            "consent_id": _ids("C", int(has_record.sum()), 6),
            "merchant_id": merchants["merchant_id"].to_numpy()[has_record],
            "purpose": "credit_readiness_assessment",
            "data_categories": categories,
            "granted_at": granted.strftime("%Y-%m-%d"),
            "expires_at": expires,
            "revoked_at": revoked_at[has_record],
        }
    )


# --- public entry points -------------------------------------------------------------


def build_tables(
    config: dict[str, Any], strength: float | None = None
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, dict[str, Any]]:
    """Build every table in memory.

    Returns (contract tables, hidden-truth table, facts about this run). The same seed
    always gives the same result. Changing `strength` changes only the deliveries.
    """
    if strength is None:
        strength = config["data"]["delivery_signal_strength"]
    strength = float(strength)
    start, n_days, main_days = _window(config)

    # One independent random stream per table, so tables do not disturb each other.
    streams = np.random.SeedSequence(config["seed"]).spawn(6)
    rng_merchants, rng_purchases, rng_deliveries, rng_loans, rng_questions, rng_consents = (
        np.random.default_rng(stream) for stream in streams
    )

    merchants, latent = _make_merchants(rng_merchants, config, start, main_days)
    loans, payments, loan_facts = _make_loans_and_payments(
        rng_loans, config, merchants, latent, start, n_days
    )
    tables = {
        "merchants": merchants,
        "purchases": _make_purchases(rng_purchases, config, merchants, latent, start, n_days),
        "deliveries": _make_deliveries(
            rng_deliveries, config, merchants, latent, start, n_days, strength
        ),
        "payments": payments,
        "loans": loans,
        "questionnaire": _make_questionnaire(
            rng_questions, config, merchants, latent, start, n_days
        ),
        "consents": _make_consents(rng_consents, config, merchants, latent, start, n_days),
    }
    tables = {name: check_frame(name, frame) for name, frame in tables.items()}

    window_end = str(start + np.timedelta64(n_days - 1, "D"))
    facts = {
        "data_mode": "synthetic_bd",
        "note": "Synthetic data. Not real merchants. Decision support only.",
        "seed": config["seed"],
        "delivery_signal_strength": strength,
        "window_start": str(start),
        "main_window_end": str(start + np.timedelta64(main_days - 1, "D")),
        "window_end": window_end,
        "rows": {name: int(len(frame)) for name, frame in tables.items()},
        **loan_facts,
    }
    return tables, latent.drop(columns=["onboard_day"]), facts


def generate(
    config: dict[str, Any], out_dir: Path | None = None, strength: float | None = None
) -> dict[str, Path]:
    """Generate every contract table as CSV and return the file paths. Same seed, same data."""
    tables, latent, facts = build_tables(config, strength)
    folder = Path(out_dir) if out_dir is not None else output_dir(config, strength)
    folder.mkdir(parents=True, exist_ok=True)

    paths = {}
    for name, frame in tables.items():
        paths[name] = folder / f"{name}.csv"
        frame.to_csv(paths[name], index=False, lineterminator="\n")
    latent.to_csv(folder / LATENT_FILE, index=False, lineterminator="\n")
    (folder / META_FILE).write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8")
    return paths


def main(argv: list[str] | None = None) -> int:
    """Command line: generate the synthetic tables for one or all signal strengths."""
    parser = argparse.ArgumentParser(description="Generate the synthetic_bd tables.")
    parser.add_argument("--strength", type=float, choices=ALL_STRENGTHS, default=None)
    parser.add_argument("--all-strengths", action="store_true")
    args = parser.parse_args(argv)

    config = load_config()
    strengths = ALL_STRENGTHS if args.all_strengths else (args.strength,)
    for strength in strengths:
        paths = generate(config, strength=strength)
        folder = next(iter(paths.values())).parent
        facts = json.loads((folder / META_FILE).read_text(encoding="utf-8"))
        print(f"Synthetic data written to {folder}")
        print(f"  signal strength: {facts['delivery_signal_strength']}, seed: {facts['seed']}")
        for name, rows in facts["rows"].items():
            print(f"  {name:<14}{rows:>10,}")
        print(f"  repaid share (observed loans): {facts['repaid_share_observed']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
