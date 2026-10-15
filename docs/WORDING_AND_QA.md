# WORDING_AND_QA.md: what we may claim, and answers to likely questions

## Say
- "Decision support for staff; the officer decides and records why."
- "Prototype on synthetic data. Results show our pipeline works and is honest; they say nothing about real merchants."
- "We treat REDX delivery data as a hypothesis, test it with an ablation and a zero-signal control, and report the result."
- "The design and code are reusable; each platform adds its own adapter, retrains and publishes its own model card."
- "We learned from Kaleidofin's approach." (the source is CGAP's Kaleidofin case in "Banking in Layers", cited in our Finverse result; read it before quoting any outcome, and never promise the same outcomes for CredLens)
- "We do not add invented history to real public records; each real dataset is scored on what it actually contains."
- "Finverse also recommends short financial diaries; that is our next pilot step, not part of this prototype."
- "Our data model follows Mifos X: merchants, loans and repayments export in its format, and we loaded a sample into a running Mifos X (Apache Fineract in Docker, on a laptop): 50 merchants, 85 loans, 73 repayments, nothing refused, and Mifos X's own loan statuses matched ours for all 85." Say "a sample, on a local test server", and that the scoring and the dashboard run beside Mifos X, not inside it.
- "73% of small retailers sell on credit; 27.5% have formal-finance access (ShopUp Series B press release)." The submission used 72% (Daily Star, 2021); if asked, say the source changed.

## Do not say
- "CredLens runs on Mifos X" or "is integrated into Mifos X": the dashboard and the model are separate; Mifos X received exported data in a one-off load.
- "Unexplored", "first of its kind", "nobody does this": platform lenders already score merchants from commerce data, and ShopUp already lends through Baki.
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
- Why believe the REDX result? Not yet. Synthetic runs show the pipeline finds a signal when one exists and none when absent. On real outcomes, only Taiwan's credit cards show the method working (test AUC 0.75, on loans held back until the end). India shows the thin-file problem itself (0.60), Home Credit's ranking comes mostly from a score bought from outside, and Kiva cannot be scored at all (its model ranks later loans the wrong way round). Say this plainly; never quote Kiva or India as support. The REDX question itself needs partner data; the same code runs on it.
- Why no ShopUp data? The hackathon requires no proprietary partner data. The schema is ShopUp-shaped, so their extract plugs in through an adapter.
- How does consent work in Bangladesh? Platform consent recorded in the consents table; scoring blocked without it. AA, SGFinDex and Open Finance PH are design references.
- What if returns come from riders? Part of synthetic returns is logistics noise; features prefer merchant-attributable events; reasons are neutral observations.
- Small-town or unlicensed shops? Audited by group with bootstrap ranges, never inputs; thin files land in "Needs more info", never a low band.
- Who are the labels for? Only people who got credit (selection bias). We propose small starter limits in a pilot.
- Always say: "synthetic or public data", "decision support, an officer decides", "REDX is a hypothesis we test".

## v3 answers (after the data work of Oct 12)
- Does this already exist? Yes, the scoring idea does: MYbank, Udaan and others lend to merchants from platform data, and ShopUp lends through Baki. Our contribution is how the score is used: an officer decides, coverage is shown apart from the score, reasons are in plain language, the delivery signal is tested with a control where it is absent, results are audited by group, and scoring needs consent.
- Say about delivery data: "Whether delivery reliability adds predictive value beyond purchases and payments is rarely tested in public; we test it openly, including a control where the signal is absent."
- Why 90% repayment in the synthetic data? It is our assumption. Published Bangladesh recovery rates are higher (98% microfinance, FY2023) but count eventual recovery, not 30-day lateness; other Asian datasets show 8 to 22% early defaults. The real figure needs a partner's data.
- Why 30 days? It follows the microfinance PAR30 convention and suits short-term merchant credit. It is one config value; we do not know ShopUp's own rule.
- Two figures for selling on credit: 73% of small retailers (ShopUp press release) and 52 to 56% of informal businesses in Dhaka, Chittagong and Cox's Bazar (World Bank survey, 2022). They describe different groups; quote each with its source.
- What does the India result show? Real Indian borrowers, half of them with no credit record. The outcome is missing the first instalment, an early-warning signal, not eventual default.
- Is Home Credit Asian data? We do not know; the data does not state its country. We label it "country not stated".
- Did you use data.org's Zindi Financial Health challenge? No, its files were locked after it closed. We cite it as related work.
- How does a new merchant's data get in? In production the lender's systems feed the adapter automatically. In the prototype an admin uploads CSV exports on the import page, where each file is checked against the data contract before loading; an officer records questionnaire answers on a form. Nobody types purchase or delivery records by hand.
