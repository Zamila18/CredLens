"""Tests for the scoring service the API calls.

Owner role: C (ML engineer).
Implements: PROJECT_BRIEF section 8 (review queue and score endpoints): features are
    built once, a merchant is scored on their latest loan, and nothing is scored without
    a valid consent.
"""

from __future__ import annotations

import copy

import pandas as pd
import pytest

from src.api.schemas import MerchantQueueItem, ScoreResponse
from src.config import load_config
from src.model import scoring
from src.model.dataset import build_dataset
from src.model.explain import ConsentRequired
from src.model.scoring import QUEUE_COLUMNS, Scorer, UnknownMerchant
from src.model.train import train_models
from src.synth.generate import build_tables


@pytest.fixture(scope="module")
def config() -> dict:
    small = copy.deepcopy(load_config())
    small["data"]["n_merchants"] = 2000
    small["model"]["bootstrap_resamples"] = 50
    small["model"]["candidates"] = ["logistic_regression"]
    small["score"]["reasons_report_sample"] = 20
    return small


@pytest.fixture(scope="module")
def tables(config) -> dict:
    return build_tables(config, 0.5)[0]


@pytest.fixture(scope="module")
def saved(tables, config) -> dict:
    result = train_models(build_dataset(tables, config), config)
    return {
        "model": result["model"],
        "calibrator": result["calibrator"],
        "features": result["features"],
        "version_id": "test-version",
    }


@pytest.fixture(scope="module")
def scorer(config, tables, saved) -> Scorer:
    return Scorer(config, tables=tables, saved=saved)


@pytest.fixture(scope="module")
def queue(scorer) -> pd.DataFrame:
    return scorer.queue()


def test_the_feature_table_is_built_once_and_reused(config, tables, saved, monkeypatch):
    """Looking up cards and the queue must not rebuild features: that takes half a minute."""
    builds = []
    real = scoring.build_dataset
    monkeypatch.setattr(scoring, "build_dataset", lambda *a, **k: builds.append(1) or real(*a, **k))
    scorer = Scorer(config, tables=tables, saved=saved)
    queue = scorer.queue()
    for merchant_id in queue.loc[queue["consent_valid"], "merchant_id"].head(5):
        scorer.card(merchant_id)
    scorer.queue()
    assert len(builds) == 1


def test_the_queue_lists_each_pending_merchant_once(queue, scorer, tables):
    assert list(queue.columns) == QUEUE_COLUMNS
    assert queue["merchant_id"].is_unique
    assert len(queue) > 50
    assert set(queue["merchant_id"]) <= set(tables["merchants"]["merchant_id"])
    assert list(queue["pending_since"]) == sorted(queue["pending_since"]), "oldest first"
    for merchant_id in queue["merchant_id"].head(20):
        assert scorer.feature_row(merchant_id)["label_status"] != "labelled"


def test_a_merchant_is_scored_on_their_latest_loan(scorer, tables):
    loans = tables["loans"]
    several = loans["merchant_id"].value_counts()
    merchant_id = several[several >= 2].index[0]
    latest = loans[loans["merchant_id"] == merchant_id].sort_values("issued_at").iloc[-1]
    assert scorer.feature_row(merchant_id)["loan_id"] == latest["loan_id"]


def test_no_consent_means_no_score_in_the_queue_or_on_the_card(queue, scorer):
    refused = queue[~queue["consent_valid"]]
    assert len(refused) > 0, "the sample must contain a pending merchant without consent"
    for column in ("score", "coverage", "band", "low_score_warning"):
        assert refused[column].isna().all(), column
    with pytest.raises(ConsentRequired):
        scorer.card(refused["merchant_id"].iloc[0])
    allowed = queue[queue["consent_valid"]]
    assert allowed["score"].notna().all() and allowed["band"].notna().all()


def test_the_card_and_the_queue_agree(queue, scorer):
    for _, row in queue[queue["consent_valid"]].head(40).iterrows():
        card = scorer.card(row["merchant_id"])
        assert card["score"] == row["score"]
        assert card["band"] == row["band"]
        assert card["coverage"] == pytest.approx(row["coverage"])
        assert card["low_score_warning"] == row["low_score_warning"]


def test_cards_and_queue_rows_fit_the_api_contract(queue, scorer, tables):
    merchants = tables["merchants"].set_index("merchant_id")
    for _, row in queue.head(30).iterrows():
        details = merchants.loc[row["merchant_id"]]
        item = MerchantQueueItem.model_validate(
            {
                "merchant_id": row["merchant_id"],
                "onboarded_at": str(details["onboarded_at"]),
                "status": "pending",
                "pending_since": row["pending_since"],
                "score": None if pd.isna(row["score"]) else int(row["score"]),
                "coverage": None if pd.isna(row["coverage"]) else float(row["coverage"]),
                "band": None if pd.isna(row["band"]) else row["band"],
                "consent_valid": bool(row["consent_valid"]),
            }
        )
        assert item.consent_valid or item.score is None
    merchant_id = queue.loc[queue["consent_valid"], "merchant_id"].iloc[0]
    card = scorer.card(merchant_id)
    banner = card.pop("banner")
    response = ScoreResponse.model_validate(card)
    assert response.merchant_id == merchant_id
    assert response.model_version == "test-version"
    assert "Decision support only" in banner


def test_an_unknown_merchant_gives_a_clear_error(scorer):
    with pytest.raises(UnknownMerchant, match="No loan found"):
        scorer.card("M-DOES-NOT-EXIST")


def test_scoring_changes_nothing_in_the_data(scorer, tables):
    """No code path here may touch a loan: scoring is reading only."""
    before = {name: frame.copy() for name, frame in tables.items()}
    queue = scorer.queue()
    scorer.card(queue.loc[queue["consent_valid"], "merchant_id"].iloc[0])
    for name, frame in tables.items():
        pd.testing.assert_frame_equal(frame, before[name])
    words = " ".join(str(value) for value in queue["band"].dropna().unique()).lower()
    assert not any(word in words for word in ("approve", "decline", "reject"))
