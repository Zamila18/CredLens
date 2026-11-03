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
    textBn: 'আপনার ভূমিকা এটি খুলতে পারে না। আপনার প্রতিষ্ঠান ভূমিকা ঠিক করে; দরকার হলে অ্যাডমিনকে বলুন।',
    title: 'Not open to this role',
    text: 'Your role cannot open this. Your organisation decides roles; ask your administrator if you need it.',
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
  import_not_allowed: {
    titleBn: 'এই রেকর্ড আমদানি করা যায় না',
    textBn: 'ডেটায় আগে থেকেই আছে এমন মার্চেন্টের ইতিহাস বা অনুমতি ফাইল থেকে বদলানো যায় না; তা আসে উৎস সিস্টেম আর অনুমতির ব্যবস্থা থেকে। কিছুই লোড হয়নি। API জানায়:',
    title: 'These records cannot be imported',
    text: 'The history or consent of a merchant already in the data cannot be changed from a file; it comes from the source systems and the consent system. Nothing was loaded. The API says:',
    useApiMessage: true,
  },
  no_pending_loan: {
    titleBn: 'কোনো ঋণ সিদ্ধান্তের অপেক্ষায় নেই',
    textBn: 'এই মার্চেন্টের সর্বশেষ ঋণের ফলাফল জানা, তাই এখন সিদ্ধান্ত রাখার কিছু নেই।',
    title: 'No loan is waiting for a decision',
    text: 'The latest loan of this merchant already has an outcome, so there is nothing to decide now.',
  },
  consent_already_valid: {
    titleBn: 'অনুমতি আগেই আছে',
    textBn: 'এই মার্চেন্টের বৈধ অনুমতি আছে, তাই চাওয়ার কিছু নেই।',
    title: 'Consent is already valid',
    text: 'This merchant already has a valid consent, so there is nothing to ask for.',
  },
  not_found: {
    titleBn: 'পাতা পাওয়া যায়নি',
    textBn: 'এই ঠিকানায় কোনো পাতা নেই। মেনু থেকে একটি পাতা বেছে নিন।',
    title: 'Page not found',
    text: 'There is no page at this address. Choose a page from the menu.',
  },
  bad_bundle: {
    titleBn: 'জিপ ফাইলটি পড়া যায়নি',
    textBn: 'merchants.csv, loans.csv, … নামের CSV ফাইলসহ একটি .zip দিন। API জানায়:',
    title: 'The zip could not be read',
    text: 'Upload one .zip holding CSV files named merchants.csv, loans.csv and so on. The API says:',
    useApiMessage: true,
  },
  file_too_large: {
    titleBn: 'ফাইল খুব বড়',
    textBn: 'ফাইলটি সীমার চেয়ে বড়। ছোট ফাইলে ভাগ করে একটি একটি করে আমদানি করুন।',
    title: 'File too large',
    text: 'The file is larger than the limit. Split it into smaller files and import them one by one.',
    useApiMessage: true,
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

  // --- the demo workflow (src/api/routes_intake.py). The API's own sentence is shown too:
  // it names the exact field, date or limit.
  intake_closed: {
    title: 'Entering records is switched off',
    text: 'This prototype accepts only synthetic demo records, and that mode is off. Nothing was saved.',
    titleBn: 'রেকর্ড লেখা বন্ধ',
    textBn: 'এই প্রোটোটাইপ শুধু সিনথেটিক ডেমো রেকর্ড নেয়, আর সেই মোড বন্ধ। কিছুই সংরক্ষণ হয়নি।',
  },
  date_after_demo_calendar: {
    title: 'That date is after the demo calendar',
    text: 'The synthetic world ends on its last business day. Choose that day or an earlier one.',
    titleBn: 'তারিখটি ডেমো ক্যালেন্ডারের পরে',
    textBn: 'সিনথেটিক জগৎ তার শেষ ব্যবসার দিনে শেষ হয়। সেই দিন বা আগের কোনো দিন বেছে নিন।',
    useApiMessage: true,
  },
  invalid_date: {
    title: 'Check the date',
    text: 'A date is missing or not in a form CredLens can read.',
    titleBn: 'তারিখটি দেখুন',
    textBn: 'একটি তারিখ নেই, বা এমনভাবে লেখা যা CredLens পড়তে পারে না।',
    useApiMessage: true,
  },
  invalid_dates: {
    title: 'Check the dates',
    text: 'The dates do not fit together.',
    titleBn: 'তারিখগুলো দেখুন',
    textBn: 'তারিখগুলো একে অপরের সাথে মেলে না।',
    useApiMessage: true,
  },
  invalid_choice: {
    title: 'Choose one of the listed options',
    text: 'One of the answers is not among the choices.',
    titleBn: 'তালিকার একটি বেছে নিন',
    textBn: 'একটি উত্তর তালিকার মধ্যে নেই।',
    useApiMessage: true,
  },
  invalid_name: {
    title: 'Check the shop’s name',
    text: 'The name is missing or too long.',
    titleBn: 'দোকানের নাম দেখুন',
    textBn: 'নাম নেই বা অনেক লম্বা।',
    useApiMessage: true,
  },
  invalid_amount: {
    title: 'Check the amount',
    text: 'The amount is missing or outside what is allowed.',
    titleBn: 'অঙ্কটি দেখুন',
    textBn: 'অঙ্ক নেই বা অনুমোদিত সীমার বাইরে।',
    useApiMessage: true,
  },
  invalid_reference: {
    title: 'Check the reference',
    text: 'A reference number is too long.',
    titleBn: 'রেফারেন্স দেখুন',
    textBn: 'একটি রেফারেন্স নম্বর অনেক লম্বা।',
    useApiMessage: true,
  },
  invalid_category: {
    title: 'Check the kind of stock',
    text: 'The description is too long.',
    titleBn: 'মালের ধরন দেখুন',
    textBn: 'বিবরণ অনেক লম্বা।',
    useApiMessage: true,
  },
  note_too_long: {
    title: 'The note is too long',
    text: 'Shorten the note and save again.',
    titleBn: 'নোটটি অনেক লম্বা',
    textBn: 'নোট ছোট করে আবার সংরক্ষণ করুন।',
    useApiMessage: true,
  },
  benchmark_merchant: {
    title: 'This merchant is read-only',
    text: 'It belongs to the benchmark data. Records can be added only for shops created in the app.',
    titleBn: 'এই মার্চেন্ট শুধু দেখার জন্য',
    textBn: 'এটি বেঞ্চমার্ক ডেটার অংশ। শুধু অ্যাপে তৈরি দোকানের জন্য রেকর্ড যোগ করা যায়।',
  },
  consent_category_missing: {
    title: 'Consent does not cover this',
    text: 'The merchant’s consent does not include this kind of record, so it cannot be saved.',
    titleBn: 'অনুমতিতে এটি নেই',
    textBn: 'মার্চেন্টের অনুমতিতে এই ধরনের রেকর্ড নেই, তাই সংরক্ষণ করা যাবে না।',
  },
  withdrawal_not_supported: {
    title: 'Withdrawing consent is not built yet',
    text: 'This merchant already has a valid consent. Withdrawal is planned for a later version.',
    titleBn: 'অনুমতি তুলে নেওয়া এখনও তৈরি হয়নি',
    textBn: 'এই মার্চেন্টের ইতিমধ্যে বৈধ অনুমতি আছে। তুলে নেওয়া পরের সংস্করণে আসবে।',
  },
  possible_duplicate: {
    title: 'This shop may already exist',
    text: 'A shop with the same name is already registered in this district. Open it if it is the same shop.',
    titleBn: 'দোকানটি হয়তো আগেই আছে',
    textBn: 'এই জেলায় একই নামে একটি দোকান আগেই নিবন্ধিত। একই দোকান হলে সেটি খুলুন।',
  },
  duplicate_reference: {
    title: 'Already saved',
    text: 'A record with this reference number is already saved for this shop.',
    titleBn: 'আগেই সংরক্ষিত',
    textBn: 'এই রেফারেন্স নম্বরের একটি রেকর্ড এই দোকানের জন্য আগেই সংরক্ষিত।',
  },
  not_a_workbook: {
    title: 'Not an Excel workbook',
    text: 'Open the file in Excel, save it as .xlsx (Excel Workbook) and choose it again.',
    titleBn: 'এক্সেল ওয়ার্কবুক নয়',
    textBn: 'ফাইলটি এক্সেলে খুলে .xlsx (Excel Workbook) হিসেবে সংরক্ষণ করে আবার বেছে নিন।',
  },
  empty_file: {
    title: 'The file is empty',
    text: 'Choose the workbook that holds the purchases.',
    titleBn: 'ফাইলটি খালি',
    textBn: 'যে ওয়ার্কবুকে কেনাকাটা আছে সেটি বেছে নিন।',
  },
  empty_workbook: {
    title: 'No rows to read',
    text: 'The workbook has no filled rows. Check that the purchases are on a sheet with a header row.',
    titleBn: 'পড়ার মতো সারি নেই',
    textBn: 'ওয়ার্কবুকে কোনো ভরা সারি নেই। দেখুন কেনাকাটা শিরোনাম-সারিসহ কোনো শিটে আছে কি না।',
  },
  unknown_sheet: {
    title: 'Sheet not found',
    text: 'Choose one of the sheets in this workbook.',
    titleBn: 'শিট পাওয়া যায়নি',
    textBn: 'এই ওয়ার্কবুকের একটি শিট বেছে নিন।',
  },
  missing_column: {
    title: 'Choose the columns',
    text: 'Say which column holds the date and which holds the amount.',
    titleBn: 'কলাম বেছে নিন',
    textBn: 'কোন কলামে তারিখ আর কোন কলামে টাকার অঙ্ক আছে, বলে দিন।',
  },
  column_used_twice: {
    title: 'A column is chosen twice',
    text: 'Each column can stand for one thing only.',
    titleBn: 'একটি কলাম দুবার বেছে নেওয়া হয়েছে',
    textBn: 'প্রতিটি কলাম কেবল একটি জিনিস বোঝাতে পারে।',
  },
  date_order_needed: {
    title: 'Choose how dates are written',
    text: 'Some dates can be read two ways, like 03/04/2026. Say whether the day or the month comes first.',
    titleBn: 'তারিখ কীভাবে লেখা তা বেছে নিন',
    textBn: 'কিছু তারিখ দুইভাবে পড়া যায়, যেমন 03/04/2026। আগে দিন না মাস, বলে দিন।',
  },
  preview_changed: {
    title: 'Preview again',
    text: 'The file or your choices changed after the preview, so nothing was saved. Check the preview again.',
    titleBn: 'আবার দেখে নিন',
    textBn: 'দেখে নেওয়ার পর ফাইল বা আপনার পছন্দ বদলেছে, তাই কিছু সংরক্ষণ হয়নি। আবার দেখে নিন।',
  },
  wrong_loan: {
    title: 'Choose one of this shop’s loans',
    text: 'The repayment must belong to one of this shop’s own earlier loans.',
    titleBn: 'এই দোকানের একটি ঋণ বেছে নিন',
    textBn: 'পরিশোধটি এই দোকানের আগের কোনো ঋণের হতে হবে।',
  },
  application_not_loan: {
    title: 'An application is not a loan',
    text: 'A repayment can only be recorded against a loan that was issued, never against an application.',
    titleBn: 'আবেদন ঋণ নয়',
    textBn: 'পরিশোধ শুধু দেওয়া ঋণের বিপরীতে রাখা যায়, কোনো আবেদনের বিপরীতে নয়।',
  },
  application_exists: {
    title: 'This shop already has an application',
    text: 'This prototype allows one application per shop.',
    titleBn: 'এই দোকানের আগেই আবেদন আছে',
    textBn: 'এই প্রোটোটাইপে দোকানপ্রতি একটি আবেদন।',
  },
  application_before_latest_loan: {
    title: 'Check the application date',
    text: 'The application must be dated on or after the shop’s latest loan.',
    titleBn: 'আবেদনের তারিখ দেখুন',
    textBn: 'আবেদনের তারিখ দোকানের সর্বশেষ ঋণের দিন বা তার পরে হতে হবে।',
    useApiMessage: true,
  },
  records_not_usable: {
    title: 'Nothing was saved',
    text: 'These records could not be read for the assessment. Check the dates and amounts, then save again.',
    titleBn: 'কিছুই সংরক্ষণ হয়নি',
    textBn: 'এই রেকর্ডগুলো মূল্যায়নের জন্য পড়া যায়নি। তারিখ ও অঙ্ক দেখে আবার সংরক্ষণ করুন।',
  },
  assessment_not_updated: {
    title: 'Assessment not updated',
    text: 'The latest records are saved, but the score could not be redone, so no score is shown. An older score is never shown as current.',
    titleBn: 'মূল্যায়ন হালনাগাদ হয়নি',
    textBn: 'সর্বশেষ রেকর্ড সংরক্ষিত, কিন্তু স্কোর আবার করা যায়নি, তাই কোনো স্কোর দেখানো হচ্ছে না। পুরোনো স্কোর কখনো চলতি হিসেবে দেখানো হয় না।',
  },
  no_application: {
    title: 'No application yet',
    text: 'This shop has not applied. Nothing is assessed until it does.',
    titleBn: 'এখনও আবেদন নেই',
    textBn: 'এই দোকান আবেদন করেনি। আবেদন না করা পর্যন্ত কিছু মূল্যায়ন হয় না।',
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
  import_not_allowed: 409,
  no_pending_loan: 409,
  file_too_large: 413,
  not_a_workbook: 422,
  empty_file: 422,
  empty_workbook: 422,
  unknown_sheet: 422,
  missing_column: 422,
  column_used_twice: 422,
  date_order_needed: 422,
  preview_changed: 409,
  bad_bundle: 422,
  not_found: 404,
  consent_already_valid: 409,
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
