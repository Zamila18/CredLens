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
| Audit-only columns | Age band from `Date.of.Birth`, `State_ID`, `Employment.Type` (provisional until Phase 7) |
| Leakage note | The dictionary describes every bureau column as "at the time of disbursement". Branch and employee identifiers must not be headline reasons |
| Limits | Vehicle loans to individuals, not merchants. A short three-month window |

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
