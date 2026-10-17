/**
 * CoverageBar: how much of the expected evidence exists (not the score).
 * The fill takes the band colour; grey for a thin file (Needs more info).
 * `wide` stretches the bar to its container (score cards); the default is 96px (lists).
 */
import type { Band } from '@/api/types'
import { useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { BAND_BAR } from './band'

export function CoverageBar({
  coverage,
  band,
  wide = false,
  label = true,
}: {
  coverage: number
  band: Band | null
  wide?: boolean
  /** False when a big percentage is already shown next to the bar. */
  label?: boolean
}) {
  const t = useT()
  const percent = Math.round(coverage * 100)
  return (
    <div className={cn('flex items-center gap-2', wide && 'w-full')}>
      <div
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        aria-label={t('Coverage', 'কভারেজ')}
        className={cn('h-2 overflow-hidden rounded-full bg-track', wide ? 'flex-1' : 'w-24')}
      >
        <span className={cn('block h-2 rounded-full', band ? BAND_BAR[band] : 'bg-coverage')} style={{ width: `${percent}%` }} />
      </div>
      {label && (
        <span className="font-mono text-xs text-muted tabular">
          {percent}% {t('coverage', 'কভারেজ')}
        </span>
      )}
    </div>
  )
}
