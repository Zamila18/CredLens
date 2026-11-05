"""Measure how well receipts are read, and how many mistakes the built-in checks catch.

Run: python -m src.receipts.ocr_check [--dev N] [--held-out N]
Purpose: a number to trust, or not. Test receipts are drawn from known specs (src/receipts/
    samples.py), damaged like phone photos, read by the real OCR engine and parsed. For each
    receipt we compare line amounts, the total, the date, the memo number and the supplier with
    the truth, and we count how many wrong values carried a flag a person would see.
    "Silent" errors (wrong and unflagged) are the dangerous ones: they are reported first.
    Parsing was tuned on the development set only; the held-out set is read once.
Owner role: C (assessment).
Implements: "verify the OCR to work properly" of the Records Desk redesign.

Printed memos only. Handwriting is not measured here because the engine does not support it;
the product sends such receipts to manual typing.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from datetime import date
from pathlib import Path

from src.extraction.engine import EasyOcrEngine
from src.receipts import parse, prepare, samples

REPORT = Path(__file__).resolve().parents[2] / "reports" / "receipt_ocr_check.md"
DAMAGES = ("clean", "tilt", "blur", "dim", "photo")
TODAY = date(2026, 11, 5)


def _close(a, b) -> bool:
    return a is not None and b is not None and abs(float(a) - float(b)) < 0.5


def score(sample: samples.Sample, read: parse.ParsedReceipt) -> dict:
    truth = sample.lines
    out = {
        "lines_truth": len(truth),
        "lines_read": len(read.lines),
        "line_count_ok": len(truth) == len(read.lines),
        "amount_ok": 0,
        "amount_wrong_flagged": 0,
        "amount_wrong_silent": 0,
        "qty_ok": 0,
        "total_ok": _close(read.stated_total.value, sample.total),
        "date_ok": read.receipt_date.value == sample.day,
        "memo_ok": (read.memo_no.value or "") == sample.memo_no,
        "supplier_ok": (read.supplier.value or "").replace(" ", "")
        == sample.supplier.replace(" ", ""),
    }
    note_flag = any(n.startswith("!") for n in read.notes)
    for i, want in enumerate(truth):
        got = read.lines[i] if i < len(read.lines) else None
        if got is None:
            out["amount_wrong_flagged"] += 1  # a missing line shows as a count mismatch note
            continue
        if _close(got.amount.value, want.amount):
            out["amount_ok"] += 1
        elif got.flags or note_flag:
            out["amount_wrong_flagged"] += 1
        else:
            out["amount_wrong_silent"] += 1
        if _close(got.quantity.value, want.quantity):
            out["qty_ok"] += 1
    return out


def run(count: int, seed: int, engine: EasyOcrEngine) -> tuple[list[dict], float]:
    rng = random.Random(seed)
    rows = []
    started = time.time()
    for i in range(count):
        language = "en" if i % 2 == 0 else "bn"
        spec = samples.make_spec(rng, language, TODAY)
        kind = DAMAGES[(i // 2) % len(DAMAGES)]
        image = samples.damage(samples.render(spec), kind, rng)
        boxes = engine.read(prepare.straighten(image))
        read = parse.parse_receipt(boxes, "purchase", TODAY)
        row = score(spec, read)
        row.update(language=language, damage=kind)
        rows.append(row)
        print(
            f"{seed}:{i} {language}/{kind} amounts {row['amount_ok']}/{row['lines_truth']} "
            f"silent {row['amount_wrong_silent']}",
            flush=True,
        )
    return rows, (time.time() - started) / max(count, 1)


def summarise(rows: list[dict]) -> dict:
    n_lines = sum(r["lines_truth"] for r in rows)
    ok = sum(r["amount_ok"] for r in rows)
    flagged = sum(r["amount_wrong_flagged"] for r in rows)
    silent = sum(r["amount_wrong_silent"] for r in rows)
    wrong = flagged + silent
    pct = lambda a, b: round(100 * a / b, 1) if b else None  # noqa: E731
    return {
        "receipts": len(rows),
        "lines": n_lines,
        "amount_right_pct": pct(ok, n_lines),
        "amount_wrong": wrong,
        "wrong_but_flagged": flagged,
        "wrong_and_silent": silent,
        "caught_pct": pct(flagged, wrong),
        "qty_right_pct": pct(sum(r["qty_ok"] for r in rows), n_lines),
        "total_right_pct": pct(sum(r["total_ok"] for r in rows), len(rows)),
        "date_right_pct": pct(sum(r["date_ok"] for r in rows), len(rows)),
        "memo_right_pct": pct(sum(r["memo_ok"] for r in rows), len(rows)),
        "supplier_right_pct": pct(sum(r["supplier_ok"] for r in rows), len(rows)),
        "line_count_right_pct": pct(sum(r["line_count_ok"] for r in rows), len(rows)),
    }


def by(rows: list[dict], key: str) -> dict:
    return {k: summarise([r for r in rows if r[key] == k]) for k in sorted({r[key] for r in rows})}


def table(title: str, groups: dict) -> str:
    cols = (
        "receipts",
        "amount_right_pct",
        "caught_pct",
        "wrong_and_silent",
        "total_right_pct",
        "date_right_pct",
    )
    lines = [
        f"### {title}",
        "",
        "| group | " + " | ".join(cols) + " |",
        "|---|" + "---|" * len(cols),
    ]
    for name, s in groups.items():
        lines.append(f"| {name} | " + " | ".join(str(s[c]) for c in cols) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", type=int, default=10)
    ap.add_argument("--held-out", type=int, default=20)
    ap.add_argument("--dev-seed", type=int, default=11)
    ap.add_argument("--held-seed", type=int, default=202)
    args = ap.parse_args()
    engine = EasyOcrEngine(["bn", "en"])
    dev, dev_t = run(args.dev, args.dev_seed, engine)
    held, held_t = run(args.held_out, args.held_seed, engine)
    d, h = summarise(dev), summarise(held)
    text = f"""# Receipt reading check

Printed purchase memos drawn from known contents, damaged like phone photos, read with the real
engine (EasyOCR, Bangla and English) and parsed by `src/receipts/parse.py`. Regenerate with
`python -m src.receipts.ocr_check`. The first run of this check (before the photos were
straightened; `receipt_ocr_check_before_straightening.md`) showed that tilted photos broke the
table. That run's receipts were used to find the problem, so the numbers below come from fresh
receipts (seeds {args.dev_seed} development and {args.held_seed} held-out), read once after
the fixes.
**Handwriting is not measured: the engine does not support it, and
such receipts go to manual typing.**

## Held-out set ({h["receipts"]} receipts, {h["lines"]} lines, about {held_t:.0f} s per receipt)

Amounts right: **{h["amount_right_pct"]}%**. Wrong amounts: {h["amount_wrong"]}, of which
**{h["wrong_but_flagged"]} carried a flag a person would see** ({h["caught_pct"]}% caught) and
**{h["wrong_and_silent"]} were silent** (wrong and unflagged). Total right {h["total_right_pct"]}%,
date {h["date_right_pct"]}%, memo number {h["memo_right_pct"]}%,
supplier {h["supplier_right_pct"]}%,
line count {h["line_count_right_pct"]}%.

{table("Held-out, by language", by(held, "language"))}
{table("Held-out, by photo condition", by(held, "damage"))}
## Development set ({d["receipts"]} receipts)

Amounts right {d["amount_right_pct"]}%, wrong {d["amount_wrong"]} ({d["caught_pct"]}% flagged,
{d["wrong_and_silent"]} silent).

## What this does and does not show

- A flag is raised for low engine confidence, missing amounts, quantity x rate not equal to the
  amount, lines not adding up to the stated total, and impossible dates. A silent error is a wrong
  value that passed every check, for example a wrong quantity and a wrong amount that still agree.
- Every published line is checked by a Records Officer first. These numbers say how much work
  that check has to do and how often the software points at the right cell, not that the
  software can be trusted alone.
- The test receipts are clean printed layouts. Real market memos vary much more.
"""
    REPORT.write_text(text, encoding="utf-8")
    Path(str(REPORT).replace(".md", ".json")).write_text(
        json.dumps({"held_out": h, "development": d, "rows_held_out": held}, indent=2),
        encoding="utf-8",
    )
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
