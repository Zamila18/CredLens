"""The second model: gradient-boosted trees (LightGBM), kept on a short leash.

Purpose: a more flexible model to compare with the logistic regression. It can pick up
    bends and combinations a straight-line model cannot.
Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 5. Settings: `model.lightgbm` in
    config/default.yaml.

Three rules keep it as honest as the simple model:

1. Every input may only push the probability the way its meaning says (`higher_is` in
   the feature dictionary). LightGBM calls this a monotone constraint. Paying later can
   never raise the probability, so a reason can never contradict the facts.

2. Missing data stays neutral. LightGBM can treat "missing" as a signal of its own, which
   would let a merchant with no delivery data be scored down for having none. So missing
   values are first replaced with the training average, as for the logistic regression.
   Because of rule 1 the trees cannot single that average out: it is always scored
   between a slightly worse and a slightly better merchant.

3. It is tuned without looking at the validation period. The last months of the TRAINING
   period are held back as a "tuning part": each setting is fitted on the earlier
   training months and stopped when the tuning part stops improving. The winning setting
   is then fitted on the whole training period. The validation period stays clean for
   calibration and for the comparison with the logistic regression.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from lightgbm import LGBMClassifier, early_stopping, log_evaluation
from sklearn.impute import SimpleImputer
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from src.model.preprocess import QuantileClipper
from src.model.split import TIME_SPLIT

DATE_COLUMN = "cutoff_date"


def make_lightgbm(
    config: dict[str, Any],
    features: list[str],
    directions: dict[str, int],
    setting: dict[str, Any],
    trees: int,
) -> Pipeline:
    """Clip, fill missing with the training average, then boosted trees with fixed directions.

    Args:
        features: the input names, in the order the model will receive them.
        directions: +1 (higher is better) or -1 (higher is worse) for every input.
        setting: one entry of `model.lightgbm.grid`.
        trees: how many trees to grow.
    """
    settings = config["model"]["lightgbm"]
    lower, upper = settings["clip_quantiles"]
    booster = LGBMClassifier(
        n_estimators=trees,
        num_leaves=setting["num_leaves"],
        learning_rate=setting["learning_rate"],
        min_child_samples=setting["min_child_samples"],
        subsample=settings["row_share_per_tree"],
        subsample_freq=1,
        colsample_bytree=settings["input_share_per_tree"],
        reg_lambda=settings["l2_penalty"],
        monotone_constraints=[directions[name] for name in features],
        monotone_constraints_method="advanced",
        random_state=config["seed"],
        n_jobs=1,  # one thread and the two flags below: same command, same model
        deterministic=True,
        force_row_wise=True,
        verbose=-1,
    )
    return Pipeline(
        [
            ("clip", QuantileClipper(lower, upper)),
            ("fill", SimpleImputer(strategy="mean", keep_empty_features=True)),
            ("model", booster),
        ]
    )


def tuning_parts(
    train: pd.DataFrame, config: dict[str, Any], split_method: str
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Cut the training period into a part to fit on and a part to tune on.

    With a time split the tuning part is the last `tuning_months` of the training period,
    so tuning also looks forward in time. Without dates, or when the training period is
    too short for that cut to leave both outcomes in the earlier part (India has one
    training month), it is a random share with the same repaid share in both parts.
    Returns the two parts and a sentence describing them.
    """
    settings = config["model"]["lightgbm"]
    fit_part = None
    if split_method == TIME_SPLIT and DATE_COLUMN in train.columns:
        dates = pd.to_datetime(train[DATE_COLUMN])
        start = dates.max() - pd.DateOffset(months=settings["tuning_months"])
        fit_part, tune_part = train[dates <= start], train[dates > start]
        how = f"the last {settings['tuning_months']} months of the training period"
        if len(fit_part) < len(tune_part) or fit_part["label"].nunique() < 2:
            fit_part = None  # too short to cut by time
    if fit_part is None:
        if train["label"].nunique() < 2 or train["label"].value_counts().min() < 2:
            raise ValueError(
                "The training period has only one outcome (or a single loan of one "
                "outcome); LightGBM cannot be tuned."
            )
        fit_part, tune_part = train_test_split(
            train,
            test_size=settings["tuning_share"],
            stratify=train["label"],
            random_state=config["seed"],
        )
        how = f"a random {settings['tuning_share']:.0%} of the training loans"
        if split_method == TIME_SPLIT:
            how += " (the training period is too short to hold back its last months)"
    for name, part in (("fit", fit_part), ("tuning", tune_part)):
        if len(part) == 0 or part["label"].nunique() < 2:
            raise ValueError(
                f"The {name} part of the training period has no loans or only one outcome; "
                "LightGBM cannot be tuned. Check `model.lightgbm.tuning_months`."
            )
    return fit_part, tune_part, how


def tune_lightgbm(
    config: dict[str, Any],
    train: pd.DataFrame,
    features: list[str],
    directions: dict[str, int],
    split_method: str,
) -> tuple[Pipeline, dict[str, Any]]:
    """Try every setting of the grid, keep the best, and fit it on all training loans.

    "Best" is the lowest log loss on the tuning part (log loss rewards probabilities that
    are both well ranked and honest). Each try grows trees until the tuning part has not
    improved for `early_stopping_rounds` trees.

    Returns the fitted model and a report of what was tried.
    """
    settings = config["model"]["lightgbm"]
    fit_part, tune_part, how = tuning_parts(train, config, split_method)
    tune_labels = tune_part["label"].to_numpy()

    tried = []
    for setting in settings["grid"]:
        model = make_lightgbm(config, features, directions, setting, settings["max_trees"])
        # The preparation steps are fitted on the fit part only, then applied to both.
        prepare = Pipeline(model.steps[:-1]).fit(fit_part[features])
        model.named_steps["model"].fit(
            prepare.transform(fit_part[features]),
            fit_part["label"],
            eval_X=prepare.transform(tune_part[features]),
            eval_y=tune_labels,
            eval_metric="binary_logloss",
            callbacks=[
                early_stopping(settings["early_stopping_rounds"], verbose=False),
                log_evaluation(0),
            ],
        )
        booster = model.named_steps["model"]
        trees = max(int(booster.best_iteration_ or settings["max_trees"]), 1)
        probabilities = booster.predict_proba(
            prepare.transform(tune_part[features]), num_iteration=trees
        )[:, 1]
        tried.append(
            {
                **setting,
                "trees": trees,
                "tuning_log_loss": float(log_loss(tune_labels, probabilities)),
                "tuning_roc_auc": float(roc_auc_score(tune_labels, probabilities)),
            }
        )

    best = min(tried, key=lambda entry: entry["tuning_log_loss"])
    setting = {name: best[name] for name in ("num_leaves", "learning_rate", "min_child_samples")}
    final = make_lightgbm(config, features, directions, setting, best["trees"])
    final.fit(train[features], train["label"])
    report = {
        "tuned_on": how,
        "fit_part_loans": int(len(fit_part)),
        "tuning_part_loans": int(len(tune_part)),
        "chosen": best,
        "tried": tried,
        "note": (
            "Tuned inside the training period only; the validation period was not used. "
            "The final model is fitted on the whole training period."
        ),
    }
    return final, report
