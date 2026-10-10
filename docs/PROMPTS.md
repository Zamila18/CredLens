# PROMPTS.md: phase-by-phase prompts for Claude Code

How to use: open the repo in Claude Code, make sure CLAUDE.md and PROJECT_BRIEF.md are in the root, then paste one phase at a time. After each phase, read the summary, run `python tasks.py test`, skim the code, and commit it yourself (Claude Code never runs git commands that change the repo). Only then paste the next phase.

Current stage: Phase 0 only (structure). Phases 1 onward involve data and are deferred until the team decides the data path (synthetic, label-only from ShopUp, or a real extract). Each teammate works on their own branch for their phases.

## Phase 0: scaffold, STRUCTURE ONLY (owner: D or lead)
Paste the prompt in `docs/PHASE0_PROMPT.md`. Done when: structure exists, config loads, `python tasks.py lint` and `python tasks.py test` pass, API `/health` and the Streamlit placeholder boot, and Claude Code lists the files it created. Claude Code does not commit; you do.

## Phase 1: synthetic data (owner: B) [deferred until the data path is decided; synthetic is the default]
"Implement src/synth/generate.py exactly per docs/GENERATOR_SPEC.md and section 5 of the brief, seeded, reading all numbers from config. Write src/synth/schemas.md (column dictionary). Add tests: row counts, no duplicate merchant_id, foreign keys, thin-file share, date order, repayment share, correlation checks at delivery_signal_strength 0 and 1. Support running at strengths 0, 0.5, 1 via a CLI flag. Summarise numbers observed and stop."
Done when: `python tasks.py data` works and the generator tests pass.

## Phase 1b: if ShopUp sends labels or a real extract (owner: B + C)
"Read docs/REAL_DATA_SWITCH.md. Here is what ShopUp sent: <describe files and columns; do not paste real data into the chat if it is sensitive, describe the schema instead>. Implement src/adapters/label_only.py or shopup_real.py to map it to our tables, write a data validation report (duplicates, orphans, date order, missing rates, outcome definition), and list which features and ablation sets are possible with this data. Do not touch raw files. Keep real data outside the repo. Summarise and stop."

## Phase 2: database (owner: B)
"Implement src/db/models.py (SQLAlchemy) for merchants, orders, deliveries, payments, loans, questionnaire, consents, users, decisions (append-only), audit_log, model_versions, and src/db/load.py (CSV to SQLite). Make the schema resemble Mifos X concepts (client, loan, repayment schedule, transaction) as far as practical and write src/db/mifos_adapter.py that exports synthetic clients and loans as Mifos X-importable CSV/JSON. Add the `backup` task in tasks.py. Enforce append-only on decisions in code and test it. Summarise and stop."

## Phase 3: features and labels (owner: B + C)
"Implement src/features/build_features.py computing all features in docs/FEATURE_DICTIONARY.md as of each loan's cutoff using strictly earlier data, plus coverage features, and src/features/dictionary.yaml with the Bangla/English sentences. Implement src/model/labels.py per docs/MODEL_SPEC.md section 2. Add test_leakage.py that fails if any feature reads data on or after the cutoff (inject a deliberate leak in a test to prove the test catches it). Summarise and stop."

## Phase 4: baseline model and evaluation (owner: C)
"Implement src/model/split.py (time split 12/3/3 from config), train.py for Logistic Regression, evaluate.py (ROC-AUC, PR-AUC, Brier, calibration data, top-k precision, bootstrap ranges, baselines). Save artifacts with version metadata. Write reports/metrics.json and reports/calibration.png. Warn if AUC exceeds sanity.suspicious_auc. Summarise results honestly and stop."

## Phase 5: calibration, score, coverage, band (owner: C)
"Implement calibrate.py (Platt and isotonic, chosen on validation, fitted on validation only) and score.py (score = round(100 x probability), coverage from config weights, band rules from config, missing delivery data lowers coverage only). Add unit tests with the worked examples in docs/MODEL_SPEC.md. Summarise and stop."

## Phase 6: LightGBM, SHAP, reasons (owner: C)
"Add LightGBM to train.py with validation-based tuning and early stopping; implement model choice per config (prefer simple if gain is small). Implement explain.py: SHAP for trees, coefficient x value for LR, top 3 up and 3 down, dictionary sentences in Bangla and English, remainder grouped so contributions sum to the final score. Add test_reasons.py. Summarise and stop."

## Phase 7: API (owner: D)
"Implement the FastAPI app per section 8 of the brief with roles (officer/admin/viewer via header token), consent check before scoring, audit entry on every profile read and write, override requires reason, append-only decisions, and /merchants/{id}/score returning score, probability, band, coverage, reasons and model_version. Add test_api.py and test_no_autodecision.py. Summarise and stop."

## Phase 8: dashboard (owner: D)
"Implement the Streamlit app per section 9: review queue, merchant detail (timeline, gauge, coverage meter, helps/hurts reasons, 'Why might this be wrong?', decision form), decision log, model card, consent view, audit log (admin), portfolio view, persistent banner 'Synthetic demo data. Decision support only.' Show Bangla/English toggle for reasons. Summarise and stop."

## Phase 9: ablation, fairness, model card (owner: C + lead)
"Implement ablation.py (sets A to D at strengths 0, 0.5, 1, regenerating data per strength), fairness.py (group metrics, calibration by group, flag gaps above config), and model_card.py writing docs/model_card.md and the JSON served at /model/card. Add test_zero_signal.py. Include honest captions: results on synthetic data prove nothing about real merchants. Summarise and stop."

## Phase 10: Mifos X spike, polish, rehearsal (owner: B + D)
"Time-box one day: try running Mifos X Community App in Docker and loading synthetic clients and loans via its API. If it works, document exactly what works; if not, document why and stay with the export adapter. Do not claim an integration that does not exist. Then: README with run instructions, docs/data_inventory.md, docs/starter_kit.md, docs/adapting.md (how another platform would add an adapter), Makefile polish, and a scripted demo path."

## Phase 11: final review (all)
"Act as a sceptical judge. Read the repo, the model card and the slides text. List every claim not supported by code or tests, every place a score could be shown without coverage, any feature that could leak the future, and any wording that overclaims. Propose fixes but do not apply them without asking."

## Tips
- Use plan mode before big phases. Review diffs. Ask Claude Code to explain any file you cannot explain yourself; judges may ask.
- If a phase output looks too good (high AUC), assume leakage until proven otherwise.
- Keep each pull request small; one reviewer minimum.
