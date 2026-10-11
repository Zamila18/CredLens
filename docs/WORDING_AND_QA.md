# WORDING_AND_QA.md: what we may claim, and answers to likely questions

## Say
- "Decision support for staff; the officer decides and records why."
- "Prototype on synthetic data. Results show our pipeline works and is honest; they say nothing about real merchants."
- "We treat REDX delivery data as a hypothesis, test it with an ablation and a zero-signal control, and report the result."
- "The design and code are reusable; each platform adds its own adapter, retrains and publishes its own model card."
- "We learned from Kaleidofin's approach." (the source is CGAP's Kaleidofin case in "Banking in Layers", cited in our Finverse result; read it before quoting any outcome, and never promise the same outcomes for CredLens)
- "We do not add invented history to real public records; each real dataset is scored on what it actually contains."
- "Finverse also recommends short financial diaries; that is our next pilot step, not part of this prototype."
- "Mifos X-style data model with an export adapter." If the optional Docker spike was tried, add its result honestly; if it was not tried, say so.
- "73% of small retailers sell on credit; 27.5% have formal-finance access (ShopUp Series B press release)." The submission used 72% (Daily Star, 2021); if asked, say the source changed.

## Do not say
- "Automated approval", "AI decides", "proven", "works for all of Asia", "fair" (say "we measured gaps and report them"), "REDX data predicts repayment" (as fact), any outcome for other organisations.

## Q&A
- Are we building only for ShopUp? The demo uses ShopUp as the partner FSP, but the core is reusable: adapters, dictionary, thresholds and consent method change per platform.
- Do we need REDX data? Not to run. It may add signal beyond purchases and payments; ablation tests it. Missing REDX data lowers coverage, not the score.
- Why would REDX help? Parcel volume, returns and cash-on-delivery reliability are behavioural evidence of a working business for merchants with no bank history.
- Does the model give 0/1? No. It gives a probability; the score is probability x 100 after calibration. 0/1 are only training labels.
- Why a time-based split? A random split leaks the future into training and inflates results.
- Why calibration? So a score of 72 means about a 72% chance, not just a rank.
- Why SHAP and a dictionary? Officers need reasons in plain language, not feature names.
- How do you avoid unfairness? Group variables are audit-only; we report AUC, calibration and band shares by group with bootstrap ranges and flag gaps only when the ranges do not overlap; we do not claim fairness.
- What stops over-reliance on the score? Reasons next to the score, coverage warnings, mandatory written reasons for overrides, override-rate monitoring.
- Why trust synthetic data? We do not. We show the method is sound and ready to re-run on real data.
- What did you take from Finverse? Core + Context design, consent record and mock consent page, FinHealth-style 10-item questionnaire, Mifos X-style data model, data inventory, master-data test, pilot KPIs.
- What happens with real data? Request a small anonymised sample under consent; run the same pipeline; revalidate; publish a new model card.

## v2 answers (from the team review)
- Why believe the REDX result? Not yet. Synthetic runs show the pipeline finds a signal when one exists and none when absent. Real-label runs (Kiva Asia, Taiwan credit cards) show the method works on real outcomes. The REDX question itself needs partner data; the same code runs on it.
- Why no ShopUp data? The hackathon requires no proprietary partner data. The schema is ShopUp-shaped, so their extract plugs in through an adapter.
- How does consent work in Bangladesh? Platform consent recorded in the consents table; scoring blocked without it. AA, SGFinDex and Open Finance PH are design references.
- What if returns come from riders? Part of synthetic returns is logistics noise; features prefer merchant-attributable events; reasons are neutral observations.
- Small-town or unlicensed shops? Audited by group with bootstrap ranges, never inputs; thin files land in "Needs more info", never a low band.
- Who are the labels for? Only people who got credit (selection bias). We propose small starter limits in a pilot.
- Always say: "synthetic or public data", "decision support, an officer decides", "REDX is a hypothesis we test".
