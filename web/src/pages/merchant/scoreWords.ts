/**
 * Words for the score card's full input list and coverage checklist (Oct 17), in English
 * and Bangla. The API sends codes (`deliveries_present`, `return_rate_90d`); the page
 * shows these words. A code missing here is shown in plain words made from the code.
 */
import type { Lang } from '@/app/session-context'

type Pair = { en: string; bn: string }

/** The coverage checklist of the synthetic data (config `coverage_weights`). */
export const COVERAGE_ITEM: Record<string, Pair> = {
  history_6_months: { en: 'At least 6 months of history', bn: 'অন্তত 6 মাসের ইতিহাস' },
  purchases_present: { en: 'Regular stock purchases', bn: 'নিয়মিত মাল কেনা' },
  payments_present: { en: 'Repayment history', bn: 'পরিশোধের ইতিহাস' },
  deliveries_present: { en: 'Delivery records (optional)', bn: 'ডেলিভারির রেকর্ড (ঐচ্ছিক)' },
  questionnaire_done: { en: 'Questionnaire answered', bn: 'প্রশ্নাবলির উত্তর দেওয়া' },
  recent_activity_30d: { en: 'Active in the last 30 days', bn: 'গত 30 দিনে সক্রিয়' },
}

/** Where an input's data comes from. */
export const GROUP: Record<string, Pair> = {
  purchases: { en: 'Purchases', bn: 'কেনাকাটা' },
  payments: { en: 'Repayments', bn: 'পরিশোধ' },
  deliveries: { en: 'Deliveries', bn: 'ডেলিভারি' },
  questionnaire: { en: 'Questionnaire', bn: 'প্রশ্নাবলি' },
}

/** Bangla names of the synthetic model's inputs (the English comes from the API). */
export const INPUT_BN: Record<string, string> = {
  basket_growth: 'কেনাকাটার বৃদ্ধি',
  supplier_repeat_share: 'একই সরবরাহকারী থেকে কেনা',
  avg_pay_delay_days: 'গড়ে পরিশোধে দেরি',
  late_pay_count_90d: '90 দিনে দেরিতে পরিশোধ',
  ontime_payment_rate: 'সময়মতো পরিশোধ',
  credit_utilisation: 'ঋণসীমার ব্যবহার',
  return_rate_90d: 'ফেরত',
  failed_rate_90d: 'ব্যর্থ ডেলিভারি',
  cod_remit_ontime_rate: 'ক্যাশ-অন-ডেলিভারির টাকা সময়মতো ফেরত',
  dispatch_to_delivery_hours: 'ডেলিভারির সময়',
}

function plain(code: string): string {
  const words = code.replace(/_/g, ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}

export function coverageItemText(item: string, lang: Lang): string {
  const pair = COVERAGE_ITEM[item]
  return pair ? pair[lang] : plain(item)
}

export function groupText(group: string, lang: Lang): string {
  const pair = GROUP[group]
  return pair ? pair[lang] : plain(group)
}

export function inputName(code: string, label: string, lang: Lang): string {
  return lang === 'bn' && INPUT_BN[code] ? INPUT_BN[code] : label
}

/** The id of the evidence group (on the review's records panel) that a model input group reads. */
export function groupAnchor(group: string): string | null {
  const id = ({ purchases: 'purchases', payments: 'repayments', deliveries: 'deliveries' } as Record<string, string>)[group]
  return id ? `records-${id}` : null
}
