# CLAUDE.md (project instructions for Claude Code)

Project: CredLens, a Merchant Readiness Dashboard, Team 4Bytes (2026 Data, AI & Policy APAC Hackathon, Financial Health Frontiers).

## Read first, in this order
1. `PROJECT_BRIEF.md` (source of truth). Section 17 overrides earlier sections where they conflict.
2. `docs/DATASET_PLAN.md` (data modes, which public datasets, how to map them, the review fixes).
3. `docs/MODEL_SPEC.md`, `docs/GENERATOR_SPEC.md`, `docs/FEATURE_DICTIONARY.md`.
4. `config/default.yaml` (all tunable numbers; never hard-code them).
5. `docs/WORDING_AND_QA.md` (what we may and may not claim).

## Current stage and data plan
- Fresh start. Work in phases from `docs/PROMPTS.md`, beginning with Phase 0. Stop after each phase.
- ShopUp data was not obtained. Three data modes run through one pipeline: `synthetic_bd` (main demo), `kiva_asia` and `homecredit` (public real-label checks). ShopUp can plug in later through `src/adapters/shopup_real.py`.
- Every data source sits behind an adapter in `src/adapters/`. Never hard-wire the pipeline to one source.

## HUMAN STEP protocol (strict)
Some things only the human can do: create accounts, accept dataset terms, download files, look up figures behind a login, install software, make decisions, run git. Whenever progress needs one of these:
1. STOP the current work at a clean point. Do not guess, fake data, scrape, or invent numbers to get around it.
2. Print a block titled `HUMAN STEP NEEDED` with numbered, beginner-friendly steps: the exact URL to open, whether an account or sign-in is needed, what to click, which file(s) to download (exact names), the exact folder to save them in (for example `E:\CredLens\data\raw\kiva\`), how to unzip if needed, how to check it worked (for example a file size or a command to run), and the exact sentence to reply with when done (for example "kiva files ready").
3. Say why it is needed and what you will do next once it is done.
4. If a link may have changed, say so and tell the human what to search for on the site.
5. After the human replies, verify (list the folder, read headers) before continuing.
Also use a HUMAN STEP for: Bangladesh calibration figures (Findex, Bangladesh Bank), Kaggle account and competition-rules acceptance, Kiva snapshot download, Docker installation for the Mifos spike, the Bangla sentence review by a native speaker, and every commit point.

## HANDOVER POINT protocol
At the end of Phase 0, 3, 7, 6+9 (whichever finishes second) and 11 (see the table in docs/PROMPTS.md), after the phase summary, print a block titled `HANDOVER POINT` with:
1. What is now ready and tested.
2. The exact steps for the human: run `python tasks.py test`, then the git commands to run THEMSELVES (git status, git add, git commit -m "<suggested message>", git push). You only suggest them; never run them.
3. Which teammate role can start now, which phases they take, and which folders they own.
4. The first message the teammate should paste into their own Claude Code.
5. Anything the teammate must download or set up (as HUMAN STEPs).
When a session starts and the human says they are a teammate taking over, check the repo state against the last committed phase before doing anything.

## Non-negotiable rules
- No real partner data. Every screen names its data source ("Synthetic demo data" or "Public data: Kiva / Home Credit, not ShopUp data") and says "Decision support only."
- The model outputs a calibrated probability; score = round(100 x probability). Never present a bare 0/1.
- No code path may approve or decline credit. Humans decide; overrides need a written reason; decisions are append-only.
- Features use only data available before each loan's decision date. Split by time where dates exist (Home Credit: stratified random, marked weaker).
- Mokam data = the merchant's wholesale PURCHASES, never sales. No repeat-customer or sales-growth features.
- Group columns (town_tier, shop_type, has_trade_license; Kiva gender/country; Home Credit gender/age band/region rating) are audit-only, never model inputs.
- Questionnaire is shown beside the score, not inside the headline model.
- Missing REDX/delivery data lowers coverage, never the score by itself. Low coverage gives "Needs more info", regardless of score. Delivery reasons are neutral observations.
- Raw public data stays in `data/raw/` (gitignored). Never commit or redistribute Findex microdata or Kaggle data. No secrets in the repo.

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
- `app` run Streamlit on :8501
- `test` run pytest
- `lint` run ruff
- `backup` copy the SQLite file with a timestamp

## Definition of done
See section 12 of `PROJECT_BRIEF.md` and `docs/ACCEPTANCE_CHECKLIST.md`.
