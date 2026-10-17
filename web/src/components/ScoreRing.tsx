/**
 * ScoreRing (approved design sheet, section 5): the score as a ring with "/100".
 * The ring takes the band colour: green Strong, amber Review, muted grey for Needs more info
 * (too little evidence to lean on the number; the number stays readable).
 * A ring is never shown alone: put the band chip and the coverage next to it.
 */
import type { Band } from '@/api/types'
import { bandText, useLang, useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { BAND_ARC, scoreNumberClass } from './band'

type Props = {
  score: number
  band: Band
  coverage: number
  size?: number
  className?: string
}

export function ScoreRing({ score, band, coverage, size = 104, className }: Props) {
  const t = useT()
  const lang = useLang()
  const stroke = Math.max(7, Math.round(size * 0.09))
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const label = t(
    `Score ${score} of 100, ${band}, coverage ${Math.round(coverage * 100)} percent`,
    `স্কোর ১০০-এর মধ্যে ${score}, ${bandText(band, lang)}, কভারেজ ${Math.round(coverage * 100)} শতাংশ`,
  )
  return (
    <div className={cn('relative shrink-0', className)} style={{ width: size, height: size }} role="img" aria-label={label}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#E6EEF0" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={BAND_ARC[band]}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${((c * Math.min(100, Math.max(0, score))) / 100).toFixed(1)} ${c.toFixed(1)}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center" aria-hidden="true">
        <span
          className={cn('font-display leading-none font-bold tabular', scoreNumberClass(band, false))}
          style={{ fontSize: Math.round(size * 0.34) }}
        >
          {score}
        </span>
        <span className="text-xs text-muted-2" style={{ fontSize: Math.max(11, Math.round(size * 0.11)) }}>
          /100
        </span>
      </div>
    </div>
  )
}
