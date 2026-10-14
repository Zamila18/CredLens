"""Train the model, measure it on the validation period and save it with a version.

Purpose: the training run behind `python tasks.py train`.
Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md sections 4, 5, 9 and 12. Settings: the `model`, `split`,
    `evaluation` and `sanity` sections of config/default.yaml.

What a run does:
1. Loads the tables of the active data mode through its adapter.
2. Builds features and labels, and keeps only loans with a known outcome whose merchant
   has a valid consent (src/model/dataset.py).
3. Splits by time: train, validation, test (src/model/split.py).
4. Fits two candidates on the training period only: a regularised logistic regression
   and LightGBM (src/model/boosted.py). In both, an input can only push the probability
   the way its meaning says, so reasons never contradict the facts.
5. Checks calibration of each on the VALIDATION period and corrects it only if that
   clearly helps (src/model/calibrate.py).
6. Chooses one: the logistic regression stays unless LightGBM is clearly better.
   Measures the result on the VALIDATION period, next to two baselines, and separately
   for first loans and repeat loans.
7. Saves the model, its calibrator and a metadata file with a version id, and writes the
   report.

The test period is not touched here. It is kept for the final report (Phase 11), and
every look at it is recorded in reports/<mode>/test_set_use.json.

The model outputs a probability of repaying in time. It never approves or declines
anything: an officer decides.

The reasons behind a score are computed in src/model/explain.py.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import matplotlib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.adapters import get_adapter
from src.config import PROJECT_ROOT, VALID_MODES, load_config
from src.features.dictionary import SYNTHETIC_MODE, expected_directions, load_dictionary
from src.model.boosted import tune_lightgbm
from src.model.calibrate import choose_calibrator
from src.model.dataset import build_dataset, dataset_summary, modelling_rows
from src.model.evaluate import baseline_metrics, evaluate, paired_auc_gain
from src.model.explain import reasons_summary
from src.model.inputs import input_groups, model_inputs, simpler_model
from src.model.preprocess import QuantileClipper
from src.model.score import NEEDS_MORE_INFO, band_lines, band_summary, score_table
from src.model.split import split_for_mode

matplotlib.use("Agg")  # draw to files; no window needed
import matplotlib.pyplot as plt  # noqa: E402

ARTIFACTS_DIR = PROJECT_ROOT / "src" / "model" / "artifacts"
REPORTS_DIR = PROJECT_ROOT / "reports"
MODEL_FILE = "model.joblib"
METADATA_FILE = "metadata.json"
METRICS_FILE = "metrics.json"
CALIBRATION_PLOT = "calibration_validation.png"
PAYMENT_HISTORY_COLUMN = "avg_pay_delay_days"  # empty exactly when a loan is a first loan
HISTORY_COLUMN = "cov_history_6_months"  # yes when the merchant has six months of history
LOGISTIC_REGRESSION = "logistic_regression"
DATA_MISSING = 3  # exit code when the data mode's raw files are not on this machine
LIGHTGBM = "lightgbm"


def make_logistic_regression(config: dict[str, Any]) -> Pipeline:
    """The interpretable baseline: clip, fill missing with the average, scale, then fit.

    Every step learns from the training loans only. Missing values get the training
    average and no "missing" flag, so missing data is neutral (src/model/preprocess.py).
    """
    settings = config["model"]["logistic_regression"]
    lower, upper = settings["clip_quantiles"]
    return Pipeline(
        [
            ("clip", QuantileClipper(lower, upper)),
            ("fill", SimpleImputer(strategy="mean", keep_empty_features=True)),
            ("scale", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    C=settings["C"], max_iter=settings["max_iter"], random_state=config["seed"]
                ),
            ),
        ]
    )


def fit_with_expected_directions(
    config: dict[str, Any],
    train: pd.DataFrame,
    features: list[str],
    directions: dict[str, int],
) -> tuple[Pipeline, list[str], list[str]]:
    """Fit the logistic regression so that every weight points the way its meaning says.

    Each input has an expected direction in the feature dictionary (`higher_is: better`
    or `worse`). After a fit, an input whose weight points the other way is removed and
    the model is fitted again, until none is left.

    Why: a weight with the wrong sign comes from noise or from inputs that overlap. It
    would produce a reason that contradicts the facts, for example "payments were often
    late" shown to a merchant who paid on time. An officer must be able to trust that a
    sentence means what it says.

    Returns the fitted model, the inputs it kept, and the inputs it removed.
    """
    kept, removed = list(features), []
    while True:
        model = make_logistic_regression(config).fit(train[kept], train["label"])
        weights = model.named_steps["model"].coef_[0]
        wrong = [name for name, w in zip(kept, weights) if w * directions[name] < 0]
        if not wrong:
            return model, kept, removed
        removed += wrong
        kept = [name for name in kept if name not in wrong]
        if not kept:
            raise ValueError(
                "Every input pointed against its expected direction; no model was fitted. "
                "Check the labels and the `higher_is` entries in the feature dictionary."
            )


def _score(model: Pipeline, rows: pd.DataFrame, features: list[str]) -> np.ndarray:
    """The model's own repayment probabilities for the given loans, before calibration."""
    return model.predict_proba(rows[features])[:, 1]


def predict_probability(saved: dict[str, Any], rows: pd.DataFrame) -> np.ndarray:
    """Calibrated repayment probabilities from a saved model (the output of `load_model`).

    This is the number a score is made from: score = round(100 x this probability).
    """
    if "calibrator" not in saved:
        raise ValueError(
            "This saved model has no calibrator (it was trained before calibration was "
            "added). Train it again with: python tasks.py train"
        )
    raw = _score(saved["model"], rows, saved["features"])
    return saved["calibrator"].predict(raw)


def _first_loans(rows: pd.DataFrame) -> np.ndarray | None:
    """True for loans with no payment history; None when the data source has no such column."""
    if PAYMENT_HISTORY_COLUMN not in rows.columns:
        return None
    return rows[PAYMENT_HISTORY_COLUMN].isna().to_numpy()


def _by_history(
    validation: pd.DataFrame, probabilities: np.ndarray, config: dict[str, Any], mode: str
) -> dict[str, Any]:
    """Validation AUC for first loans and for repeat loans, shown apart on purpose.

    A first loan has no payment history, which is the hard case this project is about.
    The model must not hide behind the easier repeat loans. Empty for a data source that
    cannot tell the two apart.
    """
    first = _first_loans(validation)
    if first is None:
        return {}
    labels = validation["label"].to_numpy()
    result = {}
    for name, mask in (("first_loans", first), ("repeat_loans", ~first)):
        part = labels[mask]
        if len(part) == 0 or part.min() == part.max():
            continue
        report = evaluate(part, probabilities[mask], config, mode)
        result[name] = {
            "loans": report["loans"],
            "not_repaid_loans": report["not_repaid_loans"],
            "roc_auc": report["metrics"]["roc_auc"],
            "roc_auc_range": report["ranges"]["roc_auc"],
            "warnings": report["warnings"],
        }
    return result


def _fit_candidate(
    name: str,
    config: dict[str, Any],
    split: Any,
    candidates: list[str],
    directions: dict[str, int],
    mode: str,
) -> dict[str, Any]:
    """Fit one kind of model on the training period and measure it on validation.

    Calibration learns from the validation period only. The numbers use the out-of-fold
    probabilities, so no loan is measured with a correction that saw it.
    """
    extra: dict[str, Any] = {}
    if name == LOGISTIC_REGRESSION:
        model, features, removed = fit_with_expected_directions(
            config, split.train, candidates, directions
        )
    elif name == LIGHTGBM:
        model, extra["tuning"] = tune_lightgbm(
            config, split.train, candidates, directions, split.method
        )
        features, removed = list(candidates), []
    else:
        raise ValueError(f"Unknown model: {name!r}")

    labels = split.validation["label"].to_numpy()
    raw = _score(model, split.validation, features)
    calibration = choose_calibrator(raw, labels, config)
    probabilities = calibration["out_of_fold"]
    return {
        "name": name,
        "model": model,
        "features": features,
        "removed": removed,
        "raw": raw,
        "calibration": calibration,
        "probabilities": probabilities,
        "evaluation": evaluate(labels, probabilities, config, mode),
        "train_roc_auc": float(
            roc_auc_score(split.train["label"], _score(model, split.train, features))
        ),
        **extra,
    }


def choose_model(
    fitted: dict[str, dict[str, Any]], labels: np.ndarray, config: dict[str, Any]
) -> dict[str, Any]:
    """Pick the model to use. The simple one stays unless the flexible one is clearly better.

    LightGBM replaces the logistic regression only if both hold on the validation period:
    the whole range of its AUC gain (measured on the same resampled loans) is at or above
    `model.prefer_simple_if_auc_gain_below`, and its Brier score is not worse.

    Why the whole range and not the single number: on synthetic data LightGBM gained
    between +0.002 and +0.013 AUC depending on the data seed, and a rule on the single
    number picked it in one run out of nine. A choice that flips with the seed is not a
    finding. A simple model that an officer and a judge can follow is worth more than a
    gain we cannot be sure of.
    """
    if len(fitted) == 1:
        only = next(iter(fitted))
        return {"chosen": only, "reason": "the only candidate in `model.candidates`"}

    simple, flexible = fitted[LOGISTIC_REGRESSION], fitted[LIGHTGBM]
    needed = config["model"]["prefer_simple_if_auc_gain_below"]
    gain = paired_auc_gain(labels, simple["probabilities"], flexible["probabilities"], config)
    brier_simple = simple["evaluation"]["metrics"]["brier"]
    brier_flexible = flexible["evaluation"]["metrics"]["brier"]
    checks = {
        "whole_gain_range_reaches_the_threshold": bool(gain["range"][0] >= needed),
        "brier_is_not_worse": bool(brier_flexible <= brier_simple),
    }
    chosen = LIGHTGBM if all(checks.values()) else LOGISTIC_REGRESSION
    failed = [name.replace("_", " ") for name, passed in checks.items() if not passed]
    reason = (
        f"LightGBM adds {gain['auc_gain']:+.4f} AUC over the logistic regression "
        f"(range {gain['range'][0]:+.4f} to {gain['range'][1]:+.4f}; the whole range must "
        f"reach {needed:+.4f}). "
        + ("Both checks pass." if not failed else f"Not met: {', '.join(failed)}.")
    )
    return {
        "chosen": chosen,
        "reason": reason,
        "auc_gain_of_lightgbm": gain,
        "brier": {LOGISTIC_REGRESSION: brier_simple, LIGHTGBM: brier_flexible},
        "checks": checks,
    }


def _predicted_against_actual(
    validation: pd.DataFrame, probabilities: np.ndarray, needs_more_info: np.ndarray
) -> dict[str, dict[str, Any]]:
    """Mean predicted probability next to the actual repaid share, for groups that matter.

    A model can be right on average and still be unfair to a group: for example score new
    merchants lower although they repay just as often. This table shows it if it happens.
    Every data mode gets the two coverage groups (thin files against the rest); the
    synthetic data also gets first loans and short histories.
    """
    labels = validation["label"].to_numpy()
    groups: dict[str, np.ndarray] = {
        "coverage_below_the_line": needs_more_info,
        "coverage_at_or_above_the_line": ~needs_more_info,
    }
    first = _first_loans(validation)
    if first is not None:
        groups["first_loans"], groups["repeat_loans"] = first, ~first
    if HISTORY_COLUMN in validation.columns:
        long_history = validation[HISTORY_COLUMN].fillna(False).astype(bool).to_numpy()
        groups["under_6_months_history"] = ~long_history
        groups["6_months_history_or_more"] = long_history
    table = {}
    for name, inside in groups.items():
        if inside.any():
            table[name] = {
                "loans": int(inside.sum()),
                "mean_predicted": float(probabilities[inside].mean()),
                "share_repaid": float(labels[inside].mean()),
                "predicted_minus_actual": float(
                    probabilities[inside].mean() - labels[inside].mean()
                ),
            }
    return table


def train_models(
    dataset: pd.DataFrame, config: dict[str, Any], mode: str | None = None
) -> dict[str, Any]:
    """Fit the candidate models, choose one and report how it does on validation.

    Args:
        dataset: the output of `build_dataset` (every loan, with label and consent).
        config: the validated config.
        mode: the data mode; defaults to the one in the config.

    Returns a dict with the chosen model, its calibrator and feature list, the split, the
    report, and every fitted candidate under "candidates".
    """
    mode = mode or config["data"]["mode"]
    rows = modelling_rows(dataset)
    split = split_for_mode(rows, config, mode)
    validation_labels = split.validation["label"].to_numpy()

    dictionary = load_dictionary()
    directions = expected_directions(dictionary, mode)
    candidates = model_inputs(mode)
    fitted = {
        name: _fit_candidate(name, config, split, candidates, directions, mode)
        for name in config["model"]["candidates"]
    }
    choice = choose_model(fitted, validation_labels, config)
    winner = fitted[choice["chosen"]]
    model, features = winner["model"], winner["features"]
    calibration, probabilities = winner["calibration"], winner["probabilities"]
    headline = winner["evaluation"]

    # Baselines to beat (docs/MODEL_SPEC.md section 9): always the average rate, and a
    # simpler model with part of the inputs (src/model/inputs.py says which, and why).
    simpler = _fit_simpler_model(config, split, directions, winner["raw"], mode)
    average_rate = float(split.train["label"].mean())

    # Score, coverage and band of every validation loan, as an officer would see them.
    scored = score_table(probabilities, split.validation, config, mode)
    bands = band_summary(scored, validation_labels)
    first_loans = _first_loans(split.validation)
    waiting = (scored["band"] == NEEDS_MORE_INFO).to_numpy()

    notes = []
    strong_share = headline["metrics"]["share_at_or_above_strong_line"]
    if strong_share > 0.9:
        notes.append(
            f"{strong_share:.0%} of validation loans score at or above the Strong line "
            f"({band_lines(config, mode)['band_strong_min_score']}), so this line separates "
            "almost nobody. Set `score.band_strong_min_score` from the score distribution."
        )
    if strong_share < 0.01:
        notes.append(
            f"Almost no validation loan ({strong_share:.1%}) reaches the Strong line "
            f"({band_lines(config, mode)['band_strong_min_score']}): with this data the model "
            "cannot single out loans it expects to be repaid at least nine times in ten."
        )
    if waiting.mean() > 0.4:
        notes.append(
            f"{waiting.mean():.0%} of validation loans fall in 'Needs more info'. Check "
            "`score.band_min_coverage` against the coverage this data source can reach."
        )

    report = {
        "data_mode": mode,
        "measured_on": "validation period (the test period is not touched in training)",
        "split": {
            "method": split.method,
            "note": split.note,
            "boundaries": split.boundaries,
            "sizes": split.sizes(),
            "left_out": split.left_out,
        },
        "dataset": dataset_summary(dataset),
        "model": choice["chosen"],
        "model_choice": choice,
        "candidates": {
            name: {
                "inputs_used": candidate["features"],
                "inputs_removed_for_pointing_the_wrong_way": candidate["removed"],
                "calibration_method": candidate["calibration"]["method"],
                "train_roc_auc": candidate["train_roc_auc"],
                "validation_metrics": candidate["evaluation"]["metrics"],
                "validation_ranges": candidate["evaluation"]["ranges"],
                "validation_by_history": _by_history(
                    split.validation, candidate["probabilities"], config, mode
                ),
                **({"tuning": candidate["tuning"]} if "tuning" in candidate else {}),
            }
            for name, candidate in fitted.items()
        },
        "feature_groups": input_groups(mode, dictionary),
        "inputs_used": features,
        "inputs_removed_for_pointing_the_wrong_way": winner["removed"],
        "calibration": {
            "method": calibration["method"],
            "chosen_by": calibration["chosen_by"],
            "fitted_on": "validation period only; re-checked once on the test period",
            "compared_on": (
                f"out-of-fold probabilities, {config['model']['calibration_folds']} folds "
                "of the validation period"
            ),
            "candidates": calibration["candidates"],
        },
        "validation": headline,
        "validation_by_history": _by_history(split.validation, probabilities, config, mode),
        "validation_predicted_against_actual": _predicted_against_actual(
            split.validation, probabilities, waiting
        ),
        "validation_by_coverage": _by_coverage(
            validation_labels, probabilities, waiting, config, mode
        ),
        "validation_bands": {
            "lines": band_lines(config, mode),
            "bands": bands,
            "needs_more_info_share_first_loans": _share(waiting, first_loans, True),
            "needs_more_info_share_repeat_loans": _share(waiting, first_loans, False),
            "low_score_warning_share": float(scored["low_score_warning"].mean()),
        },
        "baselines": {
            "always_average_rate": baseline_metrics(validation_labels, average_rate),
            "simpler_model": simpler["baseline"],
        },
        "gain_over_simpler_model": simpler["gain"],
        "reasons_check": reasons_summary(
            {
                "model": model,
                "calibrator": calibration["calibrator"],
                "features": features,
                "data_mode": mode,
            },
            split.validation,
            config,
        ),
        "notes": notes,
    }
    if LOGISTIC_REGRESSION in fitted:
        simple = fitted[LOGISTIC_REGRESSION]
        report["coefficients"] = _coefficients(simple["model"], simple["features"])
    return {
        "model": model,
        "model_name": choice["chosen"],
        "calibrator": calibration["calibrator"],
        "split": split,
        "features": features,
        "report": report,
        "candidates": fitted,
    }


def _by_coverage(
    labels: np.ndarray,
    probabilities: np.ndarray,
    needs_more_info: np.ndarray,
    config: dict[str, Any],
    mode: str,
) -> dict[str, Any]:
    """Validation AUC inside each coverage group: thin files and the rest.

    Tells whether the model can rank the loans it has little data on, which a single AUC
    over everyone hides. A group with only one outcome is left out.
    """
    result = {}
    groups = (
        ("coverage_below_the_line", needs_more_info),
        ("coverage_at_or_above_the_line", ~needs_more_info),
    )
    for name, inside in groups:
        part = labels[inside]
        if len(part) == 0 or part.min() == part.max():
            continue
        report = evaluate(part, probabilities[inside], config, mode)
        result[name] = {
            "loans": report["loans"],
            "roc_auc": report["metrics"]["roc_auc"],
            "roc_auc_range": report["ranges"]["roc_auc"],
        }
    return result


def _fit_simpler_model(
    config: dict[str, Any],
    split: Any,
    directions: dict[str, int],
    chosen_probabilities: np.ndarray,
    mode: str,
) -> dict[str, Any]:
    """Fit the simpler model of the mode and measure what the full model adds to it.

    It is a logistic regression on part of the inputs, fitted like the main one. If every
    one of its inputs points against its meaning in this data, it cannot be fitted; the
    report then says so instead of stopping the whole run.
    """
    definition = simpler_model(mode)
    labels = split.validation["label"].to_numpy()
    baseline = {"name": definition["name"], "description": definition["description"]}
    try:
        model, features, _ = fit_with_expected_directions(
            config, split.train, definition["features"], directions
        )
    except ValueError:
        baseline.update(
            features=[],
            metrics=None,
            ranges=None,
            note="Could not be fitted: its inputs point against their meaning in this data.",
        )
        return {"baseline": baseline, "gain": None}
    probabilities = _score(model, split.validation, features)
    measured = evaluate(labels, probabilities, config, mode)
    baseline.update(features=features, metrics=measured["metrics"], ranges=measured["ranges"])
    return {
        "baseline": baseline,
        "gain": paired_auc_gain(labels, probabilities, chosen_probabilities, config),
    }


def _share(flags: np.ndarray, first_loans: np.ndarray | None, first: bool) -> float | None:
    """Share of flagged loans among first loans (or repeat loans); None if there are none."""
    if first_loans is None:
        return None
    group = first_loans if first else ~first_loans
    return float(flags[group].mean()) if group.any() else None


def _coefficients(model: Pipeline, features: list[str]) -> dict[str, float]:
    """The weight of each input after scaling. Positive means it raises the probability."""
    weights = model.named_steps["model"].coef_[0]
    return {name: round(float(weight), 4) for name, weight in zip(features, weights)}


def code_commit() -> str:
    """The current commit of the repository (read-only), marked if files are uncommitted."""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
        changed = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{commit}+uncommitted" if changed else commit


def save_artifacts(
    result: dict[str, Any], config: dict[str, Any], artifacts_dir: Path | None = None
) -> dict[str, Any]:
    """Save the model and its metadata; return the metadata.

    Every score and decision later records the version id written here.
    """
    report = result["report"]
    mode = report["data_mode"]
    folder = (Path(artifacts_dir) if artifacts_dir is not None else ARTIFACTS_DIR) / mode
    folder.mkdir(parents=True, exist_ok=True)

    commit = code_commit()
    created = datetime.now()
    metadata = {
        "version_id": f"{mode}-{created:%Y%m%d-%H%M%S}-{commit.split('+')[0]}",
        "created_at": created.isoformat(timespec="seconds"),
        "data_mode": mode,
        "code_commit": commit,
        "data_seed": config["seed"],
        # Only the synthetic data has a signal strength; public data is what it is.
        "delivery_signal_strength": (
            config["data"]["delivery_signal_strength"] if mode == SYNTHETIC_MODE else None
        ),
        "model": report["model"],
        "calibrator": report["calibration"]["method"],
        "feature_list": result["features"],
        "train_window": report["split"]["boundaries"],
        "split_method": report["split"]["method"],
        "validation_metrics": report["validation"]["metrics"],
        "validation_ranges": report["validation"]["ranges"],
        "note": "Outputs a probability of repaying in time. Decision support only.",
    }
    saved = {
        "model": result["model"],
        "model_name": result["model_name"],
        "data_mode": mode,
        "calibrator": result["calibrator"],
        "features": result["features"],
        "version_id": metadata["version_id"],
    }
    joblib.dump(saved, folder / MODEL_FILE)
    (folder / METADATA_FILE).write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def load_model(mode: str, artifacts_dir: Path | None = None) -> dict[str, Any]:
    """Load a saved model: the fitted pipeline, its calibrator, feature list and version id.

    Use `predict_probability` on the result to get calibrated probabilities.
    """
    folder = (Path(artifacts_dir) if artifacts_dir is not None else ARTIFACTS_DIR) / mode
    path = folder / MODEL_FILE
    if not path.exists():
        raise FileNotFoundError(
            f"No trained model at {path}. Create it with: python tasks.py train"
        )
    return joblib.load(path)


def write_report(
    result: dict[str, Any], metadata: dict[str, Any], reports_dir: Path | None = None
) -> dict[str, Path]:
    """Write metrics.json and the calibration plot for the validation period."""
    report = dict(result["report"])
    report["model_version"] = metadata["version_id"]
    folder = (Path(reports_dir) if reports_dir is not None else REPORTS_DIR) / report["data_mode"]
    folder.mkdir(parents=True, exist_ok=True)

    metrics_path = folder / METRICS_FILE
    metrics_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    table = pd.DataFrame(report["validation"]["calibration"])
    figure, axis = plt.subplots(figsize=(5, 5))
    low = min(table["mean_predicted"].min(), table["share_repaid"].min()) - 0.02
    axis.plot([low, 1], [low, 1], linestyle="--", color="grey", label="perfectly calibrated")
    axis.plot(table["mean_predicted"], table["share_repaid"], marker="o", label="model")
    axis.set_xlabel("Predicted probability of repaying in time")
    axis.set_ylabel("Share that actually repaid")
    axis.set_title(f"Calibration on the validation period ({report['data_mode']})")
    axis.legend()
    figure.tight_layout()
    plot_path = folder / CALIBRATION_PLOT
    figure.savefig(plot_path, dpi=120)
    plt.close(figure)
    return {"metrics": metrics_path, "calibration_plot": plot_path}


def run_training(config: dict[str, Any]) -> dict[str, Any]:
    """The whole training run for the data mode in the config. Returns the result and metadata."""
    mode = config["data"]["mode"]
    tables = get_adapter(config).load_all()
    dataset = build_dataset(tables, config, mode=mode)
    result = train_models(dataset, config, mode)
    metadata = save_artifacts(result, config)
    paths = write_report(result, metadata)
    return {**result, "metadata": metadata, "paths": paths}


def main(argv: list[str] | None = None) -> int:
    """Command line: train one data mode, save the model and print a short summary."""
    parser = argparse.ArgumentParser(description="Train and measure the model of one data mode.")
    parser.add_argument("--mode", choices=VALID_MODES, help="data mode; default: the config's")
    arguments = parser.parse_args(argv)
    config = load_config()
    if arguments.mode:
        config["data"]["mode"] = arguments.mode
    try:
        run = run_training(config)
    except FileNotFoundError as missing:
        # A teammate without the public downloads: say so, and let `--all-modes` go on.
        print(f"Not trained '{config['data']['mode']}': {missing}")
        return DATA_MISSING
    report, metadata = run["report"], run["metadata"]
    validation = report["validation"]
    metrics, ranges = validation["metrics"], validation["ranges"]
    baseline = report["baselines"]

    print(f"Trained on '{report['data_mode']}'. Model in use: {report['model']}.")
    print(f"  version: {metadata['version_id']}")
    print(f"  loans used: {report['split']['sizes']}  ({report['split']['method']} split)")
    print(f"  left out of modelling: {report['dataset']}")
    print("  Measured on the VALIDATION period (test period not touched):")
    print(
        f"    AUC {metrics['roc_auc']:.3f} "
        f"(range {ranges['roc_auc'][0]:.3f} to {ranges['roc_auc'][1]:.3f}); "
        "average-rate baseline 0.500"
    )
    simpler, gain = baseline["simpler_model"], report["gain_over_simpler_model"]
    if simpler["metrics"] is None:
        print(f"    simpler model ({simpler['name']}): {simpler['note']}")
    else:
        print(
            f"    simpler model ({simpler['name']}): AUC {simpler['metrics']['roc_auc']:.3f}; "
            f"the model in use adds {gain['auc_gain']:+.3f} "
            f"(range {gain['range'][0]:+.3f} to {gain['range'][1]:+.3f})"
        )
    print(
        f"    Brier {metrics['brier']:.4f} "
        f"(average-rate baseline {baseline['always_average_rate']['brier']:.4f}); "
        f"calibration error {metrics['calibration_error']:.4f}"
    )
    print(
        f"    not repaid among the {config['evaluation']['top_k']} lowest-scored: "
        f"{metrics['not_repaid_rate_in_lowest_k']:.0%} "
        f"(overall {1 - validation['share_repaid']:.0%})"
    )
    calibration = report["calibration"]
    compared = ", ".join(
        f"{name} {numbers['brier']:.4f}" for name, numbers in calibration["candidates"].items()
    )
    print(f"    calibration: '{calibration['method']}' chosen (out-of-fold Brier: {compared})")
    groups = {**report["validation_by_history"], **report["validation_by_coverage"]}
    for name, part in groups.items():
        print(
            f"    {name.replace('_', ' ')}: AUC {part['roc_auc']:.3f} "
            f"(range {part['roc_auc_range'][0]:.3f} to {part['roc_auc_range'][1]:.3f}, "
            f"{part['loans']} loans)"
        )
    lines = report["validation_bands"]["lines"]
    print(
        f"  Bands (Strong line {lines['band_strong_min_score']}, "
        f"coverage line {lines['band_min_coverage']:.0%}):"
    )
    for band, part in report["validation_bands"]["bands"].items():
        repaid = "n/a" if part["share_repaid"] is None else f"{part['share_repaid']:.1%}"
        print(f"    {band}: {part['share']:.0%} of loans, {repaid} repaid")
    print("  Candidates on validation:")
    for name, candidate in report["candidates"].items():
        numbers, spread = candidate["validation_metrics"], candidate["validation_ranges"]
        print(
            f"    {name}: AUC {numbers['roc_auc']:.3f} "
            f"(range {spread['roc_auc'][0]:.3f} to {spread['roc_auc'][1]:.3f}), "
            f"Brier {numbers['brier']:.4f}, training AUC {candidate['train_roc_auc']:.3f}"
        )
    print(f"    choice: {report['model_choice']['reason']}")
    print("  Predicted against actual (a gap means a group is scored too high or too low):")
    for name, part in report["validation_predicted_against_actual"].items():
        print(
            f"    {name.replace('_', ' ')}: predicted {part['mean_predicted']:.1%}, "
            f"repaid {part['share_repaid']:.1%}"
        )
    check = report["reasons_check"]
    print(
        f"  Reasons checked on {check['loans_checked']} validation loans: parts and score "
        f"differ by at most {check['largest_gap']:.6f}; "
        f"{check['loans_with_no_reason']} loans had no reason to show"
    )
    removed = report["inputs_removed_for_pointing_the_wrong_way"]
    print(f"  inputs used: {len(report['inputs_used'])}")
    print(f"  inputs removed for pointing the wrong way: {removed or 'none'}")
    for warning in validation["warnings"]:
        print(f"  WARNING: {warning}")
    for note in report["notes"]:
        print(f"  NOTE: {note}")
    print(f"  Report: {run['paths']['metrics']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
