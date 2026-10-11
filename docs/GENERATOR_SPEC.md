# GENERATOR_SPEC.md: synthetic data design

Goal: realistic enough to exercise every feature of the system, simple enough to explain. All parameters come from `config/default.yaml`. Same seed gives the same data.

## Core idea: one hidden variable
Each merchant i has a hidden reliability r_i ~ Normal(0, 1). The system never sees r_i. Purchases, payments, deliveries and loan outcome are noisy reflections of it.

## Merchant attributes
- onboarded_at: spread over `months` (18) months.
- town_tier: metro 25%, city 45%, small_town 30%. shop_type: grocery 35%, pharmacy 15%, apparel 20%, electronics 15%, other 15%. has_trade_license: higher in metro. consent_data_use ~ `consent_rate`. questionnaire_done ~ `questionnaire_rate`.
- Group effects on outcomes: default none (0). Add an optional `inject_group_bias` switch (default off) used only to test that the fairness checks can catch a planted gap.

## Purchases (Mokam-style wholesale purchases; the merchant BUYS stock)
- Weekly purchase count ~ Poisson(lambda), log(lambda) = base(tier, shop_type) + 0.5*r + trend_i + seasonality_t + noise.
- trend_i ~ Normal(0.1*r, 0.1) per month (growing vs shrinking shops). Seasonality: restocking peaks before Eid, dips in monsoon months.
- Thin-file merchants (`thin_file_share`): very few purchases in their first 30 days.
- amount ~ LogNormal(mu_category + 0.1*r, 0.5). supplier_id drawn from a small pool; probability of reusing a past supplier rises with r.
- No sales or customer records exist in Mokam. A sales proxy comes only from REDX outgoing parcels.

## Payments (Baki-style, repeat borrowers)
- days late ~ Gamma with mean exp(1.0 - 0.6*r) days, clipped to >= 0. Probability of a late payment falls with r.

## Deliveries (REDX-style), with the negative control
- `s` = delivery_signal_strength.
- 75% of merchants have delivery data (`no_delivery_data_share` have none).
- Per parcel: P(return) = sigmoid(-2.2 - s*0.9*r + noise); P(failed) similar, smaller. P(COD remitted on time) = sigmoid(1.2 + s*0.8*r + noise). Dispatch-to-delivery hours ~ LogNormal(3.2 - s*0.15*r, 0.4).
- Logistics noise: a share `logistics_noise_share` of returns/failures is drawn independently of r and tagged return_reason = address_issue or rider_issue. The rest are tagged refused / wrong_item / other.
- At s = 0 these are independent of r. Purchases and payments still carry r, so delivery data adds nothing beyond them. At s > 0 delivery data is an extra noisy measurement of r, so a gain appears. This is what the ablation tests.

## Loans and outcomes
- 1 to 3 loans per merchant, first no earlier than 45 days after onboarding; limit grows with tier and history. Only merchants with consent=true get scored.
- P(repaid within 30 days of due date) = sigmoid(1.2 + 1.1*r + 0.15*Normal(0,1)). Draw days_late accordingly; outcome_label per `labels` config. Loans too young are left unobserved.
- Expected repayment share roughly 75-85%; check and report.

## Questionnaire (FinHealth-style, 10 items, 1-5)
Item = clip(round(3 + 0.4*r + Normal(0,1)), 1, 5); stress item reverse-coded. Weakly related to r, so it is a directional signal only. Generated for the questionnaire panel; excluded from the headline model (`questionnaire_in_model: false`).

## Missingness and realism
Some merchants have no deliveries; payments exist only for repeat borrowers; questionnaire for ~40%. Missingness is random with respect to r (document this: real missingness is likely not random).

## Required self-checks (tests)
Row counts; no duplicate merchant_id; foreign keys resolve; thin-file share near target; dates in order; repayment share in range; correlation of r with order growth > 0 and with return rate ~ 0 when s = 0.

## Calibration to Bangladesh (v2)
Set these from public sources and cite them in docs/DATA_SOURCES.md; never invent figures. Leave a TODO naming the source until a human supplies the number.
- Share of merchants using mobile money / digital payments: Global Findex 2025 Bangladesh microdata.
- Month-by-month seasonality of merchant payments: Bangladesh Bank MFS monthly statistics.
- Share of small retailers selling on credit (73%) and formal-finance access (27.5%): ShopUp Series B press release (context for the deck; optional prior for questionnaire answers).
