/**
 * Plain words for the states the API reports, in English and Bangla, with their tone.
 *
 * These are the trust-critical distinctions of CredLens, so their wording lives in one
 * place: what is known about a record (typed in by staff is not verified), whether an
 * assessment is current, and that an application is a request, never an issued loan.
 */
import type { Pair } from './i18n'

export type Tone = 'neutral' | 'strong' | 'amber' | 'peri' | 'info'
export type StatusWords = Pair & { tone: Tone; help: Pair }

/** What is known about a record (record_provenance.status). Nothing here means "verified" unless it says so. */
export const RECORD_STATUS: Record<string, StatusWords> = {
  synthetic_demo: {
    en: 'Synthetic demo record',
    bn: 'সিনথেটিক ডেমো রেকর্ড',
    tone: 'neutral',
    help: { en: 'Generated for the demonstration. Not real data.', bn: 'ডেমোর জন্য তৈরি। আসল ডেটা নয়।' },
  },
  staff_entered: {
    en: 'Typed in by staff · not verified',
    bn: 'কর্মী লিখেছেন · যাচাই হয়নি',
    tone: 'neutral',
    help: { en: 'Entered by hand. Nobody has checked it against a source.', bn: 'হাতে লেখা। কোনো উৎসের সাথে মিলিয়ে দেখা হয়নি।' },
  },
  imported_spreadsheet: {
    en: 'From a spreadsheet · not verified',
    bn: 'স্প্রেডশিট থেকে · যাচাই হয়নি',
    tone: 'neutral',
    help: { en: 'Uploaded from a file. Where the file came from is not checked.', bn: 'ফাইল থেকে তোলা। ফাইলের উৎস যাচাই হয়নি।' },
  },
  format_checked: {
    en: 'Format checked',
    bn: 'ধরন যাচাই হয়েছে',
    tone: 'info',
    help: { en: 'Dates and amounts are well formed. Whether they are true is not known.', bn: 'তারিখ ও অঙ্ক ঠিক ধরনের। সত্য কি না জানা নেই।' },
  },
  reviewed: {
    en: 'Reviewed',
    bn: 'পর্যালোচিত',
    tone: 'info',
    help: { en: 'A named person reviewed it.', bn: 'একজন নির্দিষ্ট ব্যক্তি এটি দেখেছেন।' },
  },
  independently_verified: {
    en: 'Independently verified',
    bn: 'স্বাধীনভাবে যাচাইকৃত',
    tone: 'strong',
    help: { en: 'Checked against an independent source, with a record of how.', bn: 'স্বাধীন উৎসের সাথে মিলিয়ে যাচাই, কীভাবে তার রেকর্ডসহ।' },
  },
}

/** Whether a merchant's assessment can be trusted as current. */
export const ASSESSMENT_STATUS: Record<string, StatusWords> = {
  current: {
    en: 'Assessment up to date',
    bn: 'মূল্যায়ন হালনাগাদ',
    tone: 'strong',
    help: { en: 'The score includes every saved record dated before the application.', bn: 'আবেদনের আগের সব সংরক্ষিত রেকর্ড স্কোরে আছে।' },
  },
  refreshed: {
    en: 'Assessment up to date',
    bn: 'মূল্যায়ন হালনাগাদ',
    tone: 'strong',
    help: { en: 'The assessment was redone with the saved records.', bn: 'সংরক্ষিত রেকর্ড দিয়ে মূল্যায়ন আবার করা হয়েছে।' },
  },
  not_updated: {
    en: 'Assessment not updated',
    bn: 'মূল্যায়ন হালনাগাদ হয়নি',
    tone: 'amber',
    help: { en: 'Records are saved, but the score could not be redone. No score is shown until it is.', bn: 'রেকর্ড সংরক্ষিত, কিন্তু স্কোর আবার করা যায়নি। না হওয়া পর্যন্ত কোনো স্কোর দেখানো হবে না।' },
  },
  not_scored: {
    en: 'Not assessed yet',
    bn: 'এখনও মূল্যায়ন হয়নি',
    tone: 'neutral',
    help: { en: 'The application is saved; the assessment has not run yet.', bn: 'আবেদন সংরক্ষিত; মূল্যায়ন এখনও হয়নি।' },
  },
  no_application: {
    en: 'No application yet',
    bn: 'এখনও আবেদন নেই',
    tone: 'neutral',
    help: { en: 'Nothing is assessed until the merchant applies.', bn: 'আবেদন না করা পর্যন্ত কিছু মূল্যায়ন হয় না।' },
  },
}

/** A loan-shaped row, said plainly. */
export const LOAN_KIND: Record<string, StatusWords> = {
  application: {
    en: 'Application · requested, not issued',
    bn: 'আবেদন · চাওয়া হয়েছে, দেওয়া হয়নি',
    tone: 'peri',
    help: { en: 'The amount the merchant asked for. No loan has been issued.', bn: 'মার্চেন্ট যে অঙ্ক চেয়েছেন। কোনো ঋণ দেওয়া হয়নি।' },
  },
  loan: {
    en: 'Issued loan',
    bn: 'দেওয়া ঋণ',
    tone: 'neutral',
    help: { en: 'A loan from the lender’s records (synthetic in this demo).', bn: 'ঋণদাতার রেকর্ডের একটি ঋণ (এই ডেমোতে সিনথেটিক)।' },
  },
}

/** Consent recorded in the app: always simulated in this prototype. */
export const SIMULATED_CONSENT: Pair = {
  en: 'Simulated consent (synthetic demo)',
  bn: 'সিমুলেটেড অনুমতি (সিনথেটিক ডেমো)',
}

/**
 * Review readiness (GET /merchants/{id}/review). Says whether the evidence is in order for
 * a person to review. Never approval, eligibility or a level of risk.
 */
export const READINESS: Record<string, StatusWords> = {
  ready: {
    en: 'Ready for review',
    bn: 'পর্যালোচনার জন্য প্রস্তুত',
    tone: 'strong',
    help: { en: 'The evidence checks pass. This is not an approval: you decide.', bn: 'প্রমাণের যাচাই ঠিক আছে। এটি অনুমোদন নয়: সিদ্ধান্ত আপনার।' },
  },
  check_needed: {
    en: 'One check needed',
    bn: 'একটি যাচাই বাকি',
    tone: 'amber',
    help: { en: 'Something is worth checking before you decide. It does not change the score.', bn: 'সিদ্ধান্তের আগে একটি বিষয় দেখা দরকার। এটি স্কোর বদলায় না।' },
  },
  more_info_needed: {
    en: 'More information needed',
    bn: 'আরও তথ্য দরকার',
    tone: 'peri',
    help: { en: 'Required evidence is missing, so the assessment is not enough to review.', bn: 'দরকারি প্রমাণ নেই, তাই পর্যালোচনার জন্য মূল্যায়ন যথেষ্ট নয়।' },
  },
  not_updated: {
    en: 'Assessment not updated',
    bn: 'মূল্যায়ন হালনাগাদ হয়নি',
    tone: 'amber',
    help: { en: 'New records are saved but the score could not be redone. No score is shown.', bn: 'নতুন রেকর্ড সংরক্ষিত, কিন্তু স্কোর আবার করা যায়নি। কোনো স্কোর দেখানো হয় না।' },
  },
}

/** A generated benchmark row has no entry record: say so instead of guessing how it entered. */
export const GENERATED_RECORD: StatusWords = {
  en: 'Generated synthetic record',
  bn: 'তৈরি করা সিনথেটিক রেকর্ড',
  tone: 'neutral',
  help: { en: 'Part of the synthetic benchmark data. It has no entry record.', bn: 'সিনথেটিক বেঞ্চমার্ক ডেটার অংশ। এর কোনো এন্ট্রি রেকর্ড নেই।' },
}
