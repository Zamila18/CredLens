"""Cross-platform task runner for CredLens.

Purpose: one command per job, the same on Windows, Mac and Linux.
Owner role: A (lead) keeps this file; other roles ask for changes.
Implements: the "Commands" list in CLAUDE.md and PROJECT_BRIEF section 12.

Usage:
    python tasks.py setup
    python tasks.py data [--mode <mode>] [--strength 0|0.5|1] [--all-strengths] [--reset-db]
    python tasks.py train | api | app | test | lint | backup

This file uses the standard library only, so it runs before the virtual
environment exists. Every other command runs inside `.venv`.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"

# Kept in step with VALID_MODES in src/config.py. It is repeated here because
# this file must not import anything outside the standard library.
VALID_MODES = ("synthetic_bd", "kiva_asia", "taiwan_cc", "india_ltfs", "homecredit")


def venv_python() -> Path:
    """Return the path of the Python inside .venv for this operating system."""
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def run(args: list[str], env: dict[str, str] | None = None) -> int:
    """Run a command from the project root and return its exit code."""
    print("> " + " ".join(args))
    return subprocess.call(args, cwd=ROOT, env=env)


def run_in_venv(args: list[str], env: dict[str, str] | None = None) -> int:
    """Run `python <args>` with the virtual environment's Python."""
    python = venv_python()
    if not python.exists():
        print("No .venv found. Run this first: python tasks.py setup")
        return 1
    return run([str(python), *args], env=env)


def not_implemented(task: str, phase: str) -> int:
    """Say plainly that a task has no logic yet. Exit code 0 by design."""
    print(f"{task}: not implemented yet ({phase}).")
    return 0


def task_setup(_: argparse.Namespace) -> int:
    """Create .venv and install the pinned dependencies."""
    if not venv_python().exists():
        print(f"Creating virtual environment in {VENV_DIR} ...")
        venv.EnvBuilder(with_pip=True).create(VENV_DIR)
    return run_in_venv(["-m", "pip", "install", "-r", "requirements.txt"])


def task_data(args: argparse.Namespace) -> int:
    """Generate the synthetic tables, or say what a public data mode still needs."""
    if args.mode not in (None, "synthetic_bd"):
        return not_implemented(f"data (mode: {args.mode})", "Phase 7 public-data adapters")
    command = ["-m", "src.synth.generate"]
    if args.all_strengths:
        command.append("--all-strengths")
    elif args.strength is not None:
        command += ["--strength", str(args.strength)]
    code = run_in_venv(command)
    if code != 0:
        return code
    # Load the strength set in the config into the database. The loader refuses to
    # overwrite existing data unless --reset-db is given.
    return run_in_venv(["-m", "src.db.load"] + (["--reset"] if args.reset_db else []))


PUBLIC_MODES = ("taiwan_cc", "india_ltfs", "homecredit", "kiva_asia")


def task_train(args: argparse.Namespace) -> int:
    """Build features, train, evaluate on the validation period, save the model and report."""
    if args.all_modes:
        for mode in ("synthetic_bd", *PUBLIC_MODES):
            code = run_in_venv(["-m", "src.model.train", "--mode", mode])
            if code != 0:
                return code
        return 0
    command = ["-m", "src.model.train"]
    if args.mode:
        command += ["--mode", args.mode]
    return run_in_venv(command)


def task_api(_: argparse.Namespace) -> int:
    """Run the FastAPI app on port 8000."""
    return run_in_venv(["-m", "uvicorn", "src.api.main:app", "--port", "8000"])


def task_app(_: argparse.Namespace) -> int:
    """Run the React dashboard dev server (Vite, port 5173). Needs Node.js."""
    if not (ROOT / "web" / "package.json").exists():
        return not_implemented("app", "Phase 10 creates the React app in web/")
    npm = "npm.cmd" if os.name == "nt" else "npm"
    return subprocess.call([npm, "run", "dev"], cwd=ROOT / "web")


def task_test(_: argparse.Namespace) -> int:
    """Run the tests."""
    return run_in_venv(["-m", "pytest"])


def task_lint(_: argparse.Namespace) -> int:
    """Run ruff over the project."""
    return run_in_venv(["-m", "ruff", "check", "."])


def task_backup(_: argparse.Namespace) -> int:
    """Copy the SQLite file with a timestamp, or export tables from Postgres."""
    return run_in_venv(["-m", "src.db.backup"])


def build_parser() -> argparse.ArgumentParser:
    """Describe the available tasks for --help."""
    parser = argparse.ArgumentParser(description="CredLens task runner")
    tasks = parser.add_subparsers(dest="task", required=True)

    setup = tasks.add_parser("setup", help="create .venv and install dependencies")
    setup.set_defaults(func=task_setup)

    data = tasks.add_parser("data", help="generate or load data and load the database")
    data.add_argument("--mode", choices=VALID_MODES, help="data mode; default is the one in config")
    data.add_argument(
        "--strength", type=float, choices=(0.0, 0.5, 1.0), help="delivery signal strength"
    )
    data.add_argument("--all-strengths", action="store_true", help="generate 0, 0.5 and 1")
    data.add_argument(
        "--reset-db",
        action="store_true",
        help="wipe the database first, including decisions and the audit log",
    )
    data.set_defaults(func=task_data)

    train = tasks.add_parser("train", help="features, training, calibration, reports")
    train.add_argument("--mode", choices=VALID_MODES, help="data mode; default: the config's")
    train.add_argument(
        "--all-modes", action="store_true", help="train the synthetic data and all public modes"
    )
    train.set_defaults(func=task_train)
    tasks.add_parser("api", help="run FastAPI on :8000").set_defaults(func=task_api)
    tasks.add_parser("app", help="run the React dashboard on :5173").set_defaults(func=task_app)
    tasks.add_parser("test", help="run pytest").set_defaults(func=task_test)
    tasks.add_parser("lint", help="run ruff").set_defaults(func=task_lint)
    tasks.add_parser("backup", help="back up the database").set_defaults(func=task_backup)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse the command line and run the chosen task."""
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
