/**
 * A clear message for every error code in docs/API_NOTES.md (shown by ErrorCallout).
 * Wording for the main four follows States.dc.html.
 *
 * `useApiMessage: true` adds the API's own message under ours: for those codes the
 * API's text names the exact command to run, or says what was wrong with the form.
 */
import type { ApiError } from './client'

export type ErrorCopy = {
  title: string
  text: string
  useApiMessage?: boolean
}

export const ERROR_COPY: Record<string, ErrorCopy> = {
  missing_token: {
    title: 'Pick a demo role',
    text: 'The request had no demo user. Pick a role in the sidebar.',
  },
  unknown_token: {
    title: 'Unknown demo user',
    text: 'The API does not know this demo user. Pick officer-1, officer-2, admin-1 or viewer-1 in the sidebar.',
  },
  role_not_allowed: {
    title: 'Not open to this role',
    text: 'Your demo role cannot open this. Switch the role in the sidebar to see it.',
  },
  consent_required: {
    title: 'Consent needed',
    text: 'This merchant has no valid consent, so there is no score and no decision. Ask the merchant to grant access.',
  },
  consent_scope: {
    title: 'Questionnaire not covered',
    text: "This merchant's consent does not cover the questionnaire, so answers cannot be recorded. The score is not affected.",
  },
  rows_not_shown: {
    title: 'Totals only for this source',
    text: "Home Credit rows may not be shown. Open the model card for this source's results.",
  },
  unknown_merchant: {
    title: 'Merchant not found',
    text: 'No merchant with this id has a loan in the current data. Check the id, or go back to the review queue.',
  },
  unknown_table: {
    title: 'Unknown table',
    text: 'Import accepts only these tables: merchants, loans, purchases, deliveries, payments, questionnaire, consents.',
  },
  import_not_available: {
    title: 'Import is off for public data',
    text: 'The API is running a public data mode, and the database holds only synthetic data. Set the data mode to synthetic_bd in the config and restart the API to import files.',
  },
  file_too_large: {
    title: 'File too large',
    text: 'A file can be at most 10 MB. Split it into smaller files and import them one by one.',
  },
  validation: {
    title: 'The API refused this request',
    text: 'Something in the form is not accepted. The API says:',
    useApiMessage: true,
  },
  data_mismatch: {
    title: 'Scorer and database disagree',
    text: 'The scorer and the database hold different data. Run python tasks.py data --reset-db, then restart the API.',
    useApiMessage: true,
  },
  scorer_not_ready: {
    title: 'The scorer is starting',
    text: 'The API builds the scorer at start-up, about half a minute. This page retries on its own.',
  },
  database_not_ready: {
    title: 'The database is not ready',
    text: 'The API cannot read the database yet. This page retries on its own.',
    useApiMessage: true,
  },
  not_started: {
    title: 'The API has not finished starting',
    text: 'Part of the API is not ready yet. This page retries on its own.',
    useApiMessage: true,
  },
  network: {
    title: 'The API is not answering',
    text: 'Nothing answered on port 8000. The API may still be starting (about half a minute), or it is stopped: run python tasks.py api. This page retries on its own.',
  },
}

const FALLBACK: ErrorCopy = {
  title: 'Something went wrong',
  text: 'The API returned an error this page does not know. The API says:',
  useApiMessage: true,
}

/** Every code we have a message for, in the order of docs/API_NOTES.md (for /dev/states). */
export const KNOWN_ERROR_CODES = Object.keys(ERROR_COPY)

/** The HTTP status each code comes with (for the pill on /dev/states). */
export const ERROR_STATUS: Record<string, number> = {
  missing_token: 401,
  unknown_token: 401,
  role_not_allowed: 403,
  consent_required: 403,
  consent_scope: 403,
  rows_not_shown: 403,
  unknown_merchant: 404,
  unknown_table: 404,
  import_not_available: 409,
  file_too_large: 413,
  validation: 422,
  data_mismatch: 500,
  scorer_not_ready: 503,
  database_not_ready: 503,
  not_started: 503,
  network: 0,
}

export function describeError(error: Pick<ApiError, 'code'>): ErrorCopy {
  return ERROR_COPY[error.code] ?? FALLBACK
}
