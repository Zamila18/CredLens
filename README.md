# CredLens

**Explainable merchant readiness for lenders.**

CredLens is a staff-facing dashboard that helps a credit officer assess a small merchant who is new to credit. It brings the merchant's wholesale purchases, parcel deliveries and repayment history into one view, shows a readiness score with plain-language reasons, and records the officer's decision.

> **Synthetic and public data only. Decision support only.**
> The score is advice. An officer decides, and every decision is logged. No part of this system approves or declines credit.

Built by Team 4Bytes (Ahsanullah University of Science and Technology) for the 2026 Data, AI & Policy APAC Hackathon: Financial Health Frontiers. It is a prototype to demonstrate and defend, not a production system.

## Status

**Phase 0 (scaffold) is done. Nothing is trained and no data is generated yet.**

| Works now | Not built yet |
|---|---|
| Project structure, config loading and checks | Synthetic data generator (Phase 1) |
| Data contract and adapter interface | Database (Phase 2), features (Phase 3) |
| Feature dictionary with English and Bangla sentences | Model, calibration, reasons (Phases 4 to 6) |
| API contract, sample responses, `GET /health` | Public-data adapters (Phase 7), real-label runs (Phase 8) |
| Lint, tests and CI | API endpoints (Phase 9), React dashboard (Phase 10) |

The plan, phase by phase, is in [docs/PROMPTS.md](docs/PROMPTS.md). The full brief is [PROJECT_BRIEF.md](PROJECT_BRIEF.md); section 18 holds the latest decisions.

## What the officer will see

1. One view of the merchant's purchases (Mokam-style: what the shop buys), deliveries (REDX-style) and payments (Baki-style).
2. A readiness score from 0 to 100. It is a calibrated repayment probability times 100, never a bare yes or no.
3. Three reasons that raise the score and three that lower it, in English and Bangla.
4. A separate coverage percentage: how much history the score rests on. Low coverage gives the band "Needs more info", whatever the score.
5. Accept, override or needs-more-info buttons. An override needs a written reason.

## Data

No partner data is used. Every screen names its data source.

| Data mode | Source | What it is for |
|---|---|---|
| `synthetic_bd` | Generated, calibrated to public Bangladesh figures | The main demo, with every data stream |
| `kiva_asia` | Kiva loans, filtered to Asia | Checks the method on real Asian small-business outcomes |
| `taiwan_cc` | UCI Taiwan credit-card default data | Checks the method on real Asian payment behaviour |
| `homecredit` | Kaggle Home Credit (country not stated) | Checks the method at larger scale |

Results on synthetic data show that the pipeline is sound. They say nothing about real merchants. The public datasets test the method; none of them is ShopUp data. Sources and licences: [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

## Run it

You need Python 3.10 or newer. On Windows, use `python`; on Mac or Linux, `python3` (or `make <task>`).

```
python tasks.py setup     # create .venv and install dependencies
python tasks.py test      # run the tests
python tasks.py lint      # run ruff
python tasks.py api       # start the API, then open http://localhost:8000/docs
```

`data`, `train`, `app` and `backup` exist as commands and say "not implemented yet" until their phase.

To use a shared database, copy `.env.example` to `.env` and fill in `DATABASE_URL`. Without it, a local SQLite file is used. Never commit `.env`.

## Layout

```
config/default.yaml   every tunable number
src/config.py         loads and checks the config
src/adapters/         one adapter per data source, all returning the same seven tables
src/synth/            synthetic data generator
src/db/               database tables, loading, Mifos X-style export
src/features/         feature builder and the reason-sentence dictionary
src/model/            labels, split, training, calibration, score, reasons, evaluation
src/api/              FastAPI app; schemas.py is the API contract
web/                  React dashboard (Phase 10)
tests/                tests; tests/fixtures/ holds tiny hand-made sample files
docs/                 specifications, data plan, wording rules, checklist
```

## Rules this project keeps

- The model outputs a calibrated probability. The 0/1 values are training labels only.
- Features use only data from before each loan's decision date. Splits are by time where dates exist.
- Town tier, shop type, licence status and similar group columns are used to audit results, never as model inputs.
- Missing delivery data lowers coverage, never the score by itself.
- The questionnaire is shown beside the score, not inside it.
- Scoring is refused without a valid consent record.
- No real merchant data and no secrets in the repository.
