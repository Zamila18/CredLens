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

### 1.3 Kiva loans, filtered to Asia (`kiva_asia`)

| Item | Entry |
|---|---|
| What did not work | The official link (`s3.kiva.org`) no longer exists. The Kaggle "additional kiva snapshot" (2018, 1,419,607 loans) has only funding statuses and **no repayment outcome**. Duke's 5,000-loan sample has 100 defaults, **none in Asia**, and contains borrower names. All checked Oct 12 |
| Source used | Kiva's official JSON snapshot dated 2 May 2016, saved by the Internet Archive on 1 July 2016: http://web.archive.org/web/20160701132740/http://s3.kiva.org/snapshots/kiva_ds_json.zip |
| File | `data/raw/kiva/kiva_ds_json.zip`, 1,161,901,690 bytes, kept zipped and read in place. 2,123 loan files of 500 loans; 17 are empty in the archived copy (about 8,500 loans missing). Checked Oct 13 |
| Licence / terms | Kiva's snapshot page states no data licence, only general terms of use. Recorded as: terms not stated |
| Repeated loans | **The snapshot repeats loans.** Of 384,476 Asian loan records, 27,461 loans appear two or three times as identical copies, leaving **354,487 distinct loans**. The adapter keeps each once. The counts first written here on Oct 13 (300,418 paid, 4,080 defaulted; 157,162 and 2,743 in the three sectors) had not removed the repeats and were too high; the figures below replace them |
| What the file holds (each loan once) | Asia and the Pacific: 272,076 paid, 3,892 defaulted, 64,998 still in repayment, the rest expired, refunded or deleted. **Retail + Food + Services: 142,938 paid and 2,642 defaulted (1.8%).** By country (paid / defaulted): Philippines 150,419 / 2,342; Cambodia 39,688 / 26; Tajikistan 21,506 / 46; Pakistan 18,856 / 828; Vietnam 9,763 / 1; Samoa 8,893 / 35; Mongolia 7,182 / 16; Kyrgyzstan 5,837 / 6; Indonesia 4,437 / 124; Timor-Leste 1,773 / 28; Nepal 1,255 / 0; Afghanistan 1,242 / 436; India 327 / 4. **No Bangladesh loans** |
| Loans used by the mode | Retail, Food and Services; posted from 1 July 2009 to 30 June 2013; outcome `paid` or `defaulted`: **65,304 loans, 2,512 defaulted (3.8%)**. Split by posting date: 30 months train (32,581 loans, 315 defaults), 9 months validation (15,113; 793), 9 months held back (17,610; 1,404) |
| Why the window ends in mid-2013 | Of loans posted in the second half of 2013, 4.7% were still being repaid when the snapshot was taken; in 2014, over 10%; in late 2015, 65%. Keeping only the finished loans of those years would keep the quick payers and hide late defaults. Up to mid-2013 about 1% were still running; they are left out because their outcome is unknown |
| Personal data | The file contains borrower names, photos and stories. The adapter never keeps them: it reads the terms, sector, country, partner, dates and status, plus the number of borrowers and their gender for the group audit. A test builds an archive full of the word SECRET and checks none of it survives, on disk or in any table |
| **The description leaks the outcome** | Kiva removes the description from loans that defaulted: in this snapshot 0% of defaulted Asian loans have one and 99.8% of repaid loans do. "Has a description" would be the outcome in disguise, so it is used nowhere, not even in coverage (the first coverage plan had it). Funding amount, number of lenders, `delinquent` and `paid_date` are after-the-fact and are also never read |
| Model inputs (3) | The loan's term in months (group L), and two about the field partner (group P, reported with and without): the share of the partner's earlier loans that had defaulted by the posting day, and whether the partner carries the loss when a borrower does not pay. **There is no borrower-behaviour input: Kiva knows nothing of how a borrower paid before** |
| Partner track record, without looking ahead | An earlier loan counts only if its outcome was known on the posting day: a repaid loan from its `paid_date`; a defaulted loan from the end of its term plus six months (the snapshot gives no date for a default). A partner with fewer than 30 such loans has no track record: the input is empty |
| Coverage | Term and amount recorded (20%), sector and activity recorded (20%), partner has a track record (60%). 4,767 loans from partners without one get "Needs more info" |
| Audit-only columns | Borrower gender (female 58,269; male 5,952; mixed 1,083) and country. The sector goes to `shop_type`, audit-only everywhere |
| Limits to state | (1) **Defaults here are a partner event.** Three field partners hold about 80% of all Asian defaults, and one of them accounts for most of 2012. A default often means the partner failed, not the shop. (2) **The partner's past did not foresee it.** A first look on the validation months: with the loan's term alone, AUC about 0.64 (logistic regression) to 0.67 (LightGBM); adding the partner's track record does not help the logistic regression and drops LightGBM to 0.41, worse than a coin toss, because the partners that failed in 2012 had clean records until then. (3) Loans are in US dollars and run through intermediaries, unlike a platform lending to its own merchants. The proper run is Phase 8; whatever it shows is reported as it is |

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
| Kiva 2018 snapshot (Kaggle) and Duke Kiva sample | No repayment outcome; no Asian defaults. The 2016 archived snapshot is used instead (section 1.3) |
| India Informal Sector Enterprise Survey microdata | Replaced by the Bangladesh city indicators from the same survey programme |
| US SBA small-business loans | Not Asian |
| Czech PKDD'99 bank data | Not Asian; very small |
| Country-level tables used as training data | No row per borrower and no outcome; calibration and slides only |

## 5. A gap to state openly

No public dataset has repayment outcomes for Asian small merchants together with their purchase and delivery history. The synthetic data stands in for that, and the public datasets test the method on real outcomes of other kinds. Closing the gap needs a partner's data.
