# Claude Code starter pack v2: CredLens (Team 4Bytes)

This replaces the earlier pack completely. Delete the old pack files from the repo before copying this one in.

## What is in this pack
| File | Purpose |
|---|---|
| CLAUDE.md | Rules, HUMAN STEP protocol, git rule; Claude Code reads it automatically |
| PROJECT_BRIEF.md | Source of truth; section 17 has the v2 data modes and review fixes |
| config/default.yaml | Every tunable number, including data.mode |
| docs/DATASET_PLAN.md | Which public datasets, why, how to map them, brief faults and fixes |
| docs/MODEL_SPEC.md | How the model must work, with worked examples and v2 additions |
| docs/GENERATOR_SPEC.md | Synthetic data design (purchases, logistics noise, Bangladesh calibration) |
| docs/FEATURE_DICTIONARY.md | Features with Bangla/English reason sentences |
| docs/PROMPTS.md | Phase 0 to 13 prompts to paste into Claude Code |
| docs/ACCEPTANCE_CHECKLIST.md | What must be true before the demo |
| docs/WORDING_AND_QA.md | Allowed claims and judge answers |
| docs/REAL_DATA_SWITCH.md, docs/DATA_REQUEST_SHOPUP.md | For later, if ShopUp shares data |
| docs/FINVERSE_ALIGNMENT.md | Finverse recommendations mapped to the build |
| docs/HUMAN_TODO.md | What people must do |

## How to start
1. In the repo, delete the old pack files (CLAUDE.md, PROJECT_BRIEF.md, README_FIRST.md, config/, docs/) and anything Claude Code generated from them.
2. Unzip this pack into the repo root.
3. Open the repo in VS Code, open Claude Code, and paste the Phase 0 prompt from docs/PROMPTS.md.
4. When Claude Code shows `HUMAN STEP NEEDED`, follow its steps and reply with the sentence it asks for.
5. After each phase: review, run `python tasks.py test`, commit yourself, then paste the next phase.
