# Model card: kiva_asia

*Public data: Kiva (Asia), not ShopUp data. Decision support only.* Written by `python -m src.model.model_card` from the reports; do not edit by hand.

**Model version:** `kiva_asia-20261014-135932-4198b26`

## Intended use

A check of the method on public data with real outcomes. This model is not for scoring anyone: it shows how the same pipeline does where the outcomes are known.

## Data

- **Source:** Kiva loans in Asia from Kiva's snapshot of 2 May 2016 (Internet Archive copy), retail, food and services.
- **Terms:** No data licence stated, only Kiva's general terms of use.
- **Outcome (label):** Repaid: the loan was paid back, not defaulted.
- **Split:** Split by loan issue date. Each period ends the day before the next begins.
- **Loans:** 32,581 to train, 15,113 to measure (validation). The held-back test loans are not used here.

## Model

- **Model in use:** logistic regression, calibration: Platt scaling.
- **Inputs** (each can only push the score the way its meaning says; how much data exists about a borrower is never an input):
  - The number of months over which the loan is to be repaid
  - 1 when the field partner, not the lender, carries the loss if the borrower does not pay

## Results (validation period)

| Measure | Value | 95% range |
|---|---|---|
| AUC (0.50 = coin toss; about 0.70 is useful) | 0.644 | 0.634 to 0.655 |
| Brier score (always-average: 0.052) | 0.050 | 0.047 to 0.053 |
| Calibration error | 0.065 | 0.062 to 0.069 |
| Simpler model (the loan's terms only, without the two inputs about the field partner) AUC | 0.644 | |
| What the full model adds | 0.000 | 0.000 to 0.000 |

| Band | Share of loans | Repaid |
|---|---|---|
| Strong | 96% | 94.7% |
| Review | 0% | - |
| Needs more info | 4% | 95.7% |

**What this shows.** Where the only information is about the loan and its field partner, a score cannot be trusted.

**What this does not show.** Anything about scoring a merchant from behaviour. This model must not be used to pick out risky loans, and its AUC must not be quoted as support.

## Group audit (validation period)

- Ranking differs for borrower gender 'female' (13,758 loans): AUC 0.66 against 0.51 for everyone else.
- Ranking differs for borrower gender 'male' (1,319 loans): AUC 0.52 against 0.66 for everyone else.
- Ranking differs for country 'Philippines' (10,857 loans): AUC 0.82 against 0.33 for everyone else.
- Ranking differs for country 'Pakistan' (605 loans): AUC 0.45 against 0.65 for everyone else.
- Calibration differs for country 'Pakistan' (605 loans, 79% repaid): the model expects 16 points more repayment than happened for this group, against 1 point less repayment than happened for everyone else.
- Ranking differs for country 'Indonesia' (253 loans): AUC 0.39 against 0.64 for everyone else.
- Calibration differs for country 'Indonesia' (253 loans, 84% repaid): the model expects 9 points more repayment than happened for this group, against about as much repayment as happened for everyone else.
- Each group is compared with everyone else, so a gap in one group also shows, mirrored, in the other groups of the same column.
- 10 group(s) had too few repaid or not-repaid loans to measure; only their size is reported.
- Columns audited: borrower gender, country. Full table: `reports/FAIRNESS.md`.

## Limits

- Public data, not ShopUp data. Not usable for scoring: see 'What this does not show'.
- Labels exist only for people who received credit before. The model may not work for applicants who would have been turned down under earlier policy.
- Scores are less certain when coverage is low. A thin file is never treated as a bad file: below the coverage line the band is 'Needs more info', whatever the score.
- The numbers above are from the validation period. It was also used to choose the model and the calibration, so they are a little optimistic.
- Group columns are used only to audit results, never as model inputs. The group audit shows where the model works measurably differently on these data; it does not show that the model is fair.
- The tool supports a human decision. It must not be used for automatic approval or decline.
