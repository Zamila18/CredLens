# CredLens dashboard: design spec

This file and the `screens/` folder are the source of truth for how the dashboard looks.
`screens/*.dc.html` are the design files from the CredLens Dashboard canvas. Each one is a
self-contained HTML mockup: the markup and inline styles give exact colours, sizes and
spacing, and the `<script data-dc-script>` block at the bottom holds the sample data and the
interaction logic (filters, tabs, decision form states). They use a design runtime
(`support.js`, `<x-dc>`, `<sc-for>`, `<sc-if>`, `{{holes}}`) that is NOT part of the app:
read them as a reference and rebuild them as React components. Do not copy that runtime.

A PDF export of the canvas, if present beside this file, is a visual check only.

The numbers inside the mockups (AUC 0.710, band shares, consent dates and so on) are sample
data copied from `tests/fixtures/api/` and `reports/REAL_LABEL_RESULTS.md`. The app must take
every number from the API. Nothing numeric is hard-coded in a component.

## 1. Screen list

| Mockup file | Route | API calls | Who sees it |
|---|---|---|---|
| `Main.dc.html` | `/` Review queue | `GET /merchants` (`status`, `band`, `town_tier`) | all roles |
| `Merchant.dc.html` | `/merchants/:id` | `GET /merchants/{id}`, `GET /merchants/{id}/score`, `GET /merchants/{id}/consent`, `GET /decisions?merchant_id=`, `POST /merchants/{id}/decision`, `POST /merchants/{id}/questionnaire` | all roles read; officer writes |
| `ModelCard.dc.html` | `/model` | `GET /model/card` and `GET /model/card?mode=<mode>` for the other tabs | all roles |
| `Portfolio.dc.html` | `/portfolio` | `GET /merchants`, `GET /decisions`, `GET /model/card` | admin, viewer (officer may read too) |
| `Decisions.dc.html` | `/decisions` | `GET /decisions` | all roles |
| `Audit.dc.html` | `/audit` | `GET /audit?limit=` | admin |
| `Consent.dc.html` | `/consent` | `GET /merchants` (consent_valid per merchant) + `GET /merchants/{id}/consent` for the detail of one merchant | all roles |
| `ConsentMobile.dc.html` | `/demo/consent` | none (static demo of what a merchant sees) | anyone; labelled "Demo screen · not live" |
| `Import.dc.html` | `/admin/import` | `POST /admin/import/{table}?dry_run=` | admin |
| `States.dc.html` | none | reference board: tokens, the four lens states, error callouts | — |
| `Lens.dc.html`, `Sidebar.dc.html` | none | shared components | — |

## 2. Tokens

Put these in `tailwind.config` (theme.extend.colors) and as CSS variables. Names are suggestions.

| Token | Hex | Use |
|---|---|---|
| ink | `#13201C` | main text |
| ink-2 | `#2E3934` | secondary text |
| muted | `#4C5853` | labels, captions (passes 4.5:1 on white and on ground) |
| muted-2 | `#55625C` | mono meta lines |
| night | `#0F1D19` | sidebar background |
| night-2 | `#182B25` | sidebar controls; border `#2F453E` |
| night-active | `#1F3B33` | active nav item, with inset left bar `#E0A44A` 3px |
| ground | `#F4F5F1` | page background |
| banner | `#E9ECE4` | banner strip; bottom border `#DADED5` |
| card | `#FFFFFF` | cards; border `#E1E4DD`, radius 16px |
| line | `#E6E8E2` | table row dividers; `#EEF0EA` inside cards |
| lens | `#0E5A4A` | Strong, primary button, helps bars, links |
| lens-dark | `#0B4A3D` / `#08392F` | text on Strong tint / link hover |
| strong-tint | `#DCEFE6` chip, `#F2F8F5` panel, `#EEF6F2` selected |
| amber | `#B5650D` | Review, "holds back" bars |
| amber-text | `#7A4304` on `#FBEBD2` chip, `#FCF4E7` panel |
| marigold | `#E0A44A` | logo dot, active nav bar, Review segment in stacked bars |
| peri | `#8A97BF` | Needs more info ring and chip outline (1.5px inset) |
| peri-text | `#33406A` on `#E8ECF6` chip, `#EEF0F7` panel; heading `#262F52` |
| slate-blue | `#4A5A8C` / `#5A6894` | deliveries stream, habit bars, NMI stripes |
| rust | `#8A3A10` | low-score warning number, 0.70 benchmark line, withdraw consent |
| coverage | `#2D4F45` | coverage ring and bars |
| neutral-chip | `#4A524E` on `#ECEDE9` | Pending, no consent, roles |

Rules: no red anywhere. "Needs more info" is never an alarm colour: periwinkle with a
dashed/striped pattern (`repeating-linear-gradient(90deg,#5A6894 0 4px,#E3E6DF 4px 6px)`).
Bands differ in lightness as well as hue.

Type: IBM Plex Sans (UI), IBM Plex Mono (scores, ids, money, dates, metrics; with
`font-variant-numeric: tabular-nums`), Noto Sans Bengali (Bangla reasons and the consent
page). Load from Google Fonts. Page title 30/36 semibold, section title 18 semibold,
eyebrow 12 semibold uppercase tracking .06em, body 14–15, captions 12–13.

Radii: card 16, panel 12–14, button 8–12, chip 999. Touch targets at least 44px tall
(36px for compact filter chips). Page padding 28–32px, max content width 1240px (1320 on
the merchant page), card gap 16–24px.

Money: Bangladeshi grouping with the taka sign, `৳1,48,000` (see `taka()` in
`Merchant.dc.html`). Dates: `10 Jan 2025`; times `11 Jun · 10:42`.

## 3. App shell (every page)

- Left: `Sidebar` (248px, night). Logo: the three-ring lens mark (see SVG in `Sidebar.dc.html`)
  + "CredLens" + "MERCHANT READINESS". Groups: Work (Review queue with pending count badge,
  Decision log, Portfolio) and Trust (Model card, Consent, Audit log `admin` tag,
  Data import `admin` tag). Hide items the current role may not open (table in
  `docs/API_NOTES.md`).
- Sidebar bottom: "Demo role" segmented control Officer / Admin / Viewer. It sets the
  `X-Demo-Token` header to `officer-1`, `admin-1` or `viewer-1` and stores the choice in
  localStorage. Caption: "Signed in as officer-1. A demo role switch, not a login."
- Sidebar "Data source": shows the current `data_mode` from `GET /health`. The API decides
  the mode from config, so it is read-only in the app; to change it, edit config and restart
  the API. Public modes: model card and totals only, no queue; Home Credit rows never shown.
- Top banner strip on every page: info icon + **banner text from `GET /health`**, bold
  first sentence, then "Decision support only." Right side, mono: `data_mode … · model …`.
  Never hard-code the banner text.
- Layout: flex-wrap row; sidebar `flex: 1 1 240px`, main `flex: 999 1 560px; min-width: 0`
  so the sidebar stacks above the content on a phone. Wide tables sit in an
  `overflow-x: auto` box.

## 4. Components

**LensDial** (`Lens.dc.html`): the signature element. A score is never shown without it or
without a band chip and a coverage figure next to it.
- 200×200 SVG. Outer track r=90, stroke `#C3C9C0` 3px dashed `2 5`. Coverage arc r=90,
  stroke `#2D4F45` 6px, round caps, length = coverage × circumference, starting at 12 o'clock.
- Inner track r=70, stroke `#E8EAE4` 14px. Score arc r=70, 14px, round caps, length =
  score/100 × circumference, colour by band: Strong `#0E5A4A`, Review `#B5650D`,
  Needs more info `#8A97BF`.
- Centre: score in Plex Mono 54px semibold, "of 100" under it. Number colour: `#6D79A0`
  when Needs more info, `#8A3A10` when `low_score_warning`, else ink.
- Below: band chip (append " · low score" when `low_score_warning` and band is not NMI)
  and `coverage 85%` in mono.
- No consent: grey tracks, padlock icon, "No score", chip "Consent needed", caption
  "scoring blocked".
- `role="img"` with an aria-label that reads score, band and coverage.

**BandChip**: Strong `#DCEFE6/#0B4A3D`; Review `#FBEBD2/#7A4304`; Needs more info
`#E8ECF6/#33406A` + inset 1.5px `#8A97BF`; none `#ECEDE9/#4A524E`.

**CoverageBar** (queue): 96×6px track `#E3E6DF`, fill `#2D4F45`; striped periwinkle when
band is NMI; label `35% coverage` in mono 12px.

**ReasonCard**: sentence (EN or BN by toggle) + mono `+3.0 pts` / `−1.5 pts`, an 8px bar
whose width is |contribution| ÷ largest |contribution| on the screen, optional `detail` in
mono 12px. Helps on `#F2F8F5` with lens bars; holds back on `#FCF4E7` with amber bars.
Never render `reason.code`.

**Score equation line** (merchant page): mono, on ground: `90.0 average merchant + 6.0 helps
− 2.5 holds back + 0.5 everything else = 94`, computed from `baseline_score`, the shown
contributions and `other_contribution`.

**DecisionForm**: four selectable cards (role radio): Accept suggestion / Override: raise /
Override: lower / Needs more info, each with a hint line. Textarea label switches to
"Written reason (required for an override)" for overrides. "Record decision" is disabled
until an action is chosen and, for an override, the reason is not blank. Under it, mono:
`Saved with: score 94 · model <version>`. After a 201: success panel "Recorded: …", the
reason, `officer · score shown · model · audit entry written`, "Decisions are append-only.
To change course, record a new decision." and a "Record another decision" button.
There is no Approve or Decline button anywhere in the app.

**StatTile**: white card, 13px muted label, mono 28px value, optional 12px caption.

**ErrorCallout** (`States.dc.html`): white card, mono status pill, title, plain sentence, and
the API `code` in mono 12px. One per error code in `docs/API_NOTES.md`; copy for the main
ones is in the mockup (consent_required, rows_not_shown, scorer_not_ready,
import_not_available).

## 5. Screens

**Review queue** (`Main.dc.html`): header + search box (merchant id). Four StatTiles:
Pending, Needs more info, Consent missing · no score, Decided. Filters: status segmented
(All / Pending / Decided), band chips (All / Strong / Review / Needs more info /
No consent), Town tier and Shop type selects. Table columns: Merchant (mono id, district ·
town tier), Readiness (score 28px mono + BandChip + CoverageBar; or padlock "Consent
needed / No score until the merchant consents"), Shop, Onboarded, Waiting since, Status
chip, "Open ›" link. Footer: "Showing n of N merchants" and "A thin file shows as Needs more
info, never as a low band." Empty state row. The API returns about 4,200 rows with no
paging: paginate or virtualise on the client.

**Merchant detail** (`Merchant.dc.html`): breadcrumb; header with mono id, consent chip,
"Pending since" chip, shop facts; English / বাংলা toggle (top right). Two columns that wrap:
- Left: "Evidence, last 90 days" three cards (Purchases · Mokam, Deliveries · REDX,
  Payments · Baki; a stream that is `null` shows "No records in this source" instead of
  zeros). Unified timeline with stream filter chips; each row: date, coloured dot
  (purchase lens green, delivery slate blue, payment amber, loan ink diamond), label,
  source caption, amount. Newest first.
- Right: Score card. At the top, the summary paragraph from the API (`summary_en` /
  `summary_bn`, by the language toggle; it describes, it never recommends). Then LensDial + plain sentences: calibrated probability shown as score;
  coverage is not the score; band meaning). "Why this score" (Helps / Holds back columns,
  max 3 each, "Observations, not causes", equation line). "Financial habits" panel with the
  "Directional · not part of the score" chip, four 1–5 bars, stress and confidence,
  answered date, "Record new answers" button opening the 10-question form. "Why might this
  be wrong?" box on `#EEF0F7`. A consent panel from `GET /merchants/{id}/consent` (valid or
  not, as-of date, categories as chips, the records with granted / expires / revoked), in the
  same card style. DecisionForm (officer only; admin and viewer see a read-only
  note and this merchant's decision history).
- `consent_required`: whole right column shows the no-consent LensDial and the callout; no
  decision form, no questionnaire.

**Model card** (`ModelCard.dc.html`): source tabs, "What this source tells us" card
(headline, model facts, warning flag on `#FBEBD2`, Shows / Does not show panels), AUC card
with a range bar on a 0.50–0.90 scale and a dashed rust line at the 0.70 bar, Brier,
calibration error, lowest-20 tiles, Bands table with a stacked bar, "Thin files rank worse"
coverage-group bars, synthetic-only REDX ablation section, calibration plot, group results
table, limitations list. Every value comes from `GET /model/card` (tabs call
`?mode=<mode>`). Read docs/API_NOTES.md for the keys inside `metrics`. If a value is missing
for a mode, hide that block or say "not reported for this source"; never fill it in.

**Portfolio** (`Portfolio.dc.html`): band split stacked bar + three repaid tiles, officer use
(accept / override / more-info counts, override-rate bar with the caption about
rubber-stamping), decisions over time bar chart (Recharts is fine), group gaps table.

**Decision log** (`Decisions.dc.html`): "Append-only" badge, three StatTiles (agreed with the
band = accepts ÷ (accepts + overrides); overrides with a written reason; asked for more
info), filters (merchant id, action), table: When, Merchant (link), Score shown, Action chip,
Why (or "No note. Accepting needs none."), Officer · model.

**Audit log** (`Audit.dc.html`): filters (actor, action, rows 200/500/1000 → `limit`), list
newest first: time, glyph tile per action, "officer-1 opened the profile of FIX-M003",
mono meta line `action · role · #id`, role chip. Header note "this view is itself audited".

**Consent** (`Consent.dc.html`): header with "See what the merchant sees ›" linking to
`/demo/consent`; three principle panels; table of merchant, data allowed (category chips),
granted, expires, status (Valid / Revoked date) and its effect. Footer sentence about AA,
SGFinDex and Open Finance PH being design references.

**Mock consent page** (`ConsentMobile.dc.html`): 390px phone layout in Bangla with small
English sub-lines; three locked data rows + optional questionnaire checkbox; purpose /
duration / revoke list; "সিদ্ধান্ত নেবেন একজন কর্মকর্তা, কম্পিউটার নয়।"; buttons
অনুমতি দিন / এখন না; then a confirmed state with অনুমতি তুলে নিন, then a withdrawn state.
Client-side state only. The Bangla needs a native-speaker review before the demo.

**Data import** (`Import.dc.html`): blue info strip. Its text must be: in production the
source systems feed CredLens on a schedule; in this prototype imported rows are checked and
stored but never reach a score (training reads the generated files, not the database);
scoring from the database is a pilot step. Step
1 table picker in contract order (merchants, loans, purchases, deliveries, payments,
questionnaire, consents); step 2 drop zone (CSV, 10 MB) + "Check only, do not load" checkbox
(→ `dry_run=true`) + "Check file" / "Check and load"; step 3 report from `ImportReport`:
rows accepted, rows rejected, loaded yes/no, rejections table (line, record id, reasons),
`note`, truncation notice. Body is the raw file with `Content-Type: text/csv`.

## 6. Where the mockups are out of date

The mockups were drawn before the API changes of Oct 15. Where they differ from
`docs/API_NOTES.md` or `src/api/schemas.py`, the API wins. Known differences:

1. The merchant page needs the summary paragraph and the consent panel (added in section 5;
   not drawn in the mockup). Draw them in the same style.
2. The import info strip in the mockup says new merchants get a score after training. That
   is wrong; use the text in section 5.
3. The consent page has no "all consents" endpoint. Build the table from `GET /merchants`
   (valid / not valid) and open one merchant's records with `GET /merchants/{id}/consent`.
   There is no revoke endpoint, on purpose.
4. Demo users are officer-1, officer-2, admin-1 and viewer-1 (the mockup shows three).
5. All numbers in the mockups are samples. Take every number from the API.

If a page needs a field or endpoint the API does not have, do not edit `src/api/`. Write
down what is needed so Dipto can ask Humayra (she owns `src/api/`).
