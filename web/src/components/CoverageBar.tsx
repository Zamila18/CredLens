/**
 * CoverageBar: how much of the expected evidence exists (not the score).
 * 96×6px; striped periwinkle when the band is Needs more info.
 */
import type { Band } from '@/api/types'
import { cn } from '@/lib/utils'
import { useT } from '@/lib/i18n'

export function CoverageBar({ coverage, band }: { coverage: number; band: Band | null }) {
  const t = useT()
  const percent = Math.round(coverage * 100)
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 overflow-hidden rounded-[3px] bg-track" aria-hidden="true">
        <span
          className={cn('block h-1.5', band === 'Needs more info' ? 'stripes-nmi' : 'bg-coverage')}
          style={{ width: `${percent}%` }}
        />
      </div>
      <span className="font-mono text-xs text-muted tabular">{percent}% {t('coverage', 'কভারেজ')}</span>
    </div>
  )
}
