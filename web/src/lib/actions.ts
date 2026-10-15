/**
 * The four officer actions. There is no approve or decline: the officer accepts the
 * suggestion, overrides it (with a written reason), or asks for more information.
 */
import type { OfficerAction } from '@/api/types'

export const ACTIONS: { value: OfficerAction; label: string; hint: string }[] = [
  { value: 'accept', label: 'Accept suggestion', hint: 'Agree with the band' },
  { value: 'override_up', label: 'Override: raise', hint: 'You see more strength than the score' },
  { value: 'override_down', label: 'Override: lower', hint: 'You see risk the score misses' },
  { value: 'needs_more_info', label: 'Needs more info', hint: 'Collect more evidence first' },
]

/** Short names for chips and filters ("Accept", not "Accept suggestion"). */
export const ACTION_SHORT: Record<OfficerAction, string> = {
  accept: 'Accept',
  override_up: 'Override: raise',
  override_down: 'Override: lower',
  needs_more_info: 'Needs more info',
}

export function isOverride(action: OfficerAction | null | undefined): boolean {
  return action === 'override_up' || action === 'override_down'
}
