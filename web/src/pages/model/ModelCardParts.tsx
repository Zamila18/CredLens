/**
 * Blocks of the model card page (ModelCard.dc.html). Each block takes the card and
 * shows only what the card reports.
 */
import type { ReactNode } from 'react'

import type { ModelCard } from '@/api/types'
import { BandChip } from '@/components/BandChip'
import { Card, Eyebrow } from '@/components/Page'
import { count, pct } from '@/lib/format'
import { useLang, useT, valueText } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { auc, num, numbers, onScale, range, signed, textIn, type Metrics } from './metrics'

function Mono({ children, strong }: { children: ReactNode; strong?: boolean }) {
  return <span className={cn('font-mono tabular', strong && 'font-semibold')}>{children}</span>
}

/** The AUC scale in the mockup runs from 0.50 (coin toss) to 0.90. */
const AUC_LO = 0.5
const AUC_HI = 0.9

export function AucCard({ m }: { m: Metrics }) {
  const t = useT()
  const lang = useLang()
  const value = num(m, 'roc_auc')
  if (value === undefined) return null
  const r = range(m, 'roc_auc_range')
  const bar = num(m, 'auc_benchmark')
  const simpler = textIn(m, 'simpler_model', lang)
  const choice = textIn(m, 'model_choice', lang)
  const simplerAuc = num(m, 'simpler_model_roc_auc')
  const gain = num(m, 'auc_gain_over_simpler_model')
  const gainRange = range(m, 'auc_gain_over_simpler_model_range')
  const ticks = [0.5, 0.6, 0.7, 0.8, 0.9]

  return (
    <Card className="col-span-full flex flex-col gap-3 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <Eyebrow>{t('Ranking · ROC-AUC', 'ক্রম · ROC-AUC')}</Eyebrow>
        <span className="text-xs text-muted">
          {t('0.50 is a coin toss', '0.50 মানে টস করার মতো')}
          {bar !== undefined &&
            t(` · ${bar.toFixed(2)} is a useful bar for this kind of lending`, ` · এ ধরনের ঋণে ${bar.toFixed(2)} একটি কাজের মাপকাঠি`)}
        </span>
      </div>
      <div className="flex flex-wrap items-baseline gap-3">
        <span className="font-mono text-[40px] leading-[44px] font-semibold tabular">{auc(value)}</span>
        {r && (
          <span className="font-mono text-sm text-ink-3 tabular">
            {t('95% range', '95% সীমা')} {auc(r[0])} {t('to', 'থেকে')} {auc(r[1])}
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
            {t('Simpler model', 'সহজ মডেল')} ({simpler}): <Mono strong>{auc(simplerAuc)}</Mono>
          </span>
        )}
        {gain !== undefined && (
          <span>
            {t('Full model adds:', 'পুরো মডেল যোগ করে:')} <Mono strong>{signed(gain)}</Mono>
            {gainRange && (
              <Mono>
                {' '}
                ({signed(gainRange[0])} {t('to', 'থেকে')} {signed(gainRange[1])})
              </Mono>
            )}
          </span>
        )}
      </div>
      {choice && <p className="m-0 text-[13px] text-muted">{choice}</p>}
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
  const t = useT()
  const lang = useLang()
  const brier = num(m, 'brier')
  const brierBase = num(m, 'brier_always_average_rate')
  const calErr = num(m, 'calibration_error')
  const calRange = range(m, 'calibration_error_range')
  const repaid = num(m, 'share_repaid')
  return (
    <>
      {brier !== undefined && (
        <SmallMetric label={t('Probability error · Brier', 'সম্ভাবনার ভুল · Brier')} value={brier.toFixed(4)}>
          {brierBase !== undefined && (
            <>
              {t('Always guessing the average:', 'সবসময় গড় অনুমান করলে:')} <Mono>{brierBase.toFixed(4)}</Mono>.{' '}
            </>
          )}
          {t('Lower is better.', 'যত কম, তত ভালো।')}
        </SmallMetric>
      )}
      {calErr !== undefined && (
        <SmallMetric label={t('Calibration error', 'ক্যালিব্রেশনের ভুল')} value={calErr.toFixed(3)}>
          {calRange && (
            <>
              {t('Range', 'সীমা')} <Mono>{calRange[0].toFixed(3)}</Mono> {t('to', 'থেকে')} <Mono>{calRange[1].toFixed(3)}</Mono>.{' '}
            </>
          )}
          {textIn(m, 'calibration', lang) && (
            <>
              {t('Method:', 'পদ্ধতি:')} {textIn(m, 'calibration', lang)}.{' '}
            </>
          )}
          {t('Does a 90 mean about 90 in 100 repay?', '90 মানে কি ১০০-এর মধ্যে প্রায় ৯০ জন পরিশোধ করেন?')}
        </SmallMetric>
      )}
      {repaid !== undefined && (
        <SmallMetric label={t('Repaid, validation', 'পরিশোধ, যাচাই')} value={pct(repaid, 1)}>
          {textIn(m, 'label', lang) ?? t('Share of loans repaid in the validation period.', 'যাচাইয়ের সময়ের যত ঋণ পরিশোধ হয়েছে।')}
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
  const t = useT()
  const rows = BANDS.map((b) => ({ ...b, share: num(m, b.key), repaid: num(m, `${b.key}_repaid`) }))
  if (rows.every((r) => r.share === undefined)) return null
  return (
    <Card className="flex flex-col gap-3.5 p-5">
      <div className="flex flex-col gap-1">
        <h2 className="m-0 text-lg font-semibold">{t('Bands', 'ব্যান্ড')}</h2>
        <span className="text-[13px] text-muted">
          {t('Share of validation loans in each band, and how many of them repaid.', 'প্রতিটি ব্যান্ডে যাচাইয়ের ঋণের ভাগ, আর তার কতগুলো পরিশোধ হয়েছে।')}
        </span>
      </div>
      <div className="flex h-3.5 overflow-hidden rounded-[7px] bg-line-soft" aria-hidden="true">
        {rows.map((r) => (r.share ? <span key={r.name} className={cn('block h-3.5', r.seg)} style={{ width: `${r.share * 100}%` }} /> : null))}
      </div>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="text-left text-xs text-muted">
            <th scope="col" className="py-1.5 font-semibold">{t('Band', 'ব্যান্ড')}</th>
            <th scope="col" className="py-1.5 text-right font-semibold">{t('Share of loans', 'ঋণের ভাগ')}</th>
            <th scope="col" className="py-1.5 text-right font-semibold">{t('Repaid', 'পরিশোধ')}</th>
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
  const t = useT()
  const lang = useLang()
  const value = num(m, 'test_roc_auc')
  const r = range(m, 'test_roc_auc_range')
  const loans = num(m, 'test_loans')
  const diff = num(m, 'test_minus_validation_auc')
  const reading = textIn(m, 'test_reading', lang) ?? textIn(m, 'test_result', lang)
  if (value === undefined && !reading) return null
  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className="flex flex-col gap-1">
        <h2 className="m-0 text-lg font-semibold">{t('Held-back test period', 'আলাদা রাখা পরীক্ষার সময়')}</h2>
        <span className="text-[13px] text-muted">
          {t('Loans kept aside until the end and measured once.', 'যে ঋণ শেষ পর্যন্ত আলাদা রাখা হয়েছিল, আর একবারই মাপা হয়েছে।')}
        </span>
      </div>
      {value !== undefined && (
        <div className="flex flex-wrap items-baseline gap-3">
          <span className="font-mono text-[32px] font-semibold tabular">{auc(value)}</span>
          {r && (
            <span className="font-mono text-sm text-ink-3 tabular">
              {t('range', 'সীমা')} {auc(r[0])} {t('to', 'থেকে')} {auc(r[1])}
            </span>
          )}
        </div>
      )}
      {(loans !== undefined || diff !== undefined) && (
        <span className="text-[13px] text-ink-2">
          {loans !== undefined && (
            <>
              <Mono>{count(loans)}</Mono> {t('loans.', 'টি ঋণ।')}{' '}
            </>
          )}
          {diff !== undefined && (
            <>
              {t('Against validation:', 'যাচাইয়ের তুলনায়:')} <Mono strong>{signed(diff)}</Mono>.
            </>
          )}
        </span>
      )}
      {reading && <p className="m-0 text-sm leading-[21px] text-ink-2">{reading}</p>}
    </Card>
  )
}

/**
 * How well the probabilities match what happened (calibration bins), how many of the
 * lowest-scored loans were not repaid, and the ranking under and above the coverage line.
 * All on the validation period, from the card.
 */
export function CalibrationCard({ m }: { m: Metrics }) {
  const t = useT()
  const predicted = numbers(m, 'calibration_mean_predicted')
  const actual = numbers(m, 'calibration_share_repaid')
  const k = num(m, 'lowest_k')
  const lowest = num(m, 'not_repaid_rate_in_lowest_k')
  const overall = num(m, 'not_repaid_rate_overall')
  const below = num(m, 'auc_coverage_below_the_line')
  const above = num(m, 'auc_coverage_at_or_above_the_line')
  const belowLoans = num(m, 'loans_coverage_below_the_line')
  const aboveLoans = num(m, 'loans_coverage_at_or_above_the_line')
  const bins = predicted && actual && predicted.length === actual.length ? predicted.map((p, i) => [p, actual[i]]) : []
  if (bins.length === 0 && lowest === undefined && below === undefined) return null

  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex flex-col gap-1">
        <h2 className="m-0 text-lg font-semibold">{t('Calibration and the lowest scores', 'ক্যালিব্রেশন ও সবচেয়ে কম স্কোর')}</h2>
        <span className="text-[13px] text-muted">
          {t(
            'Validation loans in ten groups by predicted probability: what the model expected, and what happened.',
            'অনুমিত সম্ভাবনা অনুযায়ী যাচাইয়ের ঋণ দশ ভাগে: মডেল কী আশা করেছিল, আর আসলে কী হয়েছে।',
          )}
        </span>
      </div>
      {bins.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[420px] border-collapse text-[13px]">
            <thead>
              <tr className="text-left text-xs text-muted">
                <th scope="col" className="py-1.5 font-semibold">{t('Group', 'ভাগ')}</th>
                <th scope="col" className="py-1.5 text-right font-semibold">{t('Expected to repay', 'পরিশোধের প্রত্যাশা')}</th>
                <th scope="col" className="py-1.5 text-right font-semibold">{t('Actually repaid', 'আসলে পরিশোধ')}</th>
                <th scope="col" className="py-1.5 text-right font-semibold">{t('Difference', 'পার্থক্য')}</th>
              </tr>
            </thead>
            <tbody>
              {bins.map(([p, a], i) => (
                <tr key={i} className="border-t border-line-soft">
                  <td className="py-1.5 font-mono">{i + 1}</td>
                  <td className="py-1.5 text-right font-mono tabular">{pct(p, 1)}</td>
                  <td className="py-1.5 text-right font-mono tabular">{pct(a, 1)}</td>
                  <td className="py-1.5 text-right font-mono tabular">{signed((a - p) * 100, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(240px,100%),1fr))] gap-4 text-sm text-ink-2">
        {lowest !== undefined && k !== undefined && (
          <div className="flex flex-col gap-1 rounded-panel bg-ground p-4">
            <span className="font-mono text-[26px] font-semibold tabular">{pct(lowest)}</span>
            <span>
              {t(
                `not repaid among the ${count(k)} lowest-scored loans`,
                `সবচেয়ে কম স্কোরের ${count(k)}টি ঋণের মধ্যে পরিশোধ হয়নি`,
              )}
              {overall !== undefined && t(` (overall ${pct(overall)})`, ` (সব মিলিয়ে ${pct(overall)})`)}
            </span>
          </div>
        )}
        {below !== undefined && above !== undefined && (
          <div className="flex flex-col gap-1 rounded-panel bg-ground p-4">
            <span className="font-mono text-[26px] font-semibold tabular">
              {auc(below)} · {auc(above)}
            </span>
            <span>
              {t('AUC under the coverage line', 'কভারেজ সীমার নিচে AUC')}
              {belowLoans !== undefined && ` (${count(belowLoans)})`} · {t('at or above it', 'সীমায় বা ওপরে')}
              {aboveLoans !== undefined && ` (${count(aboveLoans)})`}.{' '}
              {t(
                'Thin files rank worse, which is why they get "Needs more info".',
                'কম তথ্যের ফাইলে ক্রম দুর্বল, তাই সেগুলো "আরও তথ্য প্রয়োজন" পায়।',
              )}
            </span>
          </div>
        )}
      </div>
    </Card>
  )
}

/** Synthetic only: does delivery data add anything? From the `ablation` rows. */
export function AblationCard({ card }: { card: ModelCard }) {
  const t = useT()
  const lang = useLang()
  const rows = card.ablation.filter((r) => typeof r.delivery_signal_strength === 'number')
  if (rows.length === 0) return null
  const n = (v: unknown) => (typeof v === 'number' ? v : undefined)
  const maxAdd = Math.max(0.0001, ...rows.map((r) => n(r.deliveries_add_highest) ?? n(r.deliveries_add_mean) ?? 0))
  const runs = textIn(card.metrics, 'ablation_runs', lang)

  return (
    <Card className="flex flex-col gap-5 p-6">
      <div className="flex flex-col gap-1">
        <Eyebrow>{t('Synthetic only · the REDX question', 'শুধু সিনথেটিক · REDX-এর প্রশ্ন')}</Eyebrow>
        <h2 className="m-0 text-[22px] font-semibold">{t('Does delivery data add anything?', 'ডেলিভারির ডেটা কি কিছু যোগ করে?')}</h2>
        <p className="m-0 max-w-[760px] text-sm text-ink-3">
          {t(
            'We wrote the generator, so we can set how strongly delivery behaviour is tied to repayment. At strength 0 there is no link, and the delivery inputs must add nothing. If they did, the pipeline would be leaking.',
            'জেনারেটর আমাদের লেখা, তাই ডেলিভারির আচরণ পরিশোধের সাথে কতটা জড়িত তা আমরা ঠিক করতে পারি। শক্তি 0 হলে কোনো সম্পর্ক নেই, আর ডেলিভারির ইনপুট কিছুই যোগ করবে না। করলে বুঝতে হতো পাইপলাইনে তথ্য ফাঁস হচ্ছে।',
          )}
        </p>
      </div>
      <div className="flex flex-col gap-3.5">
        <span className="text-[13px] font-semibold">
          {t('AUC added by delivery inputs, by planted signal strength', 'ডেলিভারির ইনপুট কতটা AUC যোগ করে, বসানো সংকেতের শক্তি অনুযায়ী')}
        </span>
        {rows.map((r, i) => {
          const mean = n(r.deliveries_add_mean) ?? 0
          const lo = n(r.deliveries_add_lowest)
          const hi = n(r.deliveries_add_highest)
          return (
            <div key={i} className="grid grid-cols-[110px_minmax(0,1fr)_auto] items-center gap-3">
              <span className="text-[13px]">
                {t('Strength', 'শক্তি')} {n(r.delivery_signal_strength)}
              </span>
              <div className="relative h-2.5 rounded-[5px] bg-line-soft" aria-hidden="true">
                <span className="absolute inset-y-0 left-0 rounded-[5px] bg-lens" style={{ width: `${Math.max(1.5, (Math.max(0, mean) / maxAdd) * 100)}%` }} />
              </div>
              <span className="text-right font-mono text-[13px] font-semibold tabular">
                {signed(mean)}
                {lo !== undefined && hi !== undefined && (
                  <span className="font-normal text-muted">
                    {' '}
                    ({signed(lo)} {t('to', 'থেকে')} {signed(hi)})
                  </span>
                )}
              </span>
            </div>
          )
        })}
        <span className="text-[13px] text-ink-3">
          {rows[0]?.seeds !== undefined && t(`Averaged over ${n(rows[0].seeds)} seeds. `, `${n(rows[0].seeds)}টি সিডের গড়। `)}
          {t(
            'At strength 0 the range spans zero: the negative control holds. This shows the method can find a signal. It does not show that REDX data predicts repayment.',
            'শক্তি 0-তে সীমা শূন্যকে ধরে: নেতিবাচক নিয়ন্ত্রণ ঠিক আছে। এটি দেখায় পদ্ধতিটি সংকেত খুঁজে পেতে পারে। এটি দেখায় না যে REDX-এর ডেটা পরিশোধের পূর্বাভাস দেয়।',
          )}
        </span>
      </div>
      <div className="flex flex-col gap-2">
        <span className="text-[13px] font-semibold">{t('Feature sets, added one at a time (AUC)', 'ইনপুটের দল, একটি একটি করে যোগ (AUC)')}</span>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[460px] border-collapse text-[13px]">
            <thead>
              <tr className="text-left text-xs text-muted">
                <th scope="col" className="py-1.5 font-semibold">{t('Signal strength', 'সংকেতের শক্তি')}</th>
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
        <span className="text-[13px] text-ink-3">
          {t(
            'The questionnaire (D) is shown beside the score, never inside the headline model.',
            'প্রশ্নাবলি (D) স্কোরের পাশে দেখানো হয়, মূল মডেলের ভেতরে কখনও নয়।',
          )}
        </span>
      </div>
    </Card>
  )
}

/** The audit's statuses (src/model/fairness.py) in Bangla. */
const STATUS_BN: Record<string, string> = {
  flagged: 'চিহ্নিত',
  'no gap': 'ফারাক নেই',
  'gap, but within the ranges': 'ফারাক আছে, তবে সীমার মধ্যে',
  'too few loans to measure': 'মাপার মতো যথেষ্ট ঋণ নেই',
}

function FlagCell({ value }: { value: unknown }) {
  const lang = useLang()
  const v = typeof value === 'string' ? value : '—'
  const shown = lang === 'bn' ? (STATUS_BN[v] ?? v) : v
  return <span className={cn(v === 'flagged' && 'font-semibold text-amber-text', v !== 'flagged' && 'text-muted')}>{shown}</span>
}

/** Results by audit group. Audit only: these columns are never model inputs. */
export function GroupsCard({ card }: { card: ModelCard }) {
  const t = useT()
  const lang = useLang()
  const rows = card.group_results
  const findings = textIn(card.metrics, 'group_findings', lang)
  if (rows.length === 0 && !findings) return null
  const n = (v: unknown) => (typeof v === 'number' ? v : undefined)
  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className="flex flex-col gap-1">
        <h2 className="m-0 text-lg font-semibold">{t('Results by group', 'দল অনুযায়ী ফলাফল')}</h2>
        <span className="text-[13px] text-muted">
          {t(
            'Audit only, never model inputs. A gap is flagged only when the ranges do not overlap. We report gaps; we do not claim fairness.',
            'শুধু অডিটের জন্য, কখনও মডেলের ইনপুট নয়। সীমা একে অপরের ওপর না পড়লেই কেবল ফারাক চিহ্নিত হয়। আমরা ফারাক জানাই; ন্যায্যতার দাবি করি না।',
          )}
        </span>
      </div>
      {findings && <p className="m-0 text-sm leading-[21px] text-ink-2">{findings}</p>}
      {rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-[13px]">
            <thead>
              <tr className="text-left text-xs text-muted">
                <th scope="col" className="py-1.5 font-semibold">{t('Column', 'কলাম')}</th>
                <th scope="col" className="py-1.5 font-semibold">{t('Group', 'দল')}</th>
                <th scope="col" className="py-1.5 text-right font-semibold">{t('Loans', 'ঋণ')}</th>
                <th scope="col" className="py-1.5 text-right font-semibold">{t('Repaid', 'পরিশোধ')}</th>
                <th scope="col" className="py-1.5 text-right font-semibold">AUC</th>
                <th scope="col" className="py-1.5 text-right font-semibold">{t('Avg score', 'গড় স্কোর')}</th>
                <th scope="col" className="py-1.5 pl-3 font-semibold">{t('Ranking', 'ক্রম')}</th>
                <th scope="col" className="py-1.5 font-semibold">{t('Calibration', 'ক্যালিব্রেশন')}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((g, i) => (
                <tr key={i} className="border-t border-line-soft">
                  <td className="py-2 font-mono text-xs text-muted-2">{String(g.column ?? '—')}</td>
                  <td className="py-2">{valueText(g.group == null ? null : String(g.group), lang)}</td>
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
