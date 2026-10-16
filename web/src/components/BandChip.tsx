/**
 * BandChip: the band as a coloured pill. With `lowScoreWarning` (and a band other
 * than Needs more info) it reads "Review · low score".
 */
import type { ReactNode } from 'react'

import type { Band } from '@/api/types'
import { BAND_TEXT, pick, useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { bandChipClass } from './band'

type Props = {
  band: Band | null
  lowScoreWarning?: boolean | null
  /** Text when there is no band, e.g. "Consent needed". */
  noneLabel?: string
  size?: 'sm' | 'md'
  className?: string
}

export function BandChip({ band, lowScoreWarning, noneLabel, size = 'sm', className }: Props) {
  const lang = useLang()
  const name = band ? pick(BAND_TEXT[band], lang) : ''
  const label = band
    ? lowScoreWarning && band !== 'Needs more info'
      ? `${name} · ${lang === 'bn' ? 'কম স্কোর' : 'low score'}`
      : name
    : (noneLabel ?? (lang === 'bn' ? 'কোনো ব্যান্ড নেই' : 'No band'))
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full font-semibold whitespace-nowrap',
        size === 'sm' ? 'px-2.5 py-0.5 text-xs leading-[18px]' : 'px-3 py-1 text-[13px]',
        bandChipClass(band),
        className,
      )}
    >
      {label}
    </span>
  )
}

/** A plain neutral pill (Pending, roles, "admin" tags). */
export function Chip({ children, tone = 'neutral', className }: { children: ReactNode; tone?: 'neutral' | 'strong' | 'amber' | 'peri'; className?: string }) {
  const tones = {
    neutral: 'bg-neutral-chip text-neutral-text',
    strong: 'bg-strong-chip text-lens-dark',
    amber: 'bg-amber-chip text-amber-text',
    peri: 'bg-peri-chip text-peri-text',
  }
  return (
    <span className={cn('inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs leading-[18px] font-semibold whitespace-nowrap', tones[tone], className)}>
      {children}
    </span>
  )
}
