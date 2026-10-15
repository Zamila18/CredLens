# Model card: india_ltfs

*Public data: India L&T vehicle loans, not ShopUp data. Decision support only.* Written by `python -m src.model.model_card` from the reports; do not edit by hand.

**Model version:** `india_ltfs-20261014-135734-4198b26`

## Intended use

A check of the method on public data with real outcomes. This model is not for scoring anyone: it shows how the same pipeline does where the outcomes are known.

## Data

- **Source:** L&T vehicle loans, India (Kaggle): 233,154 loans disbursed Aug to Oct 2018.
- **Terms:** No usage terms stated on the page.
- **Outcome (label):** Repaid: the first instalment was paid on its due date (an early-warning outcome, not eventual default).
- **Split:** Split by loan issue date. Each period ends the day before the next begins.
- **Loans:** 68,002 to train, 66,788 to measure (validation). The held-back test loans are not used here.

## Model

- **Model in use:** LightGBM (boosted decision trees), calibration: Platt scaling.
- **Inputs** (each can only push the score the way its meaning says; how much data exists about a borrower is never an input):
  - One minus the loan-to-value, the part of the vehicle's price the borrower paid up front
  - Credit-bureau score at disbursement, for borrowers the bureau could score
  - Overdue earlier loans divided by all earlier loans, at disbursement
  - Loans that became delinquent in the six months before disbursement
  - New loans taken in the six months before disbursement
  - Enquiries the borrower made for loans, as recorded by the bureau

## Results (validation period)

| Measure | Value | 95% range |
|---|---|---|
| AUC (0.50 = coin toss; about 0.70 is useful) | 0.611 | 0.606 to 0.617 |
| Brier score (always-average: 0.156) | 0.151 | 0.150 to 0.153 |
| Calibration error | 0.005 | 0.004 to 0.009 |
| Simpler model (only the loan's terms: all that exists for a borrower with no bureau record) AUC | 0.565 | |
| What the full model adds | 0.046 | 0.042 to 0.050 |

| Band | Share of loans | Repaid |
|---|---|---|
| Strong | 5% | 91.1% |
| Review | 44% | 81.6% |
| Needs more info | 50% | 79.0% |

**What this shows.** The thin-file problem in real data: half the borrowers have no bureau record, and for them the model ranks barely better than chance.

**What this does not show.** That the method works: the AUC is well under the 0.70 benchmark. Use this source as the problem statement, not as a result.

## Group audit (validation period)

- Calibration differs for state (source code) '13' (5,403 loans, 71% repaid): the model expects 11 points more repayment than happened for this group, against 1 point less repayment than happened for everyone else.
- Ranking differs for state (source code) '12' (1,339 loans): AUC 0.54 against 0.61 for everyone else.
- Calibration differs for state (source code) '12' (1,339 loans, 79% repaid): the model expects 5 points more repayment than happened for this group, against about as much repayment as happened for everyone else.
- Calibration differs for state (source code) '19' (406 loans, 89% repaid): the model expects 9 points less repayment than happened for this group, against about as much repayment as happened for everyone else.
- Each group is compared with everyone else, so a gap in one group also shows, mirrored, in the other groups of the same column.
- 3 group(s) had too few repaid or not-repaid loans to measure; only their size is reported.
- Columns audited: age band, state (source code), employment type. Full table: `reports/FAIRNESS.md`.

## Limits

- Public data, not ShopUp data. The outcome is a missed first instalment, not a loan going bad. Each part of the time split is one month long.
- Labels exist only for people who received credit before. The model may not work for applicants who would have been turned down under earlier policy.
- Scores are less certain when coverage is low. A thin file is never treated as a bad file: below the coverage line the band is 'Needs more info', whatever the score.
- The numbers above are from the validation period. It was also used to choose the model and the calibration, so they are a little optimistic.
- Group columns are used only to audit results, never as model inputs. The group audit shows where the model works measurably differently on these data; it does not show that the model is fair.
- The tool supports a human decision. It must not be used for automatic approval or decline.
