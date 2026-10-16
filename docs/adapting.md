# Adapting CredLens to another lender's data

Owner role: D (full-stack, Humayra), Phase 12. Written for an engineer at a lender or a platform who has their
own data, and for us the day ShopUp (or anyone) shares an extract.

The idea: **everything in CredLens reads seven tables, not a source.** A small piece of code, an *adapter*, turns
one source into those seven tables. The features, the model, the score, the coverage, the bands, the reasons, the
API and the dashboard do not change. This page is what that piece of code must do, where it is plugged in, and
what must be checked and re-set afterwards.

Read `docs/REAL_DATA_SWITCH.md` first for what to ask a partner and how to handle what arrives. This page is the
engineering half.

## 1. Three questions before any code

1. **What do you have?** For each of the seven tables below: do you have it, in full, for the same merchants and
   the same months? A table you do not have stays **empty**. Nothing is made up to fill it.
2. **What does "repaid in time" mean in your data?** Our rule: a loan is 1 (good) when every payment due was paid in
   full within 30 days of its due date, 0 when a payment came later or is still unpaid more than 30 days after its due
   date, and it has **no label** while it is younger than 60 days. The numbers are settings
   (`labels` in `config/default.yaml`). If your definition differs, write it down and change the setting; do not bend
   the data. If your file simply states the outcome of every loan (as public loan files do), list the mode in
   `labels.supplied_by_source` and the stated outcome is the label. A label is what happened, never a credit decision: do not map "approved" or "declined" to it.
3. **Do you hold a consent for each merchant, and may you use their data for this?** The `consents` table is not
   optional: **no valid consent, no score** is enforced in the scorer and the API. Without consents, nothing scores.

## 2. The seven tables

Every column below must be present, in any order, and no other column may be. `check_frame` (in
`src/adapters/base.py`) stops with the names of the missing and the unexpected columns.

```text
merchants:     merchant_id, onboarded_at, district, town_tier, shop_type, has_trade_license, consent_data_use, questionnaire_done
purchases:     purchase_id, merchant_id, purchase_date, amount_bdt, category, supplier_id
deliveries:    delivery_id, merchant_id, dispatched_at, delivered_at, status, return_reason, is_cod, cod_remitted_on_time
payments:      payment_id, merchant_id, loan_id, due_date, paid_date, amount_due_bdt, amount_paid_bdt
loans:         loan_id, merchant_id, issued_at, limit_bdt, outcome_label, label_observed_at
questionnaire: merchant_id, spend1, spend2, save1, save2, borrow1, borrow2, plan1, plan2, stress, confidence, answered_at
consents:      consent_id, merchant_id, purpose, data_categories, granted_at, expires_at, revoked_at
```

What each means, and the types the code expects (the full dictionary of the synthetic data is `src/synth/schemas.md`):

| Rule | Detail |
|---|---|
| Ids | Text. **Pseudonymised before they reach you or us**: no names, phone numbers, addresses or national ids anywhere. |
| Dates | Text, `YYYY-MM-DD`. Timestamps (`dispatched_at`, `delivered_at`): `YYYY-MM-DDTHH:MM:SS`. |
| Amounts | Numbers (the column names say `bdt`; the currency is your decision, but say so in the model card). |
| Yes/no | `True` / `False`. `cod_remitted_on_time` may be empty (not a cash-on-delivery parcel, not delivered yet). |
| `purchases` | What the merchant **buys** for stock. They are never sales or revenue, in the data or on any screen. |
| `deliveries.status` | `delivered`, `returned`, `failed` or `cancelled`. `return_reason` values `address_issue` and `rider_issue` mean a logistics problem that is not counted against the merchant. |
| `loans.outcome_label` | 1, 0, or empty while unknown. For data with payment records the labels are worked out from `payments` (`src/model/labels.py`); the column is then a check, not the source. |
| `merchants.town_tier`, `shop_type`, `has_trade_license` | **Audit columns.** Used only to check the model for gaps between groups, never as inputs. |
| `consents` | A consent holds if it was granted on or before "today", expires after it, and was not revoked on or before it. `data_categories` lists what it covers, separated by `|`. |

## 3. The adapter

Copy this, rename the class and the mode, and replace the body of `_read` and `audit_frame` with how *your*
export is read. Everything else stays. If your export already has these column names it is nearly done; if
not, build each table with `pd.DataFrame({"merchant_id": raw["client_ref"], ...})`, one table per method.

```python
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from src.adapters.base import DataAdapter, check_frame, empty_frame

BOOLEANS = {
    "merchants": ["has_trade_license", "consent_data_use", "questionnaire_done"],
    "deliveries": ["is_cod"],
}
NULLABLE_BOOLEANS = {"deliveries": ["cod_remitted_on_time"]}
NUMBERS = {"purchases": ["amount_bdt"], "payments": ["amount_due_bdt", "amount_paid_bdt"], "loans": ["limit_bdt"]}
WHOLE_NUMBERS = {
    "loans": ["outcome_label"],
    "questionnaire": ["spend1", "spend2", "save1", "save2", "borrow1", "borrow2", "plan1", "plan2", "stress", "confidence"],
}


class LenderXAdapter(DataAdapter):
    """Reads one lender's export: a folder with one CSV per table, named like the table."""

    mode = "lender_x"  # the name of the data mode (step 4 of "Plugging it in")

    def __init__(self, config, folder=None):
        super().__init__(config)
        # The export lives OUTSIDE the repository. Never commit it.
        self.folder = Path(folder or os.environ["CREDLENS_LENDER_DATA"])

    def _read(self, table: str) -> pd.DataFrame:
        path = self.folder / f"{table}.csv"
        if not path.exists():  # a stream the lender does not have stays empty: nothing is invented
            return empty_frame(table)
        frame = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
        for column in BOOLEANS.get(table, []):
            frame[column] = frame[column] == "True"
        for column in NULLABLE_BOOLEANS.get(table, []):
            frame[column] = frame[column].map({"True": True, "False": False}).astype("boolean")
        for column in NUMBERS.get(table, []):
            frame[column] = frame[column].astype(float)
        for column in WHOLE_NUMBERS.get(table, []):
            frame[column] = pd.to_numeric(frame[column]).astype("Int64")
        return check_frame(table, frame)  # refuses missing or unexpected columns, by name

    def load_merchants(self):
        return self._read("merchants")

    def load_purchases(self):
        return self._read("purchases")

    def load_deliveries(self):
        return self._read("deliveries")

    def load_payments(self):
        return self._read("payments")

    def load_loans(self):
        return self._read("loans")

    def load_questionnaire(self):
        return self._read("questionnaire")

    def load_consents(self):
        return self._read("consents")

    def audit_frame(self):
        """Group columns for the fairness audit. They are never passed to the model."""
        return self.load_merchants()[["merchant_id", "town_tier", "shop_type", "has_trade_license"]]
```

Rules every adapter follows (`src/adapters/base.py`):

- Each `load_*` returns **exactly** the contract columns. A table the source lacks returns `empty_frame(table)`.
- **A missing stream lowers coverage; it never lowers the score by itself.** A merchant without parcel data is
  shown "Needs more info" when coverage falls under the line, not a bad score. (Checked in the tests of this
  page: with every delivery removed, no delivery feature exists, the coverage item "deliveries present" is false,
  and coverage falls by that item's weight; by the weight of "recent activity" too for a merchant whose only
  recent activity was a parcel.)
- Never read an outcome or a group column into a feature. The group columns come back from `audit_frame()` and stay
  there.
- Never write into the raw export. Never copy it into the repository.

## 4. Plugging it in

The adapter is the first of several places that name a data mode. Nothing here is automatic, and some of the
places belong to the lead (`src/model/`, `src/features/`, `config/`): change them together, in one pull request.

| # | Where | What to add |
|---|---|---|
| 1 | `src/adapters/lender_x.py` | the adapter above |
| 2 | `src/adapters/factory.py`, `ADAPTERS` | `"lender_x": LenderXAdapter` |
| 3 | `src/config.py`, `VALID_MODES` and `SOURCE_LABELS` | the mode, and the sentence every screen shows for it: `"Public data: ..."` for open data, or e.g. `"Lender X data."`; the banner adds "Decision support only." |
| 4 | `tasks.py`, `VALID_MODES` | the same name (the file cannot import `src`, so the list is repeated) |
| 5 | `config/default.yaml` | `coverage_weights_by_mode.lender_x` (must sum to 1.0, see below), `fairness.audit_only_columns.lender_x`, and if your history is shorter than 18 months `split_by_mode.lender_x`; also the band lines under `score.by_mode.lender_x` (see section 6) |
| 6 | `src/db/load.py`, `LOADABLE_MODES` | the mode, if its tables are to be loaded into the database (profile, timeline, decisions and the audit log need them) |
| 7 | `src/model/model_card.py` | the plain-words entries of the mode (`SOURCES`, `READING`, `MODE_LIMITS`, `TEST_READING`): what the data is, what its results do and do not show |
| 8 | `web/src/lib/modes.ts` (`MODE_ORDER` and the labels) | the mode, so the data-source selector and the model-card tabs list it; then `cd web && npm run types` with the API running |

The API needs no change for a new mode: its list of data modes (`DataMode` in `src/api/schemas.py`) is read from
`VALID_MODES`.

**Known gap (Oct 16): the shared feature path is tied to the name `synthetic_bd`.** The features built from
`purchases`, `deliveries` and `payments` are looked up in two places by comparing the mode with `synthetic_bd`:
`features_for_mode` in `src/features/dictionary.py`, and `model_inputs` and `SIMPLER_MODELS` in
`src/model/inputs.py`. A new mode whose data has the shape of the contract therefore stops at training with
`The feature dictionary has no entries for data mode 'lender_x'`. The fix is small: let those two places treat
any mode that is built from the contract tables as they treat `synthetic_bd` (for example a list of such modes in
`config/default.yaml`). Ask the lead to make that change first. It was checked on Oct 16 with a throwaway
adapter that served the synthetic tables under the mode name `lender_x`: with only those two places changed,
features, labels, the time split, training, calibration, the score, band, coverage, the reasons in English and
Bangla and the banner all worked for the new mode. Until it is changed, a lender's data cannot run under a mode name of
its own, and running it under `synthetic_bd` would put "Synthetic demo data" on real merchants, which must never
happen.

**The six coverage items.** For a source built from the contract tables, coverage is the weighted checklist of
these six items, so `coverage_weights_by_mode.lender_x` must use exactly these names and sum to 1.0:
`history_6_months`, `purchases_present`, `payments_present`, `deliveries_present`, `questionnaire_done`,
`recent_activity_30d`. The synthetic weights are 0.25, 0.20, 0.20, 0.15, 0.10, 0.10; they are a starting point to
discuss, not a result. A lender with no parcel data gives `deliveries_present` the weight 0 and spreads it over the
others; otherwise every one of its merchants would sit under the "Needs more info" line.

**A source that is not shaped like the contract** (a credit bureau summary, card statements, a loan file: the way
our Taiwan, India, Home Credit and Kiva modes work) fills the seven tables as far as it can and returns
`source_records()`: one row per loan with only the columns known at decision time. It then needs its own feature
builder (`src/features/<mode>.py`, registered in `src/features/source_features.py`, which also holds
`MODEL_INPUTS`, the list of its model inputs), its own entries under
`source_features.<mode>` in `src/features/dictionary.yaml` (every input says which way it points, with sentences in
English and Bangla), and an entry in `src/model/inputs.py`. Read `src/adapters/taiwan_cc.py` and
`src/features/taiwan_cc.py` first: they are the smallest example. That is more work than the contract path.

## 5. Running it, in order

```
set CREDLENS_LENDER_DATA=D:\path\outside\the\repo\lender_x_export      (Linux: export CREDLENS_LENDER_DATA=...)
python tasks.py train --mode lender_x          # features, labels, split, model, calibration, report
python -m src.model.fairness --mode lender_x   # gaps between groups, from audit_frame()
python -m src.model.model_card --mode lender_x # the model card, written for this model version
python -m src.model.final_test --mode lender_x # the test months, ONCE per model (it is recorded)
```

Then start the API with `CREDLENS_DATA_MODE=lender_x`. The banner follows the mode by itself (it comes from
`GET /health`); the selector and the model-card tab need row 8 above.

Two limits to know: `python tasks.py data` generates only the synthetic data, so a lender's tables get into the
database by an extension of the loader (step 6 above) or, to show the idea, by the admin import page; and rows
imported through that page do not reach a score (the scorer reads the adapter's files, not the database).

## 6. What must be re-set and re-checked: nothing from the synthetic data carries over

- **Band lines** (Strong from 90, coverage line 45%, low-score warning under 70) were set from the synthetic
  scores. They are settings, not facts: set them again from the new data's validation scores
  (`score.by_mode.lender_x`).
- **Coverage weights**, **the label rule** and **the split months** (above).
- **The model card is written again** for the new model; every number on the old one is about other data. Results on
  a small real sample are reported as such: "small real sample, not a validation".
- **The group audit** (`fairness`): the audit columns of the lender (region, shop type, gender of owner ...) go in
  `audit_frame()` and `fairness.audit_only_columns`. They are never inputs. A gap is reported, not explained away.
- **The wording** in `docs/WORDING_AND_QA.md`: say "decision support", "the officer decides", "synthetic or public
  data" only where it is true. Do not say the model works for the lender's merchants before it has been validated on
  their outcomes.

## 7. Tests a new adapter should come with

Copy the pattern of `tests/test_adapters.py` and `tests/test_fixtures.py`, on a few hand-made rows (ids that start
with `FIX-`), never on the real export:

1. the factory returns your adapter for your mode;
2. every `load_*` returns exactly the contract columns (`check_frame`), and a missing file gives `empty_frame`;
3. ids are unique, every `merchant_id` and `loan_id` resolves;
4. the audit columns are not among the model inputs, and no outcome column is in the feature table
   (`tests/test_leakage.py` has the planted-leak pattern);
5. `python tasks.py test` and `python tasks.py lint` pass.

`tests/test_adapting_guide.py` checks this page itself: the column lists in section 2 equal the contract, the
adapter in section 3 runs and gives the same tables as the synthetic adapter on the fixture files, a wrong column
is refused by name, and a missing stream really lowers coverage without making up features.

## 8. Checklist before anyone is shown a score from new data

- [ ] A written definition of "repaid in time" and of "late"; the label setting matches it.
- [ ] Ids pseudonymised; no personal field in any table; the export is outside the repository.
- [ ] A consent record for every merchant; the `consents` table is real, not filled in to make the scorer run.
- [ ] A stream the source lacks is empty, and the coverage weights say so.
- [ ] Band lines, coverage weights and split months set from the new data.
- [ ] Group audit run; every gap written in the model card.
- [ ] The model card says what the data is and is not, in words a judge can read.
- [ ] The banner names the data source. No screen says approved, declined or eligible.
