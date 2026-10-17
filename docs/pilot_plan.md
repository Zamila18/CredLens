# Pilot plan and pilot KPIs

Owner role: A (lead). Written Oct 18, 2026, from PROJECT_BRIEF section 17 (items 8 and 9) and section 18
(item 13). Promised in the Phase 2 submission ("pilot KPIs"). **None of these can be measured on synthetic
data**: they are what a pilot with a real lender would measure.

## Where the pilot sits

The 4-week roadmap is the **first small pilot** of Finverse's 12 to 24 month two-track plan. It is not the
whole plan, and it promises no outcome.

## What the pilot does (a proposal)

1. **Data, with consent:** one lender (ShopUp, or another platform) shares a small anonymised sample of past
   merchants with their loans and outcomes, under a data-sharing agreement and each merchant's consent
   (`docs/data_inventory.md`, `docs/adapting.md`).
2. **Retrain and measure:** the same pipeline is trained on that data, measured on later months it never saw,
   and the group audit is run. A new model card says what it shows and what it does not. Nothing reaches an
   officer before this.
3. **Small starter limits:** labels exist only for merchants who already received credit, so the pilot gives
   small starter limits to a few merchants the model knows less about, to learn about them safely.
4. **Officers use it beside their usual process** for a few hundred merchants; the score suggests, the officer
   decides and records why.
5. **Next step after the pilot:** a small financial-diaries study (about 40 merchants, 3 months), as Finverse
   recommends. Not built in this prototype.

## Pilot KPIs

| KPI | What it tells us | Where the prototype already records it |
|---|---|---|
| Time from application to decision | Whether the joined view saves officers time | Loan issue date and `decisions.decided_at` |
| Share of thin-file applications decided without extra manual data gathering | Whether thin files can be handled from platform data | Decisions on merchants under the coverage line, and how many were "Needs more info" |
| Override rate and agreement rate | How officers use the score (too few overrides can mean rubber-stamping; about half means the score is not helping) | Decision log; Portfolio question 3 |
| Share in "Needs more info" | How often the evidence is too thin | Review queue and Portfolio question 2 |
| Later: repayment outcomes of accepted merchants, on real data with the lender's permission | Whether the score ranks real merchants well, and whether any group is treated differently | Loan outcomes; model card and group audit, re-run on the pilot data |

## What may and may not be said

- The pilot **measures**; it does not assume the prototype's synthetic results carry over.
- No outcome is claimed for Kaleidofin: the Finverse case concerns user research and product design.
- Nothing in CredLens approves or declines credit, in the pilot or after it.
