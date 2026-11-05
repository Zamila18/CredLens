# CredLens

**Checked records and a clear credit summary for lenders who serve small shops.**

CredLens is a platform for a lender (our partner is ShopUp) that wants to lend to small shops it can see but cannot judge. A lender registers; its **Records Desk** uploads each shop's paper receipts; a reader fills a table and flags every doubtful figure; a person checks and publishes the record; the **shop owner** confirms it or reports a mistake; and a **Credit Officer** reads one plain summary: a confidence score out of 100, a suggested loan range, what looks good and what to watch. The officer decides.

> **Decision support only.** The score is advice. A person decides, and every decision is kept with its reason. No part of this system approves or declines credit.
> The model was trained on practice (synthetic) data and has not been checked on real repayments. No ShopUp data was used: the ShopUp demonstration is fictional.

Built by Team 4Bytes (Ahsanullah University of Science and Technology) for the 2026 Data, AI & Policy APAC Hackathon: Financial Health Frontiers. It is a prototype to demonstrate and defend, not a production system.

## The product in one minute

| Who | Signs in with | What they do |
|---|---|---|
| **Records Officer** (the lender's processing team) | email and password ("I am on the Records Desk") | Uploads a shop's receipts, compares the table with the picture, fixes anything wrong, publishes. Answers a merchant's report. |
| **Merchant** (the shop owner) | Merchant ID and the owner's name ("I am a merchant") | Sees their own receipts as tables, says "looks right" or reports a wrong line with a photo of their own copy, applies for a loan. |
| **Credit Officer** (the first one in a company owns it) | email and password ("I am a company") | Adds shops (paper consent form, signed copy read, then checked by a second officer), reads the credit summary, records a decision. |
| **Platform admin** | email and password from `.env` | Lists companies. Sees no shop's personal data by default. |

Only **published** lines reach the officers and the score. A line the merchant reports leaves the score until the Records Desk answers. An auditor role can read the log.

### What a Credit Officer reads

1. **Credit score, out of 100.** A *confidence score* built from the shop's checked records: the higher it is, the more the records support repayment. It comes from the model's calibrated estimate, never a bare yes or no. A shop with too few checked receipts shows **no score** (a number there would be a guess).
2. **Suggested loan range**, worked out from the company's own range rule and the shop's checked purchases only (sales are not used), capped at the amount the shop asked for.
3. **What looks good** and **what to watch**: plain sentences, and how late earlier instalments were paid, taken straight from the records.
4. **Your decision**: go with the suggestion, lend more or less than suggested (a written reason is needed), or ask for more records.

The technical panels (coverage, inputs, how the range was worked out) are collapsed below. The range rule is set once by the company owner (Settings → Loan range rule).

## Status (November 2026)

| Works now | Simulated or not done |
|---|---|
| Lender sign-up, invitation codes, roles, merchant sign-in with a Merchant ID | All shops and records are synthetic; there is no live link to ShopUp's systems |
| Paper consent form (English and Bangla) with a reference, signed copy read, checked by a person | Consent wording is a draft awaiting review by Bangladeshi lawyers |
| Receipt reading (EasyOCR) with built-in checks: quantity × rate, lines against the total, impossible dates, outliers, low confidence | The reader does not read handwriting: those receipts are typed in by the Records Desk |
| Records Desk check and publish; merchant confirms or reports a line; reported lines leave the score | The model has not been retrained on real repayments (retraining is an offline, versioned step) |
| Credit summary: score, range, reasons, decision with a written reason in an append-only log | Hosting on a server ([docs/DEPLOY.md](docs/DEPLOY.md)); native-speaker review of the Bangla |
| Stored assessments that can be recomputed from their own inputs and range rule | Email delivery: work emails are unverified and password resets are admin-issued codes |
| The ShopUp demonstration: nine fictional shops with months of history (`python tasks.py demo`) | |
| Lint, about 1,200 tests and CI | |

Fuller status, limits and the latest numbers: [docs/product/PLATFORM_STATUS.md](docs/product/PLATFORM_STATUS.md).

### How well are receipts read? (measured)

`python -m src.receipts.ocr_check` makes printed memos from known contents, damages them like phone photos, reads them with the real engine and counts what was right ([reports/receipt_ocr_check.md](reports/receipt_ocr_check.md)). On 20 fresh receipts (90 lines): amounts right **73.3%** after straightening tilted photos (54.7% before); English 90.2%, Bangla 59.2%. All 24 wrong amounts carried a flag a person would see. That is a small sample, not a guarantee, so a person checks every receipt before it counts.

### Where the model stands (synthetic data, validation months, seed 42)

| Measure | Value |
|---|---|
| Model in use | Logistic regression on 10 behaviour inputs |
| AUC | 0.710 (95% range 0.688 to 0.729); purchases only 0.667; a coin toss 0.500 |
| LightGBM, for comparison | 0.722 (0.701 to 0.742); gain +0.013, not enough to replace the simple model |
| Calibration error | 0.012 (no correction needed) |
| Bands | Strong 56% of loans (95.2% repaid), Review 29% (82.1%), Needs more info 15% (88.3%) |

These numbers show that the pipeline works on generated data. They are not a claim about real merchants. Say "around 0.70", not "above 0.70". One thing the demonstration showed: the model leans hardest on supplier loyalty (the share of repeat purchases from the same wholesalers), while payment delays inside the 30-day "repaid in time" rule barely move the score. Recalibrating on real repayments is the first job after a pilot. Details and limits: [PROJECT_BRIEF.md](PROJECT_BRIEF.md) section 18.

## Data

No partner data is used. The public data checks test the method; none of them is ShopUp data.

| Data mode | Source | What it is for |
|---|---|---|
| `synthetic_bd` | Generated, calibrated to public Bangladesh figures (20,000 merchants) | Trains the model and checks the pipeline end to end (offline) |
| `taiwan_cc` | UCI Taiwan credit-card default data | Checks the method on real Asian payment behaviour (AUC 0.743) |
| `india_ltfs` | India L&T vehicle loans (Kaggle) | Real borrowers, half with no credit record (AUC 0.611) |
| `homecredit` | Kaggle Home Credit (country not stated) | Larger scale (AUC 0.746; 0.601 without its outside score) |
| `kiva_asia` | Kiva loans to shops in Asia, 2009 to 2013 | Shows the limits: no borrower behaviour to score (AUC 0.644) |

Only Taiwan is evidence that the method works; the others show where it cannot, and why ([reports/REAL_LABEL_RESULTS.md](reports/REAL_LABEL_RESULTS.md)). Group audit: [reports/FAIRNESS.md](reports/FAIRNESS.md). Sources and licences: [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

## Run it

You need Python 3.10 or newer and, for the dashboard, Node.js 20.19 or newer. On Windows use `python` (PowerShell or cmd, not Git Bash, so `node` is on the PATH); on Mac or Linux `python3`.

```
python tasks.py setup       # create .venv and install dependencies (once, and when requirements.txt changes)
python tasks.py init-db     # create the empty operational database (data/credlens.db)
python tasks.py admins      # create the platform admins listed in .env (never prints passwords)
python tasks.py ocr-setup   # download the receipt reader's models once (needs internet; then it runs offline)
python tasks.py api         # API on :8000 (docs at http://localhost:8000/docs); also reads receipts in the background
python tasks.py app         # dashboard on :5173
```

The scorer takes about 30 seconds to build when the API starts. It needs the synthetic data and the trained model (`python tasks.py data`, then `python tasks.py train`) once.

**Settings (`.env`, never committed).** Copy `.env.example` to `.env`. It holds `CREDLENS_SECRET_KEY` (at least 32 characters; it signs invitation codes) and up to four platform admins (`CREDLENS_PLATFORM_ADMIN_1_EMAIL` and `_PASSWORD`, up to `_4_`). `DATABASE_URL` is optional; without it a local SQLite file is used. Existing databases made before the Records Desk redesign must be recreated: delete `data/credlens.db`, then `init-db` and `admins`. The old `data/app.db` is untouched.

**The ShopUp demonstration** (its own database; the real one is never touched):

```
python tasks.py demo        # builds data/credlens_demo.db (about 8 minutes; --fast skips the real receipt reader)
python tasks.py api --demo  # serves it on :8000 (stop any other API on :8000 first)
python tasks.py app
```

Each build writes [docs/product/DEMO_SHOPUP.md](docs/product/DEMO_SHOPUP.md): the logins, the nine shop stories, the scores the model gave and a suggested order for a video (`python tasks.py demo --guide-only` rewrites just that guide from the existing database). To rebuild it, stop the demo API first (Windows will not delete an open database). Everything about ShopUp in it is invented.

**Checks.** `python tasks.py test`, `python tasks.py lint`, then in `web/`: `npx tsc -b`, `npm run lint` and `npm run build`. After changing `src/api/schemas.py`, regenerate the dashboard's API types with the API running: `cd web`, then `npm run types` (uses `openapi-typescript@7.13.0` through npx, so the first run needs internet).

**Common problems**
- *The sign-in page says "check your connection":* the API is not running, or it answered 503 because the database is missing or made for an older version. Start `python tasks.py api` (or `api --demo`), and recreate an old database as above.
- *A page says "Page not found" after a link:* reload; the retired pages (Field work, spreadsheet imports, data sources, data quality) no longer exist.
- *Receipts stay "reading":* the reader runs inside the API process; run `python tasks.py ocr-setup` once with internet, and keep the API running.
- *Pages load slowly the first time:* the Vite dev server compiles on first load.
- *Something went wrong with the database:* stop the API and copy back the latest file from `data/backups/` (`python tasks.py backup` makes one). Never delete a database you cannot recreate.

Putting it on a server, or running offline at a venue: [docs/DEPLOY.md](docs/DEPLOY.md).

## Layout

```
config/default.yaml   every tunable number
src/accounts/         sign-up, invitations, sessions, merchant sign-in, platform admins
src/onboarding/       merchant registration, consent form PDF, signed-copy checks
src/extraction/       the receipt and form reader (EasyOCR), its queue and worker
src/receipts/         parsing, built-in checks, check-and-publish, merchant reports
src/assessment/       stored assessments, the company range rule, the credit summary
src/intake/           record rules (purchases, deliveries, repayments, applications, visits)
src/api/              FastAPI app; schemas.py is the API contract
src/demo/             the ShopUp demonstration (fictional cast, seeding, drawn receipts)
src/model/            labels, training, calibration, score, reasons, evaluation
src/features/         feature builder and the reason-sentence dictionary
src/adapters/         one adapter per data source, all returning the same seven tables
src/synth/            synthetic data generator (offline)
src/db/               database tables, init, loaders, backup
web/                  React dashboard (Vite, TypeScript, Tailwind), English and Bangla
tests/                about 1,200 tests; tests/fixtures/ holds tiny hand-made sample files
reports/              measured results: model, public data, fairness, receipt reading
docs/                 specifications, data plan, wording rules, product status and demo guide
```

## Rules this project keeps

- A person decides. The model gives a calibrated estimate; the 0/1 values are training labels only.
- Only checked lines count: every number is checked by the Records Desk, and the merchant can report a wrong line, which then leaves the score.
- No consent, no assessment. Scoring is refused without a valid consent record.
- A shop with too little checked data gets "not enough receipts yet", never a low score; missing data never lowers a score by itself.
- Features use only data from before each loan's decision date. Splits are by time where dates exist.
- Town, shop type, licence status and similar group columns are used to audit results, never as model inputs.
- The questionnaire is shown beside the score, not inside it.
- A reason is shown only when its sentence is true for the shop.
- The simpler model stays in use unless the more complex one is clearly better.
- The merchant sees their own records and decision status, never the score.
- No real merchant data and no secrets in the repository.
