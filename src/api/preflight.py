"""Check that a machine has the files the API needs, before it is started.

Purpose: one command that says, in plain words, what is missing on a server (or a laptop)
    and how to fix it. Run it after setting a server up and before every demo.
Owner role: D (full-stack).
Implements: docs/SERVER_FILES.md (what the API needs, and how the files get there).

    python -m src.api.preflight             check this machine (a laptop)
    python -m src.api.preflight --server    stricter: this is the hosted site

Every line is OK, WARN or FAIL. The exit code is 1 when anything FAILs. The database
address is a secret and is never printed: only its kind (SQLite or PostgreSQL) is.

What is checked, for the data mode the API will run:
- the generated tables are on disk (`data/raw/synthetic_bd/strength_<s>/`);
- the database exists, holds the demo users, and holds the same merchants as the files;
- the trained model is there (`src/model/artifacts/<mode>/`);
- the model card was written for that very model (otherwise the API shows a warning);
- every data mode has a model card, so the dashboard's model-card tabs work;
- on the server only: the API runs the synthetic data, no raw public file is on the machine,
  and the hidden-truth file is gone.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from src.adapters.base import CONTRACT
from src.config import PROJECT_ROOT, VALID_MODES, get_database_url, load_config
from src.db import models as db
from src.db.load import DEMO_USERS, LOADABLE_MODES
from src.synth.paths import output_dir

OK, WARN, FAIL = "OK", "WARN", "FAIL"

# Folders a person downloads raw public data into. They must never be on a server.
RAW_PUBLIC_FOLDERS = ("taiwan_cc", "india_ltfs", "homecredit", "kiva")
LATENT_TRUTH_FILE = "_latent_truth.csv"
MODEL_FILES = ("model.joblib", "metadata.json")


@dataclass(frozen=True)
class Check:
    """One line of the report."""

    level: str
    name: str
    detail: str


def _model_version(folder: Path) -> str | None:
    try:
        return json.loads((folder / "metadata.json").read_text(encoding="utf-8"))["version_id"]
    except (OSError, ValueError, KeyError):
        return None


def _card_version(path: Path) -> str | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))["model_version"]
    except (OSError, ValueError, KeyError):
        return None


def check_mode(config: dict[str, Any], server: bool) -> list[Check]:
    mode = config["data"]["mode"]
    if mode in LOADABLE_MODES:
        return [Check(OK, "data mode", f"'{mode}' (the database holds this one)")]
    level = FAIL if server else WARN
    return [
        Check(
            level,
            "data mode",
            f"'{mode}' is a public data mode. Its raw files must not be on a server and the "
            "database holds only synthetic data. Set CREDLENS_DATA_MODE=synthetic_bd (or "
            "remove it); the dashboard still shows every mode's model card.",
        )
    ]


def check_tables(config: dict[str, Any]) -> list[Check]:
    folder = output_dir(config)
    missing = [t for t in CONTRACT if not (folder / f"{t}.csv").exists()]
    if missing:
        return [
            Check(
                FAIL,
                "generated tables",
                f"missing in {folder}: {', '.join(missing)}. "
                "Create them with: python tasks.py data",
            )
        ]
    return [Check(OK, "generated tables", f"all {len(CONTRACT)} tables in {folder}")]


def check_database(config: dict[str, Any], folder: Path | None = None) -> list[Check]:
    url = get_database_url(config)
    kind = "SQLite" if url.startswith("sqlite") else "PostgreSQL"
    engine = db.make_engine(url)
    try:
        if not inspect(engine).has_table("users"):
            empty = f"{kind}: it is empty. Create it with: python tasks.py data"
            return [Check(FAIL, "database", empty)]
        with Session(engine) as session:
            users = set(session.scalars(select(db.User.user_id)))
            merchants = session.scalar(select(func.count()).select_from(db.Merchant))
            decisions = session.scalar(select(func.count()).select_from(db.Decision))
    finally:
        engine.dispose()
    checks = [Check(OK, "database", f"{kind}; {merchants:,} merchants, {decisions:,} decisions")]
    missing_users = sorted({u["user_id"] for u in DEMO_USERS} - users)
    if missing_users:
        checks.append(
            Check(
                FAIL,
                "demo users",
                f"missing {', '.join(missing_users)}: python tasks.py data --reset-db",
            )
        )
    else:
        checks.append(Check(OK, "demo users", f"{len(DEMO_USERS)} demo users"))
    path = (folder or output_dir(config)) / "merchants.csv"
    if path.exists():
        in_files = len(pd.read_csv(path, usecols=["merchant_id"]))
        if in_files != merchants:
            checks.append(
                Check(
                    FAIL,
                    "database matches files",
                    f"{merchants:,} merchants in the database but {in_files:,} in the files. "
                    "The queue would not match the profiles: python tasks.py data --reset-db",
                )
            )
        else:
            checks.append(Check(OK, "database matches files", f"{in_files:,} merchants in both"))
    return checks


def check_model(config: dict[str, Any], root: Path, server: bool) -> list[Check]:
    mode = config["data"]["mode"]
    folder = root / "src" / "model" / "artifacts" / mode
    missing = [name for name in MODEL_FILES if not (folder / name).exists()]
    if missing:
        return [
            Check(
                FAIL,
                "trained model",
                f"missing in {folder}: {', '.join(missing)}. The trained model is committed in "
                "git: git pull, or git checkout -- src/model/artifacts/synthetic_bd/. "
                "Do not run `train` on a server: the model card describes one "
                "particular trained model.",
            )
        ]
    version = _model_version(folder)
    checks = [Check(OK, "trained model", f"version {version}")]
    card = root / "reports" / mode / "model_card.json"
    card_version = _card_version(card)
    if card_version is None:
        checks.append(Check(FAIL, "model card of this mode", f"{card} is missing or unreadable"))
    elif card_version != version:
        checks.append(
            Check(
                FAIL if server else WARN,
                "model card matches the model",
                f"the card was written for {card_version} but the model is {version}. The API "
                "puts a warning above the card's limits. Put the committed model back "
                "(git checkout -- src/model/artifacts/synthetic_bd/) so both are the same version.",
            )
        )
    else:
        checks.append(Check(OK, "model card matches the model", f"both are {version}"))
    return checks


def check_cards(root: Path) -> list[Check]:
    missing = [m for m in VALID_MODES if not (root / "reports" / m / "model_card.json").exists()]
    if missing:
        return [
            Check(
                FAIL,
                "model cards",
                f"missing for: {', '.join(missing)} (reports/<mode>/model_card.json is in git: "
                "git pull)",
            )
        ]
    return [Check(OK, "model cards", f"all {len(VALID_MODES)} data modes have one")]


def check_server_only(config: dict[str, Any], root: Path) -> list[Check]:
    checks: list[Check] = []
    present = []
    for name in RAW_PUBLIC_FOLDERS:
        folder = root / "data" / "raw" / name
        if folder.exists() and any(folder.iterdir()):
            present.append(name)
    if present:
        checks.append(
            Check(
                FAIL,
                "raw public data",
                f"found data/raw/{', data/raw/'.join(present)}. Raw public files (Kaggle, UCI, "
                "Kiva) may never be on a server. Delete the folder.",
            )
        )
    else:
        checks.append(Check(OK, "raw public data", "none on this machine"))
    truth = output_dir(config) / LATENT_TRUTH_FILE
    if truth.exists():
        checks.append(
            Check(
                WARN,
                "hidden-truth file",
                f"{truth} is for the generator's tests only. Delete it on the server.",
            )
        )
    else:
        checks.append(Check(OK, "hidden-truth file", "not on this machine"))
    return checks


def run_checks(
    config: dict[str, Any], root: Path = PROJECT_ROOT, server: bool = False
) -> list[Check]:
    """Every check, in the order they are printed."""
    checks = check_mode(config, server)
    if config["data"]["mode"] in LOADABLE_MODES:
        checks += check_tables(config)
        checks += check_database(config)
    checks += check_model(config, root, server)
    checks += check_cards(root)
    if server:
        checks += check_server_only(config, root)
    return checks


def format_report(checks: list[Check]) -> str:
    width = max(len(check.name) for check in checks)
    lines = [f"[{check.level:<4}] {check.name:<{width}}  {check.detail}" for check in checks]
    failed = sum(check.level == FAIL for check in checks)
    warned = sum(check.level == WARN for check in checks)
    lines.append("")
    lines.append(
        "Ready: the API can be started."
        if not failed
        else f"NOT READY: {failed} check(s) failed. Fix the FAIL lines, then run this again."
    )
    if warned:
        lines.append(f"{warned} warning(s): read them before a demo.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check that the API's files are in place.")
    parser.add_argument("--server", action="store_true", help="stricter checks for the hosted site")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    checks = run_checks(load_config(), server=args.server)
    print(format_report(checks))
    return 1 if any(check.level == FAIL for check in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
