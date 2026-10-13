"""Put features, labels and consent together: the rows a model may learn from.

Purpose: one place that decides which loans may be used for training and testing.
Owner role: C (ML engineer).
Implements: PROJECT_BRIEF section 2 (privacy by design: no valid consent, no scoring),
    docs/MODEL_SPEC.md sections 2 and 3.

A loan is used for modelling only if both are true:
- it has a known outcome (see src/model/labels.py), and
- its merchant has a valid consent today: a consent record that is not revoked and not
  expired. A merchant who never agreed, or who withdrew, is not scored, and their data
  does not train the model either.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.features.build_features import build_features
from src.model.labels import LABELLED, build_labels, latest_date


def merchants_with_valid_consent(consents: pd.DataFrame, as_of: pd.Timestamp | str) -> set[str]:
    """Merchants with a consent that is granted, not revoked and not expired on `as_of`."""
    as_of = pd.Timestamp(as_of).normalize()
    granted = pd.to_datetime(consents["granted_at"]) <= as_of
    not_expired = pd.to_datetime(consents["expires_at"]) > as_of
    revoked_at = pd.to_datetime(consents["revoked_at"])
    not_revoked = revoked_at.isna() | (revoked_at > as_of)
    return set(consents.loc[granted & not_expired & not_revoked, "merchant_id"])


def build_dataset(
    tables: dict[str, pd.DataFrame], config: dict[str, Any], as_of: pd.Timestamp | str | None = None
) -> pd.DataFrame:
    """One row per loan: features, label, label status and whether consent is valid.

    Every loan is kept, including pending ones and those without consent, so the caller
    can count what was left out. Use `modelling_rows` for the rows a model may use.
    """
    as_of = pd.Timestamp(as_of) if as_of is not None else latest_date(tables)
    features = build_features(tables, config)
    labels = build_labels(tables["loans"], tables["payments"], config, as_of)
    dataset = features.merge(
        labels[["loan_id", "label", "label_status", "label_source"]],
        on="loan_id",
        how="left",
        validate="one_to_one",
    )
    consenting = merchants_with_valid_consent(tables["consents"], as_of)
    dataset["consent_valid"] = dataset["merchant_id"].isin(consenting)
    return dataset


def modelling_rows(dataset: pd.DataFrame) -> pd.DataFrame:
    """The loans a model may be trained or tested on: known outcome and valid consent."""
    usable = dataset[(dataset["label_status"] == LABELLED) & dataset["consent_valid"]].copy()
    usable["label"] = usable["label"].astype(int)
    return usable


def dataset_summary(dataset: pd.DataFrame) -> dict[str, int]:
    """How many loans there are, and how many were left out of modelling and why."""
    labelled = dataset["label_status"] == LABELLED
    return {
        "loans": int(len(dataset)),
        "used_for_modelling": int((labelled & dataset["consent_valid"]).sum()),
        "left_out_no_outcome_yet": int((~labelled).sum()),
        "left_out_no_valid_consent": int((labelled & ~dataset["consent_valid"]).sum()),
    }
