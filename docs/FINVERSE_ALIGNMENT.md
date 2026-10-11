# FINVERSE_ALIGNMENT.md

Source: the team's Finverse result (data.org). Full rules are in section 13 of PROJECT_BRIEF.md; this is the quick map.

| Finverse theme | What we build | Where |
|---|---|---|
| Limited data availability and access | Starter kit from DATASET_PLAN, three data modes (synthetic_bd, kiva_asia, homecredit), data inventory | docs/starter_kit.md, docs/data_inventory.md |
| Consent rails (AA/SGFinDex as design references only) | platform consent: consents table, mock consent page, consent check before scoring | src/db, app page, API |
| Fragmented systems | Single merchant master table, master-data test, backup | tests, `make backup` |
| Internal hub (Mifos X) | Mifos X-style data model, export adapter (A), Docker spike (B, stretch) | src/db/mifos_adapter.py |
| Missing contextual/subjective data | 10-item FinHealth-style questionnaire, four subscores, marked "directional", shown beside the score | panel + separate ablation D |
| Core + Context | Reusable core, per-platform adapters, config | PROJECT_BRIEF section 15 |
| Pilot plan | 4-week roadmap is the first small pilot of a 12 to 24 month two-track plan; pilot KPIs documented | docs |
| Skip what is not needed | No n8n, no RudderStack; Metabase optional | |

Wording: no outcome claims for Kaleidofin; do not claim a Mifos X integration unless the spike works.
