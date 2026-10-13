# DATA_SOURCES.md: where the data comes from

Owner role: A (lead), with B for the columns. Last updated Oct 12, 2026, after the files were downloaded and inspected. The "we use / we drop" column lists are completed in Phase 7, when the adapters are built.

Status words used below:
- **Checked**: the real file was opened on the date given and the item was confirmed from it.
- **Not checked**: nobody on the team has confirmed the item yet.

Rules for every source:
- Raw files are downloaded by a person into `data/raw/<source>/`. That folder is gitignored.
- Raw files are never committed, uploaded to the shared database, or redistributed.
- No generated history is ever added to a real record.
- Group columns (gender, country, age band and similar) are used only to audit results, never as model inputs.
- Results on public data test the method. None of these sources is ShopUp data.

## 1. Sources that train or evaluate a model (row-level, real outcomes)

### 1.1 Taiwan credit-card default, UCI (`taiwan_cc`)

| Item | Entry |
|---|---|
| Link | https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients |
| Licence / terms | CC BY 4.0, as stated on the UCI page (read Oct 12, 2026). Cite I-Cheng Yeh, 2009 |
| File | `data/raw/taiwan_cc/default of credit card clients.xls` (5.5 MB). Checked Oct 12 |
| Size | 30,000 clients, 25 columns, no missing values, no duplicate ids |
| Label | `default payment next month`: 6,636 defaulted (22.1%). Our label = 1 minus this |
| Columns | `ID`, `LIMIT_BAL`, `SEX`, `EDUCATION`, `MARRIAGE`, `AGE`, `PAY_0`, `PAY_2` to `PAY_6`, `BILL_AMT1` to `6`, `PAY_AMT1` to `6` |
| Audit-only columns | `SEX`, `EDUCATION`, `MARRIAGE`, age band from `AGE` |
| Quirks | An extra header row (`X1`, `X2`, ...) above the real names. A few undocumented codes in `EDUCATION` (0, 5, 6) and `MARRIAGE` (0) |
| Limits | Consumer credit cards, not merchants. One fixed window with no per-row dates, so the split is stratified random and marked weaker. Data from 2005 |
| Adapter (built Oct 13) | `src/adapters/taiwan_cc.py`. One merchant, one loan and one "public_dataset" consent row per client; the six monthly statements go into `payments` (bill, amount paid, month end as a nominal date: the source gives months only); purchases, deliveries and questionnaire stay empty. Amounts are New Taiwan dollars, not converted, although the contract's column names end in `_bdt` |
| What a feature may read | `LIMIT_BAL`, the six `PAY_` status codes, the six `BILL_AMT` and the six `PAY_AMT` columns: all known at the end of September 2005, before the October outcome. The outcome, `ID`, `SEX`, `EDUCATION`, `MARRIAGE` and `AGE` never reach the feature builder; a test plants each one and checks it is refused |
| Status codes | -2 = card not used that month, -1 = paid in full, 0 = minimum paid, 1 to 8 = months late. The UCI page documents -1 and 1 to 9 only; the reading of -2 and 0 comes from the data set's author and is the one generally used. 2,759 to 4,895 clients per month have -2 |
| Model inputs (8) | Share of used months paid on time, longest delay, latest delay, change in delay, share of bills paid, share of the limit in use, balance growth, share of months with a bill but no payment. The credit limit itself is context, not an input: it is the lender's view, not the client's behaviour |
| Coverage | Limit recorded (15%), card used in at least 4 of 6 months (35%), a bill in at least 4 months (25%), at least one payment (25%). 24,527 clients have full coverage; 2,725 fall under the 45% line. The 1,269 clients with only a credit limit repaid less often (67%) than the rest (78%): the model cannot see that, by design, and they get "Needs more info" |
| First look (not the reported result) | A quick fit on the training part, read on the validation part: AUC about 0.74 for the logistic regression and 0.76 for LightGBM from behaviour inputs alone. The proper run with ranges, calibration and bands is Phase 8 |

### 1.2 India L&T vehicle loans, Kaggle (`india_ltfs`)

| Item | Entry |
|---|---|
| Link | https://www.kaggle.com/datasets/mamtadhaker/lt-vehicle-loan-default-prediction |
| Licence / terms | The page says "Other (specified in description)", and the description contains no usage terms (read Oct 12, 2026). Recorded as: no terms stated |
| Files | `data/raw/india_ltfs/train.csv` (42 MB) and `data_dictionary.csv`. Checked Oct 12 |
| Size | 233,154 loans, 41 columns, no duplicate ids. Only `Employment.Type` has missing values (7,661) |
| Label | `loan_default`: "Payment default in the first EMI on due date" (data dictionary). 50,611 defaulted (21.7%). This is missing the first instalment, an early-warning outcome, not eventual default. Our label = 1 minus this |
| Dates | `DisbursalDate` from 2018-08-01 to 2018-10-31, so a time split over three months is possible |
| Notable | 50.2% of borrowers have a bureau score of zero (no credit record): real thin files. 127,635 are self-employed. 22 states, 82 branches |
| Audit-only columns | Age band from `Date.of.Birth`, `State_ID`, `Employment.Type` |
| Leakage note | The dictionary describes every bureau column as "at the time of disbursement". Branch and employee identifiers must not be headline reasons |
| Limits | Vehicle loans to individuals, not merchants. A short three-month window |
| Adapter (built Oct 13) | `src/adapters/india_ltfs.py`. One merchant, one loan and one "public_dataset" consent row per loan; purchases, deliveries, payments and questionnaire stay empty. Amounts are Indian rupees, not converted. Dates in the file are day-month-two-digit-year; a birth year read as later than the loan (for example 2064) is moved back a century. `label_observed_at` is one month after disbursal, a nominal date |
| What a feature may read | The disbursal date, the three loan columns (`disbursed_amount`, `asset_cost`, `ltv`) and eleven bureau columns, all "at the time of disbursement". Never: the outcome, the id, date of birth, employment type, state, or the branch, dealer, manufacturer, pin code and employee identifiers (they describe the lender's organisation, not the borrower). A test plants each of the ten and checks it is refused |
| Model inputs (6) | Share of the price paid up front (one minus loan-to-value), bureau score (only where the bureau gave one), share of earlier loans overdue, loans that fell behind in six months, new loans in six months, loan enquiries. Loan amount, number of earlier loans and length of credit history are context, not inputs |
| Thin files | 116,950 borrowers (50.2%) have no bureau record. For them the five bureau inputs are empty and only the up-front share is known |
| Coverage | Loan terms recorded (20%), bureau record exists (40%), credit history of at least 12 months (25%), bureau score available (15%). Half the borrowers sit at 20% and get "Needs more info"; 79,894 have full coverage |
| Split | By month of disbursal: August 2018 trains (68,002 loans), September validates (66,788), October is held back (98,364) |
| First look (not the reported result) | A quick fit on August, read on September: AUC about 0.59 for the logistic regression and 0.61 for LightGBM; 0.58 for borrowers without a bureau record and 0.62 to 0.63 for those with one. This is weak, and it is reported as it is: a bureau summary says little about who misses a first instalment, and for half the borrowers there is no bureau summary at all. The proper run is Phase 8 |

### 1.3 Kiva loans, filtered to Asia (`kiva_asia`): file checked Oct 13, adapter not built yet

| Item | Entry |
|---|---|
| What did not work | The official link (`s3.kiva.org`) no longer exists. The Kaggle "additional kiva snapshot" (2018, 1,419,607 loans) has only funding statuses and **no repayment outcome**. Duke's 5,000-loan sample has 100 defaults, **none in Asia**, and contains borrower names. All checked Oct 12 |
| What may work | Kiva's official JSON snapshot dated 2 May 2016, saved by the Internet Archive on 1 July 2016: http://web.archive.org/web/20160701132740/http://s3.kiva.org/snapshots/kiva_ds_json.zip (1.16 GB, 1,061,401 loans). A 3 MB probe on Oct 12 showed statuses `paid`, `defaulted`, `in_repayment`, with posting dates, sector, country, partner and loan terms |
| Download status | Done. `data/raw/kiva/kiva_ds_json.zip`, 1,161,901,690 bytes, kept zipped and read in place. 2,123 loan files; 17 of them are empty in the archived copy (about 8,500 loans missing), leaving 1,052,900 loans. Checked Oct 13 |
| What the full file holds | Statuses: 805,589 paid, 22,471 defaulted, 162,751 still in repayment, the rest expired, refunded or deleted. **Asia-Pacific, finished loans: 300,418 paid and 4,080 defaulted. Retail + Food + Services only: 157,162 paid and 2,743 defaulted (1.7%).** By country (paid / defaulted): Philippines 162,566 / 2,369; Cambodia 46,281 / 27; Tajikistan 24,441 / 46; Pakistan 20,124 / 828; Vietnam 10,992 / 1; Samoa 9,997 / 35; Mongolia 8,368 / 22; Kyrgyzstan 6,472 / 7; Indonesia 5,008 / 139; Afghanistan 1,607 / 574; India 327 / 4. **No Bangladesh loans.** So the mode qualifies (well above the 100 not-repaid loans needed for stable numbers) |
| Limits to state | (1) Defaults are rare and bunched: 2,545 of the 4,080 Asian defaults were posted in 2012, and three countries hold most of them, so a default here often reflects a field partner failing, not one borrower. (2) Loans posted in 2014 to 2016 are mostly still in repayment; keeping only finished loans from those years would keep the quick payers and hide late defaults, so the adapter must cut off at a posting date by which outcomes are known. (3) Every sector in Asia has defaults; the sector filter is a choice for closeness to merchants, not a need |
| Licence / terms | Kiva's snapshot page states no data licence, only general terms of use. Recorded as: terms not stated |
| Personal data | The file contains borrower names, photos and stories. The adapter must drop them on load and keep only loan terms and outcomes |
| Limits | No purchase, delivery or payment history. Defaults are rare (about 2%) and partly driven by the field partner |

### 1.4 Home Credit Default Risk, Kaggle (`homecredit`)

| Item | Entry |
|---|---|
| Link | https://www.kaggle.com/competitions/home-credit-default-risk/data |
| Licence / terms | Checked Oct 12, 2026 (rules page read by the lead). The competition-specific rule says: "you may access and use the Competition Data only for the purposes of the Competition", and it supersedes the general rule that allows academic and non-commercial use. Section 7.B forbids transmitting, publishing or redistributing the data. "The Competition" is Kaggle's 2018 Home Credit competition, so use in this hackathon prototype is outside the literal terms. **The team lead decided on Oct 12 to use it anyway as a local, non-commercial method check and accepts that risk.** |
| Safeguards | Raw files stay on the lead's laptop only: never committed, never loaded into the shared database, never copied to the hosting server. The hosted dashboard shows only aggregate results (metrics, calibration, group audit) for this mode, never individual records. First data source to remove if anyone objects |
| Files | `data/raw/homecredit/application_train.csv` (166 MB), `installments_payments.csv` (723 MB), `POS_CASH_balance.csv` (393 MB). Checked Oct 12 |
| Size | 307,511 applicants, 122 application columns; 13.6 million instalment rows; 10.0 million POS rows |
| Label | `TARGET`: 24,825 with payment difficulties (8.1%). Our label = 1 minus this |
| History coverage | 94.8% of applicants have instalment history; 94.1% have POS history |
| Audit-only columns | `CODE_GENDER`, age band from `DAYS_BIRTH`, `REGION_RATING_CLIENT` |
| Limits | **The data does not state its country**, so it is labelled "country not stated" and does not support an Asian claim. Consumer loans, not merchants. All history is dated in days relative to the application (always earlier), with no absolute dates, so the split is stratified random and marked weaker |
| Adapter (built Oct 13) | `src/adapters/homecredit.py`. A seeded sample of 50,000 applicants (`data.homecredit.sample_size`). One merchant, one loan and one "public_dataset" consent row per application; `issued_at` is one nominal date for all, because the source has no calendar dates. The contract `payments` table is left empty on purpose: the earlier instalments feed the features, and rows of this source are never shown on a screen |
| Reading 1.1 GB on a laptop | The two history files are read a million rows at a time, keeping only the needed columns and the sampled applicants; the per-applicant counts are saved in `data/raw/homecredit/_derived/` (gitignored with the raw folder). Measured on the lead's laptop (8 GB of memory, no GPU): 11 seconds the first time, 1 second after |
| What a feature may read | Seven application columns (income, loan amount, repayment amount, goods price, three outside scores) and nine counts worked out from the history files. Never: the outcome, the id, gender, date of birth, region rating; the other descriptions of the person (occupation, family, housing, education, employer type) are not even loaded. Every history row must be dated before the application, or the build stops |
| Model inputs (9) | Six from earlier instalments (share on time, average days late, share over 30 days late, share paid short, last year's share on time, share of months with an overdue amount), two from the loan asked for (repayment against stated income, loan against goods price) and one outside score (the average of the up-to-three `EXT_SOURCE` columns), kept in its own group so a run can be reported with and without it |
| Coverage | Application data present (20%), any earlier instalment (35%), at least 12 earlier instalments (25%), any monthly record of an earlier store or cash loan (20%). In the sample 35,723 applicants have full coverage and 2,514 have the application only |
| First look (not the reported result) | Validation part of a random split: with the applicant's own behaviour only, AUC about 0.60 (logistic regression) to 0.62 (LightGBM); with the outside score added, 0.75. So most of the ranking power here comes from the outside score, not from repayment history. The proper run, both ways, is Phase 8 |

## 2. Public figures collected for the synthetic data and the slides (never used for training)

The figures themselves are in `config/calibration/`, with the source and the check for each in its README. **Only the Bangladesh Bank series is read by the generator** (it sets the seasonal shape of purchases). The other rows are context for slides and for anyone who extends the generator; no code reads them today. The generator's remaining numbers (purchase rates, amounts, parcel volumes, loan limits) are the team's own assumptions.

| Source | Link | What it gives | Status |
|---|---|---|---|
| Bangladesh Bank, Mobile Financial Services monthly statements | https://www.bb.org.bd/en/index.php/financialactivity/mfsdata | "Merchant Payment" (crore BDT) for Jan 2023 to Feb 2025: the seasonal shape of purchases | Checked Oct 12: read by hand by the lead; every pair of months reproduces the percentage change printed on the page |
| World Bank Enterprise Surveys, Informal Sector Enterprise Survey | https://www.enterprisesurveys.org/en/data | Indicators for Chittagong MA, Cox's Bazar and Dhaka MA, 2022 (about 3,700 businesses): selling and buying on credit, loans, bank accounts, mobile money, workers | Checked Oct 12 against the Excel export with observation counts |
| World Bank, Global Findex Database 2025 (country-level) | https://www.worldbank.org/en/publication/globalfindex/download-data | Bangladesh 2024: account ownership, mobile money, borrowing, saving | Read Oct 12. Column meanings were inferred from column names; confirm in the codebook before quoting. "Made a digital merchant payment" is doubtful and unused |
| ShopUp Series B press release | https://shopup.com.bd/web/press/valar-ventures-shopup-bangladesh | 73% of small retailers sell on credit; 27.5% have formal-finance access (company statement) | Not checked by this team since the review of Oct 10 |
| Microcredit Regulatory Authority; City Bank-bKash announcements | See the comment on `generator.repayment_share_target` in the config | Context for the 90% repayment assumption: 98% microfinance recovery (FY2023); 0.5% non-performing on digital nano loans (lender's own figure, July 2026) | Read in news reports on Oct 12, not in the original publications |

Two figures for selling on credit describe different groups: 73% of small retailers (ShopUp) and 52 to 56% of informal businesses of all kinds in three cities (World Bank). Quote each with its source.

## 3. Context and design references (slides, questionnaire, benchmarks)

| Source | Link | Used for |
|---|---|---|
| CGAP, Leveraging Transactional Data for MSE Lending | https://www.cgap.org/research/publication/leveraging-transactional-data-for-micro-and-small-enterprise-lending | Benchmark: AUC of about 0.70 is considered useful |
| FinHealth Score Toolkit | https://finhealthnetwork.org/wp-content/uploads/2021/11/FinHealthScoreToolkit-2021.pdf | Base wording for the 10-item questionnaire (check its terms of use) |
| Corner Shop Diaries | https://cornershop-msc-l-ift.com/ | Cash-flow rhythm of small shops |
| Small Firm Diaries, Indonesia | https://www.smallfirmdiaries.org/indonesia | Shocks and resilience patterns |
| data.org Financial Health Prediction Challenge (Zindi) | https://zindi.world/competitions/dataorg-financial-health-prediction-challenge | Related work by the hackathon organiser: an SME financial-health index for four Southern African countries. Cited only |
| IMF Financial Access Survey; Data.gov.in; NDAP; SHRUG | Listed in the team's Finverse result | Starter-kit context sources |

## 4. Considered and not used

| Source | Why not |
|---|---|
| Zindi data.org Financial Health challenge data | Its rules allow use under CC BY-SA 4.0, but the files were locked after the competition closed (tried Oct 12). Also African, and the label is financial health, not repayment |
| Kiva 2018 snapshot (Kaggle) and Duke Kiva sample | No repayment outcome; no Asian defaults |
| India Informal Sector Enterprise Survey microdata | Replaced by the Bangladesh city indicators from the same survey programme |
| US SBA small-business loans | Not Asian |
| Czech PKDD'99 bank data | Not Asian; very small |
| Country-level tables used as training data | No row per borrower and no outcome; calibration and slides only |

## 5. A gap to state openly

No public dataset has repayment outcomes for Asian small merchants together with their purchase and delivery history. The synthetic data stands in for that, and the public datasets test the method on real outcomes of other kinds. Closing the gap needs a partner's data.
