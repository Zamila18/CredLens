# Live demo guide: test the whole prototype by hand (and show it to the judges)

This guide walks through CredLens end to end on a laptop: start it, look at every page,
upload a lender's file of new merchants, see them scored, record decisions, and check the
audit trail. The same steps are the demo script for the judges (about 8 minutes).

Everything here is synthetic data. Every screen says so, and says "Decision support only."

## 0. Before you start (once)

| Step | Command (in `E:\CredLens`, with `.venv` active) | You should see |
|---|---|---|
| Clean database | `python tasks.py data --reset-db` | the row counts, ending with `users 4` |
| Python tests | `python tasks.py test` | all passed (a few skipped) |
| Web build check | `cd web` then `npm run build` | `built in …` with no errors |

The reset gives a fresh local database: no decisions, no audit entries, no imported
merchants. It only touches the local SQLite file `data/app.db`.

## 1. Start the two servers

Open two terminals in `E:\CredLens` (with `.venv` active):

1. Terminal 1: `python tasks.py api`. Wait until it prints `Application startup complete`
   (about half a minute: the scorer is built at start).
2. Terminal 2: `python tasks.py app`. It prints a local address.
3. Open `http://localhost:5173` in the browser.

If a page says **"The API is not answering"**, terminal 1 is still starting or stopped.

## 2. Walk through the pages (role: Officer 1)

The demo role is in the sidebar (bottom). It is a demo role switch, not a login.
The **English / বাংলা** switch is at the top right; `?lang=bn` in the address opens a page
in Bangla.

| Page | What to check |
|---|---|
| **Home** `/` | The shop picture with "মুদি দোকান" on its sign; M000031's card (90, Strong, 65% coverage); Today: Pending 4,178, Needs more info 611, Consent missing 200, Decided 0 |
| **Review queue** `/queue` | Two-by-two cards; each score has its band and coverage; a no-consent card shows a lock and no score. Try the filters (Status, Town tier, Shop type, Band) and the search |
| **Merchant** `M000031` | Sections in order: identity, readiness overview (summary, 90/100, Strong, 65%), evidence (৳1,49,960 in 18 purchases; 21 parcels; 0% on time across 1 repayment), why this score (bars to scale), timeline (real dates), financial habits (no answers yet), why might this be wrong, consent (C000030, checked for 30 Aug 2026), your decision, decisions on this merchant |
| **Model card** `/model` | Tabs for the five data sources; open each accordion (inputs, model choice, calibration, A/B/C/D, group metrics, other sources) |
| **Consent** `/consent` | 3,978 valid, 200 not; "View record" opens a record inline; "See what the merchant sees" opens the phone demo |
| **Phone demo** `/demo/consent` | Ask → See the 10 questions → Go back; Give permission → Withdraw → Look again; Not now → Look again. Untick the optional questions, then Give permission: the summary leaves the questions out. Nothing is sent to the API |
| **Portfolio** `/portfolio` | One-minute summary and five questions; "View in queue" opens the queue already filtered |

## 3. The live import (role: Admin)

The demo file is `data/demo/credlens_demo_bundle.zip`: five NEW synthetic merchants
(D00001 to D00005) as a lender's export, plus three deliberate mistakes.
`data/demo/EXPECTED.md` says what each should show.

1. In the sidebar, set **Demo role: Admin**. "Audit log" and "Data import" appear.
2. Open **Data import**. "All tables (zip)" is already selected.
3. Drop or browse to `credlens_demo_bundle.zip`. Leave **"Check only, do not load"** ticked.
   Press **Check file**.
   - Expected: received 460, accepted 457, rejected 3, loaded "Nothing: check only".
   - The three rejected rows: `M000031` (already in the database: an import never
     overwrites), `D-BAD-DATE` (date 2026-13-40), `D-BAD-STATUS` (unknown status).
4. Untick "Check only". Press **Check and load**.
   - Expected: loaded "Yes: accepted rows", and **"New merchants now in the review queue: 5"**:

| Merchant | Shows |
|---|---|
| D00001 | 96 · Strong · 100% coverage |
| D00002 | 75 · Needs more info · 35% coverage (thin file: more evidence, not a lower band) |
| D00003 | 64 · Review · low score · 90% coverage |
| D00004 | Consent needed: no score |
| D00005 | 84 · Review · 75% coverage (no REDX records: coverage lower, score not lowered by itself) |

5. Click **D00001**. Its page has a score, reasons, evidence and a timeline, made by the same
   saved model as every other merchant. Nothing was retrained.
6. Open **Review queue** and search `D0`: the five new cards, D00004 locked.

What to say: "A lender's file is checked against the data contract before anything loads,
the bad rows are named, and new customers are scored by the same model with the same rules.
The file can never change an existing merchant's history or consent."

## 4. Decisions (role: Officer 1)

1. Set **Demo role: Officer 1**. Open **D00003** (low score).
2. Under "Your decision", pick **Override: raise**. "Record decision" stays disabled until
   a written reason is typed (spaces alone do not count). Type a reason; record it.
   - Expected: "Recorded: Override: raise", with the score, band, coverage and model version
     saved with it, in Bangladesh time.
3. Open **D00004**: no score, no evidence, no decision form. Consent comes first.
4. Open **Decision log**: the decision, with the score, band and coverage at the time.
   There is no edit or delete anywhere; a change of mind is a new decision.
5. Optional: on **D00001** record "Accept suggestion" as Officer 1, then switch to
   **Officer 2** and record "Needs more info" on **D00002**. The decision log and the
   portfolio's questions 3 and 4 count them.

## 5. The audit trail (role: Admin)

1. Set **Demo role: Admin**. Open **Audit log**.
2. Expected, newest first, in Bangladesh time: "admin-1 opened the audit log",
   the decisions, "officer-1 read the score of …", "officer-1 opened the profile of …",
   "admin-1 imported a bundle of files", "admin-1 checked a bundle of files", and the
   queue views. Every read of a merchant was written before anything was shown.
3. Switch to **Viewer**: everything is read-only; no decision form, no admin pages.

## 6. Phone width

In the browser, open the developer tools and pick a phone (390 px wide), or open the site
on a phone on the same network. The sidebar becomes a menu button; cards stack; tables
scroll inside their own box; nothing spills sideways.

## 7. Run it again from a clean state

The import is real: D00001 to D00005 stay in the database (an import never overwrites, so
uploading the same file again rejects them as repeats). To start over:

1. Stop the API (Ctrl+C in terminal 1).
2. `python -m src.db.load --reset` (reloads the local database from the generated files;
   faster than `python tasks.py data --reset-db`, which also regenerates them).
3. Start the API again: `python tasks.py api`.

The API must be restarted after a reset: it keeps the scored merchants in memory.

## If something goes wrong

| You see | Do this |
|---|---|
| "The API is not answering" | Start terminal 1 (`python tasks.py api`) and wait half a minute |
| "The scorer and the database hold different data" | `python tasks.py data --reset-db`, then restart the API |
| HTTP 500 when recording a decision after pulling new code | The database misses new columns: `python tasks.py data --reset-db` |
| The import says "These records cannot be imported" | The file names a merchant that is already in the data; use the demo zip as it is |
| Upload refused: "The zip could not be read" | Upload the `.zip` itself, not a folder or a single CSV, with "All tables (zip)" selected |
| Fonts look plain | Hard-refresh the browser (Ctrl+F5); the fonts are bundled, no internet is needed |
