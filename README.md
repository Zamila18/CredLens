# CredLens

**Explainable merchant readiness for lenders.**

CredLens is a staff-facing dashboard that helps a credit officer assess a small merchant who is new to credit. It brings the merchant's wholesale purchases, parcel deliveries and repayment history into one view, shows a readiness score with plain-language reasons, and records the officer's decision.

> **Synthetic and public data only. Decision support only.**
> The score is advice. An officer decides, and every decision is logged. No part of this system approves or declines credit.

Built by Team 4Bytes (Ahsanullah University of Science and Technology) for the 2026 Data, AI & Policy APAC Hackathon: Financial Health Frontiers. It is a prototype to demonstrate and defend, not a production system.

## Status

**Phases 0 to 8 are done (Oct 14, 2026): scaffold, synthetic data, database, features and labels, two models with a rule for choosing between them, calibration, score, coverage and bands, the reasons behind a score, adapters for four public data sources, and training runs on all of them. The API endpoints and the dashboard are being built now.**

| Works now | Not built yet |
|---|---|
| Project structure, config loading and checks | |
| Data contract and adapter interface; adapters and features for all four public sources (Taiwan, India, Home Credit, Kiva) | |
| Synthetic data generator: 20,000 merchants, three delivery signal strengths | API endpoints for the queue, profile, score, decisions and audit (Phase 9) |
| Database (SQLite locally): tables, loader, backup; append-only decisions and audit log | React dashboard (Phase 10) |
| Mifos X: the export was loaded into a running Mifos X (Apache Fineract in Docker): 50 merchants, 85 loans, 73 repayments, nothing refused, loan statuses matched for all 85 ([tools/mifos/](tools/mifos/README.md)) | |
| Features built only from data before each loan, labels from the 30-day rule, and a leakage guard | Ablation, group audit, model cards, final check on the held-back test months (Phase 11) |
| Logistic regression and LightGBM, trained on 12 months and measured on the next 3; the simple model stays unless the other is clearly better | Supabase database and hosting (Phase 12) |
| Calibration check; score, coverage, band and low-score warning | |
| Reasons: three up and three down, in English and Bangla, with numbers that add up to the score (exact SHAP values) | |
| Scoring service for the API: review queue and score card, nothing scored without consent | |
| Training runs on all five data modes, with an honest reading of each: [reports/REAL_LABEL_RESULTS.md](reports/REAL_LABEL_RESULTS.md) | |
| API contract, sample responses, `GET /health` | |
| Ablation A to D with the negative control ([reports/ablation/](reports/ablation/ABLATION.md)); PostgreSQL path checked | |
| Group audit on every data mode, with a planted-gap test ([reports/FAIRNESS.md](reports/FAIRNESS.md)) | |
| One model card per data mode ([docs/model_card_synthetic_bd.md](docs/model_card_synthetic_bd.md) and the others), served by `GET /model/card` | |
| Lint, 761 tests and CI | |

### Where the model stands (synthetic data, validation months, seed 42)

| Measure | Value |
|---|---|
| Model in use | Logistic regression on 10 behaviour inputs |
| AUC | 0.710 (95% range 0.688 to 0.729); purchases only 0.667; a coin toss 0.500 |
| LightGBM, for comparison | 0.722 (0.701 to 0.742); gain +0.013 (+0.003 to +0.021), not enough to replace the simple model |
| First loans / repeat loans | 0.665 / 0.770 |
| Calibration error | 0.012 (no correction needed) |
| Bands | Strong 56% of loans (95.2% repaid), Review 29% (82.1%), Needs more info 15% (88.3%) |

These numbers show that the pipeline works on generated data. They are not a claim about real merchants, and the last three months of data have not been looked at yet. Say "around 0.70", not "above 0.70". Details and limits: [PROJECT_BRIEF.md](PROJECT_BRIEF.md) section 18, items 23 to 28.

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
| `kiva_asia` | Kiva loans to shops in Asia, 2009 to 2013 (2016 archive: 65,304 loans, 2,512 defaulted; no Bangladesh loans) | Real Asian small-business outcomes, but with no borrower behaviour to score: it shows the limits, not the method |
| `taiwan_cc` | UCI Taiwan credit-card default data | Checks the method on real Asian payment behaviour |
| `india_ltfs` | India L&T vehicle loans (Kaggle) | Checks the method on real Indian borrowers, half of them with no credit record |
| `homecredit` | Kaggle Home Credit (country not stated) | Checks the method at larger scale |

`synthetic_bd` runs end to end today; All five modes train with the same code (`python tasks.py train --all-modes`). Validation AUC on the public sources: Taiwan 0.743, India 0.611, Home Credit 0.746 (0.601 without its outside score), Kiva 0.644. Only Taiwan is evidence that the method works; the others show where it cannot, and why. See [reports/REAL_LABEL_RESULTS.md](reports/REAL_LABEL_RESULTS.md). Results on synthetic data show that the pipeline is sound. They say nothing about real merchants. The public datasets test the method; none of them is ShopUp data. Sources and licences: [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

## Run it

You need Python 3.10 or newer. On Windows, use `python`; on Mac or Linux, `python3` (or `make <task>`).

```
python tasks.py setup     # create .venv and install dependencies
python tasks.py test      # run the tests
python tasks.py lint      # run ruff
python tasks.py data      # generate the synthetic data and load the local database (about 55 seconds)
python tasks.py train     # train both models, choose one, measure it on the validation period, save it (about 1 minute)
python tasks.py train --mode taiwan_cc   # the same for a public data mode (needs its raw file in data/raw/)
python tasks.py train --all-modes        # all five modes, about 4 minutes
python -m src.model.scoring   # print one real score card with its reasons (needs data and train first)
python tasks.py backup    # copy the database with a timestamp
python tasks.py api       # start the API, then open http://localhost:8000/docs
```

`python tasks.py data --all-strengths` generates all three delivery signal strengths. `python tasks.py data --reset-db` wipes the database first, including recorded decisions. `app` exists as a command and says "not implemented yet" until Phase 10.

To use a shared database, copy `.env.example` to `.env` and fill in `DATABASE_URL`. Without it, a local SQLite file is used. Never commit `.env`.

## Layout

```
config/default.yaml   every tunable number
src/config.py         loads and checks the config
src/adapters/         one adapter per data source, all returning the same seven tables
src/synth/            synthetic data generator
src/db/               database tables, loading, Mifos X export and loader
src/features/         feature builder and the reason-sentence dictionary
src/model/            labels, split, training, calibration, score, reasons, evaluation;
                      scoring.py is what the API calls for the queue and a score card
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
- Scoring is refused without a valid consent record, and merchants without one are never used for training.
- A reason is shown only when its sentence is true for the merchant, and the parts always add up to the score.
- The simpler model stays in use unless the more complex one is clearly better.
- No real merchant data and no secrets in the repository.
