# Starter kit: using CredLens with your own data, in another lender or country

Owner role: A (lead). Written Oct 18, 2026. Promised in the Phase 2 submission ("starter kit";
PROJECT_BRIEF section 17, item 3 and section 18, item 13).

This is the page to start from. It says what CredLens needs, how the pieces fit, which public data
can help, and what must be checked before anyone sees a score. The details are in the guides it points to.

## 1. What CredLens is, in one paragraph

A staff dashboard for thin-file, new-to-credit merchants. It joins a merchant's **stock purchases**
(Mokam-style wholesale orders the shop buys), **deliveries** (REDX-style parcels the shop sends) and
**repayments** (Baki-style credit), and shows a **readiness score** (the calibrated chance, out of 100, that a
loan is repaid in full within 30 days of its due date), a separate **coverage** figure (how much of the
expected evidence exists), a **band**, and the **reasons** in plain English and Bangla. An officer decides and
records why. **Nothing approves or declines credit.** No consent, no score.

## 2. The one-page schema map: seven tables

Every source is turned into the same seven tables (the data contract, `src/adapters/base.py`). A table a
source does not have stays **empty**; nothing is made up to fill it.

```
                        merchants (merchant_id, onboarded_at, district, town_tier, shop_type,
                            │       has_trade_license, consent_data_use, questionnaire_done)
     ┌──────────────┬───────┼───────────────┬──────────────────┬──────────────────┐
  purchases      deliveries │            questionnaire      consents
  (what the shop (parcels it │            (10 habit answers, (purpose, categories,
   BUYS: date,    sends:     │             1 to 5; never      granted, expires,
   amount,        dispatched,│             in the score)      revoked)
   category,      delivered, │
   supplier)      status,    loans (loan_id, issued_at, limit, outcome, when the outcome was known)
                  return     │
                  reason,    payments (loan_id, due date, paid date, amount due, amount paid)
                  COD, COD on time)
```

Column by column, with the checks each column gets: `docs/adapting.md`, section 2.
What each model input means and how it is built: `docs/FEATURE_DICTIONARY.md` and
`src/features/dictionary.yaml`.

Two rules that matter most:
- **Purchases are what the shop buys, not what it sells.** No sales or repeat-customer features exist.
- **Town tier, shop type and trade licence are audit-only.** They check the model for gaps between groups;
  they are never model inputs.

## 3. How to plug in your data

1. **Answer three questions first** (`docs/adapting.md`, section 1): which tables you have, what "repaid in
   time" means in your data, and whether you hold a consent for each merchant.
2. **Write an adapter**: one file in `src/adapters/` that reads your export and returns the seven tables. Copy
   `src/adapters/shopup_real.py` (the empty template for a partner's data) or one of the public adapters.
   Never wire the pipeline to one source.
3. **Register it** in `src/adapters/factory.py` and add its coverage checklist to `config/default.yaml`
   (`coverage_weights_by_mode`; the weights sum to 1).
4. **Run, in order**: build features, train, calibrate, measure on later months, write the model card
   (`python tasks.py train`), then serve it (`python tasks.py api`). `docs/adapting.md`, section 5.
5. **Nothing carries over from the synthetic data**: re-set and re-check the label rule, the band lines and the
   coverage weights on your own data (`docs/adapting.md`, section 6).
6. **New merchants from a file**: an admin can upload a zip of the seven CSVs on the Data import page; each
   file is checked against the contract, the bad rows are named, and new merchants are scored by the saved
   model. An import never changes an existing merchant's history or consent (`docs/API_NOTES.md`, "Import").

## 4. Public data that can help

Sources are listed with what they are good for. Licences and what we read from each:
`docs/DATA_SOURCES.md`. Raw files stay in `data/raw/` and are never committed or redistributed.

### To test the method on real repayment outcomes (row-level)
| Source | Region | Good for | Watch out |
|---|---|---|---|
| UCI Taiwan credit-card default | Taiwan | Repayment behaviour; CC BY 4.0 | Consumers, 2005, no dates per row |
| L&T vehicle loans (Kaggle) | India | Thin files: half have no bureau record | No terms stated; first-instalment default only |
| Kiva snapshot, Asia (Internet Archive) | Asia | Real small businesses | Defaults are mostly a field-partner event; our model on it must not be used |
| Home Credit (Kaggle) | Country not stated | Scale, instalment history | Competition-only terms; rows never shown |

### To shape synthetic data or check proportions (published totals)
| Source | Link | What it gives |
|---|---|---|
| Bangladesh Bank, mobile financial services statements | https://www.bb.org.bd/en/index.php/financialactivity/mfsdata | Monthly merchant payments: the seasonal shape our generator uses |
| World Bank Enterprise Surveys, informal sector | https://www.enterprisesurveys.org/en/data | Credit, accounts and mobile money of informal businesses, by city |
| World Bank Global Findex 2025 | https://www.worldbank.org/en/publication/globalfindex/download-data | Account ownership, mobile money, borrowing and saving of **all adults 15+** (not merchants). Definitions confirmed against the official glossary on Oct 17, 2026 (`config/calibration/`) |

Bangladesh 2024 (Findex, all adults 15+), useful context, **not used by the model**: 43.3% have an account;
20.8% personally used mobile money; 70.3% borrowed any money in the past year, but 13.1% borrowed from a
bank, credit card or mobile money; 2.8% made a digital payment to a merchant.

### Context (regional portals named in the team's Finverse result)
| Source | Link | Good for |
|---|---|---|
| IMF Financial Access Survey | find "Financial Access Survey" on the IMF's data site (imf.org); one series is mirrored at https://fred.stlouisfed.org/series/BGDFCMTVXDC (Bangladesh mobile money value) | Supply-side access: accounts, branches, mobile money, by country and year |
| Open Government Data Platform India | https://data.gov.in | Indian government datasets |
| NITI Aayog National Data and Analytics Platform (NDAP) | https://ndap.niti.gov.in | Indian government data with analytics tools |
| SHRUG, Development Data Lab | https://www.devdatalab.org/shrug | Village- and town-level data for India |

**The gap to state openly:** no public dataset has repayment outcomes for Asian small merchants together with
their purchase and delivery history. Closing it needs a partner's data, with consent.

## 5. Before anyone sees a score from new data

The full checklist is `docs/adapting.md`, section 8. The points that may never be skipped:
1. Every merchant has a consent record; no valid consent, no score.
2. Every model input uses only data from before the loan's decision date (`tests/test_leakage.py`).
3. The model is measured on later months it never saw, with ranges; the result is written in a model card,
   including what it does not show.
4. The group audit has been run (town, shop type, licence, or your source's equivalents), and any gap is reported.
5. Thin files get "Needs more info", never a lower score.
6. Officers know the score suggests and they decide; every override has a written reason.

## 6. What a first pilot could look like

- One lender, a few hundred merchants who consent, three months, small starter limits (labels exist only for
  merchants who already got credit, so a pilot is how the model learns about the others).
- Run the live import with the lender's own export first, in "check only".
- A small financial-diaries study (about 40 merchants, 3 months), as Finverse recommends; not built here.

## 7. Where everything is

| You want | Read |
|---|---|
| The data contract and adapters | `docs/adapting.md` |
| Where our data came from, licences | `docs/DATA_SOURCES.md` |
| What data we hold and where | `docs/data_inventory.md` |
| How the model works and was tested | `docs/MODEL_SPEC.md`, `docs/model_card_<mode>.md` |
| The API | `docs/API_NOTES.md` |
| Hosting it | `docs/DEPLOY.md`, `docs/SERVER_FILES.md` |
| Showing it to someone | `docs/LIVE_DEMO_GUIDE.md` |
| What we may and may not claim | `docs/WORDING_AND_QA.md` |
