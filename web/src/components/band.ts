/**
 * Band colours (approved design sheet, sections 4 and 5). Every band is also written in
 * words. "Needs more info" is violet on its chip and a muted grey on the ring and bar
 * (too little evidence to lean on the number), never an alarm colour. Red is for errors only.
 */
import type { Band } from '@/api/types'

/** Score arc colour on the LensDial. */
export const BAND_ARC: Record<Band, string> = {
  Strong: '#16845B',
  Review: '#B7791F',
  'Needs more info': '#8E9AAD',
}

/** Chip classes. `null` is "no band": no consent, or nothing to show. */
export function bandChipClass(band: Band | null): string {
  switch (band) {
    case 'Strong':
      return 'bg-strong-chip text-lens-dark'
    case 'Review':
      return 'bg-amber-chip text-amber-text'
    case 'Needs more info':
      return 'bg-peri-chip text-peri-text'
    default:
      return 'bg-neutral-chip text-neutral-text'
  }
}

/** Coloured dot inside a band chip. */
export const BAND_DOT: Record<Band, string> = {
  Strong: 'bg-band-strong',
  Review: 'bg-band-review',
  'Needs more info': 'bg-band-nmi',
}

/** Coverage bar fill: the band colour; grey for a thin file. */
export const BAND_BAR: Record<Band, string> = {
  Strong: 'bg-band-strong',
  Review: 'bg-band-review',
  'Needs more info': 'bg-[#8E9AAD]',
}

/** Colour of the score number: muted (still readable) for a thin file, else ink. */
export function scoreNumberClass(band: Band | null, lowScoreWarning: boolean | null | undefined): string {
  void lowScoreWarning // a low score is shown by the ring and the chip, not by an alarm colour
  if (band === 'Needs more info') return 'text-[#5F6B80]'
  return 'text-ink'
}
