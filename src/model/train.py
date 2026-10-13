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
4. Fits a regularised logistic regression on the training period only. An input whose
   weight points against its meaning is removed, so reasons never contradict the facts.
5. Checks calibration on the VALIDATION period and corrects it only if that clearly
   helps (src/model/calibrate.py).
6. Measures the result on the VALIDATION period, next to two baselines, and separately
   for first loans and repeat loans.
7. Saves the model, its calibrator and a metadata file with a version id, and writes the
   report.

The test period is not touched here. It is kept for the final report (Phase 11), and
every look at it is recorded in reports/<mode>/test_set_use.json.

The model outputs a probability of repaying in time. It never approves or declines
anything: an officer decides.

LightGBM and reasons are added in Phase 6.
"""

from __future__ import annotations

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
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.adapters import get_adapter
from src.config import PROJECT_ROOT, load_config
from src.features.build_features import FEATURE_GROUPS, model_feature_names
from src.features.dictionary import expected_directions, load_dictionary
from src.model.calibrate import choose_calibrator
from src.model.dataset import build_dataset, dataset_summary, modelling_rows
from src.model.evaluate import baseline_metrics, evaluate, paired_auc_gain
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
HEADLINE_GROUPS = "ABC"  # purchases + payments + deliveries; the questionnaire is never in
PAYMENT_HISTORY_COLUMN = "avg_pay_delay_days"  # empty exactly when a loan is a first loan


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


def train_models(
    dataset: pd.DataFrame, config: dict[str, Any], mode: str | None = None
) -> dict[str, Any]:
    """Fit the logistic regression and report how it does on the validation period.

    Args:
        dataset: the output of `build_dataset` (every loan, with label and consent).
        config: the validated config.
        mode: the data mode; defaults to the one in the config.

    Returns a dict with the fitted model, the split, the feature list and the report.
    """
    mode = mode or config["data"]["mode"]
    rows = modelling_rows(dataset)
    split = split_for_mode(rows, config, mode)
    validation_labels = split.validation["label"].to_numpy()

    directions = expected_directions(load_dictionary())
    candidates = model_feature_names(HEADLINE_GROUPS)
    model, features, removed = fit_with_expected_directions(
        config, split.train, candidates, directions
    )
    raw_probabilities = _score(model, split.validation, features)

    # Calibration learns from the validation period only. The numbers below use the
    # out-of-fold probabilities, so no loan is measured with a correction that saw it.
    calibration = choose_calibrator(raw_probabilities, validation_labels, config)
    probabilities = calibration["out_of_fold"]
    headline = evaluate(validation_labels, probabilities, config, mode)

    # Baselines to beat (docs/MODEL_SPEC.md section 9).
    purchase_model, purchase_features, _ = fit_with_expected_directions(
        config, split.train, model_feature_names("A"), directions
    )
    purchase_probabilities = _score(purchase_model, split.validation, purchase_features)
    purchases_only = evaluate(validation_labels, purchase_probabilities, config, mode)
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
        "model": "logistic_regression",
        "feature_groups": {group: FEATURE_GROUPS[group] for group in HEADLINE_GROUPS},
        "inputs_used": features,
        "inputs_removed_for_pointing_the_wrong_way": removed,
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
        "validation_bands": {
            "lines": band_lines(config, mode),
            "bands": bands,
            "needs_more_info_share_first_loans": _share(waiting, first_loans, True),
            "needs_more_info_share_repeat_loans": _share(waiting, first_loans, False),
            "low_score_warning_share": float(scored["low_score_warning"].mean()),
        },
        "baselines": {
            "always_average_rate": baseline_metrics(validation_labels, average_rate),
            "purchases_only": {
                "features": purchase_features,
                "metrics": purchases_only["metrics"],
                "ranges": purchases_only["ranges"],
            },
        },
        "gain_over_purchases_only": paired_auc_gain(
            validation_labels, purchase_probabilities, raw_probabilities, config
        ),
        "coefficients": _coefficients(model, features),
        "notes": notes,
    }
    return {
        "model": model,
        "calibrator": calibration["calibrator"],
        "split": split,
        "features": features,
        "report": report,
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
        "delivery_signal_strength": config["data"]["delivery_signal_strength"],
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
    """The whole training run for the active data mode. Returns the result and metadata."""
    tables = get_adapter(config).load_all()
    dataset = build_dataset(tables, config)
    result = train_models(dataset, config)
    metadata = save_artifacts(result, config)
    paths = write_report(result, metadata)
    return {**result, "metadata": metadata, "paths": paths}


def main() -> int:
    """Command line: train, save and print a short summary."""
    config = load_config()
    run = run_training(config)
    report, metadata = run["report"], run["metadata"]
    validation = report["validation"]
    metrics, ranges = validation["metrics"], validation["ranges"]
    baseline = report["baselines"]

    print(f"Trained {report['model']} on '{report['data_mode']}'.")
    print(f"  version: {metadata['version_id']}")
    print(f"  loans used: {report['split']['sizes']}  ({report['split']['method']} split)")
    print(f"  left out of modelling: {report['dataset']}")
    print("  Measured on the VALIDATION period (test period not touched):")
    print(
        f"    AUC {metrics['roc_auc']:.3f} "
        f"(range {ranges['roc_auc'][0]:.3f} to {ranges['roc_auc'][1]:.3f}); "
        f"purchases-only baseline {baseline['purchases_only']['metrics']['roc_auc']:.3f}; "
        "average-rate baseline 0.500"
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
    gain = report["gain_over_purchases_only"]
    print(
        f"    gain over purchases only: {gain['auc_gain']:+.3f} "
        f"(range {gain['range'][0]:+.3f} to {gain['range'][1]:+.3f})"
    )
    for name, part in report["validation_by_history"].items():
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
