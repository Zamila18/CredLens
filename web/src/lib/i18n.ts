/**
 * English and Bangla for the whole dashboard.
 *
 * The language switch in the sidebar changes every word on every page, not only the
 * reasons. Each piece of text is written in both languages where it is used:
 *
 *   const t = useT()
 *   <h1>{t('Review queue', 'পর্যালোচনার তালিকা')}</h1>
 *
 * Words that come from the API as codes (bands, actions, data sources, roles) are
 * translated here, once. Numbers stay in English digits in both languages, as the
 * reasons and summaries from the API do.
 *
 * The Bangla needs a native-speaker review before the demo (CLAUDE.md, HUMAN STEP).
 */
import { useCallback } from 'react'

import type { Band, DataMode, OfficerAction, Role } from '@/api/types'
import { useSession, type Lang } from '@/app/session-context'

export type { Lang }

/** Pick the English or the Bangla of one piece of text. */
export type T = (en: string, bn: string) => string

/** The text picker for the current language. */
export function useT(): T {
  const { lang } = useSession()
  return useCallback((en: string, bn: string) => (lang === 'bn' ? bn : en), [lang])
}

/** The current language, for code that needs more than a text pick. */
export function useLang(): Lang {
  return useSession().lang
}

export type Pair = { en: string; bn: string }

export function pick(pair: Pair, lang: Lang): string {
  return lang === 'bn' ? pair.bn : pair.en
}

/** Band names. The API sends the English name; this is what the page shows. */
export const BAND_TEXT: Record<Band, Pair> = {
  Strong: { en: 'Strong', bn: 'শক্তিশালী' },
  Review: { en: 'Review', bn: 'পর্যালোচনা' },
  'Needs more info': { en: 'Needs more info', bn: 'আরও তথ্য প্রয়োজন' },
}

export function bandText(band: Band | null | undefined, lang: Lang): string {
  return band ? pick(BAND_TEXT[band], lang) : lang === 'bn' ? 'কোনো ব্যান্ড নেই' : 'No band'
}

/** Data sources: short names for the sidebar and the model card tabs. */
export const MODE_TEXT: Record<DataMode, Pair> = {
  synthetic_bd: { en: 'Synthetic', bn: 'সিনথেটিক' },
  taiwan_cc: { en: 'Taiwan cards', bn: 'তাইওয়ান ক্রেডিট কার্ড' },
  india_ltfs: { en: 'India vehicle loans', bn: 'ভারত গাড়ির ঋণ' },
  homecredit: { en: 'Home Credit · country not stated', bn: 'হোম ক্রেডিট · দেশ উল্লেখ নেই' },
  kiva_asia: { en: 'Kiva Asia', bn: 'কিভা এশিয়া' },
}

/**
 * The banner sentence of each data source in Bangla. The English comes from GET /health
 * (src/config.py SOURCE_LABELS); keep the two in step.
 */
export const BANNER_BN: Record<DataMode, string> = {
  synthetic_bd: 'সিনথেটিক ডেমো ডেটা। শুধু সিদ্ধান্তে সহায়তা।',
  taiwan_cc: 'পাবলিক ডেটা: তাইওয়ানের ক্রেডিট কার্ড, ShopUp-এর ডেটা নয়। শুধু সিদ্ধান্তে সহায়তা।',
  india_ltfs: 'পাবলিক ডেটা: ভারতের L&T গাড়ির ঋণ, ShopUp-এর ডেটা নয়। শুধু সিদ্ধান্তে সহায়তা।',
  homecredit: 'পাবলিক ডেটা: হোম ক্রেডিট (দেশ উল্লেখ নেই), ShopUp-এর ডেটা নয়। শুধু সিদ্ধান্তে সহায়তা।',
  kiva_asia: 'পাবলিক ডেটা: কিভা (এশিয়া), ShopUp-এর ডেটা নয়। শুধু সিদ্ধান্তে সহায়তা।',
}

/** The officer's four actions. There is no approve or decline. */
export const ACTION_TEXT: Record<OfficerAction, { label: Pair; short: Pair; hint: Pair }> = {
  accept: {
    label: { en: 'Go with the suggestion', bn: 'প্রস্তাব অনুযায়ী এগোন' },
    short: { en: 'Agreed', bn: 'একমত' },
    hint: { en: 'I agree with the summary above', bn: 'উপরের সারসংক্ষেপের সাথে একমত' },
  },
  override_up: {
    label: { en: 'Lend more than suggested', bn: 'প্রস্তাবের চেয়ে বেশি দিন' },
    short: { en: 'Lend more', bn: 'বেশি দিন' },
    hint: { en: 'I see more strength than the summary', bn: 'সারসংক্ষেপের চেয়ে বেশি শক্তি দেখছি' },
  },
  override_down: {
    label: { en: 'Lend less than suggested', bn: 'প্রস্তাবের চেয়ে কম দিন' },
    short: { en: 'Lend less', bn: 'কম দিন' },
    hint: { en: 'I see a risk the summary misses', bn: 'সারসংক্ষেপে ধরা পড়েনি এমন ঝুঁকি দেখছি' },
  },
  needs_more_info: {
    label: { en: 'Ask for more records', bn: 'আরও রেকর্ড চান' },
    short: { en: 'More records asked', bn: 'আরও রেকর্ড চাওয়া' },
    hint: { en: 'Wait for more receipts first', bn: 'আগে আরও রসিদ আসুক' },
  },
}

export const ROLE_TEXT: Record<Role, Pair> = {
  platform_admin: { en: 'Platform admin', bn: 'প্ল্যাটফর্ম অ্যাডমিন' },
  credit_officer: { en: 'Credit officer', bn: 'ক্রেডিট অফিসার' },
  records_officer: { en: 'Records Desk', bn: 'রেকর্ড ডেস্ক' },
  merchant: { en: 'Merchant', bn: 'ব্যবসায়ী' },
  auditor: { en: 'Auditor', bn: 'অডিটর' },
}

/** Town tiers and shop types, as the data holds them. Unknown values are shown as they are. */
export const VALUE_TEXT: Record<string, Pair> = {
  metro: { en: 'metro', bn: 'মহানগর' },
  city: { en: 'city', bn: 'শহর' },
  small_town: { en: 'small town', bn: 'ছোট শহর' },
  grocery: { en: 'grocery', bn: 'মুদি দোকান' },
  pharmacy: { en: 'pharmacy', bn: 'ফার্মেসি' },
  apparel: { en: 'apparel', bn: 'কাপড়ের দোকান' },
  electronics: { en: 'electronics', bn: 'ইলেকট্রনিক্স' },
  other: { en: 'other', bn: 'অন্যান্য' },
  // Yes/no columns (trade licence) as the group audit writes them.
  True: { en: 'yes', bn: 'আছে' },
  False: { en: 'no', bn: 'নেই' },
}

export function valueText(value: string | null | undefined, lang: Lang): string {
  if (!value) return '—'
  return VALUE_TEXT[value] ? pick(VALUE_TEXT[value], lang) : value
}

/** Consent data categories. */
export const CATEGORY_TEXT: Record<string, Pair> = {
  purchases: { en: 'purchases', bn: 'কেনাকাটা' },
  deliveries: { en: 'deliveries', bn: 'ডেলিভারি' },
  payments: { en: 'payments', bn: 'পেমেন্ট' },
  questionnaire: { en: 'the questionnaire', bn: 'প্রশ্নাবলি' },
  field_visits: { en: 'field visit notes', bn: 'মাঠ পরিদর্শনের নোট' },
}

/** ["purchases", "payments", "questionnaire"] -> "purchases, payments and the questionnaire". */
export function listInWords(items: string[], lang: Lang): string {
  const words = items.map((c) => (CATEGORY_TEXT[c] ? pick(CATEGORY_TEXT[c], lang) : c.replaceAll('_', ' ')))
  if (words.length <= 1) return words.join('')
  const and = lang === 'bn' ? ' এবং ' : ' and '
  return `${words.slice(0, -1).join(', ')}${and}${words[words.length - 1]}`
}

/** One consent category as a short chip word ("purchases", "কেনাকাটা"). */
export function categoryWord(code: string, lang: Lang): string {
  if (lang === 'en') return code.replaceAll('_', ' ')
  return CATEGORY_TEXT[code]?.bn ?? code.replaceAll('_', ' ')
}

/** Consent purposes. */
export const PURPOSE_TEXT: Record<string, Pair> = {
  credit_readiness_assessment: { en: 'Credit readiness assessment', bn: 'ঋণের প্রস্তুতি যাচাই' },
}

/** Questionnaire groups. */
export const GROUP_TEXT: Record<string, Pair> = {
  Spend: { en: 'Spend', bn: 'খরচ' },
  Save: { en: 'Save', bn: 'সঞ্চয়' },
  Borrow: { en: 'Borrow', bn: 'ধার' },
  Plan: { en: 'Plan', bn: 'পরিকল্পনা' },
  Context: { en: 'Context', bn: 'প্রেক্ষাপট' },
}

/** Timeline streams. */
export const STREAM_TEXT: Record<string, Pair> = {
  purchase: { en: 'Purchase', bn: 'কেনা' },
  delivery: { en: 'Delivery', bn: 'ডেলিভারি' },
  payment: { en: 'Payment', bn: 'পেমেন্ট' },
  loan: { en: 'Loan', bn: 'ঋণ' },
}
