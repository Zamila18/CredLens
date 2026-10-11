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

## 6. Calibration
- Check: bin validation predictions (0-0.1 ... 0.9-1.0), plot predicted mean vs actual repayment rate.
- Fix with Platt scaling or isotonic regression, fitted on validation only, then frozen. Re-check on test.
- Calibration preserves ranking; it fixes the meaning of the number.

## 7. Score, coverage, band
- score = round(100 x calibrated probability).
- coverage (0-100%) = weighted checklist from `coverage_weights`: history of at least 6 months, purchases present for most months, payments present, deliveries present, questionnaire done, activity in last 30 days.
- Coverage is per data mode. `synthetic_bd` uses `coverage_weights`; each public mode uses its own list in `coverage_weights_by_mode`, built only from fields that source really has (for example Kiva: loan terms, sector, field-partner track record as of the posting date). Every list sums to 1.0. Never fill a missing stream with generated data to raise coverage.
- Band:
  - coverage < `band_min_coverage` -> "Needs more info" (regardless of score)
  - else score >= `band_strong_min_score` -> "Strong"
  - else "Review"; if score is also low (for example < 40), attach a low-score warning.
- Example: probability 0.72, coverage 85% -> score 72, band Strong. Probability 0.66, coverage 35% -> score 66, band Needs more info.

## 8. Explanations
- SHAP (tree explainer) for LightGBM; coefficient x standardised value for Logistic Regression.
- Take the top 3 contributions that raise the score and top 3 that lower it. Map each feature to its dictionary sentence (Bangla and English). Group the remainder into "all other features" so contributions sum to the final score.
- Sentences are observations ("returns are higher than similar shops; this may reflect delivery conditions"), never accusations or causes.
- Example (mean score 60): purchase growth +8, payment delay +5, supplier repeat share +4, returns -6, one late payment -4, thin delivery data -2, others +7 = 72.

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

Repeat for `delivery_signal_strength` = 0, 0.5, 1 (regenerate data each time).
- Strength 0: C must not beat B by more than `zero_signal_max_auc_gain`. If it does, stop: bug or leakage. This is the negative control.
- Strength 0.5 and 1: expect small then clear gain, growing with strength.
- Keep a feature group only if its gain exceeds the bootstrap range and does not worsen group gaps.
- Meaning: proves the pipeline can detect a signal if present; does NOT prove REDX data predicts repayment in the real world.

## 11. Fairness by group
Group columns: town_tier, shop_type, has_trade_license (audit only, not features); in public modes the audit columns from config `fairness.audit_only_columns`. For each group report AUC, mean score, band shares and calibration, each with a bootstrap range. Flag a gap above `flag_gap_points` only when the ranges do not overlap or it persists across seeds; small groups are noisy. Also compare calibration by group. Report what was measured; do not claim "fair".

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
