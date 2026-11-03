# CredLens Product Recovery Blueprint

Status: **proposal for review.** Nothing in this document has been implemented. No
application code, database or model was changed to write it.
Date: 31 October 2026. Basis: the working tree audited in
`docs/audits/CREDLENS_END_TO_END_AUDIT.md` (branch `platform-modification`, HEAD `43dcc00`,
all later work uncommitted).

Each requirement below is marked with how it is delivered:

| Mark | Meaning |
|---|---|
| **REUSE** | Existing code or table, used as it is |
| **MODIFY** | Existing code or table, changed |
| **NEW** | New code or table |

---

## 1. Revised product definition

**CredLens is the daily operating system for an FSP's merchant-evidence work.** Sales
Representatives (SRs) visit assigned shops and record what they see. Merchants confirm or
dispute those records and give separate, informed consent for a credit assessment. An
independent verifier checks the evidence. A credit officer reviews only eligible evidence,
with an assessment that keeps four things apart:

- creditworthiness (the model's estimate);
- evidence coverage (how much exists);
- data reliability (how much is verified, disputed or flagged);
- prediction uncertainty;

and records a human decision.

What changes from today:

| Today | After recovery |
|---|---|
| Three demo roles chosen on a public page; the user id is the credential | Seven roles with real accounts, sessions and backend-enforced scope |
| Any officer can work on any shop of the organisation | An SR works on assigned shops only |
| Records count toward the score the moment they are saved | Only verified, undisputed, consented, non-duplicate records count |
| Merchant has no access (a static preview page) | Merchant has an OTP or assisted account for their own shop only |
| Data-quality review never changes what is scored | Lifecycle states decide scoring eligibility |
| One organisation in practice | Organisations created and administered in the product |

What stays (REUSE):

- the ML pipeline, the saved model (experimental baseline), coverage, the band rules and
  exact Shapley reasons;
- provenance and lineage;
- the source registry and connector contract;
- data-quality checks;
- append-only decisions and audit;
- the organisation guard;
- the Excel import engine;
- the bilingual words.

**Synthetic separation stays absolute.** The 20,000 benchmark merchants and the sandbox
feed remain in a sandbox organisation. Real organisations never see them, and nothing
synthetic is ever eligible evidence outside the sandbox (§11).

---

## 2. Roles and permission matrix

### 2.1 Roles

| Role | Scope | Obtains access | Authenticates | Today |
|---|---|---|---|---|
| **Platform Administrator** (`platform_admin`) | Whole platform, **not** organisation data by default | Created at install (CLI, one-off) | Password + second factor | NEW (nearest today: none) |
| **Organisation Administrator** (`org_admin`) | One organisation | Created by the platform admin | Password (+ second factor) | MODIFY from `admin` |
| **Sales Representative** (`sr`) | Shops assigned to them | Invited by the org admin | Password (phone-first login) | MODIFY from `officer` (field part) |
| **Supervisor / Evidence Verifier** (`verifier`) | Shops of their team/territory in one organisation | Invited by the org admin | Password | NEW |
| **Credit Officer / Reviewer** (`credit_officer`) | Assessment-ready shops in one organisation | Invited by the org admin | Password | MODIFY from `officer` (decision part) |
| **Merchant / Shop Owner** (`merchant`) | Their own shop(s) only | Linked by an SR when the shop is registered (phone number) | OTP to the registered phone, or an assisted session with an SR present | NEW |
| **Auditor** (`auditor`) | One organisation, read-only, including the audit log | Invited by the org admin | Password | MODIFY from `viewer` (justified: reviewers and regulators need read-only trails) |

One person can hold more than one staff role in one organisation (for example a small FSP
where a supervisor is also a credit officer). **Separation-of-duty rules apply per record,
not per account** (§5.3). A merchant account is never also a staff account.

### 2.2 Permission matrix (enforced in the API; the UI only mirrors it)

Abbreviations:
- **A**: allowed;
- **A\***: allowed within the user's scope only (own organisation, own assignments, own shop);
- **—**: not allowed.

| Capability | Platform admin | Org admin | SR | Verifier | Credit officer | Merchant | Auditor |
|---|---|---|---|---|---|---|---|
| Create organisations | A | — | — | — | — | — | — |
| Manage organisation settings | — | A\* | — | — | — | — | — |
| Invite or deactivate staff, set roles | A (org admins only) | A\* | — | — | — | — | — |
| Create or assign territories/shops to SRs | — | A\* | — | A\* (reassign in own team) | — | — | — |
| Register a shop | — | A\* | A\* (becomes assigned to them) | — | — | — | — |
| View a shop profile | — | A\* | A\* (assigned) | A\* | A\* (assessment-ready or decided) | A\* (own) | A\* (read) |
| Start a visit, add entries, save drafts | — | — | A\* (assigned) | — | — | — | — |
| Submit a day's records | — | — | A\* (assigned) | — | — | — | — |
| Create a correction of own submitted entry | — | — | A\* | — | — | — | — |
| Confirm or dispute an entry, request a correction | — | — | — | — | — | A\* (own shop) | — |
| Record consent (merchant decides; staff may assist) | — | — | A\* (assisted, assigned) | — | — | A\* (own) | — |
| Withdraw consent | — | — | A\* (assisted) | — | — | A\* (own) | — |
| Verify or reject evidence | — | — | — (never) | A\* (never their own submissions) | — | — | — |
| Mark a duplicate | — | — | — | A\* | — | — | — |
| View an assessment | — | — | — | — | A\* | — (sees own records and consent only) | A\* |
| Create an application | — | — | A\* (assisted) | — | A\* | A\* (request) | — |
| Record a credit decision | — | — | — | — | A\* (not if they verified this shop's evidence, unless the org allows a single-person FSP) | — | — |
| Manage data sources (connectors) | — | A\* | — | — | — | — | — |
| Bulk data-file import | — | A\* | — | — | — | — | — |
| Data-quality reviews | — | A\* | — | A\* | A\* (read) | — | A\* (read) |
| Audit log | Platform events | A\* | — | — | — | Own shop's history | A\* |
| Model card | A | A | A | A | A | — | A |
| Reports / export | — | A\* | — | — | A\* | — | A\* |

Rules every endpoint applies, in this order: authenticated session → membership in the
target organisation → role allows the action → **record scope** (assignment for an SR, own
shop for a merchant) → separation of duty. A failure at the organisation or scope step
answers **404** (as `merchant_guard` does today), so record ids cannot be probed.

---

## 3. SR daily operational workflow

### 3.1 Flow

```
Log in ─▶ "Today": assigned shops (territory, due follow-ups, disputes to fix)
   └─▶ Shop ─▶ Start visit (date, outcome) ─▶ add entries (purchase, sale-free stock receipt,
        delivery, repayment, cash/credit note, photo) ─▶ Save draft (any time, resumes later)
        └─▶ Review the day ─▶ Submit ─▶ "Submitted · waiting for the merchant"
   └─▶ "My submissions": status per entry (submitted / confirmed / disputed / verified / rejected)
   └─▶ Disputes & corrections inbox ─▶ create a correction (original kept) ─▶ resubmit
   └─▶ Follow-ups (from verifier or merchant) ─▶ complete
```

### 3.2 Requirements mapped

| # | Requirement | Delivery | Detail |
|---|---|---|---|
| 1 | Own account login | NEW | `auth` service, `user_credentials`, `sessions` (§9, §10) |
| 2 | Territory and assigned shops | NEW + REUSE | `shop_assignments` (NEW); list view REUSES `/field/shops` logic, filtered by assignment |
| 3 | Shop profile | MODIFY | `ShopTasks` page plus `/merchants/{id}/workflow`, scoped to the assignment |
| 4 | Dated visit | REUSE + MODIFY | `visits` table and `POST /merchants/{id}/visits`; the visit becomes the header that entries point to |
| 5 | Multiple entries in a visit | MODIFY | `purchases`, `deliveries` and `payments` stay the typed stores (no duplicate table). Each entry's `record_provenance` row gains `visit_id` |
| 6 | Drafts | NEW | `entry_drafts`: a mutable working area per SR, visit and shop. **Not evidence; never scored** |
| 7 | Submit daily records | NEW logic | `POST /visits/{id}/submit` turns the draft into typed records + provenance + `evidence_events: submitted` in one transaction (all or nothing) |
| 8 | Previous submissions and statuses | NEW view, REUSE data | Status comes from the latest `evidence_events` row per record |
| 9 | Corrections and disputes inbox | NEW | Driven by `evidence_events` (`disputed`, `correction_requested`) |
| 10 | Follow-up actions | NEW | `follow_ups` table (assigned to, due, linked record/visit, done event) |

Fields kept on every record (requirement list → where it lives):

| Field | Where |
|---|---|
| Shop identity | typed table `merchant_id` (REUSE) |
| Business date | typed table date column (REUSE) |
| Visit reference | `record_provenance.visit_id` (NEW column) |
| Submitted by | `record_provenance.actor` (REUSE) |
| Entry type | `record_provenance.record_type` (REUSE) |
| Amounts, quantities, attributes | typed columns (REUSE). `quantity`/`unit` for purchases: NEW nullable columns, only if the team confirms SRs record them |
| Notes | `record_provenance.note` (NEW nullable column); visits already have `note` |
| Supporting files | `evidence_files` (NEW; phase 3) |
| Created / submitted timestamps | `record_provenance.entered_at` (REUSE) + `evidence_events.at` for `submitted` |
| Record status | latest `evidence_events` row (NEW) |
| Verification history | all `evidence_events` rows (NEW, append-only) |

Existing guards kept: business date never after the calendar end (sandbox); the double-tap
check; the paper reference recognised again; consent category required per record type.
**Change:** today consent is required *before* recording. After recovery, evidence may be
collected **only with the merchant's consent to record** (§4.3). Consent to *assess* is
separate and is required before scoring.

---

## 4. Merchant review and consent workflow

### 4.1 Access

| Mode | How | Delivery |
|---|---|---|
| OTP | The merchant enters the registered phone and receives a 6-digit code (5-minute expiry, 5 attempts, rate-limited per phone and IP), then gets a session limited to their shop(s) | NEW (`otp_challenges`, SMS provider: **external dependency**) |
| Assisted | An SR opens "merchant review" on their device; a code is sent to the merchant's phone and the merchant reads it aloud; the event records `assisted_by` | NEW |
| Fallback (no phone) | Paper form signed; the verifier records the paper reference; marked weakest | REUSE pattern from the current consent `method` (paper form) |

In the sandbox, OTP codes are shown on screen and labelled **simulated** (no SMS sent).
Production requires an SMS provider (decision §15).

### 4.2 Reviewing records

The merchant sees their shop's submitted entries grouped by visit. For each entry:

| Action | Result |
|---|---|
| **Confirm** | `evidence_events: merchant_confirmed` |
| **Dispute** (with a reason) | `merchant_disputed`; the entry becomes ineligible until resolved |
| **Request correction** (with a reason) | `correction_requested`; appears in the SR's inbox |

Merchant confirmation is an **attestation**. It is shown as "confirmed by the shop owner",
never as "verified".

### 4.3 Consent (separate from record confirmation)

Two consents, each with its own purpose, categories, wording version and history:

| Consent | Purpose | Required for |
|---|---|---|
| Consent to record | SR may record and keep the shop's business entries | Creating records (REUSE today's check, re-labelled) |
| Consent to assess | The FSP may use the listed evidence for a credit assessment | Scoring and the credit officer's view |

- **Before agreeing**, the merchant sees: who will see the data, which categories, how long
  it is kept, that saying no has no penalty, and how to withdraw.
- **Withdrawal** sets `consents.revoked_at` (the column exists; REUSE) and adds a
  `consent_events` row `withdrawn` (MODIFY: new allowed value, §10). After withdrawal:
  - the shop is no longer assessable;
  - existing records are kept for audit but not scored;
  - this is shown to the credit officer.
- **History** is all `consent_events` of the shop (REUSE table).

---

## 5. Evidence verification lifecycle

### 5.1 States (one append-only event per transition, in `evidence_events`)

```
draft (entry_drafts, not evidence)
  └─submit─▶ SUBMITTED
                ├─merchant─▶ MERCHANT_CONFIRMED ──┐
                ├─merchant─▶ DISPUTED ──correction─▶ SUPERSEDED (original) + new record SUBMITTED
                │                 └─verifier resolves "stands"─▶ back to SUBMITTED
                └─(no merchant action)────────────┤
                                                  ▼
                                   verifier ─▶ VERIFIED  or  REJECTED (reason)
                                   verifier ─▶ DUPLICATE (points to the kept record)
```

### 5.2 What each state means for scoring

| Latest state | Eligible for scoring? |
|---|---|
| submitted, merchant_confirmed | No (not independently verified) |
| verified | **Yes** (if the other rules in §11 pass) |
| disputed, correction_requested | No |
| rejected, duplicate, superseded | No |

### 5.3 Separation of duty (checked in the API, not the UI)

- A verifier cannot verify a record whose `submitted` event actor is themselves → 403
  `own_submission`.
- A merchant event never moves a record to `verified`.
- A credit officer cannot decide on a shop whose evidence they verified, unless the
  organisation setting `single_person_fsp` is on, which is audited and shown on the
  decision.
- An SR cannot verify, cannot resolve their own dispute, and cannot decide.

### 5.4 Corrections

A correction is a **new** typed record whose provenance points to the original
(`supersedes_record_id` on the `evidence_events: superseded` row). The original row is
never edited or deleted; it stays readable with its full history.

### 5.5 Reuse of Workstream D

- The data-quality checks (look-alike shops, possible duplicates, stale or missing
  evidence, lapsed consent) are REUSED as the verifier's queue inputs.
- A data-quality "duplicate" review becomes a `DUPLICATE` evidence event (MODIFY), so it
  finally removes the record from scoring.

---

## 6. FSP credit assessment workflow

| Element shown | Source | Delivery |
|---|---|---|
| Business profile | merchants, merchant_profiles | REUSE |
| Verified, eligible evidence (and counts of ineligible by reason) | typed tables filtered by §11 | MODIFY (`review.py` evidence groups gain eligibility) |
| Historical activity, repayment behaviour | evidence panels, feature context | REUSE |
| Evidence completeness (coverage) | `score.py` coverage | REUSE (computed on eligible evidence only) |
| Data reliability | share verified / confirmed / disputed / flagged | NEW summary |
| Missing evidence | coverage checklist, evidence requests | REUSE |
| Data-quality warnings | `quality.py` | REUSE |
| Risk prediction | saved LR model, labelled "experimental baseline: trained on synthetic data" until real validation | REUSE (label MODIFY) |
| Supporting and contradicting factors | exact Shapley reasons | REUSE |
| Prediction uncertainty | per-merchant interval (bootstrap of the model on resamples), shown separately | NEW (phase 4; until then "not estimated" is stated) |
| Limitations | model card limits, thin-file note | REUSE + MODIFY (below the coverage line, lead with "not enough verified evidence") |
| Assessment history | `assessment_runs` (each run: model version, eligible-evidence fingerprint, score, coverage, band) | NEW |
| Decisions | `decisions` (append-only) | REUSE; decision links to the assessment run (NEW column) |

The scoring engine, features, weights and band lines are **not changed**. Only the **input
set** changes: eligible evidence instead of all evidence.

---

## 7. Dashboards and navigation per role

| Role | Home | Main navigation |
|---|---|---|
| Platform admin | Organisations | Organisations · Platform admins · System health |
| Org admin | Team & coverage | Team (users, roles) · Territories & assignments · Shops · Data sources · Data files · Settings · Audit |
| SR | **Today** (assigned shops, drafts, disputes, follow-ups) | Today · My shops · My submissions · Inbox (disputes/corrections) |
| Verifier | **Verification queue** (submitted records by shop, oldest first; own submissions excluded) | Queue · Shops · Data quality · History |
| Credit officer | **Assessments ready** (consent to assess + eligible evidence) | Ready · Applications · Decisions · Model card |
| Merchant | **My shop** (pending entries to review, consent status) | Review records · Consent · History |
| Auditor | Audit log | Audit · Decisions · Shops (read) · Data quality (read) |

Every list has search, filters, an empty state that says what to do next, a confirmation
after a submission, and recovery from errors (draft kept on a failed submit). The Bangla
words follow the current inline style until the message-catalogue work.

---

## 8. Frontend: retain, redesign, rebuild, remove

| Current page/component | Decision | Reason |
|---|---|---|
| Public site (`pages/public/*`) | Retain | Positioning is right; the sign-in entry changes |
| `/demo` demo-role entry | **Rebuild** as a real sign-in (staff) + OTP (merchant); demo entry only in the sandbox build | No mock users in production auth |
| App shell, sidebar, `navigation.ts` | Redesign | Menu per role (§7) from the session, not a demo-role selector |
| Dashboard (`DashboardPage`, `EvidencePanels`) | Redesign into role homes; keep the panels for org admin and credit officer, using eligible evidence | Charts after workflows |
| Field Mode (`pages/field/*`) | **Rebuild as the SR workspace**; reuse forms (`RecordsTask`, `VisitTask`, `ImportTask`, `NewShop`) inside a visit with drafts | Today each record saves immediately and alone |
| Consent task, `ConsentDemoPage` | Rebuild as the merchant consent flow (two consents, withdrawal) | The demo page is static |
| Merchant page (`pages/merchant/*`) | Redesign as the **credit officer's assessment**; retain score, coverage and reason panels | Add eligibility, reliability, history |
| Applications, Decisions | Retain + modify | Scope by role; link the decision to the assessment run |
| Review queue (`QueuePage`, benchmark-based) | Keep for the sandbox only | Benchmark merchants are not real shops |
| Directory | Retain (org admin, verifier) | — |
| Data quality | Retain; becomes part of the verifier queue | — |
| Data sources | Retain (org admin) | — |
| Imports, Data files | Retain (org admin; SR for Excel inside a visit) | — |
| Portfolio, Model card | Retain (credit officer, auditor, org admin) | — |
| Consent records | Redesign (org admin, auditor: read; per shop) | — |
| Audit | Retain + scope by role | — |
| Settings | Redesign as the organisation settings | — |
| `DevStates` | Remove from production builds | Developer page |
| NEW | Sign-in, OTP, Team, Assignments, SR Today, My submissions, Inbox, Merchant home, Merchant review, Verification queue, Assessment history | — |

---

## 9. Backend services and API changes

### 9.1 Services

| Service | Delivery | Notes |
|---|---|---|
| `auth` | NEW | Password hashing (argon2id, **needs a new dependency: approval**), sessions (random 256-bit token, stored hashed, expiry, revoke), login rate limiting, OTP issue/verify. The `X-Demo-Token` path is kept **only** when `environment = sandbox` and is refused otherwise |
| `access` | NEW, reusing `tenancy.py` | One function per request, `scope(user, merchant)` → membership, role, assignment, own-shop; `merchant_guard` generalised |
| `organizations` / `users` | NEW | CRUD with audit |
| `assignments` | NEW | Assign, reassign, end; history kept |
| `visits` / `drafts` | MODIFY `src/intake/visits.py`, `records.py` | Submit converts drafts into typed records in one transaction |
| `evidence lifecycle` | NEW | Transition rules (§5), separation of duty, events |
| `consent` | MODIFY `src/intake/consent.py` | Two purposes, withdrawal, OTP/assisted evidence |
| `eligibility` | NEW | One function `eligible_record_ids(session, merchant, as_of)`, used by scoring, review and dashboards |
| scoring input | MODIFY `src/api/imported.py:58` (`tables_for_merchants`) | Filter purchases, deliveries and payments to eligible ids. **No change to the model, features or weights** |
| `assessments` | NEW | Persist each run; decisions reference it |
| `quality` | REUSE | Feeds the verifier queue; duplicate review → lifecycle event |

### 9.2 API (new or changed; every route keeps the error shape and audit)

| Method | Route | Roles | Delivery |
|---|---|---|---|
| POST | /auth/login, /auth/logout, GET /auth/me | staff | NEW |
| POST | /auth/otp/request, /auth/otp/verify | merchant | NEW |
| POST/GET | /platform/organizations | platform_admin | NEW |
| GET/POST | /org/users, POST /org/users/{id}/deactivate | org_admin | NEW |
| GET/POST | /org/assignments, POST /org/assignments/{id}/end | org_admin, verifier (own team) | NEW |
| GET | /sr/today, /sr/shops | sr | NEW (reuses `/field/shops` code) |
| POST | /merchants/{id}/visits (start), PUT /visits/{id}/draft, POST /visits/{id}/submit | sr (assigned) | MODIFY + NEW |
| GET | /sr/submissions, /sr/inbox | sr | NEW |
| POST | /records/{type}/{id}/correction | sr (submitter) | NEW |
| GET | /me/shop, /me/records | merchant | NEW |
| POST | /me/records/{type}/{id}/confirm, /dispute, /correction-request | merchant | NEW |
| POST | /me/consents, /me/consents/{id}/withdraw (and assisted variants under /merchants/{id}/…) | merchant, sr (assisted) | MODIFY |
| GET | /verification/queue | verifier | NEW |
| POST | /records/{type}/{id}/verify, /reject, /duplicate, /resolve-dispute | verifier | NEW |
| GET | /assessments/ready, /merchants/{id}/assessment, /merchants/{id}/assessments | credit_officer, auditor | NEW (wraps `review` + `score`) |
| POST | /merchants/{id}/decision | credit_officer | MODIFY (links to the assessment run; separation of duty) |
| GET | /follow-ups, POST /follow-ups/{id}/done | sr, verifier | NEW |

Existing routes stay; their role lists change from `officer/admin/viewer` to the new roles,
with a sandbox compatibility mapping (officer → sr + credit_officer, admin → org_admin,
viewer → auditor) so current tests keep running while they are migrated.

---

## 10. Database architecture and migrations

Principles:

- No duplicate evidence tables. The typed tables stay the only store of business entries.
- Lifecycle, consent and audit history are append-only.
- Every migration is a separate, approved, backed-up step (the Workstream B/C/D procedure).

| ID | Change | Kind | Why it cannot be avoided | Risk |
|---|---|---|---|---|
| M1 | `memberships` (user_id, organization_id NULL for platform, role, status, created_by, created_at) | New table | `users.role` has a CHECK limited to officer/admin/viewer; SQLite cannot alter it. Also allows one person several roles | Low |
| M2 | `user_credentials` (user_id, password_hash, updated_at, failed_attempts, locked_until) and `sessions` (token_hash, user_id, created, expires, revoked_at, ip, user_agent) | New tables | Real authentication | Low |
| M3 | `users` + columns: `phone`, `email`, `status`, `created_at`, `merchant_id` (for merchant accounts) | Nullable columns | Accounts | Low |
| M4 | `otp_challenges` (phone_hash, code_hash, expires, attempts, purpose, used_at) | New table | Merchant OTP | Low |
| M5 | `shop_assignments` (merchant_id, sr_user_id, organization_id, territory, assigned_by, from, until) | New table, append-only by convention (ending = new row) | SR scope | Low |
| M6 | `entry_drafts` (draft_id, visit_id, sr_user_id, merchant_id, payload JSON, updated_at) | New mutable table | Drafts are not evidence | Low |
| M7 | `record_provenance` + `visit_id`, `note`, `superseded_by` | Nullable columns on an append-only table (ADD COLUMN is allowed; existing triggers block updates only) | Visit link, notes | Low |
| M8 | `evidence_events` (event_id, organization_id, record_type, record_id, merchant_id, event, actor, actor_role, reason, related_record_id, assisted_by, at) | New append-only table + 3 triggers | Lifecycle and verification history | Low |
| M9 | `consent_events.response` + `withdrawn`, and `consent_events.purpose` gains `record` / `assess` | **Table rebuild** (CHECK change). The table is **empty in `data/app.db`** today. Needs a new rebuild step in `src/db/upgrade.py` | Withdrawal history in the existing table. Alternative: a new `consent_withdrawals` table (no rebuild, slight duplication) | Medium (tooling) |
| M10 | `follow_ups` | New table | SR/verifier tasks | Low |
| M11 | `assessment_runs` + `decisions.assessment_run_id` (nullable column) | New table + column | Assessment history; link decisions | Low |
| M12 | `evidence_files` (+ storage folder outside the repo) | New table | Photos/receipts (phase 3; needs upload scanning) | Medium |
| M13 | `merchant_profiles` + `owner_name`, `phone` (nullable; personal data) | Nullable columns | Merchant access | Low (privacy review) |

Relationships:
- `memberships.user_id → users`;
- `shop_assignments.merchant_id → merchants`, `sr_user_id → users`;
- `evidence_events.(record_type, record_id)` → typed tables (no foreign key, as with
  provenance today);
- `entry_drafts.visit_id → visits`;
- `assessment_runs.merchant_id → merchants`.

Scoring eligibility needs no table: it is a query (§11).

On PostgreSQL, M9 is a plain constraint change.

---

## 11. Credit-scoring eligibility rules

A record counts toward a real organisation's assessment only if **all** of these hold at
the moment of assessment:

1. Its shop belongs to the assessing organisation.
2. A valid **consent to assess** covering its category exists (not expired, not withdrawn).
3. Its latest lifecycle state is `verified`.
4. Its verifier is not its submitter (enforced at verification, re-checked here).
5. It is not superseded, rejected or marked duplicate, and has no open dispute.
6. Its business date is on or before the assessment date (existing leakage rule; REUSE).
7. It is **not synthetic** (`record_provenance.simulated` is false). Synthetic records
   count only inside the sandbox organisation, and the screen says so.

Consequences, kept from today:

- **Missing or ineligible evidence lowers coverage, never the score** (neutral imputation;
  REUSE).
- Below the coverage line the band is "Needs more info", and the screen leads with "not
  enough verified evidence".
- Merchant confirmation alone never makes a record eligible.
- REDX-type deliveries and other optional sources only add coverage when present.

---

## 12. Existing versus proposed component map

| Requirement | Existing | Proposed |
|---|---|---|
| Organisations | `organizations`, `tenancy.py`, `merchant_guard` | REUSE + organisation CRUD (NEW) |
| Users and roles | `users` (3 roles, CHECK), demo token | M1–M3, auth service (NEW); demo token sandbox-only |
| SR scope | none (any officer) | `shop_assignments` (NEW) + `access.scope` |
| Shop registration | `src/intake/merchants.py`, `POST /merchants` | REUSE + auto-assign to the creating SR |
| Visits | `visits`, `src/intake/visits.py` | MODIFY: header for entries |
| Business entries | `purchases`/`deliveries`/`payments`, `src/intake/records.py` | REUSE stores; MODIFY flow (drafts → submit) |
| Drafts | none | `entry_drafts` (NEW) |
| Excel import | `src/intake/spreadsheet.py` | REUSE inside a visit; imported rows enter as `submitted` |
| Provenance | `record_provenance` | MODIFY (visit_id, note) |
| Lifecycle / verification | statuses `reviewed`/`independently_verified` defined but never set | `evidence_events` (NEW); old statuses left unused |
| Merchant access | none (static preview) | OTP/assisted + merchant routes (NEW) |
| Consent | `consents`, `consent_events`, `src/intake/consent.py` | MODIFY: two purposes, withdrawal |
| Data quality | `quality.py`, `quality_reviews` | REUSE; duplicate → lifecycle |
| Connectors | `src/connectors/*` | REUSE; synced rows enter as `submitted`, never auto-verified |
| Scoring | model, features, `score.py`, `explain.py` | REUSE unchanged; input filtered by eligibility |
| Assessment history | none | `assessment_runs` (NEW) |
| Decisions | `decisions` (append-only) | MODIFY: link to run, separation of duty |
| Audit | `audit_log` | REUSE; every new action writes an entry |

---

## 13. Security and privacy

- **Authentication.**
  - argon2id password hashes; login rate limiting and lockout.
  - Sessions as opaque random tokens stored hashed, with idle and absolute expiry; logout
    revokes the session.
  - Admins use a second factor.
  - The demo token is refused outside the sandbox. The **environment gate** refuses
    start-up outside the sandbox without auth configured (audit S1/S2).
- **Authorisation.**
  - Every route checks organisation, role, scope and separation of duty, in that order.
  - Out-of-scope requests answer 404.
  - Tests use **separate authenticated accounts** across two organisations and two SRs.
- **Merchant OTP.**
  - Codes stored hashed, valid 5 minutes, 5 attempts, rate-limited per phone and IP.
  - Sessions are limited to the merchant's own shop(s).
  - An assisted session records the SR.
- **Personal data.**
  - Phone and owner name are stored only with consent to record, are shown masked to
    roles that do not need them, and are never exported in bulk.
  - Retention and deletion rules are a decision (§15).
- **Uploads.** Request-size caps before reading, decompression limits, and evidence files
  stored outside the web root with type checks (audit S5/S6).
- **Evidence integrity.**
  - Append-only lifecycle.
  - Corrections supersede and never overwrite.
  - Maker-checker.
  - Scoring uses eligible records only (audit S3/S8).
- **Synthetic separation.** Sandbox organisation only; `simulated` flag never eligible
  elsewhere.

---

## 14. End-to-end acceptance criteria

### Milestone 1 (first vertical slice; must pass through the real UI and API on a persistent database)

Setup: two organisations (A, B); org A has two SRs (SR1, SR2), one verifier (V), one
credit officer (CO), two shops (S1 assigned to SR1, S2 assigned to SR2); org B has its own
admin and SR.

| # | Criterion |
|---|---|
| AC1 | Org admin A signs in with a password, creates SR1, SR2, V and CO, and assigns S1 to SR1 and S2 to SR2. Each action appears in the audit log |
| AC2 | SR1 signs in and sees **only S1** under Today. Opening S2 by its URL or API id answers 404. Org B's SR sees neither |
| AC3 | SR1 starts a visit on S1, adds three entries, and saves a draft. After signing out and back in, the draft is still there. Drafts appear nowhere in scoring, lists or dashboards |
| AC4 | SR1 submits. The three records exist in their typed tables with provenance (visit, submitter, timestamps) and a `submitted` event each. The submission confirmation lists them |
| AC5 | The merchant of S1 signs in by OTP (simulated in the sandbox) and sees only S1's entries. Confirms two and disputes one with a reason. The merchant of S2 cannot see S1 (404) |
| AC6 | SR1's inbox shows the dispute. SR1 creates a correction; the original stays visible as "superseded" with its history |
| AC7 | Consent to assess is recorded **separately** by the merchant. Confirming records did not create it. Withdrawing it later makes S1 not assessable while keeping the records |
| AC8 | V sees the verification queue without any record V submitted. V verifies two records and rejects none. SR1 calling the verify endpoint gets 403 |
| AC9 | CO sees S1 under "Assessments ready" only after consent to assess exists and at least one record is verified. The assessment shows eligible counts, ineligible counts by reason, coverage, reliability, reasons and the "experimental baseline" label |
| AC10 | The score is computed only from verified records. A disputed or unverified record changes nothing; verifying it changes the assessment, and both runs appear in the history |
| AC11 | CO records a decision linked to the assessment run. CO cannot decide on a shop whose evidence CO verified (unless the organisation is single-person, which is then shown) |
| AC12 | No step works with the demo token outside the sandbox organisation; every 403/404 above is covered by an automated API test using separate sessions |

### Later milestones

The same style of criteria applies to:
- follow-ups;
- Excel import inside a visit;
- connector rows entering as submitted;
- assessment uncertainty;
- auditor read-only access;
- organisation creation by the platform admin.

---

## 15. Phased implementation roadmap

Each phase ends only when its whole user journey works in the browser on a persistent
database, with automated API tests per role. Migrations are proposed, approved and applied
per phase.

| Phase | Scope | Migrations | Depends on | Complexity |
|---|---|---|---|---|
| **0. Safeguard** | Commit the current work in reviewed parts; environment gate; upload caps | none | Team git step | Low |
| **1. Accounts and scope** | Auth service, sessions, memberships, org admin user management, assignments, role-based shell, sandbox compatibility mapping | M1, M2, M3, M5 | **Approval of argon2 dependency** | Medium |
| **2. SR visit flow** | Visits with entries, drafts, submit, my submissions, corrections | M6, M7, M8 (+ evidence events for submit) | 1 | Medium |
| **3. Merchant review and consent** | OTP/assisted access, confirm/dispute/correction request, two consents, withdrawal | M4, M9, M13 | 1, 2; SMS provider decision (sandbox: simulated) | Medium |
| **4. Verification and eligibility** | Verifier queue, verify/reject/duplicate, separation of duty, eligibility filter in scoring, assessment page with eligibility | M8 (events), M11 | 2, 3 | Medium |
| **5. Assessment history and decisions** | Assessment runs, decision link, CO separation rule | M11 | 4 | Low |
| = **Milestone 1 complete** (AC1–AC12) | | | | |
| 6. Follow-ups, Excel in visit, connector rows as submitted | | M10 | 5 | Medium |
| 7. Evidence files | Uploads with scanning and storage | M12 | storage decision | Medium |
| 8. Platform admin, auditor, reports/exports | | — | 1 | Medium |
| 9. Uncertainty per merchant; real-data validation | | — | **External outcome data** | High |

### Blockers and decisions needed before Phase 1

1. **Commit strategy:** about 23,000 lines are still uncommitted.
2. **New dependency approval:** `argon2-cffi` (password hashing). Possibly `pyotp` later for
   staff second factors.
3. **SMS provider** for merchant OTP in production (sandbox shows codes on screen, marked
   simulated).
4. **M9:** rebuild `consent_events` (empty today) or add `consent_withdrawals`.
5. **Whether `single_person_fsp` is allowed** and how it is shown.
6. **Personal-data retention** for phone and owner name.
7. **Whether the benchmark queue page stays** in non-sandbox builds (recommended: sandbox
   only).

### Do not build

- Automatic verification from merchant confirmation or connector sync.
- Automatic merging of shops.
- Automatic approvals or limits.
- LLM-written explanations.
- New score weights or a second scoring engine.
- Charts that are not backed by eligible evidence.
