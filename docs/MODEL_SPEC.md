# MODEL_SPEC.md: how the model must work

The model outputs a probability between 0 and 1 that a merchant repays. After calibration, score = round(100 x probability). The 0 and 1 values are only training labels. All numbers below come from `config/default.yaml`; all example figures are illustrative.

## Pipeline (build in this order)
1. Join and clean data by merchant_id.
2. Build labels.
3. Build features as of each loan's cutoff.
4. Split by time.
5. Train Logistic Regression and LightGBM.
6. Calibrate.
7. Score, coverage, band.
8. Explain (SHAP + dictionary).
9. Evaluate.
10. Ablation (A to D) at signal strengths 0, 0.5, 1.
11. Fairness by group.
12. Model card and versioning.

## 1. Join and clean
- Every purchase, delivery, payment, loan points to one valid merchant_id; reject and count orphans.
- Dates valid and ordered (no event before the merchant's onboarding date). Remove duplicates.
- Missing data stays missing. Never fill silently; gaps reduce coverage.

## 2. Labels
- label = 1 if repaid within `good_if_days_late_at_most` (30) days of the due date; 0 if later or default.
- Exclude loans younger than `min_loan_age_days` (60): outcome unknown.
- Example: 50,000 BDT repaid 10 days late -> 1. Unpaid 60 days after due date -> 0. Issued 35 days ago -> excluded.

## 3. Features (as-of cutoff = loan issue date, strictly earlier data only)
See `docs/FEATURE_DICTIONARY.md`. Feature groups: A purchases, B payments, C deliveries, D questionnaire (D is NOT in the headline model; shown beside the score and tested only in ablation). Public modes use their own source-specific features. Coverage features (history months, counts) are separate. Test: no feature may read any row dated on or after the cutoff.

## 4. Split by loan issue date
(Kiva: posted_time. The Taiwan and Home Credit data have no usable per-row dates: stratified random split, marked weaker in its model card; these are the only allowed exceptions.) Train first 12 months, validation next 3, test last 3. The same merchant may appear in several periods with features computed at each loan's own cutoff. Tune only on validation. Touch test once for the final report. Any other random split is a bug.

## 5. Models
- Logistic Regression: regularised, features scaled, missing handled with imputation plus missing-indicator columns. Transparent baseline.
- LightGBM: gradient-boosted trees; handles missing natively. Tune trees/depth/learning rate/min samples per leaf on validation. Watch overfitting.
- Choose by validation AUC, Brier and calibration. If LightGBM gains less than `prefer_simple_if_auc_gain_below`, keep Logistic Regression. Report both in the model card.
- If defaults are rare, also look at PR-AUC and use class weights in training only. Never rebalance validation or test.
- As built (Oct 13). The three lines above describe the first plan; the code differs in these ways, on purpose:
  - **No missing-indicator columns and no native missing handling.** Both models get the training average in place of a missing value (`src/model/preprocess.py`, `src/model/boosted.py`). A "was missing" signal would let a merchant with no delivery data, or a new merchant, be scored down for having little data.
  - **Every input can only push the way its meaning says** (`higher_is` in `dictionary.yaml`). The logistic regression drops an input whose weight points the other way; LightGBM uses monotone constraints. With those constraints the trees cannot single out the filled-in average either.
  - **LightGBM is tuned inside the training period**: the last `model.lightgbm.tuning_months` of training are held back, each setting of `model.lightgbm.grid` is fitted on the earlier months with early stopping, and the winner is fitted on all training months. The validation period is not used for tuning, so it stays clean for calibration and for comparing the two models.
  - **Choice rule.** LightGBM is used only if the whole bootstrap range of its AUC gain over the logistic regression (same resampled loans) is at or above `prefer_simple_if_auc_gain_below` (0.01) and its Brier score is not worse. Result on synthetic data, strength 0.5, seed 42: logistic regression 0.710 (0.688 to 0.729), LightGBM 0.722 (0.701 to 0.742), gain +0.013 (+0.003 to +0.021): the range dips under 0.01, so the **logistic regression is the model in use**. Across seeds 42, 7 and 123 and three signal strengths the gain was +0.002 to +0.013; a rule on the single number would have picked LightGBM in one run of nine. Both models are in `reports/<mode>/metrics.json` under `candidates`.
  - Negative control for LightGBM (same nine runs): delivery inputs add -0.004 to +0.001 AUC at strength 0 (every range spans zero), about +0.02 at 0.5 and +0.05 at 1.

## 6. Calibration
- Check: bin validation predictions (0-0.1 ... 0.9-1.0), plot predicted mean vs actual repayment rate.
- Fix with Platt scaling or isotonic regression, fitted on validation only, then frozen. Re-check on test.
- Calibration preserves ranking; it fixes the meaning of the number. This is enforced since Oct 14: isotonic can flatten a stretch of scores that rank loans the wrong way round, which raises the AUC by using the validation outcomes themselves (on Kiva from 0.644 to 0.756). A calibrator whose out-of-fold AUC is more than `model.calibration_max_auc_gain` (0.005) above the uncalibrated model is not eligible.
- As built (`src/model/calibrate.py`): three choices, `none`, `platt`, `isotonic`. A correction measured on the loans it learned from always looks good, so the validation loans are cut into `model.calibration_folds` folds and each choice is compared on out-of-fold probabilities. With `model.calibration: auto` the simplest choice stays unless a more flexible one lowers the Brier score by at least `model.calibration_min_brier_gain`. The saved calibrator is fitted on all validation loans. The validation numbers in the report use the out-of-fold probabilities. On synthetic data (seed 42, strength 0.5) the logistic regression is already calibrated (error 0.012; Brier 0.0819 with none, 0.0818 with either correction), so `none` is kept.

## 7. Score, coverage, band
- score = round(100 x calibrated probability).
- coverage (0-100%) = weighted checklist from `coverage_weights`: history of at least 6 months, purchases present for most months, payments present, deliveries present, questionnaire done, activity in last 30 days.
- Coverage is per data mode. `synthetic_bd` uses `coverage_weights`; each public mode uses its own list in `coverage_weights_by_mode`, built only from fields that source really has (for example Kiva: loan terms, sector, field-partner track record as of the posting date). Every list sums to 1.0. Never fill a missing stream with generated data to raise coverage.
- Band:
  - coverage < `band_min_coverage` -> "Needs more info" (regardless of score)
  - else score >= `band_strong_min_score` -> "Strong"
  - else "Review".
  - A score below `low_score_warning_below` also carries an explicit low-score warning.
- Lines as set on Oct 13 (`score` section of the config): Strong line 90, coverage line 0.45, low-score warning below 70. They were set from the validation scores of the synthetic data and are settings, not facts: about nine in ten loans are repaid, so most scores sit between 80 and 99, and the first lines (70 and 0.60) put 97% of loans at or above the Strong line and 91% of first-loan merchants in "Needs more info". A data mode can have its own lines under `score.by_mode`; set them again for any real data source.
- Examples (tests in `tests/test_score.py`): probability 0.92, coverage 85% -> score 92, Strong. Probability 0.84, coverage 85% -> score 84, Review. Probability 0.93, coverage 35% -> score 93, Needs more info. Probability 0.62, coverage 85% -> score 62, Review with a low-score warning.
- As built (`src/model/score.py`): `score_table` gives probability, score, coverage, band and warning per loan; `band_summary` gives the share of loans and the share repaid per band. On synthetic validation data (seed 42, strength 0.5): Strong 56% of loans (95.2% repaid), Review 29% (82.1% repaid), Needs more info 15% (88.3% repaid). 28% of first loans and under 1% of repeat loans are "Needs more info".

## 8. Explanations
- SHAP (tree explainer) for LightGBM; coefficient x standardised value for Logistic Regression.
- Take the top 3 contributions that raise the score and top 3 that lower it. Map each feature to its dictionary sentence (Bangla and English). Group the remainder into "all other features" so contributions sum to the final score.
- Sentences are observations ("returns are higher than similar shops; this may reflect delivery conditions"), never accusations or causes.
- Example (mean score 60): purchase growth +8, payment delay +5, supplier repeat share +4, returns -6, one late payment -4, thin delivery data -2, others +7 = 72. (An illustration of the arithmetic from the first plan; real baselines sit near 92, see below.)
- As built (`src/model/explain.py`, Oct 13). One method for both models, so the SHAP library is not needed:
  - The baseline is the score of the "average merchant" (every input at its training average, which is also what the model puts in place of a missing input). On synthetic data it is about 92.
  - Each input's contribution is its exact Shapley value against that baseline, in score points: the merchant's real inputs are switched on one at a time in every possible order and the moves of the score are averaged. With about ten inputs this is at most 1,024 model calls per merchant (about 0.02 seconds), so nothing is approximated. These are SHAP values: `tests/test_reasons.py` checks that they equal the output of the SHAP library's exact explainer (`shap.Explainer(..., algorithm="exact")`) for both models, to eight decimals. The library's faster tree explainer was tried and differed from its own exact explainer by up to 0.9 score points on LightGBM, so the exact computation is the one used. More than `score.max_inputs_for_exact_reasons` inputs is refused with a clear message.
  - Baseline + every contribution = 100 x probability, exactly. On screen: baseline + the reasons shown + "all other inputs" = the whole-number score; the last part also absorbs the rounding.
  - A missing input contributes exactly zero and never becomes a reason. A better-than-average value never gets a negative contribution, because every input is constrained to push one way.
  - A sentence is shown only if it is true for the merchant (`shown_when` in `dictionary.yaml`): "No recent late payments" needs none, "purchases are growing" needs growth above zero, "most payments arrive on time" needs more than half. When the plain sentence is not true, the comparing sentence under `otherwise` is shown instead ("Credit use is higher than at similar shops"), so the largest contribution each way is always among the reasons. Contributions under `score.min_reason_points` are not shown. "All other inputs" holds what is left after the top three each way: on validation its size is under 0.5 points for half the loans and above 2 points for about one loan in nine (merchants with more than three reasons on one side).
  - Each reason carries a number for context, for example "Returns 11.1% vs average 6.8%" (`detail` in `dictionary.yaml`). "Average" is the training average after clipping; for skewed inputs such as purchase growth it is well above the median.
  - `score_card` refuses to compute anything without a valid consent (`ConsentRequired`). The card and the review queue give the same score for the same loan (tested). `score_card` returns everything the API needs for `GET /merchants/{id}/score` (the fields of `ScoreResponse` except the merchant id). The training report checks the sums on a sample of validation loans (`reasons_check`).

## 9. Evaluation (test period only)
- ROC-AUC, PR-AUC, Brier score, calibration curve, top-k precision (k=20), reviewable share at the chosen threshold.
- Bootstrap ranges (`bootstrap_resamples`). Report ranges, not third decimals.
- Baselines to beat: always predict the average repayment rate; purchases-only model.
- If AUC > `suspicious_auc` on synthetic data, treat as leakage until proven otherwise.

## 10. Ablation
| Run | Features | Gain measured |
|---|---|---|
| A | purchases | baseline |
| B | A + payments | AUC(B) - AUC(A) |
| C | B + deliveries (REDX) | AUC(C) - AUC(B) |
| D | C + questionnaire | AUC(D) - AUC(C), reported as a separate finding; the headline model is C (or the best of A to C) |

As built (Oct 14, `src/model/ablation.py`, report in `reports/ablation/`): the headline logistic regression for each run, on data generated afresh for strengths 0, 0.5 and 1 and seeds 42, 7 and 123, measured on validation months with paired gains. Deliveries add +0.0000 at strength 0 (-0.0003 to +0.0004 over seeds), +0.025 at 0.5 and +0.055 at 1; the negative control passes and `tests/test_zero_signal.py` keeps checking it, with a positive control at strength 1.

Repeat for `delivery_signal_strength` = 0, 0.5, 1 (regenerate data each time).
- Strength 0: C must not beat B by more than `zero_signal_max_auc_gain`. If it does, stop: bug or leakage. This is the negative control.
- Strength 0.5 and 1: expect small then clear gain, growing with strength.
- Keep a feature group only if its gain exceeds the bootstrap range and does not worsen group gaps.
- Meaning: proves the pipeline can detect a signal if present; does NOT prove REDX data predicts repayment in the real world.

## 11. Fairness by group
Group columns: town_tier, shop_type, has_trade_license (audit only, not features); in public modes the audit columns from config `fairness.audit_only_columns`. For each group report AUC, mean score, band shares and calibration, each with a bootstrap range. Flag a gap above `flag_gap_points` only when the ranges do not overlap or it persists across seeds; small groups are noisy. Also compare calibration by group. Report what was measured; do not claim "fair".

As built (Oct 15, `src/model/fairness.py`, `python -m src.model.fairness --all-modes`, reports in `reports/<mode>/fairness.json` and `reports/FAIRNESS.md`): on the validation months, each group is compared with the rest of the loans on ranking (AUC of the group minus AUC of the rest) and calibration ((predicted minus actual) of the group minus the same for the rest). A gap above 0.05 is flagged when the ranges of group and rest do not overlap, or, on synthetic data, when it is above the line in all three seeds (42, 7, 123). Probabilities are calibrated out of fold, exactly as in the training report, and the audit stops unless its validation AUC equals the report's. Groups with fewer than `min_group_outcomes` (30) repaid or not-repaid loans show their size only (no outcomes or scores). The audit refuses to run if a group column is a model input. `tests/test_fairness.py` plants a gap (`generator.inject_group_bias` 1.5 on small-town merchants) and checks that it is flagged, and that nothing is flagged without it.

## 12. Model card and versioning
Model card per data mode (`docs/model_card_<mode>.md` plus JSON at `/model/card?mode=`): intended use (decision support only), data (synthetic with generator settings and signal strengths, or the public source with filters and licence), label definition and exclusions, split dates and counts, models compared and chosen, metrics with ranges and calibration plot, ablation results, group results and flagged gaps, limitations and out-of-scope uses (no automatic approval, no real-world validity claim), selection bias, and "public data is not ShopUp data".
Versioning: each trained model gets a version id storing commit, data seed, config, metrics, calibrator. Every score and decision records it.

## Files (suggested)
`src/model/labels.py, split.py, train.py, calibrate.py, score.py, explain.py, evaluate.py, ablation.py, fairness.py, model_card.py`

## Common mistakes to avoid
Random split; features after the cutoff; counting young loans as defaults; tuning on test; trusting a huge AUC on synthetic data; skipping calibration; showing score without coverage; showing code feature names to officers; using group columns as features; treating Mokam purchases as sales; putting the questionnaire inside the score; claiming REDX "proves" anything; missing seeds/versions; letting the score auto-decide.

## v2 additions: data modes and real-label checks
- data.mode in config selects the adapter: synthetic_bd | kiva_asia | taiwan_cc | homecredit. Same pipeline for all.
- kiva_asia: label paid=1, defaulted=0; drop unknown outcomes; time split on posted_time. Very imbalanced: report PR-AUC and top-k next to AUC. Purchase/delivery/payment groups are null, so coverage is low by design.
- taiwan_cc: one fixed observation window with no per-row dates, so use a stratified random split and mark it "weaker split" in the model card. Label = 1 − default.
- homecredit: relative days only, so use a stratified random split marked "weaker split". Label = 1 − TARGET. The data does not state its country: the model card says "country not stated" and makes no Asian claim from it.
- Difficulty target for synthetic_bd: tune generator noise so test AUC is about 0.72 to 0.82 at signal strength 0.5. Report metrics across at least 3 seeds.
- Explanation check: top reasons plus "all other features" must sum to the final score, tested.
- Leakage guard per source: a whitelist of decision-time columns; a test fails if any other column reaches the feature matrix.
- Questionnaire (group D) is excluded from the headline model; D is reported as a separate ablation finding.
- Group audit: bootstrap range per group; flag only when ranges do not overlap or the gap persists across seeds.
- Model card "Known limits": copy from docs/DATASET_PLAN.md section 4 and the review list, and add one card per data mode.
- india_ltfs: real disbursal dates over three months (Aug to Oct 2018), so split by time: train on August, validate on September, test on October, and say in the model card that the window is short. Label = 1 - loan_default, where loan_default is "payment default in the first EMI on due date" (an early-warning outcome). Treat branch and employee identifiers with care: never as headline reasons.
- synthetic_bd label timing: every loan issued in the 18-month main window has an outcome; loans issued in the 61-day tail are unlabelled and must be excluded from training and testing (they are the pending cases).
- synthetic_bd repayment share is about 90%, so the classes are imbalanced: report PR-AUC and top-k next to AUC here too.
