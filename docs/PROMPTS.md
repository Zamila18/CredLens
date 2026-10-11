# PROMPTS.md: phase-by-phase prompts for Claude Code (v2, fresh start)

How to use: open the repo in Claude Code (VS Code panel is fine). Paste one phase at a time. After each phase: read the summary, follow any HUMAN STEP it gives you, run `python tasks.py test`, then commit yourself. Claude Code never runs git commands that change the repo.

Finish by Oct 20 (Oct 21 buffer). Three people work in parallel; phase numbers are unchanged. Day table: PROJECT_BRIEF section 10.
- Lead (data): 0 scaffold → 1 synthetic generator → 2 database → 3 features → 7 public-data adapters → 12 deploy/docs → 13 final review.
- ML teammate: labels, split, metrics, calibration and score on fixtures from the night Phase 0 ends → 4 baseline → 5 calibration/score → 6 LightGBM/SHAP → 8 real-label runs → 11 ablation/fairness/model card.
- Full-stack teammate: 10 dashboard and 9 API against fixtures from the night Phase 0 ends → 9 on the real database → real scores in the dashboard.
Data modes: synthetic_bd (20,000 merchants), kiva_asia, taiwan_cc, homecredit (country not stated; first to cut if time runs short). Backup for Kiva: India L&T vehicle loans.

Stack (PROJECT_BRIEF section 18): React dashboard in `web/`, FastAPI, Supabase Postgres (SQLite for local work and tests), Hostinger VPS.

## Handover points (when a teammate can take over)

Claude Code prints a `HANDOVER POINT` block at the end of these phases (see CLAUDE.md). At each one: run `python tasks.py test`, commit and push yourself, then tell the teammate.

| After phase | What is ready | Who can start, in parallel | Their phases |
|---|---|---|---|
| Phase 0 (scaffold), Oct 12 | Structure, config, adapters interface, tasks.py, API /health, API contract (`src/api/schemas.py`), fixture CSVs and JSON, `web/` placeholder | Both teammates. C (ML): labels, split, metrics, calibration, score on fixture CSVs. D (full-stack): React app and fixture API | Lead: 1, 2, 3, 7. C: model pieces. D: 9, 10 (fixtures first) |
| Phase 1 (generator), Oct 13 | Real synthetic tables through the adapter | C reruns on real synthetic data; rough end-to-end model slice on Oct 14 | C: slice |
| Phase 3 (features + labels), Oct 15 | Feature table and labels for synthetic_bd | C (ML) builds the real model | C: 4, 5, 6, then 8 and 11 |
| Phase 7 (public adapters), Oct 17 | Taiwan, Kiva Asia and Home Credit in the data contract | C runs real-label runs | C: 8 |
| Phase 6 + 9 | Model artifacts and API | D wires the real scores into the dashboard | D: 10 |
| Phase 11 | Everything built | Whole team | 12, 13 |

How a teammate starts (they do this themselves):
1. Clone the private repo (you add them as collaborator first), `git pull` to get your commit.
2. Create their own branch, for example `git checkout -b feat/api` (they run git, not Claude Code).
3. `python tasks.py setup`, then open the repo in VS Code with Claude Code.
4. First message to Claude Code: "Read CLAUDE.md, PROJECT_BRIEF.md and docs/PROMPTS.md. I am role <A/B/C/D>. The last committed phase is <N>. Check the repo matches that, then wait." Then paste their phase.
5. Small pull requests; one teammate reviews; merge only when tests pass.
Rule: two people never work on the same folder at the same time (folders per role are in PROJECT_BRIEF section 11).

## Phase 0: scaffold, STRUCTURE ONLY (paste this first)
```
Read CLAUDE.md, PROJECT_BRIEF.md (especially sections 16 and 17), config/default.yaml and every file in docs/ before doing anything. This is a fresh start: nothing exists yet except this pack.

Follow the GIT RULE and the HUMAN STEP protocol in CLAUDE.md strictly.

Task: initialise the project STRUCTURE ONLY. No data generation, no downloads, no training, no real logic.
1. .gitignore (data/raw/, data/*.db, src/model/artifacts/, .env, __pycache__/, .venv/, reports/*.png, *.zip, *.parquet, web/node_modules/, web/dist/) and .env.example (DATABASE_URL placeholder, no real values).
2. The repository structure in PROJECT_BRIEF section 4, with these adapters in src/adapters/: base.py (abstract DataAdapter: load_merchants, load_purchases, load_deliveries, load_payments, load_loans, load_questionnaire, load_consents, plus audit_frame(); each returns a pandas DataFrame matching the data contract; missing streams return empty frames with the right columns), shopup_synthetic.py, kiva_asia.py, taiwan_cc.py, homecredit.py, shopup_real.py (all stubs), and a factory get_adapter(config) choosing by data.mode.
3. src/features/dictionary.yaml created from docs/FEATURE_DICTIONARY.md.
4. Every module gets a docstring: purpose, owner role (A/B/C/D), and the brief/spec section it implements. Stubs raise NotImplementedError with a clear message.
5. src/config.py: load and validate config/default.yaml (coverage_weights sum to 1.0, data.mode is one of the four, split months positive) and resolve the database URL (the DATABASE_URL environment variable if set, otherwise the SQLite default). Implement this one fully.
6. tasks.py (standard library only) with tasks setup, data, train, api, app, test, lint, backup, and `data --mode <mode>`; thin Makefile wrapper. Unimplemented tasks print "not implemented yet" and exit 0.
7. requirements.txt (pinned minor versions, Python >=3.10): pandas, numpy, faker, sqlalchemy, psycopg2-binary, python-dotenv, scikit-learn, lightgbm, shap, joblib, matplotlib, fastapi, pydantic, uvicorn, pyyaml, pytest, ruff. pyproject.toml for ruff and pytest.
8. tests/: placeholder skipped tests named in the brief, plus one real passing config test. Also src/api/schemas.py (Pydantic response shapes from brief section 8) and tests/fixtures/: tiny hand-made CSVs in the data contract and sample API JSON (queue, profile, score, decisions), so the ML and full-stack teammates can start before real data and a real model exist.
9. src/api/main.py with GET /health (returns the active data mode and the banner text for it); it must boot. web/ holds only a README placeholder for now: the React app is created in Phase 10, so Phase 0 needs no Node.js.
10. README.md (CredLens, tagline "Explainable merchant readiness for lenders"), docs/DATA_SOURCES.md skeleton, .github/workflows/ci.yml (ruff + pytest on pull requests).
Then run setup, lint, test, and boot the API once. If anything needs me (for example a missing tool), give a HUMAN STEP.
Finish with: tree, stub vs implemented, decisions, open questions, files created or changed, and the HANDOVER POINT block. STOP.
```

## Phase 1: synthetic data, synthetic_bd mode (owner: B)
"Implement src/synth/generate.py and src/adapters/shopup_synthetic.py exactly per docs/GENERATOR_SPEC.md (Mokam = purchases, logistics noise, questionnaire excluded from the model) and section 5 of the brief, seeded, reading all numbers from config. Write src/synth/schemas.md (column dictionary). Add tests: row counts, no duplicate merchant_id, foreign keys, thin-file share, date order, repayment share, correlation checks at delivery_signal_strength 0 and 1. Support running at strengths 0, 0.5, 1 via a CLI flag. For the Bangladesh calibration numbers, do not invent values: give me a HUMAN STEP to look them up (Findex Bangladesh, Bangladesh Bank MFS) and use clearly marked placeholders until I reply. Summarise numbers observed and stop."
Done when: `python tasks.py data` works and the generator tests pass.

## Phase 2: database (owner: B)
"Implement src/db/models.py (SQLAlchemy) for merchants, purchases, deliveries, payments, loans, questionnaire, consents, users, decisions (append-only), audit_log, model_versions, and src/db/load.py (CSV to the database at the configured URL: SQLite locally, Supabase Postgres when DATABASE_URL is set; the same code must work on both, and tests use SQLite only). If the Supabase project does not exist yet, give me a HUMAN STEP to create it and put the connection string in .env; never print or commit the string. Make the schema resemble Mifos X concepts (client, loan, repayment schedule, transaction) as far as practical and write src/db/mifos_adapter.py that exports synthetic clients and loans as Mifos X-importable CSV/JSON. Add the `backup` task in tasks.py. Enforce append-only on decisions in code and test it. Summarise and stop."

## Phase 3: features and labels (owner: B + C)
"Implement src/features/build_features.py computing all features in docs/FEATURE_DICTIONARY.md as of each loan's cutoff using strictly earlier data, plus coverage features, and src/features/dictionary.yaml with the Bangla/English sentences. Implement src/model/labels.py per docs/MODEL_SPEC.md section 2. Add test_leakage.py that fails if any feature reads data on or after the cutoff (inject a deliberate leak in a test to prove the test catches it). Summarise and stop."

## Phase 4: baseline model and evaluation (owner: C)
"Implement src/model/split.py (time split 12/3/3 from config), train.py for Logistic Regression, evaluate.py (ROC-AUC, PR-AUC, Brier, calibration data, top-k precision, bootstrap ranges, baselines). Save artifacts with version metadata. Write reports/metrics.json and reports/calibration.png. Warn if AUC exceeds sanity.suspicious_auc. Summarise results honestly and stop."

## Phase 5: calibration, score, coverage, band (owner: C)
"Implement calibrate.py (Platt and isotonic, chosen on validation, fitted on validation only) and score.py (score = round(100 x probability), coverage from config weights, band rules from config, missing delivery data lowers coverage only). Add unit tests with the worked examples in docs/MODEL_SPEC.md. Summarise and stop."

## Phase 6: LightGBM, SHAP, reasons (owner: C)
"Add LightGBM to train.py with validation-based tuning and early stopping; implement model choice per config (prefer simple if gain is small). Implement explain.py: SHAP for trees, coefficient x value for LR, top 3 up and 3 down, dictionary sentences in Bangla and English, remainder grouped so contributions sum to the final score. Add test_reasons.py. Summarise and stop."

## Phase 7: public-data adapters (owner: B + C; runs after Phase 3)
"Read docs/DATASET_PLAN.md sections 2 and 3. Implement src/adapters/taiwan_cc.py, src/adapters/kiva_asia.py and src/adapters/homecredit.py, in that order. Do not download anything yourself. First check data/raw/taiwan_cc/, data/raw/kiva/ and data/raw/homecredit/. If files are missing, STOP and give me a HUMAN STEP for each source: the exact page, whether I need an account, which buttons to click, which files to download, where to save them, and how to tell you I am done. Then wait.
When files exist: inspect the real columns (print headers, dtypes, row counts, value counts of the status/target columns) and show me before mapping. Kiva: filter to Asia-Pacific and Retail/Food/Services; label paid=1, defaulted=0; drop unknown outcomes; split on posted_time. If the Kiva file cannot be downloaded or has no usable default label, stop and tell me; the backup is India L&T vehicle loans (check its licence and columns first). Taiwan: label = 1 − default, payment-behaviour features from the repayment-status, bill and payment columns, stratified random split marked weaker. Home Credit: application_train + installments_payments + POS_CASH_balance, sample per config, label = 1 − TARGET, stratified random split marked weaker, and labelled 'country not stated' everywhere. Never add generated history to real rows. Set the per-mode coverage lists in config from the fields that really exist. Map to the data contract with empty frames for missing streams. Audit-only columns from config in a separate frame. Per-source leakage whitelist with a test. Add new features to dictionary.yaml with EN and BN sentences. Tests with tiny fixture CSVs under tests/fixtures/, never real data. Write docs/DATA_SOURCES.md (link, licence note, what we use, what we drop, limits). Summarise and stop."

## Phase 8: real-label runs (owner: C)
"Run the full pipeline (split, LR and LightGBM, calibration, coverage, bands, SHAP reasons, group audit with bootstrap ranges) with data.mode = taiwan_cc, then kiva_asia, then homecredit. Report AUC, PR-AUC, Brier, top-k with ranges; compare against the 0.70 CGAP benchmark and the 0.95 leakage alarm. Write reports/<mode>/metrics.json and a short honest summary of what this does and does not show. Summarise and stop."

## Phase 9: API (owner: D)
"Implement the FastAPI app per section 8 of the brief with roles (officer/admin/viewer via header token), consent check before scoring, audit entry on every profile read and write, override requires reason, append-only decisions, and /merchants/{id}/score returning score, probability, band, coverage, reasons and model_version. Add test_api.py and test_no_autodecision.py. Summarise and stop."

## Phase 10: dashboard (owner: D)
"Build the React dashboard in web/ (Vite + TypeScript + Tailwind + shadcn/ui, Recharts for charts) per section 9. It calls only the FastAPI API; no database access or keys in the browser. If Node.js is missing, give me a HUMAN STEP to install it. Agree the visual design with me before building all pages. Pages: review queue, merchant detail (timeline, gauge, coverage meter, helps/hurts reasons, 'Why might this be wrong?', decision form), decision log, model card, consent view, audit log (admin), portfolio view, a data-source selector (synthetic_bd / kiva_asia / taiwan_cc / homecredit) and a persistent banner naming the source (the text for the active mode comes from GET /health; see PROJECT_BRIEF section 18) plus 'Decision support only.', the questionnaire as a separate panel beside the score, Show Bangla/English toggle for reasons. Summarise and stop."

## Phase 11: ablation, fairness, model card (owner: C + lead)
"Implement ablation.py (sets A to D at strengths 0, 0.5, 1, regenerating data per strength), fairness.py (group metrics with bootstrap ranges, calibration by group, flag a gap only if ranges do not overlap or it persists across seeds), and model_card.py writing one model card per data mode (docs/model_card_<mode>.md) with the Known limits from docs/DATASET_PLAN.md and the JSON served at /model/card. Add test_zero_signal.py. Include honest captions: results on synthetic data prove nothing about real merchants. Summarise and stop."

## Phase 12: deploy, polish, rehearsal; Mifos X spike optional (owner: B + D)
"Deploy to the Hostinger VPS: Nginx serves the built React app and proxies /api to Uvicorn, HTTPS on, DATABASE_URL set on the server only. Give me HUMAN STEPs for buying the VPS, DNS and logging in. Keep the local run working as the fallback. Only if I say there is time: time-box one day to try running Mifos X Community App in Docker and loading synthetic clients and loans via its API (HUMAN STEP to install Docker first); document exactly what works, or why it does not, and stay with the export adapter. Do not claim an integration that does not exist. Then: README with run instructions, docs/data_inventory.md, docs/starter_kit.md, docs/adapting.md (how another platform would add an adapter), Makefile polish, and a scripted demo path."

## Phase 13: final review (all)
"Act as a sceptical judge. Read the repo, the model card and the slides text. List every claim not supported by code or tests, every place a score could be shown without coverage, any feature that could leak the future, and any wording that overclaims. Propose fixes but do not apply them without asking."

## Tips
- Use plan mode before big phases. Review diffs. Ask Claude Code to explain any file you cannot explain yourself; judges may ask.
- If a phase output looks too good (high AUC), assume leakage until proven otherwise.
- Keep each pull request small; one reviewer minimum.
