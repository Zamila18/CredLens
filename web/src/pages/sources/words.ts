/** Plain words for the data-source screens: states, row outcomes, fields and categories. */
import type { Pair } from '@/lib/i18n'
import type { StatusWords } from '@/lib/statuses'

export const CONNECTION_STATUS: Record<string, StatusWords> = {
  not_tested: { en: 'Not tested yet', bn: 'এখনও পরীক্ষা হয়নি', tone: 'neutral', help: { en: 'Run a connection test before syncing.', bn: 'সিঙ্কের আগে সংযোগ পরীক্ষা করুন।' } },
  connected: { en: 'Connected', bn: 'সংযুক্ত', tone: 'strong', help: { en: 'The last test or sync worked.', bn: 'শেষ পরীক্ষা বা সিঙ্ক কাজ করেছে।' } },
  error: { en: 'Needs attention', bn: 'মনোযোগ দরকার', tone: 'amber', help: { en: 'The last test or sync failed. Nothing from it was saved.', bn: 'শেষ পরীক্ষা বা সিঙ্ক ব্যর্থ। তা থেকে কিছু রাখা হয়নি।' } },
  revoked: { en: 'Revoked', bn: 'প্রত্যাহার করা', tone: 'neutral', help: { en: 'No longer used. Records it saved are kept with their origin.', bn: 'আর ব্যবহার হয় না। এর রাখা রেকর্ড উৎসসহ থেকে যায়।' } },
}

export const AVAILABILITY: Record<string, StatusWords> = {
  builtin: { en: 'Works today', bn: 'আজ চালু', tone: 'strong', help: { en: 'No connection to set up.', bn: 'কোনো সংযোগ লাগে না।' } },
  available: { en: 'Can be connected', bn: 'সংযোগ করা যায়', tone: 'info', help: { en: 'Add a connection to use it.', bn: 'ব্যবহার করতে একটি সংযোগ যোগ করুন।' } },
  planned: { en: 'Planned · not connected', bn: 'পরিকল্পিত · সংযুক্ত নয়', tone: 'neutral', help: { en: 'Needs authorised access and an implementation. Not available in this build.', bn: 'অনুমোদিত প্রবেশাধিকার ও বাস্তবায়ন দরকার। এই সংস্করণে নেই।' } },
}

export const OUTCOME: Record<string, StatusWords> = {
  add: { en: 'Will be saved', bn: 'রাখা হবে', tone: 'strong', help: { en: 'New, valid and matched.', bn: 'নতুন, বৈধ ও মেলানো।' } },
  skip: { en: 'Already saved', bn: 'আগেই রাখা', tone: 'neutral', help: { en: 'Saved by an earlier sync; nothing is added.', bn: 'আগের সিঙ্কে রাখা; কিছু যোগ হবে না।' } },
  flag: { en: 'Possible duplicate', bn: 'সম্ভাব্য দ্বৈত', tone: 'amber', help: { en: 'A purchase with the same date and amount is already saved. Left out.', bn: 'একই তারিখ ও অঙ্কের কেনাকাটা আগেই আছে। বাদ।' } },
  reject: { en: 'Refused', bn: 'বাতিল', tone: 'peri', help: { en: 'This row cannot be saved as it is.', bn: 'সারিটি এভাবে রাখা যায় না।' } },
  unmatched: { en: 'Needs a merchant match', bn: 'মার্চেন্ট মেলানো দরকার', tone: 'amber', help: { en: 'A person must link the source’s merchant first.', bn: 'আগে উৎসের মার্চেন্টকে একজন মানুষকে মেলাতে হবে।' } },
}

export const REASON: Record<string, Pair> = {
  new: { en: 'New record.', bn: 'নতুন রেকর্ড।' },
  already_synced: { en: 'Saved by an earlier sync.', bn: 'আগের সিঙ্কে রাখা।' },
  possible_duplicate: { en: 'Same date and amount as a saved purchase.', bn: 'রাখা কেনাকাটার মতো একই তারিখ ও অঙ্ক।' },
  needs_match: { en: 'The source’s merchant is not linked to a CredLens merchant yet.', bn: 'উৎসের মার্চেন্ট এখনও CredLens মার্চেন্টের সাথে যুক্ত নয়।' },
  match_rejected: { en: 'A person rejected the suggested match.', bn: 'একজন প্রস্তাবিত মিল বাতিল করেছেন।' },
  missing_reference: { en: 'The merchant or record reference is empty.', bn: 'মার্চেন্ট বা রেকর্ডের রেফারেন্স খালি।' },
  unsupported_kind: { en: 'This kind of record is not supported.', bn: 'এই ধরনের রেকর্ড সমর্থিত নয়।' },
  bad_date: { en: 'The date cannot be read.', bn: 'তারিখ পড়া যায়নি।' },
  date_after_calendar: { en: 'The date is after the business calendar ends.', bn: 'তারিখটি ব্যবসার ক্যালেন্ডারের শেষের পরে।' },
  bad_amount: { en: 'The amount is not a number above 0.', bn: 'অঙ্কটি 0-এর বেশি কোনো সংখ্যা নয়।' },
  bad_status: { en: 'The delivery status is not one CredLens knows.', bn: 'ডেলিভারির অবস্থাটি CredLens চেনে না।' },
  reference_twice_in_source: { en: 'The same record reference appears twice in this read.', bn: 'একই রেকর্ড-রেফারেন্স এই পাঠে দুবার আছে।' },
  consent_required: { en: 'The merchant has no valid consent.', bn: 'মার্চেন্টের বৈধ অনুমতি নেই।' },
  consent_category_missing: { en: 'The merchant’s consent does not cover this kind of record.', bn: 'মার্চেন্টের অনুমতিতে এই ধরনের রেকর্ড নেই।' },
}

export const FIELD_LABEL: Record<string, Pair> = {
  merchant_ref: { en: 'Merchant reference in the source', bn: 'উৎসে মার্চেন্টের রেফারেন্স' },
  merchant_name: { en: 'Merchant name', bn: 'মার্চেন্টের নাম' },
  district: { en: 'District', bn: 'জেলা' },
  record_kind: { en: 'Kind of record', bn: 'রেকর্ডের ধরন' },
  business_date: { en: 'Business date', bn: 'ব্যবসার তারিখ' },
  amount: { en: 'Amount', bn: 'অঙ্ক' },
  delivery_status: { en: 'Delivery status', bn: 'ডেলিভারির অবস্থা' },
  source_reference: { en: 'Record reference in the source', bn: 'উৎসে রেকর্ডের রেফারেন্স' },
}

export const CATEGORY: Record<string, Pair> = {
  manual: { en: 'Manual collection', bn: 'হাতে সংগ্রহ' },
  file: { en: 'Files', bn: 'ফাইল' },
  institutional: { en: 'Institutional records', bn: 'প্রতিষ্ঠানের রেকর্ড' },
  test: { en: 'Sandbox testing', bn: 'স্যান্ডবক্স পরীক্ষা' },
  platform: { en: 'Business platforms', bn: 'ব্যবসায়িক প্ল্যাটফর্ম' },
  financial: { en: 'Financial records', bn: 'আর্থিক রেকর্ড' },
  logistics: { en: 'Logistics', bn: 'লজিস্টিকস' },
  pos: { en: 'Retail POS', bn: 'রিটেইল POS' },
  distributor: { en: 'Distributor systems', bn: 'ডিস্ট্রিবিউটর সিস্টেম' },
  accounting: { en: 'Accounting', bn: 'হিসাব' },
}

export const ERROR_WORDS: Record<string, Pair> = {
  source_unavailable: { en: 'The source did not answer.', bn: 'উৎস সাড়া দেয়নি।' },
  secret_missing: { en: 'The credential this connection points to is not set in the deployment.', bn: 'এই সংযোগ যে ক্রেডেনশিয়াল দেখায় তা ইনস্টলেশনে সেট করা নেই।' },
  not_available: { en: 'This source cannot be connected in this build.', bn: 'এই সংস্করণে এই উৎস সংযুক্ত করা যায় না।' },
  records_not_usable: { en: 'The records could not be read for the assessment, so nothing was saved.', bn: 'রেকর্ডগুলো মূল্যায়নের জন্য পড়া যায়নি, তাই কিছু রাখা হয়নি।' },
  intake_closed: { en: 'This installation accepts synthetic records only.', bn: 'এই ইনস্টলেশন শুধু সিনথেটিক রেকর্ড নেয়।' },
}

/** Where a built-in source is used. */
export const BUILTIN_LINK: Record<string, { to: string; en: string; bn: string; roles?: string[] }> = {
  field_entry: { to: '/app/field', en: 'Open Field work', bn: 'মাঠের কাজ খুলুন', roles: ['officer'] },
  spreadsheet: { to: '/app/field', en: 'Import from a shop’s Business records', bn: 'দোকানের ব্যবসার রেকর্ড থেকে আমদানি', roles: ['officer'] },
  institution_files: { to: '/app/admin/import', en: 'Open Data files', bn: 'ডেটা ফাইল খুলুন', roles: ['admin'] },
}
