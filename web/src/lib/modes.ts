/**
 * Data modes. The API picks the mode from its config (GET /health says which);
 * the dashboard only reads it.
 */
import type { DataMode } from '@/api/types'

/** Short names for the sidebar and the model card tabs. */
export const MODE_LABELS: Record<DataMode, string> = {
  synthetic_bd: 'Synthetic',
  taiwan_cc: 'Taiwan cards',
  india_ltfs: 'India vehicle loans',
  homecredit: 'Home Credit · country not stated',
  kiva_asia: 'Kiva Asia',
}

/** Order of the model card tabs. */
export const MODE_ORDER: DataMode[] = ['synthetic_bd', 'taiwan_cc', 'india_ltfs', 'homecredit', 'kiva_asia']

/**
 * Only the synthetic mode has merchants to review. In a public mode every outcome
 * is already known, so there is no queue: the model card and totals only.
 */
export function hasQueue(mode: DataMode | undefined): boolean {
  return mode === 'synthetic_bd'
}
