# REAL_DATA_SWITCH.md: what to do if ShopUp gives us anything

Principle: the pipeline stays the same; only the adapter, config and some feature choices change. Keep raw data outside the Git repo and keep a data register (see docs/DATA_REQUEST_SHOPUP.md).

## Three cases
| Case | What we get | What we can do | What we cannot do |
|---|---|---|---|
| 1. Nothing | No data | Synthetic default; method and negative control only | Any real-world claim |
| 2. Labels only | Loan outcomes (repaid within 30 days or not), maybe loan amounts and dates | Check label definition and base repayment rate against our synthetic assumption (75 to 85%); recalibrate score-to-probability mapping; set realistic band lines; validate class balance | Train a real model (no features); test REDX value; real feature-based fairness |
| 3. Extract | Labels plus some orders, deliveries, payments | Map to our tables via adapter; build whichever features are possible; real ablation (A to D as available); real group checks | Anything for feature groups not provided |

## Steps (any real data)
1. Write down their definitions: what is "late", "default", "repaid"; time zone; currency; whether outcomes are final.
2. Put raw files in a read-only folder outside the repo; log them in the data register (file, date, sender, rows, checksum, location, deletion date).
3. Implement the adapter (`src/adapters/shopup_real.py` or `label_only.py`). Never edit raw files. Pseudonymise IDs on arrival if not already.
4. Run validation: duplicate IDs, orphan rows, date order, missing rates, outcome definition, base rate. Send issues back to ShopUp.
5. Update `config/default.yaml`: label rules, split months (to match their history length), band lines, coverage weights. Record every change.
6. Decide which feature groups exist; drop the rest from the feature list and the ablation; update the dictionary.
7. Retrain and recalibrate. With few hundred rows prefer Logistic Regression and report wide bootstrap ranges.
8. Report real-data results separately from synthetic ones, in their own model-card section labelled "small real sample, not a validation".
9. Delete data as agreed after the event and note it in the register.

## Case 2 detail: labels only
Useful outputs even without features: base repayment rate; distribution of days late; share of loans excluded as too young; seasonality of repayment if dates exist; whether the 30-day rule fits how ShopUp treats default. Use these to tune the synthetic generator so it looks like reality (repayment share, lateness distribution), and say so in the pitch ("generator calibrated to ShopUp's real repayment rate").

## Timing
Feature freeze is Nov 1. Data arriving after Oct 26 becomes a bonus slide only; do not redesign.
