# Receipt reading check

Printed purchase memos drawn from known contents, damaged like phone photos, read with the real
engine (EasyOCR, Bangla and English) and parsed by `src/receipts/parse.py`. Regenerate with
`python -m src.receipts.ocr_check`. The first run of this check (before the photos were
straightened; `receipt_ocr_check_before_straightening.md`) showed that tilted photos broke the
table. That run's receipts were used to find the problem, so the numbers below come from fresh
receipts (seeds 11 development and 202 held-out), read once after the fixes. **Handwriting is not measured: the engine does not support it, and
such receipts go to manual typing.**

## Held-out set (20 receipts, 90 lines, about 67 s per receipt)

Amounts right: **73.3%**. Wrong amounts: 24, of which
**24 carried a flag a person would see** (100.0% caught) and
**0 were silent** (wrong and unflagged). Total right 75.0%,
date 75.0%, memo number 75.0%,
supplier 75.0%,
line count 80.0%.

### Held-out, by language

| group | receipts | amount_right_pct | caught_pct | wrong_and_silent | total_right_pct | date_right_pct |
|---|---|---|---|---|---|---|
| bn | 10 | 59.2 | 100.0 | 0 | 60.0 | 60.0 |
| en | 10 | 90.2 | 100.0 | 0 | 90.0 | 90.0 |

### Held-out, by photo condition

| group | receipts | amount_right_pct | caught_pct | wrong_and_silent | total_right_pct | date_right_pct |
|---|---|---|---|---|---|---|
| blur | 4 | 46.7 | 100.0 | 0 | 50.0 | 25.0 |
| clean | 4 | 100.0 | None | 0 | 100.0 | 100.0 |
| dim | 4 | 94.1 | 100.0 | 0 | 75.0 | 100.0 |
| photo | 4 | 35.0 | 100.0 | 0 | 50.0 | 50.0 |
| tilt | 4 | 90.0 | 100.0 | 0 | 100.0 | 100.0 |

## Development set (10 receipts)

Amounts right 77.3%, wrong 10 (100.0% flagged,
0 silent).

## What this does and does not show

- A flag is raised for low engine confidence, missing amounts, quantity x rate not equal to the
  amount, lines not adding up to the stated total, and impossible dates. A silent error is a wrong
  value that passed every check, for example a wrong quantity and a wrong amount that still agree.
- Every published line is checked by a Records Officer first. These numbers say how much work
  that check has to do and how often the software points at the right cell, not that the
  software can be trusted alone.
- The test receipts are clean printed layouts. Real market memos vary much more.
