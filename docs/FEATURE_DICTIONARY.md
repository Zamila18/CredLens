# FEATURE_DICTIONARY.md

Each feature has: name, group, definition (as of loan cutoff), direction (what higher usually means), and a pair of reason sentences (positive when it raised the score, negative when it lowered it) in English and Bangla. Code must load these from `src/features/dictionary.yaml` (create it from this table). Sentences are observations, never accusations. Bangla text should be reviewed by a native speaker before the demo.

| name | group | definition | higher means | positive sentence (EN / BN) | negative sentence (EN / BN) |
|---|---|---|---|---|---|
| purchases_90d | A purchases | Mokam purchase orders placed by the merchant in the 90 days before cutoff | active restocking | "The shop restocks regularly, with many recent purchases." / "দোকানটি নিয়মিত মাল কেনে, সাম্প্রতিক কেনাকাটা অনেক।" | "Recent restocking activity is low." / "সাম্প্রতিক মাল কেনা কম।" |
| purchase_value_90d | A | Total purchase value, 90 days | larger business | "Recent stock purchases are healthy in size." / "সাম্প্রতিক মাল কেনার পরিমাণ ভালো।" | "Recent stock purchases are small." / "সাম্প্রতিক মাল কেনার পরিমাণ কম।" |
| basket_growth | A | Purchase value last 90 days vs the 90 before, % | growth | "Stock purchases are growing compared with the previous three months." / "আগের তিন মাসের তুলনায় মাল কেনা বাড়ছে।" | "Stock purchases are falling compared with the previous three months." / "আগের তিন মাসের তুলনায় মাল কেনা কমছে।" |
| purchase_volatility | A | Std. dev. of weekly purchase value / mean | unstable | "Weekly restocking is steady." / "সাপ্তাহিক মাল কেনা স্থিতিশীল।" | "Weekly restocking swings a lot." / "সাপ্তাহিক মাল কেনায় ওঠানামা বেশি।" |
| purchase_regularity | A | Share of weeks with at least one purchase | consistent | "The shop restocks in most weeks." / "দোকান বেশিরভাগ সপ্তাহে মাল কেনে।" | "The shop restocks in few weeks." / "দোকান কম সপ্তাহে মাল কেনে।" |
| category_diversity | A | Number of product categories purchased | diversified | "Purchases cover several product categories." / "কেনাকাটা একাধিক ক্যাটাগরিতে ছড়ানো।" | "Purchases depend on very few categories." / "কেনাকাটা অল্প কয়েকটি ক্যাটাগরির ওপর নির্ভর করে।" |
| supplier_repeat_share | A | Share of purchases from suppliers used before | stable sourcing | "The shop buys steadily from familiar suppliers." / "দোকান পরিচিত সরবরাহকারীর কাছ থেকে নিয়মিত কেনে।" | "Sourcing changes often between suppliers." / "সরবরাহকারী প্রায়ই বদলায়।" |
| parcel_volume_90d | C (sales proxy) | Outgoing REDX parcels, 90 days (only for merchants who sell online) | more sales | "The shop sends many parcels to its customers." / "দোকান তার ক্রেতাদের কাছে অনেক পার্সেল পাঠায়।" | "Few parcels sent to customers recently." / "সাম্প্রতিক সময়ে ক্রেতাদের কাছে পার্সেল কম গেছে।" |
| avg_pay_delay_days | B payments | Mean days late over past payments | worse | "Past payments were made close to the due date." / "আগের পেমেন্ট প্রায় নির্ধারিত সময়ে হয়েছে।" | "Past payments were often late." / "আগের পেমেন্ট প্রায়ই দেরিতে হয়েছে।" |
| late_pay_count_90d | B | Payments over 7 days late, 90 days | worse | "No recent late payments." / "সাম্প্রতিক কোনো দেরির পেমেন্ট নেই।" | "There were late payments recently." / "সাম্প্রতিক সময়ে পেমেন্টে দেরি হয়েছে।" |
| ontime_payment_rate | B | Share of payments within 3 days of due | reliable | "Most payments arrive on time." / "বেশিরভাগ পেমেন্ট সময়মতো আসে।" | "Few payments arrive on time." / "কম পেমেন্ট সময়মতো আসে।" |
| credit_utilisation | B | Used limit / limit | stretched | "Credit use is moderate." / "ঋণের ব্যবহার মাঝারি।" | "Credit use is close to the limit." / "ঋণের ব্যবহার সীমার কাছাকাছি।" |
| delivered_rate | C deliveries (context only) | Delivered parcels / dispatched, 90 days | reliable fulfilment | "Most parcels are delivered successfully." / "বেশিরভাগ পার্সেল সফলভাবে পৌঁছায়।" | "Many parcels are not delivered." / "অনেক পার্সেল পৌঁছায় না।" |
| return_rate_90d | C | Merchant-attributable returns (refused, wrong item) / total, 90 days; address and rider returns left out when the reason is recorded | worse | "Delivery returns are lower than similar shops." / "সমান ধরনের দোকানের তুলনায় ডেলিভারি ফেরত কম।" | "Returns are higher than similar shops; this may reflect delivery conditions." / "সমান ধরনের দোকানের তুলনায় ফেরত বেশি; এটা ডেলিভারির পরিস্থিতির কারণেও হতে পারে।" |
| failed_rate_90d | C | Failed parcels / total, 90 days; failures tagged address_issue or rider_issue excluded | worse | "Few delivery failures." / "ডেলিভারি ব্যর্থতা কম।" | "Delivery failures are higher than usual; this may reflect address or rider issues." / "ডেলিভারি ব্যর্থতা বেশি; ঠিকানা বা রাইডারের সমস্যার কারণেও হতে পারে।" |
| cod_remit_ontime_rate | C | Share of cash-on-delivery money passed back on time | reliable | "Cash-on-delivery money is passed back on time." / "ক্যাশ-অন-ডেলিভারির টাকা সময়মতো ফেরত আসে।" | "Cash-on-delivery money is often late." / "ক্যাশ-অন-ডেলিভারির টাকা প্রায়ই দেরিতে আসে।" |
| dispatch_to_delivery_hours | C | Median hours from dispatch to delivery | slower | "Parcels reach customers quickly." / "পার্সেল দ্রুত ক্রেতার কাছে পৌঁছায়।" | "Parcels take long to reach customers." / "পার্সেল পৌঁছাতে বেশি সময় লাগে।" |
| delivery_data_thin | C | Fewer than 20 parcels in 90 days (flag) | less certain | n/a | "Delivery history is thin, so the picture is less certain." / "ডেলিভারির ইতিহাস কম, তাই চিত্রটি কম নিশ্চিত।" |
| q_spend, q_save, q_borrow, q_plan | D questionnaire | Four subscores (1-5) from the 10 items | healthier habits | "Self-reported habits look healthy (directional)." / "নিজের দেওয়া তথ্য অনুযায়ী অভ্যাস ভালো (ইঙ্গিতমাত্র)।" | "Self-reported habits suggest some strain (directional)." / "নিজের দেওয়া তথ্য অনুযায়ী কিছু চাপ আছে (ইঙ্গিতমাত্র)।" |
| q_stress, q_confidence | D | Context items | n/a | same as above | same as above |

Coverage-only features (not used for the score reasons): history_months, n_purchases_total, n_deliveries_total, n_payments_total, share_of_groups_present.

Rules
- Questionnaire reasons must carry the word "directional" / "ইঙ্গিতমাত্র".
- Never show raw feature names to officers; show the sentence, with the number when helpful ("Returns 7.5% vs typical 4%").
- If a feature is missing for a merchant, do not generate a reason for it; mention missing data via coverage.
- A sentence is shown only when it is true for the merchant. Contributions are measured against the average merchant, so "better than average" alone is not enough for a plain claim. `shown_when` in `dictionary.yaml` holds the conditions: growth sentences need growth above or below zero; "No recent late payments" needs none and "There were late payments" needs at least one; "Most / Few payments arrive on time" need more or less than half; "close to the due date" needs an average delay of at most 3 days; "close to the limit" needs more than 80% of the limit in use; "passed back on time" needs more than half on time. Sentences that compare with similar shops need no condition. When a plain sentence is not true for the merchant, the comparing sentence under `otherwise` in `dictionary.yaml` is shown instead (for example "Credit use is higher than at similar shops." / "সমান ধরনের দোকানের তুলনায় ঋণের ব্যবহার বেশি।"), so a reason is never dropped for lack of a true sentence. These ten comparing sentences were added on Oct 13 and their Bangla needs the same native-speaker review as the rest.
- The number beside a reason comes from `detail` in `dictionary.yaml` (a label and a format), for example "Returns 11.1% vs average 6.8%".
- Questionnaire (group D) is shown beside the score, not used in the headline model. Its reasons appear in the questionnaire panel only.
- Public-data sources add their own entries (e.g. kiva: loan_amount_usd, term_months, repayment_interval_irregular, sector; taiwan_cc: ontime_share_6m, worst_delay_6m, pay_to_bill_ratio, limit_utilisation; homecredit: inst_ontime_rate, inst_mean_days_late, pos_months_active). Claude Code adds these to dictionary.yaml with EN/BN sentences when building the adapters.

## Features of the public data modes (Phase 7)

Each public mode has its own inputs, built only from fields that source really has. They live in `dictionary.yaml` under `source_features.<mode>` and are computed by a small builder per mode (`src/features/source_features.py`). Everything after the feature table is shared with the synthetic data. The same rules apply: behaviour only as model inputs, amounts of data as context and coverage, empty is not zero, every input says which way it points, and sentences are true or comparing. Sentences say "client", not "shop".

### `taiwan_cc` (built Oct 13; code `src/features/taiwan_cc.py`)

| Feature | Meaning | Higher is |
|---|---|---|
| ontime_share_6m | Of the six months in which the card was used, the share with no late payment | better |
| worst_delay_6m | Longest payment delay in six months, in months | worse |
| latest_delay_months | Delay in the most recent month, in months | worse |
| delay_trend_6m | Average delay of the three newest months minus the three oldest | worse |
| pay_to_bill_ratio | Amount paid in five months divided by the bills of the month before each | better |
| limit_utilisation | Average bill divided by the credit limit | worse |
| balance_growth_6m | Newest bill minus oldest bill, divided by the credit limit | worse |
| no_payment_month_share | Of the months that followed a bill, the share in which nothing was paid | worse |

Context only (never model inputs): `credit_limit`, `months_card_used`, `months_with_bill`. A month with status -2 (card not used) is left out of every lateness feature, so a client who never used the card has empty features and low coverage, not a perfect record. A negative bill (credit balance) counts as zero.

### `india_ltfs` (built Oct 13; code `src/features/india_ltfs.py`)

| Feature | Meaning | Higher is |
|---|---|---|
| down_payment_share | One minus the loan-to-value: the part of the vehicle's price paid up front | better |
| bureau_score | Credit-bureau score at disbursement, only where the bureau gave one | better |
| overdue_account_share | Overdue earlier loans divided by all earlier loans | worse |
| delinquent_accounts_6m | Loans that fell behind in the six months before disbursement | worse |
| new_accounts_6m | New loans taken in the six months before disbursement | worse |
| loan_enquiries | Loan enquiries on the bureau record | worse |

Context only (never model inputs): `loan_amount`, `asset_cost`, `earlier_loans`, `credit_history_months`, `average_account_age_months`. A borrower with no bureau record has the five bureau features empty, not zero. The small codes the file carries for "not scored" (for example 15) are not read as scores. Sentences say "borrower".

### `homecredit` (built Oct 13; code `src/features/homecredit.py`; country not stated)

| Feature | Meaning | Higher is |
|---|---|---|
| inst_ontime_rate | Share of the instalments on earlier loans paid on or before the due day | better |
| inst_mean_days_late | Average days late over those instalments (0 for one paid on time) | worse |
| inst_late_30d_share | Share paid more than 30 days late, or still unpaid after 30 days | worse |
| inst_paid_short_share | Share where less than 99% of the amount due was paid | worse |
| inst_recent_ontime_rate | The on-time share over instalments due in the last 365 days | better |
| pos_months_overdue_share | Share of the monthly records of earlier store and cash loans with an amount overdue | worse |
| annuity_to_income | The loan's repayment amount divided by the stated income | worse |
| credit_to_goods_ratio | The loan amount divided by the price of the goods | worse |
| external_score | Average of the available scores "from external data sources" (group X) | better |

Context only (never model inputs): `loan_amount`, `stated_income`, `past_instalments`, `pos_months_recorded`. An instalment paid in several parts is put together before it is judged. An instalment not paid by the day of the application counts as late by the days gone by since it was due. An applicant with no earlier loans has the six history features empty. Sentences say "applicant".

### `kiva_asia` (built Oct 13; code `src/features/kiva_asia.py`)

| Feature | Meaning | Higher is |
|---|---|---|
| repayment_term_months | Months over which the loan is to be repaid (group L) | worse |
| partner_past_default_rate | Of the field partner's earlier loans with an outcome known on the posting day, the share that defaulted (group P) | worse |
| partner_covers_default | 1 when the field partner, not the lender, carries the loss if the borrower does not pay (group P) | better |

Context only: `loan_amount_usd`, `partner_known_loans`. There is no borrower-behaviour input in this mode, and group P describes the intermediary, not the shop; results are reported with and without it. The loan's description is never read: Kiva removes it from loans that defaulted.

## How the features are computed (as built in Phase 3)

Code: `src/features/build_features.py`. Thresholds: the `features` section of `config/default.yaml`.

- **Cutoff.** A loan's cutoff is its issue date. Only events dated strictly before that day are used; an event on the cutoff day is not. One function, `events_before_cutoff`, applies this for every feature.
- **Empty is not zero.** A feature that cannot be computed is left empty. Counts of purchases are real zeros when nothing was bought. Ratios with nothing to compare (growth for a new merchant, payment features on a first loan, delivery features for a merchant who sends no parcels) stay empty and produce no reason.
- **Model inputs and context columns.** Only 10 of the features in the table above are model inputs: `basket_growth`, `supplier_repeat_share` (group A); the four payment features (group B); `return_rate_90d`, `failed_rate_90d`, `cod_remit_ontime_rate`, `dispatch_to_delivery_hours` (group C). Eight are context only (`model_input: false` in `dictionary.yaml`): `purchases_90d`, `purchase_value_90d`, `purchase_volatility`, `purchase_regularity`, `category_diversity`, `parcel_volume_90d`, `delivery_data_thin`, `delivered_rate`. They are shown on the profile, feed coverage where relevant, and never produce a reason for a score. Reason for the first seven: thin-file merchants have little data by definition; with those columns in the model they scored about three points lower while repaying just as well. Reason for `delivered_rate`: it falls when a rider or an address fails, which is not the merchant's doing.
- **Which way each input points.** Every model input carries `higher_is: better` or `higher_is: worse` in `dictionary.yaml`, matching its sentences. Training removes any input whose fitted weight points the other way and refits (`fit_with_expected_directions` in `src/model/train.py`), so a reason can never contradict what the merchant did. The report lists the inputs removed.
- **Group A, purchases.** "90d" means the 90 days before the cutoff. Growth compares that window with the 90 days before it. `supplier_repeat_share` is the chance that two of the merchant's purchases in the window came from the same supplier, counted over all pairs, so it does not depend on the number of purchases (it needs at least two). Regularity and volatility use the last 12 whole weeks the merchant existed for; empty weeks count as zero.
- **Group B, payments.** A part payment is not a repayment: at least 99% of the amount due must be paid. Only loans issued before the cutoff count, so a loan never describes itself. A payment made before the cutoff uses its real lateness. A payment not made by the cutoff but already due counts as late by the days so far, even if it was paid later: on the cutoff day nobody could know. A payment not yet due says nothing. On time means within 3 days of the due date; late means more than 7 days.
- **Group C, deliveries.** Cancelled parcels are ignored. A parcel dispatched in the last 3 days, or delivered on or after the cutoff, counts towards volume but not towards any rate, because its outcome was not yet known. `return_rate_90d` and `failed_rate_90d` leave out returns and failures tagged `address_issue` or `rider_issue`. A merchant with no parcels in the window has no delivery features at all.
- **Coverage.** Counts (`history_months`, `n_purchases_total`, `n_deliveries_total`, `n_payments_total`, `share_of_groups_present`) and one yes/no column per item of `coverage_weights`, named `cov_<item>`. Never model inputs.
- **Leakage guard.** `src/features/leakage.py` rebuilds a loan's features after erasing everything dated on or after its cutoff; nothing may change. `tests/test_leakage.py` runs it on a sample of loans, on every loan issued before one date, and on five leaks planted on purpose, each of which must be caught. Its limits: the per-loan check is a sample; the data has no time stamp for when a parcel was returned or failed, so "known three days after dispatch" is an assumption the guard cannot verify; and it checks features only, so anything a model fits (clipping limits, averages for missing values, scaling) must be fitted on the training period alone.
