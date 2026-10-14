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
| `GET /merchants`, `/merchants/{id}`, `/merchants/{id}/score`, `/decisions` | yes | yes | yes |
| `POST /merchants/{id}/decision`, `POST /merchants/{id}/questionnaire` | yes | no | no |
| `GET /model/card` | no | yes | yes |
| `GET /audit`, `POST /admin/import/{table}` | no | yes | no |

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
| 413 | `file_too_large` | import file over 10 MB |
| 422 | (FastAPI) | override with no written reason, `approve`/`decline`, answer outside 1 to 5 ... |
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
- **Score.** `banner` is not in the response; take it from `GET /health`. `code` in a reason is for
  logs; never show it. `baseline_score + shown contributions + other_contribution = score`.
- **Decision.** The score and model version are taken from the scorer on the server; whatever the
  request says about them is ignored.
- **Questionnaire.** Saving twice replaces the earlier answers (the audit log keeps who saved and when).
  The score and the coverage do not change until the next `python tasks.py train` and API restart.
- **Audit.** A profile read and a score read each write one row *before* anything is returned. A
  refused or failed read writes none. `GET /audit` is newest first (`limit` 1 to 1000, default 200)
  and is itself audited.
- **Import.** The request body is the CSV file itself (`Content-Type: text/csv`). Add `?dry_run=true`
  to only check. Import in this order: merchants, loans, purchases, deliveries, payments,
  questionnaire, consents. An import never overwrites a row. Loaded rows change no score until the
  next train and restart.
- **Model card** is a placeholder (real model version, plain-words limits, no numbers) until
  `reports/<mode>/model_card.json` exists (Phase 11).
- **Not built, because the sample endpoints list has no such call:** a consent detail or revoke
  endpoint, and a `low_score_warning` field in the queue (it is in the score card).
