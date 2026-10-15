"""Group audit: does the model work as well for every group of merchants?

Purpose: report how the model does for each group of an audit column (for example
    town tier, shop type, trade licence; sex, age band or state in the public data), so
    a gap is seen before anyone relies on the score.
Owner role: C (ML engineer), with the lead.
Implements: docs/MODEL_SPEC.md section 11, PROJECT_BRIEF section 18. Settings: the
    `fairness` section of config/default.yaml.

Rules:
- Group columns are audit-only. They come from the adapter's `audit_frame()` and are
  never model inputs; the audit refuses to run if one of them is.
- Measured on the VALIDATION months. The test months are not used here.
- The probabilities are calibrated out of fold, exactly as in the training report: no
  loan is corrected by a calibrator that saw its outcome. (The saved calibrator was
  fitted on all validation loans, so using it here would flatter the results.)
- For each group we report: loans, share repaid, mean predicted probability, mean
  score, band shares, AUC, and how far predictions are from what happened.
- Two checks per group, each against the rest of the loans:
    ranking      AUC of the group minus AUC of the rest
    calibration  (predicted minus actual) of the group minus the same for the rest;
                 positive means the model expects more repayment than the group shows
- A gap larger than `flag_gap_points` is a candidate. It is FLAGGED only if the
  bootstrap ranges of the group and the rest do not overlap, or (synthetic data, more
  than one seed) the gap is there, in the same direction, in every seed.
- A group with fewer than `min_group_outcomes` repaid or not-repaid loans is listed
  with its counts only: too few to measure.

What this does NOT show: that the model is "fair". It shows where it measurably works
differently on these data, and nothing about groups that are not in the data.

Run it: python -m src.model.fairness [--mode MODE | --all-modes]
"""

from __future__ import annotations

import argparse
import copy
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from src.adapters import get_adapter
from src.config import PROJECT_ROOT, VALID_MODES, load_config
from src.features.dictionary import SYNTHETIC_MODE
from src.model.calibrate import out_of_fold
from src.model.dataset import build_dataset, modelling_rows
from src.model.score import NEEDS_MORE_INFO, STRONG, score_table
from src.model.split import split_for_mode
from src.model.train import DATA_MISSING, load_model, train_models
from src.synth.generate import build_tables

REPORTS_DIR = PROJECT_ROOT / "reports"
REPORT_FILE = "fairness.json"
SUMMARY_FILE = "FAIRNESS.md"
FLAGGED = "flagged"
CANDIDATE = "gap, but within the ranges"
NO_GAP = "no gap"
TOO_FEW = "too few loans to measure"
NOT_STATED = "not stated"
CHECKS = ("ranking", "calibration")


class GroupColumnIsAnInput(ValueError):
    """An audit column was found among the model inputs: that must never happen."""


def audit_columns(config: dict[str, Any], mode: str) -> list[str]:
    """The group columns audited for a data mode (config `fairness`)."""
    settings = config["fairness"]
    if mode == SYNTHETIC_MODE:
        return list(settings["group_columns"])
    return list(settings["audit_only_columns"][mode])


def _range(values: list[float], level: float) -> list[float] | None:
    """The middle `level` share of the bootstrap values, or None when there are none."""
    if not values:
        return None
    low, high = 100 * (1 - level) / 2, 100 * (1 + level) / 2
    return [float(np.percentile(values, low)), float(np.percentile(values, high))]


def _overlap(first: list[float] | None, second: list[float] | None) -> bool:
    """True when two ranges share any value (or one of them is missing)."""
    if first is None or second is None:
        return True
    return first[0] <= second[1] and second[0] <= first[1]


def _auc(labels: np.ndarray, probabilities: np.ndarray) -> float | None:
    """AUC, or None when only one outcome is present."""
    if labels.min() == labels.max():
        return None
    return float(roc_auc_score(labels, probabilities))


def _status(gap: float | None, group_range: Any, rest_range: Any, config: dict[str, Any]) -> str:
    """No gap, a gap within the ranges, or a flagged gap (see the module docstring)."""
    if gap is None:
        return TOO_FEW
    if abs(gap) <= config["fairness"]["flag_gap_points"]:
        return NO_GAP
    return CANDIDATE if _overlap(group_range, rest_range) else FLAGGED


def _measure_group(
    labels: np.ndarray,
    probabilities: np.ndarray,
    inside: np.ndarray,
    per_loan: dict[str, np.ndarray],
    config: dict[str, Any],
    rng: np.random.Generator,
) -> dict[str, Any]:
    """Ranking and calibration of one group against the rest, with bootstrap ranges.

    Also the ranges of the group's mean score and band shares (`per_loan` holds the
    score and the Strong and Needs-more-info flags of every loan).
    """
    settings = config["fairness"]
    level = config["evaluation"]["bootstrap_level"]
    group, rest = np.flatnonzero(inside), np.flatnonzero(~inside)

    def numbers(rows: np.ndarray) -> tuple[float | None, float]:
        y, p = labels[rows], probabilities[rows]
        return _auc(y, p), float(p.mean() - y.mean())

    group_auc, group_calibration = numbers(group)
    rest_auc, rest_calibration = numbers(rest)
    draws: dict[str, list[float]] = {
        "group_auc": [], "rest_auc": [], "group_calibration": [], "rest_calibration": [],
        **{f"group_{name}": [] for name in per_loan},
    }
    for _ in range(settings["bootstrap_resamples"]):
        for name, rows in (("group", group), ("rest", rest)):
            sample = rows[rng.integers(0, len(rows), size=len(rows))]
            auc, calibration = numbers(sample)
            if auc is not None:
                draws[f"{name}_auc"].append(auc)
            draws[f"{name}_calibration"].append(calibration)
            if name == "group":
                for column, values in per_loan.items():
                    draws[f"group_{column}"].append(float(values[sample].mean()))
    ranges = {name: _range(values, level) for name, values in draws.items()}

    ranking_gap = None if group_auc is None or rest_auc is None else group_auc - rest_auc
    calibration_gap = group_calibration - rest_calibration
    return {
        **{f"{column}_range": ranges[f"group_{column}"] for column in per_loan},
        "roc_auc": group_auc,
        "roc_auc_range": ranges["group_auc"],
        "rest_roc_auc": rest_auc,
        "rest_roc_auc_range": ranges["rest_auc"],
        "predicted_minus_actual": group_calibration,
        "predicted_minus_actual_range": ranges["group_calibration"],
        "rest_predicted_minus_actual": rest_calibration,
        "rest_predicted_minus_actual_range": ranges["rest_calibration"],
        "ranking_gap": ranking_gap,
        "ranking": _status(ranking_gap, ranges["group_auc"], ranges["rest_auc"], config),
        "calibration_gap": calibration_gap,
        "calibration": _status(
            calibration_gap, ranges["group_calibration"], ranges["rest_calibration"], config
        ),
    }


def group_audit(
    labels: Any,
    probabilities: Any,
    scored: pd.DataFrame,
    groups: pd.DataFrame,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """One row per group of every audit column: counts, scores, bands and both checks.

    Args:
        labels: 1 = repaid in time, 0 = not, one per validation loan.
        probabilities: the calibrated repayment probabilities of the same loans.
        scored: `score_table` of the same loans (score, coverage, band), same order.
        groups: the audit columns of the same loans, same order. A missing value is
            shown as its own group, "not stated".
        config: the validated config.
    """
    labels = np.asarray(labels, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    least = config["fairness"]["min_group_outcomes"]
    rng = np.random.default_rng(config["seed"])
    bands = scored["band"].to_numpy()
    per_loan = {
        "mean_score": scored["score"].to_numpy(dtype=float),
        "share_strong": (bands == STRONG).astype(float),
        "share_needs_more_info": (bands == NEEDS_MORE_INFO).astype(float),
    }

    rows = []
    for column in groups.columns:
        values = groups[column].astype(object).where(groups[column].notna(), NOT_STATED)
        values = values.astype(str).to_numpy()
        sizes = pd.Series(values).value_counts()
        # Largest group first; equal sizes by name, so every run lists them the same way.
        for group in sorted(sizes.index, key=lambda name: (-sizes[name], name)):
            inside = values == group
            repaid = int(labels[inside].sum())
            not_repaid = int(inside.sum()) - repaid
            row: dict[str, Any] = {"column": column, "group": group, "loans": int(inside.sum())}
            if min(repaid, not_repaid) < least or (~inside).sum() == 0:
                # The outcomes or scores of a small group could point to the people in
                # it, so only its size is reported.
                row.update(ranking=TOO_FEW, calibration=TOO_FEW)
                rows.append(row)
                continue
            row.update(
                not_repaid=not_repaid,
                share_repaid=float(labels[inside].mean()),
                mean_predicted=float(probabilities[inside].mean()),
                **{name: float(each[inside].mean()) for name, each in per_loan.items()},
            )
            row.update(_measure_group(labels, probabilities, inside, per_loan, config, rng))
            rows.append(row)
    return rows


def persistent_gaps(audits: list[list[dict[str, Any]]], config: dict[str, Any]) -> None:
    """Flag a gap that is above the line, in the same direction, in every seed.

    `audits` holds one `group_audit` result per seed; the first one is updated in place
    (its rows get `seeds_with_gap` and, where the gap persists, the FLAGGED status).
    """
    line = config["fairness"]["flag_gap_points"]
    later = [{(r["column"], r["group"]): r for r in audit} for audit in audits[1:]]
    for row in audits[0]:
        key = (row["column"], row["group"])
        for check in CHECKS:
            gaps = [row.get(f"{check}_gap")] + [
                other.get(key, {}).get(f"{check}_gap") for other in later
            ]
            measured = [gap for gap in gaps if gap is not None]
            above = [gap for gap in measured if abs(gap) > line]
            row[f"{check}_seeds_with_gap"] = f"{len(above)} of {len(gaps)}"
            same_sign = len({np.sign(gap) for gap in above}) == 1
            if len(gaps) > 1 and len(above) == len(gaps) and same_sign:
                row[check] = FLAGGED


def _refuse_group_inputs(columns: list[str], features: list[str]) -> None:
    """Stop if an audit column is a model input (it must never be)."""
    both = sorted(set(columns) & set(features))
    if both:
        raise GroupColumnIsAnInput(f"Audit columns used as model inputs: {both}")


def _validation_audit(
    saved: dict[str, Any],
    tables: dict[str, pd.DataFrame],
    audit: pd.DataFrame,
    config: dict[str, Any],
    mode: str,
) -> tuple[list[dict[str, Any]], int]:
    """The group audit of a model on the validation loans of these tables."""
    columns = audit_columns(config, mode)
    _refuse_group_inputs(columns, saved["features"])
    rows = modelling_rows(build_dataset(tables, config, mode=mode))
    validation = split_for_mode(rows, config, mode).validation
    labels = validation["label"].to_numpy()
    raw = saved["model"].predict_proba(validation[saved["features"]])[:, 1]
    probabilities = out_of_fold(raw, labels, saved["calibrator"].method, config)
    scored = score_table(probabilities, validation, config, mode)
    groups = validation[["merchant_id"]].merge(
        audit[["merchant_id", *columns]].drop_duplicates("merchant_id"),
        on="merchant_id",
        how="left",
        validate="many_to_one",
    )[columns]
    overall = float(roc_auc_score(labels, probabilities))
    return group_audit(labels, probabilities, scored, groups, config), int(len(labels)), overall


class ModelDoesNotMatchData(RuntimeError):
    """The saved model was trained on other data than the data on this machine now."""


def check_against_training(overall_auc: float, mode: str, reports_dir: Path) -> None:
    """Stop unless the validation AUC equals the one the training run reported.

    If the data was generated again (another seed or strength) without training again,
    the saved model and the data no longer belong together, and an audit would describe
    neither.
    """
    path = reports_dir / mode / "metrics.json"
    reported = json.loads(path.read_text(encoding="utf-8"))["validation"]["metrics"]["roc_auc"]
    if abs(reported - overall_auc) > 1e-9:
        raise ModelDoesNotMatchData(
            f"Validation AUC is {overall_auc:.6f} here but {reported:.6f} in {path}: the "
            f"data changed since training. Run: python tasks.py train --mode {mode}"
        )


def _synthetic_seed(config: dict[str, Any], seed: int) -> list[dict[str, Any]]:
    """Generate the synthetic data with another seed, train on it and audit it."""
    local = copy.deepcopy(config)
    local["seed"] = seed
    tables = build_tables(local, local["data"]["delivery_signal_strength"])[0]
    trained = train_models(build_dataset(tables, local, mode=SYNTHETIC_MODE), local)
    audit = tables["merchants"][["merchant_id", *audit_columns(local, SYNTHETIC_MODE)]]
    return _validation_audit(trained, tables, audit, local, SYNTHETIC_MODE)[0]


def run_audit(config: dict[str, Any], progress: Any = print) -> dict[str, Any]:
    """The group audit of the saved model of the config's data mode (and more seeds)."""
    mode = config["data"]["mode"]
    started = time.time()
    adapter = get_adapter(config)
    tables = adapter.load_all()
    saved = load_model(mode)
    rows, loans, overall = _validation_audit(saved, tables, adapter.audit_frame(), config, mode)
    check_against_training(overall, mode, REPORTS_DIR)

    seeds = [config["seed"]]
    if mode == SYNTHETIC_MODE:
        others = [seed for seed in config["fairness"]["seeds"] if seed != config["seed"]]
        audits = [rows]
        for seed in others:
            progress(f"  seed {seed}: generating, training and auditing ...")
            audits.append(_synthetic_seed(config, seed))
        persistent_gaps(audits, config)
        seeds += others

    flagged = [
        f"{row['column']} = {row['group']}: {check}"
        for row in rows
        for check in CHECKS
        if row[check] == FLAGGED
    ]
    return {
        "data_mode": mode,
        "model_version": saved["version_id"],
        "measured_on": "validation months (the test months are not used)",
        "validation_loans": loans,
        "seeds": seeds,
        "columns": audit_columns(config, mode),
        "rules": {
            "gap_line": config["fairness"]["flag_gap_points"],
            "flagged_when": (
                "the gap is above the line and the ranges of the group and the rest do not "
                "overlap" + (", or it is above the line in every seed" if len(seeds) > 1 else "")
            ),
            "min_group_outcomes": config["fairness"]["min_group_outcomes"],
            "range_level": config["evaluation"]["bootstrap_level"],
            "calibration_gap_meaning": (
                "positive: the model expects more repayment from this group than it shows, "
                "compared with the rest"
            ),
        },
        "flagged": flagged,
        "groups": rows,
        "seconds": round(time.time() - started, 1),
        "note": (
            "Audit columns are never model inputs. This shows where the model measurably "
            "works differently on these data; it does not show that the model is fair."
        ),
    }


def write_report(report: dict[str, Any], reports_dir: Path | None = None) -> Path:
    """Write reports/<mode>/fairness.json."""
    folder = (Path(reports_dir) if reports_dir is not None else REPORTS_DIR) / report["data_mode"]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / REPORT_FILE
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return path


def _number(value: float | None, digits: int = 3, signed: bool = False) -> str:
    """A number for the summary table, or a dash."""
    if value is None:
        return "-"
    return f"{value:+.{digits}f}" if signed else f"{value:.{digits}f}"


def write_summary(reports_dir: Path | None = None) -> Path:
    """Write reports/FAIRNESS.md from every fairness.json that exists."""
    folder = Path(reports_dir) if reports_dir is not None else REPORTS_DIR
    lines = [
        "# Group audit (Phase 11 part 2)",
        "",
        "Written by `python -m src.model.fairness --all-modes`. Measured on the validation "
        "months of each data mode; the test months are not used. Audit columns are never "
        "model inputs.",
        "",
        "Ranking gap: AUC of the group minus AUC of the rest. Calibration gap: (predicted "
        "minus actual) of the group minus the same for the rest; positive means the model "
        "expects more repayment from the group than it shows. A gap above the line is "
        "flagged only if the ranges of the group and the rest do not overlap, or (synthetic "
        "data) it is above the line in every seed. Each group is compared with the rest, so "
        "a large gap in one group also shows, smaller and mirrored, in the groups compared "
        "with it.",
        "",
        "This shows where the model measurably works differently on these data. It does "
        "not show that the model is fair, and it says nothing about groups not in the data. "
        "Many groups are checked, so a flag is a reason to look closer, not proof. A group "
        "with too few repaid or not-repaid loans shows its size only. India's validation "
        "period is one month, so its regional gaps may belong to that month only.",
        "",
    ]
    for mode in VALID_MODES:
        path = folder / mode / REPORT_FILE
        if not path.exists():
            continue
        report = json.loads(path.read_text(encoding="utf-8"))
        lines += [
            f"## {mode}",
            "",
            f"Model {report['model_version']}, {report['validation_loans']:,} validation "
            f"loans, seeds {report['seeds']}, gap line {report['rules']['gap_line']}.",
            "",
            "Flagged: " + ("; ".join(report["flagged"]) if report["flagged"] else "none") + ".",
            "",
            "| Column | Group | Loans | Repaid | Mean score | AUC | Ranking gap | Ranking "
            "| Calibration gap | Calibration |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for row in report["groups"]:
            if row["ranking"] == TOO_FEW:
                lines.append(
                    f"| {row['column']} | {row['group']} | {row['loans']:,} "
                    f"| - | - | - | - | {TOO_FEW} | - | {TOO_FEW} |"
                )
                continue
            lines.append(
                f"| {row['column']} | {row['group']} | {row['loans']:,} "
                f"| {row['share_repaid']:.1%} | {row['mean_score']:.1f} "
                f"| {_number(row.get('roc_auc'))} | {_number(row.get('ranking_gap'), signed=True)} "
                f"| {row['ranking']} | {_number(row.get('calibration_gap'), signed=True)} "
                f"| {row['calibration']} |"
            )
        lines.append("")
    path = folder / SUMMARY_FILE
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    """Command line: audit one data mode, or every mode whose data is on this machine."""
    parser = argparse.ArgumentParser(description="Group audit on the validation months.")
    which = parser.add_mutually_exclusive_group()
    which.add_argument("--mode", choices=VALID_MODES, help="data mode; default: the config's")
    which.add_argument("--all-modes", action="store_true", help="every data mode")
    arguments = parser.parse_args(argv)
    config = load_config()
    modes = list(VALID_MODES) if arguments.all_modes else [arguments.mode or config["data"]["mode"]]

    code = 0
    for mode in modes:
        local = copy.deepcopy(config)
        local["data"]["mode"] = mode
        print(f"Group audit of '{mode}':")
        try:
            report = run_audit(local)
        except FileNotFoundError as missing:
            print(f"  not audited: {missing}")
            code = DATA_MISSING
            continue
        path = write_report(report)
        print(f"  flagged: {'; '.join(report['flagged']) or 'none'}  ({report['seconds']} s)")
        print(f"  report: {path}")
    print(f"Summary: {write_summary()}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
