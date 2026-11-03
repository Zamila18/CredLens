"""How the saved model behaves at the score lines the dashboard uses, on the validation months.

Purpose: add what the training report does not show: a confusion matrix and threshold
    numbers at each configured line, and how many merchants appear in more than one period
    of the time split. Nothing is trained, refitted or saved over: the saved model is only
    read, and its predictions are made for the validation months.
Owner role: B (model).
Implements: implementation pack, Phase 9.1.

The test months are not looked at: only the merchant ids of the test period are read (for
the overlap count); no test prediction or label is used, so `test_set_use.json` is unchanged.

"Flagged" means the line puts the loan forward for a closer look; the event the numbers are
about is "not repaid within the rule" (label 0). A line is a reading aid for an officer,
never a decision: the dashboard has no code path that approves or declines.

Run: python -m src.model.operating_points  (writes reports/<mode>/operating_points.json)
"""

from __future__ import annotations

import argparse
import json
from typing import Any

import numpy as np
import pandas as pd

from src.adapters import get_adapter
from src.config import PROJECT_ROOT, load_config
from src.model.dataset import build_dataset, modelling_rows
from src.model.score import NEEDS_MORE_INFO, band_lines, score_table
from src.model.split import split_for_mode
from src.model.train import load_model, predict_probability


def confusion(flagged: np.ndarray, not_repaid: np.ndarray) -> dict[str, Any]:
    """Counts and rates for one line. `not_repaid` is the event; `flagged` is the line's call."""
    flagged = np.asarray(flagged, dtype=bool)
    not_repaid = np.asarray(not_repaid, dtype=bool)
    tp = int((flagged & not_repaid).sum())
    fp = int((flagged & ~not_repaid).sum())
    fn = int((~flagged & not_repaid).sum())
    tn = int((~flagged & ~not_repaid).sum())

    def share(a: int, b: int) -> float | None:
        return a / b if b else None

    return {
        "flagged_not_repaid": tp,
        "flagged_repaid": fp,
        "not_flagged_not_repaid": fn,
        "not_flagged_repaid": tn,
        "share_flagged": share(tp + fp, tp + fp + fn + tn),
        "precision": share(tp, tp + fp),
        "recall": share(tp, tp + fn),
        "specificity": share(tn, tn + fp),
    }


def merchant_overlap(train: pd.DataFrame, validation: pd.DataFrame, test: pd.DataFrame) -> dict:
    """How many merchants have loans in more than one period (by merchant id only).

    With a time split this is expected and is not leakage by itself: a repeat borrower's
    later loan is scored from history before that loan's cutoff (tests/test_leakage.py),
    and its label is about that loan only.
    """
    parts = {
        "train": set(train["merchant_id"]),
        "validation": set(validation["merchant_id"]),
        "test": set(test["merchant_id"]),
    }
    in_train_val = parts["train"] & parts["validation"]
    return {
        "merchants": {name: len(ids) for name, ids in parts.items()},
        "train_and_validation": len(in_train_val),
        "train_and_test": len(parts["train"] & parts["test"]),
        "validation_and_test": len(parts["validation"] & parts["test"]),
        "validation_loans_whose_merchant_had_a_training_loan": int(
            validation["merchant_id"].isin(parts["train"]).sum()
        ),
        "validation_loans": int(len(validation)),
    }


def operating_points(config: dict[str, Any]) -> dict[str, Any]:
    """The report: confusion matrices at the configured lines, and the merchant overlap."""
    mode = config["data"]["mode"]
    saved = load_model(mode)
    dataset = build_dataset(get_adapter(config).load_all(), config, mode=mode)
    split = split_for_mode(modelling_rows(dataset), config, mode)
    validation = split.validation
    probabilities = predict_probability(saved, validation)
    table = score_table(probabilities, validation, config, mode)
    not_repaid = validation["label"].to_numpy() == 0
    lines = band_lines(config, mode)
    strong, warn = lines["band_strong_min_score"], lines["low_score_warning_below"]
    return {
        "data_mode": mode,
        "model_version": saved.get("version_id"),
        "measured_on": "validation months only (the test months are not used)",
        "event": "not repaid within the rule (label 0)",
        "lines": lines,
        "at_each_line": {
            f"score_below_{warn}_low_score_warning": confusion(
                table["score"].to_numpy() < warn, not_repaid
            ),
            f"score_below_{strong}_not_strong": confusion(
                table["score"].to_numpy() < strong, not_repaid
            ),
            "band_is_not_strong": confusion(
                (table["band"] != "Strong").to_numpy(), not_repaid
            ),
            "band_is_needs_more_info": confusion(
                (table["band"] == NEEDS_MORE_INFO).to_numpy(), not_repaid
            ),
        },
        "merchant_overlap": merchant_overlap(split.train, validation, split.test),
        "note": "Synthetic data: an engineering check of the code, not evidence of how the "
        "model would do on real Bangladesh retailers.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args(argv)
    config = load_config()
    report = operating_points(config)
    path = PROJECT_ROOT / "reports" / config["data"]["mode"] / "operating_points.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for name, numbers in report["at_each_line"].items():
        print(
            f"{name}: flagged {numbers['share_flagged']:.1%}, precision "
            f"{numbers['precision']:.3f}, recall {numbers['recall']:.3f}"
        )
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
