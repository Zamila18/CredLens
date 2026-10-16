# Model card: homecredit

*Public data: Home Credit (country not stated), not ShopUp data. Decision support only.* Written by `python -m src.model.model_card` from the reports; do not edit by hand.

**Model version:** `homecredit-20261014-135834-4198b26`

## Intended use

A check of the method on public data with real outcomes. This model is not for scoring anyone: it shows how the same pipeline does where the outcomes are known.

## Data

- **Source:** Home Credit Default Risk (Kaggle, 2018), a sample of applicants; the publisher does not state the country.
- **Terms:** Kaggle competition rules limit use to that competition and forbid redistribution; used here only as a local, non-commercial method check, by the team lead's decision. Rows are never shown; only totals.
- **Outcome (label):** Repaid: the applicant had no payment difficulties.
- **Split:** Weaker split: this data source has no usable dates, so loans were divided at random (keeping the same share of repaid loans in each part) instead of by time.
- **Loans:** 33,333 to train, 8,333 to measure (validation). The held-back test loans are not used here.

## Model

- **Model in use:** logistic regression, calibration: none (the model's probabilities were already well calibrated).
- **Why this model:** LightGBM adds +0.0049 AUC over the logistic regression (range +0.0013 to +0.0084). It is used only if the whole range reaches +0.0100 and its Brier score is not worse. Here the whole range of the gain does not reach it, so the logistic regression stays. (The simpler model stays unless the other is clearly better.)
- **Inputs** (each can only push the score the way its meaning says; how much data exists about a borrower is never an input):
  - Share of the instalments on earlier loans paid on or before the due day
  - Share of the instalments on earlier loans paid more than 30 days late, or still unpaid after 30 days
  - Share of the instalments on earlier loans where less than 99% of the amount due was paid
  - The on-time share over instalments due in the 365 days before the application
  - Share of the monthly records of earlier store and cash loans with an amount overdue
  - The loan's repayment amount divided by the income stated in the application
  - The loan amount divided by the price of the goods it pays for
  - Average of the scores "from external data sources" that the application has (up to three)

## Results (validation period)

| Measure | Value | 95% range |
|---|---|---|
| AUC (0.50 = coin toss; about 0.70 is useful) | 0.746 | 0.725 to 0.764 |
| Brier score (always-average: 0.074) | 0.068 | 0.064 to 0.073 |
| Calibration error | 0.006 | 0.005 to 0.014 |
| Simpler model (the applicant's own repayment behaviour and loan terms, without the outside score) AUC | 0.601 | |
| What the full model adds | 0.144 | 0.119 to 0.169 |

| Band | Share of loans | Repaid |
|---|---|---|
| Strong | 73% | 95.2% |
| Review | 22% | 81.2% |
| Needs more info | 5% | 92.2% |

**What this shows.** Most of the ranking comes from a credit score bought from outside; the applicant's own instalment history and loan terms carry little.

**What this does not show.** That repayment history alone is enough on this data, or anything about Asia: the country is not stated.

## Results on the held-back test period

| Measure | Validation | Test | Test 95% range |
|---|---|---|---|
| AUC | 0.746 | 0.723 | 0.702 to 0.743 |
| Brier score | 0.068 | 0.070 | 0.066 to 0.074 |
| Calibration error | 0.006 | 0.005 | 0.005 to 0.013 |

8,334 test loans, 91.9% repaid. Brier score of always predicting the training average on them: 0.074. Test bands: strong 72%, review 23%, needs more info 5%. The model, its calibration and the band lines were fixed before this look and were not changed after it.

**Reading.** The calibration holds on loans the model never saw, and the ranking is a little below the validation result.

The ledger `reports/<mode>/test_set_use.json` has 1 entry for this test period (one entry can cover several looks; its detail says).

## Group audit (validation period)

- Ranking differs for age band 'under 30' (1,170 loans): AUC 0.67 against 0.75 for everyone else.
- Ranking differs for region rating '2' (6,207 loans): AUC 0.73 against 0.80 for everyone else.
- Each group is compared with everyone else, so a gap in one group also shows, mirrored, in the other groups of the same column.
- Gaps above the line but within the ranges (not flagged): region rating '1'.
- Columns audited: gender, age band, region rating. Full table: `reports/FAIRNESS.md`.

## Limits

- Public data, not ShopUp data; the country is not stated, so it carries no claim about Asia. The split is random because the source has no calendar dates.
- Individual rows are never shown on any screen: the competition rules forbid redistribution. Only totals like these appear.
- Labels exist only for people who received credit before. The model may not work for applicants who would have been turned down under earlier policy.
- Scores are less certain when coverage is low. A thin file is never treated as a bad file: below the coverage line the band is 'Needs more info', whatever the score.
- The validation numbers are a little optimistic: that period was also used to choose the model and the calibration. The held-back test period gives the honest check.
- Group columns are used only to audit results, never as model inputs. The group audit shows where the model works measurably differently on these data; it does not show that the model is fair.
- The tool supports a human decision. It must not be used for automatic approval or decline.
