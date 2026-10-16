# Model card: taiwan_cc

*Public data: Taiwan credit cards, not ShopUp data. Decision support only.* Written by `python -m src.model.model_card` from the reports; do not edit by hand.

**Model version:** `taiwan_cc-20261014-135411-4198b26`

## Intended use

A check of the method on public data with real outcomes. This model is not for scoring anyone: it shows how the same pipeline does where the outcomes are known.

## Data

- **Source:** UCI 'default of credit card clients': 30,000 credit-card clients in Taiwan, 2005 (I-Cheng Yeh, 2009).
- **Terms:** CC BY 4.0, as stated on the UCI page.
- **Outcome (label):** Repaid: the client did not default on the next month's payment.
- **Split:** Weaker split: this data source has no usable dates, so loans were divided at random (keeping the same share of repaid loans in each part) instead of by time.
- **Loans:** 20,000 to train, 5,000 to measure (validation). The held-back test loans are not used here.

## Model

- **Model in use:** logistic regression, calibration: isotonic regression.
- **Why this model:** LightGBM adds +0.0181 AUC over the logistic regression (range +0.0099 to +0.0265). It is used only if the whole range reaches +0.0100 and its Brier score is not worse. Here the whole range of the gain does not reach it, so the logistic regression stays. (The simpler model stays unless the other is clearly better.)
- **Inputs** (each can only push the score the way its meaning says; how much data exists about a borrower is never an input):
  - Of the last six months in which the card was used, the share with no late payment
  - The longest payment delay, in months, in the last six months
  - The payment delay, in months, in the most recent month
  - Amount paid in five months divided by the bills of the month before each
  - Average bill over six months divided by the credit limit
  - Newest bill minus oldest bill, divided by the credit limit
  - Of the months that followed a bill, the share in which nothing was paid

## Results (validation period)

| Measure | Value | 95% range |
|---|---|---|
| AUC (0.50 = coin toss; about 0.70 is useful) | 0.743 | 0.725 to 0.761 |
| Brier score (always-average: 0.172) | 0.138 | 0.131 to 0.145 |
| Calibration error | 0.008 | 0.009 to 0.023 |
| Simpler model (only whether the most recent monthly bill was paid late) AUC | 0.697 | |
| What the full model adds | 0.046 | 0.033 to 0.059 |

| Band | Share of loans | Repaid |
|---|---|---|
| Strong | 25% | 89.4% |
| Review | 65% | 73.9% |
| Needs more info | 9% | 74.0% |

**What this shows.** Inputs describing how a client paid over six months rank real outcomes well, and the bands separate repaid from not repaid.

**What this does not show.** Anything about merchants: these are consumer credit cards in Taiwan in 2005. The split is random, not by time, so the result is somewhat easier than a real forward test.

## Results on the held-back test period

| Measure | Validation | Test | Test 95% range |
|---|---|---|---|
| AUC | 0.743 | 0.752 | 0.734 to 0.769 |
| Brier score | 0.138 | 0.138 | 0.132 to 0.145 |
| Calibration error | 0.008 | 0.022 | 0.015 to 0.031 |

5,000 test loans, 77.9% repaid. Brier score of always predicting the training average on them: 0.172. Test bands: strong 29%, review 62%, needs more info 9%. The model, its calibration and the band lines were fixed before this look and were not changed after it.

**Reading.** The ranking holds on loans the model never saw. On average the predictions match what happened, but the calibration error is higher than on validation; a likely reason, not tested, is that the isotonic calibration followed the validation loans a little too closely.

The ledger `reports/<mode>/test_set_use.json` has 1 entry for this test period (one entry can cover several looks; its detail says).

## Group audit (validation period)

- No group gap was flagged on these data.
- Each group is compared with everyone else, so a gap in one group also shows, mirrored, in the other groups of the same column.
- Gaps above the line but within the ranges (not flagged): age band '50 and over'.
- 6 group(s) had too few repaid or not-repaid loans to measure; only their size is reported.
- Columns audited: sex (source code), education (source code), marital status (source code), age band. Full table: `reports/FAIRNESS.md`.

## Limits

- Public data, not ShopUp data. It tests the method on real payment behaviour, not on merchants.
- Labels exist only for people who received credit before. The model may not work for applicants who would have been turned down under earlier policy.
- Scores are less certain when coverage is low. A thin file is never treated as a bad file: below the coverage line the band is 'Needs more info', whatever the score.
- The validation numbers are a little optimistic: that period was also used to choose the model and the calibration. The held-back test period gives the honest check.
- Group columns are used only to audit results, never as model inputs. The group audit shows where the model works measurably differently on these data; it does not show that the model is fair.
- The tool supports a human decision. It must not be used for automatic approval or decline.
