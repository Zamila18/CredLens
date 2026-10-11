# DATASET_PLAN.md: public data strategy and brief fixes (CredLens)

Status: ShopUp data could not be collected. The hackathon rules say no proprietary, confidential or IP-protected data is required from the partner at any stage, and the final output is a working prototype or interactive mockup that the partner could implement. So public + calibrated synthetic data is a fully valid basis. The schema stays ShopUp-shaped so ShopUp (or any similar Asian merchant-lending FSP) can plug in later through an adapter.

Items marked VERIFY must be checked by Claude Code (via HUMAN STEP if a login is needed) (link opens, columns exist, licence allows use) before code depends on them.

---

## 1. The core fact that decides the plan

No public dataset contains what our design needs in one place: per-merchant wholesale purchases (Mokam) + parcel deliveries (REDX) + loan repayment outcomes (Baki). So we do not pick "one dataset". We use three data modes that run through the SAME pipeline (features → time split → model → calibration → SHAP reasons → coverage → bands → group audit):

| Mode | Purpose | Real labels? | Asian? | What it proves |
|---|---|---|---|---|
| `synthetic_bd` (main demo) | Full dashboard with all four streams, ShopUp-shaped | No (generated) | Bangladesh-calibrated | The complete product and the REDX hypothesis test (ablation incl. zero-signal control) |
| `kiva_asia` (real-label check, small business) | Same pipeline on real Asian micro-entrepreneur loans | Yes (paid vs defaulted) | Yes (filter to Asia) | The method works on real repayment outcomes of small Asian businesses |
| `homecredit` (real-label check, behaviour) | Same pipeline on real repayment-behaviour features | Yes (TARGET) | Lender operates mainly in Asia; country not stated in data | Payment-behaviour features (on-time ratio, days late, regularity) carry signal on real data |

Pitch line: "Full design on Bangladesh-calibrated synthetic data; method validated on real Asian repayment labels; ShopUp's data plugs in through the same adapter."

---

## 2. Dataset selection: what each candidate is for

Selection rules (apply to any new link a teammate finds):
1. Unit: is a row a borrower/business, or a country aggregate? Aggregates can only calibrate or go in the deck, never train.
2. Label: is there a real repayment outcome (paid / late / default)? No label → not a training set.
3. Timing: can every feature be computed from information known before the loan decision? If not, those columns are dropped (leakage).
4. Fit: how many of our feature groups (purchases, payments, deliveries, questionnaire, loan terms) can it fill?
5. Context: Asia-Pacific rows available? Small business / informal merchant rather than salaried consumer?
6. Licence: can we use it in a public demo? Can we redistribute? (If not: keep in `data/raw/`, never in git, download script only.)
7. Size: enough positives and negatives after filtering (aim for at least a few hundred of the minority class in test).

### 2.1 Use for training/evaluation (row-level, real labels)

**Kiva loan data (VERIFY current snapshot)**: https://www.kiva.org/build/data-snapshots (background on default modelling: https://blog.bigml.com/2013/09/10/model-of-the-week-predicting-kiva-loan-defaults/ , a Kaggle mirror: Data Science for Good: Kiva Crowdfunding / "additional kiva snapshot").
- Why: real micro-loans to small shopkeepers and traders, many in Asia (Philippines, Pakistan, Cambodia, Vietnam, Tajikistan, etc.; check whether Bangladesh rows exist). Closest public match to "small merchant credit in Asia".
- Label: `status` paid → 1, defaulted → 0. Drop fundraising, expired, refunded, in-repayment (outcome unknown, like our "loan younger than 60 days" rule).
- Usable pre-decision features: loan_amount, term_in_months, repayment_interval (monthly/irregular/bullet), sector and activity (filter to Retail, Food, Services), borrower_count, partner (field partner) ID and its historical stats computed as-of date, posted_time, currency/country.
- Audit-only (never model inputs): gender, country/region, rural flag if present. Same rule as town tier/shop type/licence.
- Drop (leakage): funded_amount if it is filled after posting, paid_amount, any repayment-schedule outcome, lender count if recorded after funding.
- Limits to state: defaults are rare (very imbalanced; report PR-AUC and top-k, not just AUC); no per-borrower transaction history, so purchase/delivery features are unavailable and coverage will be low; default is partly driven by field partner behaviour; Kiva lenders are not the FSP. Claim only "the method holds up on real Asian small-business repayment labels".

**Home Credit Default Risk (Kaggle)**: https://www.kaggle.com/competitions/home-credit-default-risk/data
- Why: real labels plus rich repayment history tables that map directly onto our payment features.
- Map: `installments_payments` → on_time_payment_ratio, mean_days_late, max_days_late, payment_regularity; `POS_CASH_balance` / `credit_card_balance` → transaction regularity, balance trend; `bureau` → prior credit count and delinquencies; `previous_application` → prior approvals/refusals.
- Use a subset (e.g. application_train + installments_payments + POS_CASH) to keep it light on a laptop. Sample to ~50k applicants if memory is tight.
- Audit-only: CODE_GENDER, DAYS_BIRTH-derived age band, region rating. Not inputs.
- Limits: consumer loans, not merchants; no dates (relative days only), so the time split must use a proxy (state this; or use random split with a clear note that it is weaker than our temporal rule). Kaggle competition data rules apply: VERIFY the rules allow non-commercial demo use; do not redistribute; never commit to git.

### 2.2 Use to calibrate the synthetic generator (Bangladesh first)

These are surveys and aggregates. They set realistic proportions and ranges; they never train the model.
- **Global Findex 2025 microdata, Bangladesh**: https://microdata.worldbank.org/index.php/catalog/7869 (free registration, no redistribution). Use for: share with an account, mobile money use, borrowing sources, saving, ability to raise emergency funds. Feeds generator priors (e.g. share of merchants paying digitally) and questionnaire answer distributions.
- **Global Findex 2021 microdata, Bangladesh**: https://microdata.worldbank.org/catalog/4615 (VERIFY link). Trend comparison only.
- **Bangladesh Bank MFS monthly statistics**: https://www.bb.org.bd/en/index.php/financialactivity/mfsdata. Use for: merchant payment growth and seasonality (Eid peaks) in the synthetic monthly series.
- **FRED / IMF FAS, Bangladesh mobile money value**: https://fred.stlouisfed.org/series/BGDFCMTVXDC. Deck context and growth sanity check.
- **ShopUp Series B press release**: https://shopup.com.bd/web/press/valar-ventures-shopup-bangladesh. Source for 73% of small retailers selling on credit and 27.5% formal-finance access (company statement). Use 73% everywhere unless the Daily Star article itself says 72%; quote one source consistently.
- **Bangladesh Bank / RAPID baseline financial inclusion survey 2025**: https://www.rapidbd.org/?p=4962. Description only for now; use if a data release exists (VERIFY).

### 2.3 Context and design references only (deck, questionnaire, benchmarks)
- CGAP, Leveraging Transactional Data for MSE Lending: https://www.cgap.org/research/publication/leveraging-transactional-data-for-micro-and-small-enterprise-lending. Benchmark: AUC around 0.70+ is considered useful for transactional-data MSE models. Use as the realistic target; treat AUC > 0.95 as a leakage alarm.
- Corner Shop Diaries (India, Indonesia): https://cornershop-msc-l-ift.com/ and Small Firm Diaries Indonesia: https://www.smallfirmdiaries.org/indonesia. Daily/weekly cash-flow rhythm and shock patterns for the generator (VERIFY whether raw data is downloadable; otherwise use published figures).
- India Informal Sector Enterprise Survey 2022: https://microdata.worldbank.org/index.php/catalog/6488. Merchant size distribution proxy for South Asia.
- FinHealth Score Toolkit: https://finhealthnetwork.org/wp-content/uploads/2021/11/FinHealthScoreToolkit-2021.pdf. Base wording for the 10-item questionnaire.

### 2.4 Not chosen (and why), so nobody re-proposes them
- Country-level tables (Findex download, FAS): no rows per borrower, no labels.
- Generic consumer credit sets (German Credit, Taiwan credit-card default): tiny or consumer-only; Home Credit already covers behaviour features better.
- E-commerce order sets from other regions (e.g. Brazil): not Asian, no credit label. Optional only as a reference for realistic return-rate ranges.

---

## 3. How to modify each dataset to fit our system

All three adapters must output the same data contract (PROJECT_BRIEF section 5). Columns a source cannot fill stay null, and coverage (weighted checklist) drops accordingly. This is the feature, not a bug: thin files go to "Needs more info".

| Contract table | synthetic_bd | kiva_asia | homecredit |
|---|---|---|---|
| merchants | generated (shop type, town tier, licence: audit only) | one row per loan; sector/activity → shop_type; country → audit group | one row per applicant; region rating → audit group |
| purchases (was "orders") | generated Mokam purchase history | null | null (or POS_CASH as a proxy, flagged) |
| payments | generated repayment/payment history | null (no history) | installments_payments |
| deliveries | generated REDX parcels with logistics-noise term | null | null |
| loans | generated Baki loans | the Kiva loan (amount, term, interval, posted date) | the application (amount, annuity, term) |
| questionnaire | generated, shown separately | null | null |
| consents | generated "platform consent" rows | synthetic consent = true (public data) | synthetic consent = true |

Common steps for each real-label adapter:
1. Download script only (`scripts/fetch_<source>.py` or manual instructions); raw files in `data/raw/<source>/`, gitignored.
2. Filter (Kiva: Asia + Retail/Food/Services + closed outcomes; Home Credit: optional sample).
3. Build the label with the same rule shape as ours (1 = repaid, 0 = defaulted or 30+ days late where available; drop unknown outcomes).
4. Leakage guard: whitelist columns known at decision time; unit test fails if a blacklisted column reaches the feature matrix.
5. Time split on decision date (Kiva posted_time). Home Credit has no absolute date: use a stratified random split and label the run "weaker split" in the model card.
6. Feature engineering through the existing dictionary; add new entries (EN/BN reason sentences) for source-specific features like `repayment_interval_irregular`.
7. Audit columns kept in a separate frame, never passed to the model.
8. Run baselines, LR, LightGBM, calibration, SHAP reasons, group audit with bootstrap ranges. Save a per-source model card.

---

## 4. Faults in the project brief and how to fix them (already applied in pack v2; keep them)

From the teammates' review, checked against our documents, plus our own.

1. **Mokam orders treated as sales.** Mokam is wholesale sourcing: the merchant BUYS stock. Rename to purchase features: purchase_frequency, purchase_regularity, basket_growth, supplier_repeat_share. Remove "repeat customer share" and "customers come back". If a sales proxy is needed, use REDX outgoing parcel volume (merchants who sell online). Update FEATURE_DICTIONARY, generator, reason sentences.
2. **Target user drift.** One sentence everywhere: "Small merchants new to ShopUp credit, with Mokam purchase history and, where they sell online, REDX parcels."
3. **72% vs 73%.** Use 73% with the ShopUp press release as source (or the exact Daily Star figure if re-checked). Keep 27.5% formal-finance access.
4. **Delivery returns as merchant fault.** Add `logistics_noise_share` to the generator (part of returns unrelated to repayment). Prefer merchant-attributable events (refused, wrong item). Reword reasons as neutral observations: "Return rate is higher than similar shops; this may reflect delivery conditions."
5. **Questionnaire inside the model.** Take it out of the headline score. Show it beside the score as its own indicator. Keep ablation set D as a separate finding.
6. **Account Aggregator wording.** Bangladesh has no AA rail. Say: India's AA, SGFinDex and Open Finance PH are design references; consent here is platform consent recorded in the consents table, and scoring is blocked without it.
7. **Mifos X promise.** Keep the plain statement: Mifos-style data model, Streamlit + FastAPI + SQLite build, one-day Docker spike as stretch, report the result honestly.
8. **REDX ablation is circular on synthetic data.** Add the real-label runs (kiva_asia, homecredit). Claim only that the method works on real labels; the REDX question needs partner data.
9. **Selection bias not stated.** Labels exist only for people who got credit. Add to known limits; propose a pilot with small starter limits to collect wider labels.
10. **5-point group gap rule is noisy on small groups.** Report bootstrap ranges per group; flag only when ranges do not overlap or the gap persists across seeds.
11. **Data plan out of date (our own).** Brief section 16 assumes ShopUp data or labels. Replace with this three-mode plan and the hackathon rule that no proprietary data is required.
12. **Benchmarks (our own).** Add CGAP's ~0.70 AUC as the realistic usefulness bar; keep AUC > 0.95 as a leakage alarm.
13. **Group columns on public data (our own).** Kiva gender/country and Home Credit gender/age are audit-only, same as town tier/shop type/licence.
14. **Licences (our own).** Findex microdata and Kaggle data must not be redistributed: download scripts only, `data/raw/` gitignored, sources listed in the model card.

Model card "Known limits" text: use section 3 of the teammates' review as written, plus: "Real-label checks use Kiva (Asian micro-entrepreneurs) and Home Credit (consumer loans). Neither is ShopUp data; they test the method, not ShopUp performance."

---

## 5. ShopUp alignment, later

When ShopUp (or another FSP) can share even a small extract, `src/adapters/shopup_real.py` maps it to the same contract. The first questions to ask: (1) Are Mokam rows purchases only? (2) Which merchants does Baki lend to? (3) Can REDX returns be split by reason (refused vs address vs rider)? (4) What is "late" in Baki's policy?
