# DATA_SOURCES.md: where the data comes from (skeleton)

Owner role: A (lead), with B for the columns. Completed in Phase 7, when the real files are inspected.

Status words used below:
- **Not checked**: nobody on the team has opened the real file or page yet.
- **Checked**: a teammate opened it on the date given and confirmed the item.

Nothing in this file is a result. Every "we use" and "we drop" entry is a plan until Phase 7 confirms the real columns.

Rules for every source:
- Raw files are downloaded by a person into `data/raw/<source>/`. That folder is gitignored.
- Raw files are never committed, uploaded to the shared database, or redistributed.
- No generated history is ever added to a real record.
- Group columns (gender, country, age band and similar) are used only to audit results, never as model inputs.

## 1. Sources that train or evaluate a model (row-level, real outcomes)

### 1.1 Kiva loans, filtered to Asia (`kiva_asia`)

| Item | Entry |
|---|---|
| Link | https://www.kiva.org/build/data-snapshots (fallback: the Kaggle dataset "additional kiva snapshot") |
| Licence / terms | Not checked |
| Download status | Not checked. The official links were reported broken in 2022 |
| Save to | `data/raw/kiva/` |
| Label | Planned: status paid = 1, defaulted = 0; other statuses dropped. Not checked on the real file |
| We use | To be filled in Phase 7 |
| We drop | To be filled in Phase 7 (anything recorded after the loan was posted) |
| Audit-only columns | To be filled in Phase 7 (planned: borrower gender, country) |
| Limits | No purchase, delivery or payment history. Defaults are rare. Default is partly driven by the field partner |

### 1.2 Taiwan credit-card default, UCI (`taiwan_cc`)

| Item | Entry |
|---|---|
| Link | https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients |
| Licence / terms | CC BY 4.0 according to the UCI page (seen in a web search on Oct 12, 2026). Cite I-Cheng Yeh, 2009 |
| Download status | Not checked |
| Save to | `data/raw/taiwan_cc/` |
| Label | Planned: 1 minus "default payment next month". Not checked on the real file |
| We use | To be filled in Phase 7 |
| We drop | To be filled in Phase 7 |
| Audit-only columns | To be filled in Phase 7 (planned: sex, education, marital status, age band) |
| Limits | Consumer credit cards, not merchants. One fixed window with no per-row dates, so the split is stratified random and marked weaker. Data from 2005 |

### 1.3 Home Credit Default Risk, Kaggle (`homecredit`)

| Item | Entry |
|---|---|
| Link | https://www.kaggle.com/competitions/home-credit-default-risk/data |
| Licence / terms | Checked Oct 12, 2026 (rules page read by the lead). The competition-specific rule says: "you may access and use the Competition Data only for the purposes of the Competition", and it supersedes the general rule that allows academic and non-commercial use. Section 7.B forbids transmitting, publishing or redistributing the data. "The Competition" is Kaggle's 2018 Home Credit competition, so use in this hackathon prototype is outside the literal terms. **The team lead decided on Oct 12 to use it anyway as a local, non-commercial method check and accepts that risk.** |
| Safeguards | Raw files stay on the lead's laptop only: never committed, never loaded into the shared database, never copied to the hosting server. The hosted dashboard shows only aggregate results (metrics, calibration, group audit) for this mode, never individual records. First data source to remove if anyone objects |
| Download status | Not downloaded yet. Needs a Kaggle account and acceptance of the competition rules |
| Save to | `data/raw/homecredit/` |
| Label | Planned: 1 minus TARGET. Not checked on the real file |
| We use | To be filled in Phase 7 (planned files: application_train, installments_payments, POS_CASH_balance) |
| We drop | To be filled in Phase 7 |
| Audit-only columns | To be filled in Phase 7 (planned: gender, age band, region rating) |
| Limits | **The data does not state its country**, so it is labelled "country not stated" and does not support an Asian claim. Consumer loans, not merchants. No absolute dates, so the split is stratified random and marked weaker |

### 1.4 Backup only: India L&T vehicle loans, Kaggle

Used only if Kiva cannot be downloaded or has no usable default label. Licence and columns: not checked. Not built unless needed.

## 2. Sources that calibrate the synthetic generator (never used for training)

| Source | Link | What we take | Value used | Status |
|---|---|---|---|---|
| Global Findex 2025 microdata, Bangladesh | https://microdata.worldbank.org/index.php/catalog/7869 | Share using mobile money / digital payments; borrowing and saving patterns | To be filled in Phase 1 | Not checked. Free registration; no redistribution |
| Bangladesh Bank MFS monthly statistics | https://www.bb.org.bd/en/index.php/financialactivity/mfsdata | Month-by-month seasonality of merchant payments | To be filled in Phase 1 | Not checked |
| ShopUp Series B press release | https://shopup.com.bd/web/press/valar-ventures-shopup-bangladesh | 73% of small retailers sell on credit; 27.5% have formal-finance access | 73%, 27.5% (company statement) | Not checked by this team since the review of Oct 10 |

Until a person supplies a figure, the generator uses a clearly marked placeholder.

## 3. Context and design references (slides, questionnaire, benchmarks)

| Source | Link | Used for |
|---|---|---|
| CGAP, Leveraging Transactional Data for MSE Lending | https://www.cgap.org/research/publication/leveraging-transactional-data-for-micro-and-small-enterprise-lending | Benchmark: AUC of about 0.70 is considered useful |
| FinHealth Score Toolkit | https://finhealthnetwork.org/wp-content/uploads/2021/11/FinHealthScoreToolkit-2021.pdf | Base wording for the 10-item questionnaire (check its terms of use) |
| Corner Shop Diaries | https://cornershop-msc-l-ift.com/ | Cash-flow rhythm of small shops |
| Small Firm Diaries, Indonesia | https://www.smallfirmdiaries.org/indonesia | Shocks and resilience patterns |
| IMF Financial Access Survey; Data.gov.in; NDAP; SHRUG | Listed in the team's Finverse result | Starter-kit context sources |

## 4. Considered and not used

| Source | Why not |
|---|---|
| US SBA small-business loans | Not Asian |
| Czech PKDD'99 bank data | Not Asian; very small |
| Country-level tables (Findex totals, IMF FAS) | No row per borrower and no outcome; calibration and slides only |
