# HANDOVER.md: where the project stands and what each person does next

Kept up to date at the end of every phase, so a handover can happen at any time.
Last updated: end of Phase 8 (Oct 14, 2026).

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

Not built yet: API endpoints (9), dashboard (10), ablation and model cards (11), deployment (12).

Data on the lead's laptop only (never in git): Taiwan, India L&T, Home Credit, the Kiva archive, Findex, World Bank informal-sector indicators. Details: `docs/DATA_SOURCES.md`.

## 2. How to start (every teammate)

1. Clone the repository and pull `main`.
2. Create your own branch (you run git; Claude Code never does): for example `git checkout -b feat/dashboard`.
3. Run `python tasks.py setup`, then `python tasks.py test`. Expect all tests to pass, with some skipped.
4. Run `python tasks.py data` to create the synthetic data and load the local SQLite database (about 55 seconds; about 190 MB of CSV and a 350 MB database file, neither committed). Running it again never overwrites the database; to start afresh use `python tasks.py data --reset-db`, which also removes recorded decisions and the audit log.
5. Open the repository in VS Code with Claude Code and paste the first message for your role (section 4).

Rules that apply to everyone: read `CLAUDE.md`; two people never work in the same folder at the same time; small pull requests; one teammate reviews; merge only when tests pass.

## 3. Who does what next

### Lead (with Claude Code): data, then the model
| Order | Work | Folders |
|---|---|---|
| 1 | Phase 2 follow-up: create the Supabase project, load it, and check the PostgreSQL triggers and backup there | `src/db/` |
| 2 | Done (Oct 13): Phases 4, 5 and 6: model, calibration, score, coverage, bands, LightGBM, reasons | `src/model/` |
| 3 | Phase 7: adapters for Taiwan, India L&T, Home Credit, and Kiva if it qualifies | `src/adapters/` |
| 4 | Phases 8 and 11: real-label runs, ablation, group audit, model cards | `src/model/`, `reports/` |

### Humayra (heavy work): the dashboard and the API behind it
She can start now. The API contract and sample responses exist, and since Oct 13 so do the real model, scores, bands and reasons (see "What the API can call" below).

| Order | Work | Folders |
|---|---|---|
| 1 | Install Node.js LTS. Create the React app (Vite + TypeScript + Tailwind + shadcn/ui). Agree colours and layout with the lead | `web/` |
| 2 | App shell: sidebar, role switch (officer / admin / viewer), data-source selector, and the banner taken from `GET /health` | `web/` |
| 3 | API endpoints that return the sample files in `tests/fixtures/api/`: review queue, profile, score, decisions, model card, audit; roles from a header token | `src/api/` |
| 4 | Pages against those endpoints: review queue; merchant detail (timeline, score gauge, coverage meter, helps/hurts reasons, questionnaire panel, "Why might this be wrong?", decision form); decision log; model card; consent; audit; portfolio. English/Bangla toggle for reasons | `web/` |
| 5 | The database exists now (`src/db/models.py`, demo users `officer-1`, `officer-2`, `admin-1`, `viewer-1`). Phase 6 is done, so connect the API to the real database and real scores (see "What the API can call" below); consent check; audit entry on every profile read; decisions append-only | `src/api/`, `web/` |
| 6 | Questionnaire form on the merchant detail page: ten answers from 1 to 5, saved through `POST /merchants/{id}/questionnaire`; the panel updates, the score does not | `src/api/`, `web/` |
| 7 | Data import page (admin only): upload a CSV for one table, the API checks it against the data contract and reports rows accepted and rejected, then loads the accepted rows (`POST /admin/import/{table}`). Build the check-and-report step first. See PROJECT_BRIEF section 18, item 20 | `src/api/`, `web/` |

Must hold on every page: the banner names the data source and says "Decision support only."; a score is never shown without coverage and band; officers see sentences, never feature names; there is no approve or decline button; an override needs a written reason; the browser calls only the API, never the database.

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

### Dipto (light work): checks, documents and the things only a person can do
| Order | Work | Where |
|---|---|---|
| 1 | Confirm the Findex column definitions in the Findex codebook and correct `config/calibration/findex_bangladesh.csv` notes if needed | `config/calibration/` |
| 2 | Read CGAP's Kaleidofin case in "Banking in Layers" and write three lines on what it actually reports | `docs/` |
| 3 | Check the Bangla sentences in `src/features/dictionary.yaml` with a native speaker's eye; list any that sound unnatural or accusing | Report to the lead; the lead edits the file |
| 4 | Draft `docs/starter_kit.md` (public sources a lender could use, from `docs/DATA_SOURCES.md` and the team's Finverse result) and `docs/data_inventory.md` (what data exists, who owns it, who may view it) | `docs/` |
| 5 | When the dashboard exists: walk through it by hand with the demo script and list every problem | Report to Humayra |
| 6 | Slides and pitch text, following `docs/WORDING_AND_QA.md` | Outside the repository |

### Third teammate (when they arrive)
Sceptical review of every claim against code and tests (Phase 13), help with deployment, the backup video and rehearsals.

## 4. First message to paste into your own Claude Code

Humayra:
> Read CLAUDE.md, PROJECT_BRIEF.md (especially section 18), docs/HANDOVER.md and web/README.md. I am role D (full-stack). The last committed phase is 6. Check the repository matches that, then wait. My first task is to create the React app in web/ and build pages against the sample responses in tests/fixtures/api/.

Dipto:
> Read CLAUDE.md, docs/HANDOVER.md, docs/DATA_SOURCES.md and docs/WORDING_AND_QA.md. I am role A support (documents and checks). The last committed phase is 6. Check the repository matches that, then wait. My first task is in docs/HANDOVER.md section 3, under my name.

## 5. What not to touch

- `config/default.yaml`, `requirements.txt`, `src/features/dictionary.yaml`: only the lead edits these. Ask for changes.
- `data/raw/`: never commit anything from it. Never upload raw public files anywhere.
- `_latent_truth.csv` in the synthetic data folders: the hidden truth for generator tests. No feature, model, API or page may read it.
- The Home Credit files stay on the lead's laptop. The hosted demo shows only aggregate results for that mode.
