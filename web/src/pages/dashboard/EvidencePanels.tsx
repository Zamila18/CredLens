/**
 * The dashboard's evidence panels, all from GET /overview's `evidence` block, which counts
 * the records of the shops added in the app (the generated benchmark merchants are described
 * on the Portfolio page instead):
 * - Evidence coverage: how many shops have each kind of evidence (one-hue meters);
 * - Where the evidence comes from: records per kind, split by source (stacked bars);
 * - Records by business month: the last six months, split by source (stacked columns);
 * - Data quality: issues that need a person, by group.
 * Every chart has its numbers written out next to it; nothing is estimated.
 */
import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router'

import type { EvidenceOverview } from '@/api/types'
import { Meter, SourceBar, SourceLegend } from '@/components/EvidenceViz'
import { Panel } from '@/components/Workspace'
import { count } from '@/lib/format'
import { pick, useLang, useT, type Pair } from '@/lib/i18n'
import { SOURCE_COLOR, SOURCE_ORDER, SOURCE_WORDS } from '@/lib/sources'
import { GROUPS } from '@/pages/quality/words'

const KIND_WORDS: Record<string, Pair> = {
  purchase: { en: 'Purchases', bn: 'কেনাকাটা' },
  delivery: { en: 'Deliveries', bn: 'ডেলিভারি' },
  payment: { en: 'Repayments', bn: 'পরিশোধ' },
  visit: { en: 'Field visits', bn: 'মাঠ পরিদর্শন' },
}

function bySource(rows: { source: string; records: number }[]): Record<string, number> {
  const out: Record<string, number> = {}
  for (const r of rows) out[r.source] = (out[r.source] ?? 0) + r.records
  return out
}

export function CoveragePanel({ e }: { e: EvidenceOverview }) {
  const t = useT()
  const c = e.coverage
  const items: [string, number, string?][] = [
    [t('Valid consent', 'বৈধ অনুমতি'), c.consent ?? 0],
    [t('Purchase records', 'কেনাকাটার রেকর্ড'), c.purchases ?? 0],
    [t('Delivery records', 'ডেলিভারির রেকর্ড'), c.deliveries ?? 0, t('Missing deliveries never lower a score.', 'ডেলিভারি না থাকলে স্কোর কমে না।')],
    [t('Repayments on issued loans', 'দেওয়া ঋণের পরিশোধ'), c.repayments ?? 0],
    [t('A field visit', 'মাঠ পরিদর্শন'), c.visits ?? 0],
    [t('An application', 'আবেদন'), c.application ?? 0],
  ]
  return (
    <Panel title={t('Evidence coverage', 'প্রমাণের বিস্তার')} action={{ to: '/app/merchants', label: t('Merchants', 'মার্চেন্ট') }}>
      <p className="m-0 text-[13.5px] text-body">
        {t(`How many of the ${count(e.app_shops)} shops added in the app have each kind of evidence.`, `অ্যাপে যোগ করা ${count(e.app_shops)}টি দোকানের কতটির কোন প্রমাণ আছে।`)}
      </p>
      {e.app_shops === 0 ? (
        <p className="m-0 text-sm text-body">{t('No shop has been added in the app yet.', 'এখনও অ্যাপে কোনো দোকান যোগ হয়নি।')}</p>
      ) : (
        <div className="flex flex-col gap-3">
          {items.map(([label, value, note]) => <Meter key={label} label={label} value={value} total={e.app_shops} note={note} />)}
        </div>
      )}
    </Panel>
  )
}

export function SourceMixPanel({ e }: { e: EvidenceOverview }) {
  const t = useT()
  const lang = useLang()
  const kinds = ['purchase', 'delivery', 'payment', 'visit'].map((k) => ({ k, counts: bySource(e.by_source.filter((r) => r.record_type === k)) }))
  const all = bySource(e.by_source)
  const total = Object.values(all).reduce((a, b) => a + b, 0)
  return (
    <Panel title={t('Where the evidence comes from', 'প্রমাণ কোথা থেকে আসে')} action={{ to: '/app/sources', label: t('Data sources', 'ডেটার উৎস') }}>
      {total === 0 ? (
        <p className="m-0 text-sm text-body">{t('No records have been entered in the app yet.', 'এখনও অ্যাপে কোনো রেকর্ড রাখা হয়নি।')}</p>
      ) : (
        <>
          <SourceLegend counts={all} />
          <div className="flex flex-col gap-3">
            {kinds.map(({ k, counts }) => {
              const n = Object.values(counts).reduce((a, b) => a + b, 0)
              return (
                <div key={k} className="flex flex-col gap-1">
                  <div className="flex items-baseline justify-between gap-3 text-[14px]">
                    <span className="text-ink">{pick(KIND_WORDS[k], lang)}</span>
                    <span className="font-semibold text-ink tabular">{count(n)}</span>
                  </div>
                  <SourceBar counts={counts} label={pick(KIND_WORDS[k], lang)} />
                </div>
              )
            })}
          </div>
          <details className="text-[13px]">
            <summary className="cursor-pointer font-semibold text-lens-dark">{t('Show as a table', 'টেবিল হিসেবে দেখান')}</summary>
            <table className="mt-2 w-full border-collapse text-left tabular">
              <thead>
                <tr className="text-muted-2">
                  <th className="py-1 font-medium">{t('Kind', 'ধরন')}</th>
                  {SOURCE_ORDER.filter((s) => all[s]).map((s) => <th key={s} className="py-1 text-right font-medium">{pick(SOURCE_WORDS[s], lang)}</th>)}
                </tr>
              </thead>
              <tbody>
                {kinds.map(({ k, counts }) => (
                  <tr key={k} className="border-t border-line">
                    <td className="py-1 text-ink">{pick(KIND_WORDS[k], lang)}</td>
                    {SOURCE_ORDER.filter((s) => all[s]).map((s) => <td key={s} className="py-1 text-right text-body">{count(counts[s] ?? 0)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        </>
      )}
    </Panel>
  )
}

function monthLabel(month: string, lang: string): string {
  const [y, m] = month.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString(lang === 'bn' ? 'bn-BD' : 'en-GB', { month: 'short', timeZone: 'UTC' })
}

/** The six business months ending at the calendar's last day, oldest first. */
function lastMonths(calendarEnd: string): string[] {
  const [y, m] = calendarEnd.split('-').map(Number)
  return Array.from({ length: 6 }, (_, i) => {
    const d = new Date(Date.UTC(y, m - 1 - (5 - i), 1))
    return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`
  })
}

export function MonthlyPanel({ e, calendarEnd }: { e: EvidenceOverview; calendarEnd: string }) {
  const t = useT()
  const lang = useLang()
  const months = lastMonths(calendarEnd).map((m) => ({ m, counts: bySource(e.by_month.filter((r) => r.month === m)) }))
  const totals = months.map(({ counts }) => Object.values(counts).reduce((a, b) => a + b, 0))
  const peak = Math.max(1, ...totals)
  const all = bySource(e.by_month)
  return (
    <Panel title={t('Records by business month', 'ব্যবসার মাস অনুযায়ী রেকর্ড')}>
      <p className="m-0 text-[13.5px] text-body">{t('By the date on the record, not the day it was typed in. Last six months of the business calendar.', 'রেকর্ডের তারিখ অনুযায়ী, লেখার দিন নয়। ব্যবসার ক্যালেন্ডারের শেষ ছয় মাস।')}</p>
      {totals.every((n) => n === 0) ? (
        <p className="m-0 text-sm text-body">{t('No records dated in these months.', 'এই মাসগুলোর তারিখে কোনো রেকর্ড নেই।')}</p>
      ) : (
        <>
          <div className="grid h-40 grid-cols-6 items-end gap-3 border-b border-line px-1" role="img" aria-label={months.map(({ m }, i) => `${monthLabel(m, lang)} ${count(totals[i])}`).join(', ')}>
            {months.map(({ m, counts }, i) => (
              <div key={m} className="flex h-full flex-col justify-end gap-1" title={`${monthLabel(m, lang)}: ${count(totals[i])}`}>
                <span className="text-center text-[12px] font-semibold text-ink tabular">{totals[i] ? count(totals[i]) : ''}</span>
                <div className="mx-auto flex w-full max-w-14 flex-col-reverse gap-[2px] overflow-hidden rounded-t-[4px]" style={{ height: `${(totals[i] / peak) * 100}%` }}>
                  {SOURCE_ORDER.filter((s) => counts[s]).map((s) => (
                    <span key={s} title={`${pick(SOURCE_WORDS[s], lang)}: ${count(counts[s])}`} style={{ flexGrow: counts[s], background: SOURCE_COLOR[s], minHeight: 3 }} />
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-6 gap-3 px-1 text-center text-[12px] text-muted-2">
            {months.map(({ m }) => <span key={m}>{monthLabel(m, lang)}</span>)}
          </div>
          <SourceLegend counts={all} />
        </>
      )}
    </Panel>
  )
}

export function QualityPanel({ e }: { e: EvidenceOverview }) {
  const t = useT()
  const lang = useLang()
  const groups = Object.entries(e.quality_by_group).sort((a, b) => b[1] - a[1])
  return (
    <Panel title={t('Data quality', 'ডেটার মান')} action={{ to: '/app/quality', label: t('Open', 'খুলুন') }}>
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
        <span className="flex items-baseline gap-2">
          <span className={`font-display text-[28px] leading-8 font-bold tabular ${e.quality_open ? 'text-amber-text' : 'text-ink'}`}>{count(e.quality_open)}</span>
          <span className="text-[14px] text-body">{t('need attention', 'মনোযোগ দরকার')}</span>
        </span>
        <span className="text-[13.5px] text-body">{t(`${count(e.quality_concerns)} ${e.quality_concerns === 1 ? 'problem' : 'problems'} confirmed by a reviewer`, `${count(e.quality_concerns)}টি সমস্যা পর্যালোচক নিশ্চিত করেছেন`)}</span>
      </div>
      {groups.length === 0 ? (
        <p className="m-0 text-sm text-body">{t('Nothing needs a person’s attention in the records right now.', 'এখন রেকর্ডে কিছুই মানুষের মনোযোগ চায় না।')}</p>
      ) : (
        <ul className="m-0 flex list-none flex-col p-0">
          {groups.map(([g, n]) => (
            <li key={g} className="border-t border-line first:border-t-0">
              <Link to="/app/quality" className="flex items-center justify-between gap-3 py-2.5 text-[14px] no-underline hover:bg-row-hover sm:px-1">
                <span className="text-ink">{pick(GROUPS[g] ?? { en: g, bn: g }, lang)}</span>
                <span className="flex items-center gap-2 font-semibold text-amber-text tabular">
                  {count(n)}
                  <ArrowRight size={14} aria-hidden="true" className="text-muted-2" />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      <p className="m-0 text-[12.5px] text-muted-2">{t('Reviews never change a record or a score.', 'পর্যালোচনা কোনো রেকর্ড বা স্কোর বদলায় না।')}</p>
    </Panel>
  )
}
