# ACCEPTANCE_CHECKLIST.md

Tick before the demo. Claude Code should help produce evidence for each item (test names, report files).

## Data
- [ ] `python tasks.py data` is reproducible with seed 42 (same row counts and hashes).
- [ ] No duplicate merchant_id; all foreign keys resolve (test_master_data).
- [ ] Thin-file share near 35%; 25% of merchants without delivery data; repayment share 75-85%.
- [ ] At signal strength 0, correlation of delivery features with hidden reliability is about 0.

## Model
- [ ] Labels follow the 30-day rule; loans under 60 days excluded.
- [ ] Time split 12/3/3 months; test_leakage passes.
- [ ] Both models trained; chosen one justified in the model card.
- [ ] Calibration plot exists and is acceptable on test; calibrator fitted on validation only.
- [ ] Metrics with bootstrap ranges; baselines beaten.
- [ ] Ablation A to D at strengths 0, 0.5, 1; zero-signal test passes; D reported separately.
- [ ] Questionnaire shown beside the score, not inside it.
- [ ] Logistics-noise returns present; delivery reasons worded neutrally.
- [ ] No sales or repeat-customer features from Mokam purchases.
- [ ] Group table by town_tier, shop_type, licence (and public-data audit columns) with bootstrap ranges; gaps flagged only when ranges do not overlap or persist across seeds.
- [ ] Every score returns probability, score, band, coverage, 3 up + 3 down reasons, model version.

## Public data
- [ ] kiva_asia and taiwan_cc adapters pass test_adapters with fixtures.
- [ ] Real-label runs done; metrics with ranges compared to 0.70 benchmark and 0.95 alarm.
- [ ] Audit-only columns never in the feature matrix (leakage whitelist test).
- [ ] Raw public data not in git; docs/DATA_SOURCES.md lists links and licences.

## System
- [ ] No auto-approve/decline path (test_no_autodecision).
- [ ] Consent missing or revoked -> scoring refused.
- [ ] Roles enforced; audit entry on every profile read and decision.
- [ ] Decisions append-only; override requires reason.
- [ ] Banner names the data source and says "Decision support only." on every page.
- [ ] The React dashboard calls only the API; no database keys or connection strings in the browser bundle or the repo.
- [ ] Tests pass on SQLite with no network; the same loader works against Supabase Postgres via `DATABASE_URL`.
- [ ] The app runs locally without the internet (fallback for the venue), and the hosted copy on Hostinger works.

## Demo
- [ ] Walk-through: thin-file merchant -> low coverage -> "Needs more info"; strong merchant -> reasons; override with reason; appears in decision log and audit.
- [ ] Model card page shows limitations in plain words.
- [ ] Backup video recorded; DB backup made; slides match what the product really does.
- [ ] Every teammate can explain their own folder.
