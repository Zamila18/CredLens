Read CLAUDE.md, docs/HANDOVER.md, docs/API_NOTES.md and docs/WORDING_AND_QA.md.
Then read web/design-reference/DESIGN_SPEC.md and every file in web/design-reference/screens/.

I am Dipto. I build Phase 10: the React dashboard in web/ (Vite + React + TypeScript +
Tailwind + shadcn/ui, React Router, Recharts for charts). The API (src/api/) is done and
owned by Humayra; the dashboard calls only the API, never the database. I have run
python tasks.py data --reset-db and python tasks.py train.

DESIGN
The dashboard must look like the design in web/design-reference/. The screens/*.dc.html
files are HTML mockups of every page: copy their colours, fonts (IBM Plex Sans, IBM Plex
Mono, Noto Sans Bengali), spacing, components (LensDial, band chips, coverage bars, reason
cards, decision form, error callouts) and the wording on the page. They use a small design
runtime (<x-dc>, <sc-for>, <sc-if>, {{...}}, support.js) that is NOT part of our app: read
them as a picture and rebuild them as React components. DESIGN_SPEC.md lists the colour
tokens, the components and which mockup belongs to which page. Restyle shadcn components to
these tokens so nothing looks like the shadcn default.
The mockups were drawn before the API changes of Oct 15. Where a mockup differs from
docs/API_NOTES.md or src/api/schemas.py, the API wins (DESIGN_SPEC.md section 6 lists the
known differences). Every number on screen comes from the API; the numbers in the mockups
are samples only.

FIRST
Check the repo, run python tasks.py test, confirm python tasks.py api works and that
node -v prints a version (if Node.js is missing, give me a HUMAN STEP NEEDED block as in
CLAUDE.md and wait). Then suggest a short plan in small parts, saying which mockup each
page follows, and wait for my go-ahead. Explain things simply; I am learning as I go.

PAGES (suggested order, I can change it)
1. App shell (Sidebar.dc.html, States.dc.html): sidebar, demo role switch (officer-1,
   officer-2, admin-1, viewer-1 sent as the X-Demo-Token header), the banner from
   GET /health, English/Bangla toggle, shared components, and a /dev/states page that
   matches States.dc.html so I can compare.
2. Review queue (Main.dc.html): GET /merchants. About 4,200 rows and no paging in the API,
   so page them in the browser.
3. Merchant detail (Merchant.dc.html): activity panels and timeline, score with coverage and
   band (LensDial), the summary (summary_en / summary_bn) on top of the score card, reasons,
   questionnaire panel and form beside the score, consent panel (GET /merchants/{id}/consent),
   decision form for officers.
4. Decision log (Decisions.dc.html), model card (ModelCard.dc.html, tabs use
   GET /model/card?mode=...), audit log (Audit.dc.html, admin), import page (Import.dc.html,
   admin), consent page (Consent.dc.html and the Bangla phone demo ConsentMobile.dc.html),
   portfolio (Portfolio.dc.html; the first to drop if time runs short).
5. Public data modes: model card and totals only, no queue. Home Credit rows never shown.

MUST STAY TRUE ON EVERY SCREEN (promises from our submission)
- The banner shows the data source and "Decision support only." (text from GET /health).
- A score always comes with its coverage and band.
- No approve or decline button. An override needs a written reason.
- Officers see plain sentences, never feature names (never show reason.code).
- The questionnaire never changes the score.
- No "approved", "declined" or "eligible" wording.
- No sign-up or login pages; the role switch is for the demo.
- Every error code in docs/API_NOTES.md gets a clear message (the callouts in States.dc.html).

RULES FOR YOU
I own web/ only. If a page needs something the API does not give, tell me what to ask
Humayra for; do not edit src/api/ or anything outside web/.
I run all git commands myself; never run state-changing git commands. After each part,
run npm run build in web/ and python tasks.py test, stop, tell me in simple words what is
done, and give me the git add and git commit commands.
