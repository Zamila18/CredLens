import { apiBlob } from '@/api/client'

/** Words for the registration wizard: statuses, fields, and the agreement boxes. */

export type Pair = [string, string]

export const STATUS_WORDS: Record<string, { words: Pair; tone: 'neutral' | 'warn' | 'good' | 'bad' }> = {
  draft: { words: ['Details saved', 'তথ্য সংরক্ষিত'], tone: 'neutral' },
  form_issued: { words: ['Form printed, waiting for the signed copy', 'ফর্ম প্রিন্ট হয়েছে, সই করা কপির অপেক্ষায়'], tone: 'neutral' },
  signed_uploaded: { words: ['Signed copy uploaded', 'সই করা কপি আপলোড হয়েছে'], tone: 'warn' },
  under_review: { words: ['Needs a person to check it', 'একজন মানুষের যাচাই দরকার'], tone: 'warn' },
  needs_correction: { words: ['Sent back for correction', 'সংশোধনের জন্য ফেরত'], tone: 'warn' },
  verified: { words: ['Verified', 'যাচাই হয়েছে'], tone: 'good' },
  active: { words: ['Active: consent recorded', 'সক্রিয়: অনুমতি রাখা হয়েছে'], tone: 'good' },
  rejected: { words: ['Rejected', 'প্রত্যাখ্যাত'], tone: 'bad' },
  withdrawn: { words: ['Consent withdrawn', 'অনুমতি তুলে নেওয়া হয়েছে'], tone: 'bad' },
}

export const FIELD_STATE_WORDS: Record<string, { words: Pair; tone: 'neutral' | 'warn' | 'good' | 'bad' }> = {
  matched: { words: ['Matches', 'মিলেছে'], tone: 'good' },
  extracted: { words: ['Read', 'পড়া হয়েছে'], tone: 'neutral' },
  confirmed: { words: ['Confirmed', 'নিশ্চিত'], tone: 'good' },
  corrected: { words: ['Corrected', 'সংশোধিত'], tone: 'good' },
  low_confidence: { words: ['Not sure: check it', 'নিশ্চিত নয়: দেখে নিন'], tone: 'warn' },
  mismatch: { words: ['Differs from what was typed', 'টাইপ করা তথ্যের সাথে অমিল'], tone: 'bad' },
  missing: { words: ['Missing', 'নেই'], tone: 'bad' },
  not_given: { words: ['Not given (optional)', 'দেওয়া হয়নি (ঐচ্ছিক)'], tone: 'neutral' },
  present: { words: ['Ink seen', 'কালি দেখা গেছে'], tone: 'neutral' },
  empty: { words: ['Empty', 'ফাঁকা'], tone: 'neutral' },
}

export const OWNERSHIP: Record<string, Pair> = {
  sole_proprietor: ['Sole proprietor', 'একক মালিক'],
  partnership: ['Partnership', 'অংশীদারি'],
  company: ['Company', 'কোম্পানি'],
  cooperative: ['Cooperative', 'সমবায়'],
  other: ['Other', 'অন্যান্য'],
}

/** The details of the form: key, English, Bangla, required. Same order as the printed form. */
export const DETAILS: [string, string, string, boolean][] = [
  ['shop_name', 'Business name', 'ব্যবসার নাম', true],
  ['legal_name', 'Legal or trading name', 'আইনি বা ট্রেডিং নাম', false],
  ['owner_name', 'Owner’s full name', 'মালিকের পুরো নাম', true],
  ['owner_mobile', 'Primary mobile number', 'প্রধান মোবাইল নম্বর', true],
  ['alternate_contact', 'Alternate contact number', 'বিকল্প যোগাযোগ নম্বর', false],
  ['district', 'District', 'জেলা', true],
  ['area', 'Market or area', 'বাজার বা এলাকা', true],
  ['shop_type', 'Business category', 'ব্যবসার ধরন', true],
  ['ownership_type', 'Ownership type', 'মালিকানার ধরন', true],
  ['established_year', 'Year established', 'প্রতিষ্ঠার বছর', false],
  ['trade_license_number', 'Trade licence number', 'ট্রেড লাইসেন্স নম্বর', false],
  ['branches', 'Number of outlets', 'দোকানের সংখ্যা', false],
  ['representative_name', 'Authorised representative', 'অনুমোদিত প্রতিনিধি', false],
  ['representative_mobile', 'Representative’s mobile', 'প্রতিনিধির মোবাইল', false],
]

/** The boxes the merchant ticks on the form. None is pre-ticked anywhere. */
export const CORE_BOXES: [string, Pair][] = [
  ['purchases', ['Wholesale purchases from suppliers', 'সরবরাহকারীর কাছ থেকে পাইকারি কেনাকাটা']],
  ['deliveries', ['Parcel deliveries', 'পার্সেল ডেলিভারি']],
  ['payments', ['Loan repayments', 'ঋণ পরিশোধ']],
  ['field_visits', ['Notes from staff visits', 'কর্মীদের পরিদর্শনের নোট']],
]
export const OPTIONAL_BOXES: [string, Pair][] = [
  ['questionnaire', ['Answers to a short questionnaire (optional)', 'ছোট প্রশ্নমালার উত্তর (ঐচ্ছিক)']],
  ['declared_obligations', ['Record existing loans I choose to tell you about (optional)', 'আমার জানানো বিদ্যমান ঋণ রাখা (ঐচ্ছিক)']],
  ['share_other_providers', ['Share my assessment with providers I name in writing (optional)', 'আমার নামোল্লেখ করা অন্য প্রতিষ্ঠানের সাথে মূল্যায়ন ভাগ (ঐচ্ছিক)']],
]

/** Fetch a file with the signed-in session and hand it to the browser as a download. */
export async function saveBlob(path: string, filename: string) {
  const blob = await apiBlob(path)
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 30_000)
}
