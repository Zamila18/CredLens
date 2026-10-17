# Data inventory: every piece of data CredLens holds, where, and under what rules

Owner role: A (lead). Written Oct 18, 2026, from the files on the lead's laptop and the repository.
Promised in the Phase 2 submission ("data inventory"; PROJECT_BRIEF section 18, item 13).
Where each public source comes from, its licence and what is read from it: `docs/DATA_SOURCES.md`.
What the hosting server holds: `docs/SERVER_FILES.md`.

## The short version

- **No real merchant's data is in CredLens.** No ShopUp data was obtained. The demo runs on synthetic
  (generated) merchants; the public datasets only test the method.
- **Raw public files stay on the lead's laptop**, in `data/raw/` (gitignored). They are never committed,
  uploaded to the shared database, copied to the server, or redistributed.
- **The hosted site holds synthetic data only.** For the public sources it shows model cards: totals and
  plain words, never a row.
- **Every look at a merchant is written down** (audit log), and decisions can never be edited or deleted.

## 1. What is held, and where

Sizes measured on the lead's laptop on Oct 18, 2026.

| Data | Where | Size | In git? | On the server? | Personal data? |
|---|---|---|---|---|---|
| Synthetic merchants (7 contract tables) | `data/raw/synthetic_bd/strength_*/` | 577 MB (3 signal strengths) | No (re-made by `python tasks.py data`, seeded) | Yes, re-made there with the same seed | None: generated, no real person |
| The generator's hidden truth `_latent_truth.csv` | next to the synthetic tables | small | No | No (deleted after `tasks.py data`) | None; read only by the generator's tests |
| Local database (SQLite) | `data/app.db` | 334 MB | No | Its own copy, made from the synthetic tables | Demo users only (4 ids, no names) |
| Live import demo batch | `data/demo/` (7 CSVs, the zip, `EXPECTED.md`) | 53 KB | Yes | Yes (with the code) | None: 5 generated merchants |
| Trained synthetic model | `src/model/artifacts/synthetic_bd/` | 8 KB | Yes (the measured model) | Yes | None |
| Public-data models | `src/model/artifacts/{taiwan_cc,india_ltfs,homecredit,kiva_asia}/` | 8 to 288 KB | No (trained on licensed files) | No | None stored; they are fitted weights |
| Reports and model cards | `reports/` | 932 KB | Yes (totals and charts only) | Yes | None: totals, no rows |
| Calibration figures | `config/calibration/` | 13 KB | Yes (published national totals) | Yes | None |
| Taiwan credit cards (UCI) | `data/raw/taiwan_cc/` | 5.3 MB | No | No | Anonymous client rows; sex, education, marriage, age are audit-only |
| India L&T vehicle loans (Kaggle) | `data/raw/india_ltfs/` | 40 MB | No | No | Anonymous loan rows; date of birth, state, employment are audit-only |
| Home Credit (Kaggle) | `data/raw/homecredit/` | 1.2 GB | No | No | Anonymous applicant rows; **rows are never shown on any screen** |
| Kiva snapshot (Internet Archive) | `data/raw/kiva/` (zip, read in place) | 1.2 GB | No | No | Contains names, photos, stories: **never read**; a test proves none survives |
| Global Findex 2025 (country level) | `data/raw/findex/` | 17 MB | No (the 7 figures used are in `config/calibration/`) | No | None: country totals |
| World Bank informal-sector indicators | `data/raw/wb_informal/` | 32 KB | No (the figures are in `config/calibration/`) | No | None: city totals |
| Secrets (`DATABASE_URL`, keys) | `.env` | tiny | **Never** (gitignored) | Written by hand on the server | No data; credentials |

## 2. What the running app stores (the database)

| Table | What | Who writes it | Can it change? |
|---|---|---|---|
| `merchants`, `loans`, `purchases`, `deliveries`, `payments` | The seven contract tables (with `questionnaire` and `consents`) | The loader, and the admin import for **new** merchants only | An import never overwrites a row, and may not add history or consent for a merchant of the original data |
| `questionnaire` | The ten habit answers | An officer (or a lender's file for a new merchant) | Saving replaces the merchant's earlier answers; never a model input |
| `consents` | Consent records: purpose, categories, granted, expires, revoked | The consent system's records (loader, or a lender's file for a new merchant) | Nothing in CredLens can grant or revoke a consent. An officer may only **ask** (recorded in the audit log) |
| `decisions` | Officer decisions, with the score, band, coverage and model version shown | Officers only | **Append-only**, refused in the code and by database triggers |
| `audit_log` | Every read of a merchant, the queue, consents and the audit log; every decision, answer, import, refusal and consent request | The API, before anything is shown | **Append-only**, as above |
| `users` | 4 demo users (officer-1, officer-2, admin-1, viewer-1) | The loader | A demo role switch, not a login |

## 3. Who may view what, and how to request access

| Who | May view | May do | How they get access |
|---|---|---|---|
| Credit officer (`officer-1`, `officer-2`) | Review queue, merchant pages of consenting merchants, decision log, portfolio, model card, consent list | Record decisions and questionnaire answers; ask a merchant for consent | In this prototype, the demo role switch. In a pilot: an account created by the lender's administrator |
| Administrator (`admin-1`) | Everything officers see, plus the audit log | Import a lender's file (new merchants only) | As above |
| Viewer (`viewer-1`), e.g. a manager or auditor | Everything officers see | Nothing: read-only | As above |
| A merchant | Their own consent screen (phone demo) | Give, refuse or withdraw consent | In their own app; CredLens has no merchant login |
| Anyone else | Public model cards and reports in the repository (totals only, no rows) | Nothing | The public repository |

**The demo role switch is not a login**, so the hosted site must sit behind a password. **To request the
raw public files**, download them from their own source under its terms (`docs/DATA_SOURCES.md`); the team
does not pass them on. **To request a pilot dataset**, a lender signs a data-sharing agreement and collects
each merchant's consent first (`docs/pilot_plan.md`). Every view of a merchant is recorded in the audit
log, which only an administrator can read.

## 4. Rules that apply to all of it

1. **Purpose:** credit-readiness assessment, and nothing else (the consent's stated purpose).
2. **Minimum data:** only the fields the features need are kept and shown. Group columns (town tier, shop
   type, trade licence; and the public sources' gender, age band, region, state) are audit-only, never
   model inputs.
3. **Consent first:** no valid consent, no score, no evidence on screen, no decision, no questionnaire.
4. **No invented history on real rows:** generated purchases, deliveries or payments are never added to a
   public dataset's records.
5. **Before the decision date only:** every model input uses data from before the loan was issued.
6. **Times:** stored in UTC, shown in Bangladesh time (UTC+06:00).
7. **Keeping and deleting:** the prototype keeps everything it holds for the hackathon. The raw public files
   are deleted from the lead's laptop when the project ends; nothing else holds them.

## 5. Practices this follows, and where to read them

- UK Information Commissioner's Office, *Data sharing: a code of practice*:
  https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/data-sharing/data-sharing-a-code-of-practice/
  (named in the team's plan as a reference for how a lender and a platform share merchant data).
- Open Data Institute (ODI) guidance on data practices and data ethics: a reference named in the team's plan.
  Find it on the ODI's own website (theodi.org); the exact page was not confirmed for this document.
- Bangladesh: there is no account-aggregator consent rail. Consent here is platform consent recorded in the
  consents table; India's Account Aggregator, Singapore's SGFinDex and Open Finance PH are design references,
  not integrations (`docs/WORDING_AND_QA.md`).

These are references for good practice. CredLens does not claim to comply with any law; a pilot with a
real lender needs that lender's own legal review.
