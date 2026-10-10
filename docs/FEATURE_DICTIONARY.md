# FEATURE_DICTIONARY.md

Each feature has: name, group, definition (as of loan cutoff), direction (what higher usually means), and a pair of reason sentences (positive when it raised the score, negative when it lowered it) in English and Bangla. Code must load these from `src/features/dictionary.yaml` (create it from this table). Sentences are observations, never accusations. Bangla text should be reviewed by a native speaker before the demo.

| name | group | definition | higher means | positive sentence (EN / BN) | negative sentence (EN / BN) |
|---|---|---|---|---|---|
| orders_90d | A orders | Orders in the 90 days before cutoff | more activity | "The shop has been active, with many recent orders." / "দোকানটি সচল, সাম্প্রতিক অর্ডার অনেক।" | "Recent order activity is low." / "সাম্প্রতিক অর্ডার কম।" |
| order_value_90d | A | Total order value, 90 days | larger business | "Recent sales volume is healthy." / "সাম্প্রতিক বিক্রির পরিমাণ ভালো।" | "Recent sales volume is small." / "সাম্প্রতিক বিক্রির পরিমাণ কম।" |
| sales_trend | A | Sales last 90 days vs the 90 before, % | growth | "Sales are growing compared with the previous three months." / "আগের তিন মাসের তুলনায় বিক্রি বাড়ছে।" | "Sales are falling compared with the previous three months." / "আগের তিন মাসের তুলনায় বিক্রি কমছে।" |
| order_volatility | A | Std. dev. of weekly order value / mean | unstable | "Weekly sales are steady." / "সাপ্তাহিক বিক্রি স্থিতিশীল।" | "Weekly sales swing a lot." / "সাপ্তাহিক বিক্রিতে ওঠানামা বেশি।" |
| weeks_active_share | A | Share of weeks with at least one order | consistent | "The shop sells in most weeks." / "দোকান বেশিরভাগ সপ্তাহে বিক্রি করে।" | "The shop sells in few weeks." / "দোকান কম সপ্তাহে বিক্রি করে।" |
| category_diversity | A | Number of product categories | diversified | "Sales are spread across several categories." / "বিক্রি একাধিক ক্যাটাগরিতে ছড়ানো।" | "Sales depend on very few categories." / "বিক্রি অল্প কয়েকটি ক্যাটাগরির ওপর নির্ভর করে।" |
| repeat_customer_share | A | Share of orders from returning customers | loyalty | "Many customers come back to this shop." / "অনেক ক্রেতা আবার এই দোকানে ফেরেন।" | "Few customers come back." / "কম ক্রেতা ফিরে আসেন।" |
| avg_pay_delay_days | B payments | Mean days late over past payments | worse | "Past payments were made close to the due date." / "আগের পেমেন্ট প্রায় নির্ধারিত সময়ে হয়েছে।" | "Past payments were often late." / "আগের পেমেন্ট প্রায়ই দেরিতে হয়েছে।" |
| late_pay_count_90d | B | Payments over 7 days late, 90 days | worse | "No recent late payments." / "সাম্প্রতিক কোনো দেরির পেমেন্ট নেই।" | "There were late payments recently." / "সাম্প্রতিক সময়ে পেমেন্টে দেরি হয়েছে।" |
| ontime_payment_rate | B | Share of payments within 3 days of due | reliable | "Most payments arrive on time." / "বেশিরভাগ পেমেন্ট সময়মতো আসে।" | "Few payments arrive on time." / "কম পেমেন্ট সময়মতো আসে।" |
| credit_utilisation | B | Used limit / limit | stretched | "Credit use is moderate." / "ঋণের ব্যবহার মাঝারি।" | "Credit use is close to the limit." / "ঋণের ব্যবহার সীমার কাছাকাছি।" |
| delivered_rate | C deliveries | Delivered parcels / dispatched, 90 days | reliable fulfilment | "Most parcels are delivered successfully." / "বেশিরভাগ পার্সেল সফলভাবে পৌঁছায়।" | "Many parcels are not delivered." / "অনেক পার্সেল পৌঁছায় না।" |
| return_rate_90d | C | Returned parcels / total, 90 days | worse | "Delivery returns are lower than similar shops." / "সমান ধরনের দোকানের তুলনায় ডেলিভারি ফেরত কম।" | "Delivery returns are higher than similar shops." / "সমান ধরনের দোকানের তুলনায় ডেলিভারি ফেরত বেশি।" |
| failed_rate_90d | C | Failed parcels / total | worse | "Few delivery failures." / "ডেলিভারি ব্যর্থতা কম।" | "Many delivery failures." / "ডেলিভারি ব্যর্থতা বেশি।" |
| cod_remit_ontime_rate | C | Share of cash-on-delivery money passed back on time | reliable | "Cash-on-delivery money is passed back on time." / "ক্যাশ-অন-ডেলিভারির টাকা সময়মতো ফেরত আসে।" | "Cash-on-delivery money is often late." / "ক্যাশ-অন-ডেলিভারির টাকা প্রায়ই দেরিতে আসে।" |
| dispatch_to_delivery_hours | C | Median hours from dispatch to delivery | slower | "Parcels reach customers quickly." / "পার্সেল দ্রুত ক্রেতার কাছে পৌঁছায়।" | "Parcels take long to reach customers." / "পার্সেল পৌঁছাতে বেশি সময় লাগে।" |
| delivery_data_thin | C | Fewer than 20 parcels in 90 days (flag) | less certain | n/a | "Delivery history is thin, so the picture is less certain." / "ডেলিভারির ইতিহাস কম, তাই চিত্রটি কম নিশ্চিত।" |
| q_spend, q_save, q_borrow, q_plan | D questionnaire | Four subscores (1-5) from the 10 items | healthier habits | "Self-reported habits look healthy (directional)." / "নিজের দেওয়া তথ্য অনুযায়ী অভ্যাস ভালো (ইঙ্গিতমাত্র)।" | "Self-reported habits suggest some strain (directional)." / "নিজের দেওয়া তথ্য অনুযায়ী কিছু চাপ আছে (ইঙ্গিতমাত্র)।" |
| q_stress, q_confidence | D | Context items | n/a | same as above | same as above |

Coverage-only features (not used for the score reasons): history_months, n_orders_total, n_deliveries_total, n_payments_total, share_of_groups_present.

Rules
- Questionnaire reasons must carry the word "directional" / "ইঙ্গিতমাত্র".
- Never show raw feature names to officers; show the sentence, with the number when helpful ("Returns 7.5% vs typical 4%").
- If a feature is missing for a merchant, do not generate a reason for it; mention missing data via coverage.
