# Demo batch: what to expect after the import

Written by `python -m src.synth.demo_batch`. Scored by the saved model as of 2026-08-30, the last day of the demo data, exactly as the API scores them after the load. Synthetic data, not real merchants.

| Merchant | Kind | Consent | Score | Coverage | Band | Waiting since |
|---|---|---|---|---|---|---|
| D00001 | Strong: a high score with enough evidence | valid | 96 | 100% | Strong | 2026-08-03 |
| D00002 | Needs more info: a thin file (coverage under the line) | valid | 75 | 35% | Needs more info | 2026-07-31 |
| D00003 | Review with a low score (under the warning line) | valid | 64 | 90% | Review | 2026-07-27 |
| D00004 | No valid consent: listed, but no score and no decision | none | - | - | no score | 2026-07-19 |
| D00005 | No REDX delivery records: lower coverage, never a lower score by itself | valid | 84 | 75% | Review | 2026-08-26 |

Deliberate mistakes the check must report (the rest loads):
- merchants.csv: M000031 is already in the database (an import never overwrites).
- purchases.csv: D-BAD-DATE has the impossible date 2026-13-40.
- deliveries.csv: D-BAD-STATUS has the unknown status 'lost_in_space'.

Rows per file: merchants 6, loans 9, purchases 291, deliveries 138, payments 9, questionnaire 3, consents 4.
