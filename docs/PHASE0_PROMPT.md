# PHASE0_PROMPT.md: paste this into Claude Code (structure only)

Before pasting: create a private GitHub repo named CredLens on your laptop, put this whole pack in the repo root (CLAUDE.md, PROJECT_BRIEF.md, config/, docs/), and open that folder in Claude Code.

```
Read CLAUDE.md, PROJECT_BRIEF.md, config/default.yaml and every file in docs/ before doing anything.

GIT RULE (strict): I handle all git operations myself. Do NOT run git init, git add, git commit, git push, git pull, git checkout, git branch, git merge, git rebase, git stash, git reset, or any other git command that changes the repository, its history, branches or remotes. Do not create commits, branches, tags or pull requests, and do not configure git. You may create or edit files such as .gitignore and the CI workflow file, but leave all version control to me. Read-only commands (git status, git diff, git log) are allowed. At the end, list the files you created or changed so I can review and commit them.

The project is called CredLens (tagline: "Explainable merchant readiness for lenders"). Use this name in the README title, the API title and the Streamlit page title.

Task: initialise the project STRUCTURE ONLY. Do not generate data, do not train anything, and do not implement real logic yet. Data work comes later, possibly with real ShopUp data (maybe only loan labels), so keep every data source swappable.

Do this:
1. Create .gitignore (data/raw, data/app.db, src/model/artifacts, .env, __pycache__, .venv, reports/*.png) and .env.example.
2. Create the repository structure from section 4 of PROJECT_BRIEF.md, plus:
   - src/adapters/__init__.py, src/adapters/base.py (an abstract DataAdapter interface: load_merchants, load_orders, load_deliveries, load_payments, load_loans, load_questionnaire, load_consents; each returns a pandas DataFrame matching the data contract in section 5), src/adapters/shopup_synthetic.py (stub), src/adapters/shopup_real.py (stub) and src/adapters/label_only.py (stub for the case where we only get loan outcomes from ShopUp; its docstring must state which features and ablation sets would then be unavailable).
   - src/features/dictionary.yaml created from docs/FEATURE_DICTIONARY.md (names, groups, definitions, EN/BN sentences).
   - Every module gets a docstring stating its purpose, its owner role (A/B/C/D) and the section of PROJECT_BRIEF.md or docs/MODEL_SPEC.md it implements. Function stubs raise NotImplementedError with a clear message.
3. src/config.py: load config/default.yaml with validation (coverage_weights sum to 1.0, split months positive, etc.) and expose a typed object. This one SHOULD be implemented.
4. Environment note: this team uses Windows with Python 3.10.11 (no `make`). Target Python >=3.10 and avoid 3.11-only features. Create tasks.py (standard library only) as the primary cross-platform runner with tasks setup (create .venv and install requirements), data, train, api, app, test, backup, lint, usable as `python tasks.py <task>`. Also add a thin Makefile that calls tasks.py for Mac/Linux. Tasks that depend on unimplemented code print "not implemented yet" and exit 0.
5. requirements.txt (pinned minor versions): pandas, numpy, faker, sqlalchemy, scikit-learn, lightgbm, shap, joblib, fastapi, pydantic, uvicorn, streamlit, plotly, pyyaml, pytest, ruff, pre-commit. Add pyproject.toml settings for ruff and pytest.
6. tests/: create the test files named in PROJECT_BRIEF.md section 4, each with a skipped placeholder test and a reason, plus one real passing test for the config loader.
7. A minimal FastAPI app in src/api/main.py with GET /health only, and a minimal Streamlit page in src/app/streamlit_app.py showing the banner "Synthetic demo data. Decision support only." and the page names as placeholders. Both must start.
8. README.md: project summary, setup, the tasks.py commands (and make equivalents), folder map with owners, links to PROJECT_BRIEF.md and docs/PROMPTS.md.
9. .github/workflows/ci.yml running ruff and pytest on pull requests.

Then run: python tasks.py setup, python tasks.py lint, python tasks.py test, and start the API and the Streamlit app once to confirm they boot.

Finish with a short summary: the tree you created, what is a stub vs implemented, decisions you made, open questions, and the list of files created or changed. STOP and wait for my next instruction.
```
