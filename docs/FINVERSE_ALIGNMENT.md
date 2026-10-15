# FINVERSE_ALIGNMENT.md

Source: the team's Finverse result (data.org). Full rules are in section 13 of PROJECT_BRIEF.md; this is the quick map.

| Finverse theme | What we build | Where |
|---|---|---|
| Limited data availability and access | Starter kit from DATASET_PLAN, five data modes (synthetic_bd, taiwan_cc, india_ltfs, homecredit, kiva_asia), data inventory | docs/starter_kit.md and docs/data_inventory.md (still to write) |
| Consent rails (AA/SGFinDex as design references only) | platform consent: consents table, mock consent page, consent check before scoring | src/db, app page, API |
| Fragmented systems | Single merchant master table, master-data test, backup | tests, `python tasks.py backup` |
| Internal hub (Mifos X) | Mifos X-style data model, export adapter (A, the deliverable), Docker spike (B, only if time allows) | src/db/mifos_adapter.py |
| Missing contextual/subjective data | 10-item FinHealth-style questionnaire, four subscores, marked "directional", shown beside the score | panel + separate ablation D |
| Financial diaries (Corner Shop Diaries, Small Firm Diaries) | Not built. Used as references for the generator; a pilot with about 40 merchants over 3 months is named as the next step | roadmap slide |
| Open APIs and standards | FastAPI publishes an OpenAPI (Swagger) spec at /docs | src/api |
| Data-sharing practice | ODI data practices guide and UK ICO data sharing code referenced | docs/data_inventory.md |
| Starter kit contents | One-page schema map, Global Findex, IMF Financial Access Survey, national portals; Finverse regional sources (Data.gov.in, NDAP, SHRUG) as context | docs/starter_kit.md |
| Core + Context | Reusable core, per-platform adapters, config | PROJECT_BRIEF section 15 |
| Pilot plan | 4-week roadmap is the first small pilot of a 12 to 24 month two-track plan; pilot KPIs documented | docs |
| Skip what is not needed | No n8n, no RudderStack; Metabase optional | |

Wording: no outcome claims for Kaleidofin; do not claim a Mifos X integration unless the spike works.
