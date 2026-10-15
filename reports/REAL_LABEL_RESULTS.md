# Results on public data with real outcomes (Phase 8)

Run on Oct 14, 2026 with `python tasks.py train --all-modes`, seed 42. The numbers for each mode are in `reports/<mode>/metrics.json`; this page says what they do and do not show.

**Read this first.**
- Every number in the big table is from the **validation part** of each data set. The held-back test part was used once, on Oct 15, for the final report: see "The one look at the held-back test part" below.
- None of these data sets is ShopUp data, and none holds merchants on a commerce platform. They test the method, not how it would perform for ShopUp.
- The same code produced all five columns. Only the list of inputs differs per source, because each source has different fields.
- AUC: how often the model ranks a loan that was repaid above one that was not. 0.50 is a coin toss. About 0.70 is considered useful for this kind of lending (CGAP).

## The numbers

| | Synthetic (Bangladesh-shaped) | Taiwan credit cards | India vehicle loans | Home Credit (country not stated) | Kiva, Asia |
|---|---|---|---|---|---|
| Loans: train / validation / held back | 13,318 / 5,853 / 6,023 | 20,000 / 5,000 / 5,000 | 68,002 / 66,788 / 98,364 | 33,333 / 8,333 / 8,334 | 32,581 / 15,113 / 17,610 |
| Split | by time | random (weaker) | by time | random (weaker) | by time |
| Repaid, validation | 90.4% | 77.9% | 80.8% | 92.0% | 94.8% |
| Model inputs | 10, behaviour | 8, behaviour | 6: 1 loan term, 5 bureau | 9: 6 instalment history, 2 loan terms, 1 outside score | 3: 1 loan term, 2 field partner |
| Model in use | logistic regression | logistic regression | LightGBM | logistic regression | logistic regression |
| **AUC (95% range)** | **0.710 (0.688 to 0.729)** | **0.743 (0.725 to 0.761)** | **0.611 (0.606 to 0.617)** | **0.746 (0.725 to 0.764)** | **0.644 (0.634 to 0.655)** |
| Other candidate | LightGBM 0.722 | LightGBM 0.761 | logistic regression 0.595 | LightGBM 0.751 | LightGBM 0.406 |
| Simpler model, and its AUC | purchases only, 0.667 | latest month only, 0.697 | loan terms only, 0.565 | without the outside score, 0.601 | without the field partner, 0.644 |
| What the full model adds (range) | +0.043 (+0.028 to +0.060) | +0.046 (+0.033 to +0.059) | +0.046 (+0.042 to +0.050) | +0.144 (+0.119 to +0.169) | 0.000 |
| AUC for loans under the coverage line (how many) | 0.583 (899) | 0.637 (469) | 0.580 (33,705) | 0.744 (409) | 0.468 (648) |
| AUC for the rest (how many) | 0.734 (4,954) | 0.750 (4,531) | 0.629 (33,083) | 0.746 (7,924) | 0.656 (14,465) |
| Brier (always-average baseline) | 0.0819 (0.0871) | 0.1381 (0.1723) | 0.1514 (0.1556) | 0.0681 (0.0739) | 0.0497 (0.0516) |
| Calibration error, and method | 0.012, none | 0.008, isotonic | 0.005, Platt | 0.006, none | 0.065, Platt |
| Not repaid among the 20 lowest-scored (overall) | 55% (10%) | 60% (22%) | 50% (19%) | 65% (8%) | 0% (5%) |
| Band Strong: share, repaid | 56%, 95.2% | 25%, 89.4% | 5%, 91.1% | 73%, 95.2% | 96%, 94.7% |
| Band Review: share, repaid | 29%, 82.1% | 65%, 73.9% | 44%, 81.6% | 22%, 81.2% | 0% |
| Band Needs more info: share, repaid | 15%, 88.3% | 9%, 74.0% | 50%, 79.0% | 5%, 92.2% | 4%, 95.7% |

The band lines are the same everywhere (Strong from a score of 90, coverage from 45%), so a score means the same thing in every column.

## What each column shows, and what it does not

### Taiwan credit cards: the method works on real behaviour
- **Shows:** eight inputs describing how a client paid over six months rank real outcomes with an AUC of 0.74. The six months add 0.046 over knowing only whether the latest bill was late. The bands separate: 89% of Strong loans repaid against 74% of Review loans. Calibration error under 1%.
- **Does not show:** anything about merchants. These are consumer credit cards in Taiwan in 2005. The split is random, not by time, so the result is somewhat easier than a real forward test.
- LightGBM reached 0.761. Its gain over the logistic regression is +0.018, and the low end of the range of that gain is 0.0099, just under the 0.01 the rule asks for, so the simpler model stays. It is a near miss, stated as such.

### India vehicle loans: the problem, measured
- **Shows:** half the borrowers (50%) have no credit-bureau record. For them the only input is the loan's terms, and the model ranks them barely better than chance: AUC 0.580 inside that group. For borrowers with a record it is 0.629, still weak. Over everyone, 0.611; a model on the loan's terms alone gets 0.565. Only 5% of loans reach the Strong band.
- **Does not show:** that the method works. An AUC of 0.61 is well under the 0.70 benchmark and is reported as it is.
- **Why it matters for this project:** this is the thin-file gap in real data. A conventional bureau summary says little about who misses a first instalment and nothing about half the borrowers. That is the gap that purchase, delivery and payment records are meant to fill. Use this column as the problem statement, not as a result.
- The outcome here is missing the first instalment, an early warning, not a loan going bad.

### Home Credit: most of the ranking comes from a score bought elsewhere
- **Shows:** with nine inputs the AUC is 0.746. Without the outside score it is 0.601. So the applicant's own instalment history and loan terms carry little, and the outside score adds 0.144.
- **Does not show:** that repayment history alone is enough on this data; it is not. Nor anything about Asia: the publisher does not state the country.
- The split is random, because the source has no calendar dates. Rows of this source are never shown on a screen; only these totals.

### Kiva, Asia: no information about the borrower, and the numbers say so
- **Shows:** Kiva knows the loan's terms and the field partner, and nothing about how a borrower paid before. On the validation months the model works from the loan's term alone. Of the two partner inputs, the past default rate pointed the wrong way and was removed: the partners that failed in 2012 had clean records until then. The other, "the partner carries the loss", has a weight but changes nothing after 2011: 19% of training loans had it and none of the validation or held-back loans did, because the practice had stopped. LightGBM, which is forced to treat a bad track record as bad, scored 0.406, worse than a coin toss.
- **The AUC of 0.644 is misleading on its own.** The 20 lowest-scored loans were all repaid, only 4% of the defaults sit in the lowest-scored fifth, the calibration error is 6.5%, and 96% of loans land in the Strong band. This model cannot be used to pick out risky loans.
- **Does not show:** anything about scoring a merchant from behaviour. Do not quote the Kiva AUC as support. What Kiva shows is the opposite case: where the only information is about the intermediary, a score cannot be trusted.

### Synthetic data: the pipeline, not the world
- **Shows:** the whole pipeline runs and behaves as designed: time split, two candidate models, calibration, bands, reasons, and a negative control (delivery inputs add nothing when the generator gives them no signal).
- **Does not show:** how accurate the tool would be for real merchants. The data is generated by our own code.

## What the five columns say together

Where a source records how people actually behaved over time (Taiwan), behaviour inputs rank real outcomes well. Where it records little about the borrower (half of India, all of Kiva), no model can, and the tool answers "Needs more info" or produces a score that should not be trusted. Home Credit sits between: its strength is an outside score, not the applicant's own history. That pattern is the argument of the project: thin-file merchants need behaviour data, and a platform that sees purchases, deliveries and payments has it.

## The one look at the held-back test part (Oct 15)

`python -m src.model.final_test --all-modes`, once per model, each look written to `reports/<mode>/test_set_use.json` before measuring. Nothing was chosen or tuned from these numbers; the models, calibrators and band lines were fixed before. Full results: `reports/<mode>/test_results.json` and the model cards.

| | Synthetic | Taiwan | India | Home Credit | Kiva |
|---|---|---|---|---|---|
| Test loans | 6,023 | 5,000 | 98,364 | 8,334 | 17,610 |
| AUC, test (95% range) | 0.728 (0.707 to 0.749) | 0.752 (0.734 to 0.769) | 0.599 (0.595 to 0.603) | 0.723 (0.702 to 0.743) | 0.435 (0.420 to 0.450) |
| AUC, validation | 0.710 | 0.743 | 0.611 | 0.746 | 0.644 |
| Calibration error, test (validation) | 0.008 (0.012) | 0.022 (0.008) | 0.045 (0.005) | 0.005 (0.006) | 0.076 (0.065) |
| Repaid, test (validation) | 90.2% (90.4%) | 77.9% (77.9%) | 76.5% (80.8%) | 91.9% (92.0%) | 92.0% (94.8%) |

- **Taiwan** holds on loans the model never saw. The average prediction matches what happened (77.3% against 77.9%), but the calibration error rose; a likely reason, not tested, is that the isotonic calibration followed the validation loans too closely.
- **India** gets weaker: in the test month 76.5% repaid against 80.8% in the validation month, and the calibration fitted on the earlier month expected 81.0%. A lender would have to recalibrate on recent loans. The ranking stays well under the 0.70 benchmark.
- **Home Credit** holds; the ranking is a little below validation, the calibration unchanged.
- **Kiva** ranks the later loans the wrong way round (AUC 0.435). It confirms the reading above: this model must not be used.
- **Synthetic** is not a clean holdout. Its test months were looked at before (ledger entries 1 and 2: several times while the generator's noise was tuned in Phase 1, and once in an audit probe on Oct 13). The result agrees with validation but is no stronger evidence.

## Two rules that changed the numbers, and why

1. **A calibrator may not improve the ranking.** On Kiva, isotonic calibration lifted the AUC from 0.644 to 0.756. It did so by flattening a stretch of scores that ranked loans the wrong way round, using the validation period's own outcomes. That is not something the model learned, so a calibrator whose AUC is more than 0.005 above the uncalibrated model is no longer eligible (`model.calibration_max_auc_gain`). Kiva's reported AUC is therefore 0.644.
2. **The simpler model stays unless the flexible one is clearly better** (decided in Phase 6). LightGBM is used only where the whole range of its gain reaches 0.01: India only.

## Limits that apply to every column

- Validation numbers. The same validation data was used to choose between two models and three calibrators, so they are a little optimistic. The held-back part, above, is the honest check.
- The ranges treat loans as independent.
- The time splits have no gap between periods (audit of Oct 15). The outcome of a loan issued near the end of a period became known only after the next period began, yet training and calibration used it. On the synthetic data that is up to 27.5% of the training loans and 66.9% of the validation loans (upper bounds: the generator dates every outcome 30 days after the due date). A strict forward test would leave a gap; the results are a little optimistic. Not changed now: a retrained model would need a second look at the test period.
- The inputs were chosen by the rule "behaviour only; how much data exists is context". Sources where "little data" predicts trouble (Taiwan clients known only by a credit limit repay less often) lose that signal on purpose and get "Needs more info" instead.
- The group audit (sex, age band, state, country and the others) is in `reports/FAIRNESS.md` (Phase 11, Oct 15), and each mode's findings are on its model card (`docs/model_card_<mode>.md`).
- The thin-file rows above show the tool's design at work: in every source but Home Credit, the model ranks loans under the coverage line worse than the rest (on Kiva, worse than chance). That is why those loans get "Needs more info" instead of a band.
- Home Credit's individual rows are never shown (competition rules): asking for a score card or a review queue in that mode is refused in code (`data.rows_never_shown`). Only totals like these appear.
