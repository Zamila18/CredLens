"""Tests for the operating-point report (src/model/operating_points.py). No model needed."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.model.operating_points import confusion, merchant_overlap


def test_the_confusion_counts_follow_the_flag_and_the_event():
    flagged = np.array([True, True, False, False, True])
    not_repaid = np.array([True, False, True, False, False])
    result = confusion(flagged, not_repaid)
    assert (result["flagged_not_repaid"], result["flagged_repaid"]) == (1, 2)
    assert (result["not_flagged_not_repaid"], result["not_flagged_repaid"]) == (1, 1)
    assert result["precision"] == 1 / 3 and result["recall"] == 0.5
    assert result["specificity"] == 1 / 3 and result["share_flagged"] == 3 / 5


def test_an_empty_side_gives_no_rate_instead_of_a_division_error():
    result = confusion(np.array([False, False]), np.array([False, False]))
    assert result["precision"] is None and result["recall"] is None
    assert result["specificity"] == 1.0


def test_merchant_overlap_counts_shared_merchants_per_pair_of_periods():
    train = pd.DataFrame({"merchant_id": ["a", "b", "c"]})
    validation = pd.DataFrame({"merchant_id": ["b", "c", "c", "d"]})
    test = pd.DataFrame({"merchant_id": ["c", "e"]})
    result = merchant_overlap(train, validation, test)
    assert result["merchants"] == {"train": 3, "validation": 3, "test": 2}
    assert result["train_and_validation"] == 2
    assert result["train_and_test"] == 1 and result["validation_and_test"] == 1
    assert result["validation_loans_whose_merchant_had_a_training_loan"] == 3
