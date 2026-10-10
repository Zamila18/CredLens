# Claude Code starter pack: CredLens (Merchant Readiness Dashboard, Team 4Bytes)

## What is in this pack
| File | Purpose |
|---|---|
| CLAUDE.md | Rules and working style Claude Code reads automatically |
| PROJECT_BRIEF.md | Source of truth: scope, stack, structure, data contract, API, pages, milestones |
| config/default.yaml | Every tunable number (labels, split, bands, coverage weights, fairness, sanity limits) |
| docs/MODEL_SPEC.md | Exactly how the model must work, with worked examples |
| docs/GENERATOR_SPEC.md | How the synthetic data must be built, including the REDX negative control |
| docs/FEATURE_DICTIONARY.md | All features with Bangla/English reason sentences |
| docs/PROMPTS.md | Phase-by-phase prompts to paste into Claude Code |
| docs/ACCEPTANCE_CHECKLIST.md | What must be true before the demo |
| docs/WORDING_AND_QA.md | Allowed claims and answers to judge questions |
| docs/DATA_REQUEST_SHOPUP.md | What to ask ShopUp for and how to manage it |
| docs/FINVERSE_ALIGNMENT.md | Quick map of Finverse recommendations to the build |
| docs/HUMAN_TODO.md | Things people must do (repo, installs, decisions, admin) |
| docs/PHASE0_PROMPT.md | The prompt to paste first: structure only, no git, no data work |
| docs/REAL_DATA_SWITCH.md | What to do if ShopUp gives labels only or a real extract |

## How to start
1. Put the whole pack in a new Git repo (root). Open it in Claude Code.
2. Do the "Before starting" items in docs/HUMAN_TODO.md.
3. Paste the prompt in docs/PHASE0_PROMPT.md (structure only). Review the files it lists. Commit them yourself: Claude Code never runs git commands that change the repo.
4. Data phases (1 onward) wait until the data path is decided. Default is synthetic; use Phase 1b if ShopUp sends labels or an extract.
