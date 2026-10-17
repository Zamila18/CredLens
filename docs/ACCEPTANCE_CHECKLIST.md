# ACCEPTANCE_CHECKLIST.md

Tick before the demo. Each ticked box names its evidence: a test in `tests/` (run with
`python tasks.py test`) or a file in `reports/`. Evidence filled in on Oct 18, 2026; a box stays
open until its evidence exists. Open boxes are listed at the end.

## Data
- [x] `python tasks.py data` is reproducible with seed 42 (same row counts and hashes).
  Evidence: `test_synth.py::test_row_counts_and_reproducibility`, `test_master_data.py::test_the_fingerprint_is_stable_and_sensitive`.
- [x] No duplicate merchant_id; all foreign keys resolve (test_master_data).
  Evidence: `test_master_data.py::test_no_duplicate_merchant_ids`, `::test_every_foreign_key_resolves`; `test_synth.py::test_ids_are_unique`, `::test_every_foreign_key_resolves`.
- [x] Thin-file share near 35%; 25% of merchants without delivery data; repayment share about 90% (the team's assumption, `generator.repayment_share_target`).
  Evidence: `test_synth.py::test_thin_file_share_is_near_target`, `::test_share_without_delivery_data_is_near_target`, `::test_repayment_share_is_in_range`.
- [x] Thin-file merchants do not score lower for having little history: no model input depends on the amount of data (test_feature_builder).
  Evidence: `test_dataset.py::test_model_inputs_context_and_coverage_do_not_overlap`, `test_features.py::test_dictionary_marks_exactly_the_context_columns_as_not_model_inputs`, `test_boosted.py::test_missing_data_is_neutral_for_lightgbm`, `test_score_inputs.py::test_missing_data_has_no_points`.
- [x] No merchant without valid consent is used to train or test a model (test_dataset).
  Evidence: `test_dataset.py::test_merchants_without_consent_are_never_used_for_modelling`, `::test_only_unrevoked_unexpired_consents_are_valid`.
- [x] At signal strength 0, correlation of delivery features with hidden reliability is about 0.
  Evidence: `test_synth.py::test_delivery_signal_is_absent_at_strength_zero`, `::test_delivery_signal_is_present_at_strength_one`.

## Model
- [x] Labels follow the 30-day rule; loans under 60 days excluded.
  Evidence: `test_labels.py::test_thirty_days_late_is_still_good_and_thirty_one_is_not`, `::test_a_loan_issued_thirty_five_days_ago_is_excluded`, `::test_a_young_loan_is_never_counted_as_a_default`; `test_synth.py::test_labels_follow_the_thirty_day_rule`.
- [x] Time split 12/3/3 months; test_leakage passes.
  Evidence: `test_split_and_evaluate.py::test_time_split_uses_twelve_three_three_months`; `test_leakage.py::test_no_feature_uses_data_on_or_after_the_cutoff`, `::test_a_planted_future_row_is_caught`. Disclosed limit: no gap between the periods (model cards, `reports/REAL_LABEL_RESULTS.md`).
- [x] Both models trained; chosen one justified in the model card.
  Evidence: `test_boosted.py` (LightGBM), `test_model_card.py::test_the_card_says_why_this_model_and_states_the_time_split_gap`; the reason is in `reports/synthetic_bd/model_card.json` (`model_choice`).
- [x] Calibration plot exists and is acceptable on test; calibrator fitted on validation only.
  Evidence: `reports/synthetic_bd/calibration_test.png` (and one per public mode); `test_calibrate.py::test_out_of_fold_is_harder_than_checking_on_the_same_loans`; `test_final_test.py::test_the_plot_is_drawn_without_looking_again`. Test calibration error 0.008 (model card).
- [x] Metrics with bootstrap ranges; baselines beaten.
  Evidence: `test_split_and_evaluate.py::test_bootstrap_ranges_contain_the_point_estimate_and_repeat`; `test_train.py::test_model_beats_both_baselines_on_validation`, `::test_paired_gain_tells_a_real_improvement_from_none`; `reports/synthetic_bd/metrics.json`.
- [x] Ablation A to D at strengths 0, 0.5, 1; zero-signal test passes; D reported separately.
  Evidence: `test_zero_signal.py::test_delivery_features_add_nothing_at_signal_strength_zero`, `::test_with_full_signal_the_delivery_gain_shows`; `reports/ablation/delivery_gain.png`; model card section "Does delivery data add useful information?".
- [x] Questionnaire shown beside the score, not inside it.
  Evidence: `test_api.py::test_saving_the_questionnaire_updates_the_panel_but_not_the_score`; `test_features.py::test_questionnaire_sentences_are_marked_directional`; checked by hand on Oct 17 (D00003 stayed 64 after answers were saved).
- [x] Logistics-noise returns present; delivery reasons worded neutrally.
  Evidence: `test_synth.py::test_logistics_noise_returns_are_present`, `::test_logistics_noise_does_not_depend_on_reliability`; `test_features.py::test_delivery_return_reasons_are_neutral_observations`.
- [x] No sales or repeat-customer features from Mokam purchases.
  Evidence: `test_features.py::test_no_sales_or_repeat_customer_features`.
- [x] Group table by town_tier, shop_type, licence (and public-data audit columns) with bootstrap ranges; gaps flagged only when ranges do not overlap or persist across seeds.
  Evidence: `test_fairness.py::test_the_audit_catches_a_planted_gap`, `::test_the_audit_invents_no_gap_when_there_is_none`, `::test_a_gap_in_every_seed_is_flagged_even_within_the_ranges`, `::test_audit_columns_are_never_model_inputs`; `reports/<mode>/fairness.json`.
- [x] Every score returns probability, score, band, coverage, up to 3 reasons up and up to 3 down, model version.
  Evidence: `test_reasons.py::test_three_reasons_up_and_three_down`, `::test_reasons_sum_to_the_score`, `::test_score_card_matches_the_api_contract`; since Oct 18 also every input and the coverage checklist (`test_score_inputs.py`).

## Public data
- [x] kiva_asia, taiwan_cc and homecredit adapters pass test_adapters with fixtures.
  Evidence: each public mode's own file (the placeholders in `test_adapters.py` were replaced by these): `test_taiwan_cc.py`, `test_india_ltfs.py`, `test_homecredit.py`, `test_kiva_asia.py`, each with `::test_the_seven_tables_match_the_contract`.
- [x] Home Credit is labelled "country not stated" on its banner and model card.
  Evidence: `test_homecredit.py::test_the_country_is_never_claimed`; `test_api.py::test_health_banner_follows_the_data_mode`; `docs/model_card_homecredit.md`.
- [x] Real-label runs done; metrics with ranges compared to 0.70 benchmark and 0.95 alarm.
  Evidence: `reports/REAL_LABEL_RESULTS.md` (validation and test AUC with ranges against 0.70); the 0.95 alarm is `sanity.suspicious_auc`, checked in `src/model/evaluate.py`.
- [x] Audit-only columns never in the feature matrix (leakage whitelist test).
  Evidence: `test_taiwan_cc.py::test_audit_columns_are_kept_apart` (and the same test in `test_india_ltfs.py`, `test_homecredit.py`); `test_fairness.py::test_audit_columns_are_never_model_inputs`.
- [x] Raw public data not in git; docs/DATA_SOURCES.md lists links and licences.
  Evidence: `.gitignore` (`data/raw/`); `docs/DATA_SOURCES.md`; `docs/data_inventory.md`.

## System
- [x] No auto-approve/decline path (test_no_autodecision).
  Evidence: `test_no_autodecision.py` (every endpoint, every role: no loan status changes; no "approved/declined/eligible" on any screen).
- [x] Consent missing or revoked -> scoring refused.
  Evidence: `test_api.py::test_scoring_is_refused_without_valid_consent`, `::test_a_profile_without_consent_shows_no_behaviour`; `test_api_import_guard.py` (an upload cannot unlock a merchant); `test_consent_request.py::test_a_request_never_grants_consent`.
- [x] Roles enforced; audit entry on every profile read and decision.
  Evidence: `test_api.py::test_each_role_can_do_exactly_what_the_brief_says`, `::test_every_profile_read_writes_an_audit_entry`, `::test_reading_a_score_is_audited_too`, `::test_if_the_audit_entry_cannot_be_written_nothing_is_returned`.
- [x] Decisions append-only; override requires reason.
  Evidence: `test_master_data.py::test_decisions_are_append_only`, `::test_the_database_itself_refuses_to_change_a_decision`, `::test_an_override_without_a_written_reason_is_refused`; `test_no_autodecision.py::test_override_requires_a_written_reason`.
- [x] Banner names the data source and says "Decision support only." on every page.
  Evidence: `test_api.py::test_health_reports_the_mode_and_the_banner`; `test_model_card.py::test_every_card_names_its_source_and_says_decision_support_only`; the banner sits in the app shell above every page (`web/src/app/Banner.tsx`), checked on screenshots of every page on Oct 17.
- [x] The React dashboard calls only the API; no database keys or connection strings in the browser bundle or the repo.
  Evidence: `web/src/api/client.ts` is the only network code; a search of the built bundle (`web/dist/`) on Oct 18 found no database address or key; the only connection string in the repo is a fake example in `test_master_data.py`.
- [x] Tests pass on SQLite with no network; the same loader works against Supabase Postgres via `DATABASE_URL`.
  Evidence: `python tasks.py test` runs on SQLite with no network; `tests/test_postgres.py` was run on Oct 14 against a throwaway PostgreSQL 18.3 in Docker (PROJECT_BRIEF section 18, item 36): the full synthetic data loaded, and decisions and the audit log refused UPDATE, DELETE and TRUNCATE. It is skipped in normal runs, which have no throwaway database.
- [ ] The app runs locally without the internet (fallback for the venue), and the hosted copy on Hostinger works.
  Local part done: fonts are bundled (`web/src/fonts.ts`), `test_offline_demo.py`. **Open:** the hosted copy (deploy not done).

## Demo
- [x] Walk-through: thin-file merchant -> low coverage -> "Needs more info"; strong merchant -> reasons; override with reason; appears in decision log and audit.
  Evidence: done by hand by the lead on Oct 17 following `docs/LIVE_DEMO_GUIDE.md` (live import of D00001 to D00005, decisions on D00003, decision log, audit log). Repeat on the hosted copy.
- [x] Model card page shows limitations in plain words.
  Evidence: `test_model_card.py::test_the_card_uses_plain_words_and_clean_keys`, `::test_no_card_overclaims`; the "What should officers keep in mind?" section.
- [ ] Backup video recorded; DB backup made; slides match what the product really does.
  **Open:** video and slides not made yet. `python tasks.py backup` exists (`test_master_data.py::test_backup_copies_the_database_file`).
- [ ] Every teammate can explain their own folder.
  **Open:** a team rehearsal.

## Still open (Oct 18)
1. Deploy, then repeat the walk-through on the hosted copy.
2. Backup video, database backup, slides.
3. Team rehearsal.
4. Native-speaker review of the Bangla (not a checklist item, but needed before the demo).
