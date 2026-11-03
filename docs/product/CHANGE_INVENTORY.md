# CredLens change inventory (Phase 0)

Purpose: classify every uncommitted change on branch `platform-modification` (base `43dcc00`, main) so the unified-platform rebuild keeps what is valuable and removes what conflicts. Source plan: `C:\Users\ESHA\.claude\plans\giggly-weaving-cerf.md`.
Taken: 2026-11-01. Read-only; nothing was changed to produce this file except the file itself.

## Baseline (before any Phase 1 work)

| Check | Result |
|---|---|
| Changed paths (`git status --short`) | **117**: 56 modified, 4 deleted, 57 untracked (the "158" in the brief counts files inside new directories) |
| Committed since `43dcc00` | **Nothing.** All of the below exists only in this working tree |
| Model artifact `src/model/artifacts/synthetic_bd/model.joblib` | SHA-256 prefix **`a9fcc5d3`** (unchanged since `43dcc00`) |
| `ruff check .` | passes |
| `npx tsc -b`, `npm run lint`, `npm run build` | pass |
| `pytest tests` | see the Phase 0 report (full run recorded there) |

**Highest risk:** the redesigned public site (`web/src/pages/public/`, `web/src/assets/showcase/`, `web/src/components/Brand.tsx`, `Motion.tsx`) and the whole accounts/tenancy/intake layer are **untracked**. A disk failure or an accidental `git clean` would lose them. The team should make a safety commit and tag before Phase 1 (commands at the end).

## Classification by area

Verdicts: **Retain**, **Rework**, **Remove**. "Phase" is where the plan changes it.

### Modified tracked files (56)

| Path(s) | What changed | Verdict | Phase |
|---|---|---|---|
| `src/model/scoring.py` | `Scorer`: `set_imported`, `set_real`, `_rebuild` (real shops scored as of today) | Rework: stop exposing benchmark merchants; drop `set_imported`; keep `set_real` | 6 |
| `src/db/models.py` | accounts tables, `QualityReview`, `ConsentForm`, org/tenancy columns | Retain + extend (fresh DB, new role set) | 1 |
| `src/api/auth.py`, `src/api/state.py`, `src/api/main.py`, `src/api/common.py`, `src/config.py` | identify/require_roles, services, router wiring, config checks | Rework: cookie only, `platform_admin`/`fsr`, org-aware audit | 1 |
| `src/api/schemas.py` | Pydantic contracts for every new endpoint | Retain + extend | all |
| `src/api/routes_admin.py`, `routes_consents.py`, `routes_decisions.py`, `routes_merchants.py` | role lists, tenancy | Retain + rework for new roles | 1-6 |
| `src/api/imported.py`, `importer.py`, `profile.py` | import tracking, `refresh_real`, consent state | Retain; `imported.py` loses sandbox path | 1/6 |
| `src/db/backup.py`, `load.py`, `mifos_adapter.py` | backup/offline loaders | Retain (offline benchmark only) | 0 |
| `config/default.yaml` | `auth`, `api` limits, `quality`, `review.range_policy` (example), `consent_forms`, `organization` | Retain + extend; range policy becomes per-org versioned | 1/6 |
| `requirements.txt` | `openpyxl` | Retain | - |
| `.gitignore` | `data/uploads/` etc. | Retain | - |
| `tests/test_api.py`, `test_no_autodecision.py`, `test_reasons.py` | endpoint registries incl. new routes | Rework: replace demo-token fixtures with account factories | 1 |
| `README.md`, `docs/HANDOVER.md`, `docs/design/CHATGPT_DESIGN_BRIEF.md` | documentation | Retain; refresh at Phase 8 | 8 |
| `web/index.html`, `web/src/index.css`, `web/src/lib/i18n.ts` | fonts/theme tokens, i18n maps | **Retain** (design system) | - |
| `web/src/App.tsx`, `app/{AppShell,Sidebar,SessionProvider,session-context}.ts*`, `api/{client,errors,types,useApi}.ts`, `api/schema.d.ts` | routes, shell, session (sandbox + account modes) | Rework: new roles, no sandbox mode | 1/7 |
| `web/src/components/{Filters,Page}.tsx` | shared UI | Retain | - |
| `web/src/pages/{AuditPage,DecisionsPage,ConsentPage,QueuePage,PortfolioPage,ImportPage,DevStates}.tsx` | read pages built on benchmark data | `QueuePage`, `ConsentPage`, `ImportPage`, `DevStates`, `PortfolioPage`: **Remove/rebuild on org data**; Audit/Decisions: Retain | 5-7 |
| `web/src/pages/merchant/{MerchantPage,ScorePanels,Evidence,DecisionPanels,QuestionnaireForm}.tsx`, `scoreWords.ts`, `model/ModelCardParts.tsx` | assessment UI | **Retain + extend** (assessment history, persisted range) | 6 |

### Deleted tracked files (4)

| Path | Verdict |
|---|---|
| `web/src/app/Banner.tsx` | Keep deleted (repeated demo banner) |
| `web/src/pages/HomePage.tsx` | Keep deleted (replaced by `pages/public/LandingPage.tsx`) |
| `web/src/pages/ConsentDemoPage.tsx` | Keep deleted (merchant-facing demo; no merchant side) |
| `web/src/pages/merchant/ConsentRequestPanel.tsx` | Keep deleted (merchant app consent request) |

### Untracked backend (new work)

| Path | Purpose | Verdict | Phase |
|---|---|---|---|
| `src/accounts/{passwords,service,cli}.py` | scrypt hashing, accounts, setup codes, CLI | Rework: Argon2id, registration, invitations | 1 |
| `src/accounts/sandbox.py` | passwordless sandbox people | **Remove** | 1 |
| `src/api/tenancy.py` | merchant guard/scope/org helpers | **Retain + harden** | 1 |
| `src/api/deployment.py` | global readiness gate | Rework to per-org status | 1 |
| `src/api/routes_auth.py`, `routes_org.py` | login/logout/me, org accounts + assignments | Rework (`/demo/people` removed, registration added) | 1/3 |
| `src/api/routes_intake.py` | field workflow (~25 routes) | Rework: split into onboarding / daily / applications | 2-4 |
| `src/api/routes_consent_forms.py`, `src/intake/consent_forms.py` | one-page consent form + signed upload | Replaced by templates + PDF + OCR; keep upload validation and atomic-write pattern | 2 |
| `src/intake/{merchants,records,applications,visits,consent,policy,spreadsheet}.py` | intake rules | Retain; remove `sandbox_request()`; extend | 2-4 |
| `src/api/{review,quality,receipt,uploads}.py`, `routes_quality.py`, `routes_workspace.py` | readiness, quality, receipt, upload guards, workspace lists | Retain; range logic reworked; wire `uploads.py` | 4-6 |
| `src/api/routes_sources.py`, `src/connectors/*` | source registry and connector contract | Retain contract; remove synthetic feed from UI | 7 |
| `src/db/upgrade.py` | additive DB upgrade | Retain (future additive changes) | - |
| `src/model/operating_points.py`, `reports/synthetic_bd/operating_points.json` | band operating points | Retain | - |
| `tests/test_api_intake.py`, `test_application_scoring_safety.py`, `test_db_upgrade.py`, `test_intake_records.py`, `test_operating_points.py`, `test_spreadsheet.py` | tests for the above | Retain; fixtures reworked | 1 |
| `docs/audits/`, `docs/product/`, `docs/EVALUATION_AND_TOOLS.md` | audit, blueprint, evaluation notes | Retain as references | - |

### Untracked frontend (new work)

| Path | Verdict | Phase |
|---|---|---|
| `pages/public/*` (LandingPage, PublicLayout, HowItWorks, Sources, Trust, DemoEntry, catalog) and `assets/showcase/`, `components/Brand.tsx`, `Motion.tsx` | **Retain** the public site and its design. `DemoEntry` and the "Try the demo" buttons/footer link: **Remove**; add Register | 1 |
| `pages/auth/*` (Login, SetupPassword, AuthFrame) | Retain + add Register | 1 |
| `app/navigation.ts` | Rework for new roles | 1/7 |
| `components/{form,ConfirmDialog,EvidenceViz,Notice,StatusTag,Workspace}.tsx`, `lib/{fieldWords,sources,statuses}.ts`, `api/useSubmit.ts` | Retain; add DataGrid, Toast, Table, FileUpload | 7 |
| `pages/{ApplicationsPage,DirectoryPage,DashboardPage,SettingsPage,ImportsPage}.tsx`, `pages/dashboard/*` | Rework to org-derived data, empty onboarding state | 5 |
| `pages/org/{TeamPage,AssignmentsPage}.tsx` | Rework to employees/invitations/FSRs | 1/3 |
| `pages/field/*` | Rework into FSR workspace and daily grid | 4 |
| `pages/quality/*`, `pages/sources/*` | Retain | - |
| `pages/merchant/{ConsentForms,Review}.tsx`, `pages/ConsentFormPrint.tsx` | `Review` retain; consent form pieces replaced | 2 |

## Entry points to remove or replace (sandbox / demo)

| Where | What |
|---|---|
| `src/accounts/sandbox.py`, `GET /demo/people` (`routes_auth.py`), persona inserts in `src/db/upgrade.py` and `src/db/load.py` | demo people |
| `X-Demo-Token` handling in `src/api/auth.py` (`is_demo_user`), `SANDBOX_REQUEST` and `sandbox_request()` in `src/intake/policy.py` | demo authentication and simulated-record flags |
| `web/src/pages/public/DemoEntry.tsx`, route `demo`, "Try the demo" in `PublicLayout.tsx`/`LandingPage.tsx`/`HowItWorksPage.tsx` | demo entry |
| `web/src/app/Sidebar.tsx` `SandboxCard`, `AppShell.tsx` `DemoContext`, `pages/field/shared.tsx` `DemoLine`, session mode `sandbox` | demo switcher and banners |
| `QueuePage`, `ConsentPage`, `ImportPage`, `PortfolioPage`, `DevStates` (benchmark-based) | pages that list the synthetic benchmark |
| `src/connectors/sandbox_feed.py` in the UI | synthetic "feed" |

Removal is staged: UI entry points in Phase 1, the demo-token code only once the API tests run on real account fixtures (end of Phase 1).

## Preserved, do not modify

`src/features/*`, `src/model/{score,explain,train,calibrate,…}.py`, `src/model/artifacts/synthetic_bd/*` (hash `a9fcc5d3`), `src/adapters/*`, `src/synth/*`, `reports/*`, `data/raw/*`, `data/backups/*`, `data/app.db` (backup only), append-only triggers and provenance tables, `consent_state` gate, `uploads.py`, `spreadsheet.py` preview-token flow.

## Safety commit for the team (suggested; I do not run git)

```
git status
git add src/accounts src/connectors src/intake src/api tests src/db src/model config requirements.txt .gitignore
git commit -m "feat(platform): accounts, tenancy, intake, consent forms, quality, sources (pre-rebuild snapshot)"
git add web docs README.md reports/synthetic_bd/operating_points.json
git commit -m "feat(web): redesigned public site and workspace UI (pre-rebuild snapshot)"
git tag pre-unified-platform
```

Two commits keep the backend and the front end separately reviewable; the tag marks the rollback point before Phase 1.
