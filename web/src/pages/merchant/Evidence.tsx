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
  return <span className="text-[13px] text-muted">No records in this source</span>
}

export function EvidenceCards({ profile }: { profile: MerchantProfile }) {
  const { purchases, deliveries, payments } = profile
  return (
    <section aria-labelledby="ev" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="ev" className="m-0 text-lg font-semibold">
          Evidence, last 90 days
        </h2>
        <span className="text-[13px] text-muted-2">The same numbers the score was computed from</span>
      </div>
      {!profile.consent_valid ? (
        <Card className="p-4 text-sm text-ink-3">
          Without a valid consent no purchase, delivery or payment records are shown.
        </Card>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fit,minmax(190px,1fr))] gap-3">
          <StreamCard color="#0E5A4A" name="Purchases" source="Mokam">
            {purchases ? (
              <>
                <Headline value={taka(purchases.value_bdt_90d)} caption={`stock bought in ${plural(purchases.n_purchases_90d, 'purchase', 'purchases')}`} />
                <Facts rows={[['Categories', count(purchases.n_categories)], ['Weeks active', count(purchases.weeks_active)]]} />
              </>
            ) : (
              <NoRecords />
            )}
          </StreamCard>
          <StreamCard color="#4A5A8C" name="Deliveries" source="REDX">
            {deliveries ? (
              <>
                <Headline value={plural(deliveries.n_parcels_90d, 'parcel', 'parcels')} caption={`${pct(deliveries.delivered_rate)} delivered`} />
                <Facts
                  rows={[
                    ['Returned', pct(deliveries.return_rate)],
                    ['Failed', pct(deliveries.failed_rate)],
                    ['COD passed back on time', pct(deliveries.cod_remit_ontime_rate)],
                  ]}
                />
              </>
            ) : (
              <NoRecords />
            )}
          </StreamCard>
          <StreamCard color="#B5650D" name="Payments" source="Baki">
            {payments ? (
              <>
                <Headline value={`${pct(payments.ontime_rate)} on time`} caption={`across ${plural(payments.n_payments, 'repayment', 'repayments')}`} />
                <Facts rows={[['Average days late', payments.avg_days_late == null ? '—' : payments.avg_days_late.toFixed(1)]]} />
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

const STREAM_META: Record<Stream, { color: string; source: string }> = {
  purchase: { color: '#0E5A4A', source: 'Mokam · stock purchase' },
  delivery: { color: '#4A5A8C', source: 'REDX · delivery' },
  payment: { color: '#B5650D', source: 'Baki · repayment' },
  loan: { color: '#13201C', source: 'Loan' },
}

const STREAM_FILTERS: { value: Stream | 'all'; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'purchase', label: 'Purchases' },
  { value: 'delivery', label: 'Deliveries' },
  { value: 'payment', label: 'Payments' },
  { value: 'loan', label: 'Loans' },
]

/** How many events to show before "Show all". */
const FIRST_EVENTS = 25

export function Timeline({ events }: { events: TimelineEvent[] }) {
  const [stream, setStream] = useState<Stream | 'all'>('all')
  const [showAll, setShowAll] = useState(false)

  // The API lists events oldest first; the timeline reads newest first.
  const matching = events.filter((e) => stream === 'all' || e.stream === stream).slice().reverse()
  const shown = showAll ? matching : matching.slice(0, FIRST_EVENTS)

  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="m-0 text-lg font-semibold">Unified timeline</h2>
        <div role="group" aria-label="Show stream" className="flex flex-wrap gap-1.5">
          {STREAM_FILTERS.map((f) => (
            <FilterChip key={f.value} on={stream === f.value} onClick={() => setStream(f.value)}>
              {f.label}
            </FilterChip>
          ))}
        </div>
      </div>
      {matching.length === 0 ? (
        <p className="m-0 border-t border-line-soft pt-3 text-sm text-muted">
          {events.length === 0 ? 'No events to show.' : 'No events in this stream.'}
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
                  <span className="text-sm font-medium">{e.label}</span>
                  <span className="text-xs text-muted-2">{meta.source}</span>
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
          {showAll ? 'Show fewer' : `Show all ${count(matching.length)} events`}
        </button>
      )}
    </Card>
  )
}
