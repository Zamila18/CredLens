/**
 * Band colours (DESIGN_SPEC.md section 4). Bands differ in lightness as well as hue,
 * and "Needs more info" is periwinkle with a dashed edge, never an alarm colour.
 */
import type { Band } from '@/api/types'

/** Score arc colour on the LensDial. */
export const BAND_ARC: Record<Band, string> = {
  Strong: '#0E5A4A',
  Review: '#B5650D',
  'Needs more info': '#8A97BF',
}

/** Chip classes. `null` is "no band": no consent, or nothing to show. */
export function bandChipClass(band: Band | null): string {
  switch (band) {
    case 'Strong':
      return 'bg-strong-chip text-lens-dark'
    case 'Review':
      return 'bg-amber-chip text-amber-text'
    case 'Needs more info':
      return 'bg-peri-chip text-peri-text shadow-[inset_0_0_0_1.5px_#8A97BF]'
    default:
      return 'bg-neutral-chip text-neutral-text'
  }
}

/** Colour of the score number: greyed for a thin file, rust under the warning line, else ink. */
export function scoreNumberClass(band: Band | null, lowScoreWarning: boolean | null | undefined): string {
  if (band === 'Needs more info') return 'text-peri-number'
  if (lowScoreWarning) return 'text-rust'
  return 'text-ink'
}
