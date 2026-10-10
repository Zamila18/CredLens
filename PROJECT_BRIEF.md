# PROJECT_BRIEF.md: CredLens, a Merchant Readiness Dashboard (Team 4Bytes)

Read this file fully before generating any code. It is the single source of truth for scope, stack, structure and rules.

## 1. What this is

An internal, staff-facing decision-support dashboard for a B2B commerce and credit company (modelled on ShopUp, Dhaka: Mokam = wholesale sourcing, REDX = last-mile logistics, Baki = embedded working-capital credit).

A credit officer opens a new merchant's profile and sees:
1. A unified view of the merchant's order data, delivery (REDX-style) outcomes and payment (Baki-style) history.
2. A **readiness score** (0-100) from an explainable ML model. The model outputs a calibrated repayment *probability* (for example 0.72), never a bare 0 or 1; score = round(100 x probability). The 0/1 values exist only as training labels.
3. **Plain-language reasons** for the score (top positive and negative factors).
4. A **data-coverage indicator** (how much history the score is based on).
5. Buttons for the officer to **accept / override** and record a reason. The system never approves or declines credit by itself.

Competition: 2026 Data, AI & Policy APAC Hackathon (Financial Health Frontiers). Finals Nov 4-6, 2026, Manila. This is a prototype to demo and defend, not a production system.

## 2. Hard rules (do not violate)

1. **Synthetic data only.** No real ShopUp data exists in this project. A generator creates all data. Label every screen "Synthetic demo data".
2. **Human in the loop.** The score is advice. No code path may auto-approve or auto-decline. Every decision is a staff action that is logged.
3. **Hypothesis, not fact.** "REDX delivery reliability helps predict Baki repayment" is an unproven hypothesis. The synthetic data may encode it, so the model comparison must include an ablation (with vs without delivery features) and the UI/README must say that results on synthetic data prove nothing about real merchants.
4. **Explainability is required.** Every score ships with reasons derived from model attributions (SHAP or coefficients) mapped to plain sentences.
5. **Privacy by design.** Data minimisation, role-based access, audit log, and a consent flag on each merchant record (merchants with consent=false are excluded from scoring).
6. No secrets in the repo. Use `.env.example`.

## 3. Recommended stack (keep it boring and fast to build)

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.10 or newer (team machines have 3.10.11; do not use 3.11-only features) | Team knows it, best ML libs |
| Data generation / ETL | pandas, numpy, Faker | Simple |
| Database | SQLite via SQLAlchemy (swap-able to PostgreSQL) | Zero setup |
| ML | scikit-learn (LogisticRegression), LightGBM or sklearn HistGradientBoosting, SHAP, joblib | Interpretable baseline plus stronger model |
| API | FastAPI + Pydantic + Uvicorn | Typed, auto docs at /docs |
| Dashboard | Streamlit (fastest) OR React + Vite + Tailwind if a member prefers | Decide in week 1, default Streamlit |
| Charts | Plotly | Works in Streamlit and React |
| Auth (demo) | Simple role switch (officer / admin / viewer) with a header token | Shows role-based access without OAuth effort |
| Tests | pytest | |
| Tooling | Docker Compose (optional), Makefile, ruff, pre-commit | |
| Mifos X (open-source core banking) | Data-model alignment and export adapter (option A); optional Docker integration (option B). See section 13 | Submission promised a Mifos X prototype |

## 4. Repository structure

```
credlens/
  README.md
  PROJECT_BRIEF.md
  tasks.py                  # cross-platform runner: python tasks.py data | train | api | app | test | lint | backup | setup
  Makefile                  # thin wrapper for Mac/Linux: make data | train | api | app | test
  pyproject.toml / requirements.txt
  .env.example
  docker-compose.yml        # optional
  data/
    raw/                    # generated CSVs (gitignored)
    app.db                  # SQLite (gitignored)
  src/
    config.py
    adapters/
      base.py               # abstract DataAdapter (swappable data sources)
      shopup_synthetic.py
      shopup_real.py        # stub until/unless ShopUp shares data
      label_only.py         # stub for loan-outcome labels only
    synth/
      generate.py           # builds merchants, orders, deliveries, payments, outcomes
      schemas.md            # column dictionary
    db/
      models.py             # SQLAlchemy tables
      load.py               # CSV -> DB
    features/
      build_features.py     # per-merchant features as of a cutoff date
    model/
      train.py              # temporal split, LR vs GBM, ablation, saves artifacts
      evaluate.py           # AUC, calibration, segment checks -> reports/
      explain.py            # SHAP -> reason codes -> plain sentences
      artifacts/            # model.joblib, metadata.json (gitignored)
    api/
      main.py               # FastAPI app
      routes_merchants.py
      routes_decisions.py
      auth.py
    app/
      streamlit_app.py      # pages: Queue, Merchant detail, Decision log, Model card
  reports/
    metrics.json
    calibration.png
    ablation.png
    fairness_by_segment.csv
  tests/
    test_synth.py test_features.py test_api.py test_no_autodecision.py
    test_leakage.py         # no feature uses data after the loan cutoff
    test_master_data.py     # unique merchant ids, every foreign key resolves
    test_zero_signal.py     # at delivery_signal_strength=0, delivery features add no meaningful AUC
    test_reasons.py         # 3 up + 3 down reasons, each mapped to a dictionary sentence
  docs/
    architecture.png        # the flow diagram
    model_card.md
    data_governance.md
```

## 5. Data contract (synthetic)

All ids are strings. Dates are ISO. Generate roughly 5,000 merchants over 18 months.

**merchants**: merchant_id, onboarded_at, district, town_tier (metro / city / small_town), shop_type (grocery, pharmacy, apparel, electronics, other), has_trade_license (bool), consent_data_use (bool, ~95% true), questionnaire_done (bool, ~40% true).

**orders** (Mokam-style): order_id, merchant_id, order_date, amount_bdt, category.

**deliveries** (REDX-style): delivery_id, merchant_id, order_id (nullable), dispatched_at, delivered_at (nullable), status (delivered / returned / failed / cancelled), is_cod (bool), cod_remitted_on_time (bool, nullable).

**payments** (Baki-style): payment_id, merchant_id, loan_id, due_date, paid_date (nullable), amount_due_bdt, amount_paid_bdt.

**loans**: loan_id, merchant_id, issued_at, limit_bdt, outcome_label (1 = repaid fine, 0 = 30+ days late or default), label_observed_at.

**questionnaire** (optional, FinHealth-style Core + Context, 10 items, 1-5 scale): merchant_id, spend1, spend2, save1, save2, borrow1, borrow2, plan1, plan2, stress, confidence, answered_at. Four subscores (Spend, Save, Borrow, Plan) plus two context items. Treated as a directional signal only, never as the sole driver of a score. Item wording must be adapted from the public FinHealth Score toolkit (check its terms of use) and translated into Bangla with care.

**consents**: consent_id, merchant_id, purpose, data_categories, granted_at, expires_at, revoked_at. Scoring is refused when there is no valid, unexpired, unrevoked consent.

**decisions** (written by the app): decision_id, merchant_id, officer_id, model_version, score_shown, officer_action (accept / override_up / override_down / needs_more_info), reason_text, decided_at.

**audit_log**: id, actor, role, action, merchant_id, timestamp.

### Generator requirements
- Seeded and reproducible (`--seed 42`).
- Latent merchant "reliability" variable drives all signals with noise, so signals are correlated but imperfect.
- Include **thin-file merchants** (few orders in first 30 days; 30-40% of new merchants) because that is the problem being solved.
- Include missingness (some merchants have no deliveries yet) so the coverage indicator is meaningful.
- Add a config switch `delivery_signal_strength` with three settings: 0 (delivery data is pure noise, the negative control), 0.5 (weak) and 1 (strong). Run the ablation at all three, so the team can show honestly that the benefit depends on the assumption. At 0, delivery features must add no meaningful gain; if they do, there is a bug or leakage.
- Add seasonality (Eid and monsoon dips) to orders.

## 6. Features (computed as of a cutoff date, using only data before it)

- Orders: count and total amount in first 14/30 days, order-value volatility, category diversity, weeks active.
- Deliveries: delivered rate, return rate, failed rate, median dispatch-to-delivery hours, COD remittance on-time rate.
- Payments (for repeat borrowers): on-time rate, average days late, utilisation.
- Context: town_tier, shop_type and has_trade_license are **audit columns only**. They are used for the segment/fairness checks and are NOT model features (avoids direct bias). Revisit only if the team decides otherwise and documents why in the model card.
- Questionnaire summary score (nullable).
- **Coverage features**: days of history, number of orders, number of deliveries, share of feature groups available.

Avoid leakage: build features strictly from events before the cutoff; labels come from after.

## 7. Modelling spec

0. **Labels**: 1 = repaid within 30 days of the due date, 0 = more than 30 days late or default. Exclude loans with fewer than 60 days of history (outcome unknown). The 30 and 60 day values are config settings.
1. **Split by time** on loan issue date: train on the first 12 months, validate on the next 3, test on the last 3 (all configurable). Never random split. Fit the calibrator on validation only; touch test once. A test must fail the build if any feature uses data after the loan's cutoff date.
2. **Models**: (a) regularised logistic regression (interpretable baseline), (b) gradient-boosted trees. Choose on validation by AUC, Brier and calibration; if the GBM gain is small, keep the logistic regression. Report both in the model card. Fixed random seeds.
3. **Feature-set ablation**: A orders-only, B +payments, C +deliveries, D +questionnaire, repeated at `delivery_signal_strength` 0, 0.5 and 1. Keep a feature group only if its gain beats the bootstrap range and does not worsen group gaps.
4. **Metrics**: ROC-AUC, PR-AUC, Brier score, calibration curve; precision at top-k and reviewable-share at a chosen threshold. Report bootstrap ranges. Baselines to beat: always predicting the average repayment rate, and the orders-only model. Treat AUC above 0.95 on synthetic data as a leakage warning.
5. **Segment checks**: metrics, calibration and band shares by town_tier, shop_type, has_trade_license (audit columns, not features). Flag gaps over 5 points for discussion in the model card. Do not claim "fair"; report what was measured.
6. **Score**: calibrated probability of good repayment x 100, rounded; bands (Strong / Review / Needs more info). The "Needs more info" band is chosen by low coverage, not low score. Coverage is a separate 0-100% number: a weighted checklist (history length, orders present, payments present, deliveries present, questionnaire done, recent activity) with weights in config. Missing REDX/delivery data lowers coverage; it must never lower the score by itself. Band lines (for example Strong at 70+, minimum coverage 60%) live in config, not code.
7. **Reasons**: top 3 positive and top 3 negative contributors (SHAP for GBM, coefficient x value for LR), mapped through a dictionary to sentences such as "Delivered 94% of recent REDX parcels (above typical)" or "Only 6 days of history, so confidence is low".
8. Save `model.joblib` and `metadata.json` (version id, code commit, data seed, train window, metrics, feature list, calibrator). Every score and every decision records the model version that produced it.
9. Dictionary sentences exist in Bangla and English, worded as observations ("returns are higher than similar shops"), not as accusations or causes.

## 8. API (FastAPI)

- `GET /health`
- `GET /merchants?status=pending&band=&town_tier=` : review queue
- `GET /merchants/{id}` : profile with merged orders / deliveries / payments summaries
- `GET /merchants/{id}/score` : `{score, probability, band, coverage, reasons_positive[], reasons_negative[], model_version}` (exactly 3 positive and 3 negative reasons when available)
- `POST /merchants/{id}/decision` : body `{officer_action, reason_text}` (reason required when action is override)
- `GET /decisions?merchant_id=` : decision history
- `GET /model/card` : metrics, ablation, limitations
- `GET /audit` (admin only)

Roles: officer (queue, score, decide), admin (plus audit, model card), viewer (read-only). Every read of a merchant profile writes an audit entry. Include a test proving no endpoint changes a loan status automatically.

## 9. Dashboard pages

1. **Review queue**: table sorted by oldest pending; filters; band badges; coverage bar.
2. **Merchant detail**: left, unified timeline (orders, deliveries, payments); right, score gauge, coverage meter, reasons in two columns (helps / hurts), questionnaire summary if present, "Why might this be wrong?" box listing limitations, and decision form (accept / override / needs more info + mandatory reason on override).
3. **Decision log**: who decided, what, agreement rate between officer and model.
4. **Model card**: metrics with ranges, calibration plot, ablation (A to D, with and without delivery features at signal strengths 0, 0.5 and 1), segment table, limitations in plain words.
5. **Consent view / mock consent page**: what data, which purpose, how long, revoke. Scoring is blocked without valid consent.
6. **Audit log** (admin) and **Portfolio view** (admin, viewer): band shares, decisions over time, override rate, group gaps.
7. Persistent banner: "Synthetic demo data. Decision support only."

## 10. Milestones (updated Oct 10; finals Nov 4-6; flight leaves Dhaka 23:55 on Nov 2; arrive Manila by 5pm Nov 3)

| When | Deliverable |
|---|---|
| Oct 10-12 | Repo, environment, schemas, synthetic generator v1, DB load |
| Oct 13-19 | Feature builder, baseline LR, API skeleton, Streamlit queue page. Onboarding week starts Oct 19 |
| Oct 20-26 | GBM + SHAP reasons, merchant detail page, decision logging, audit |
| Oct 27-31 | Ablation, calibration, segment checks, model card, tests, Docker/Makefile polish |
| Nov 1-2 | Freeze features. Demo script, slides, rehearse 3 times, record a backup demo video |
| Nov 3 | Travel and arrive. No new features |

## 11. Team split (4 members)

| Role | Owns | Folders |
|---|---|---|
| A. Lead / PM + Domain | Story, ShopUp contact, slides, pitch, model-card wording, schedule, visa/payment admin | `docs/`, README |
| B. Data engineer | Synthetic generator, DB models, loading, feature builder, data dictionary | `src/synth`, `src/db`, `src/features` |
| C. ML engineer | Training, ablation, calibration, SHAP reasons, segment checks | `src/model`, `reports/` |
| D. Full-stack | FastAPI, auth/audit, Streamlit (or React) UI, tests, Docker | `src/api`, `src/app`, `tests/` |

Rule: each person works on their own branch, opens small pull requests, and at least one other person reviews. Merge to `main` only when tests pass.

## 12. Definition of done for the demo

- `python tasks.py data`, `train`, `api` and `app` (or the same via `make` on Mac/Linux) work on a clean Windows and Linux machine.
- A live walk-through: pick a thin-file merchant, show score and reasons, show low coverage, override with a reason, see it in the decision log.
- Ablation chart shows with/without delivery features at signal strengths 0, 0.5 and 1, with honest caption, including the zero-signal control.
- Model card lists limitations: synthetic data, unvalidated hypothesis, no real-world fairness claim.
- Backup recording exists.

## 13. Finverse alignment (overrides earlier sections where they conflict)

Source: the team's Finverse result (data.org). Challenges: Limited Data Availability & Accessibility; Fragmented & Disconnected Systems; Missing Contextual & Subjective Data. The submission promised a Mifos X based prototype, a FinHealth-style questionnaire, consented Account Aggregator-style rails and a public-data starter kit. Add the following:

1. **Mifos X (option A, required):** shape the data model after Mifos X concepts (client, loan, repayment schedule, transaction) and add `src/db/mifos_adapter.py` that exports synthetic clients and loans as Mifos X-importable JSON/CSV. **Option B (stretch, spike first):** run Mifos X Community App in Docker, load the synthetic clients and loans through its API, and let the dashboard read from it. Time-box the spike to one day; if it fails, stay on option A and say so honestly. Do not claim an integration that does not exist.
2. **Consent:** add the `consents` table, a mock consent page (what data, which purpose, how long, revoke button) and a check in the scoring path. Document that Bangladesh has no Account Aggregator equivalent; this applies the idea to the platform's own records.
3. **Starter kit:** add `docs/starter_kit.md` and a one-page schema map for public datasets (Global Findex, IMF Financial Access Survey, national and central bank portals). Verify availability for Bangladesh before using any dataset. If district-level data exists, add context features; otherwise use national baselines in the deck only.
4. **Data inventory and access policy:** add `docs/data_inventory.md` (what data exists, owner, how to request, who may view).
5. **Master data:** `merchants` is the single master table; add a test that no merchant id is duplicated and every foreign key resolves. Add `make backup` for the SQLite file.
6. **Questionnaire:** use the 10-item structure above; show the four subscores and mark questionnaire-derived reasons as "directional".
7. **Optional:** one Metabase page with aggregate statistics (applications, band shares) if time allows. Skip n8n and RudderStack because the synthetic data loads once.
8. **Pilot KPIs (document only, cannot be measured on synthetic data):** time from application to decision; share of thin-file applications decided without extra manual data gathering; override rate and agreement rate; share in "Needs more info"; later, repayment outcomes of accepted merchants on real data with ShopUp's permission.
9. **Wording rules:** do not claim outcomes for Kaleidofin; the Finverse case concerns user research and product design. Describe the 4-week roadmap as the first small pilot of Finverse's 12-24 month two-track plan.

## 14. First instructions for Claude Code

1. Create the repo structure in section 4 with empty modules and docstrings.
2. Implement `src/synth/generate.py` per section 5 and `schemas.md`.
3. Add DB models and the loader, then pytest checks for row counts, no future leakage, thin-file share.
4. Stop and summarise before starting the model work.

## 15. Reusable core and adapters (so it is not ShopUp-only)

ShopUp is the hackathon partner and the demo context, but the design must stay platform-agnostic (Finverse "Core + Context").

- **Core (same everywhere):** unified merchant profile and schema, feature builder, training/ablation/calibration/SHAP pipeline, score + coverage + band logic, decision log, audit log, roles, model card.
- **Context (swappable via config and adapters):** `src/adapters/<platform>.py` mapping a platform's orders, payments and logistics exports into our tables; the feature dictionary (Bangla/English sentences); band lines and coverage weights; consent method; label rules (30/60 days).
- Ship one adapter, `src/adapters/shopup_synthetic.py`, and document in `docs/adapting.md` how another platform (marketplace, ride/food platform, Shopify-style seller tools) would add its own adapter and retrain.
- Wording: say "the design and code are reusable"; do not claim the model works for other countries or platforms without local data, local consent rules and fresh validation.
- REDX/delivery data is optional for the system to run. It is included because it may add signal beyond orders and payments, and that is tested by ablation, not assumed.

## 16. Current stage, data plan and git policy

- Current stage: project structure only. No data generation or modelling until the team decides the data path.
- Data path: default is synthetic data. The team will try to obtain something from ShopUp (possibly only loan outcome labels). All sources go through `src/adapters/`; see `docs/REAL_DATA_SWITCH.md` for the three cases (nothing, labels only, extract).
- Git policy: the human team performs all git operations. Claude Code must not run state-changing git commands or create commits/branches; it lists changed files after each phase.
