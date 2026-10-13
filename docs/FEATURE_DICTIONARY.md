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
| delivered_rate | C deliveries | Delivered parcels / dispatched, 90 days | reliable fulfilment | "Most parcels are delivered successfully." / "বেশিরভাগ পার্সেল সফলভাবে পৌঁছায়।" | "Many parcels are not delivered." / "অনেক পার্সেল পৌঁছায় না।" |
| return_rate_90d | C | Merchant-attributable returns (refused, wrong item) / total, 90 days; address/rider returns excluded when return_reason is known | worse | "Delivery returns are lower than similar shops." / "সমান ধরনের দোকানের তুলনায় ডেলিভারি ফেরত কম।" | "Returns are higher than similar shops; this may reflect delivery conditions." / "সমান ধরনের দোকানের তুলনায় ফেরত বেশি; এটা ডেলিভারির পরিস্থিতির কারণেও হতে পারে।" |
| failed_rate_90d | C | Failed parcels / total | worse | "Few delivery failures." / "ডেলিভারি ব্যর্থতা কম।" | "Delivery failures are higher than usual; this may reflect address or rider issues." / "ডেলিভারি ব্যর্থতা বেশি; ঠিকানা বা রাইডারের সমস্যার কারণেও হতে পারে।" |
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
- Questionnaire (group D) is shown beside the score, not used in the headline model. Its reasons appear in the questionnaire panel only.
- Public-data sources add their own entries (e.g. kiva: loan_amount_usd, term_months, repayment_interval_irregular, sector; taiwan_cc: ontime_share_6m, worst_delay_6m, pay_to_bill_ratio, limit_utilisation; homecredit: inst_ontime_rate, inst_mean_days_late, pos_months_active). Claude Code adds these to dictionary.yaml with EN/BN sentences when building the adapters.

## How the features are computed (as built in Phase 3)

Code: `src/features/build_features.py`. Thresholds: the `features` section of `config/default.yaml`.

- **Cutoff.** A loan's cutoff is its issue date. Only events dated strictly before that day are used; an event on the cutoff day is not. One function, `events_before_cutoff`, applies this for every feature.
- **Empty is not zero.** A feature that cannot be computed is left empty. Counts of purchases are real zeros when nothing was bought. Ratios with nothing to compare (growth for a new merchant, payment features on a first loan, delivery features for a merchant who sends no parcels) stay empty and produce no reason.
- **Group A, purchases.** "90d" means the 90 days before the cutoff. Growth compares that window with the 90 days before it. Regularity and volatility use the last 12 whole weeks the merchant existed for; empty weeks count as zero.
- **Group B, payments.** Only loans issued before the cutoff count, so a loan never describes itself. A payment made before the cutoff uses its real lateness. A payment not made by the cutoff but already due counts as late by the days so far, even if it was paid later: on the cutoff day nobody could know. A payment not yet due says nothing. On time means within 3 days of the due date; late means more than 7 days.
- **Group C, deliveries.** Cancelled parcels are ignored. A parcel dispatched in the last 3 days, or delivered on or after the cutoff, counts towards volume but not towards any rate, because its outcome was not yet known. `return_rate_90d` leaves out returns tagged `address_issue` or `rider_issue`. A merchant with no parcels in the window has no delivery features at all.
- **Coverage.** Counts (`history_months`, `n_purchases_total`, `n_deliveries_total`, `n_payments_total`, `share_of_groups_present`) and one yes/no column per item of `coverage_weights`, named `cov_<item>`. Never model inputs.
- **Leakage guard.** `src/features/leakage.py` rebuilds a loan's features after erasing everything dated on or after its cutoff; nothing may change. `tests/test_leakage.py` runs it on the real features and on five leaks planted on purpose, each of which must be caught.
