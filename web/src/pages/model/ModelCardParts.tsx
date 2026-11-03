/**
 * Sections of the model card page (approved design: 06-model-card-desktop.png). Each section
 * asks one question, answers it in a sentence, shows a restrained chart, and keeps the
 * technical detail in an accordion that opens. Each block takes the card and shows only
 * what the card reports: no ROC curve or range is drawn that the card does not hold.
 */
import { ChevronRight } from 'lucide-react'
import type { ReactNode } from 'react'

import type { ModelCard } from '@/api/types'
import { BandChip } from '@/components/BandChip'
import { Section } from '@/components/Page'
import { count, pct } from '@/lib/format'
import { useLang, useT, valueText } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { auc, num, numbers, onScale, range, signed, textIn, type Metrics } from './metrics'

/** A disclosure for technical detail: a real <details>, keyboard and screen-reader friendly. */
export function Accordion({ title, aside, children }: { title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <details className="group rounded-[12px] border border-line bg-white">
      <summary className="flex min-h-12 cursor-pointer list-none items-center gap-3 px-4 py-2 [&::-webkit-details-marker]:hidden">
        <ChevronRight size={18} className="shrink-0 text-ink-2 transition-transform group-open:rotate-90" aria-hidden="true" />
        <span className="flex-1 text-[15px] font-semibold text-ink">{title}</span>
        {aside && <span className="text-[13px] text-body">{aside}</span>}
      </summary>
      <div className="border-t border-line px-4 py-4 text-sm text-ink-2">{children}</div>
    </details>
  )
}

/** "Plain meaning" side note. */
export function PlainMeaning({ title, children }: { title: string; children: ReactNode }) {
  return (
    <aside className="flex flex-col gap-1.5 rounded-[12px] border border-[#D5E4F3] bg-info-panel p-4 text-sm leading-[21px] text-ink-2">
      <span className="text-[15px] font-semibold text-ink">{title}</span>
      {children}
    </aside>
  )
}

function Stat({ label, value, help }: { label: string; value: string; help?: string }) {
  return (
    <div className="flex flex-col gap-0.5 px-4 first:pl-0 max-md:px-0">
      <span className="text-[13px] font-medium text-ink-2">{label}</span>
      <span className="font-display text-2xl font-bold text-ink tabular">{value}</span>
      {help && <span className="text-[13px] text-body">{help}</span>}
    </div>
  )
}

/** 1. What is this model for? Source, method, outcome, the time split, inputs in words. */
export function PurposeSection({ card, firstLimitation }: { card: ModelCard; firstLimitation?: string }) {
  const t = useT()
  const lang = useLang()
  const m = card.metrics
  const inputs = textIn(m, 'inputs', lang)?.split(' | ').filter(Boolean) ?? []
  const shows = textIn(m, 'what_this_shows', lang)
  const notShows = textIn(m, 'what_this_does_not_show', lang)
  const split = [
    { name: t('Train', 'প্রশিক্ষণ'), n: num(m, 'train_loans'), help: t('Used to learn', 'শেখার জন্য') },
    { name: t('Validation', 'যাচাই'), n: num(m, 'validation_loans'), help: t('Used to check choices', 'সিদ্ধান্ত যাচাইয়ে') },
    { name: t('Test', 'পরীক্ষা'), n: num(m, 'test_loans'), help: t('Later check results', 'পরের যাচাইয়ের ফল') },
  ].filter((s) => s.n !== undefined)

  return (
    <Section
      id="purpose"
      title={t('What is this model for?', 'এই মডেল কীসের জন্য?')}
      answer={(lang === 'bn' ? textIn(m, 'intended_use', lang) : undefined) ?? card.intended_use}
      aside={
        firstLimitation && (
          <p className="m-0 max-w-[340px] rounded-[12px] border border-amber-chip bg-amber-panel px-4 py-3 text-sm leading-5 text-amber-deep">
            <b className="font-semibold">{t('Read this first: ', 'আগে এটি পড়ুন: ')}</b>
            {firstLimitation}
          </p>
        )
      }
    >
      <dl className="m-0 grid gap-4 md:grid-cols-3 md:divide-x md:divide-line">
        {[
          [t('Source', 'উৎস'), textIn(m, 'data_source', lang)],
          [t('Method', 'পদ্ধতি'), textIn(m, 'model', lang)],
          [t('Outcome', 'ফলাফল'), textIn(m, 'label', lang)],
        ]
          .filter(([, v]) => v)
          .map(([k, v]) => (
            <div key={k} className="flex flex-col gap-1 md:px-4 md:first:pl-0">
              <dt className="text-[15px] font-semibold text-ink">{k}</dt>
              <dd className="m-0 text-sm leading-[21px] text-body">{v}</dd>
            </div>
          ))}
      </dl>
      {split.length > 0 && (
        <div className="flex flex-col gap-2 rounded-[12px] border border-line p-4">
          <div className="flex items-center gap-3 text-[13px] text-body">
            <span>{t('Earlier', 'আগে')}</span>
            <span className="relative h-0.5 flex-1 bg-band-strong" aria-hidden="true">
              <span className="absolute -top-[5px] right-0 border-y-[6px] border-l-[9px] border-y-transparent border-l-band-strong" />
            </span>
            <span>{t('Later', 'পরে')}</span>
          </div>
          <ol className="m-0 grid list-none grid-cols-3 gap-2 p-0 text-center">
            {split.map((s) => (
              <li key={s.name} className="flex flex-col items-center gap-0.5">
                <span className="size-3 rounded-full bg-band-strong" aria-hidden="true" />
                <span className="text-[15px] font-semibold text-ink">{s.name}</span>
                <span className="text-sm text-ink tabular">
                  <b>{count(s.n)}</b> {t('loans', 'ঋণ')}
                </span>
                <span className="text-xs text-body">{s.help}</span>
              </li>
            ))}
          </ol>
          {textIn(m, 'split', lang) && <span className="text-[13px] text-body">{textIn(m, 'split', lang)}.</span>}
        </div>
      )}
      {(shows || notShows) && (
        <div className="grid gap-3 md:grid-cols-2">
          {shows && (
            <p className="m-0 rounded-[12px] bg-mint-2 px-4 py-3 text-sm leading-[21px] text-ink-2">
              <b className="font-semibold text-lens-dark">{t('Shows: ', 'যা দেখায়: ')}</b>
              {shows}
            </p>
          )}
          {notShows && (
            <p className="m-0 rounded-[12px] bg-peri-panel px-4 py-3 text-sm leading-[21px] text-ink-2">
              <b className="font-semibold text-peri-head">{t('Does not show: ', 'যা দেখায় না: ')}</b>
              {notShows}
            </p>
          )}
        </div>
      )}
      {inputs.length > 0 && (
        <Accordion
          title={t(`Inputs in words (${inputs.length})`, `ইনপুটগুলো কথায় (${inputs.length})`)}
          aside={
            <>
              {t('Model version: ', 'মডেল সংস্করণ: ')}
              <span className="font-mono text-xs">{card.model_version}</span>
            </>
          }
        >
          <ul className="m-0 flex flex-col gap-1.5 pl-5">
            {inputs.map((input) => (
              <li key={input}>{input}</li>
            ))}
          </ul>
        </Accordion>
      )}
    </Section>
  )
}

/** The AUC axis runs from 0.50 (a coin toss) to 0.90. */
const AUC_LO = 0.5
const AUC_HI = 0.9

/** 2. How well does it rank repayment risk? A dot plot: purchases only against the full model. */
export function RankingSection({ m }: { m: Metrics }) {
  const t = useT()
  const lang = useLang()
  const value = num(m, 'roc_auc')
  if (value === undefined) return null
  const r = range(m, 'roc_auc_range')
  const simplerAuc = num(m, 'simpler_model_roc_auc')
  const simpler = textIn(m, 'simpler_model', lang)
  const gain = num(m, 'auc_gain_over_simpler_model')
  const gainRange = range(m, 'auc_gain_over_simpler_model_range')
  const bar = num(m, 'auc_benchmark')
  const brier = num(m, 'brier')
  const brierBase = num(m, 'brier_always_average_rate')
  const calErr = num(m, 'calibration_error')
  const repaid = num(m, 'share_repaid')
  const choice = textIn(m, 'model_choice', lang)
  const test = num(m, 'test_roc_auc')
  const testRange = range(m, 'test_roc_auc_range')
  const testLoans = num(m, 'test_loans')
  const diff = num(m, 'test_minus_validation_auc')
  const reading = textIn(m, 'test_reading', lang) ?? textIn(m, 'test_result', lang)
  const ticks = [0.5, 0.6, 0.7, 0.8, 0.9]
  const pos = (v: number) => `${onScale(v, AUC_LO, AUC_HI)}%`

  const rows = [
    ...(simplerAuc !== undefined ? [{ label: t('Purchases only', 'শুধু কেনাকাটা'), v: simplerAuc, r: undefined as [number, number] | undefined, full: false }] : []),
    { label: t('Full model', 'পুরো মডেল'), v: value, r, full: true },
  ]

  return (
    <Section
      id="ranking"
      title={t('How well does it rank repayment risk?', 'পরিশোধের ঝুঁকি কতটা ঠিকভাবে সাজায়?')}
      answer={
        gain !== undefined
          ? t('It ranks outcomes better than purchases alone on these data.', 'এই ডেটায় শুধু কেনাকাটার চেয়ে ভালোভাবে ফলাফল সাজায়।')
          : t('How well the score puts loans that were repaid above loans that were not.', 'পরিশোধ হওয়া ঋণকে না-হওয়া ঋণের ওপরে স্কোর কতটা ঠিকভাবে রাখে।')
      }
    >
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_200px_200px]">
        <div className="flex flex-col gap-2 rounded-[12px] border border-line p-4" role="img" aria-label={rows.map((x) => `${x.label} ${auc(x.v)}`).join(', ')}>
          {rows.map((row) => (
            <div key={row.label} className="grid grid-cols-[110px_minmax(0,1fr)] items-center gap-3">
              <span className="text-sm text-ink-2">{row.label}</span>
              <div className="relative h-10">
                <span className="absolute inset-x-0 top-[65%] h-px bg-line" />
                {row.r && (
                  <span className="absolute top-[65%] h-0.5 -translate-y-1/2 bg-band-strong" style={{ left: pos(row.r[0]), width: `calc(${pos(row.r[1])} - ${pos(row.r[0])})` }} />
                )}
                <span
                  className={cn('absolute top-[65%] size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white', row.full ? 'bg-band-strong' : 'bg-[#6B7890]')}
                  style={{ left: pos(row.v) }}
                />
                <span className="absolute -top-0.5 -translate-x-1/2 text-[13px] font-semibold whitespace-nowrap text-ink tabular" style={{ left: pos(row.v) }}>
                  {auc(row.v)}
                </span>
              </div>
            </div>
          ))}
          <div className="grid grid-cols-[110px_minmax(0,1fr)] gap-3">
            <span />
            <div className="relative h-5 border-t border-control-line text-xs text-body">
              {ticks.map((x) => (
                <span key={x} className="absolute top-1 -translate-x-1/2 tabular" style={{ left: pos(x) }}>
                  {x.toFixed(2)}
                </span>
              ))}
              {bar !== undefined && <span className="absolute -top-[54px] h-[54px] border-l border-dashed border-band-review" style={{ left: pos(bar) }} aria-hidden="true" />}
            </div>
          </div>
          {r && (
            <span className="text-center text-[13px] text-ink-2 tabular">
              {t(`Full model ${auc(value)}, range ${auc(r[0])} to ${auc(r[1])} (the green line).`, `পুরো মডেল ${auc(value)}, সীমা ${auc(r[0])} থেকে ${auc(r[1])} (সবুজ দাগ)।`)}
            </span>
          )}
          <span className="text-center text-[13px] text-body">
            {t('A higher value means better ranking. 0.50 is like a coin toss.', 'বেশি মান মানে ভালো সাজানো। 0.50 মানে টস করার মতো।')}
            {bar !== undefined && t(` The dashed line is ${bar.toFixed(2)}, a useful level for this kind of lending.`, ` ড্যাশ দাগটি ${bar.toFixed(2)}, এ ধরনের ঋণে কাজের মাপকাঠি।`)}
          </span>
        </div>
        {gain !== undefined && (
          <div className="flex flex-col items-center justify-center gap-1 rounded-[12px] border border-mint-line bg-mint-2 p-4 text-center">
            <span className="text-sm font-semibold text-ink">{t('Gain from full model', 'পুরো মডেলের লাভ')}</span>
            <span className="font-display text-[32px] leading-10 font-bold text-ink tabular">{signed(gain)}</span>
            {gainRange && (
              <span className="text-[13px] text-body tabular">
                ({signed(gainRange[0])} {t('to', 'থেকে')} {signed(gainRange[1])})
              </span>
            )}
            {simpler && <span className="text-xs text-body">{t(`over: ${simpler}`, `তুলনা: ${simpler}`)}</span>}
          </div>
        )}
        <PlainMeaning title={t('Plain meaning', 'সহজ মানে')}>
          <span>{t('Higher means better ranking. It says nothing on its own about real merchants.', 'বেশি মানে ভালো সাজানো। আসল মার্চেন্ট সম্পর্কে এটি একা কিছু বলে না।')}</span>
        </PlainMeaning>
      </div>

      <div className="grid gap-4 rounded-[12px] border border-line p-4 sm:grid-cols-2 lg:grid-cols-4 lg:divide-x lg:divide-line">
        {brier !== undefined && <Stat label={t('Brier score', 'ব্রায়ার স্কোর')} value={brier.toFixed(4)} help={t('Lower means smaller probability errors.', 'কম মানে সম্ভাবনার ভুল কম।')} />}
        {brierBase !== undefined && <Stat label={t('Always guessing (average)', 'সবসময় গড় অনুমান')} value={brierBase.toFixed(4)} help={t('The score to beat.', 'যে মান ছাড়াতে হবে।')} />}
        {calErr !== undefined && <Stat label={t('Calibration error', 'ক্যালিব্রেশনের ভুল')} value={calErr.toFixed(3)} help={t('Checks whether chances match outcomes.', 'সম্ভাবনা আর ফলাফল মেলে কিনা।')} />}
        {repaid !== undefined && (
          <Stat
            label={t('Repaid in validation', 'যাচাইয়ে পরিশোধ')}
            value={pct(repaid, 1)}
            help={t(`About ${Math.round(repaid * 100)} of 100 loans repaid.`, `১০০টির মধ্যে প্রায় ${Math.round(repaid * 100)}টি পরিশোধ।`)}
          />
        )}
      </div>

      {(choice || test !== undefined || reading) && (
        <Accordion
          title={t('Model choice and later test results', 'মডেল বাছাই ও পরের পরীক্ষার ফল')}
          aside={test !== undefined && t(`Later-test AUC ${auc(test)}${testLoans !== undefined ? ` · ${count(testLoans)} loans` : ''}`, `পরের পরীক্ষায় AUC ${auc(test)}${testLoans !== undefined ? ` · ${count(testLoans)}টি ঋণ` : ''}`)}
        >
          <div className="flex flex-col gap-3">
            {choice && <p className="m-0 leading-[21px]">{choice}</p>}
            {test !== undefined && (
              <p className="m-0 leading-[21px]">
                {t('Held-back test period: AUC', 'আলাদা রাখা পরীক্ষার সময়: AUC')} <b className="tabular">{auc(test)}</b>
                {testRange && <span className="tabular"> ({auc(testRange[0])}–{auc(testRange[1])})</span>}
                {diff !== undefined && t(`, ${signed(diff)} against validation.`, `, যাচাইয়ের তুলনায় ${signed(diff)}।`)}
              </p>
            )}
            {reading && <p className="m-0 leading-[21px] text-body">{reading}</p>}
          </div>
        </Accordion>
      )}
    </Section>
  )
}

const BANDS = [
  { name: 'Strong' as const, key: 'band_strong_share' },
  { name: 'Review' as const, key: 'band_review_share' },
  { name: 'Needs more info' as const, key: 'band_needs_more_info_share' },
]

/** 3. What happened in each readiness category? */
export function CategoriesSection({ m }: { m: Metrics }) {
  const t = useT()
  const rows = BANDS.map((b) => ({ ...b, share: num(m, b.key), repaid: num(m, `${b.key}_repaid`) }))
  if (rows.every((r) => r.share === undefined)) return null
  return (
    <Section
      id="categories"
      title={t('What happened in each readiness category?', 'প্রতিটি প্রস্তুতি-ধরনে কী ঘটেছে?')}
      answer={t('Strong loans repaid most often. Thin files also often repaid.', 'শক্তিশালী ঋণ সবচেয়ে বেশি পরিশোধ হয়েছে। কম তথ্যের ফাইলও প্রায়ই পরিশোধ হয়েছে।')}
    >
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_260px]">
        <div className="overflow-x-auto rounded-[12px] border border-line">
          <table className="w-full min-w-[420px] border-collapse text-[15px]">
            <thead className="bg-ground">
              <tr className="text-left text-sm text-ink-2">
                <th scope="col" className="px-4 py-2.5 font-semibold">{t('Category', 'ধরন')}</th>
                <th scope="col" className="px-4 py-2.5 text-center font-semibold">{t('Share of validation loans', 'যাচাইয়ের ঋণের ভাগ')}</th>
                <th scope="col" className="px-4 py-2.5 text-center font-semibold">{t('Repaid in time', 'সময়মতো পরিশোধ')}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.name} className="border-t border-line">
                  <td className="px-4 py-2.5">
                    <BandChip band={r.name} />
                  </td>
                  <td className="px-4 py-2.5 text-center tabular">{pct(r.share)}</td>
                  <td className="px-4 py-2.5 text-center tabular">{r.share ? pct(r.repaid, 1) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <PlainMeaning title={t('Plain meaning', 'সহজ মানে')}>
          <span>{t('Thin files need more evidence, not a lower score.', 'কম তথ্যের ফাইলের দরকার আরও প্রমাণ, কম স্কোর নয়।')}</span>
        </PlainMeaning>
      </div>
    </Section>
  )
}

/** 4. Do predicted chances match repayments? The ten calibration groups against the diagonal. */
export function CalibrationSection({ m }: { m: Metrics }) {
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
  const bins = predicted && actual && predicted.length === actual.length ? predicted.map((p, i) => [p, actual[i]] as const) : []
  if (bins.length === 0 && lowest === undefined && below === undefined) return null

  // Axis: from a little under the lowest value to 100%, in steps of 5 points.
  const lo = bins.length ? Math.max(0, Math.floor((Math.min(...bins.flat()) * 100 - 3) / 5) * 5) / 100 : 0.6
  const W = 360
  const H = 240
  const pad = { l: 44, r: 12, t: 12, b: 36 }
  const x = (v: number) => pad.l + ((v - lo) / (1 - lo)) * (W - pad.l - pad.r)
  const y = (v: number) => H - pad.b - ((v - lo) / (1 - lo)) * (H - pad.t - pad.b)
  const ticks: number[] = []
  for (let v = lo; v <= 1.0001; v += 0.1) ticks.push(Math.round(v * 100) / 100)

  return (
    <Section
      id="calibration"
      title={t('Do predicted chances match repayments?', 'অনুমিত সম্ভাবনা কি পরিশোধের সাথে মেলে?')}
      answer={t('Compare expected repayment with what actually happened.', 'প্রত্যাশিত পরিশোধ আর আসলে যা হয়েছে, পাশাপাশি দেখুন।')}
    >
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
        {bins.length > 0 && (
          <figure className="m-0 flex flex-col gap-2 rounded-[12px] border border-line p-4">
            <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-[460px]" role="img" aria-label={t('Ten groups of loans: expected against actual repayment', 'ঋণের দশটি দল: প্রত্যাশিত বনাম আসল পরিশোধ')}>
              {ticks.map((v) => (
                <g key={v}>
                  <line x1={pad.l} x2={W - pad.r} y1={y(v)} y2={y(v)} stroke="#EDF3F5" />
                  <text x={pad.l - 6} y={y(v) + 4} textAnchor="end" fontSize="11" fill="#40516C">
                    {Math.round(v * 100)}
                  </text>
                  <text x={x(v)} y={H - pad.b + 16} textAnchor="middle" fontSize="11" fill="#40516C">
                    {Math.round(v * 100)}
                  </text>
                </g>
              ))}
              <line x1={x(lo)} y1={y(lo)} x2={x(1)} y2={y(1)} stroke="#6B7890" strokeDasharray="5 4" />
              {bins.map(([p, a], i) => (
                <circle key={i} cx={x(p)} cy={y(a)} r="5" fill="#16845B" stroke="#fff" strokeWidth="1.5">
                  <title>{`${pct(p, 1)} → ${pct(a, 1)}`}</title>
                </circle>
              ))}
              <text x={(pad.l + W - pad.r) / 2} y={H - 4} textAnchor="middle" fontSize="12" fill="#111B42">
                {t('Expected to repay (%)', 'পরিশোধের প্রত্যাশা (%)')}
              </text>
              <text x={12} y={(pad.t + H - pad.b) / 2} textAnchor="middle" fontSize="12" fill="#111B42" transform={`rotate(-90 12 ${(pad.t + H - pad.b) / 2})`}>
                {t('Actually repaid (%)', 'আসলে পরিশোধ (%)')}
              </text>
            </svg>
            <figcaption className="flex flex-wrap gap-4 text-[13px] text-body">
              <span className="flex items-center gap-2">
                <span className="size-3 rounded-full bg-band-strong" aria-hidden="true" />
                {t(`Groups of loans (${bins.length} points)`, `ঋণের দল (${bins.length}টি বিন্দু)`)}
              </span>
              <span className="flex items-center gap-2">
                <span className="w-5 border-t border-dashed border-[#6B7890]" aria-hidden="true" />
                {t('Perfect agreement', 'পুরো মিল')}
              </span>
            </figcaption>
          </figure>
        )}
        <PlainMeaning title={t('Key takeaways', 'মূল কথা')}>
          {lowest !== undefined && k !== undefined && (
            <span>
              {t(`${pct(lowest)} of the ${count(k)} lowest-scored loans were not repaid`, `সবচেয়ে কম স্কোরের ${count(k)}টি ঋণের ${pct(lowest)} পরিশোধ হয়নি`)}
              {overall !== undefined && t(`, against ${pct(overall)} overall.`, `, সব মিলিয়ে ${pct(overall)}।`)}
            </span>
          )}
          {below !== undefined && above !== undefined && (
            <span>
              {t(
                `Coverage below the line: ranking AUC ${auc(below)}; at or above it: ${auc(above)}. Thin files rank less reliably, which is why they get "Needs more info".`,
                `কভারেজ সীমার নিচে: AUC ${auc(below)}; সীমায় বা ওপরে: ${auc(above)}। কম তথ্যের ফাইল কম নির্ভরযোগ্যভাবে সাজে, তাই সেগুলো "আরও তথ্য প্রয়োজন" পায়।`,
              )}
            </span>
          )}
        </PlainMeaning>
      </div>
      {bins.length > 0 && (
        <Accordion title={t(`Calibration details · ${bins.length} groups`, `ক্যালিব্রেশনের বিস্তারিত · ${bins.length}টি দল`)}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[420px] border-collapse text-sm">
              <thead>
                <tr className="text-left text-[13px] text-ink-2">
                  <th scope="col" className="py-1.5 font-semibold">{t('Group', 'দল')}</th>
                  <th scope="col" className="py-1.5 text-right font-semibold">{t('Expected to repay', 'পরিশোধের প্রত্যাশা')}</th>
                  <th scope="col" className="py-1.5 text-right font-semibold">{t('Actually repaid', 'আসলে পরিশোধ')}</th>
                  <th scope="col" className="py-1.5 text-right font-semibold">{t('Difference (points)', 'পার্থক্য (পয়েন্ট)')}</th>
                </tr>
              </thead>
              <tbody>
                {bins.map(([p, a], i) => (
                  <tr key={i} className="border-t border-line">
                    <td className="py-1.5">{i + 1}</td>
                    <td className="py-1.5 text-right tabular">{pct(p, 1)}</td>
                    <td className="py-1.5 text-right tabular">{pct(a, 1)}</td>
                    <td className="py-1.5 text-right tabular">{signed((a - p) * 100, 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {belowLoans !== undefined && aboveLoans !== undefined && (
            <p className="mt-3 mb-0 text-body">
              {t(`Loans below the coverage line: ${count(belowLoans)}; at or above: ${count(aboveLoans)}.`, `কভারেজ সীমার নিচে ঋণ: ${count(belowLoans)}; সীমায় বা ওপরে: ${count(aboveLoans)}।`)}
            </p>
          )}
        </Accordion>
      )}
    </Section>
  )
}

/** 5. (Synthetic only) Does delivery data add useful information? The planted-signal test. */
export function DeliverySection({ card }: { card: ModelCard }) {
  const t = useT()
  const lang = useLang()
  const rows = card.ablation.filter((r) => typeof r.delivery_signal_strength === 'number')
  if (rows.length === 0) return null
  const n = (v: unknown) => (typeof v === 'number' ? v : undefined)
  const top = Math.max(0.01, ...rows.map((r) => n(r.deliveries_add_highest) ?? n(r.deliveries_add_mean) ?? 0))
  const runs = textIn(card.metrics, 'ablation_runs', lang)
  const seeds = n(rows[0]?.seeds)

  return (
    <Section
      id="delivery"
      title={t('Does delivery data add useful information?', 'ডেলিভারির ডেটা কি কাজের তথ্য যোগ করে?')}
      answer={t(
        'The method can find a planted signal. This does not show that real delivery data predicts repayment.',
        'পদ্ধতিটি বসানো সংকেত খুঁজে পায়। এতে দেখা যায় না যে আসল ডেলিভারির ডেটা পরিশোধের পূর্বাভাস দেয়।',
      )}
    >
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
        <figure className="m-0 flex flex-col gap-2 rounded-[12px] border border-line p-4">
          <ol className="m-0 flex h-[170px] list-none items-end gap-6 border-b border-control-line px-4 p-0" aria-label={t('AUC gain from delivery inputs, by planted signal strength', 'বসানো সংকেতের শক্তি অনুযায়ী ডেলিভারির ইনপুটের AUC লাভ')}>
            {rows.map((r, i) => {
              const mean = n(r.deliveries_add_mean) ?? 0
              const lo = n(r.deliveries_add_lowest)
              const hi = n(r.deliveries_add_highest)
              return (
                <li key={i} className="flex h-full flex-1 flex-col items-center justify-end gap-1">
                  <span className="text-sm font-semibold text-ink tabular">{signed(mean)}</span>
                  <span className="w-full max-w-[90px] rounded-t-[6px] bg-band-strong/60" style={{ height: `${Math.max(1, (Math.max(0, mean) / top) * 80)}%` }} aria-hidden="true" />
                  <span className="sr-only">
                    {t(`Strength ${n(r.delivery_signal_strength)}: ${signed(mean)}`, `শক্তি ${n(r.delivery_signal_strength)}: ${signed(mean)}`)}
                    {lo !== undefined && hi !== undefined && ` (${signed(lo)} – ${signed(hi)})`}
                  </span>
                </li>
              )
            })}
          </ol>
          <div className="flex gap-6 px-4" aria-hidden="true">
            {rows.map((r, i) => (
              <span key={i} className="flex-1 text-center text-[13px] text-body tabular">
                {n(r.delivery_signal_strength)}
              </span>
            ))}
          </div>
          <figcaption className="text-center text-[13px] text-body">
            {t('Planted signal strength (bars: AUC gain from adding delivery inputs)', 'বসানো সংকেতের শক্তি (দাগ: ডেলিভারির ইনপুট যোগে AUC লাভ)')}
            {seeds !== undefined && t(`; average of ${seeds} seeds.`, `; ${seeds}টি সিডের গড়।`)}
          </figcaption>
        </figure>
        <PlainMeaning title={t('Plain meaning', 'সহজ মানে')}>
          <span>
            {t(
              'We wrote the generator, so we set how strongly deliveries are tied to repayment. At strength 0 there is no link, and the range spans zero: the negative control holds.',
              'জেনারেটর আমাদের লেখা, তাই ডেলিভারি পরিশোধের সাথে কতটা জড়িত তা আমরা ঠিক করি। শক্তি 0-তে কোনো সম্পর্ক নেই, আর সীমা শূন্যকে ধরে: নেতিবাচক নিয়ন্ত্রণ ঠিক আছে।',
            )}
          </span>
        </PlainMeaning>
      </div>
      <Accordion title={t('Compare inputs · A/B/C/D', 'ইনপুটের তুলনা · A/B/C/D')} aside={t('The questionnaire is not in the headline model.', 'প্রশ্নাবলি মূল মডেলে নেই।')}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[460px] border-collapse text-sm">
            <thead>
              <tr className="text-left text-[13px] text-ink-2">
                <th scope="col" className="py-1.5 font-semibold">{t('Signal strength', 'সংকেতের শক্তি')}</th>
                {['A', 'B', 'C', 'D'].map((key) => (
                  <th key={key} scope="col" className="py-1.5 text-right font-semibold">
                    {key}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-t border-line">
                  <td className="py-1.5 tabular">{n(r.delivery_signal_strength)}</td>
                  {(['auc_A', 'auc_B', 'auc_C', 'auc_D'] as const).map((key) => (
                    <td key={key} className="py-1.5 text-right tabular">
                      {n(r[key]) !== undefined ? auc(n(r[key])!) : '—'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {runs && <p className="mt-3 mb-0 text-body">{runs}.</p>}
        <p className="mt-2 mb-0 text-body">
          {t('The questionnaire (D) is shown beside the score, never inside the headline model.', 'প্রশ্নাবলি (D) স্কোরের পাশে দেখানো হয়, মূল মডেলের ভেতরে কখনও নয়।')}
        </p>
      </Accordion>
    </Section>
  )
}

/** The audit's statuses (src/model/fairness.py) in plain words. */
const STATUS: Record<string, { en: string; bn: string }> = {
  flagged: { en: 'Gap flagged', bn: 'ফারাক চিহ্নিত' },
  'no gap': { en: 'No gap', bn: 'ফারাক নেই' },
  'gap, but within the ranges': { en: 'Gap within the ranges', bn: 'সীমার মধ্যে ফারাক' },
  'too few loans to measure': { en: 'Too few loans', bn: 'ঋণ কম' },
}

function status(value: unknown, lang: 'en' | 'bn'): string {
  const v = typeof value === 'string' ? value : '—'
  return STATUS[v] ? STATUS[v][lang] : v
}

const COLUMN: Record<string, { en: string; bn: string }> = {
  town_tier: { en: 'Town tier', bn: 'শহরের ধরন' },
  shop_type: { en: 'Shop type', bn: 'দোকানের ধরন' },
  has_trade_license: { en: 'Trade licence', bn: 'ট্রেড লাইসেন্স' },
}

/** 6. Does performance differ across groups? Audit only: these columns are never model inputs. */
export function GroupsSection({ card }: { card: ModelCard }) {
  const t = useT()
  const lang = useLang()
  const rows = card.group_results
  const findings = textIn(card.metrics, 'group_findings', lang)
  if (rows.length === 0 && !findings) return null
  const n = (v: unknown) => (typeof v === 'number' ? v : undefined)
  const groupName = (g: (typeof rows)[number]) => {
    const column = typeof g.column === 'string' && COLUMN[g.column] ? COLUMN[g.column][lang] : String(g.column ?? '—')
    return `${column} · ${valueText(g.group == null ? null : String(g.group), lang)}`
  }
  const worst = (g: (typeof rows)[number]) =>
    [g.ranking, g.calibration].includes('flagged') ? 'flagged' : [g.ranking, g.calibration].find((v) => v !== 'no gap') ?? 'no gap'

  return (
    <Section id="groups" title={t('Does performance differ across groups?', 'বিভিন্ন দলে কি ফল আলাদা?')} answer={findings}>
      {rows.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
          <div className="overflow-x-auto rounded-[12px] border border-line" role="region" aria-label={t('Groups', 'দল')} tabIndex={0}>
            <table className="w-full min-w-[520px] border-collapse text-[15px]">
              <thead className="bg-ground">
                <tr className="text-left text-sm text-ink-2">
                  <th scope="col" className="px-4 py-2.5 font-semibold">{t('Group', 'দল')}</th>
                  <th scope="col" className="px-4 py-2.5 text-right font-semibold">{t('Loans', 'ঋণ')}</th>
                  <th scope="col" className="px-4 py-2.5 text-right font-semibold">{t('Repaid', 'পরিশোধ')}</th>
                  <th scope="col" className="px-4 py-2.5 text-right font-semibold">{t('Average score', 'গড় স্কোর')}</th>
                  <th scope="col" className="px-4 py-2.5 font-semibold">{t('Result', 'ফলাফল')}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((g, i) => (
                  <tr key={i} className="border-t border-line">
                    <td className="px-4 py-2">{groupName(g)}</td>
                    <td className="px-4 py-2 text-right tabular">{count(n(g.loans))}</td>
                    <td className="px-4 py-2 text-right tabular">{pct(n(g.share_repaid), 1)}</td>
                    <td className="px-4 py-2 text-right tabular">{n(g.mean_score) !== undefined ? n(g.mean_score)!.toFixed(1) : '—'}</td>
                    <td className={cn('px-4 py-2', worst(g) === 'flagged' ? 'font-semibold text-amber-text' : 'text-body')}>{status(worst(g), lang)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <PlainMeaning title={t('Plain meaning', 'সহজ মানে')}>
            <span>
              {t(
                'Loans: number checked. Repaid: share paid in time. Average score: group mean out of 100. Groups overlap; do not add the loans.',
                'ঋণ: কতগুলো যাচাই হয়েছে। পরিশোধ: সময়মতো পরিশোধের ভাগ। গড় স্কোর: দলের গড়, ১০০-এর মধ্যে। দলগুলো একে অপরের সাথে মেশে; ঋণ যোগ করবেন না।',
              )}
            </span>
            <span>
              {t(
                'These columns are audit checks, never model inputs. We report gaps; we do not claim fairness.',
                'এই কলামগুলো শুধু যাচাইয়ের জন্য, কখনও মডেলের ইনপুট নয়। আমরা ফারাক জানাই; ন্যায্যতার দাবি করি না।',
              )}
            </span>
          </PlainMeaning>
        </div>
      )}
      {rows.length > 0 && (
        <Accordion title={t('Detailed group metrics', 'দলভিত্তিক বিস্তারিত')}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] border-collapse text-sm">
              <thead>
                <tr className="text-left text-[13px] text-ink-2">
                  <th scope="col" className="py-1.5 font-semibold">{t('Group', 'দল')}</th>
                  <th scope="col" className="py-1.5 text-right font-semibold">AUC</th>
                  <th scope="col" className="py-1.5 text-right font-semibold">{t('Ranking gap', 'ক্রমের ফারাক')}</th>
                  <th scope="col" className="py-1.5 pl-3 font-semibold">{t('Ranking', 'ক্রম')}</th>
                  <th scope="col" className="py-1.5 text-right font-semibold">{t('Calibration gap', 'ক্যালিব্রেশনের ফারাক')}</th>
                  <th scope="col" className="py-1.5 pl-3 font-semibold">{t('Calibration', 'ক্যালিব্রেশন')}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((g, i) => (
                  <tr key={i} className="border-t border-line">
                    <td className="py-1.5">{groupName(g)}</td>
                    <td className="py-1.5 text-right tabular">{n(g.roc_auc) !== undefined ? auc(n(g.roc_auc)!) : '—'}</td>
                    <td className="py-1.5 text-right tabular">{n(g.ranking_gap) !== undefined ? signed(n(g.ranking_gap)!) : '—'}</td>
                    <td className="py-1.5 pl-3">{status(g.ranking, lang)}</td>
                    <td className="py-1.5 text-right tabular">{n(g.calibration_gap) !== undefined ? signed(n(g.calibration_gap)!) : '—'}</td>
                    <td className="py-1.5 pl-3">{status(g.calibration, lang)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 mb-0 text-body">
            {t('A gap is flagged only when the ranges of the group and the rest do not overlap.', 'দল আর বাকিদের সীমা একে অপরের ওপর না পড়লেই কেবল ফারাক চিহ্নিত হয়।')}
          </p>
        </Accordion>
      )}
    </Section>
  )
}
