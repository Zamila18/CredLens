# HANDOVER.md: where the project stands and what each person does next

Kept up to date at the end of every phase, so a handover can happen at any time.
Last updated: end of Phase 5 (Oct 13, 2026).

## 1. What is finished and tested

| Phase | What exists | How to check |
|---|---|---|
| 0. Scaffold | Folders, config loading and checks, the seven-table data contract, adapters, feature dictionary (English and Bangla), API contract, sample API responses, `GET /health` | `python tasks.py test` |
| 1. Synthetic data | Generator for 20,000 Bangladesh-calibrated synthetic merchants at delivery signal strengths 0, 0.5 and 1; the `synthetic_bd` adapter; column dictionary (`src/synth/schemas.md`) | `python tasks.py data --all-strengths`, then `python tasks.py test` |
| 2. Database | Tables for the data contract plus users, decisions, audit log and model versions (`src/db/models.py`); loader; backup; Mifos X-style export. Decisions and the audit log are append-only, enforced in the application and by database triggers. Tested on SQLite. **Not yet run against Supabase/PostgreSQL** | `python tasks.py data` (generates, then loads `data/app.db`, about 55 seconds, about 350 MB), `python tasks.py backup`, `python -m src.db.mifos_adapter` |
| 3. Features and labels | 10 model inputs per loan in three groups (behaviour only; amounts of data are context, so a thin file cannot lower a score), coverage checklist, labels from the 30-day rule, and a leakage guard that catches planted leaks (`src/features/`, `src/model/labels.py`) | `python tasks.py test` (about 75 seconds) |
| 4. First model | Logistic regression on 10 behaviour inputs, fitted on the first 12 months, measured on the next 3 (validation). An input whose weight points against its meaning is removed and listed. Validation AUC 0.710 (0.688 to 0.729); first loans 0.665, repeat loans 0.770. Saved with a version id in `src/model/artifacts/<mode>/`; report in `reports/<mode>/metrics.json` | `python tasks.py train` (about 20 seconds) |
| 5. Calibration, score, bands | Calibration compared out of fold on validation (`none` kept: the model is already calibrated). `src/model/score.py`: score, coverage, band and low-score warning per loan. Lines: Strong 90, coverage 0.45, warning below 70 (settings in `config/default.yaml`, `score` section). On validation: Strong 56% of loans (95.2% repaid), Review 29% (82.1%), Needs more info 15% (88.3%). The sample API responses in `tests/fixtures/api/` use the new lines | `python tasks.py train`, `python tasks.py test` |

Not built yet: LightGBM and reasons (6), public-data adapters (7), real-label runs (8), API endpoints (9), dashboard (10), ablation and model cards (11), deployment (12).

Data on the lead's laptop only (never in git): Taiwan, India L&T, Home Credit, Findex, World Bank informal-sector indicators. The Kiva archive is still downloading. Details: `docs/DATA_SOURCES.md`.

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
| 2 | Phases 5 and 6: calibration, score and coverage, bands, LightGBM, reasons | `src/model/` |
| 3 | Phase 7: adapters for Taiwan, India L&T, Home Credit, and Kiva if it qualifies | `src/adapters/` |
| 4 | Phases 8 and 11: real-label runs, ablation, group audit, model cards | `src/model/`, `reports/` |

### Humayra (heavy work): the dashboard and the API behind it
She can start now. Nothing below waits for the model: the API contract and sample responses already exist.

| Order | Work | Folders |
|---|---|---|
| 1 | Install Node.js LTS. Create the React app (Vite + TypeScript + Tailwind + shadcn/ui). Agree colours and layout with the lead | `web/` |
| 2 | App shell: sidebar, role switch (officer / admin / viewer), data-source selector, and the banner taken from `GET /health` | `web/` |
| 3 | API endpoints that return the sample files in `tests/fixtures/api/`: review queue, profile, score, decisions, model card, audit; roles from a header token | `src/api/` |
| 4 | Pages against those endpoints: review queue; merchant detail (timeline, score gauge, coverage meter, helps/hurts reasons, questionnaire panel, "Why might this be wrong?", decision form); decision log; model card; consent; audit; portfolio. English/Bangla toggle for reasons | `web/` |
| 5 | The database exists now (`src/db/models.py`, demo users `officer-1`, `officer-2`, `admin-1`, `viewer-1`). After the lead's Phase 6: connect the API to the real database and real scores; consent check; audit entry on every profile read; decisions append-only | `src/api/`, `web/` |
| 6 | Questionnaire form on the merchant detail page: ten answers from 1 to 5, saved through `POST /merchants/{id}/questionnaire`; the panel updates, the score does not | `src/api/`, `web/` |
| 7 | Data import page (admin only): upload a CSV for one table, the API checks it against the data contract and reports rows accepted and rejected, then loads the accepted rows (`POST /admin/import/{table}`). Build the check-and-report step first. See PROJECT_BRIEF section 18, item 20 | `src/api/`, `web/` |

Must hold on every page: the banner names the data source and says "Decision support only."; a score is never shown without coverage and band; officers see sentences, never feature names; there is no approve or decline button; an override needs a written reason; the browser calls only the API, never the database.

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
> Read CLAUDE.md, PROJECT_BRIEF.md (especially section 18), docs/HANDOVER.md and web/README.md. I am role D (full-stack). The last committed phase is 1. Check the repository matches that, then wait. My first task is to create the React app in web/ and build pages against the sample responses in tests/fixtures/api/.

Dipto:
> Read CLAUDE.md, docs/HANDOVER.md, docs/DATA_SOURCES.md and docs/WORDING_AND_QA.md. I am role A support (documents and checks). The last committed phase is 1. Check the repository matches that, then wait. My first task is in docs/HANDOVER.md section 3, under my name.

## 5. What not to touch

- `config/default.yaml`, `requirements.txt`, `src/features/dictionary.yaml`: only the lead edits these. Ask for changes.
- `data/raw/`: never commit anything from it. Never upload raw public files anywhere.
- `_latent_truth.csv` in the synthetic data folders: the hidden truth for generator tests. No feature, model, API or page may read it.
- The Home Credit files stay on the lead's laptop. The hosted demo shows only aggregate results for that mode.
