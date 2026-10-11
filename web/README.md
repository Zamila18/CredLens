# web/: React dashboard (placeholder)

Owner role: D (full-stack). The app is created in Phase 10.

**Stack:** React + Vite + TypeScript + Tailwind + shadcn/ui, with Recharts for charts.

## Rules

- The dashboard talks only to the FastAPI API (`python tasks.py api`, port 8000). It never connects to the database, and no database key or connection string may appear in this folder.
- Every page shows the banner returned by `GET /health` (it names the data source and says "Decision support only.").
- A score is never shown without its coverage and band.
- Officers see reason sentences, never feature names.
- There is no approve or decline button. The actions are accept, override (with a written reason) and needs more info.

## Building before the model exists

- The API contract is `src/api/schemas.py`. The running API publishes it at `http://localhost:8000/openapi.json`, which can generate TypeScript types.
- Sample responses for every endpoint are in `tests/fixtures/api/`. Build pages against these first.

## Pages (PROJECT_BRIEF section 9)

Review queue, merchant detail, decision log, model card, consent view, audit log (admin), portfolio view, plus a data-source selector and an English/Bangla toggle for reasons.
