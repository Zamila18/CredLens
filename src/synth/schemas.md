# Column dictionary for the synthetic data (`synthetic_bd`)

Owner role: B (data engineer). Written with `generate.py` in Phase 1.

Everything described here is **generated**. No row describes a real merchant. The column names for
every table also live in code: `src/adapters/base.py` (`CONTRACT`). All ids are text. Dates are ISO
text (`YYYY-MM-DD`); timestamps are `YYYY-MM-DDTHH:MM:SS`.

## Where the files are

`python tasks.py data` writes one folder per delivery signal strength:

```
data/raw/synthetic_bd/strength_0/      delivery data is pure noise (the negative control)
data/raw/synthetic_bd/strength_0.5/    weak signal (the default)
data/raw/synthetic_bd/strength_1/      strong signal
```

Only `deliveries.csv` differs between the three folders. The folder is gitignored.

## The time window

| Period | Dates with the default config | What happens |
|---|---|---|
| Main window (`data.months`, 18 months) | 2025-01-01 to 2026-06-30 | Merchants are onboarded. Every loan issued here has an outcome |
| Tail (`generator.observation_tail_days`, 60 days) | 2026-07-01 to 2026-08-29 | Activity continues. Loans issued here are too young to judge: the pending cases for the review queue |

"Today" for the data is the last day of the tail.

## merchants (20,000 rows; the single master table)

| Column | Meaning |
|---|---|
| merchant_id | `M000001` ... Unique |
| onboarded_at | Day the merchant joined, spread evenly over the main window |
| district | A Bangladesh district name that fits the town tier |
| town_tier | metro / city / small_town. **Audit only, never a model input** |
| shop_type | grocery / pharmacy / apparel / electronics / other. **Audit only** |
| has_trade_license | True/False, more common in metro. **Audit only** |
| consent_data_use | True/False (about 95% true). No valid consent means no scoring |
| questionnaire_done | True/False (about 40% true) |

## purchases (about 1.85 million rows): what the merchant BUYS

Mokam-style wholesale purchases. These are never the merchant's sales.

| Column | Meaning |
|---|---|
| purchase_id | `PU00000001` ... Unique |
| merchant_id | Who bought |
| purchase_date | Never before onboarding |
| amount_bdt | Purchase value in taka |
| category | A product category that belongs to the merchant's shop type |
| supplier_id | `S0001` to `S0400`. Reliable merchants return to their main suppliers more often |

How it is generated: a weekly purchase count that depends on town tier, hidden reliability, a
per-merchant growth trend, the real Bangladesh monthly seasonality
(`config/calibration/bb_mfs_merchant_payment.csv`) and chance. Thin-file merchants (about 35%) start at a
small fraction of their normal rate and ramp up over about six months.

## deliveries (about 1.2 million rows): parcels the merchant sends

REDX-style outgoing parcels. About 25% of merchants have none at all.

| Column | Meaning |
|---|---|
| delivery_id | `D00000001` ... Unique |
| merchant_id | Who sent the parcel |
| dispatched_at | Timestamp |
| delivered_at | Timestamp; empty unless the status is delivered |
| status | delivered / returned / failed / cancelled |
| return_reason | Empty when delivered or cancelled. `address_issue`, `rider_issue`: logistics problems that never depend on the merchant. `refused`, `wrong_item`, `other`: merchant-attributable |
| is_cod | True/False: cash on delivery |
| cod_remitted_on_time | True/False for delivered cash-on-delivery parcels; empty otherwise |

How the signal strength works: merchant-attributable returns, failures, delivery speed, cash remittance
and parcel volume depend on hidden reliability multiplied by the strength. At strength 0 they do not
depend on it at all. A share of returns and failures (`data.logistics_noise_share`, 40%) is always
logistics noise.

## loans (about 30,800 rows)

Baki-style credit. One to three loans per merchant; the first no earlier than 45 days after onboarding.
A merchant who never repaid gets no further loan.

| Column | Meaning |
|---|---|
| loan_id | `L0000001` ... Unique |
| merchant_id | Borrower |
| issued_at | The cutoff date for features: only earlier data may be used |
| limit_bdt | Credit limit; grows with town tier and with each loan |
| outcome_label | 1 = repaid within 30 days of the due date; 0 = later or never. **Empty** for loans younger than 60 days |
| label_observed_at | Day the outcome became known (due date + 30 days); empty when the label is empty |

About 90% of judged loans are labelled 1. That share is a team assumption, explained in
`config/default.yaml` (`generator.repayment_share_target`).

## payments (one row per loan)

| Column | Meaning |
|---|---|
| payment_id | `P0000001` ... Unique |
| merchant_id, loan_id | Which loan this repays |
| due_date | Issue date + 30 days |
| paid_date | Empty if not paid by the end of the window |
| amount_due_bdt | The used part of the limit |
| amount_paid_bdt | Equal to the amount due when paid, otherwise 0 |

## questionnaire (about 8,000 rows; only merchants with questionnaire_done)

| Column | Meaning |
|---|---|
| merchant_id | One row per merchant |
| spend1, spend2, save1, save2, borrow1, borrow2, plan1, plan2 | Answers from 1 to 5 |
| stress | 1 to 5, reverse-coded: a low number means low stress |
| confidence | 1 to 5 |
| answered_at | Within 30 days of onboarding |

Weakly related to hidden reliability. Shown beside the score as a directional signal; never inside the
headline model.

## consents

| Column | Meaning |
|---|---|
| consent_id | `C000001` ... Unique |
| merchant_id | Who gave consent |
| purpose | `credit_readiness_assessment` |
| data_categories | Which streams are covered, separated by `|` |
| granted_at, expires_at | Valid for two years from onboarding |
| revoked_at | Empty for a valid consent |

Consenting merchants have one valid record. Of the non-consenting ones, about half have a revoked record
and the rest have none.

## Files that are not part of the data contract

| File | What it is | Who may read it |
|---|---|---|
| `_latent_truth.csv` | The hidden truth: each merchant's reliability, thin-file flag, whether they have delivery data, purchase trend | **Generator tests only.** The adapter never reads it, so no feature or model can see it |
| `_meta.json` | Seed, signal strength, window dates, row counts, repaid share | Anyone; it describes the run |
