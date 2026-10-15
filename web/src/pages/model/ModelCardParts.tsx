/**
 * Blocks of the model card page (ModelCard.dc.html). Each block takes the card and
 * shows only what the card reports.
 */
import type { ReactNode } from 'react'

import type { ModelCard } from '@/api/types'
import { BandChip } from '@/components/BandChip'
import { Card, Eyebrow } from '@/components/Page'
import { count, pct } from '@/lib/format'
import { cn } from '@/lib/utils'
import { auc, num, onScale, range, signed, text, type Metrics } from './metrics'

function Mono({ children, strong }: { children: ReactNode; strong?: boolean }) {
  return <span className={cn('font-mono tabular', strong && 'font-semibold')}>{children}</span>
}

/** The AUC scale in the mockup runs from 0.50 (coin toss) to 0.90. */
const AUC_LO = 0.5
const AUC_HI = 0.9

export function AucCard({ m }: { m: Metrics }) {
  const value = num(m, 'roc_auc')
  if (value === undefined) return null
  const r = range(m, 'roc_auc_range')
  const bar = num(m, 'auc_benchmark')
  const simpler = text(m, 'simpler_model')
  const simplerAuc = num(m, 'simpler_model_roc_auc')
  const gain = num(m, 'auc_gain_over_simpler_model')
  const gainRange = range(m, 'auc_gain_over_simpler_model_range')
  const ticks = [0.5, 0.6, 0.7, 0.8, 0.9]

  return (
    <Card className="col-span-full flex flex-col gap-3 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <Eyebrow>Ranking · ROC-AUC</Eyebrow>
        <span className="text-xs text-muted">
          0.50 is a coin toss{bar !== undefined && ` · ${bar.toFixed(2)} is a useful bar for this kind of lending`}
        </span>
      </div>
      <div className="flex flex-wrap items-baseline gap-3">
        <span className="font-mono text-[40px] leading-[44px] font-semibold tabular">{auc(value)}</span>
        {r && (
          <span className="font-mono text-sm text-ink-3 tabular">
            95% range {auc(r[0])} to {auc(r[1])}
          </span>
        )}
      </div>
      <div className="flex flex-col gap-1.5">
        <div className="relative h-2.5 rounded-[5px] bg-line-soft" aria-hidden="true">
          {r && (
            <span
              className="absolute inset-y-0 rounded-[5px] bg-[#8FB9AB]"
              style={{ left: `${onScale(r[0], AUC_LO, AUC_HI)}%`, width: `${onScale(r[1], AUC_LO, AUC_HI) - onScale(r[0], AUC_LO, AUC_HI)}%` }}
            />
          )}
          <span className="absolute -top-1 h-[18px] w-1 -translate-x-1/2 rounded-sm bg-lens" style={{ left: `${onScale(value, AUC_LO, AUC_HI)}%` }} />
          {bar !== undefined && (
            <span className="absolute -inset-y-1.5 w-0 border-l-2 border-dashed border-rust" style={{ left: `${onScale(bar, AUC_LO, AUC_HI)}%` }} />
          )}
        </div>
        <div className="flex justify-between font-mono text-[11px] text-muted-2">
          {ticks.map((t) => (
            <span key={t}>
              {t.toFixed(2)}
              {bar !== undefined && Math.abs(t - bar) < 1e-9 ? ' bar' : ''}
            </span>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-x-5 gap-y-2 text-[13px] text-ink-2">
        {simpler && simplerAuc !== undefined && (
          <span>
            Simpler model ({simpler}): <Mono strong>{auc(simplerAuc)}</Mono>
          </span>
        )}
        {gain !== undefined && (
          <span>
            Full model adds: <Mono strong>{signed(gain)}</Mono>
            {gainRange && (
              <Mono>
                {' '}
                ({signed(gainRange[0])} to {signed(gainRange[1])})
              </Mono>
            )}
          </span>
        )}
      </div>
      {text(m, 'model_choice') && <p className="m-0 text-[13px] text-muted">{text(m, 'model_choice')}</p>}
    </Card>
  )
}

function SmallMetric({ label, value, children }: { label: string; value: string; children?: ReactNode }) {
  return (
    <Card className="flex flex-col gap-2 p-5">
      <Eyebrow>{label}</Eyebrow>
      <span className="font-mono text-[32px] font-semibold tabular">{value}</span>
      {children && <span className="text-[13px] text-ink-3">{children}</span>}
    </Card>
  )
}

export function SmallMetrics({ m }: { m: Metrics }) {
  const brier = num(m, 'brier')
  const brierBase = num(m, 'brier_always_average_rate')
  const calErr = num(m, 'calibration_error')
  const calRange = range(m, 'calibration_error_range')
  const repaid = num(m, 'share_repaid')
  return (
    <>
      {brier !== undefined && (
        <SmallMetric label="Probability error · Brier" value={brier.toFixed(4)}>
          {brierBase !== undefined && (
            <>
              Always guessing the average: <Mono>{brierBase.toFixed(4)}</Mono>.{' '}
            </>
          )}
          Lower is better.
        </SmallMetric>
      )}
      {calErr !== undefined && (
        <SmallMetric label="Calibration error" value={calErr.toFixed(3)}>
          {calRange && (
            <>
              Range <Mono>{calRange[0].toFixed(3)}</Mono> to <Mono>{calRange[1].toFixed(3)}</Mono>.{' '}
            </>
          )}
          {text(m, 'calibration') && <>Method: {text(m, 'calibration')}. </>}
          Does a 90 mean about 90 in 100 repay?
        </SmallMetric>
      )}
      {repaid !== undefined && (
        <SmallMetric label="Repaid, validation" value={pct(repaid, 1)}>
          {text(m, 'label') ?? 'Share of loans repaid in the validation period.'}
        </SmallMetric>
      )}
    </>
  )
}

const BANDS = [
  { name: 'Strong' as const, key: 'band_strong_share', seg: 'bg-lens' },
  { name: 'Review' as const, key: 'band_review_share', seg: 'bg-marigold' },
  {
    name: 'Needs more info' as const,
    key: 'band_needs_more_info_share',
    seg: 'bg-[repeating-linear-gradient(90deg,#5A6894_0_5px,#C5CCE0_5px_7px)]',
  },
]

export function BandsCard({ m }: { m: Metrics }) {
  const rows = BANDS.map((b) => ({ ...b, share: num(m, b.key), repaid: num(m, `${b.key}_repaid`) }))
  if (rows.every((r) => r.share === undefined)) return null
  return (
    <Card className="flex flex-col gap-3.5 p-5">
      <div className="flex flex-col gap-1">
        <h2 className="m-0 text-lg font-semibold">Bands</h2>
        <span className="text-[13px] text-muted">Share of validation loans in each band, and how many of them repaid.</span>
      </div>
      <div className="flex h-3.5 overflow-hidden rounded-[7px] bg-line-soft" aria-hidden="true">
        {rows.map((r) => (r.share ? <span key={r.name} className={cn('block h-3.5', r.seg)} style={{ width: `${r.share * 100}%` }} /> : null))}
      </div>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="text-left text-xs text-muted">
            <th scope="col" className="py-1.5 font-semibold">Band</th>
            <th scope="col" className="py-1.5 text-right font-semibold">Share of loans</th>
            <th scope="col" className="py-1.5 text-right font-semibold">Repaid</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.name} className="border-t border-line-soft">
              <td className="py-2.5">
                <BandChip band={r.name} />
              </td>
              <td className="py-2.5 text-right font-mono tabular">{pct(r.share)}</td>
              <td className="py-2.5 text-right font-mono tabular">{r.share ? pct(r.repaid, 1) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}

/** The held-back test period: numbers when the card has them, else the card's own sentence. */
export function TestPeriodCard({ m }: { m: Metrics }) {
  const value = num(m, 'test_roc_auc')
  const r = range(m, 'test_roc_auc_range')
  const loans = num(m, 'test_loans')
  const diff = num(m, 'test_minus_validation_auc')
  const reading = text(m, 'test_reading') ?? text(m, 'test_result')
  if (value === undefined && !reading) return null
  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className="flex flex-col gap-1">
        <h2 className="m-0 text-lg font-semibold">Held-back test period</h2>
        <span className="text-[13px] text-muted">Loans kept aside until the end and measured once.</span>
      </div>
      {value !== undefined && (
        <div className="flex flex-wrap items-baseline gap-3">
          <span className="font-mono text-[32px] font-semibold tabular">{auc(value)}</span>
          {r && (
            <span className="font-mono text-sm text-ink-3 tabular">
              range {auc(r[0])} to {auc(r[1])}
            </span>
          )}
        </div>
      )}
      {(loans !== undefined || diff !== undefined) && (
        <span className="text-[13px] text-ink-2">
          {loans !== undefined && (
            <>
              <Mono>{count(loans)}</Mono> loans.{' '}
            </>
          )}
          {diff !== undefined && (
            <>
              Against validation: <Mono strong>{signed(diff)}</Mono>.
            </>
          )}
        </span>
      )}
      {reading && <p className="m-0 text-sm leading-[21px] text-ink-2">{reading}</p>}
    </Card>
  )
}

/** Synthetic only: does delivery data add anything? From the `ablation` rows. */
export function AblationCard({ card }: { card: ModelCard }) {
  const rows = card.ablation.filter((r) => typeof r.delivery_signal_strength === 'number')
  if (rows.length === 0) return null
  const n = (v: unknown) => (typeof v === 'number' ? v : undefined)
  const maxAdd = Math.max(0.0001, ...rows.map((r) => n(r.deliveries_add_highest) ?? n(r.deliveries_add_mean) ?? 0))
  const runs = text(card.metrics, 'ablation_runs')

  return (
    <Card className="flex flex-col gap-5 p-6">
      <div className="flex flex-col gap-1">
        <Eyebrow>Synthetic only · the REDX question</Eyebrow>
        <h2 className="m-0 text-[22px] font-semibold">Does delivery data add anything?</h2>
        <p className="m-0 max-w-[760px] text-sm text-ink-3">
          We wrote the generator, so we can set how strongly delivery behaviour is tied to repayment. At strength 0
          there is no link, and the delivery inputs must add nothing. If they did, the pipeline would be leaking.
        </p>
      </div>
      <div className="flex flex-col gap-3.5">
        <span className="text-[13px] font-semibold">AUC added by delivery inputs, by planted signal strength</span>
        {rows.map((r, i) => {
          const mean = n(r.deliveries_add_mean) ?? 0
          const lo = n(r.deliveries_add_lowest)
          const hi = n(r.deliveries_add_highest)
          return (
            <div key={i} className="grid grid-cols-[110px_minmax(0,1fr)_auto] items-center gap-3">
              <span className="text-[13px]">Strength {n(r.delivery_signal_strength)}</span>
              <div className="relative h-2.5 rounded-[5px] bg-line-soft" aria-hidden="true">
                <span className="absolute inset-y-0 left-0 rounded-[5px] bg-lens" style={{ width: `${Math.max(1.5, (Math.max(0, mean) / maxAdd) * 100)}%` }} />
              </div>
              <span className="text-right font-mono text-[13px] font-semibold tabular">
                {signed(mean)}
                {lo !== undefined && hi !== undefined && (
                  <span className="font-normal text-muted">
                    {' '}
                    ({signed(lo)} to {signed(hi)})
                  </span>
                )}
              </span>
            </div>
          )
        })}
        <span className="text-[13px] text-ink-3">
          {rows[0]?.seeds !== undefined && `Averaged over ${n(rows[0].seeds)} seeds. `}
          At strength 0 the range spans zero: the negative control holds. This shows the method can find a signal. It
          does not show that REDX data predicts repayment.
        </span>
      </div>
      <div className="flex flex-col gap-2">
        <span className="text-[13px] font-semibold">Feature sets, added one at a time (AUC)</span>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[460px] border-collapse text-[13px]">
            <thead>
              <tr className="text-left text-xs text-muted">
                <th scope="col" className="py-1.5 font-semibold">Signal strength</th>
                {['A', 'B', 'C', 'D'].map((k) => (
                  <th key={k} scope="col" className="py-1.5 text-right font-semibold">
                    {k}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-t border-line-soft">
                  <td className="py-2 font-mono">{n(r.delivery_signal_strength)}</td>
                  {(['auc_A', 'auc_B', 'auc_C', 'auc_D'] as const).map((k) => (
                    <td key={k} className="py-2 text-right font-mono tabular">
                      {n(r[k]) !== undefined ? auc(n(r[k])!) : '—'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {runs && <span className="text-[13px] text-ink-3">{runs}.</span>}
        <span className="text-[13px] text-ink-3">The questionnaire (D) is shown beside the score, never inside the headline model.</span>
      </div>
    </Card>
  )
}

function FlagCell({ value }: { value: unknown }) {
  const v = typeof value === 'string' ? value : '—'
  return <span className={cn(v === 'flagged' && 'font-semibold text-amber-text', v !== 'flagged' && 'text-muted')}>{v}</span>
}

/** Results by audit group. Audit only: these columns are never model inputs. */
export function GroupsCard({ card }: { card: ModelCard }) {
  const rows = card.group_results
  const findings = text(card.metrics, 'group_findings')
  if (rows.length === 0 && !findings) return null
  const n = (v: unknown) => (typeof v === 'number' ? v : undefined)
  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className="flex flex-col gap-1">
        <h2 className="m-0 text-lg font-semibold">Results by group</h2>
        <span className="text-[13px] text-muted">
          Audit only, never model inputs. A gap is flagged only when the ranges do not overlap. We report gaps; we do
          not claim fairness.
        </span>
      </div>
      {findings && <p className="m-0 text-sm leading-[21px] text-ink-2">{findings}</p>}
      {rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-[13px]">
            <thead>
              <tr className="text-left text-xs text-muted">
                <th scope="col" className="py-1.5 font-semibold">Column</th>
                <th scope="col" className="py-1.5 font-semibold">Group</th>
                <th scope="col" className="py-1.5 text-right font-semibold">Loans</th>
                <th scope="col" className="py-1.5 text-right font-semibold">Repaid</th>
                <th scope="col" className="py-1.5 text-right font-semibold">AUC</th>
                <th scope="col" className="py-1.5 text-right font-semibold">Avg score</th>
                <th scope="col" className="py-1.5 pl-3 font-semibold">Ranking</th>
                <th scope="col" className="py-1.5 font-semibold">Calibration</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((g, i) => (
                <tr key={i} className="border-t border-line-soft">
                  <td className="py-2 font-mono text-xs text-muted-2">{String(g.column ?? '—')}</td>
                  <td className="py-2">{String(g.group ?? '—')}</td>
                  <td className="py-2 text-right font-mono tabular">{count(n(g.loans))}</td>
                  <td className="py-2 text-right font-mono tabular">{pct(n(g.share_repaid), 1)}</td>
                  <td className="py-2 text-right font-mono tabular">{n(g.roc_auc) !== undefined ? auc(n(g.roc_auc)!) : '—'}</td>
                  <td className="py-2 text-right font-mono tabular">{n(g.mean_score) !== undefined ? n(g.mean_score)!.toFixed(1) : '—'}</td>
                  <td className="py-2 pl-3">
                    <FlagCell value={g.ranking} />
                  </td>
                  <td className="py-2">
                    <FlagCell value={g.calibration} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
