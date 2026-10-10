# CLAUDE.md (project instructions for Claude Code)

Project: CredLens, a Merchant Readiness Dashboard, Team 4Bytes (2026 Data, AI & Policy APAC Hackathon, Financial Health Frontiers).

## Read first, in this order
1. `PROJECT_BRIEF.md` (scope, stack, structure, data contract, rules). It is the source of truth.
2. `docs/MODEL_SPEC.md` (how the model must work, step by step, with worked examples).
3. `docs/GENERATOR_SPEC.md` (how the synthetic data must be built, including the negative control).
4. `docs/FEATURE_DICTIONARY.md` (every feature, its meaning and its Bangla/English reason sentence).
5. `config/default.yaml` (all tunable numbers; never hard-code them).
6. `docs/WORDING_AND_QA.md` (what we may and may not claim).

## Current stage and data plan
- Right now: set up the project STRUCTURE only (see Phase 0 in docs/PROMPTS.md). No data generation, no training, no real logic yet.
- Data work comes later. We will try to get something from ShopUp (possibly only loan outcome labels). Until the team says otherwise, the default plan is synthetic data.
- Therefore every data source must be swappable behind an adapter (`src/adapters/`): synthetic, real, or label-only. Never hard-wire the pipeline to one source.
- If real or label-only data is used, follow docs/REAL_DATA_SWITCH.md and keep real data outside the repo.

## Non-negotiable rules
- Synthetic data only. Show "Synthetic demo data. Decision support only." on every screen.
- The model outputs a calibrated probability; score = round(100 x probability). Never present a bare 0/1.
- No code path may approve or decline credit. Humans decide; overrides need a written reason; decisions are append-only.
- Features use only data before each loan's cutoff date. Split by time, never at random.
- town_tier, shop_type, has_trade_license are audit columns, not model features.
- Missing REDX/delivery data lowers coverage, never the score by itself.
- Low coverage gives band "Needs more info", regardless of score.
- No secrets in the repo. No real merchant data anywhere.

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
