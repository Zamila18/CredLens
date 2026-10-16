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
  /** The same in Bangla, for the language switch. */
  titleBn: string
  textBn: string
  useApiMessage?: boolean
}

export const ERROR_COPY: Record<string, ErrorCopy> = {
  missing_token: {
    titleBn: 'একটি ডেমো ভূমিকা বেছে নিন',
    textBn: 'অনুরোধে কোনো ডেমো ব্যবহারকারী ছিল না। সাইডবার থেকে একটি ভূমিকা বেছে নিন।',
    title: 'Pick a demo role',
    text: 'The request had no demo user. Pick a role in the sidebar.',
  },
  unknown_token: {
    titleBn: 'অজানা ডেমো ব্যবহারকারী',
    textBn: 'API এই ডেমো ব্যবহারকারীকে চেনে না। সাইডবার থেকে officer-1, officer-2, admin-1 বা viewer-1 বেছে নিন।',
    title: 'Unknown demo user',
    text: 'The API does not know this demo user. Pick officer-1, officer-2, admin-1 or viewer-1 in the sidebar.',
  },
  role_not_allowed: {
    titleBn: 'এই ভূমিকার জন্য খোলা নয়',
    textBn: 'আপনার ডেমো ভূমিকা এটি খুলতে পারে না। দেখতে হলে সাইডবার থেকে ভূমিকা বদলান।',
    title: 'Not open to this role',
    text: 'Your demo role cannot open this. Switch the role in the sidebar to see it.',
  },
  consent_required: {
    titleBn: 'অনুমতি দরকার',
    textBn: 'এই মার্চেন্টের কোনো বৈধ অনুমতি নেই, তাই কোনো স্কোর বা সিদ্ধান্ত নেই। মার্চেন্টকে অনুমতি দিতে বলুন।',
    title: 'Consent needed',
    text: 'This merchant has no valid consent, so there is no score and no decision. Ask the merchant to grant access.',
  },
  consent_scope: {
    titleBn: 'প্রশ্নাবলি অনুমতির মধ্যে নেই',
    textBn: 'এই মার্চেন্টের অনুমতিতে প্রশ্নাবলি নেই, তাই উত্তর রাখা যাবে না। স্কোরে কোনো প্রভাব নেই।',
    title: 'Questionnaire not covered',
    text: "This merchant's consent does not cover the questionnaire, so answers cannot be recorded. The score is not affected.",
  },
  rows_not_shown: {
    titleBn: 'এই উৎসে শুধু মোট হিসাব',
    textBn: 'হোম ক্রেডিটের সারি দেখানো যায় না। এই উৎসের ফলাফলের জন্য মডেল কার্ড খুলুন।',
    title: 'Totals only for this source',
    text: "Home Credit rows may not be shown. Open the model card for this source's results.",
  },
  unknown_merchant: {
    titleBn: 'মার্চেন্ট পাওয়া যায়নি',
    textBn: 'এখনকার ডেটায় এই আইডির কোনো মার্চেন্টের ঋণ নেই। আইডি দেখুন, বা পর্যালোচনার তালিকায় ফিরে যান।',
    title: 'Merchant not found',
    text: 'No merchant with this id has a loan in the current data. Check the id, or go back to the review queue.',
  },
  unknown_table: {
    titleBn: 'অজানা টেবিল',
    textBn: 'আমদানি শুধু এই টেবিলগুলো নেয়: merchants, loans, purchases, deliveries, payments, questionnaire, consents।',
    title: 'Unknown table',
    text: 'Import accepts only these tables: merchants, loans, purchases, deliveries, payments, questionnaire, consents.',
  },
  import_not_available: {
    titleBn: 'পাবলিক ডেটায় আমদানি বন্ধ',
    textBn: 'API একটি পাবলিক ডেটা মোডে চলছে, আর ডেটাবেসে শুধু সিনথেটিক ডেটা আছে। ফাইল আমদানি করতে কনফিগে synthetic_bd বেছে API আবার চালু করুন।',
    title: 'Import is off for public data',
    text: 'The API is running a public data mode, and the database holds only synthetic data. Set the data mode to synthetic_bd in the config and restart the API to import files.',
  },
  file_too_large: {
    titleBn: 'ফাইল খুব বড়',
    textBn: 'একটি ফাইল সর্বোচ্চ 10 MB হতে পারে। ছোট ফাইলে ভাগ করে একটি একটি করে আমদানি করুন।',
    title: 'File too large',
    text: 'A file can be at most 10 MB. Split it into smaller files and import them one by one.',
  },
  validation: {
    titleBn: 'API এই অনুরোধ গ্রহণ করেনি',
    textBn: 'ফর্মের কিছু একটা গ্রহণযোগ্য নয়। API বলছে:',
    title: 'The API refused this request',
    text: 'Something in the form is not accepted. The API says:',
    useApiMessage: true,
  },
  data_mismatch: {
    titleBn: 'স্কোরার ও ডেটাবেস মিলছে না',
    textBn: 'স্কোরার আর ডেটাবেসে ভিন্ন ডেটা আছে। python tasks.py data --reset-db চালান, তারপর API আবার চালু করুন।',
    title: 'Scorer and database disagree',
    text: 'The scorer and the database hold different data. Run python tasks.py data --reset-db, then restart the API.',
    useApiMessage: true,
  },
  scorer_not_ready: {
    titleBn: 'স্কোরার চালু হচ্ছে',
    textBn: 'চালুর সময় API প্রায় আধা মিনিট ধরে স্কোরার তৈরি করে। এই পাতা নিজেই আবার চেষ্টা করবে।',
    title: 'The scorer is starting',
    text: 'The API builds the scorer at start-up, about half a minute. This page retries on its own.',
  },
  database_not_ready: {
    titleBn: 'ডেটাবেস এখনও প্রস্তুত নয়',
    textBn: 'API এখনও ডেটাবেস পড়তে পারছে না। এই পাতা নিজেই আবার চেষ্টা করবে।',
    title: 'The database is not ready',
    text: 'The API cannot read the database yet. This page retries on its own.',
    useApiMessage: true,
  },
  not_started: {
    titleBn: 'API পুরোপুরি চালু হয়নি',
    textBn: 'API-র একটি অংশ এখনও প্রস্তুত নয়। এই পাতা নিজেই আবার চেষ্টা করবে।',
    title: 'The API has not finished starting',
    text: 'Part of the API is not ready yet. This page retries on its own.',
    useApiMessage: true,
  },
  network: {
    titleBn: 'API সাড়া দিচ্ছে না',
    textBn: 'পোর্ট 8000-এ কেউ সাড়া দিচ্ছে না। API হয়তো এখনও চালু হচ্ছে (প্রায় আধা মিনিট), অথবা বন্ধ আছে: python tasks.py api চালান। এই পাতা নিজেই আবার চেষ্টা করবে।',
    title: 'The API is not answering',
    text: 'Nothing answered on port 8000. The API may still be starting (about half a minute), or it is stopped: run python tasks.py api. This page retries on its own.',
  },
}

const FALLBACK: ErrorCopy = {
  title: 'Something went wrong',
  text: 'The API returned an error this page does not know. The API says:',
  titleBn: 'কিছু একটা ভুল হয়েছে',
  textBn: 'API এমন একটি ত্রুটি দিয়েছে যা এই পাতা চেনে না। API বলছে:',
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

/** The message for an error, in the page's language. The API's own extra text stays as sent. */
export function describeError(error: Pick<ApiError, 'code'>, lang: 'en' | 'bn' = 'en'): ErrorCopy {
  const copy = ERROR_COPY[error.code] ?? FALLBACK
  return lang === 'bn' ? { ...copy, title: copy.titleBn, text: copy.textBn } : copy
}
