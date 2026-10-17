"""A small batch of NEW merchants for the live import demo, as a lender's export would look.

Purpose: show the judges the whole path on a file: upload -> contract check -> load ->
    the new merchants appear in the review queue with a score, reasons and a band.
Owner role: A (lead).
Implements: PROJECT_BRIEF section 18, item 45 (live import demo).

How it is made:
1. A small synthetic world is generated with its own seed (same generator, same settings).
2. Its merchants are scored by the SAVED model (nothing is trained), as of the same "today"
   as the demo data in the database, exactly as the API will score them after the import.
3. Five merchants are picked, one of each kind the demo should show: Strong; Needs more info
   (thin file); Review with a low score; no valid consent (no score); and one with no
   delivery (REDX) records at all.
4. Every id is renamed so nothing clashes with the database: merchants D00001..D00005,
   other records "D-" + their old id.
5. Three rows are deliberately wrong, so the check has something to report:
   - merchants.csv repeats M000031, already in the database (an import never overwrites);
   - purchases.csv has a row with an impossible date;
   - deliveries.csv has a row with an unknown status.

Output (data/demo/): one CSV per table, the same files as `credlens_demo_bundle.zip`, and
`EXPECTED.md` with what each merchant should show after the load.

Run it: python -m src.synth.demo_batch
"""

from __future__ import annotations

import argparse
import copy
import io
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd

from src.adapters import get_adapter
from src.adapters.base import CONTRACT
from src.config import PROJECT_ROOT, load_config
from src.model.dataset import build_dataset
from src.model.explain import calibrated_probability
from src.model.labels import LABELLED, latest_date
from src.model.score import score_table
from src.model.train import load_model
from src.synth.generate import build_tables

OUT_DIR = PROJECT_ROOT / "data" / "demo"
ZIP_NAME = "credlens_demo_bundle.zip"
DEMO_SEED = 2027
DEMO_WORLD_SIZE = 600
ORDER = ("merchants", "loans", "purchases", "deliveries", "payments", "questionnaire", "consents")
ID_COLUMNS = {
    "purchases": "purchase_id",
    "deliveries": "delivery_id",
    "payments": "payment_id",
    "loans": "loan_id",
    "consents": "consent_id",
}
KINDS = (
    ("strong", "Strong: a high score with enough evidence"),
    ("needs_more_info", "Needs more info: a thin file (coverage under the line)"),
    ("low_score", "Review with a low score (under the warning line)"),
    ("no_consent", "No valid consent: listed, but no score and no decision"),
    ("no_deliveries", "No REDX delivery records: lower coverage, never a lower score by itself"),
)


def _scored_world(config: dict[str, Any], as_of: pd.Timestamp) -> tuple[dict, pd.DataFrame]:
    """A small generated world and, per merchant, its latest loan scored as the API would."""
    local = copy.deepcopy(config)
    local["seed"] = DEMO_SEED
    local["data"]["n_merchants"] = DEMO_WORLD_SIZE
    tables = build_tables(local, local["data"]["delivery_signal_strength"])[0]
    dataset = build_dataset(tables, local, as_of=as_of, mode="synthetic_bd")
    latest = dataset.sort_values(["cutoff_date", "loan_id"]).groupby("merchant_id").tail(1)
    latest = latest.set_index("merchant_id")
    latest = latest[latest["label_status"] != LABELLED]  # a loan waiting for a decision
    saved = load_model("synthetic_bd")
    scored = latest[latest["consent_valid"]]
    table = score_table(calibrated_probability(saved, scored), scored, local, "synthetic_bd")
    latest = latest.join(table[["score", "coverage", "band", "low_score_warning"]])
    has_parcels = set(tables["deliveries"]["merchant_id"])
    latest["has_deliveries"] = latest.index.isin(list(has_parcels))
    return tables, latest.sort_index()


def _pick(latest: pd.DataFrame) -> dict[str, str]:
    """One merchant of each kind (the first by id, so the same every run)."""
    rules = {
        "strong": (latest["band"] == "Strong") & latest["has_deliveries"],
        "needs_more_info": (latest["band"] == "Needs more info") & latest["has_deliveries"],
        "low_score": (latest["band"] == "Review") & (latest["low_score_warning"] == True)  # noqa: E712
        & latest["has_deliveries"],
        "no_consent": ~latest["consent_valid"].astype(bool),
        "no_deliveries": latest["consent_valid"].astype(bool) & ~latest["has_deliveries"]
        & latest["band"].isin(["Strong", "Review"]),
    }
    picked: dict[str, str] = {}
    for kind, rule in rules.items():
        choices = [m for m in latest.index[rule.fillna(False)] if m not in picked.values()]
        if not choices:
            raise RuntimeError(f"No merchant of kind '{kind}' in the demo world; change the seed.")
        picked[kind] = choices[0]
    return picked


def rename_merchants(
    tables: dict[str, pd.DataFrame], merchant_ids: list[str]
) -> dict[str, pd.DataFrame]:
    """Only these merchants' rows, every id renamed so nothing clashes with the database.

    The merchants become D00001, D00002, ... in the order given; every other id gets "D-".
    """
    new_ids = {old: f"D{n:05d}" for n, old in enumerate(merchant_ids, start=1)}
    out: dict[str, pd.DataFrame] = {}
    for name in ORDER:
        frame = tables[name][tables[name]["merchant_id"].isin(list(new_ids))].copy()
        frame["merchant_id"] = frame["merchant_id"].map(new_ids)
        if name in ID_COLUMNS:
            column = ID_COLUMNS[name]
            frame[column] = "D-" + frame[column].astype(str)
        if name == "payments":
            frame["loan_id"] = "D-" + frame["loan_id"].astype(str)
        out[name] = frame[CONTRACT[name]].reset_index(drop=True)
    return out


def _add_mistakes(tables: dict[str, pd.DataFrame], existing: pd.Series) -> None:
    """Three deliberate errors for the check to find (see the module docstring)."""
    copy_row = existing.copy()
    tables["merchants"] = pd.concat([tables["merchants"], copy_row.to_frame().T], ignore_index=True)
    first = tables["purchases"].iloc[0].copy()
    first["purchase_id"] = "D-BAD-DATE"
    first["purchase_date"] = "2026-13-40"
    tables["purchases"] = pd.concat([tables["purchases"], first.to_frame().T], ignore_index=True)
    parcel = tables["deliveries"].iloc[0].copy()
    parcel["delivery_id"] = "D-BAD-STATUS"
    parcel["status"] = "lost_in_space"
    tables["deliveries"] = pd.concat([tables["deliveries"], parcel.to_frame().T], ignore_index=True)


def build_demo_batch(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Make the demo batch. Returns the tables, the picks and the expected outcome per merchant."""
    config = config or load_config()
    main = get_adapter(config).load_all()
    as_of = latest_date(main)
    world, latest = _scored_world(config, as_of)
    picked = _pick(latest)
    tables = rename_merchants(world, list(picked.values()))
    if latest_date(tables) > as_of:
        # The API reads "today" from the database: a later row would move it for everyone.
        raise RuntimeError("The demo batch has records after the demo data's last day.")
    existing = main["merchants"][main["merchants"]["merchant_id"] == "M000031"].iloc[0]
    _add_mistakes(tables, existing[CONTRACT["merchants"]])
    expected = []
    for n, (kind, old) in enumerate(picked.items(), start=1):
        row = latest.loc[old]
        expected.append(
            {
                "merchant_id": f"D{n:05d}",
                "kind": dict(KINDS)[kind],
                "consent": bool(row["consent_valid"]),
                "score": None if pd.isna(row["score"]) else int(row["score"]),
                "coverage": None if pd.isna(row["coverage"]) else float(row["coverage"]),
                "band": None if pd.isna(row["band"]) else str(row["band"]),
                "pending_since": str(pd.Timestamp(row["cutoff_date"]).date()),
            }
        )
    return {"tables": tables, "expected": expected, "as_of": str(as_of.date())}


def _csv(frame: pd.DataFrame) -> str:
    buffer = io.StringIO()
    frame.to_csv(buffer, index=False, lineterminator="\n")
    return buffer.getvalue()


def bundle_zip(tables: dict[str, pd.DataFrame]) -> bytes:
    """The tables as one zip of CSV files: the upload of the import page."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in ORDER:
            if name in tables:
                archive.writestr(f"{name}.csv", _csv(tables[name]))
    return buffer.getvalue()


def write_demo_batch(out_dir: Path = OUT_DIR, config: dict[str, Any] | None = None) -> Path:
    """Write the CSVs, the zip and EXPECTED.md. Returns the zip's path."""
    batch = build_demo_batch(config)
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / ZIP_NAME
    for name in ORDER:
        text = _csv(batch["tables"][name])
        (out_dir / f"{name}.csv").write_text(text, encoding="utf-8", newline="\n")
    zip_path.write_bytes(bundle_zip(batch["tables"]))
    lines = [
        "# Demo batch: what to expect after the import",
        "",
        f"Written by `python -m src.synth.demo_batch`. Scored by the saved model as of "
        f"{batch['as_of']}, the last day of the demo data, exactly as the API scores them "
        "after the load. Synthetic data, not real merchants.",
        "",
        "| Merchant | Kind | Consent | Score | Coverage | Band | Waiting since |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in batch["expected"]:
        coverage = "-" if row["coverage"] is None else f"{row['coverage']:.0%}"
        lines.append(
            f"| {row['merchant_id']} | {row['kind']} | {'valid' if row['consent'] else 'none'} "
            f"| {row['score'] if row['score'] is not None else '-'} | {coverage} "
            f"| {row['band'] or 'no score'} | {row['pending_since']} |"
        )
    rows = {name: len(batch["tables"][name]) for name in ORDER}
    lines += [
        "",
        "Deliberate mistakes the check must report (the rest loads):",
        "- merchants.csv: M000031 is already in the database (an import never overwrites).",
        "- purchases.csv: D-BAD-DATE has the impossible date 2026-13-40.",
        "- deliveries.csv: D-BAD-STATUS has the unknown status 'lost_in_space'.",
        "",
        "Rows per file: " + ", ".join(f"{name} {count}" for name, count in rows.items()) + ".",
        "",
    ]
    (out_dir / "EXPECTED.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return zip_path


def main(argv: list[str] | None = None) -> int:
    """Command line: write the demo batch to data/demo/."""
    parser = argparse.ArgumentParser(description="Write the live import demo batch.")
    parser.add_argument("--out", type=Path, default=OUT_DIR, help="folder to write to")
    arguments = parser.parse_args(argv)
    path = write_demo_batch(arguments.out)
    print(f"Demo batch written: {path}")
    print((arguments.out / "EXPECTED.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
