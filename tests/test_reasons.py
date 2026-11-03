"""Tests for the reasons behind a score.

Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 8 and docs/FEATURE_DICTIONARY.md (three reasons up
    and three down, dictionary sentences in English and Bangla, parts that sum to the
    score, no reason for missing data, sentences that are true for the merchant).
"""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

from src.api.schemas import ScoreResponse
from src.config import banner_text, load_config
from src.features.build_features import DELIVERY_FEATURES, PAYMENT_FEATURES, model_feature_names
from src.features.dictionary import (
    detail_text,
    expected_directions,
    load_dictionary,
    reason_sentences,
    statement_holds,
)
from src.model.dataset import build_dataset
from src.model.explain import (
    ConsentRequired,
    average_inputs,
    calibrated_probability,
    contributions_for_row,
    explain_score,
    reasons_summary,
    score_card,
)
from src.model.score import band_for, score_table
from src.model.train import train_models
from src.synth.generate import build_tables

SAMPLE = 120  # loans explained in the tests that sweep over many merchants


@pytest.fixture(scope="module")
def config() -> dict:
    small = copy.deepcopy(load_config())
    small["data"]["n_merchants"] = 3000
    small["model"]["bootstrap_resamples"] = 50
    small["score"]["reasons_report_sample"] = 40
    return small


@pytest.fixture(scope="module")
def result(config) -> dict:
    tables, _, _ = build_tables(config, 1.0)
    return train_models(build_dataset(tables, config), config)


def as_saved(candidate: dict, version: str) -> dict:
    return {
        "model": candidate["model"],
        "calibrator": candidate["calibration"]["calibrator"],
        "features": candidate["features"],
        "version_id": version,
    }


@pytest.fixture(scope="module", params=["logistic_regression", "lightgbm"])
def saved(request, result) -> dict:
    """Every rule below must hold for both kinds of model."""
    return as_saved(result["candidates"][request.param], f"test-{request.param}")


@pytest.fixture(scope="module")
def loans(result) -> pd.DataFrame:
    return result["split"].validation.sample(n=SAMPLE, random_state=3)


@pytest.fixture(scope="module")
def explanations(saved, loans, config) -> list[tuple[pd.Series, dict]]:
    dictionary = load_dictionary()
    return [(row, explain_score(saved, row, config, dictionary)) for _, row in loans.iterrows()]


# --- the parts add up -------------------------------------------------------------------


def test_reasons_sum_to_the_score(explanations):
    """Baseline, top reasons and all other inputs add up to the score shown."""
    for _, explanation in explanations:
        reasons = explanation["reasons_positive"] + explanation["reasons_negative"]
        on_screen = (
            explanation["baseline_score"]
            + sum(reason["contribution"] for reason in reasons)
            + explanation["other_contribution"]
        )
        assert on_screen == pytest.approx(explanation["score"], abs=1e-9)


def test_all_contributions_sum_to_the_exact_score(saved, loans, config):
    """Before any rounding: baseline + every input's points = 100 x probability."""
    probabilities = calibrated_probability(saved, loans)
    for (_, row), probability in zip(loans.iterrows(), probabilities):
        parts = contributions_for_row(saved, row, config)
        assert parts["exact_score"] == pytest.approx(100 * probability, abs=1e-9)
        total = parts["baseline_score"] + sum(parts["points"].values())
        assert total == pytest.approx(parts["exact_score"], abs=1e-9)


def test_contributions_equal_the_shap_library_values(saved, loans, config):
    """Our numbers are SHAP values: the SHAP library's exact explainer gives the same."""
    import shap

    features = saved["features"]
    rows = loans.head(20)
    prepare = saved["model"][:-1]  # the clip and fill steps
    nobody = pd.DataFrame([[np.nan] * len(features)], columns=features)
    average_merchant = prepare.transform(nobody)

    def probability(prepared_inputs: np.ndarray) -> np.ndarray:
        raw = saved["model"][-1].predict_proba(prepared_inputs)[:, 1]
        return saved["calibrator"].predict(raw)

    explainer = shap.Explainer(probability, average_merchant, algorithm="exact")
    from_library = 100 * explainer(prepare.transform(rows[features])).values
    ours = np.array(
        [
            [contributions_for_row(saved, row, config)["points"][name] for name in features]
            for _, row in rows.iterrows()
        ]
    )
    np.testing.assert_allclose(ours, from_library, atol=1e-8)


def test_the_baseline_is_the_score_of_the_average_merchant(saved, config):
    """Someone with no data at all is the average merchant: baseline score, no reasons."""
    nobody = pd.Series(np.nan, index=saved["features"])
    explanation = explain_score(saved, nobody, config)
    assert explanation["reasons_positive"] == [] and explanation["reasons_negative"] == []
    assert all(points == 0 for points in explanation["points"].values())
    average = pd.DataFrame([average_inputs(saved)])
    same_score = 100 * calibrated_probability(saved, average)[0]
    assert explanation["exact_baseline_score"] == pytest.approx(same_score)


# --- what is shown ----------------------------------------------------------------------


def test_three_reasons_up_and_three_down(explanations, config):
    """A score comes with at most the top 3 reasons that raise it and the top 3 that lower it."""
    wanted = config["score"]["top_reasons_each_side"]
    for _, explanation in explanations:
        positive = [reason["contribution"] for reason in explanation["reasons_positive"]]
        negative = [reason["contribution"] for reason in explanation["reasons_negative"]]
        assert len(positive) <= wanted and len(negative) <= wanted
        assert all(points > 0 for points in positive)
        assert all(points < 0 for points in negative)
        assert positive == sorted(positive, reverse=True), "largest first"
        assert negative == sorted(negative), "largest first"
    assert any(len(e["reasons_positive"]) == wanted for _, e in explanations)


def test_the_largest_contribution_is_always_among_the_reasons(explanations, config):
    """Nothing big is hidden in "all other inputs": the top mover each way is shown."""
    smallest = config["score"]["min_reason_points"]
    for _, explanation in explanations:
        for side, sign in (("positive", 1), ("negative", -1)):
            movers = {n: sign * p for n, p in explanation["points"].items() if sign * p >= smallest}
            shown = [reason["contribution"] for reason in explanation[f"reasons_{side}"]]
            if movers:
                assert shown, "an input moved the score, so there is a reason"
                assert sign * shown[0] == pytest.approx(round(max(movers.values()), 2))
            wanted = min(len(movers), config["score"]["top_reasons_each_side"])
            assert len(shown) == wanted


def test_every_reason_maps_to_a_dictionary_sentence(explanations):
    """Each reason is a dictionary sentence in English and Bangla, never a feature name."""
    dictionary = load_dictionary()["features"]
    names = set(model_feature_names("ABC"))
    for _, explanation in explanations:
        for side in ("positive", "negative"):
            for reason in explanation[f"reasons_{side}"]:
                assert reason["code"] in names
                entry = dictionary[reason["code"]]
                allowed = [entry[side], (entry.get("otherwise") or {}).get(side)]
                shown = {"en": reason["sentence_en"], "bn": reason["sentence_bn"]}
                assert shown in allowed
                for text in (reason["sentence_en"], reason["sentence_bn"], reason["detail"]):
                    assert not any(name in text for name in names), "no raw feature names"


def test_missing_features_produce_no_reason(saved, loans, config):
    """A feature the merchant does not have never appears as a reason, and adds no points."""
    for group in (PAYMENT_FEATURES, DELIVERY_FEATURES):
        row = loans.iloc[0].copy()
        row[group] = np.nan
        explanation = explain_score(saved, row, config)
        reasons = explanation["reasons_positive"] + explanation["reasons_negative"]
        assert not {reason["code"] for reason in reasons} & set(group)
        # An input the model dropped has no entry at all, which is also "no points".
        assert all(explanation["points"].get(name, 0) == 0 for name in group)


def test_first_loan_merchants_get_no_payment_reasons(explanations):
    seen = 0
    for row, explanation in explanations:
        if pd.isna(row["avg_pay_delay_days"]):
            seen += 1
            assert all(explanation["points"].get(name, 0) == 0 for name in PAYMENT_FEATURES)
    assert seen > 0, "the sample must contain first loans"


# --- reasons never contradict the facts -------------------------------------------------


def test_a_better_than_average_value_never_lowers_the_score(saved, explanations):
    directions = expected_directions(load_dictionary())
    averages = average_inputs(saved)
    for row, explanation in explanations:
        for name, points in explanation["points"].items():
            if pd.isna(row[name]):
                continue
            better = (row[name] - averages[name]) * directions[name]
            if better > 0:
                assert points >= -1e-9, name
            elif better < 0:
                assert points <= 1e-9, name


def test_sentences_shown_are_true_for_the_merchant(explanations):
    """A plain claim is shown only when it holds; otherwise the comparing sentence is used."""
    dictionary = load_dictionary()["features"]
    plain, comparing = 0, 0
    for row, explanation in explanations:
        for side, raised in (("positive", True), ("negative", False)):
            for reason in explanation[f"reasons_{side}"]:
                entry = dictionary[reason["code"]]
                value = row[reason["code"]]
                if reason["sentence_en"] == entry[side]["en"]:
                    plain += 1
                    assert statement_holds(entry, raised, value), reason["sentence_en"]
                else:
                    comparing += 1
                    assert not statement_holds(entry, raised, value)
                    assert "than at similar shops" in reason["sentence_en"]
    assert plain > 50 and comparing > 0


def test_the_plain_claims_mean_what_they_say():
    """None late means none; growing means above zero; close to the limit means over 80%."""
    features = load_dictionary()["features"]
    late = features["late_pay_count_90d"]
    assert reason_sentences(late, True, 0) == late["positive"]
    assert reason_sentences(late, False, 2) == late["negative"]
    growth = features["basket_growth"]
    assert reason_sentences(growth, False, -5) == growth["negative"]
    assert reason_sentences(growth, False, 40) == growth["otherwise"]["negative"]
    assert "more slowly" in growth["otherwise"]["negative"]["en"]
    credit = features["credit_utilisation"]
    assert reason_sentences(credit, False, 0.9) == credit["negative"]
    assert reason_sentences(credit, False, 0.6) == credit["otherwise"]["negative"]
    delay = features["avg_pay_delay_days"]
    assert reason_sentences(delay, True, 2) == delay["positive"]
    assert reason_sentences(delay, True, 6) == delay["otherwise"]["positive"]
    returns = features["return_rate_90d"]
    assert reason_sentences(returns, False, 0.2) == returns["negative"], "already a comparison"
    assert reason_sentences({"positive": None, "negative": None}, True, 1) is None


def test_every_comparing_sentence_exists_in_both_languages():
    for name, entry in load_dictionary()["features"].items():
        for side, sentences in (entry.get("otherwise") or {}).items():
            assert side in ("positive", "negative"), name
            assert sentences["en"].strip() and sentences["bn"].strip(), name
            assert "similar shops" in sentences["en"], name


def test_delivery_reasons_stay_neutral_observations():
    """A delivery sentence that lowers the score names conditions, not blame."""
    dictionary = load_dictionary()["features"]
    for name in ("return_rate_90d", "failed_rate_90d"):
        assert "may reflect" in dictionary[name]["negative"]["en"]
    for name in model_feature_names("ABC"):
        for side in ("positive", "negative"):
            text = dictionary[name][side]["en"].lower()
            blaming = ("fraud", "dishonest", "bad merchant", "because")
            assert not any(word in text for word in blaming)


def test_statement_holds_reads_the_conditions():
    entry = {"shown_when": {"positive": {"at_most": 0}, "negative": {"at_least": 1}}}
    assert statement_holds(entry, True, 0) and not statement_holds(entry, True, 0.2)
    assert statement_holds(entry, False, 1) and not statement_holds(entry, False, 0)
    both = {"shown_when": {"positive": {"above": 0, "below": 10}}}
    assert statement_holds(both, True, 5) and not statement_holds(both, True, 10)
    assert statement_holds({}, True, -99), "no condition: a comparison with similar shops"
    assert statement_holds(both, False, -99), "no condition for that side"


def test_detail_text_shows_the_value_beside_the_average():
    dictionary = load_dictionary()["features"]
    assert detail_text(dictionary["return_rate_90d"], 0.075, 0.07) == (
        "Returns 7.5% vs average 7.0%"
    )
    assert detail_text(dictionary["basket_growth"], -20.4, 150.0) == (
        "Purchase growth -20% vs average +150%"
    )
    assert "4.0 days" in detail_text(dictionary["avg_pay_delay_days"], 4, 8.6)
    assert "24 hours" in detail_text(dictionary["dispatch_to_delivery_hours"], 24.2, 25)
    assert detail_text(dictionary["late_pay_count_90d"], 1, 0.25) == (
        "Late payments in 90 days 1 vs average 0.2"
    )
    assert detail_text({"positive": None}, 1, 2) is None


def test_every_model_input_has_a_detail_format():
    dictionary = load_dictionary()["features"]
    for name in model_feature_names("ABC"):
        assert detail_text(dictionary[name], 0.5, 0.4), name


# --- the card an officer sees -----------------------------------------------------------


def test_score_card_matches_the_api_contract(saved, loans, config):
    for _, row in loans.head(25).iterrows():
        card = score_card(saved, row, config, "synthetic_bd")
        banner = card.pop("banner")
        response = ScoreResponse.model_validate({"merchant_id": row["merchant_id"], **card})
        assert response.score == round(100 * response.probability)
        assert response.band == band_for(response.score, response.coverage, config)
        assert response.model_version == saved["version_id"]
        assert banner == banner_text("synthetic_bd") and "Decision support only" in banner
        assert 0 < response.probability < 1, "never a bare 0 or 1"


def test_no_valid_consent_means_no_score(saved, loans, config):
    """The rule of the whole project: without consent nothing is computed."""
    row = loans.iloc[0].copy()
    row["consent_valid"] = False
    with pytest.raises(ConsentRequired, match="no valid consent"):
        score_card(saved, row, config, "synthetic_bd")
    with pytest.raises(ConsentRequired):
        score_card(saved, loans.iloc[0], config, "synthetic_bd", consent_valid=False)
    unknown = loans.iloc[0].drop("consent_valid")
    with pytest.raises(ConsentRequired):
        score_card(saved, unknown, config, "synthetic_bd")
    assert score_card(saved, unknown, config, "synthetic_bd", consent_valid=True)["score"] >= 0


def test_the_card_shows_the_same_score_as_the_review_queue(saved, loans, config):
    """The queue (many loans at once) and the card (one loan) must never disagree."""
    queue = score_table(calibrated_probability(saved, loans), loans, config, "synthetic_bd")
    for index, row in loans.iterrows():
        card = score_card(saved, row, config, "synthetic_bd")
        assert card["score"] == queue.loc[index, "score"]
        assert card["band"] == queue.loc[index, "band"]
        assert card["probability"] == pytest.approx(queue.loc[index, "probability"], abs=1e-12)


def test_a_card_never_carries_a_decision(saved, loans, config):
    card = score_card(saved, loans.iloc[0], config, "synthetic_bd")
    text = str(card).lower()
    assert not any(word in text for word in ("approve", "decline", "reject"))
    assert "decision" not in {key.lower() for key in card}


def test_explaining_twice_gives_the_same_reasons(saved, loans, config):
    row = loans.iloc[5]
    assert explain_score(saved, row, config) == explain_score(saved, row, config)


def test_too_many_inputs_are_refused_with_a_clear_message(saved, loans, config):
    tight = copy.deepcopy(config)
    tight["score"]["max_inputs_for_exact_reasons"] = 2
    full_row = loans.dropna(subset=saved["features"]).iloc[0]
    with pytest.raises(ValueError, match="max_inputs_for_exact_reasons"):
        explain_score(saved, full_row, tight)


def test_training_report_checks_the_reasons(result, config):
    check = result["report"]["reasons_check"]
    assert check["loans_checked"] == config["score"]["reasons_report_sample"]
    assert check["largest_gap"] < 1e-6
    assert check["times_each_input_was_a_top_reason"]
    assert set(check["size_of_all_other_inputs"]) == {"median", "nine_in_ten_below", "largest"}


def test_reasons_summary_counts_both_sides(saved, loans, config):
    summary = reasons_summary(saved, loans, config)
    for counts in summary["times_each_input_was_a_top_reason"].values():
        assert set(counts) == {"positive", "negative"}
    assert summary["loans_with_no_reason"] < summary["loans_checked"]


# --- the plain-language summary --------------------------------------------------------------


def test_every_card_carries_a_summary_in_both_languages(saved, loans, config):
    from src.model.explain import BAND_BN

    for _, row in loans.head(30).iterrows():
        card = score_card(saved, row, config, "synthetic_bd")
        english, bangla = card["summary_en"], card["summary_bn"]
        assert english.startswith(f"Score {card['score']} ({card['band']})")
        assert BAND_BN[card["band"]] in bangla
        assert english.endswith("the decision is yours.")
        assert bangla.endswith("সিদ্ধান্ত আপনার।")
        if card["reasons_positive"]:
            assert card["reasons_positive"][0]["sentence_en"] in english
            assert card["reasons_positive"][0]["sentence_bn"] in bangla
        if card["reasons_negative"]:
            assert card["reasons_negative"][0]["sentence_en"] in english
        assert ("The score is low" in english) == card["low_score_warning"]


def test_the_summary_follows_the_band(config):
    from src.model.explain import plain_summary

    def card(band, score, low=False):
        return {
            "score": score, "band": band, "coverage": 0.7, "low_score_warning": low,
            "reasons_positive": [], "reasons_negative": [],
        }  # fmt: skip

    strong = plain_summary(card("Strong", 93), config, "synthetic_bd")
    assert "at least 9 in 10" in strong["summary_en"]
    assert "১০টি ঋণের মধ্যে অন্তত 9টি" in strong["summary_bn"]
    waiting = plain_summary(card("Needs more info", 95), config, "synthetic_bd")
    assert "too little information" in waiting["summary_en"]
    low = plain_summary(card("Review", 60, low=True), config, "synthetic_bd")
    assert "fewer than 7 in 10" in low["summary_en"]
    assert "No single piece of information stood out" in low["summary_en"]


def test_the_summary_never_recommends_lending_or_not(saved, loans, config):
    words = ("approve", "decline", "reject", "eligible", "grant", "should lend", "recommend")
    for _, row in loans.head(30).iterrows():
        text = score_card(saved, row, config, "synthetic_bd")["summary_en"].lower()
        assert not any(word in text for word in words)



# --- stability (implementation pack, Phase 9.2) -------------------------------------------


def test_a_tiny_change_in_one_input_barely_moves_any_points(saved, loans, config):
    """Explanations are stable: nudging one present input by a hair (relative 1e-9) moves
    every input's points by less than 0.01 and flips the side of no reason that matters."""
    for _, row in loans.head(15).iterrows():
        before = contributions_for_row(saved, row, config)["points"]
        present = [name for name in saved["features"] if not pd.isna(row[name])]
        for name in present[:3]:
            nudged = row.copy()
            nudged[name] = row[name] * (1 + 1e-9) + 1e-12
            after = contributions_for_row(saved, nudged, config)["points"]
            for feature, points in before.items():
                assert after[feature] == pytest.approx(points, abs=0.01), (name, feature)
                if abs(points) > 0.05:
                    assert np.sign(after[feature]) == np.sign(points), (name, feature)


def test_the_order_of_the_inputs_does_not_change_the_explanation(saved, loans, config):
    """The same values given in another column order explain to the same points."""
    row = loans.iloc[7]
    shuffled = row[list(reversed(row.index))]
    assert contributions_for_row(saved, shuffled, config) == contributions_for_row(
        saved, row, config
    )
