# Receipt reading check

Printed purchase memos drawn from known contents, damaged like phone photos, read with the real
engine (EasyOCR, Bangla and English) and parsed by `src/receipts/parse.py`. Regenerate with
`python -m src.receipts.ocr_check`. Parsing was tuned on the development set; the held-out set
was read once after tuning. **Handwriting is not measured: the engine does not support it, and
such receipts go to manual typing.**

## Held-out set (20 receipts, 95 lines, about 82 s per receipt)

Amounts right: **54.7%**. Wrong amounts: 43, of which
**42 carried a flag a person would see** (97.7% caught) and
**1 were silent** (wrong and unflagged). Total right 70.0%,
date 45.0%, memo number 50.0%, supplier 65.0%,
line count 50.0%.

### Held-out, by language

| group | receipts | amount_right_pct | caught_pct | wrong_and_silent | total_right_pct | date_right_pct |
|---|---|---|---|---|---|---|
| bn | 10 | 57.1 | 100.0 | 0 | 60.0 | 0.0 |
| en | 10 | 52.2 | 95.5 | 1 | 80.0 | 90.0 |

### Held-out, by photo condition

| group | receipts | amount_right_pct | caught_pct | wrong_and_silent | total_right_pct | date_right_pct |
|---|---|---|---|---|---|---|
| blur | 4 | 68.4 | 100.0 | 0 | 50.0 | 25.0 |
| clean | 4 | 100.0 | None | 0 | 100.0 | 50.0 |
| dim | 4 | 94.4 | 100.0 | 0 | 75.0 | 50.0 |
| photo | 4 | 0.0 | 100.0 | 0 | 25.0 | 50.0 |
| tilt | 4 | 23.8 | 93.8 | 1 | 100.0 | 50.0 |

## Development set (10 receipts)

Amounts right 50.0%, wrong 22 (86.4% flagged,
3 silent).

## What this does and does not show

- A flag is raised for low engine confidence, missing amounts, quantity x rate not equal to the
  amount, lines not adding up to the stated total, and impossible dates. A silent error is a wrong
  value that passed every check, for example a wrong quantity and a wrong amount that still agree.
- Every published line is checked by a Records Officer first. These numbers say how much work
  that check has to do and how often the software points at the right cell, not that the
  software can be trusted alone.
- The test receipts are clean printed layouts. Real market memos vary much more.
