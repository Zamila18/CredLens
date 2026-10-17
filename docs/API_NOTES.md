# API notes (Phase 9): what the dashboard needs to know

Owner role: D (full-stack). The shapes are in `src/api/schemas.py`; the running API publishes
them at `http://localhost:8000/openapi.json` and `/docs`. This page holds what the spec cannot say.

## Calling the API

- Every endpoint except `GET /health` needs the header `X-Demo-Token: <demo user id>`:
  `officer-1`, `officer-2`, `admin-1` or `viewer-1`. The role comes from the `users` table.
  **This is a demo role switch, not a login.** Say so if a judge asks.
- The browser may call from `http://localhost:5173` (Vite). For another origin set
  `CREDLENS_CORS_ORIGINS` (comma separated) before starting the API.
- The API builds the scorer once at start-up (about half a minute). Until it has finished, the port
  does not answer. It needs `python tasks.py data` and `python tasks.py train` first.

## Who may call what

| Endpoint | officer | admin | viewer |
|---|---|---|---|
| `GET /merchants`, `/merchants/{id}`, `/merchants/{id}/score`, `/merchants/{id}/consent`, `/decisions`, `/model/card` | yes | yes | yes |
| `POST /merchants/{id}/decision`, `POST /merchants/{id}/questionnaire`, `POST /merchants/{id}/consent-request` | yes | no | no |
| `GET /audit`, `POST /admin/import/{table}`, `POST /admin/import-bundle` | no | yes | no |

## Errors

Every error the API raises on purpose is `{"detail": {"code": "...", "message": "..."}}`.
A request with a wrong shape is the usual FastAPI 422.

| Status | `code` | Meaning |
|---|---|---|
| 401 | `missing_token`, `unknown_token` | no or unknown `X-Demo-Token` |
| 403 | `role_not_allowed` | this role may not do this |
| 403 | `consent_required` | **no valid consent: no score, no decision, no questionnaire.** Show "consent needed" |
| 403 | `consent_scope` | consent is valid but does not cover the questionnaire |
| 403 | `rows_not_shown` | Home Credit mode: totals only, no merchant pages |
| 404 | `unknown_merchant`, `unknown_table` | |
| 409 | `import_not_available` | a public data mode is active; the database holds only synthetic data |
| 409 | `consent_already_valid` | a consent request for a merchant whose consent is already valid: nothing to ask for |
| 409 | `no_pending_loan` | a decision on a merchant whose latest loan already has an outcome: nothing is waiting for a decision. Hide the decision form for such a merchant |
| 409 | `import_not_allowed` | an import of history or consent rows for a merchant of the original data (see Import) |
| 413 | `file_too_large` | import file over 10 MB |
| 422 | `bad_bundle` | the bundle upload is not a zip, holds no contract CSV, or has a file named after no contract table |
| 422 | (FastAPI) | override with no written reason, a reason over 2,000 characters, `approve`/`decline`, answer outside 1 to 5 ... |
| 500 | `data_mismatch` | the scorer and the database hold different data: `python tasks.py data --reset-db` |
| 503 | `scorer_not_ready`, `database_not_ready`, `not_started` | the message names the command to run |

## Things that behave in a way you might not expect

- **Queue.** `status` is `decided` when any officer has recorded a decision on the merchant (the
  decisions table has no loan id). Decided rows have `pending_since: null`. Pending rows come first,
  oldest first. A merchant without consent has `score`, `coverage` and `band` all null. There is no
  paging: about 4,200 rows on the synthetic data.
- **Profile without consent** says `consent_valid: false` and holds no behaviour at all: no summaries,
  no questionnaire, empty timeline. A stream with no records for that merchant is `null`.
- **90-day numbers in the profile** are the numbers the score was computed from, so they agree with
  the reasons. The timeline lists everything up to the last day in the data.
- **Score.** `summary_en` / `summary_bn` is a short paragraph built from the card itself (no
  language model): show it at the top of the score card, in the language the toggle picks. It
  describes; it never recommends lending or not. `banner` is not in the response; take it from
  `GET /health`. `code` in a reason is for
  logs; never show it. `baseline_score + shown contributions + other_contribution = score`.
  Since Oct 18 the card also has `inputs` (every model input in model order: `group`, `label`,
  `has_data`, `points`, the sentence and `detail` when there is one; `baseline_score` + all `points`
  = the exact score, and an input with no data has 0 points) and `coverage_items` (the coverage
  checklist: `item`, `weight`, `present`; coverage = the sum of the present weights). Show every input
  instead of "everything else", and the checklist beside the coverage.
- **Decision.** The score and model version are taken from the scorer on the server; whatever the
  request says about them is ignored.
- **Questionnaire.** Saving twice replaces the earlier answers (the audit log keeps who saved and when).
  The score never uses the questionnaire. Every consenting merchant's consent covers the
  questionnaire since Oct 15 (`python tasks.py data --reset-db` after pulling); a merchant whose
  consent does not cover it is refused with `consent_scope`.
- **Consent.** `GET /merchants/{id}/consent` reads the consent live from the database and is
  audited. There is no revoke endpoint on purpose: the scorer reads consent once at start-up,
  so a revoked consent would still be scored until a restart.
- **Audit.** A profile read and a score read each write one row *before* anything is returned. A
  refused or failed read writes none. `GET /audit` is newest first (`limit` 1 to 1000, default 200)
  and is itself audited.
- **Import.** The request body is the CSV file itself (`Content-Type: text/csv`). Add `?dry_run=true`
  to only check. Import in this order: merchants, loans, purchases, deliveries, payments,
  questionnaire, consents. An import never overwrites a row.
  **Imported merchants are scored (Oct 17).** After every import that loads rows, the API reads every
  merchant that is not in the original data from the database and scores it with the saved model and
  the same feature rules, as of the same "today" as the rest of the data. Nothing is retrained. A new
  merchant with a loan waiting and a valid consent appears in the review queue with a score, reasons
  and a band; one without consent is listed with no score. This also runs when the API starts, so
  imported merchants survive a restart.
  **Bundle import:** `POST /admin/import-bundle?dry_run=` (admin only, audited) takes a zip of contract
  CSVs (`Content-Type: application/zip`; files named `merchants.csv`, `loans.csv`, ...; a folder inside
  the zip is fine). The files are checked in the order above in ONE transaction, each against what the
  files before it would add. With `dry_run=true`, or when any file is refused as a whole (wrong
  columns), nothing is kept. The answer is `BundleReport`: `dry_run`, `loaded`, `tables` (one
  `ImportReport` per file), `new_merchants` (merchants of the bundle that can now be scored; link each
  to its page) and `note`. A bad upload (not a zip, no contract CSV, an unknown file name) is 422
  `bad_bundle`. The demo file is `data/demo/credlens_demo_bundle.zip` (`python -m src.synth.demo_batch`;
  `data/demo/EXPECTED.md` says what each merchant should show).
  **What an import may not do (409 `import_not_allowed`, nothing loaded, even with `dry_run`):**
  purchases, deliveries, payments, loans, questionnaire or consents rows may not name a merchant of the
  original data (their history and consent come from the source systems and the consent system; an
  uploaded consent row used to unlock a merchant's profile, F1, and an uploaded history row showed on
  the timeline while the score ignored it, F10). In a bundle, one such row refuses the whole bundle.
  The error lists the merchant ids it found (`detail.merchants`, at most 20). A merchant added by the
  import itself may get all of these rows, consent included: that is a lender bringing its own
  customers with its own consent records. Each refusal writes an audit entry `refused_import_<table>`
  (`refused_import_bundle` for a bundle). A history table needs the scorer: without it the answer is
  503 `scorer_not_ready`.
- **Model card.** Written per data mode by `python -m src.model.model_card --all-modes` into
  `reports/<mode>/model_card.json` (and `docs/model_card_<mode>.md`). `GET /model/card?mode=taiwan_cc`
  gives another mode's card, for the public data pages; without `mode`, the running mode's.
  `metrics` holds numbers and short texts (`data_source`, `label`, `what_this_shows`,
  `what_this_does_not_show`, `group_findings`, `inputs` with " | " between inputs, and on the
  synthetic card `ablation_runs`, which explains the `auc_A` to `auc_D` keys of `ablation`); show the
  texts as sentences. If the card was written for an older model version, its first limitation
  says so: show it. A mode with no written card gets a placeholder with no numbers.
- **Queue.** `low_score_warning` is in each row (null when there is no score).
- **Band lines.** The score card and the model card carry `band_rules`
  (`strong_min_score`, `min_coverage` as a share from 0 to 1, `low_score_warning_below`) for the
  card's data mode, read from the config. Show them beside the band ("Strong: score 90 or more and
  coverage 45% or more"). Take the band itself from the API; never work it out from these numbers.
- **Consent list.** `GET /consents?merchant_id=&status=&limit=&offset=` (every role, audited) gives
  one page of consent records for the consent page's main table: `consent_id`, `merchant_id`,
  `purpose`, `data_categories` (a list), `granted_at`, `expires_at`, `revoked_at` and `status`
  (`valid`, `expired`, `revoked`, `not_started`, worked out for `as_of`, the last day in the data,
  with the rule the scorer uses). `total` counts all pages; `counts` gives the records per status for
  the merchant filter (use it for tiles; it ignores the `status` filter). `limit` is 1 to 500
  (default 100). Newest consent last per merchant; ordered by merchant id.
- **Ready.** `GET /ready` (no token) is 200 when the database is open and the scorer is built,
  else 503 with the plain reasons. The API's port does not answer at all while the scorer is being
  built (30 to 60 seconds), so a script must treat "not answering" as "starting". `deploy/wait_for_api.py`
  does that.
- **Production.** With `CREDLENS_ENV=production` the API serves no `/docs`, `/redoc` or `/openapi.json`.
  `CREDLENS_CORS_ORIGINS` lists the browser origins allowed to call it (empty: none; unset: the
  Vite dev server).
- **Timeline.** Each event has `label` and `label_bn` (Bangla, Oct 16), for the dashboard's English/Bangla switch.
- **Model card in Bangla.** Every sentence in `metrics` has a Bangla twin `<key>_bn` (for example `label_bn`, `what_this_shows_bn`, `group_findings_bn`, `intended_use_bn`), and `limitations_bn` holds the limitations in Bangla (written from `src/model/model_card_bn.py`). A stale-card warning comes first in both lists.
- **Phase 13 changes (Oct 16), for the dashboard.**
  - *New error codes:* `import_not_allowed` (409; see Import), `no_pending_loan` (409; a decision on a merchant
    with no loan waiting), and the 422 for a written reason of more than 2,000 characters
    (`detail[0].loc` ends in `reason_text`; the limit is `maxLength` of `reason_text` in `/openapi.json`, and
    `api.reason_max_chars` in the config). Show a counter on the reason box.
  - *A double click is one decision.* The same officer, merchant, action and reason again within
    `api.duplicate_decision_seconds` (5) returns the earlier decision with HTTP **200** (a new one is **201**).
    Treat both as saved.
  - *`GET /decisions` can be paged.* `?limit=` and `?offset=` are optional; without them every decision is
    returned, as before. The header `X-Total-Count` holds how many decisions match (`merchant_id` filter
    included). A browser on another origin may read it (it is in `Access-Control-Expose-Headers`).
  - *New audit actions* (they appear in `GET /audit`, `action`): `view_queue` (every read of the queue, no
    merchant), `refused_score`, `refused_decision` and `refused_questionnaire` (an attempt on a merchant
    without consent, or, for a decision, on a merchant with no loan waiting; the merchant is named),
    `refused_import_<table>` (an import of consents, or of history rows for a scored merchant). Existing
    actions: `view_profile`, `view_score`, `view_consent`, `view_consents`, `record_decision`,
    `record_questionnaire`, `import_<table>`, `check_import_<table>`, `view_audit_log`. Show them in plain words.
  - *Two writes can no longer fail with HTTP 500 when many people use the demo at once:* the database waits up to
    30 seconds for its turn (`api.sqlite_busy_timeout_seconds`).
- **Nothing approves or declines credit.** The word "approve" appears in `src/db/mifos_load.py`: it is the
  Fineract API command used to replay old synthetic loans on a local Mifos test server, one loan after the
  other as they were issued. CredLens itself never approves anything: that file imports only the standard
  library and `src.db.mifos_adapter`, reads no score, and a test (`tests/test_no_autodecision.py`) checks it.
- **Known limit: consent has two readers.** The scorer reads the consent records once, when the API starts
  (from the generated files); the profile, the consent endpoints and the questionnaire read the database live.
  They agree because nothing in the API can change a consent: there is no revoke endpoint, and an import cannot add
  a consent or history for a merchant of the original data. Imported merchants are read from the database by
  both readers. A consent changed in the
  database by another route would be seen by the profile at once and by the score only after a restart.
- **Oct 17 changes, for the dashboard.**
  - *Decisions keep what was on screen:* `band_shown` and `coverage_shown` (0 to 1) beside `score_shown`.
    Empty on decisions recorded before Oct 17. Show all three in the decision log.
  - *`decided_at` is UTC* with no zone suffix. Show it in Bangladesh time (UTC+06:00).
  - *Live import:* `POST /admin/import-bundle`, consents for new merchants, and imported merchants
    scored (see Import). New error code `bad_bundle` (422); new audit actions `import_bundle`,
    `check_import_bundle`, `refused_import_bundle`.
  - The local database needs the new decision columns: `python tasks.py data --reset-db` once.
- **Oct 18 changes, for the dashboard.**
  - *Every input on the score card:* `inputs` and `coverage_items` (see Score).
  - *Ask for consent:* `POST /merchants/{id}/consent-request` (officers only, no body) records that an
    officer asked a merchant without a valid consent for one: an audit entry `request_consent`, and the
    answer `ConsentRequestOut` (`requested_by`, `requested_at` in UTC, `note`). It never creates, changes or
    revokes a consent and scores nothing; only the merchant can grant consent, in their own app.
    `GET /merchants/{id}/consent` lists the requests, newest first, in `consent_requests`. A merchant whose
    consent is already valid gets 409 `consent_already_valid`. No database change: requests live in the
    audit log.
- **Not built:** a consent revoke endpoint (see Consent).
