"""The final measurement on the held-back test period: once per model, and written down.

Purpose: every number so far comes from the validation period, which was also used to
    choose the model and its calibration, so it is a little optimistic. The test period
    was held back for one honest look at the model that will be used.
Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md sections 4 and 9 ("touch test once for the final report"),
    src/model/holdout_ledger.py.

Rules:
- One look per model version. Before measuring, the look is written to the ledger
  (reports/<mode>/test_set_use.json), so even a run that fails afterwards is counted. A
  second look at the same model version is refused unless a written reason is given
  (`--again "reason"`), and that reason goes into the ledger too.
- Nothing is chosen or tuned from these numbers. The model, its calibrator (fitted on
  the validation period) and the band lines stay as they are, whatever the result.
- The saved model must belong to the data on this machine: its validation AUC is worked
  out again and must equal the training report's, or nothing is measured.
- The result is reported as it comes out, next to the validation result.

Output: reports/<mode>/test_results.json (the model card picks it up) and
reports/<mode>/calibration_test.png, drawn from the calibration table in that file, so
redrawing it never looks at the test period again (`--redraw-plots`).

Run it: python -m src.model.final_test --mode MODE   (or --all-modes)
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from src.adapters import get_adapter
from src.config import PROJECT_ROOT, VALID_MODES, load_config
from src.model.calibrate import out_of_fold
from src.model.dataset import build_dataset, modelling_rows
from src.model.evaluate import baseline_metrics, evaluate
from src.model.holdout_ledger import read_ledger, record_test_use
from src.model.score import NEEDS_MORE_INFO, band_summary, score_table
from src.model.split import split_for_mode
from src.model.train import DATA_MISSING, METRICS_FILE, load_model, predict_probability

matplotlib.use("Agg")  # draw to files; no window needed
import matplotlib.pyplot as plt  # noqa: E402

REPORTS_DIR = PROJECT_ROOT / "reports"
RESULTS_FILE = "test_results.json"
PLOT_FILE = "calibration_test.png"
FINAL_PURPOSE = "final report (Phase 11 part 4)"


class AlreadyMeasured(RuntimeError):
    """The test period was already used for this model version."""


class ModelDoesNotMatchData(RuntimeError):
    """The saved model was trained on other data than the data on this machine now."""


def earlier_final_looks(mode: str, model_version: str, reports_dir: Path) -> list[dict]:
    """Ledger entries of earlier final looks at this model version."""
    return [
        entry
        for entry in read_ledger(mode, reports_dir)
        if entry["purpose"].startswith(FINAL_PURPOSE) and model_version in entry["detail"]
    ]


def _check_model_matches_data(
    saved: dict[str, Any], validation: Any, metrics: dict[str, Any], config: dict[str, Any]
) -> None:
    """Stop unless the validation AUC, worked out again, equals the training report's."""
    labels = validation["label"].to_numpy()
    raw = saved["model"].predict_proba(validation[saved["features"]])[:, 1]
    again = roc_auc_score(labels, out_of_fold(raw, labels, saved["calibrator"].method, config))
    reported = metrics["validation"]["metrics"]["roc_auc"]
    if abs(again - reported) > 1e-9:
        raise ModelDoesNotMatchData(
            f"Validation AUC is {again:.6f} here but {reported:.6f} in the training report: "
            "the data changed since training. Train again before the final measurement."
        )


def _by_coverage(labels: np.ndarray, probabilities: np.ndarray, waiting: np.ndarray) -> dict:
    """AUC under and above the coverage line (a group with one outcome is left out)."""
    result = {}
    for name, inside in (
        ("coverage_below_the_line", waiting),
        ("coverage_at_or_above_the_line", ~waiting),
    ):
        part = labels[inside]
        if len(part) and part.min() != part.max():
            result[name] = {
                "loans": int(inside.sum()),
                "roc_auc": float(roc_auc_score(part, probabilities[inside])),
            }
    return result


def measure_test_period(
    config: dict[str, Any],
    reports_dir: Path = REPORTS_DIR,
    again_reason: str | None = None,
    tables: dict[str, Any] | None = None,
    saved: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The one look at the test period for the saved model of the config's data mode.

    `tables` and `saved` can be passed in (tests do); by default they come from the
    adapter and the saved model.
    """
    mode = config["data"]["mode"]
    metrics_path = reports_dir / mode / METRICS_FILE
    if not metrics_path.exists():
        raise FileNotFoundError(f"No training report at {metrics_path}: train first.")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    saved = saved if saved is not None else load_model(mode)
    version = saved["version_id"]
    if version != metrics["model_version"]:
        raise ModelDoesNotMatchData(
            f"The saved model is {version} but the training report is for "
            f"{metrics['model_version']}."
        )

    earlier = earlier_final_looks(mode, version, reports_dir)
    if earlier and not (again_reason or "").strip():
        raise AlreadyMeasured(
            f"The test period was already used for {version} (look number "
            f"{earlier[-1]['number']}). Looking again must be justified: --again \"reason\"."
        )

    tables = tables if tables is not None else get_adapter(config).load_all()
    split = split_for_mode(modelling_rows(build_dataset(tables, config, mode=mode)), config, mode)
    _check_model_matches_data(saved, split.validation, metrics, config)

    purpose = FINAL_PURPOSE + (f", again: {again_reason.strip()}" if earlier else "")
    look = record_test_use(
        mode,
        purpose,
        f"Model {version}: AUC, Brier, calibration, bands and coverage groups on the "
        f"{len(split.test):,} test loans. Nothing is chosen or tuned from the result.",
        reports_dir,
    )

    test = split.test
    labels = test["label"].to_numpy()
    probabilities = predict_probability(saved, test)
    measured = evaluate(labels, probabilities, config, mode)
    scored = score_table(probabilities, test, config, mode)
    waiting = (scored["band"] == NEEDS_MORE_INFO).to_numpy()
    validation_auc = metrics["validation"]["metrics"]["roc_auc"]
    return {
        "data_mode": mode,
        "model_version": version,
        "measured_on": "test period (held back until now)",
        "ledger_look_number": look,
        "split": {"method": split.method, "boundaries": split.boundaries, "sizes": split.sizes()},
        "test": measured,
        "test_bands": band_summary(scored, labels),
        "test_by_coverage": _by_coverage(labels, probabilities, waiting),
        "always_average_rate": baseline_metrics(labels, float(split.train["label"].mean())),
        "validation_for_comparison": {
            "roc_auc": validation_auc,
            "roc_auc_range": metrics["validation"]["ranges"]["roc_auc"],
            "brier": metrics["validation"]["metrics"]["brier"],
            "calibration_error": metrics["validation"]["metrics"]["calibration_error"],
        },
        "test_minus_validation_auc": measured["metrics"]["roc_auc"] - validation_auc,
        "note": (
            "Reported as it came out. The model, calibrator and band lines were fixed before "
            "this look and were not changed after it."
        ),
    }


def draw_calibration(results: dict[str, Any], reports_dir: Path = REPORTS_DIR) -> Path:
    """Draw the test-period calibration from the table in the results (no new look)."""
    table = pd.DataFrame(results["test"]["calibration"])
    figure, axis = plt.subplots(figsize=(5, 5))
    low = min(table["mean_predicted"].min(), table["share_repaid"].min()) - 0.02
    axis.plot([low, 1], [low, 1], linestyle="--", color="grey", label="perfectly calibrated")
    axis.plot(table["mean_predicted"], table["share_repaid"], marker="o", label="model")
    axis.set_xlabel("Predicted probability of repaying in time")
    axis.set_ylabel("Share that actually repaid")
    axis.set_title(f"Calibration on the test period ({results['data_mode']})")
    axis.legend()
    figure.tight_layout()
    path = reports_dir / results["data_mode"] / PLOT_FILE
    figure.savefig(path, dpi=120)
    plt.close(figure)
    return path


def write_results(results: dict[str, Any], reports_dir: Path = REPORTS_DIR) -> Path:
    """Write reports/<mode>/test_results.json and its calibration plot."""
    path = reports_dir / results["data_mode"] / RESULTS_FILE
    path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    draw_calibration(results, reports_dir)
    return path


def main(argv: list[str] | None = None) -> int:
    """Command line: the final test-period measurement for one mode or every mode."""
    parser = argparse.ArgumentParser(description="One look at the held-back test period.")
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--mode", choices=VALID_MODES, help="one data mode")
    which.add_argument("--all-modes", action="store_true", help="every data mode")
    parser.add_argument("--again", metavar="REASON", help="look again at the same model, and why")
    parser.add_argument(
        "--redraw-plots",
        action="store_true",
        help="only redraw the plots from the saved results; does not look at the test period",
    )
    arguments = parser.parse_args(argv)
    config = load_config()
    modes = list(VALID_MODES) if arguments.all_modes else [arguments.mode]

    if arguments.redraw_plots:
        for mode in modes:
            path = REPORTS_DIR / mode / RESULTS_FILE
            if path.exists():
                results = json.loads(path.read_text(encoding="utf-8"))
                print(f"'{mode}': {draw_calibration(results)}")
        return 0

    code = 0
    for mode in modes:
        local = copy.deepcopy(config)
        local["data"]["mode"] = mode
        try:
            results = measure_test_period(local, again_reason=arguments.again)
        except FileNotFoundError as missing:
            print(f"'{mode}' not measured: {missing}")
            code = DATA_MISSING
            continue
        except (AlreadyMeasured, ModelDoesNotMatchData) as refused:
            print(f"'{mode}' not measured: {refused}")
            code = 1
            continue
        path = write_results(results)
        test, ranges = results["test"]["metrics"], results["test"]["ranges"]
        print(
            f"'{mode}': test AUC {test['roc_auc']:.3f} "
            f"({ranges['roc_auc'][0]:.3f} to {ranges['roc_auc'][1]:.3f}); validation was "
            f"{results['validation_for_comparison']['roc_auc']:.3f}. Look number "
            f"{results['ledger_look_number']} in the ledger. Report: {path}"
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
