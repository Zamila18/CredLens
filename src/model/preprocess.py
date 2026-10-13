"""Steps that prepare the model inputs. Everything here is fitted on the training period only.

Purpose: small, explainable preparation steps shared by the models.
Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 5 and PROJECT_BRIEF section 18, item 23.

Two rules these steps protect:
- No look ahead: limits and averages are learned from the training loans and then applied
  unchanged to validation, test and new loans.
- Missing is neutral: an empty value is replaced by the training average and the model is
  given no "this was missing" signal. A merchant without delivery data, or without
  earlier loans, therefore gets the average contribution for those inputs, never a
  penalty. Missing data lowers coverage, not the score.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin


class QuantileClipper(BaseEstimator, TransformerMixin):
    """Pull extreme values in to limits learned from the training data.

    A few merchants have wild values (for example purchase growth of several thousand
    percent when they bought almost nothing the quarter before). Left alone, such values
    dominate a linear model. Each column is clipped to the given lower and upper
    quantile of the training loans. Empty values stay empty.
    """

    def __init__(self, lower: float = 0.01, upper: float = 0.99) -> None:
        self.lower = lower
        self.upper = upper

    def fit(self, X, y=None) -> QuantileClipper:
        """Learn the limits of every column from the training loans."""
        values = np.asarray(pd.DataFrame(X), dtype=float)
        self.feature_names_in_ = np.array(list(pd.DataFrame(X).columns), dtype=object)
        with np.errstate(all="ignore"):
            self.lower_limits_ = np.nanquantile(values, self.lower, axis=0)
            self.upper_limits_ = np.nanquantile(values, self.upper, axis=0)
        return self

    def transform(self, X) -> np.ndarray:
        """Clip every column to the limits learned in `fit`."""
        values = np.asarray(pd.DataFrame(X), dtype=float)
        return np.clip(values, self.lower_limits_, self.upper_limits_)

    def get_feature_names_out(self, input_features=None) -> np.ndarray:
        """Column names are unchanged."""
        return self.feature_names_in_ if input_features is None else np.asarray(input_features)
