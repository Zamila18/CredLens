"""Scores for the API: build the feature table once, then answer quickly.

Purpose: the one place the API asks for a review queue or a merchant's score card.
Owner role: C (ML engineer). The API (role D) calls it and never rebuilds features itself.
Implements: PROJECT_BRIEF section 8 (review queue and score endpoints) and section 18,
    item 18 (loans issued in the last 61 days have no outcome yet: they are the pending
    cases of the review queue).

Why this exists. Building the feature table reads every purchase, parcel and payment and
takes about half a minute for 20,000 merchants. Doing that for each request would make
every page wait. A `Scorer` does it once, when the API starts, and keeps the result.

What is scored. Features are computed per loan, as of the day the loan was issued. A
merchant's score card uses their most recent loan. The review queue lists the merchants
whose most recent loan has no outcome yet.

Rules kept here so that no endpoint can forget them:
- No valid consent, no score. In the queue such a merchant has no score, coverage or
  band; asking for the card raises `ConsentRequired`.
- A band is a reading aid. Nothing here approves or declines anything, and nothing here
  changes a loan.

Command line, to look at one card:
    python -m src.model.scoring              (the first merchant of the queue)
    python -m src.model.scoring M0000123     (a merchant id)
"""

from __future__ import annotations

import json
import sys
from typing import Any

import pandas as pd

from src.adapters import get_adapter
from src.config import load_config
from src.model.dataset import build_dataset
from src.model.explain import calibrated_probability, refuse_hidden_rows, score_card
from src.model.labels import LABELLED
from src.model.score import score_table
from src.model.train import load_model

QUEUE_COLUMNS = [
    "merchant_id",
    "loan_id",
    "pending_since",
    "consent_valid",
    "score",
    "coverage",
    "band",
    "low_score_warning",
]


class UnknownMerchant(KeyError):
    """Raised when a merchant id has no loan in the active data mode."""


class Scorer:
    """Holds the feature table and the saved model of one data mode.

    Create one when the API starts and reuse it for every request. To pick up new data
    or a newly trained model, create a new one.

    Args:
        config: the validated config.
        mode: the data mode; defaults to the one in the config.
        tables: the data-contract tables; read through the adapter when not given.
        saved: a saved model (`load_model`); loaded from disk when not given.
    """

    def __init__(
        self,
        config: dict[str, Any],
        mode: str | None = None,
        tables: dict[str, pd.DataFrame] | None = None,
        saved: dict[str, Any] | None = None,
    ) -> None:
        self.config = config
        self.mode = mode or config["data"]["mode"]
        self.saved = saved if saved is not None else load_model(self.mode)
        tables = tables if tables is not None else get_adapter(config).load_all()
        dataset = build_dataset(tables, config)
        # The most recent loan of every merchant; ties broken by loan id so it is stable.
        ordered = dataset.sort_values(["cutoff_date", "loan_id"])
        self._latest = ordered.groupby("merchant_id", sort=False).tail(1).set_index("merchant_id")
        self.model_version = self.saved["version_id"]

    def merchant_ids(self) -> list[str]:
        """Every merchant that can be looked up (has at least one loan)."""
        return list(self._latest.index)

    def feature_row(self, merchant_id: str) -> pd.Series:
        """The feature row a merchant is scored on: their most recent loan."""
        if merchant_id not in self._latest.index:
            raise UnknownMerchant(f"No loan found for merchant {merchant_id!r} in '{self.mode}'.")
        return self._latest.loc[merchant_id]

    def card(self, merchant_id: str) -> dict[str, Any]:
        """The score card of one merchant: score, coverage, band, reasons, banner.

        Has every field of `ScoreResponse` (src/api/schemas.py). Raises `ConsentRequired`
        when the merchant has no valid consent, and `UnknownMerchant` for an unknown id.
        """
        row = self.feature_row(merchant_id)
        card = score_card(self.saved, row, self.config, self.mode)
        return {"merchant_id": merchant_id, **card}

    def queue(self) -> pd.DataFrame:
        """The review queue: one row per merchant whose latest loan has no outcome yet.

        Columns: merchant_id, loan_id, pending_since (the day the loan was issued),
        consent_valid, score, coverage, band, low_score_warning. Oldest first. A merchant
        without valid consent is listed with no score, coverage or band. Whether an
        decided is not known here; the API adds that from the
        decisions table.

        A data mode whose rows may never be shown (Home Credit) raises `RowsNotShown`.
        A public data mode has no pending loans (every outcome is known), so its queue is
        empty.
        """
        refuse_hidden_rows(self.config, self.mode)
        pending = self._latest[self._latest["label_status"] != LABELLED]
        issued = pd.to_datetime(pending["cutoff_date"]).dt.strftime("%Y-%m-%d")
        queue = pd.DataFrame(
            {
                "merchant_id": pending.index,
                "loan_id": pending["loan_id"].to_numpy(),
                "pending_since": issued.to_numpy(),
                "consent_valid": pending["consent_valid"].astype(bool).to_numpy(),
            }
        )
        for column in ("score", "coverage", "band", "low_score_warning"):
            queue[column] = None
        allowed = pending[pending["consent_valid"]]
        if len(allowed):
            probabilities = calibrated_probability(self.saved, allowed)
            scored = score_table(probabilities, allowed, self.config, self.mode)
            consenting = queue["consent_valid"].to_numpy()
            for column in ("score", "coverage", "band", "low_score_warning"):
                queue.loc[consenting, column] = scored[column].to_numpy()
        queue = queue.sort_values(["pending_since", "merchant_id"]).reset_index(drop=True)
        return queue[QUEUE_COLUMNS]


def main(argv: list[str] | None = None) -> int:
    """Print one score card as JSON (Bangla included, so the output is forced to UTF-8)."""
    arguments = sys.argv[1:] if argv is None else argv
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    scorer = Scorer(load_config())
    if arguments:
        merchant_id = arguments[0]
    else:
        queue = scorer.queue()
        merchant_id = queue.loc[queue["consent_valid"], "merchant_id"].iloc[0]
    print(json.dumps(scorer.card(merchant_id), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
