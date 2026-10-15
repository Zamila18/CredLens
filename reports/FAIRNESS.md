# Group audit (Phase 11 part 2)

Written by `python -m src.model.fairness --all-modes`. Measured on the validation months of each data mode; the test months are not used. Audit columns are never model inputs.

Ranking gap: AUC of the group minus AUC of the rest. Calibration gap: (predicted minus actual) of the group minus the same for the rest; positive means the model expects more repayment from the group than it shows. A gap above the line is flagged only if the ranges of the group and the rest do not overlap, or (synthetic data) it is above the line in every seed. Each group is compared with the rest, so a large gap in one group also shows, smaller and mirrored, in the groups compared with it.

This shows where the model measurably works differently on these data. It does not show that the model is fair, and it says nothing about groups not in the data. Many groups are checked, so a flag is a reason to look closer, not proof. A group with too few repaid or not-repaid loans shows its size only. India's validation period is one month, so its regional gaps may belong to that month only.

## synthetic_bd

Model synthetic_bd-20261015-005409-9db9d66, 5,853 validation loans, seeds [42, 7, 123], gap line 0.05.

Flagged: none.

| Column | Group | Loans | Repaid | Mean score | AUC | Ranking gap | Ranking | Calibration gap | Calibration |
|---|---|---|---|---|---|---|---|---|---|
| town_tier | city | 2,651 | 90.2% | 90.0 | 0.730 | +0.038 | no gap | +0.005 | no gap |
| town_tier | small_town | 1,750 | 90.5% | 89.8 | 0.690 | -0.028 | no gap | -0.004 | no gap |
| town_tier | metro | 1,452 | 90.5% | 89.8 | 0.695 | -0.019 | no gap | -0.002 | no gap |
| shop_type | grocery | 2,062 | 90.0% | 89.6 | 0.703 | -0.011 | no gap | +0.003 | no gap |
| shop_type | apparel | 1,134 | 90.3% | 90.2 | 0.737 | +0.034 | no gap | +0.004 | no gap |
| shop_type | other | 917 | 89.4% | 90.1 | 0.691 | -0.022 | no gap | +0.014 | no gap |
| shop_type | electronics | 907 | 92.4% | 90.1 | 0.694 | -0.017 | no gap | -0.021 | no gap |
| shop_type | pharmacy | 833 | 90.3% | 89.5 | 0.726 | +0.019 | no gap | -0.003 | no gap |
| has_trade_license | False | 3,517 | 90.2% | 89.9 | 0.725 | +0.040 | no gap | +0.003 | no gap |
| has_trade_license | True | 2,336 | 90.6% | 89.9 | 0.685 | -0.040 | no gap | -0.003 | no gap |

## kiva_asia

Model kiva_asia-20261014-135932-4198b26, 15,113 validation loans, seeds [42], gap line 0.05.

Flagged: borrower_genders = female: ranking; borrower_genders = male: ranking; country = Philippines: ranking; country = Pakistan: ranking; country = Pakistan: calibration; country = Indonesia: ranking; country = Indonesia: calibration.

| Column | Group | Loans | Repaid | Mean score | AUC | Ranking gap | Ranking | Calibration gap | Calibration |
|---|---|---|---|---|---|---|---|---|---|
| borrower_genders | female | 13,758 | 94.7% | 94.8 | 0.659 | +0.148 | flagged | +0.011 | no gap |
| borrower_genders | male | 1,319 | 95.4% | 94.0 | 0.516 | -0.142 | flagged | -0.014 | no gap |
| borrower_genders | mixed | 36 | - | - | - | - | too few loans to measure | - | too few loans to measure |
| country | Philippines | 10,857 | 94.4% | 95.1 | 0.816 | +0.489 | flagged | +0.027 | no gap |
| country | Vietnam | 790 | - | - | - | - | too few loans to measure | - | too few loans to measure |
| country | Tajikistan | 724 | - | - | - | - | too few loans to measure | - | too few loans to measure |
| country | Cambodia | 698 | - | - | - | - | too few loans to measure | - | too few loans to measure |
| country | Pakistan | 605 | 78.5% | 94.1 | 0.452 | -0.193 | flagged | +0.165 | flagged |
| country | Samoa | 466 | - | - | - | - | too few loans to measure | - | too few loans to measure |
| country | Mongolia | 396 | - | - | - | - | too few loans to measure | - | too few loans to measure |
| country | Indonesia | 253 | 83.8% | 92.3 | 0.390 | -0.255 | flagged | +0.087 | flagged |
| country | India | 111 | - | - | - | - | too few loans to measure | - | too few loans to measure |
| country | Timor-Leste | 89 | - | - | - | - | too few loans to measure | - | too few loans to measure |
| country | Kyrgyzstan | 76 | - | - | - | - | too few loans to measure | - | too few loans to measure |
| country | Nepal | 48 | - | - | - | - | too few loans to measure | - | too few loans to measure |

## taiwan_cc

Model taiwan_cc-20261014-135411-4198b26, 5,000 validation loans, seeds [42], gap line 0.05.

Flagged: none.

| Column | Group | Loans | Repaid | Mean score | AUC | Ranking gap | Ranking | Calibration gap | Calibration |
|---|---|---|---|---|---|---|---|---|---|
| SEX | 2 | 3,023 | 79.5% | 78.7 | 0.725 | -0.039 | no gap | -0.020 | no gap |
| SEX | 1 | 1,977 | 75.4% | 76.6 | 0.764 | +0.039 | no gap | +0.020 | no gap |
| EDUCATION | 2 | 2,353 | 76.5% | 76.8 | 0.743 | +0.001 | no gap | +0.006 | no gap |
| EDUCATION | 1 | 1,724 | 79.8% | 80.3 | 0.728 | -0.021 | no gap | +0.008 | no gap |
| EDUCATION | 3 | 845 | 76.2% | 75.5 | 0.766 | +0.029 | no gap | -0.009 | no gap |
| EDUCATION | 5 | 49 | - | - | - | - | too few loans to measure | - | too few loans to measure |
| EDUCATION | 4 | 19 | - | - | - | - | too few loans to measure | - | too few loans to measure |
| EDUCATION | 0 | 7 | - | - | - | - | too few loans to measure | - | too few loans to measure |
| EDUCATION | 6 | 3 | - | - | - | - | too few loans to measure | - | too few loans to measure |
| MARRIAGE | 2 | 2,630 | 79.6% | 78.2 | 0.744 | +0.003 | no gap | -0.029 | no gap |
| MARRIAGE | 1 | 2,299 | 76.0% | 77.5 | 0.741 | -0.005 | no gap | +0.028 | no gap |
| MARRIAGE | 3 | 63 | - | - | - | - | too few loans to measure | - | too few loans to measure |
| MARRIAGE | 0 | 8 | - | - | - | - | too few loans to measure | - | too few loans to measure |
| age_band | 30 to 39 | 1,855 | 79.6% | 78.8 | 0.766 | +0.037 | no gap | -0.012 | no gap |
| age_band | under 30 | 1,606 | 77.8% | 77.2 | 0.749 | +0.010 | no gap | -0.008 | no gap |
| age_band | 40 to 49 | 1,093 | 75.8% | 77.4 | 0.721 | -0.028 | no gap | +0.020 | no gap |
| age_band | 50 and over | 446 | 76.0% | 77.4 | 0.682 | -0.067 | gap, but within the ranges | +0.015 | no gap |

## india_ltfs

Model india_ltfs-20261014-135734-4198b26, 66,788 validation loans, seeds [42], gap line 0.05.

Flagged: State_ID = 13: calibration; State_ID = 12: ranking; State_ID = 12: calibration; State_ID = 19: calibration.

| Column | Group | Loans | Repaid | Mean score | AUC | Ranking gap | Ranking | Calibration gap | Calibration |
|---|---|---|---|---|---|---|---|---|---|
| age_band | 25 to 34 | 26,144 | 80.3% | 81.1 | 0.612 | +0.001 | no gap | +0.013 | no gap |
| age_band | 35 to 44 | 16,681 | 82.1% | 80.7 | 0.613 | +0.003 | no gap | -0.019 | no gap |
| age_band | under 25 | 13,108 | 78.6% | 80.4 | 0.591 | -0.025 | no gap | +0.022 | no gap |
| age_band | 45 to 54 | 8,711 | 82.1% | 80.7 | 0.631 | +0.023 | no gap | -0.016 | no gap |
| age_band | 55 and over | 2,144 | 84.7% | 81.0 | 0.636 | +0.026 | no gap | -0.039 | no gap |
| State_ID | 4 | 12,448 | 82.3% | 79.5 | 0.618 | +0.006 | no gap | -0.034 | no gap |
| State_ID | 3 | 10,355 | 82.5% | 82.9 | 0.600 | -0.011 | no gap | +0.005 | no gap |
| State_ID | 6 | 8,882 | 82.4% | 80.3 | 0.644 | +0.038 | no gap | -0.025 | no gap |
| State_ID | 13 | 5,403 | 71.1% | 82.0 | 0.595 | -0.022 | no gap | +0.120 | flagged |
| State_ID | 9 | 4,751 | 81.0% | 79.6 | 0.599 | -0.013 | no gap | -0.015 | no gap |
| State_ID | 8 | 4,165 | 80.4% | 80.2 | 0.628 | +0.018 | no gap | -0.003 | no gap |
| State_ID | 5 | 2,761 | 82.3% | 81.9 | 0.637 | +0.027 | no gap | -0.003 | no gap |
| State_ID | 1 | 2,654 | 84.0% | 80.9 | 0.639 | +0.029 | no gap | -0.033 | no gap |
| State_ID | 14 | 2,622 | 75.6% | 79.1 | 0.617 | +0.008 | no gap | +0.037 | no gap |
| State_ID | 7 | 2,216 | 82.6% | 81.9 | 0.596 | -0.015 | no gap | -0.006 | no gap |
| State_ID | 11 | 1,858 | 80.7% | 79.0 | 0.638 | +0.028 | no gap | -0.017 | no gap |
| State_ID | 18 | 1,583 | 79.7% | 79.9 | 0.601 | -0.010 | no gap | +0.002 | no gap |
| State_ID | 12 | 1,339 | 79.4% | 84.4 | 0.540 | -0.073 | flagged | +0.051 | flagged |
| State_ID | 15 | 1,232 | 82.0% | 81.5 | 0.612 | +0.002 | no gap | -0.005 | no gap |
| State_ID | 2 | 1,196 | 78.7% | 80.2 | 0.631 | +0.021 | no gap | +0.016 | no gap |
| State_ID | 10 | 1,066 | 84.4% | 81.5 | 0.635 | +0.025 | no gap | -0.029 | no gap |
| State_ID | 17 | 973 | 76.5% | 80.0 | 0.635 | +0.025 | no gap | +0.036 | no gap |
| State_ID | 16 | 761 | 83.8% | 80.4 | 0.641 | +0.030 | no gap | -0.035 | no gap |
| State_ID | 19 | 406 | 88.7% | 80.1 | 0.603 | -0.008 | no gap | -0.086 | flagged |
| State_ID | 20 | 60 | - | - | - | - | too few loans to measure | - | too few loans to measure |
| State_ID | 21 | 35 | - | - | - | - | too few loans to measure | - | too few loans to measure |
| State_ID | 22 | 22 | - | - | - | - | too few loans to measure | - | too few loans to measure |
| Employment.Type | Self employed | 37,370 | 79.4% | 81.1 | 0.603 | -0.022 | no gap | +0.038 | no gap |
| Employment.Type | Salaried | 27,271 | 82.7% | 80.4 | 0.628 | +0.025 | no gap | -0.038 | no gap |
| Employment.Type | not stated | 2,147 | 81.1% | 81.1 | 0.597 | -0.015 | no gap | -0.001 | no gap |

## homecredit

Model homecredit-20261014-135834-4198b26, 8,333 validation loans, seeds [42], gap line 0.05.

Flagged: age_band = under 30: ranking; REGION_RATING_CLIENT = 2: ranking.

| Column | Group | Loans | Repaid | Mean score | AUC | Ranking gap | Ranking | Calibration gap | Calibration |
|---|---|---|---|---|---|---|---|---|---|
| CODE_GENDER | F | 5,568 | 92.9% | 92.2 | 0.757 | +0.033 | no gap | -0.020 | no gap |
| CODE_GENDER | M | 2,765 | 90.1% | 91.3 | 0.724 | -0.033 | no gap | +0.020 | no gap |
| age_band | 30 to 39 | 2,173 | 90.2% | 91.5 | 0.750 | +0.009 | no gap | +0.018 | no gap |
| age_band | 40 to 49 | 2,097 | 92.9% | 92.9 | 0.747 | +0.004 | no gap | +0.000 | no gap |
| age_band | 50 to 59 | 1,893 | 93.8% | 93.1 | 0.729 | -0.016 | no gap | -0.010 | no gap |
| age_band | under 30 | 1,170 | 88.5% | 88.0 | 0.674 | -0.079 | flagged | -0.005 | no gap |
| age_band | 60 and over | 1,000 | 94.5% | 93.5 | 0.765 | +0.023 | no gap | -0.012 | no gap |
| REGION_RATING_CLIENT | 2 | 6,207 | 92.0% | 92.1 | 0.729 | -0.066 | flagged | +0.007 | no gap |
| REGION_RATING_CLIENT | 3 | 1,271 | 88.9% | 89.2 | 0.763 | +0.024 | no gap | +0.004 | no gap |
| REGION_RATING_CLIENT | 1 | 855 | 96.3% | 94.5 | 0.798 | +0.061 | gap, but within the ranges | -0.019 | no gap |
