/**
 * Right column of the merchant page (Merchant.dc.html): score card, reasons, the
 * financial habits panel and "Why might this be wrong?". Every number comes from
 * GET /merchants/{id}/score or the profile.
 */
import type { ReactNode } from 'react'

import type { Lang } from '@/app/session-context'
import type { Band, MerchantProfile, Reason, Score } from '@/api/types'
import { Chip } from '@/components/BandChip'
import { LensDial } from '@/components/LensDial'
import { Card, Eyebrow } from '@/components/Page'
import { ReasonCard } from '@/components/ReasonCard'
import { fmtDate, pct } from '@/lib/format'
import { cn } from '@/lib/utils'

/** What each band asks of the officer. Describes; never says lend or do not lend. */
const BAND_MEANING: Record<Band, string> = {
  Strong: 'Strong: a high score with enough evidence behind it. Proceed with normal checks.',
  Review: 'Review: the score is under the Strong line. Read every reason before deciding.',
  'Needs more info': 'Needs more info: too little evidence to rely on the number. The ask is more evidence, not a lower band.',
}

function Mono({ children }: { children: ReactNode }) {
  return <span className="font-mono font-semibold tabular">{children}</span>
}

export function ScoreCard({ score, lang }: { score: Score; lang: Lang }) {
  const summary = lang === 'bn' ? (score.summary_bn ?? score.summary_en) : score.summary_en
  const summaryIsBn = lang === 'bn' && Boolean(score.summary_bn)
  return (
    <Card className="flex flex-col">
      {summary && (
        <div className="flex flex-col gap-1.5 border-b border-line-soft px-5 pt-5 pb-4">
          <Eyebrow>Summary</Eyebrow>
          <p className={cn('m-0 text-[15px]', summaryIsBn ? 'font-bn leading-[26px]' : 'leading-[23px]')}>{summary}</p>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-5 p-5">
        <LensDial score={score.score} coverage={score.coverage} band={score.band} lowScoreWarning={score.low_score_warning} />
        <div className="flex flex-[1_1_200px] flex-col gap-3">
          <h2 className="m-0">
            <Eyebrow>Readiness score</Eyebrow>
          </h2>
          <p className="m-0 text-[15px] leading-[22px]">
            Calibrated probability of repaying within 30 days of the due date: <Mono>{score.probability.toFixed(2)}</Mono>,
            shown as <Mono>{score.score}</Mono>.
          </p>
          <p className="m-0 text-sm leading-[21px] text-ink-3">
            <span className="font-semibold">Coverage {pct(score.coverage)}</span> is how much of the expected evidence
            exists. It is not the score. The outer ring fills with it.
          </p>
          <p className="m-0 text-[13px] text-muted-2">{BAND_MEANING[score.band]}</p>
          {score.low_score_warning && (
            <p className="m-0 text-[13px] font-medium text-rust">Low score: read every reason before deciding.</p>
          )}
        </div>
      </div>
    </Card>
  )
}

/** "1.2" for the equation line; the sign is written separately. */
function abs1(n: number) {
  return Math.abs(n).toFixed(1)
}

function sum(reasons: Reason[]) {
  return reasons.reduce((total, r) => total + r.contribution, 0)
}

export function WhyThisScore({ score, lang }: { score: Score; lang: Lang }) {
  const helps = score.reasons_positive
  const holds = score.reasons_negative
  const maxAbs = Math.max(0, ...[...helps, ...holds].map((r) => Math.abs(r.contribution)))
  const helpsTotal = sum(helps)
  const holdsTotal = sum(holds)
  const other = score.other_contribution

  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="m-0 text-lg font-semibold">Why this score</h2>
        <span className="text-xs text-muted-2">Observations, not causes</span>
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-4">
        <div className="flex flex-col gap-2.5">
          <span className="text-[13px] font-semibold text-lens-dark">Helps</span>
          {helps.length === 0 && <span className="text-[13px] text-muted">Nothing stands out for this merchant.</span>}
          {helps.map((r, i) => (
            <ReasonCard key={i} reason={r} lang={lang} maxAbs={maxAbs} />
          ))}
        </div>
        <div className="flex flex-col gap-2.5">
          <span className="text-[13px] font-semibold text-amber-text">Holds back</span>
          {holds.length === 0 && <span className="text-[13px] text-muted">Nothing stands out for this merchant.</span>}
          {holds.map((r, i) => (
            <ReasonCard key={i} reason={r} lang={lang} maxAbs={maxAbs} />
          ))}
        </div>
      </div>
      {/* baseline + helps + holds back + everything else = score */}
      <div
        className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5 rounded-[10px] bg-ground px-3.5 py-3 font-mono text-[13px] text-ink-2 tabular"
        aria-label={`Average merchant ${abs1(score.baseline_score)}, plus ${abs1(helpsTotal)} from what helps, minus ${abs1(holdsTotal)} from what holds back, ${other < 0 ? 'minus' : 'plus'} ${abs1(other)} from everything else, gives ${score.score}`}
      >
        <span>{score.baseline_score.toFixed(1)} average merchant</span>
        <span aria-hidden="true">+</span>
        <span className="text-lens-dark">{abs1(helpsTotal)} helps</span>
        <span aria-hidden="true">−</span>
        <span className="text-amber-text">{abs1(holdsTotal)} holds back</span>
        <span aria-hidden="true">{other < 0 ? '−' : '+'}</span>
        <span>{abs1(other)} everything else</span>
        <span aria-hidden="true">=</span>
        <span className="font-semibold">{score.score}</span>
      </div>
    </Card>
  )
}

const HABITS: { key: 'spend' | 'save' | 'borrow' | 'plan'; label: string }[] = [
  { key: 'spend', label: 'Spend' },
  { key: 'save', label: 'Save' },
  { key: 'borrow', label: 'Borrow' },
  { key: 'plan', label: 'Plan' },
]

/**
 * Financial habits (the questionnaire). Shown beside the score, never inside it:
 * saving new answers does not change the score. `action` is the officer's
 * "Record new answers" button (added in Part 3b).
 */
export function HabitsPanel({ profile, action }: { profile: MerchantProfile; action?: ReactNode }) {
  const q = profile.questionnaire
  return (
    <Card className="flex flex-col gap-3.5 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="m-0 text-lg font-semibold">Financial habits</h2>
        <Chip tone="peri" className="px-2.5 py-1">
          Directional · not part of the score
        </Chip>
      </div>
      {q ? (
        <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-x-5 gap-y-3">
          {HABITS.map((h) => (
            <div key={h.key} className="flex flex-col gap-1.5">
              <div className="flex justify-between text-[13px]">
                <span>{h.label}</span>
                <span className="font-mono font-semibold tabular">{q[h.key].toFixed(1)} / 5</span>
              </div>
              <div className="h-2 overflow-hidden rounded bg-line-soft" aria-hidden="true">
                <span className="block h-2 bg-slate" style={{ width: `${(q[h.key] / 5) * 100}%` }} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="m-0 text-sm text-ink-3">No answers recorded yet for this merchant.</p>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2.5 text-[13px] text-muted">
        <span>
          {q
            ? `Stress ${q.stress} / 5 · Confidence ${q.confidence} / 5 · answered ${fmtDate(q.answered_at)}`
            : 'The ten questions are optional and never change the score.'}
        </span>
        {action}
      </div>
    </Card>
  )
}

export function WhyMightThisBeWrong() {
  return (
    <section aria-labelledby="ww" className="flex flex-col gap-2.5 rounded-card bg-peri-panel px-5 py-[18px]">
      <h2 id="ww" className="m-0 text-base font-semibold text-peri-head">
        Why might this be wrong?
      </h2>
      <ul className="m-0 flex flex-col gap-1.5 pl-[18px] text-sm leading-5 text-peri-body">
        <li>Returns can come from riders or addresses, not the shop.</li>
        <li>The model learned from synthetic data. It says nothing yet about real merchants.</li>
        <li>Labels exist only for merchants who got credit before.</li>
        <li>A reason describes the data. It does not prove a cause.</li>
      </ul>
    </section>
  )
}

/** Shown in place of the score card when the API answers consent_required. */
export function NoConsentScore() {
  return (
    <Card className="flex flex-wrap items-center gap-5 p-5">
      <LensDial noConsent />
      <div className="flex flex-[1_1_200px] flex-col gap-3">
        <h2 className="m-0">
          <Eyebrow>Readiness score</Eyebrow>
        </h2>
        <p className="m-0 text-[15px] leading-[22px]">
          Scoring is blocked until the merchant grants consent. There is no score, no decision and no questionnaire.
        </p>
      </div>
    </Card>
  )
}
