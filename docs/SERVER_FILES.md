# What the server needs, and how the files get there

Owner role: D (full-stack). Written for Phase 12; `docs/DEPLOY.md` uses it.
Checked by a command: `python -m src.api.preflight --server` (see the end of this page).

## The short version

The hosted site runs the **synthetic data mode only** (`synthetic_bd`). That is the demo.
The four public data modes (Taiwan, India, Home Credit, Kiva) need raw files that may never leave
the lead's laptop, so the server never scores them. The dashboard still shows their **model
cards** (totals and plain words, no rows), and those cards are in git.

## The files, one by one

| What | Where | How it gets to the server | Size |
|---|---|---|---|
| The code, the config, `dictionary.yaml` | the repository | `git clone` | small |
| The built dashboard | `web/dist/` | built on the server (`npm ci`, `npm run build`) or built on a laptop and copied | a few MB |
| The model cards of all five modes (`reports/<mode>/model_card.json`) | the repository | `git clone` (they are committed) | small |
| The generated tables | `data/raw/synthetic_bd/strength_0.5/` (7 CSV files) | **`python tasks.py data`** on the server. The generator is seeded, so the server gets exactly the lead's data (Humayra's laptop and the lead's laptop gave the same queue: 2,197 Strong, 1,170 Review, 611 Needs more info, 200 without consent) | about 190 MB |
| The database | `data/app.db` (SQLite) | made by the same `python tasks.py data` | about 330 MB |
| **The trained model** | `src/model/artifacts/synthetic_bd/` (`model.joblib`, `metadata.json`) | **copied from the lead's laptop** (`scp`, see below). Not in git, and not trained on the server | 5 KB |
| The secrets file | `.env` on the server only | written by hand from `deploy/env.template` (made in the deploy step) | tiny |

### Why the model is copied and not trained on the server

The model card, the test-month results (`reports/synthetic_bd/test_results.json`) and the audit all
describe **one** trained model, named by its version, for example `synthetic_bd-20261015-005409-9db9d66`.
`python tasks.py train` makes a new version every time it runs (the time is part of the name), and the test
months may be looked at only once per model. A model trained on the server would be a different version
from the one in the card, and the dashboard would warn that the card describes an older model. So the lead
trains once, writes the card, and copies the two small model files. Training on the laptop is fine for
development; just do not commit the changed `reports/` files.

Copy command (from the lead's laptop, in the project folder; the guide gives the full steps):

    scp src/model/artifacts/synthetic_bd/model.joblib src/model/artifacts/synthetic_bd/metadata.json USER@SERVER:/opt/credlens/src/model/artifacts/synthetic_bd/

## What must NOT be on the server

- **Raw public data**: `data/raw/taiwan_cc/`, `data/raw/india_ltfs/`, `data/raw/homecredit/`,
  `data/raw/kiva/`. Never copied, never uploaded (the sources' terms; CLAUDE.md).
- **Home Credit rows** are never shown anywhere. In that mode the API refuses queue, profile, score,
  decision and questionnaire calls (`rows_not_shown`); only its model card (totals) is served.
- **`_latent_truth.csv`** (the generator's hidden truth, for the generator's tests only). Delete it after
  `python tasks.py data`.
- **Secrets in git**: `.env` is gitignored. Only `deploy/env.template`, with no real values, is committed.

## What each data mode needs at start-up

| Data mode | Can the server run the API in this mode? | What the dashboard shows for it |
|---|---|---|
| `synthetic_bd` | **Yes**: tables + database + model (above) | everything: queue, merchants, decisions, consent, audit, import, model card |
| `taiwan_cc`, `india_ltfs`, `kiva_asia` | No (needs the raw file) | the model card tab only (`GET /model/card?mode=<mode>`, from `reports/<mode>/model_card.json`) |
| `homecredit` | No, and its rows are never shown | the model card tab only (totals) |

The API's own mode is `data.mode` in `config/default.yaml`, or the environment variable
`CREDLENS_DATA_MODE`. On the server it must be `synthetic_bd`.

## What happens at start-up, and what happens when something is missing

The API starts, builds the scorer (about 30 seconds: the port does not answer until it has finished) and
then serves. If the tables or the model are missing it **still starts** so `/health` works, and every
endpoint that needs them answers `503` with the command to run. So a wrong server shows up as a `503`
message, not as a crash. The preflight check finds it earlier:

    python -m src.api.preflight --server

It prints `OK`, `WARN` or `FAIL` for each need, never prints the database address, and exits with 1 when
anything fails. Run it after setting the server up and before every demo. It checks that:

1. the API runs the synthetic data (not a public mode);
2. the seven generated tables are there;
3. the database exists, has the four demo users, and holds the same merchants as the tables;
4. the trained model is there;
5. the model card was written for that very model (on the server a mismatch is a FAIL);
6. every data mode has a model card;
7. (server only) no raw public file is on the machine, and the hidden-truth file is gone.

## The database

The demo runs on **SQLite** (`data/app.db`). It needs no account and no network, and it is the same
database the laptop fallback uses. Decisions and audit entries are append-only in it (the application and
database triggers both refuse an update or a delete). `python tasks.py backup` copies the file with a
timestamp; do it before and after the demo.

The shared online database (Supabase) was **not** set up: Humayra chose to stay on SQLite on Oct 16. The
lead must confirm this, because the project brief and CLAUDE.md name Supabase. So the PostgreSQL triggers
(`decisions` and `audit_log` refusing UPDATE, DELETE and TRUNCATE) stay as untested as they were; only
the SQLite ones are covered by tests. Say that, not more, if a judge asks.
