/**
 * Left column of the merchant page (Merchant.dc.html): "Evidence, last 90 days" and the
 * unified timeline. The 90-day numbers are the ones the score was computed from.
 * A stream that is null has no records in that source: it says so instead of zeros.
 */
import { useState, type ReactNode } from 'react'

import type { MerchantProfile, TimelineEvent } from '@/api/types'
import { FilterChip } from '@/components/Filters'
import { Card } from '@/components/Page'
import { count, fmtDate, pct, taka } from '@/lib/format'
import { useLang, useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'

function plural(n: number, one: string, many: string) {
  return `${count(n)} ${n === 1 ? one : many}`
}

function StreamCard({ color, name, source, children }: { color: string; name: string; source: string; children: ReactNode }) {
  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex items-center gap-2">
        <span className="size-2.5 rounded-[3px]" style={{ background: color }} aria-hidden="true" />
        <span className="text-sm font-semibold">{name}</span>
        <span className="text-xs text-muted-2">{source}</span>
      </div>
      {children}
    </Card>
  )
}

function Headline({ value, caption }: { value: string; caption: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-mono text-2xl font-semibold tabular">{value}</span>
      <span className="text-[13px] text-muted">{caption}</span>
    </div>
  )
}

function Facts({ rows }: { rows: [string, string][] }) {
  return (
    <dl className="m-0 grid grid-cols-[1fr_auto] gap-x-3 gap-y-1.5 text-[13px]">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-muted">{k}</dt>
          <dd className="m-0 font-mono tabular">{v}</dd>
        </div>
      ))}
    </dl>
  )
}

function NoRecords() {
  const t = useT()
  return <span className="text-[13px] text-muted">{t('No records in this source', 'এই উৎসে কোনো রেকর্ড নেই')}</span>
}

export function EvidenceCards({ profile }: { profile: MerchantProfile }) {
  const t = useT()
  const { purchases, deliveries, payments } = profile
  return (
    <section aria-labelledby="ev" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="ev" className="m-0 text-lg font-semibold">
          {t('Evidence, last 90 days', 'প্রমাণ, গত ৯০ দিন')}
        </h2>
        <span className="text-[13px] text-muted-2">
          {t('The same numbers the score was computed from', 'যে সংখ্যা থেকে স্কোর হিসাব হয়েছে, সেগুলোই')}
        </span>
      </div>
      {!profile.consent_valid ? (
        <Card className="p-4 text-sm text-ink-3">
          {t(
            'Without a valid consent no purchase, delivery or payment records are shown.',
            'বৈধ অনুমতি ছাড়া কেনাকাটা, ডেলিভারি বা পেমেন্টের কোনো রেকর্ড দেখানো হয় না।',
          )}
        </Card>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fit,minmax(190px,1fr))] gap-3">
          <StreamCard color="#0E5A4A" name={t('Purchases', 'কেনাকাটা')} source="Mokam">
            {purchases ? (
              <>
                <Headline
                  value={taka(purchases.value_bdt_90d)}
                  caption={t(
                    `stock bought in ${plural(purchases.n_purchases_90d, 'purchase', 'purchases')}`,
                    `${count(purchases.n_purchases_90d)} বার মাল কেনা হয়েছে`,
                  )}
                />
                <Facts
                  rows={[
                    [t('Categories', 'পণ্যের ধরন'), count(purchases.n_categories)],
                    [t('Weeks active', 'সক্রিয় সপ্তাহ'), count(purchases.weeks_active)],
                  ]}
                />
              </>
            ) : (
              <NoRecords />
            )}
          </StreamCard>
          <StreamCard color="#4A5A8C" name={t('Deliveries', 'ডেলিভারি')} source="REDX">
            {deliveries ? (
              <>
                <Headline
                  value={t(plural(deliveries.n_parcels_90d, 'parcel', 'parcels'), `${count(deliveries.n_parcels_90d)} পার্সেল`)}
                  caption={t(`${pct(deliveries.delivered_rate)} delivered`, `${pct(deliveries.delivered_rate)} পৌঁছেছে`)}
                />
                <Facts
                  rows={[
                    [t('Returned', 'ফেরত'), pct(deliveries.return_rate)],
                    [t('Failed', 'পৌঁছানো যায়নি'), pct(deliveries.failed_rate)],
                    [t('COD passed back on time', 'ক্যাশ অন ডেলিভারির টাকা সময়মতো ফেরত'), pct(deliveries.cod_remit_ontime_rate)],
                  ]}
                />
              </>
            ) : (
              <NoRecords />
            )}
          </StreamCard>
          <StreamCard color="#B5650D" name={t('Payments', 'পেমেন্ট')} source="Baki">
            {payments ? (
              <>
                <Headline
                  value={t(`${pct(payments.ontime_rate)} on time`, `${pct(payments.ontime_rate)} সময়মতো`)}
                  caption={t(
                    `across ${plural(payments.n_payments, 'repayment', 'repayments')}`,
                    `${count(payments.n_payments)}টি পরিশোধের মধ্যে`,
                  )}
                />
                <Facts
                  rows={[
                    [
                      t('Average days late', 'গড়ে কত দিন দেরি'),
                      payments.avg_days_late == null ? '—' : payments.avg_days_late.toFixed(1),
                    ],
                  ]}
                />
              </>
            ) : (
              <NoRecords />
            )}
          </StreamCard>
        </div>
      )}
    </section>
  )
}

type Stream = TimelineEvent['stream']

const STREAM_META: Record<Stream, { color: string; source: string; sourceBn: string }> = {
  purchase: { color: '#0E5A4A', source: 'Mokam · stock purchase', sourceBn: 'Mokam · মাল কেনা' },
  delivery: { color: '#4A5A8C', source: 'REDX · delivery', sourceBn: 'REDX · ডেলিভারি' },
  payment: { color: '#B5650D', source: 'Baki · repayment', sourceBn: 'Baki · পরিশোধ' },
  loan: { color: '#13201C', source: 'Loan', sourceBn: 'ঋণ' },
}

const STREAM_FILTERS: { value: Stream | 'all'; label: string; labelBn: string }[] = [
  { value: 'all', label: 'All', labelBn: 'সব' },
  { value: 'purchase', label: 'Purchases', labelBn: 'কেনাকাটা' },
  { value: 'delivery', label: 'Deliveries', labelBn: 'ডেলিভারি' },
  { value: 'payment', label: 'Payments', labelBn: 'পেমেন্ট' },
  { value: 'loan', label: 'Loans', labelBn: 'ঋণ' },
]

/** How many events to show before "Show all". */
const FIRST_EVENTS = 25

export function Timeline({ events }: { events: TimelineEvent[] }) {
  const t = useT()
  const lang = useLang()
  const [stream, setStream] = useState<Stream | 'all'>('all')
  const [showAll, setShowAll] = useState(false)

  // The API lists events oldest first; the timeline reads newest first.
  const matching = events.filter((e) => stream === 'all' || e.stream === stream).slice().reverse()
  const shown = showAll ? matching : matching.slice(0, FIRST_EVENTS)

  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="m-0 text-lg font-semibold">{t('Unified timeline', 'একসাথে সময়রেখা')}</h2>
        <div role="group" aria-label={t('Show stream', 'কোন ধারা দেখাবে')} className="flex flex-wrap gap-1.5">
          {STREAM_FILTERS.map((f) => (
            <FilterChip key={f.value} on={stream === f.value} onClick={() => setStream(f.value)}>
              {t(f.label, f.labelBn)}
            </FilterChip>
          ))}
        </div>
      </div>
      {matching.length === 0 ? (
        <p className="m-0 border-t border-line-soft pt-3 text-sm text-muted">
          {events.length === 0
            ? t('No events to show.', 'দেখানোর মতো কোনো ঘটনা নেই।')
            : t('No events in this stream.', 'এই ধারায় কোনো ঘটনা নেই।')}
        </p>
      ) : (
        <ol className="m-0 flex list-none flex-col p-0">
          {shown.map((e, i) => {
            const meta = STREAM_META[e.stream]
            return (
              <li
                key={`${e.date}-${i}`}
                className="grid grid-cols-[96px_20px_minmax(0,1fr)_auto] items-start gap-3 border-t border-line-soft py-2.5"
              >
                <span className="pt-px font-mono text-[13px] text-muted tabular">{fmtDate(e.date)}</span>
                <span
                  aria-hidden="true"
                  className={cn('mt-[5px] block size-2.5', e.stream === 'loan' ? 'rotate-45 rounded-[2px]' : 'rounded-full')}
                  style={{ background: meta.color }}
                />
                <span className="flex flex-col gap-0.5">
                  <span className="text-sm font-medium">{lang === 'bn' && e.label_bn ? e.label_bn : e.label}</span>
                  <span className="text-xs text-muted-2">{t(meta.source, meta.sourceBn)}</span>
                </span>
                <span className="font-mono text-sm font-medium tabular">{taka(e.amount_bdt)}</span>
              </li>
            )
          })}
        </ol>
      )}
      {matching.length > FIRST_EVENTS && (
        <button
          type="button"
          onClick={() => setShowAll((v) => !v)}
          className="min-h-10 cursor-pointer self-start rounded-lg border border-button-line bg-card px-3.5 font-sans text-[13px] font-semibold text-lens hover:bg-open-hover"
        >
          {showAll
            ? t('Show fewer', 'কম দেখান')
            : t(`Show all ${count(matching.length)} events`, `সব ${count(matching.length)}টি ঘটনা দেখান`)}
        </button>
      )}
    </Card>
  )
}
