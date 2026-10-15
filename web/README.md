# web/: React dashboard

Owner: Dipto (Phase 10). The API it calls (`src/api/`) is owned by Humayra.

**Stack:** React + Vite + TypeScript + Tailwind v4 + shadcn/ui (restyled), React Router, Recharts.
Linting with oxlint. Node.js 20 or newer (tested on 24).

## Run it

1. Start the API in another terminal: `python tasks.py api` (it takes about half a minute
   before port 8000 answers).
2. In `web/`: `npm install` (first time only), then `npm run dev`.
3. Open http://localhost:5173.

The browser calls `/api/...`; Vite forwards those calls to http://localhost:8000 and drops the
`/api` prefix (`vite.config.ts`). To point at another API, set `CREDLENS_API` before `npm run dev`.

| Command | What it does |
|---|---|
| `npm run dev` | development server on :5173 |
| `npm run build` | type-check, then build into `dist/` |
| `npm run lint` | oxlint |
| `npm run types` | regenerate `src/api/schema.d.ts` from the running API's `/openapi.json` |

## Where things are

- `src/index.css`: the design tokens (colours, fonts) from `design-reference/DESIGN_SPEC.md`.
  Tailwind v4 reads its theme from this file; there is no `tailwind.config`.
- `src/api/client.ts`: the only code that calls the API. Adds `X-Demo-Token`, turns errors
  into `ApiError` with the API's `code`.
- `src/api/types.ts`: short names for the generated API types.
- `src/components/ui/`: shadcn/ui components, restyled to the CredLens tokens.
- `design-reference/`: the mockups the pages follow (read them as pictures; their runtime is
  not part of the app).

## Rules

- The dashboard talks only to the FastAPI API. It never connects to the database, and no
  database key or connection string may appear in this folder.
- Every page shows the banner returned by `GET /health` (it names the data source and says
  "Decision support only.").
- A score is never shown without its coverage and band.
- Officers see reason sentences, never feature names (`reason.code` is never rendered).
- There is no approve or decline button. The actions are accept, override (with a written
  reason) and needs more info.
- The role switch (`officer-1`, `officer-2`, `admin-1`, `viewer-1`) is a demo, not a login.
