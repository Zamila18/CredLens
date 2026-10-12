# config/calibration: public figures that tune the synthetic generator

Owner role: A (lead). These are published national totals, not records about any person or
business, so they may live in the repository. They never train a model; they only set
realistic proportions and seasonality for the synthetic data (docs/GENERATOR_SPEC.md,
"Calibration to Bangladesh").

## bb_mfs_merchant_payment.csv

| Item | Entry |
|---|---|
| What | Monthly "Merchant Payment" value through mobile financial services, in crore BDT |
| Source | Bangladesh Bank, Mobile Financial Services comparative summary statements, section B (product-wise), row 7 |
| Link | https://www.bb.org.bd/en/index.php/financialactivity/mfsdata |
| Read by | The team lead, by hand, from the "search previous data" pages on Oct 12, 2026 |
| Coverage | January 2023 to February 2025 (26 months). March 2025 onward returned "No data found" on that date |
| Check done | For every pair of months, the two values reproduce the percentage change printed on the page |

## findex_bangladesh.csv

| Item | Entry |
|---|---|
| What | Share of adults (age 15+) in Bangladesh for a few financial-inclusion indicators, survey year 2024, group "all" |
| Source | World Bank, Global Findex Database 2025, country-level file `GlobalFindexDatabase2025.csv` |
| Link | https://www.worldbank.org/en/publication/globalfindex/download-data |
| Read by | Claude Code on Oct 12, 2026, from the file the lead downloaded into `data/raw/findex/` |
| Open point | The CSV has column codes and no labels. Five indicators were matched by self-describing column names; they must be confirmed against the Findex codebook before being quoted in slides. "Borrowed from a formal institution" was not found |

These describe all adults, not merchants. Use them as loose priors and context, not as facts
about shop owners.

## wb_informal_bangladesh.csv

| Item | Entry |
|---|---|
| What | City-level indicators for unregistered (informal) businesses in Chittagong MA, Cox's Bazar and Dhaka MA, survey year 2022 |
| Source | World Bank Enterprise Surveys, Informal Sector Enterprise Surveys, indicator table ("Download a custom set of indicators") |
| Link | https://www.enterprisesurveys.org/en/data (Informal Sector Enterprise Surveys section) |
| Read by | Claude Code on Oct 12, 2026, from the page text the lead pasted. The page listed 15 cities in a row; the Bangladesh cities were the 6th, 7th and 8th values on each line |
| Check done | Verified on Oct 12, 2026 against the lead's export `CustomQuery-InformalSectorWBES-Oct-12-2026.xlsx` (three Bangladesh cities, all topics, with number of observations). Every value matches. The `n_` columns give the number of businesses behind each figure |

These are informal businesses of all kinds in three cities, not ShopUp merchants. Use them
as priors for the synthetic merchants (credit selling, mobile money use, loans, bank
accounts), and say so wherever a figure is shown.

## Notes for the merchant-payment series
- The series grows strongly over time, so remove the trend before reading seasonality.
- July is low in both 2023 and 2024. July 2024 may also reflect a one-off disruption that month;
  this is the lead's and Claude Code's reading, not something the source states.
- Do not fill missing months with estimates. If a month is absent, leave it absent.
