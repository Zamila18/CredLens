# HANDOVER.md: where the project stands and what each person does next

Kept up to date at the end of every phase, so a handover can happen at any time.
Last updated: live import demo added, dashboard redesign in progress (Oct 17, 2026).

## 1. What is finished and tested

| Phase | What exists | How to check |
|---|---|---|
| 0. Scaffold | Folders, config loading and checks, the seven-table data contract, adapters, feature dictionary (English and Bangla), API contract, sample API responses, `GET /health` | `python tasks.py test` |
| 1. Synthetic data | Generator for 20,000 Bangladesh-calibrated synthetic merchants at delivery signal strengths 0, 0.5 and 1; the `synthetic_bd` adapter; column dictionary (`src/synth/schemas.md`) | `python tasks.py data --all-strengths`, then `python tasks.py test` |
| 2. Database | Tables for the data contract plus users, decisions, audit log and model versions (`src/db/models.py`); loader; backup; Mifos X-style export. Decisions and the audit log are append-only, enforced in the application and by database triggers. Tested on SQLite. **Not yet run against Supabase/PostgreSQL** | `python tasks.py data` (generates, then loads `data/app.db`, about 55 seconds, about 350 MB), `python tasks.py backup`, `python -m src.db.mifos_adapter` |
| 3. Features and labels | 10 model inputs per loan in three groups (behaviour only; amounts of data are context, so a thin file cannot lower a score), coverage checklist, labels from the 30-day rule, and a leakage guard that catches planted leaks (`src/features/`, `src/model/labels.py`) | `python tasks.py test` (about 75 seconds) |
| 4. First model | Logistic regression on 10 behaviour inputs, fitted on the first 12 months, measured on the next 3 (validation). An input whose weight points against its meaning is removed and listed. Validation AUC 0.710 (0.688 to 0.729); first loans 0.665, repeat loans 0.770. Saved with a version id in `src/model/artifacts/<mode>/`; report in `reports/<mode>/metrics.json` | `python tasks.py train` (about 20 seconds) |
| 5. Calibration, score, bands | Calibration compared out of fold on validation (`none` kept: the model is already calibrated). `src/model/score.py`: score, coverage, band and low-score warning per loan. Lines: Strong 90, coverage 0.45, warning below 70 (settings in `config/default.yaml`, `score` section). On validation: Strong 56% of loans (95.2% repaid), Review 29% (82.1%), Needs more info 15% (88.3%). The sample API responses in `tests/fixtures/api/` use the new lines | `python tasks.py train`, `python tasks.py test` |
| 6 (part 1). Second model | LightGBM with the same rules (missing data neutral, each input only pushes the way its meaning says), tuned inside the training period (`src/model/boosted.py`). Choice rule in `train.py`: the logistic regression stays unless the whole range of LightGBM's AUC gain reaches 0.01. On synthetic data: 0.710 against 0.722, gain +0.013 (+0.003 to +0.021), so the **logistic regression is in use** | `python tasks.py train` (about 40 seconds) |
| 6 (part 2). Reasons | `src/model/explain.py`: baseline (the average merchant) plus exact contributions per input that add up to the score; top 3 up and top 3 down as dictionary sentences in English and Bangla, each with a number ("Returns 11.1% vs average 6.8%"); a sentence is shown only when it is true for the merchant. `score_card(saved, feature_row, config, mode)` returns everything `GET /merchants/{id}/score` needs | `python tasks.py test` |
| 7 (part 1). Taiwan | Shared plumbing for public data (`source_records`, one feature builder per mode, stated outcomes as labels) and the `taiwan_cc` mode: adapter, eight behaviour inputs, coverage, audit columns kept apart, a planted-leak test. India, Home Credit and Kiva adapters follow | `python tasks.py test` |
| 7 (part 2). India | The `india_ltfs` mode: adapter, six behaviour inputs (one from the loan, five from the bureau summary), coverage, time split by month, audit columns and organisation identifiers kept away from the model. Half the borrowers have no bureau record and get "Needs more info" | `python tasks.py test` |
| 7 (part 3). Home Credit | The `homecredit` mode (country not stated): adapter that reads 1.1 GB of history in chunks and saves the per-applicant counts, nine inputs (six from earlier instalments, two from the loan, one outside score kept apart), coverage, a check that no history row is dated after the application | `python tasks.py test` |
| 7 (part 4). Kiva | The `kiva_asia` mode: reads the 1.16 GB archive in place, keeps no personal data, removes repeated loans, cuts off at mid-2013, works out each field partner's track record as of the posting day. Three inputs, none about borrower behaviour. The description is never read (it reveals the outcome) | `python tasks.py test` |
| 8. Real-label runs | Training runs for every data mode (`python tasks.py train --all-modes`, about 4 minutes). Validation AUC: Taiwan 0.743, India 0.611, Home Credit 0.746 (0.601 without its outside score), Kiva 0.644 (not usable: see the results page). What each result does and does not show: `reports/REAL_LABEL_RESULTS.md`. Home Credit rows can never be shown: a score card or queue in that mode is refused (`RowsNotShown`); the dashboard shows that mode's totals only. A public mode has no review queue (every outcome is known) | `python tasks.py train --mode taiwan_cc` (needs the raw file on the machine) |
| Mifos X check | A real Mifos X (Apache Fineract) in Docker accepted 50 merchants, 85 loans and 73 repayments from the export, and its loan statuses matched CredLens for all 85 (`tools/mifos/`, `src/db/mifos_load.py`). Local test only | `tools/mifos/README.md` (needs Docker Desktop) |
| 11 (part 1). Ablation | Purchases, payments, deliveries and questionnaire added one at a time, at three delivery signal strengths and three seeds. Deliveries add nothing when they carry no signal (+0.0000) and +0.055 at full signal; the negative control is a test. Report and chart in `reports/ablation/`. Also: the PostgreSQL path is checked (a fault with `TRUNCATE` fixed) | `python -m src.model.ablation` (about 8 minutes) |
| 9. API (Humayra) | Queue, profile, score, consent, decisions, model card, audit, questionnaire and import endpoints; demo roles from the `X-Demo-Token` header; consent check; an audit entry on every read of a merchant; decisions append-only, with the score and model version taken from the server. Contract and role table: `docs/API_NOTES.md` | `python tasks.py api`, then http://localhost:8000/docs |
| Plain summary | Every score card carries `summary_en` and `summary_bn`: a short paragraph built from the card itself (no language model, no internet), which never recommends lending or not | `python -m src.model.scoring` |
| Phase 9 review (Oct 15) | Every consent now covers the questionnaire (before, 11,624 consenting merchants could not be asked it); the queue carries `low_score_warning`; `GET /merchants/{id}/consent`; officers can read the model card; the score response carries the summary; `docs/API_NOTES.md` now says plainly that imported rows never reach a score | `python tasks.py test` |
| 11 (part 2). Group audit | Every audit column of every data mode, on the validation months: ranking and calibration of each group against the rest, with ranges; flagged only when ranges do not overlap or (synthetic) a gap is in all three seeds. A planted gap is caught by a test. Flagged: none in synthetic or Taiwan; regions in India, under-30s in Home Credit (ranking only), countries in Kiva. Details: `reports/FAIRNESS.md`, PROJECT_BRIEF item 40 | `python -m src.model.fairness --all-modes` (about 7 minutes; public modes need their raw files) |
| 11 (part 3). Model cards | One card per data mode from the reports: use, data and terms, label, split, inputs in words, results with ranges, bands, what it shows and does not, ablation, group findings, limits. JSON for `GET /model/card` (any mode with `?mode=`), a page in `docs/model_card_<mode>.md`. Public-data cards say the model is a method check, not for scoring | `python -m src.model.model_card --all-modes` (seconds) |
| 11 (part 4). Test period | Each model measured once on its held-back test period, every look in the ledger first, a second look refused without a written reason. Test AUC: synthetic 0.728 (not a clean holdout: looked at in Phase 1), Taiwan 0.752, India 0.599 (calibration off after a drop in repayment), Home Credit 0.723, Kiva 0.435 (wrong way round). On every model card | `python -m src.model.final_test --mode MODE` (refuses a second look) |
| 10. Dashboard (Dipto) | React dashboard in `web/` against the API: review queue, merchant page (score dial with coverage and band, plain summary, reasons, evidence and timeline, consent, decision form, questionnaire form), decision log, model card with a tab per data source (`?mode=`), audit log, data import, consent page and the Bangla phone consent demo, portfolio. Every number comes from the API. Reviewed by the lead on Oct 16: scores, bands, coverage and model-card AUCs match the model and the reports; an officer's decision reaches the log and the audit; public modes checked live | `python tasks.py api`, then in `web/`: `npm ci` and `npm run dev` (http://localhost:5173) |
| Live import (Oct 17) | New merchants in an imported file are scored by the saved model (nothing retrained) and appear in the review queue; `POST /admin/import-bundle` checks a zip of the contract files in one transaction; a new merchant may bring its consent; decisions keep `band_shown` and `coverage_shown`. Demo file: `data/demo/credlens_demo_bundle.zip`, expected results in `data/demo/EXPECTED.md` | `python -m pytest tests/test_live_import.py`; `python -m src.synth.demo_batch` |

Not built yet: deployment (12). Phases 10 and 11 are complete. Since Oct 16 the language switch (sidebar, "Language · ভাষা") changes the whole dashboard and the model cards; the Bangla needs a native-speaker review before the demo.

**The synthetic model is in git** (`src/model/artifacts/synthetic_bd/`, Oct 16): it is the one measured on the test period, so every laptop and the server use it and its model card keeps the test result and the group audit. Do not run `python tasks.py train` for synthetic data before the demo; if you did, `git restore src/model/artifacts/synthetic_bd` brings the measured model back.

**After pulling the Oct 15 changes, everyone runs once:** `python tasks.py data --reset-db`, then `python tasks.py train` (the consents changed, and the reset also clears test decisions). This resets the LOCAL SQLite database only: if your `.env` points at Supabase, the command refuses, on purpose. Resetting the shared database is a team decision (`python -m src.db.load --reset --reset-shared-database`).

Data on the lead's laptop only (never in git): Taiwan, India L&T, Home Credit, the Kiva archive, Findex, World Bank informal-sector indicators. Details: `docs/DATA_SOURCES.md`.

## 2. How to start (every teammate)

1. Clone the repository and pull `main`.
2. Create your own branch (you run git; Claude Code never does): for example `git checkout -b feat/dashboard`.
3. Run `python tasks.py setup`, then `python tasks.py test`. Expect all tests to pass, with some skipped.
4. Run `python tasks.py data` to create the synthetic data and load the local SQLite database (about 55 seconds; about 190 MB of CSV and a 350 MB database file, neither committed). Running it again never overwrites the database; to start afresh use `python tasks.py data --reset-db`, which also removes recorded decisions and the audit log.
5. Open the repository in VS Code with Claude Code and paste the first message for your role (section 4).

Rules that apply to everyone: read `CLAUDE.md`; two people never work in the same folder at the same time; small pull requests; one teammate reviews; merge only when tests pass.

## 3. Who does what next (team split of Oct 15)

| Person | Phases | Folders |
|---|---|---|
| Lead (Zamila, with Claude Code) | 11 (parts 2 to 4), documents and checks; the Hostinger deployment at the end, by following `docs/DEPLOY.md` | `src/model/`, `reports/`, `src/synth/`, `src/adapters/`, `src/db/`, `config/`, `docs/` |
| Dipto | 10: the dashboard | `web/` |
| Humayra | 12 and 13: backend, database, deployment files and guide, backend review | `src/api/`, `deploy/` (new), `docs/DEPLOY.md`, `docs/adapting.md` |

Dipto and Humayra meet at the API. If a page needs a field or endpoint that is missing, Dipto asks Humayra and she adds it in `src/api/`; Dipto does not edit `src/api/`.

### Lead (with Claude Code)
| Order | Work | Folders |
|---|---|---|
| 1 | Done (Oct 15): Phase 11 part 2, the group audit | `src/model/fairness.py`, `reports/` |
| 2 | Done (Oct 15): Phase 11 part 3, the model cards | `src/model/model_card.py` |
| 3 | Done (Oct 15): Phase 11 part 4, the test period, once per model | `src/model/final_test.py`, `reports/` |
| 4 | Documents and checks (moved from Dipto): Findex codebook check, CGAP Kaleidofin case, first pass of the Bangla review (a native speaker confirms), `docs/starter_kit.md`, `docs/data_inventory.md`, slides text | `docs/`, `config/calibration/` |
| 5 | Remove the two stale Phase 7 skip placeholders in `tests/test_adapters.py` | `tests/` |
| 6 | In progress (Oct 17): live import demo (done) and the dashboard redesign from `web/design-reference/CredLens_Final_Designs/` | `src/api/`, `src/synth/demo_batch.py`, `web/` |
| 7 | When everything else is done: buy the Hostinger VPS and deploy by following Humayra's `docs/DEPLOY.md` | the server |

Phase 11 stays with the lead: the public data modes need the raw files, which exist only on the lead's laptop and may not be shared.

### Dipto: Phase 10, the dashboard
Phase 9 (the API) is done, reviewed and fixed. Phase 10 builds the React dashboard in `web/` against it. Everything a page needs is in `GET /openapi.json` and `docs/API_NOTES.md`; sample responses are in `tests/fixtures/api/`.

| Order | Work | Folders |
|---|---|---|
| 1 | Node.js LTS; create the React app (Vite + TypeScript + Tailwind + shadcn/ui); types from `/openapi.json` | `web/` |
| 2 | App shell: sidebar, role switch (`officer-1`, `officer-2`, `admin-1`, `viewer-1`, sent as `X-Demo-Token`), banner from `GET /health` on every page, English/Bangla toggle | `web/` |
| 3 | Review queue (`GET /merchants`): score, coverage, band, low-score warning, consent; "no consent" rows show no score | `web/` |
| 4 | Merchant detail: timeline, purchases/deliveries/payments panels, score with coverage meter and band, the plain summary (`summary_en`/`summary_bn`) at the top, helps/hurts reasons, questionnaire panel and form (beside the score, never inside it), consent panel (`GET /merchants/{id}/consent`), "Why might this be wrong?", decision form (officers only; override needs a reason) | `web/` |
| 5 | Decision log, model card (every role), audit log (admin), import page (admin; says imported rows do not change scores yet), portfolio (first to cut if time runs out) | `web/` |
| 6 | Public data modes: no review queue; show the model card and totals only. Home Credit rows are never shown (the API refuses them) | `web/` |

Must hold on every page: the banner names the data source and says "Decision support only."; a score is never shown without coverage and band; officers see sentences, never feature names; there is no approve or decline button; an override needs a written reason; the browser calls only the API, never the database.

A real baseline score is about 92 and most reasons move the score by 0.2 to 6 points, so design the reason bars for small numbers.

### Humayra: Phases 12 and 13, the backend
| Order | Work | Where |
|---|---|---|
| 1 | Supabase: create the project (HUMAN STEP; the lead can invite her), put `DATABASE_URL` in `.env`, load the synthetic data, check that decisions and the audit log refuse UPDATE, DELETE and TRUNCATE, and that `python tasks.py backup` works there. Never run `tests/test_postgres.py` against Supabase (it is for a throwaway local database only) | `.env` (never committed) |
| 2 | Find out what the API needs on a server for each data mode. Raw public files never go to the server; public modes show reports and totals only; Home Credit rows never | `src/api/`, `docs/DEPLOY.md` |
| 3 | Deployment files and guide (Zamila runs them on the Hostinger VPS at the end): the API as a systemd service, an Nginx config that serves the built dashboard and passes `/api` to the API, HTTPS, the whole site behind a password, a production `.env` template (no real values), and `docs/DEPLOY.md` with every command in order for a fresh Ubuntu server. Test what can be tested on a laptop (production settings, the built dashboard served by the API or a local Nginx) | `deploy/`, `docs/DEPLOY.md` |
| 4 | Which model files and reports the server needs, and how they get there; a health check that waits for the scorer (about 30 seconds to build) | `deploy/`, `docs/DEPLOY.md` |
| 5 | Offline fallback: one documented way to run API and dashboard on a laptop with no internet | `docs/DEPLOY.md`, `README.md` |
| 6 | `docs/adapting.md` (how another lender adds a data adapter in `src/adapters/`); a small script that picks the demo merchants (one Strong, one Needs more info, one without consent) | `docs/`, `deploy/` |
| 7 | Add any field or endpoint Dipto's pages need | `src/api/` |
| 8 | Phase 13 backend review: every endpoint has the right roles, consent check and audit; nothing approves or declines; hosted and local give the same score; no secrets in the repo; CORS limited to the site; speed of queue, score and consent; backend boxes in `docs/ACCEPTANCE_CHECKLIST.md` filled with evidence | whole repo (read), fixes in her folders |

#### What the API can call for real scores (ready since Oct 13)

```python
from src.config import load_config
from src.model.explain import ConsentRequired
from src.model.scoring import Scorer, UnknownMerchant

scorer = Scorer(load_config())      # ONCE, when the API starts (about 30 seconds); keep it
queue = scorer.queue()              # review queue as a table, oldest first
card = scorer.card("M0000123")      # one merchant's score card
```

- Create the `Scorer` once at start-up and reuse it. It builds the feature table, which takes about half a minute for 20,000 merchants; never do that per request. It needs `python tasks.py data` and `python tasks.py train` to have been run.
- `scorer.card(id)` has every field of `ScoreResponse` in `src/api/schemas.py`, plus `banner`. It raises `ConsentRequired` when the merchant has no valid consent (turn that into the API's "consent needed" response) and `UnknownMerchant` for an id with no loan (a 404).
- `scorer.queue()` has `merchant_id`, `loan_id`, `pending_since`, `consent_valid`, `score`, `coverage`, `band`, `low_score_warning`. A merchant without consent is listed with no score, coverage or band. It does not know whether an officer has already decided: add `status` from the decisions table, and the district, town tier and shop type from the merchants table.
- A merchant is scored on their most recent loan. The queue holds the merchants whose most recent loan has no outcome yet (about 4,000 on the synthetic data).
- To look at a real card: `python -m src.model.scoring` (first merchant of the queue) or `python -m src.model.scoring <merchant_id>`.
- Rules for the endpoints: write an audit entry on every profile read; never turn a band into an approve or decline; never change a loan.

Sample numbers changed on Oct 13: scores in `tests/fixtures/api/` now follow the new band lines (Strong from 90, coverage from 45%). A real baseline score is about 92 and most reasons move the score by 0.2 to 6 points, so design the reason bars for small numbers.

## 4. First message to paste into your own Claude Code

Dipto:
> Read CLAUDE.md, docs/HANDOVER.md, docs/API_NOTES.md and docs/WORDING_AND_QA.md. I am Dipto and I build Phase 10, the React dashboard in web/. Check the repository, run the tests, then wait.

Humayra:
> Read CLAUDE.md, docs/HANDOVER.md, docs/API_NOTES.md and PROJECT_BRIEF.md section 18. I am Humayra and I do the backend for Phases 12 and 13. Check the repository, run the tests, then wait.

## 5. What not to touch

- `config/default.yaml`, `requirements.txt`, `src/features/dictionary.yaml`: only the lead edits these. Ask for changes.
- `data/raw/`: never commit anything from it. Never upload raw public files anywhere.
- `_latent_truth.csv` in the synthetic data folders: the hidden truth for generator tests. No feature, model, API or page may read it.
- The Home Credit files stay on the lead's laptop. The hosted demo shows only aggregate results for that mode.
