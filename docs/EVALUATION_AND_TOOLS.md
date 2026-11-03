# Model evaluation, fair-use checks and tool decisions (Phase 9)

Written Oct 31, 2026, for the model in use: `synthetic_bd-20261015-005409-9db9d66` (logistic regression, file `src/model/artifacts/synthetic_bd/model.joblib`, SHA-256 starting `a9fcc5d3`). Nothing was retrained, refitted or replaced in this phase.

**Read this first.** Every number below comes from synthetic, Bangladesh-shaped data made by our own generator. These numbers test the code and the method. They are **not** evidence of how the model would do for real Bangladesh retailers or for ShopUp. The public real-label checks are in `reports/REAL_LABEL_RESULTS.md`.

## 1. What the score is

| Question | Answer, from the code |
|---|---|
| What is predicted | The probability that a loan is repaid in full within the rule in `config/default.yaml` (label 1 = repaid). Higher is better. |
| Score | `round(100 × probability)`, 0 to 100 (`src/model/score.py`). |
| Calibration | None. The method was picked automatically on the validation months: Platt and isotonic scaling did not lower the out-of-fold Brier score enough to be kept. Calibration error: 0.012 on validation and 0.008 on the test months. Reliability chart: `reports/synthetic_bd/calibration_test.png`. |
| Bands | Strong: score ≥ 90 and coverage ≥ 0.45. Needs more info: coverage < 0.45, whatever the score. Review: everything else. A low-score warning is shown under 70. All are settings in `config/default.yaml` (`score`), not code. |
| Missing data | An input the merchant has no data for gets 0 points. It lowers coverage, never the score (`tests/test_score_inputs.py`, `tests/test_reasons.py`). |
| Requested amount | Not a model input. An application's amount and the 0 limit on its loan row never reach the features (`tests/test_application_scoring_safety.py`). |
| Decisions | No code path approves or declines. The score suggests; an officer decides (`tests/test_no_autodecision.py`). |

## 2. How well it ranks and how honest its probabilities are

The data are split by loan date: training from Jan 2025, validation from Jan 2026, and a held-back test period from Apr to Jun 2026. Each of the 3 looks at the test months is logged in `reports/synthetic_bd/test_set_use.json`; this phase made no new look.

| | Validation (5,853 loans, 9.6% not repaid) | Test (6,023 loans, 9.8% not repaid) |
|---|---|---|
| ROC-AUC (95% range) | 0.710 (0.688 to 0.729) | 0.728 (0.707 to 0.749) |
| PR-AUC for "not repaid" | 0.230 (0.200 to 0.265) | 0.248 (0.214 to 0.281) |
| Brier score | 0.0819 | 0.0818 |
| Always-the-average baseline | AUC 0.50, Brier 0.0871 | |
| Simpler model (purchases only) | AUC 0.667. The full model adds +0.043 (+0.028 to +0.060). | |
| LightGBM challenger | AUC +0.013 over logistic regression, range +0.003 to +0.021 | |

Ranges are from 500 bootstrap resamples. Coverage matters: on validation, AUC is 0.583 for loans under the coverage line and 0.734 for the rest. That is why low coverage gives "Needs more info" instead of a score band.

## 3. What happens at each line (new in this phase)

`python -m src.model.operating_points` writes `reports/synthetic_bd/operating_points.json`. It uses the validation months only. In this table, "flagged" means the line puts a loan forward for a closer look, and the event is "not repaid".

| Line | Share flagged | Precision | Recall |
|---|---|---|---|
| Score under 70 (low-score warning) | 3.4% | 0.357 | 0.126 |
| Score under 90 (not Strong) | 33.5% | 0.176 | 0.613 |
| Band is not Strong | 44.1% | 0.157 | 0.720 |
| Band is Needs more info | 15.4% | 0.117 | 0.186 |

These shares match the training report exactly (3.4% warned, 55.9% Strong), which confirms that the saved file reproduces the reported model.

How to read the table:
- The low-score warning is rare and about 1 in 3 of the loans it marks are not repaid, but it catches only 13% of loans that go unpaid.
- "Not Strong" catches 72% of unpaid loans by putting 44% of loans in front of an officer.
- Needs more info is about missing evidence, not risk: its unpaid rate (11.7%) is close to the average (9.6%), which is how it is designed.

## 4. Leakage checks

| Risk | Status | Where it is checked |
|---|---|---|
| Data on or after a loan's cutoff used for that loan | None found. A planted future row is caught. | `tests/test_leakage.py` |
| Requested amount or limit of the scored loan in its own inputs | Not an input. | `tests/test_application_scoring_safety.py` |
| An application counted as past credit, or a payment against an application | Refused by code and by database triggers. | `tests/test_application_scoring_safety.py`, `tests/test_intake_records.py` |
| The same merchant in more than one period | Yes, and expected with a time split: 2,180 merchants have loans in both training and validation, and 2,338 of the 5,853 validation loans belong to a merchant with an earlier training loan. Each loan is scored only from history before its own cutoff, and its label is about that loan only. A random split by row would have been the real leak; the time split avoids it. | `reports/synthetic_bd/operating_points.json` |

## 5. How the reasons are made

- **Method.** `src/model/explain.py` computes exact Shapley values of the calibrated probability. The baseline is the average merchant: every input missing, so the model's fill-in step uses the training averages. Every subset of the inputs the merchant has is evaluated (2ⁿ subsets, n ≤ 14; there are 10 inputs). It is not an approximation and not a rule.
  - Points = 100 × the Shapley value, so baseline + all points = the exact score.
  - A test checks the values against the SHAP library's exact explainer to 1e-8 (`tests/test_reasons.py`). SHAP is used only as that test reference; the app does not import it.
- **What a reason means.** A reason is a feature-level description of this merchant's data compared with the average merchant. It is not a cause. It is never tied to one invoice, because every input sums up many records. In the officer workspace each reason links to its record group, never to a single record.
- **Stability tests added in this phase:**
  - nudging one input by a relative 1e-9 moves no input's points by more than 0.01 and flips no reason above 0.05 points;
  - the order of the inputs does not change the result.

  Tests that already existed: the same input gives the same reasons; a better-than-average value never lowers the score; missing inputs give 0 points.
- **Decision.** Keep the current method. LIME would add a second, approximate local model next to an exact one, which brings no gain and adds perturbation choices to defend. An LLM to rephrase reasons is not added: the sentences come from the feature dictionary and are tested to be true for the merchant.

## 6. LightGBM

LightGBM is already a challenger, trained on the same split with the same metrics. The rule in `config/default.yaml` keeps it only if the whole range of its AUC gain reaches +0.010. The gain is +0.013, but the range runs from +0.003 to +0.021, so logistic regression stays. That keeps the model easier to explain and its directions checkable. No change in this hackathon.

## 7. OCR

Deferred. EasyOCR and Tesseract are not installed. OCR needs representative documents from a provider and permission to use them. Any future version would need a person to check the text before it is saved, would never send documents to an outside AI service by default, and would never be a required step. Text read from a photo does not prove a document is genuine or belongs to the merchant.

## 8. Fairness and possible harm

- **What can be checked.** `reports/synthetic_bd/fairness.json` compares town tier, shop type and trade licence on the validation months, over 3 seeds. These columns are for audit only and are never model inputs. No group is flagged: repaid shares are 0.894 to 0.924 and mean predictions 0.895 to 0.902 across groups.
- **What cannot be checked.** These groups are synthetic, so they say nothing about real groups. The synthetic data holds no gender, age, religion or disability, and none is invented. Fairness for real Bangladesh retailers cannot be established until real data and lawful group information exist. A library such as Fairlearn would not change that.
- **Plausible harms to watch in a pilot:**
  - shops with few records (first borrowers, shops new to the platform) get "Needs more info" far more often (28% of first loans against 0.1% of repeat loans on validation), which could delay them;
  - shops whose suppliers or couriers are not on any connected platform look thinner;
  - delivery returns can come from riders or addresses, not the shop (shown as a caveat on every merchant page).
  - Counter-measures already in place: missing data never lowers the score, delivery data is optional, the questionnaire sits beside the score and not inside it, and an officer always decides.

## 9. Tool decisions

| Tool | Problem it would solve | Present? | Decision |
|---|---|---|---|
| openpyxl 3.1.5 | Read .xlsx purchase sheets | Yes, added in Phase 7 with approval | Keep. Used only in `src/intake/spreadsheet.py`; fallback: typed entry. |
| scikit-learn, pandas | Model, metrics, data | Yes | Keep. All of the evaluation above uses them. |
| SHAP 0.49 | Check that the reasons are true SHAP values | Yes (requirements) | Keep as a test reference only. Not needed at run time. |
| LightGBM 4.7 | Challenger model | Yes | Keep as a challenger. Not switched (section 6). |
| LIME | Another local explanation | No | Not added (section 5). |
| Fairlearn | Group metrics | No | Not added. The existing `src/model/fairness.py` covers what the synthetic groups allow; there is no real group data to add. |
| Evidently | Drift monitoring | No | Later, for a pilot with real data. Not P0. |
| Playwright | Automated browser tests | No | Not added. Pages were checked by hand in the app's built-in browser at 390, 768 and 1280 px; API tests cover the rules. Worth adding before a pilot, with its own approval (it downloads browsers). |
| EasyOCR, Tesseract | Read paper memos | No | Deferred (section 7). |
| An LLM | Rephrase reasons, read documents | No | Not added. Fixed, tested sentences are safer for credit explanations. |

## 10. How to repeat this

```
python -m src.model.operating_points
python -m pytest tests/test_reasons.py tests/test_operating_points.py tests/test_leakage.py tests/test_application_scoring_safety.py
```
