# PROJECT_BRIEF.md: CredLens, a Merchant Readiness Dashboard (Team 4Bytes)

Read this file fully before generating any code. It is the single source of truth for scope, stack, structure and rules.

## 1. What this is

An internal, staff-facing decision-support dashboard for a B2B commerce and credit company (modelled on ShopUp, Dhaka: Mokam = wholesale sourcing, REDX = last-mile logistics, Baki = embedded working-capital credit).

A credit officer opens a new merchant's profile and sees:
1. A unified view of the merchant's wholesale purchase data (Mokam-style: what the shop BUYS from suppliers), delivery (REDX-style) outcomes and payment (Baki-style) history.
2. A **readiness score** (0-100) from an explainable ML model. The model outputs a calibrated repayment *probability* (for example 0.72), never a bare 0 or 1; score = round(100 x probability). The 0/1 values exist only as training labels.
3. **Plain-language reasons** for the score (top positive and negative factors).
4. A **data-coverage indicator** (how much history the score is based on).
5. Buttons for the officer to **accept / override** and record a reason. The system never approves or declines credit by itself.

Competition: 2026 Data, AI & Policy APAC Hackathon (Financial Health Frontiers). Finals Nov 4-6, 2026, Manila. This is a prototype to demo and defend, not a production system.

## 2. Hard rules (do not violate)

1. **No real partner data.** ShopUp data could not be obtained, and the hackathon rules say no proprietary partner data is required. The system runs in three data modes (see section 17 and docs/DATASET_PLAN.md): `synthetic_bd` (main demo, Bangladesh-calibrated synthetic), `kiva_asia` and `taiwan_cc` (public real-label checks). Every screen shows the data source: "Synthetic demo data" or "Public data (Kiva / Taiwan credit cards), not ShopUp data".
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
| Database | PostgreSQL on Supabase (hosted, shared by the team) via SQLAlchemy; SQLite for local development and tests, chosen by `DATABASE_URL` | One codebase; tests run offline with no secrets |
| ML | scikit-learn (LogisticRegression), LightGBM or sklearn HistGradientBoosting, SHAP, joblib | Interpretable baseline plus stronger model |
| API | FastAPI + Pydantic + Uvicorn | Typed, auto docs at /docs |
| Dashboard | React + Vite + TypeScript + Tailwind + shadcn/ui, in `web/` (decided Oct 12) | Polished UI; team knows React. Talks only to the API |
| Charts | Recharts in the dashboard; matplotlib for report images | |
| Hosting | Hostinger VPS: Nginx serves the React build and proxies `/api` to Uvicorn | Python ML libraries need a VPS, not shared hosting |
| Auth (demo) | Simple role switch (officer / admin / viewer) with a header token | Shows role-based access without OAuth effort |
| Tests | pytest | |
| Tooling | Docker Compose (optional), Makefile, ruff, pre-commit | |
| Mifos X (open-source core banking) | Data-model alignment and export adapter (option A, required). Docker integration (option B) only if time allows. See sections 13 and 18 | Submission promised a Mifos X prototype; keep it simple and report honestly |

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
    raw/                    # generated CSVs and human-downloaded public data: raw/kiva/, raw/taiwan_cc/ (gitignored)
    app.db                  # SQLite for local development and tests (gitignored); shared DB is Supabase Postgres
  src/
    config.py
    adapters/
      base.py               # abstract DataAdapter (swappable data sources)
      shopup_synthetic.py   # synthetic_bd mode
      kiva_asia.py          # public real-label mode (Kiva, Asia-Pacific small businesses)
      taiwan_cc.py          # public real-label mode (UCI Taiwan credit-card default)
      shopup_real.py        # stub for later, if ShopUp shares data
      factory.py            # get_adapter(config) by data.mode
    synth/
      generate.py           # builds merchants, purchases, deliveries, payments, outcomes
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
  web/                      # React + Vite + TypeScript + Tailwind dashboard; talks only to the API
    src/                    # pages: Queue, Merchant detail, Decision log, Model card, Consent, Audit, Portfolio
  reports/
    <mode>/metrics.json     # one folder per data mode
    calibration.png
    ablation.png
    fairness_by_segment.csv
  tests/
    test_synth.py test_features.py test_api.py test_no_autodecision.py
    test_leakage.py         # no feature uses data after the loan cutoff
    test_master_data.py     # unique merchant ids, every foreign key resolves
    test_zero_signal.py     # at delivery_signal_strength=0, delivery features add no meaningful AUC
    test_reasons.py         # 3 up + 3 down reasons, each mapped to a dictionary sentence
    test_adapters.py        # each adapter returns the data contract; tiny fixtures only
    fixtures/               # tiny hand-made CSVs, never real data
  docs/
    architecture.png        # the flow diagram
    model_card_<mode>.md    # one per data mode
    DATA_SOURCES.md         # links, licences, what we use and drop
    data_governance.md
```

## 5. Data contract (synthetic)

All ids are strings. Dates are ISO. Generate roughly 5,000 merchants over 18 months.

**merchants**: merchant_id, onboarded_at, district, town_tier (metro / city / small_town), shop_type (grocery, pharmacy, apparel, electronics, other), has_trade_license (bool), consent_data_use (bool, ~95% true), questionnaire_done (bool, ~40% true).

**purchases** (Mokam-style wholesale purchases: the merchant buys stock): purchase_id, merchant_id, purchase_date, amount_bdt, category, supplier_id. These are NOT the merchant's sales.

**deliveries** (REDX-style): delivery_id, merchant_id (the merchant's outgoing parcels to its own customers; a sales proxy for merchants who sell online), dispatched_at, delivered_at (nullable), status (delivered / returned / failed / cancelled), return_reason (refused / wrong_item / address_issue / rider_issue / other, nullable), is_cod (bool), cod_remitted_on_time (bool, nullable).

**payments** (Baki-style): payment_id, merchant_id, loan_id, due_date, paid_date (nullable), amount_due_bdt, amount_paid_bdt.

**loans**: loan_id, merchant_id, issued_at, limit_bdt, outcome_label (1 = repaid fine, 0 = 30+ days late or default), label_observed_at.

**questionnaire** (optional, FinHealth-style Core + Context, 10 items, 1-5 scale): merchant_id, spend1, spend2, save1, save2, borrow1, borrow2, plan1, plan2, stress, confidence, answered_at. Four subscores (Spend, Save, Borrow, Plan) plus two context items. Shown BESIDE the score as its own indicator; NOT part of the headline model (config `questionnaire_in_model: false`). Ablation set D is reported as a separate finding. Item wording must be adapted from the public FinHealth Score toolkit (check its terms of use) and translated into Bangla with care.

**consents**: consent_id, merchant_id, purpose, data_categories, granted_at, expires_at, revoked_at. Scoring is refused when there is no valid, unexpired, unrevoked consent.

**decisions** (written by the app): decision_id, merchant_id, officer_id, model_version, score_shown, officer_action (accept / override_up / override_down / needs_more_info), reason_text, decided_at.

**audit_log**: id, actor, role, action, merchant_id, timestamp.

### Generator requirements
- Seeded and reproducible (`--seed 42`).
- Latent merchant "reliability" variable drives all signals with noise, so signals are correlated but imperfect.
- Include **thin-file merchants** (few purchases in first 30 days; 30-40% of new merchants) because that is the problem being solved.
- Include missingness (some merchants have no deliveries yet) so the coverage indicator is meaningful.
- Add a config switch `delivery_signal_strength` with three settings: 0 (delivery data is pure noise, the negative control), 0.5 (weak) and 1 (strong). Run the ablation at all three, so the team can show honestly that the benefit depends on the assumption. At 0, delivery features must add no meaningful gain; if they do, there is a bug or leakage.
- Add seasonality (Eid peaks, monsoon dips) to purchases. Add `logistics_noise_share`: part of returns/failures caused by address or rider issues, independent of the merchant.

## 6. Features (computed as of a cutoff date, using only data before it)

- Purchases: count and value in first 14/30 days, purchase regularity, basket growth, category diversity, supplier repeat share, weeks active. No sales or repeat-customer features (Mokam does not show sales). Sales proxy only from REDX parcel volume.
- Deliveries: delivered rate, return rate, failed rate, median dispatch-to-delivery hours, COD remittance on-time rate.
- Payments (for repeat borrowers): on-time rate, average days late, utilisation.
- Context: town_tier, shop_type and has_trade_license are **audit columns only**. They are used for the segment/fairness checks and are NOT model features (avoids direct bias). Revisit only if the team decides otherwise and documents why in the model card.
- Questionnaire subscores (nullable): shown in their own panel beside the score, NOT used by the headline model.
- Public-data modes add source-specific features (see FEATURE_DICTIONARY and DATASET_PLAN).
- **Coverage features**: days of history, number of purchases, number of deliveries, share of feature groups available.

Avoid leakage: build features strictly from events before the cutoff; labels come from after.

## 7. Modelling spec

0. **Labels**: 1 = repaid within 30 days of the due date, 0 = more than 30 days late or default. Exclude loans with fewer than 60 days of history (outcome unknown). The 30 and 60 day values are config settings.
1. **Split by time** on loan issue date (Kiva: posted_time): train on the first 12 months, validate on the next 3, test on the last 3 (all configurable). Never random split, except the Taiwan data, which has no per-row dates: stratified random split, marked "weaker split" in its model card. Fit the calibrator on validation only; touch test once. A test must fail the build if any feature uses data after the loan's cutoff date.
2. **Models**: (a) regularised logistic regression (interpretable baseline), (b) gradient-boosted trees. Choose on validation by AUC, Brier and calibration; if the GBM gain is small, keep the logistic regression. Report both in the model card. Fixed random seeds.
3. **Feature-set ablation**: A purchases-only, B +payments, C +deliveries, D +questionnaire (reported as a separate finding; the headline model uses A to C), repeated at `delivery_signal_strength` 0, 0.5 and 1. Keep a feature group only if its gain beats the bootstrap range and does not worsen group gaps.
4. **Metrics**: ROC-AUC, PR-AUC, Brier score, calibration curve; precision at top-k and reviewable-share at a chosen threshold. Report bootstrap ranges. Baselines to beat: always predicting the average repayment rate, and the purchases-only model. Treat AUC above 0.95 as a leakage warning; around 0.70+ is the realistic usefulness bar (CGAP). Run the same metrics for kiva_asia and taiwan_cc.
5. **Segment checks**: metrics, calibration and band shares by town_tier, shop_type, has_trade_license (audit columns, not features). Report bootstrap ranges per group; flag a gap only when ranges do not overlap or it persists across seeds. Same rule for public-data audit columns (section 17). Do not claim "fair"; report what was measured.
6. **Score**: calibrated probability of good repayment x 100, rounded; bands (Strong / Review / Needs more info). The "Needs more info" band is chosen by low coverage, not low score. Coverage is a separate 0-100% number: a weighted checklist (history length, purchases present, payments present, deliveries present, questionnaire done, recent activity) with weights in config. Missing REDX/delivery data lowers coverage; it must never lower the score by itself. Band lines (for example Strong at 70+, minimum coverage 60%) live in config, not code.
7. **Reasons**: top 3 positive and top 3 negative contributors (SHAP for GBM, coefficient x value for LR), mapped through a dictionary to sentences such as "Delivered 94% of recent REDX parcels (above typical)" or "Only 6 days of history, so confidence is low".
8. Save `model.joblib` and `metadata.json` (version id, code commit, data seed, train window, metrics, feature list, calibrator). Every score and every decision records the model version that produced it.
9. Dictionary sentences exist in Bangla and English, worded as observations ("returns are higher than similar shops"), not as accusations or causes.

## 8. API (FastAPI)

- `GET /health`
- `GET /merchants?status=pending&band=&town_tier=` : review queue
- `GET /merchants/{id}` : profile with merged purchases / deliveries / payments summaries
- `GET /merchants/{id}/score` : `{score, probability, band, coverage, reasons_positive[], reasons_negative[], model_version}` (exactly 3 positive and 3 negative reasons when available)
- `POST /merchants/{id}/decision` : body `{officer_action, reason_text}` (reason required when action is override)
- `GET /decisions?merchant_id=` : decision history
- `GET /model/card` : metrics, ablation, limitations
- `GET /audit` (admin only)

Roles: officer (queue, score, decide), admin (plus audit, model card), viewer (read-only). Every read of a merchant profile writes an audit entry. Include a test proving no endpoint changes a loan status automatically.

## 9. Dashboard pages

Built as a React app in `web/`. It reads and writes only through the FastAPI API, never the database directly, so consent, roles, audit and the no-auto-decision rule cannot be bypassed.

1. **Review queue**: table sorted by oldest pending; filters; band badges; coverage bar.
2. **Merchant detail**: left, unified timeline (purchases, deliveries, payments); right, score gauge, coverage meter, reasons in two columns (helps / hurts), questionnaire panel beside the score (four subscores, marked directional, not part of the score), "Why might this be wrong?" box listing limitations, and decision form (accept / override / needs more info + mandatory reason on override).
3. **Decision log**: who decided, what, agreement rate between officer and model.
4. **Model card** (one per data mode; selector at top): metrics with ranges, calibration plot, ablation (A to D, with and without delivery features at signal strengths 0, 0.5 and 1), segment table, limitations in plain words.
5. **Consent view / mock consent page**: what data, which purpose, how long, revoke. Scoring is blocked without valid consent.
6. **Audit log** (admin) and **Portfolio view** (admin, viewer): band shares, decisions over time, override rate, group gaps.
7. Data-source selector in the sidebar (synthetic_bd / kiva_asia / taiwan_cc). Public modes show only the pages their data supports (no timeline when streams are empty).
8. Persistent banner naming the source ("Synthetic demo data" or "Public data: Kiva / Taiwan credit cards, not ShopUp data") plus "Decision support only."

## 10. Milestones (updated Oct 10; finals Nov 4-6; flight leaves Dhaka 23:55 on Nov 2; arrive Manila by 5pm Nov 3)

| When | Deliverable |
|---|---|
| Oct 12 | Phase 0 scaffold with the API contract and fixtures; both teammates start that night |
| Oct 13 | Phase 1 synthetic generator; React app shell; model pieces on fixtures |
| Oct 14-15 | Phase 2 database (SQLite + Supabase), Phase 3 features and leakage test; end-to-end model slice on Oct 14; dashboard pages on the fixture API |
| Oct 16-17 | Phase 7 public-data adapters (Kiva Asia, Taiwan); Phases 4-6 model, calibration, SHAP reasons; Phase 9 API on the real database |
| Oct 18-19 | Phase 8 real-label runs; Phase 11 ablation, group audit, model cards; real scores in the dashboard; Phase 12 deploy to Hostinger; docs |
| Oct 20 | Phase 13 sceptical review, fixes, full walk-through. Build finished |
| Oct 21 | Buffer: leftover fixes, backup video. No new features |
| Oct 22-Nov 2 | Slides, pitch, three rehearsals, onboarding week; bug fixes only |
| Nov 3 | Travel and arrive. No new features |

## 11. Team split (4 members)

| Role | Owns | Folders |
|---|---|---|
| A. Lead / PM + Domain | Story, ShopUp contact, Bangladesh calibration figures, dataset downloads and licence checks, slides, pitch, model-card wording, schedule, visa/payment admin | `docs/`, README |
| B. Data engineer | Synthetic generator, public-data adapters, DB models, loading, feature builder, data dictionary | `src/synth`, `src/db`, `src/features` |
| C. ML engineer | Training, ablation, calibration, SHAP reasons, segment checks | `src/model`, `reports/` |
| D. Full-stack | FastAPI, auth/audit, React UI, tests, deployment | `src/api`, `web/`, `tests/` |

Rule: each person works on their own branch, opens small pull requests, and at least one other person reviews. Merge to `main` only when tests pass.

## 12. Definition of done for the demo

- `python tasks.py data`, `train`, `api` and `app` (or the same via `make` on Mac/Linux) work on a clean Windows and Linux machine.
- A live walk-through: pick a thin-file merchant, show score and reasons, show low coverage, override with a reason, see it in the decision log.
- Ablation chart shows with/without delivery features at signal strengths 0, 0.5 and 1, with honest caption, including the zero-signal control.
- Real-label runs on kiva_asia and taiwan_cc shown with honest captions (method check, not ShopUp performance).
- Model cards list limitations: synthetic data, unvalidated REDX hypothesis, selection bias, public data is not ShopUp data, no real-world fairness claim.
- Backup recording exists.

## 13. Finverse alignment (overrides earlier sections where they conflict)

Source: the team's Finverse result (data.org). Challenges: Limited Data Availability & Accessibility; Fragmented & Disconnected Systems; Missing Contextual & Subjective Data. The submission promised a Mifos X based prototype, a FinHealth-style questionnaire, consent rails inspired by Account Aggregator-style designs (design reference only, see section 17) and a public-data starter kit. Add the following:

1. **Mifos X (option A, required):** shape the data model after Mifos X concepts (client, loan, repayment schedule, transaction) and add `src/db/mifos_adapter.py` that exports synthetic clients and loans as Mifos X-importable JSON/CSV. **Option B (optional, only if time allows after everything else works):** run Mifos X Community App in Docker and load the synthetic clients and loans through its API. Time-box it to one day; if it is skipped or fails, stay on option A and say so honestly. Do not claim an integration that does not exist.
2. **Consent:** add the `consents` table, a mock consent page (what data, which purpose, how long, revoke button) and a check in the scoring path. Document that Bangladesh has no Account Aggregator equivalent; this applies the idea to the platform's own records.
3. **Starter kit:** add `docs/starter_kit.md` built from docs/DATASET_PLAN.md (training sources, calibration sources, context sources, with links and licence notes).
4. **Data inventory and access policy:** add `docs/data_inventory.md` (what data exists, owner, how to request, who may view).
5. **Master data:** `merchants` is the single master table; add a test that no merchant id is duplicated and every foreign key resolves. Add a `backup` task for the database (SQLite file copy locally; table export for Postgres).
6. **Questionnaire:** use the 10-item structure above; show the four subscores in a panel beside the score, marked "directional"; not part of the headline score.
7. **Optional:** one Metabase page with aggregate statistics (applications, band shares) if time allows. Skip n8n and RudderStack because the synthetic data loads once.
8. **Pilot KPIs (document only, cannot be measured on synthetic data):** time from application to decision; share of thin-file applications decided without extra manual data gathering; override rate and agreement rate; share in "Needs more info"; later, repayment outcomes of accepted merchants on real data with ShopUp's permission.
9. **Wording rules:** do not claim outcomes for Kaleidofin; the Finverse case concerns user research and product design. Describe the 4-week roadmap as the first small pilot of Finverse's 12-24 month two-track plan.

## 14. First instructions for Claude Code

Follow the phases in docs/PROMPTS.md, starting at Phase 0. Stop after each phase.

## 15. Reusable core and adapters (so it is not ShopUp-only)

ShopUp is the hackathon partner and the demo context, but the design must stay platform-agnostic (Finverse "Core + Context").

- **Core (same everywhere):** unified merchant profile and schema, feature builder, training/ablation/calibration/SHAP pipeline, score + coverage + band logic, decision log, audit log, roles, model card.
- **Context (swappable via config and adapters):** `src/adapters/<platform>.py` mapping a platform's purchases, payments and logistics exports into our tables; the feature dictionary (Bangla/English sentences); band lines and coverage weights; consent method; label rules (30/60 days).
- Ship three working adapters (shopup_synthetic, kiva_asia, taiwan_cc) plus the shopup_real stub, and document in `docs/adapting.md` how another platform (marketplace, ride/food platform, Shopify-style seller tools) would add its own adapter and retrain.
- Wording: say "the design and code are reusable"; do not claim the model works for other countries or platforms without local data, local consent rules and fresh validation.
- REDX/delivery data is optional for the system to run. It is included because it may add signal beyond purchases and payments, and that is tested by ablation, not assumed.

## 16. Current stage, data plan and git policy

- Current stage: fresh start. Nothing is built yet. Begin with Phase 0 (structure only), then dataset work first (see section 18).
- Data path: ShopUp data was not obtained. Use the three data modes in section 17. ShopUp (or any similar FSP) can plug in later via `src/adapters/shopup_real.py`; see docs/REAL_DATA_SWITCH.md.
- Raw public data lives in `data/raw/<source>/`, is gitignored, and is downloaded by a human (see the HUMAN STEP protocol in CLAUDE.md). Never redistribute Findex microdata or Kaggle data.
- Git policy: the human performs all git operations. Claude Code never runs state-changing git commands; it lists changed files after each phase.

## 17. Data modes and review fixes (v2, overrides earlier sections where they conflict)

Full detail: docs/DATASET_PLAN.md.

| Mode | Source | Labels | Proves |
|---|---|---|---|
| synthetic_bd | generator calibrated with Findex Bangladesh, Bangladesh Bank MFS, ShopUp public figures | generated | full product and the REDX hypothesis ablation (incl. zero-signal control) |
| kiva_asia | Kiva loan snapshot filtered to Asia + Retail/Food/Services | real (paid vs defaulted) | method works on real Asian small-business repayment |
| taiwan_cc | UCI "Default of Credit Card Clients" (Taiwan, 30,000 clients, CC BY 4.0) | real (default next month) | payment-behaviour features carry signal on real Asian data |

Fixes applied in v2 (keep them):
1. Mokam = purchases, not sales. No repeat-customer or sales-growth features.
2. Target user, one sentence everywhere: "Small merchants new to ShopUp credit, with Mokam purchase history and, where they sell online, REDX parcels."
3. Statistic: 73% of small retailers sell on credit; 27.5% have formal-finance access (ShopUp Series B press release). Use one source consistently.
4. Delivery returns: logistics noise in the generator; prefer merchant-attributable events (refused, wrong item); reasons worded as neutral observations ("may reflect delivery conditions").
5. Questionnaire beside the score, not inside it.
6. India's Account Aggregator, SGFinDex and Open Finance PH are design references only. Bangladesh has no AA rail; consent here is platform consent recorded in the `consents` table; scoring is blocked without it.
7. Mifos X: Mifos-style data model and export adapter in a React + FastAPI + Postgres build; one-day Docker spike only if time allows; report the result honestly.
8. REDX ablation on synthetic data is circular by itself, so real-label runs (kiva_asia, taiwan_cc) are required. Claim only that the method works on real labels.
9. Selection bias: labels exist only for people who received credit. State it; propose a pilot with small starter limits.
10. Group gaps: bootstrap ranges per group; flag only when ranges do not overlap or the gap persists across seeds.
11. Benchmark: AUC around 0.70+ is useful for transactional MSE lending (CGAP). AUC > 0.95 is a leakage alarm.
12. Public-data audit columns (Kiva gender/country; Taiwan sex/education/marital status/age band) are audit-only, never inputs.
13. Asia-Pacific relevance: the design targets Asian small merchants; Bangladesh first, with Kiva covering wider Asia.

## 18. Team decisions of Oct 12 (v3, overrides earlier sections where they conflict)

1. **Stay consistent with the Phase 2 submission.** The build must deliver what the submitted form describes: a staff dashboard unifying order (Mokam purchase), Baki payment and REDX delivery records for thin-file, new-to-credit merchants; an explainable model giving score plus reasons; staff decide; a FinHealth-style questionnaire; consented data access; the starter-kit approach to limited data; a Mifos X-based prototype (delivered as the Mifos-style data model and export adapter).
2. **Dataset first, finished by Oct 20 (Oct 21 buffer).** Three people work in parallel from the night Phase 0 ends, using small fixtures. Lead (data): phases 0 → 1 → 2 → 3 → 7, then 12 and 13. ML teammate: labels, 4, 5, 6, 8, 11. Full-stack teammate: 9 and 10. The public-data adapters (7) come after features because they depend on downloads and must not block the synthetic track. Phase numbers are unchanged. See the day table in section 10.
3. **Statistic:** 73% of small retailers sell on credit; 27.5% have formal-finance access (ShopUp Series B press release). The submission said 72% (Daily Star, 2021); use 73% from now on and be ready to explain the one-point difference as a change of source.
4. **Dashboard:** React + Vite + TypeScript + Tailwind + shadcn/ui in `web/`. No Streamlit. The browser calls only the FastAPI API.
5. **Database:** Supabase PostgreSQL for the shared and hosted database; SQLite for local development, tests and CI. The connection string comes from the `DATABASE_URL` environment variable and is never committed. Only synthetic and public-derived data may be loaded. Raw public files stay in `data/raw/` and are not uploaded.
6. **Hosting:** Hostinger VPS (API and React build). Deployment is a late step and must not block data or model work. Keep a local run and a backup video in case the venue network fails.
7. **Mifos X:** option A (data model plus export adapter) is the deliverable. The Docker spike is optional and attempted only if time allows; never claim an integration that was not built.
8. **Kaleidofin:** a design reference only. The team's Finverse result cites "CGAP's Kaleidofin case in 'Banking in Layers'" as a case study; that is the source behind the submission's sentence. A teammate must read it before quoting any outcome (VERIFY). Cite it as a case study Finverse pointed us to. Do not present its client outcomes as evidence for CredLens, and do not promise the same outcomes. There is nothing to integrate technically (no public data or API).
9. **Asian context only (data modes v4).** `synthetic_bd` (main demo, Bangladesh-calibrated), `kiva_asia` (Kiva loans filtered to Asia and Retail/Food/Services: real Asian small businesses) and `taiwan_cc` (UCI Taiwan credit-card default, CC BY 4.0: real Asian payment behaviour). Backup if Kiva cannot be downloaded or has no usable default label: India L&T vehicle loans (Kaggle; licence and columns unverified). Dropped: Home Credit (the data does not state its country) and any non-Asian source. Report Kiva results with a breakdown for Finverse focus countries (India, Indonesia, Philippines) where the file supports it.
10. **No invented history on real rows.** Never add generated purchases, deliveries or payments to Kiva or Taiwan records; that would leak the outcome and mislabel the data. The complete four-stream picture belongs to `synthetic_bd` only.
11. **Coverage is per data mode.** Coverage means "how much of what this source can provide is present", using `coverage_weights_by_mode` in config (each list sums to 1.0). Public modes therefore get meaningful coverage, bands and reasons from their own real fields. Dashboard pages show what each source has instead of empty charts.
12. **Model quality bar.** The synthetic generator is tuned so test AUC lands around 0.72 to 0.82 at signal strength 0.5; the 0.95 alarm is a bug detector. Every metric has a bootstrap range and is repeated across at least 3 seeds; reasons must sum to the score; a rough end-to-end model slice runs by Oct 14. Real-label results are reported as they come out, never tuned up.
13. **Finverse gaps closed in documents.** The starter kit includes the one-page schema map, IMF Financial Access Survey and Finverse's regional sources (Data.gov.in, NDAP, SHRUG) as context; the data inventory references the ODI data practices guide and the UK ICO data sharing code; the roadmap names a small financial-diaries pilot (about 40 merchants, 3 months) as the next step, since diaries are recommended by Finverse but not built here.
