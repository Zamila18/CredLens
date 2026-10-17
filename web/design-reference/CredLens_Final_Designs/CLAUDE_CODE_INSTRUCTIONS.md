# CredLens — Claude Code implementation instructions

Build the working CredLens interface to closely match the approved images in this folder. This is an implementation handoff, not a request for another design concept. Read this file and `CHATGPT_DESIGN_BRIEF.md` completely, inspect every reference image, inspect the existing repository, and then implement the pages and interactions.

## 1. Authority and scope

- Preserve the approved colour theme, typography, shapes, spacing, charts, imagery, and page-specific layout. Do not replace the approved mint theme with a different design system.
- Implement actual responsive UI components, not screenshots displayed as whole pages. Text must be selectable, controls usable, charts data-driven, routes navigable, and layout accessible.
- Use the existing project's framework, package manager, API contracts, and conventions. Do not assume React, Laravel, or ASP.NET from unrelated projects. Read repository instructions first; extend rather than replace the application.
- Later user decisions in this handoff override the original brief: the review queue is a card grid, merchant detail is a single vertical sequence of full-width sections, Decision log is a table, and Portfolio uses five questions. No extra filter sidebar.
- The original brief remains authoritative for supplied business values and rules. Generated image text, spellings, chart geometry, icons, and numbers may contain rendering mistakes. Correct these in code rather than copying errors. Preserve the visual design while rendering accurate text and proportional charts.
- The user does not need additional Bangla mockup images. Implement full English/Bangla localisation in code for every page and state.
- This task authorizes local implementation and validation. Do not deploy, publish, or replace backend services merely to match the UI.

## 2. Reference map

All paths below are relative to this folder. `IMAGE_MANIFEST.json` gives actual PNG sizes. Images were generated at differing raster dimensions; the intended desktop viewport is 1440 CSS pixels, not the literal PNG width. Use image proportions and shared component measurements to reconstruct the desktop UI. Do not shrink body text to match a tall image thumbnail.

| Route / purpose | Primary visual reference |
| --- | --- |
| Shared design tokens and specimens | `00-design-system.png` |
| `/` | `01-home-desktop.png` |
| Home translation reference | `01-home-bangla.png` |
| `/queue` | `02-review-queue-desktop.png` |
| `/merchants/:id` | `03-merchant-desktop.png` |
| `/decisions` | `04-decision-log-desktop.png` |
| `/portfolio` | `05-portfolio-desktop.png` |
| `/model` | `06-model-card-desktop.png` |
| `/consent` | `07-consent-desktop.png` |
| `/demo/consent`, overview of states | `08-consent-desktop.png` |
| Consent state 1: Ask | `08-consent-page-1-ask.png` |
| Consent state 2: Questions opened | `08-consent-page-2-questions.png` |
| Consent state 3: Consent given | `08-consent-page-3-given.png` |
| Consent state 4: Not now | `08-consent-page-4-not-now.png` |
| Consent state 5: Withdrawn | `08-consent-page-5-withdrawn.png` |
| Additional phone-only Ask reference | `08-consent-phone-ask.png` |
| `/audit` | `09-audit-log-desktop.png` |
| `/admin/import` | `10-data-import-desktop.png` |
| Loading, empty, errors and public-mode components | `11-interface-states-desktop.png` |

The five separate consent-state images take precedence over the overview where there is a discrepancy. The phone hardware is a presentation frame on the desktop demo; it is not a second application shell on real mobile screens. Do not render a phone inside another phone.

## 3. Fidelity and shared visual system

Start with reusable primitives: application shell, banner, sidebar, language/role controls, page header, section card, metric tile, category chip, score ring, coverage bar, filters, table, chart frame, and state callout.

Token starting points from the approved sheet:

```css
--ink: #111B42;
--body: #40516C;
--page: #F6FAFA;
--card: #FFFFFF;
--border: #DCE7EB;
--accent: #008A6C;
--mint: #DFF7EF;
--strong: #16845B;
--review: #B7791F;
--needs-info: #6555A6;
--error: #C63535;
```

Use DM Sans for headings, Inter for Latin body text, and Noto Sans Bengali for Bangla. Prefer the existing font setup; self-host if the environment needs an offline build. Use approximately 32px page titles, 22px section headings, 32–40px key numbers, 16px body text, and at least 14px dense labels/table text. Use 8/16/24/32px spacing, approximately 14px card radii, and fine borders. Match page-specific exceptions in the images.

Keep subtle mint gradients/translucency where approved, especially headers and selected controls. Do not reintroduce bright glow, heavy glass bevels, waves, rainbow charts, or large dark green blocks. Text remains crisp and readable; adjust foreground shades within the approved palette for accessible contrast. Red is for actual errors, never thin evidence or a voluntary consent choice. Every category also has a written label.

Use understated consistent outline icons. Avoid adding icons to every label or changing the logo between pages because generated images differ. Do not add decorative sidebar icons merely because one PNG contains them; use a consistent restrained navigation treatment. Use the Home wordmark as the canonical brand.

The generic shop illustration in Home is the only substantial raster artwork required. Use an existing suitable asset, or extract only the artwork from the supplied Home image if no clean asset exists. Do not embed the page screenshot or the score/text overlay as the illustration. Recreate simple workflow drawings, rings, indicators, and charts using SVG/CSS or the existing chart library.

## 4. Page clarity, navigation, and roles

Every substantial card has a short title explaining what it answers, one plain answer sentence, then numbers/visuals. Give each number an everyday label or meaning. Use one discreet page note, `Sample values for the mockup`, when presenting illustrative fixtures; avoid badges on every card. Do not invent live facts to fill a missing field: use explicit unavailable text or an explicitly labelled fixture.

Keep the source banner, product name/tagline, data-mode indicator, English / বাংলা switch, and demo-role switch on all app pages. The canonical demo banner is `Synthetic demo data. Decision support only.` Show the configured model version, initially `synthetic_bd-20261015-005409-9db9d66`, as data, not an unchangeable string buried throughout the component tree.

Use Work: Review queue, Decision log, Portfolio; Trust: Model card, Consent, plus Audit log and Data import for Admin. Only the current route is active. Home must not remain active on consent subpages. The queue badge is the pending count, 4,177 in the supplied fixture. Source selection is configuration-driven, not an invented user-facing switch.

Four demo users: Officer 1 (`officer-1`), Officer 2 (`officer-2`), Admin (`admin-1`), Viewer (`viewer-1`). This is not authentication. Always display `A demo role switch, not a login.`

- Officers alone record decisions and questionnaire answers. They cannot access audit/import.
- Admin reads all pages and performs data import, but does not record merchant decisions or habits answers.
- Viewer is read-only.
- Hide unauthorized navigation and protect direct route/actions too. Use existing server permissions when available, not just disabled buttons.
- Read-only merchant copy must name the actual selected identity, not always viewer-1.

Public modes show source-supported totals/model cards only. No public merchant profiles or public review queue; never render Home Credit row-level data. The queue public-mode message belongs to its selected source, not a synthetic banner with misleading public data.

## 5. Non-negotiable domain behaviour

1. A readiness score is calibrated repayment probability ×100. Coverage is a separate evidence-completeness percentage. Whenever an individual score appears, also show its category and coverage, including decision history and previews.
2. Coverage <45% means Needs more info, regardless of score. Otherwise score ≥90 means Strong; lower means Review. Score <70 adds `Review · low score` and `Low score: read every reason before deciding.`
3. No valid consent means no score, no evidence records, no decision form, and no questionnaire. Do not fake a zero score.
4. Four decision actions only: Accept suggestion; Override: raise; Override: lower; Needs more info. Both overrides require a nonblank written reason. Trim whitespace; validate on client and server where applicable.
5. Decisions are append-only. Save the score snapshot, model version, officer, timestamp, action and reason. Never implement edit/delete. A later decision adds another record.
6. Questionnaire answers are directional, never model inputs for the headline score. Saving answers does not change readiness.
7. Mokam is stock purchased by the shop, not its sales. REDX is outbound deliveries. Baki is credit/repayment.
8. Merchant identity is an ID, district/tier/type, not a person's name or portrait.
9. No loan-approval/decline/eligibility flows, login, sign-up, prices, or unsupported claims of fairness or real-world proof. `Rows rejected` in file validation is not a lending verdict and is allowed.

## 6. Page-specific build directions

### Home

Reproduce the approved original composition: fixed desktop shell, source banner, split hero with shop artwork and score overlay, two real navigation CTAs, four Today tiles, three workflow steps, trust statements, source strip and footer. Counts: pending 4,177; needs info 611; consent missing 200; decided 1. Hero merchant M000031: score90, Strong, coverage65%. Public sources say `public data, not ShopUp data`. Add plain explanatory helper copy where needed without expanding into a new marketing site.

### Review queue

Use the finalized two-by-two merchant card grid on desktop, not a table or list. Horizontal search/status/category/tier/type filters, no extra filter sidebar. Each scored card has a circular score gauge and an independent coverage meter; unknown-consent card has a lock state. Keep card heights and action alignment consistent.

| Merchant | Location | Type | Score/category/coverage | Supplied dates |
| --- | --- | --- | --- | --- |
| M000031 | Sylhet · city | grocery | 90 / Strong /65% | Onboarded27 Jan2026 |
| M008824 | Narayanganj · metro | grocery | 91 / Needs more info /35% | Waiting1 Jul2026 |
| M001356 | Noakhali · small town | electronics | 66 / Review · low score /45% | Waiting1 Jul2026 |
| M019714 | Chattogram · metro | pharmacy | Consent needed; no score | Waiting2 Jul2026 |

The 91 ring/number is muted but readable. Open routes to the corresponding merchant. Filters/search combine, empty state works, and pagination is driven by actual data. The visual fixture says page1 of84 and1–50 of4,178; do not pretend four hardcoded cards are all50 records. Seed adequate data or clearly use fixture pagination through an adapter.

### Merchant detail

The final layout is a single scrolling sequence of full-width sections: identity header → readiness overview → evidence → score reasons → unified timeline → financial habits → limitations → consent → decision → history. Do not restore the original two-column brief layout. Inline metrics within a section are fine.

M000031 data: purchases ৳1,49,960 in **18** purchases, categories1, weeks active11; deliveries21, delivered85.7%, returned9.5%, failed4.8%, COD on time92.3%; payments0% on time across1 repayment, average7.0 days late. Some image lettering reads16 purchases: that is a generated-image error; use18.

Summary precedes ring90/100, Strong, and separate65% coverage. Copy the explanation and six reason sentences/values from the brief. Contribution bars must be proportional around zero: +1.66,+1.28,+0.63,−4.30,−0.83,−0.58. Keep observations-not-causes language. Do not derive a fake high-precision reconstructed score from rounded contribution labels; retain the supplied illustrative arithmetic as rounded explanatory copy.

Timeline: filters All/Purchases/Deliveries/Payments/Loans; newest first. Explicit source/type, date, event, amount/status. For the recorded late payment label Due date → Paid date and7 days late. `Payment due; no payment recorded` does not automatically mean late. Unknown dates/amounts must not be fabricated in the live UI. The screenshot dates shown as dashes are missing fixture values, not a required visual design. Display actual API dates when present, and meaningful unavailable text otherwise. Mark the sample ৳40,000 loan and214 event count as fixtures where used.

Habits: M000031 has no answers. The approved image additionally shows a clearly labelled answered-state preview from **M007421**, not M000031: Spend1.5/5, Save2.5/5, Borrow1.0/5, Plan2.5/5; stress4/5 (5=a lot), confidence3/5, answered2 Apr2026. Preserve this distinction. If showing the preview in demo mode, keep its attribution explicit. Never attach these answers to the wrong merchant or persist them as submitted values. Bars fill30%,50%,20%,50%. Stress is not a positive performance metric.

Consent record C000030: purpose Credit readiness assessment, granted27 Jan2026, expires27 Jan2028, not revoked, scopes purchases/deliveries/payments/questionnaire, checked as of30 Aug2026 (dataset reference day). Do not silently evaluate historical demo consent with the computer's current date; honour the API/demo reference-date convention and label it.

Implement the three additional detail states from the brief using the same components even though separate final images are not supplied: M008824 insufficient coverage; M001356 low score; M019714 no consent. The first two still show reasons and guards supported by their data; no-consent hides evidence/decision/habits. Do not invent unseen record values.

### Decision log

Use the latest finalized **table** reference, not earlier large-card versions. Columns When, Merchant, Score at the time of the decision (category+coverage), Action, Why, Officer. Show all four sample action types, actual timestamps, Bangladesh timezone label, common model version with explanation, append-only notice and `New decisions are recorded on a merchant's page.`

Sample fixture records: M000031 Accept suggestion16 Oct2026 14:35 officer-1; M001356 Override: raise16 Oct2026 13:50 officer-2; M000031 Override: lower16 Oct2026 12:20 officer-1; M008824 Needs more info15 Oct2026 16:10 officer-2. Use the written reasons visible in the final image as fictional fixtures. The score is the original snapshot, not an invented revised score. Summary8 of10 accepted,2 of2 overrides explained,2 requests for info describes a larger sample than the four visible rows; do not incorrectly calculate it from only those rows or imply four records are the complete dataset.

### Portfolio

Preserve the approved five-question layout and top `Portfolio in one minute` summary. Question → plain answer → data visual → meaning. No unexplained jargon-only card titles.

1. Do the bands mean anything? Validation5,853 loans; Strong95.2% repaid/share56%; Review82.1%/29%; Needs more info88.3%/15%. Explain thin files need evidence, not a lower score.
2. How much work is waiting today?4,178 total; Strong2,197; Review1,170; needs info611; no consent200. Every View in queue link applies its category filter. Outcomes unknown. Note: original brief counts total queue while also describing pending4,177/decided1. For actual API data use accurate waiting/total language; do not silently change business counts to reconcile demo copy.
3. How do officers use the score?8 accepts,2 explained overrides,2 requests. Override rate2/(8+2)=20%; info requests excluded. No invented healthy range.
4. When were decisions made? Sample13/14/15/16 Oct2026 counts2/3/3/4; clear axis and bar labels.
5. Does the model work differently for groups? Readable group table and no-gap explanation. Group statistics in the mockup are illustrative, not measured results from the running model. They overlap; do not sum their counts. Report gaps without a fairness claim.

### Model card

Use the finalized clean version with restrained charts, no dense multi-chart poster. Source tabs must update content with the correct source code. Technical details are expandable accordions: inputs, model choice/later test, ten calibration groups, A/B/C/D comparison, detailed group metrics, other public sources. They must open and show actual content, not dead decorative rows.

Canonical values: logistic regression; time split13,318/5,853/6,023; validation AUC.710 (range.688–.729); purchases-only.667; gain+.043 (range+.028–+.060); LightGBM improvement+.0128; Brier.0819 vs baseline.0871; calibration error.012; validation repaid90.4%; later AUC.728(range.707–.749),gain+.018; below45% coverage AUC.583 vs at/above.734; lowest20 loans55% not repaid vs10%overall; planted strength0/.5/1 gives AUC gain.000/.025/.055.

Do not fabricate ROC curves or confidence intervals from scalar metrics. Clearly distinguish illustrative calibration/group table rows from true published model outputs. For production replace chart fixtures with API/model-card data. Preserve synthetic-data limitation, later-test-not-clean-holdout caveat, questionnaire exclusion, and the statement that planted-signal tests do not prove REDX predicts repayment. Public validation→test AUC: Taiwan.743→.752; India.611→.599 with state gaps; Home Credit.746→.723; Kiva.644→.435 with must-not-use warning. Do not infer real-world effectiveness from sample charts.

### Consent administration

Use final table with inline expanded record, no side drawer. Purpose/minimum-data/questionnaire explanations, valid3,978 and no-valid200 counts with meaning. Filters/search work; View record expands the correct merchant and is an audited read. No revoke button in staff view. `Not revoked` is text, not missing data. `See what the merchant sees` routes to the demo.

### Mock consent page: five states, not five independent live services

Use the desktop shell with one centred390px logical-width phone on a normal state view, matching separate images. A development/design overview can show all states, but default experience starts at Ask. Never show all states simultaneously as the interactive phone UI.

The complete external page description says this is a demo and **nothing is sent to the API and no consent is recorded**. Success-screen wording about recorded consent is simulated script copy, not evidence of a real database write. All these interactions are local ephemeral state only; do not POST/DELETE consent through the real API. An explicit Reset in a developer harness may reset state, but do not invent a visible customer button not in the designs.

State transitions:

```text
Ask --See the 10 questions--> Questions opened --Go back--> Ask
Ask --Give permission--> Consent given --Withdraw consent--> Withdrawn
Ask --Not now--> Not now --Look again--> Ask
Withdrawn --Look again--> Ask
```

Three required scope rows are ticked/locked; optional questionnaire is ticked by default and can be unticked. Keep its selection on returning from Questions. If it is unticked, Consent given must not falsely claim questionnaire permission. The screenshot describes the default checked case.

Every phone has `Demo screen · not live` and `Synthetic demo data`. Bangla is primary with smaller English under it. Exact Ask, Questions, Given, Not now and Withdrawn copy is in `CONSENT_PHONE_COPY.md`. Questions are read-only; no answer controls here. Show all10 with a scrollable phone region and an accessible Go back action; a long design capture is not a requirement for absurd device height in the actual responsive UI. Keep the native-speaker review note outside the phone. No account fields, merchant score, approval or eligibility claim. Withdrawal and Not now are normal choices, not red errors.

### Audit log

Admin-only. Filters Actor/Action/Rows200,500,1000 and Refresh. Newest-first date/time, plain event sentence, event code/role/ID and role chip. Retain source visual styling and populated fixtures but use actual API events where available. Profile and score reads are each audited before disclosure by the existing backend. Opening this log is itself audited. Do not fake successful audit persistence with a toast if a required API write fails.

### Data import

Match final image with the **top blue production-feed explanation removed** at the user's request. Do not restore that callout. Keep other bottom score/audit notes shown in the final design.

Admin-only, synthetic/fixture CSVs. Table order merchants→loans→purchases→deliveries→payments→questionnaire→consents. CSV≤10MB, exact contract columns. Check-only selected: button Check file, result received3/accepted2/rejected1/loaded Nothing: check only. Example duplicate merchant M000001 is rejected because imports never overwrite. The sample line2 and file size in the PNG are fixtures.

Switching off check-only uses Check and load through the existing permitted API. Validate before loading, show real results, keep imports out of the scoring pipeline in this prototype, record audit events. Don't add manual transaction-entry features, export actions or pretend to upload files without a real request (unless explicitly labelled local fixture mode).

### Interface states

Reuse components for loading, empty results, neutral403 Consent needed, genuine API connection error,404 and no-queue public mode. A connection failure is not automatically HTTP500. Never use a consent block as a bad score. The states sheet is a reference/harness, not a new required sidebar route. Keep technical codes small with human explanations. Public source preview has its own correct data-mode banner.

## 7. Full Bangla implementation — no new images needed

Build complete `en`/`bn` dictionaries using the repository's localisation system. Translate all navigation, headings, labels, answers, help, field errors, placeholders, table headers, chips, chart legends/axes/tooltips, empty/loading/error messages, modal copy, consent states and accessibility labels. Do not translate just the menu. Preserve brand/source identifiers, merchant IDs, API/model codes and English digits in both languages. Use `Intl.NumberFormat`/date formatting with Latin numbering (`nu-latn`) or the equivalent appropriate to the app. Monetary formatting should retain the intended ৳ and Bangladesh grouping.

Use the original brief's Bangla glossary and questionnaire as canonical starting copy. `01-home-bangla.png` is a visual localisation sample, not authoritative OCR text. Correct awkward glyphs or spelling generated in that image. Keep the main language switch functional on every page and preserve selection across navigation/reloads. Phone consent stays Bangla-first with English secondary per its bilingual design; use the surrounding shell's selected language without dropping required phone translations.

Translate dynamic explanations faithfully without changing their meaning or implying automatic lending decisions. Provide a native-speaker-review checklist for release; never claim generated Bangla has already passed that review. Use actual Bengali text, not images. Set `lang` appropriately and avoid clipping Bengali vowel signs/line boxes.

Key glossary:

| English | Bangla |
| --- | --- |
| Review queue | পর্যালোচনার তালিকা |
| Decision log | সিদ্ধান্তের খাতা |
| Portfolio | পোর্টফোলিও |
| Model card | মডেল কার্ড |
| Consent | অনুমতি |
| Audit log | অডিট লগ |
| Data import | ডেটা আমদানি |
| Readiness score | প্রস্তুতির স্কোর |
| Coverage | কভারেজ |
| Strong | শক্তিশালী |
| Review | পর্যালোচনা |
| Needs more info | আরও তথ্য প্রয়োজন |
| Accept suggestion | পরামর্শ মেনে নিন |
| Override: raise | পরিবর্তন: বাড়ান |
| Override: lower | পরিবর্তন: কমান |
| Record decision | সিদ্ধান্ত রাখুন |
| Pending / Decided | অপেক্ষমাণ / সিদ্ধান্ত হয়েছে |

## 8. Responsive implementation and accessibility

Implement every route at1440 desktop, tablet and390px phone widths without requiring more mockup images. Preserve content order. Sidebar becomes an accessible drawer with menu trigger; keep role, source and language discoverable. Queue grid collapses to one card per row. Merchant sections stay one vertical flow; inline evidence metrics stack. Tables use a labelled horizontal overflow region or a carefully structured mobile rendition, never microscopic text. Charts reflow with readable legends and adequate tap targets. No body-level horizontal overflow.

The desktop consent demo may have an ornamental device frame; on actual phone-width screens use the viewport directly. Buttons remain reachable when questions scroll. Preserve the main reading order, focus position on transitions, and meaningful screen-reader announcements. Required checked controls must expose their locked state; optional checkbox must be operable.

Use real buttons/links, visible focus, keyboard navigation, labelled fields, semantic table headers, accessible disclosures and dialogs. Charts need text summaries and underlying data access. Respect reduced-motion; any ring/bar animation is subtle, optional and must not distort values or imply live updates.

## 9. Build and verification workflow

1. Inspect repo instructions, routes, shared layout, assets, APIs and existing dependencies. Produce a concise implementation plan; do not stop after planning.
2. Inventory reference images and extract design tokens. Build shared shell/primitives, then pages in numbered order. Do not install a new UI kit or replace the existing stack without a concrete need.
3. Use typed/validated data adapters and explicit fixtures when backend data is unavailable. Keep fixtures in one place, label samples and avoid mixing them with measured model outputs. Do not invent endpoint paths—inspect the existing contract.
4. Implement interactions, permissions, all three merchant conditions, questionnaire and consent states, source modes, both languages and responsive layout.
5. Start the app and capture1440px desktop and390px mobile screenshots using an available browser/test tool. Compare each against its named reference. Correct spacing, geometry, typography, colors, clipping, active navigation and charts. Use image-aware inspection, not only DOM assertions.
6. Meaningful checks: category thresholds44.9/45 and89.9/90; low-score69.9/70; no-consent disclosure blocking; role guards/direct routes; blank/whitespace override reasons; append-only history; full questionnaire completion; no readiness change after habits save; default optional consent/unticked scope; all phone transitions; no real API consent mutation; combined filters; public-mode suppression; CSV contract/size/duplicates/check-only; EN/BN coverage and Latin digits; proportional bars, correct totals and timezone labels.
7. Run the project's build/lint/type checks and focused tests appropriate to changed behavior. Do not claim screenshots or checks ran if tools were unavailable. State real integration limits plainly.
8. Deliver working code, changed-file summary, run instructions, validation results and any specific missing backend data. Preserve the approved designs; don't report a fresh redesign as a match.

## 10. Acceptance checklist

- All routes implemented with exact approved reference mapping; no page is a screenshot background.
- Final queue grid, scrolling merchant page, decision table and five-question Portfolio retained.
- Accurate score/category/coverage, consent and role rules; no forbidden lending controls.
- All10 questionnaire questions supported; habits remain separate from score.
- Five bilingual consent states functional locally, correct branching, no real consent writes.
- Plain explanations, labelled numbers, legible text, proportional meaningful charts and no copied generated-image typos.
- Full English/Bangla implementation, English digits, font coverage and mobile390px support.
- Original final Data import top-callout removal preserved.
- Required screenshots/checks performed and limitations honestly recorded.
