"""Pack the two things the server cannot make for itself into one file, ready to copy.

Purpose: the server gets the code from git and makes the data with `python tasks.py data`. It
    cannot make (1) the built dashboard (needs Node.js, built on a laptop) or (2) the trained
    model (the model card and the test-month results describe one particular trained model, so
    the server must use that one, not train its own). This script puts both in one archive.
Owner role: D (full-stack).
Implements: docs/SERVER_FILES.md and docs/DEPLOY.md.

Run it on the laptop that trained the model the cards describe (the lead's), after the dashboard
is built (cd web && npm ci && npm run build):

    python deploy/make_bundle.py                writes credlens-upload.tar.gz
    python deploy/make_bundle.py --allow-other-model   (only if you know the card is outdated)

It refuses to pack a model that the committed model card was not written for, because the
dashboard would then show a warning above the card's limits. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODE = "synthetic_bd"
MODEL_FILES = ("model.joblib", "metadata.json")
DEFAULT_OUTPUT = ROOT / "credlens-upload.tar.gz"


class BundleError(Exception):
    """Something is missing or does not match; the message says how to fix it."""


def model_version(root: Path) -> str:
    folder = root / "src" / "model" / "artifacts" / MODE
    missing = [name for name in MODEL_FILES if not (folder / name).exists()]
    if missing:
        raise BundleError(
            f"No trained model in {folder} (missing {', '.join(missing)}). "
            "Run this on the laptop that trained it, or: python tasks.py train"
        )
    return json.loads((folder / "metadata.json").read_text(encoding="utf-8"))["version_id"]


def card_version(root: Path) -> str | None:
    path = root / "reports" / MODE / "model_card.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))["model_version"]
    except (OSError, ValueError, KeyError):
        return None


def files_to_pack(root: Path, allow_other_model: bool = False) -> list[Path]:
    """The files for the archive (paths below `root`), or BundleError."""
    dist = root / "web" / "dist"
    if not (dist / "index.html").exists():
        raise BundleError("The dashboard is not built. Run: cd web && npm ci && npm run build")
    version = model_version(root)
    card = card_version(root)
    if card != version and not allow_other_model:
        raise BundleError(
            f"The model here is {version} but the model card was written for {card}. "
            "Pack the model the card describes (the lead's laptop), or pull the latest "
            "reports, or, only if you are sure, use --allow-other-model."
        )
    files = sorted(path for path in dist.rglob("*") if path.is_file())
    folder = root / "src" / "model" / "artifacts" / MODE
    return files + [folder / name for name in MODEL_FILES]


def make_bundle(root: Path, output: Path, allow_other_model: bool = False) -> list[str]:
    """Write the archive; return the names inside it."""
    names = []
    with tarfile.open(output, "w:gz") as archive:
        for path in files_to_pack(root, allow_other_model):
            name = path.relative_to(root).as_posix()
            archive.add(path, arcname=name)
            names.append(name)
    return names


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pack the dashboard and the trained model.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--allow-other-model", action="store_true")
    args = parser.parse_args(argv)
    try:
        names = make_bundle(ROOT, args.output, args.allow_other_model)
    except BundleError as error:
        print(f"NOT PACKED: {error}")
        return 1
    size = args.output.stat().st_size / (1024 * 1024)
    print(f"Wrote {args.output} ({size:.1f} MB, {len(names)} files):")
    print(f"  model {model_version(ROOT)} and the built dashboard")
    print("Copy it to the server as described in docs/DEPLOY.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
