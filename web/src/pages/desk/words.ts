/** Plain words for the Records Desk screens (receipt kinds and states). */
import type { Pair } from '@/lib/i18n'

export const KIND_WORDS: Record<string, Pair> = {
  purchase: { en: 'Purchase receipt', bn: 'ক্রয়ের রসিদ' },
  delivery: { en: 'Delivery slip', bn: 'ডেলিভারি স্লিপ' },
  repayment: { en: 'Repayment slip', bn: 'পরিশোধের রসিদ' },
}

export const STATUS_WORDS: Record<string, Pair & { tone: 'amber' | 'strong' | 'neutral' | 'peri' }> = {
  extracted: { en: 'Needs checking', bn: 'যাচাই বাকি', tone: 'amber' },
  checked: { en: 'Checked, not published', bn: 'যাচাই হয়েছে, প্রকাশ বাকি', tone: 'peri' },
  published: { en: 'Published', bn: 'প্রকাশিত', tone: 'strong' },
  rejected: { en: 'Rejected', bn: 'বাতিল', tone: 'neutral' },
}

export const TONES = {
  amber: 'bg-amber-chip text-amber-text',
  strong: 'bg-strong-chip text-lens-dark',
  neutral: 'bg-neutral-chip text-neutral-text',
  peri: 'bg-peri-chip text-peri-text',
} as const

export const OUTCOME_WORDS: Record<string, Pair> = {
  delivered: { en: 'Delivered', bn: 'পৌঁছেছে' },
  returned: { en: 'Returned', bn: 'ফেরত' },
  failed: { en: 'Failed', bn: 'ব্যর্থ' },
}
