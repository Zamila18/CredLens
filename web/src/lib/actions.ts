/**
 * The four officer actions, in plain words. There is no approve or decline: the officer goes
 * with the suggestion, lends more or less than it suggests (with a written reason), or asks for
 * more records. The codes (accept, override_up, ...) are what the server stores.
 */
import type { OfficerAction } from '@/api/types'

export const ACTIONS: { value: OfficerAction; label: string; hint: string }[] = [
  { value: 'accept', label: 'Go with the suggestion', hint: 'I agree with the summary above' },
  { value: 'override_up', label: 'Lend more than suggested', hint: 'I see more strength than the summary' },
  { value: 'override_down', label: 'Lend less than suggested', hint: 'I see a risk the summary misses' },
  { value: 'needs_more_info', label: 'Ask for more records', hint: 'Wait for more receipts first' },
]

/** Short names for chips and filters. */
export const ACTION_SHORT: Record<OfficerAction, string> = {
  accept: 'Agreed',
  override_up: 'Lend more',
  override_down: 'Lend less',
  needs_more_info: 'More records asked',
}

export function isOverride(action: OfficerAction | null | undefined): boolean {
  return action === 'override_up' || action === 'override_down'
}
