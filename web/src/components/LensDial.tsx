/**
 * LensDial (Lens.dc.html): a score is never alone. The inner ring is the score, the
 * outer ring is coverage, and the band chip and coverage figure sit underneath.
 *
 * Two forms:
 *   <LensDial score={94} coverage={0.85} band="Strong" lowScoreWarning={false} />
 *   <LensDial noConsent />   (grey rings, padlock, "No score", "Consent needed")
 * A score cannot be passed without its coverage and band: TypeScript refuses it.
 */
import type { Band } from '@/api/types'
import { cn } from '@/lib/utils'
import { BAND_ARC, scoreNumberClass } from './band'
import { BandChip } from './BandChip'
import { LockIcon } from './icons'

type Scored = {
  noConsent?: false
  score: number
  coverage: number
  band: Band
  lowScoreWarning: boolean
}
type NoConsent = { noConsent: true }

const R_SCORE = 70
const R_COVER = 90
const C_SCORE = 2 * Math.PI * R_SCORE
const C_COVER = 2 * Math.PI * R_COVER

export function LensDial(props: Scored | NoConsent) {
  const scored = !props.noConsent
  const score = scored ? props.score : 0
  const coverage = scored ? props.coverage : 0
  const band = scored ? props.band : null
  const warn = scored ? props.lowScoreWarning : false
  const coverPct = Math.round(coverage * 100)

  const aria = scored
    ? `Score ${score} of 100, band ${band}, coverage ${coverPct} percent`
    : 'No score: consent needed'

  return (
    <div className="flex w-[220px] flex-col items-center gap-2.5">
      <div className="relative size-[200px]">
        <svg width="200" height="200" viewBox="0 0 200 200" role="img" aria-label={aria}>
          {/* Outer track (dashed) and coverage arc */}
          <circle cx="100" cy="100" r={R_COVER} fill="none" stroke="#C3C9C0" strokeWidth="3" strokeDasharray="2 5" />
          {scored && (
            <circle
              cx="100" cy="100" r={R_COVER} fill="none" stroke="#2D4F45" strokeWidth="6" strokeLinecap="round"
              strokeDasharray={`${(C_COVER * coverage).toFixed(1)} ${C_COVER.toFixed(1)}`}
              transform="rotate(-90 100 100)"
            />
          )}
          {/* Inner track and score arc */}
          <circle cx="100" cy="100" r={R_SCORE} fill="none" stroke="#E8EAE4" strokeWidth="14" />
          {scored && band && (
            <circle
              cx="100" cy="100" r={R_SCORE} fill="none" stroke={BAND_ARC[band]} strokeWidth="14" strokeLinecap="round"
              strokeDasharray={`${((C_SCORE * score) / 100).toFixed(1)} ${C_SCORE.toFixed(1)}`}
              transform="rotate(-90 100 100)"
            />
          )}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center" aria-hidden="true">
          {scored ? (
            <>
              <span className={cn('font-mono text-[54px] leading-[58px] font-semibold tracking-[-0.03em] tabular', scoreNumberClass(band, warn))}>
                {score}
              </span>
              <span className="-mt-1 text-xs text-muted-2">of 100</span>
            </>
          ) : (
            <>
              <LockIcon size={26} />
              <span className="mt-1 text-[13px] font-semibold text-neutral-text">No score</span>
            </>
          )}
        </div>
      </div>
      <div className="flex flex-col items-center gap-1.5">
        <BandChip band={band} lowScoreWarning={warn} noneLabel="Consent needed" size="md" />
        <span className="font-mono text-xs text-muted tabular">{scored ? `coverage ${coverPct}%` : 'scoring blocked'}</span>
      </div>
    </div>
  )
}
