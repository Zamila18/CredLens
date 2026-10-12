# CLAUDE.md (project instructions for Claude Code)

Project: CredLens, a Merchant Readiness Dashboard, Team 4Bytes (2026 Data, AI & Policy APAC Hackathon, Financial Health Frontiers).

## Read first, in this order
1. `PROJECT_BRIEF.md` (source of truth). Sections 17 and 18 override earlier sections where they conflict; section 18 (team decisions of Oct 12) wins over 17.
2. `docs/DATASET_PLAN.md` (data modes, which public datasets, how to map them, the review fixes).
3. `docs/MODEL_SPEC.md`, `docs/GENERATOR_SPEC.md`, `docs/FEATURE_DICTIONARY.md`.
4. `config/default.yaml` (all tunable numbers; never hard-code them).
5. `docs/WORDING_AND_QA.md` (what we may and may not claim).

## Current stage and data plan
- Fresh start. Work in phases from `docs/PROMPTS.md`, beginning with Phase 0. Stop after each phase.
- Dataset first, build finished by Oct 20 (Oct 21 buffer). Lead track: 0 → 1 → 2 → 3 → 7 → 12 → 13. The ML teammate (labels, 4, 5, 6, 8, 11) and the full-stack teammate (9, 10) start the night Phase 0 ends, working against fixtures. See PROJECT_BRIEF sections 10 and 18.
- Asian context only. Never add generated purchases, deliveries or payments to real public rows. Coverage is per data mode (`coverage_weights_by_mode`).
- The build must stay consistent with the team's Phase 2 submission (summarised in PROJECT_BRIEF section 18). If a change would drift from it, say so before making it.
- Stack: Python for data, model and FastAPI; React + Vite + TypeScript + Tailwind dashboard in `web/`; Supabase PostgreSQL as the shared database with SQLite for local development and tests; Hostinger VPS for hosting.
- ShopUp data was not obtained. Four data modes run through one pipeline: `synthetic_bd` (main demo, 20,000 merchants), and the public real-label checks `kiva_asia`, `taiwan_cc` and `homecredit`. Kiva and Taiwan are Asian sources; Home Credit does not state its country and is always labelled "country not stated". ShopUp can plug in later through `src/adapters/shopup_real.py`.
- Every data source sits behind an adapter in `src/adapters/`. Never hard-wire the pipeline to one source.

## HUMAN STEP protocol (strict)
Some things only the human can do: create accounts, accept dataset terms, download files, look up figures behind a login, install software, make decisions, run git. Whenever progress needs one of these:
1. STOP the current work at a clean point. Do not guess, fake data, scrape, or invent numbers to get around it.
2. Print a block titled `HUMAN STEP NEEDED` with numbered, beginner-friendly steps: the exact URL to open, whether an account or sign-in is needed, what to click, which file(s) to download (exact names), the exact folder to save them in (for example `E:\CredLens\data\raw\kiva\`), how to unzip if needed, how to check it worked (for example a file size or a command to run), and the exact sentence to reply with when done (for example "kiva files ready").
3. Say why it is needed and what you will do next once it is done.
4. If a link may have changed, say so and tell the human what to search for on the site.
5. After the human replies, verify (list the folder, read headers) before continuing.
Also use a HUMAN STEP for: Bangladesh calibration figures (Findex, Bangladesh Bank), Kiva snapshot download (official page or Kaggle mirror, which needs a Kaggle account), Taiwan credit-card file download from UCI, Home Credit download from Kaggle (account and competition-rules acceptance), Node.js installation for the dashboard, creating the Supabase project and putting its connection string in `.env`, buying and setting up the Hostinger VPS, Docker installation if the optional Mifos spike is attempted, the Bangla sentence review by a native speaker, and every commit point.

## HANDOVER POINT protocol
At the end of Phase 0, 1, 3, 7, 6+9 (whichever finishes second) and 11 (see the table in docs/PROMPTS.md), after the phase summary, print a block titled `HANDOVER POINT` with:
1. What is now ready and tested.
2. The exact steps for the human: run `python tasks.py test`, then the git commands to run THEMSELVES (git status, git add, git commit -m "<suggested message>", git push). You only suggest them; never run them.
3. Which teammate role can start now, which phases they take, and which folders they own.
4. The first message the teammate should paste into their own Claude Code.
5. Anything the teammate must download or set up (as HUMAN STEPs).
When a session starts and the human says they are a teammate taking over, check the repo state against the last committed phase before doing anything.

## Non-negotiable rules
- No real partner data. Every screen names its data source ("Synthetic demo data" or "Public data: <source>, not ShopUp data", per data mode as in PROJECT_BRIEF section 18) and says "Decision support only."
- The model outputs a calibrated probability; score = round(100 x probability). Never present a bare 0/1.
- No code path may approve or decline credit. Humans decide; overrides need a written reason; decisions are append-only.
- Features use only data available before each loan's decision date. Split by time where dates exist (Taiwan and Home Credit: stratified random, marked weaker).
- Mokam data = the merchant's wholesale PURCHASES, never sales. No repeat-customer or sales-growth features.
- Group columns (town_tier, shop_type, has_trade_license; Kiva gender/country; Taiwan sex/education/marital status/age band; Home Credit gender/age band/region rating) are audit-only, never model inputs.
- Questionnaire is shown beside the score, not inside the headline model.
- Missing REDX/delivery data lowers coverage, never the score by itself. Low coverage gives "Needs more info", regardless of score. Delivery reasons are neutral observations.
- Raw public data stays in `data/raw/` (gitignored). Never commit or redistribute Findex microdata or Kaggle data. No secrets in the repo.
- The database connection string comes from the `DATABASE_URL` environment variable (`.env`, gitignored). Tests and CI run on SQLite with no network. Only synthetic and public-derived tables go into Supabase; raw public files are never uploaded.
- The React dashboard talks only to the FastAPI API, never to the database. No database keys in frontend code.

## Working style
- Work in phases from `docs/PROMPTS.md`. After each phase: run tests, summarise what exists, list open questions, then STOP and wait.
- GIT (strict): the human team handles ALL git operations (init, add, commit, push, pull, branches, merges, rebases, tags, pull requests, git config). Never run any state-changing git command and never create commits or branches. Read-only commands (git status, git diff, git log) are fine. After each phase, list the files you created or changed so the team can review and commit them.
- Do not rewrite files owned by another role without saying so.
- Fixed random seeds everywhere (default 42). Same command, same result.
- Prefer plain, readable code with docstrings. Teammates must be able to explain every file to judges.
- Anything uncertain (library versions, Mifos X API details): say so, check, and do not invent.

## Environment
- The team uses Windows laptops with Python 3.10.11 and Git 2.50. Target Python 3.10 or newer (set requires-python ">=3.10"); do not use 3.11-only features (for example tomllib, ExceptionGroup, typing.Self, `except*`).
- `make` is NOT installed on Windows. The primary runner is a cross-platform `tasks.py` (standard library only; `python tasks.py <task>`). Keep a Makefile as a thin wrapper that calls it, for Mac/Linux users.
- Use a virtual environment (`.venv`) created by `python tasks.py setup`. Use pathlib and forward-slash-safe paths; avoid shell-specific commands. Test on Windows semantics (no bash-only syntax).

## Commands (implement in tasks.py; Makefile wraps them)
- `setup` create .venv and install dependencies
- `data` generate synthetic data and load the DB
- `train` build features, train, calibrate, evaluate, write reports and model card
- `api` run FastAPI on :8000
- `app` run the React dashboard dev server (Vite, :5173); needs Node.js
- `test` run pytest
- `lint` run ruff
- `backup` copy the SQLite file with a timestamp, or export the tables when the database is Postgres

## Definition of done
See section 12 of `PROJECT_BRIEF.md` and `docs/ACCEPTANCE_CHECKLIST.md`.
