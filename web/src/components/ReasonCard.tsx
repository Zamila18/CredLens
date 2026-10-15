/**
 * ReasonCard: one plain sentence behind a score, its points and a bar.
 *
 * - The sentence is English or Bangla by the language toggle.
 * - The bar width is |contribution| ÷ the largest |contribution| on the screen, so
 *   small numbers (most reasons move a score by 0.2 to 6 points) still read.
 * - `reason.code` is a feature name for logs. It is never shown to officers.
 */
import type { Lang } from '@/app/session-context'
import type { Reason } from '@/api/types'
import { pts } from '@/lib/format'
import { cn } from '@/lib/utils'

type Props = {
  reason: Reason
  lang: Lang
  /** Largest |contribution| among the reasons on the screen. */
  maxAbs: number
}

export function ReasonCard({ reason, lang, maxAbs }: Props) {
  const helps = reason.contribution >= 0
  const sentence = lang === 'bn' ? reason.sentence_bn : reason.sentence_en
  const width = maxAbs > 0 ? Math.max(3, (Math.abs(reason.contribution) / maxAbs) * 100) : 0

  return (
    <div className={cn('flex flex-col gap-1.5 rounded-panel p-3', helps ? 'bg-strong-panel' : 'bg-amber-panel')}>
      <div className="flex items-baseline justify-between gap-2.5">
        <span className={cn('text-sm', lang === 'bn' ? 'font-bn leading-[22px]' : 'leading-5')}>{sentence}</span>
        <span className={cn('font-mono text-[13px] font-semibold whitespace-nowrap tabular', helps ? 'text-lens-dark' : 'text-amber-text')}>
          {pts(reason.contribution)}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded bg-line-soft" aria-hidden="true">
        <span className={cn('block h-2', helps ? 'bg-lens' : 'bg-amber')} style={{ width: `${width}%` }} />
      </div>
      {reason.detail && <span className="font-mono text-xs text-muted-2">{reason.detail}</span>}
    </div>
  )
}
