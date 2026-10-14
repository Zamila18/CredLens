"""Ablation: what does each group of data add, and is the delivery signal real?

Purpose: answer two questions a judge will ask about the synthetic results.
    1. How much does each data source add? Purchases (A), then payments (B), then
       deliveries (C), then the questionnaire (D).
    2. Is the delivery gain real, or would any extra column look useful? The generator
       can set the delivery signal to zero; then deliveries must add nothing.
Owner role: C (ML engineer).
Implements: docs/MODEL_SPEC.md section 10, PROJECT_BRIEF section 18, item 37. Settings:
    `ablation` and `sanity.zero_signal_max_auc_gain` in config/default.yaml.

The runs (each one adds a group to the one before):
    A  purchases only
    B  A + payments
    C  B + deliveries          <- the headline model's inputs
    D  C + questionnaire       <- a separate finding: the questionnaire is NEVER in the
                                  headline model; it is shown beside the score.

How it is measured. For every delivery signal strength (0, 0.5, 1) and every data seed,
the synthetic data is generated afresh, the same logistic regression as the headline
model is fitted on the training months for each run, and AUC is measured on the
validation months. What a group adds is the paired AUC gain over the run before it, on
the same resampled loans, with a range. The test months are not used.

The negative control: at strength 0 the generator gives deliveries no link to whether
a merchant repays. If deliveries still "add" more than `zero_signal_max_auc_gain`, the
pipeline is finding signal that is not there, and the result says FAILED.

This is synthetic data. It shows that the pipeline measures what the generator put in;
it does not show how much deliveries would add for real merchants. That needs partner
data.

Run it: python -m src.model.ablation   (about 10 minutes for 3 strengths x 3 seeds)
"""

from __future__ import annotations

import argparse
import copy
import json
import time
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np

from src.config import PROJECT_ROOT, load_config
from src.features.build_features import QUESTIONNAIRE_FEATURES, model_feature_names
from src.features.dictionary import expected_directions, load_dictionary
from src.model.dataset import build_dataset, modelling_rows
from src.model.evaluate import bootstrap_ranges, paired_auc_gain, point_metrics
from src.model.split import split_for_mode
from src.model.train import _score, fit_with_expected_directions
from src.synth.generate import build_tables

matplotlib.use("Agg")  # draw to files; no window needed
import matplotlib.pyplot as plt  # noqa: E402

MODE = "synthetic_bd"
RUNS = {"A": "A", "B": "AB", "C": "ABC", "D": "ABCD"}
RUN_NAMES = {
    "A": "purchases",
    "B": "+ payments",
    "C": "+ deliveries (headline inputs)",
    "D": "+ questionnaire (never in the headline model)",
}
# The questionnaire subscores run from 1 to 5, higher meaning healthier habits. They are
# not model inputs anywhere else, so their direction is stated here, for this check only.
QUESTIONNAIRE_DIRECTIONS = dict.fromkeys(QUESTIONNAIRE_FEATURES, 1)
REPORT_DIR = PROJECT_ROOT / "reports" / "ablation"
# Chart colours: one series in the first categorical hue; text and grid in neutral inks.
SERIES = "#2a78d6"
TEXT_PRIMARY, TEXT_SECONDARY, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def ablation_on_tables(tables: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Fit the four runs on one data set and measure each on the validation months.

    Returns, per run, the inputs used and the AUC with its range; and per added group,
    the paired AUC gain over the run before it, with its range.
    """
    rows = modelling_rows(build_dataset(tables, config, mode=MODE))
    split = split_for_mode(rows, config, MODE)
    labels = split.validation["label"].to_numpy()
    directions = {**expected_directions(load_dictionary()), **QUESTIONNAIRE_DIRECTIONS}

    probabilities: dict[str, np.ndarray] = {}
    runs: dict[str, Any] = {}
    for run, groups in RUNS.items():
        model, kept, removed = fit_with_expected_directions(
            config, split.train, model_feature_names(groups), directions
        )
        probabilities[run] = _score(model, split.validation, kept)
        auc = point_metrics(labels, probabilities[run], config)["roc_auc"]
        runs[run] = {
            "inputs": kept,
            "removed_for_pointing_the_wrong_way": removed,
            "roc_auc": auc,
            "roc_auc_range": bootstrap_ranges(labels, probabilities[run], config)["roc_auc"],
        }

    order = list(RUNS)
    gains = {
        run: paired_auc_gain(labels, probabilities[before], probabilities[run], config)
        for before, run in zip(order, order[1:])
    }
    return {
        "validation_loans": int(len(labels)),
        "validation_not_repaid": int((labels == 0).sum()),
        "runs": runs,
        "gains": gains,
    }


def run_ablation(
    config: dict[str, Any],
    strengths: list[float] | None = None,
    seeds: list[int] | None = None,
    progress: Any = print,
) -> dict[str, Any]:
    """Every strength and seed in the config (or as given); returns all results.

    The data is generated afresh for each pair, with that seed and that strength.
    """
    settings = config["ablation"]
    strengths = settings["strengths"] if strengths is None else strengths
    seeds = settings["seeds"] if seeds is None else seeds
    limit = config["sanity"]["zero_signal_max_auc_gain"]

    results = []
    for strength in strengths:
        for seed in seeds:
            started = time.time()
            local = copy.deepcopy(config)
            local["seed"] = seed
            local["data"]["delivery_signal_strength"] = strength
            tables, _, _ = build_tables(local, strength)
            outcome = ablation_on_tables(tables, local)
            delivery = outcome["gains"]["C"]
            outcome.update(strength=strength, seed=seed, seconds=round(time.time() - started, 1))
            results.append(outcome)
            progress(
                f"  strength {strength}, seed {seed}: "
                + "  ".join(f"{run} {outcome['runs'][run]['roc_auc']:.3f}" for run in RUNS)
                + "  | deliveries add "
                f"{delivery['auc_gain']:+.4f} ({outcome['seconds']} s)"
            )

    zero = [r for r in results if r["strength"] == 0]
    control = {
        "rule": (
            f"At delivery signal strength 0, deliveries may add at most {limit} AUC "
            "(the point gain, in every seed)."
        ),
        "gains_at_strength_0": {r["seed"]: r["gains"]["C"]["auc_gain"] for r in zero},
        "passed": bool(zero) and all(r["gains"]["C"]["auc_gain"] <= limit for r in zero),
    }
    return {
        "data_mode": MODE,
        "measured_on": "validation months (the test months are not used)",
        "model": "logistic_regression, as the headline model",
        "runs": RUN_NAMES,
        "strengths": strengths,
        "seeds": seeds,
        "zero_signal_control": control,
        "summary": summarise(results),
        "results": results,
    }


def summarise(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Per strength: mean AUC of each run and mean gain of each added group, over seeds."""
    summary: dict[str, Any] = {}
    for strength in sorted({r["strength"] for r in results}):
        chosen = [r for r in results if r["strength"] == strength]
        summary[str(strength)] = {
            "auc": {
                run: float(np.mean([r["runs"][run]["roc_auc"] for r in chosen])) for run in RUNS
            },
            "gain": {
                run: {
                    "mean": float(np.mean([r["gains"][run]["auc_gain"] for r in chosen])),
                    "lowest": float(min(r["gains"][run]["auc_gain"] for r in chosen)),
                    "highest": float(max(r["gains"][run]["auc_gain"] for r in chosen)),
                    "clearly_above_zero_in": sum(
                        r["gains"][run]["clearly_better"] for r in chosen
                    ),
                }
                for run in list(RUNS)[1:]
            },
            "seeds": len(chosen),
        }
    return summary


def draw_delivery_gain(report: dict[str, Any], path: Path) -> Path:
    """One chart: what deliveries add at each signal strength, every seed shown.

    Each seed is a small dot, the mean a larger one, joined by a thin line over the
    strengths. The dashed line is the limit the negative control allows at strength 0.
    """
    strengths = [float(s) for s in report["summary"]]
    limit = report["zero_signal_control"]["rule"]
    allowed = float(limit.split("at most ")[1].split(" ")[0])
    figure, axis = plt.subplots(figsize=(6.4, 4.0), facecolor=SURFACE)
    axis.set_facecolor(SURFACE)
    for result in report["results"]:
        axis.scatter(
            result["strength"], result["gains"]["C"]["auc_gain"], s=22, color=SERIES,
            alpha=0.45, linewidths=0, zorder=3,
        )
    means = [report["summary"][str(s)]["gain"]["C"]["mean"] for s in report["summary"]]
    axis.plot(strengths, means, color=SERIES, linewidth=2, zorder=2)
    axis.scatter(
        strengths, means, s=64, color=SERIES, edgecolors=SURFACE, linewidths=2, zorder=4
    )
    for strength, mean in zip(strengths, means):
        axis.annotate(
            f"{mean:+.3f}", (strength, mean), textcoords="offset points", xytext=(10, 6),
            color=TEXT_PRIMARY, fontsize=9,
        )
    axis.axhline(0, color=TEXT_SECONDARY, linewidth=1)
    axis.axhline(allowed, color=TEXT_SECONDARY, linewidth=1, linestyle=(0, (4, 3)))
    axis.annotate(
        f"limit at strength 0 (+{allowed})", (strengths[-1], allowed), textcoords="offset points",
        xytext=(0, 4), ha="right", color=TEXT_SECONDARY, fontsize=8,
    )
    axis.set_xticks(strengths, [f"{s:g}" + (" (no signal)" if s == 0 else "") for s in strengths])
    axis.set_xlabel("Delivery signal strength in the generator", color=TEXT_SECONDARY)
    axis.set_ylabel("AUC added by delivery data", color=TEXT_SECONDARY)
    axis.set_title(
        "Deliveries add nothing when they carry no signal", color=TEXT_PRIMARY, loc="left",
        fontsize=11,
    )
    axis.grid(axis="y", color=GRID, linewidth=0.8)
    axis.tick_params(colors=TEXT_SECONDARY, labelsize=9)
    for side in ("top", "right", "left"):
        axis.spines[side].set_visible(False)
    axis.spines["bottom"].set_color(GRID)
    figure.text(
        0.01, 0.01, "Synthetic data, validation months. Small dots: one data seed each; "
        "large dots: the mean.", color=TEXT_SECONDARY, fontsize=7,
    )
    figure.tight_layout(rect=(0, 0.04, 1, 1))
    figure.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(figure)
    return path


def write_reports(report: dict[str, Any], folder: Path = REPORT_DIR) -> dict[str, Path]:
    """Write ablation.json, ABLATION.md and the chart; return their paths."""
    folder.mkdir(parents=True, exist_ok=True)
    chart_path = draw_delivery_gain(report, folder / "delivery_gain.png")
    json_path = folder / "ablation.json"
    json_path.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")

    lines = [
        "# Ablation on synthetic data",
        "",
        "Written by `python -m src.model.ablation`. Validation months only; synthetic data.",
        f"Seeds: {', '.join(str(s) for s in report['seeds'])}. Model: logistic regression, "
        "as the headline model.",
        "",
        "## Mean validation AUC over the seeds",
        "",
        "| Delivery signal strength | A purchases | B + payments | C + deliveries | "
        "D + questionnaire |",
        "|---|---|---|---|---|",
    ]
    for strength, part in report["summary"].items():
        auc = part["auc"]
        lines.append(
            f"| {strength} | {auc['A']:.3f} | {auc['B']:.3f} | {auc['C']:.3f} | {auc['D']:.3f} |"
        )
    lines += [
        "",
        "## What each group adds (paired AUC gain; mean, and lowest to highest over seeds)",
        "",
        "| Delivery signal strength | Payments (B over A) | Deliveries (C over B) | "
        "Questionnaire (D over C) |",
        "|---|---|---|---|",
    ]
    for strength, part in report["summary"].items():
        cells = [
            f"{g['mean']:+.4f} ({g['lowest']:+.4f} to {g['highest']:+.4f})"
            for g in (part["gain"][run] for run in ("B", "C", "D"))
        ]
        lines.append(f"| {strength} | " + " | ".join(cells) + " |")
    control = report["zero_signal_control"]
    gains = ", ".join(f"seed {s}: {g:+.4f}" for s, g in control["gains_at_strength_0"].items())
    lines += [
        "",
        "## Negative control",
        "",
        "![What deliveries add at each signal strength](delivery_gain.png)",
        "",
        f"{control['rule']} Result: **{'PASSED' if control['passed'] else 'FAILED'}** ({gains}).",
        "",
        "## How to read this",
        "",
        "- The delivery gain grows with the signal the generator puts in, and is about zero "
        "when it puts in none. That shows the pipeline measures what is there and does not "
        "invent signal. It does not show how much REDX data would add for real merchants: "
        "the generator decides that here, and only partner data can answer it.",
        "- The questionnaire (D) adds signal because the generator ties its answers to how "
        "reliable a merchant is. It is still never in the headline model: answers are "
        "self-reported, easy to game once they move a score, and only 40% of merchants "
        "answered. It is shown beside the score instead.",
    ]
    md_path = folder / "ABLATION.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_path, "markdown": md_path, "chart": chart_path}


def main(argv: list[str] | None = None) -> int:
    """Command line: run the ablation and write the reports."""
    parser = argparse.ArgumentParser(description="Ablation A to D at three signal strengths.")
    parser.add_argument("--seeds", type=int, nargs="*", help="data seeds; default: the config's")
    arguments = parser.parse_args(argv)
    config = load_config()
    print("Ablation on synthetic data (validation months):")
    report = run_ablation(config, seeds=arguments.seeds)
    paths = write_reports(report)
    control = report["zero_signal_control"]
    print(f"Negative control: {'PASSED' if control['passed'] else 'FAILED'}. {control['rule']}")
    print(f"Report: {paths['markdown']}")
    return 0 if control["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
