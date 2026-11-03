/**
 * Merchant page (approved design: 03-merchant-desktop.png): "Evidence, last 90 days" and the
 * unified timeline. The 90-day numbers are the ones the score was computed from.
 * A stream that is null has no records in that source: it says so instead of zeros.
 * Nothing here is invented: dates, amounts and labels come from GET /merchants/{id}.
 */
import { ShoppingBasket, Truck, Wallet } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import type { MerchantLoan, MerchantProfile, TimelineEvent } from '@/api/types'
import { StatusTag } from '@/components/StatusTag'
import { LOAN_KIND } from '@/lib/statuses'
import { FilterChip } from '@/components/Filters'
import { Section } from '@/components/Page'
import { count, fmtDate, pct, taka } from '@/lib/format'
import { useLang, useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'

function plural(n: number, one: string, many: string) {
  return `${count(n)} ${n === 1 ? one : many}`
}

/** Stream colours: purchases blue, deliveries violet, repayments amber, loans ink (each also named in words). */
const STREAM_COLOR = { purchase: '#2F6FB0', delivery: '#6555A6', payment: '#B7791F', loan: '#111B42' } as const

function StreamCard({
  icon,
  color,
  name,
  source,
  tone,
  children,
}: {
  icon: ReactNode
  color: string
  name: string
  source: string
  tone: string
  children: ReactNode
}) {
  return (
    <div className={cn('flex flex-col gap-3 rounded-[12px] border p-4', tone)}>
      <div className="flex items-center gap-2 text-sm font-semibold" style={{ color }}>
        {icon}
        <span>
          {name} · {source}
        </span>
      </div>
      {children}
    </div>
  )
}

function Headline({ value, caption }: { value: string; caption: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-display text-[30px] leading-9 font-bold text-ink tabular">{value}</span>
      <span className="text-sm text-body">{caption}</span>
    </div>
  )
}

function Facts({ rows }: { rows: [string, string][] }) {
  return (
    <dl className="m-0 grid grid-cols-2 gap-3 border-t border-line pt-3">
      {rows.map(([k, v]) => (
        <div key={k} className="flex flex-col gap-0.5">
          <dt className="text-[13px] text-muted-2">{k}</dt>
          <dd className="m-0 text-lg font-semibold text-ink tabular">{v}</dd>
        </div>
      ))}
    </dl>
  )
}

function NoRecords() {
  const t = useT()
  return <span className="text-sm text-body">{t('No records in this source.', 'এই উৎসে কোনো রেকর্ড নেই।')}</span>
}

/** The parcels donut: delivered, returned, failed (and anything else) as shares of 90 days. */
function ParcelDonut({ parcels, delivered, returned, failed }: { parcels: number; delivered: number; returned: number; failed: number }) {
  const t = useT()
  const size = 96
  const stroke = 12
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const parts = [
    { share: delivered, color: '#16845B' },
    { share: returned, color: '#D9A441' },
    { share: failed, color: '#8E9AAD' },
  ]
  let offset = 0
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#E6EEF0" strokeWidth={stroke} />
        {parts.map((p) => {
          const length = c * Math.max(0, p.share)
          const circle = (
            <circle
              key={p.color}
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              stroke={p.color}
              strokeWidth={stroke}
              strokeDasharray={`${length.toFixed(1)} ${c.toFixed(1)}`}
              strokeDashoffset={(-offset).toFixed(1)}
              transform={`rotate(-90 ${size / 2} ${size / 2})`}
            />
          )
          offset += length
          return circle
        })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-display text-2xl leading-none font-bold text-ink tabular">{count(parcels)}</span>
        <span className="text-xs text-body">{t('parcels', 'পার্সেল')}</span>
      </div>
    </div>
  )
}

function Legend({ color, children }: { color: string; children: ReactNode }) {
  return (
    <li className="flex items-center gap-2 text-sm text-ink-2">
      <span className="size-2.5 shrink-0 rounded-full" style={{ background: color }} aria-hidden="true" />
      {children}
    </li>
  )
}

export function EvidenceCards({ profile }: { profile: MerchantProfile }) {
  const t = useT()
  const { purchases, deliveries, payments } = profile
  return (
    <Section
      id="evidence"
      title={t('Evidence, last 90 days', 'প্রমাণ, গত ৯০ দিন')}
      answer={t('The same numbers the score was computed from.', 'যে সংখ্যা থেকে স্কোর হিসাব হয়েছে, সেগুলোই।')}
    >
      <div className="grid gap-4 @2xl:grid-cols-3">
        <StreamCard
          icon={<ShoppingBasket size={18} aria-hidden="true" />}
          color={STREAM_COLOR.purchase}
          name={t('Purchases', 'কেনাকাটা')}
          source={t('stock bought from suppliers', 'সরবরাহকারীর কাছ থেকে কেনা')}
          tone="border-[#D5E4F3] bg-info-panel/60"
        >
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

        <StreamCard
          icon={<Truck size={18} aria-hidden="true" />}
          color={STREAM_COLOR.delivery}
          name={t('Deliveries', 'ডেলিভারি')}
          source={t('parcels sent to customers', 'গ্রাহকের কাছে পাঠানো পার্সেল')}
          tone="border-peri-chip bg-peri-panel/60"
        >
          {deliveries ? (
            <>
              <div className="flex flex-wrap items-center gap-4">
                <ParcelDonut
                  parcels={deliveries.n_parcels_90d}
                  delivered={deliveries.delivered_rate ?? 0}
                  returned={deliveries.return_rate ?? 0}
                  failed={deliveries.failed_rate ?? 0}
                />
                <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
                  <Legend color="#16845B">{t(`${pct(deliveries.delivered_rate, 1)} delivered`, `${pct(deliveries.delivered_rate, 1)} পৌঁছেছে`)}</Legend>
                  <Legend color="#D9A441">{t(`${pct(deliveries.return_rate, 1)} returned`, `${pct(deliveries.return_rate, 1)} ফেরত`)}</Legend>
                  <Legend color="#8E9AAD">{t(`${pct(deliveries.failed_rate, 1)} failed`, `${pct(deliveries.failed_rate, 1)} পৌঁছানো যায়নি`)}</Legend>
                </ul>
              </div>
              <div className="flex flex-col gap-1 border-t border-line pt-3">
                <span className="text-[13px] text-muted-2">{t('COD passed back on time', 'ক্যাশ অন ডেলিভারির টাকা সময়মতো ফেরত')}</span>
                <div className="flex items-center gap-3">
                  <span className="text-lg font-semibold text-ink tabular">{pct(deliveries.cod_remit_ontime_rate, 1)}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-track" aria-hidden="true">
                    <span className="block h-2 rounded-full bg-band-strong" style={{ width: pct(deliveries.cod_remit_ontime_rate) === '—' ? 0 : pct(deliveries.cod_remit_ontime_rate) }} />
                  </div>
                </div>
              </div>
            </>
          ) : (
            <NoRecords />
          )}
        </StreamCard>

        <StreamCard
          icon={<Wallet size={18} aria-hidden="true" />}
          color={STREAM_COLOR.payment}
          name={t('Payments', 'পেমেন্ট')}
          source={t('earlier credit', 'আগের ঋণ')}
          tone="border-amber-chip bg-amber-panel"
        >
          {payments ? (
            <>
              <Headline
                value={pct(payments.ontime_rate)}
                caption={t(
                  `on time across ${plural(payments.n_payments, 'repayment', 'repayments')}`,
                  `${count(payments.n_payments)}টি পরিশোধের মধ্যে সময়মতো`,
                )}
              />
              <Facts
                rows={[
                  [t('Average days late', 'গড়ে কত দিন দেরি'), payments.avg_days_late == null ? '—' : payments.avg_days_late.toFixed(1)],
                ]}
              />
            </>
          ) : (
            <NoRecords />
          )}
        </StreamCard>
      </div>
    </Section>
  )
}

type Stream = TimelineEvent['stream']

const STREAM_META: Record<Stream, { tag: string; tagBn: string; chip: string }> = {
  purchase: { tag: 'Purchase', tagBn: 'কেনা', chip: 'border-[#CFE0F2] bg-info-panel text-[#245C93]' },
  delivery: { tag: 'Delivery', tagBn: 'ডেলিভারি', chip: 'border-peri-chip bg-peri-panel text-peri-text' },
  payment: { tag: 'Repayment', tagBn: 'পরিশোধ', chip: 'border-amber-chip bg-amber-panel text-amber-text' },
  loan: { tag: 'Loan', tagBn: 'ঋণ', chip: 'border-line bg-neutral-chip text-ink-2' },
}

/** An application is on the loan stream but is a request, not a loan: it gets its own tag. */
const APPLICATION_META = {
  tag: 'Application · not a loan',
  tagBn: 'আবেদন · ঋণ নয়',
  chip: 'border-peri-chip bg-peri-panel text-peri-text',
}

const STREAM_FILTERS: { value: Stream | 'all'; label: string; labelBn: string }[] = [
  { value: 'all', label: 'All', labelBn: 'সব' },
  { value: 'purchase', label: 'Purchases', labelBn: 'কেনাকাটা' },
  { value: 'delivery', label: 'Deliveries', labelBn: 'ডেলিভারি' },
  { value: 'payment', label: 'Payments', labelBn: 'পেমেন্ট' },
  { value: 'loan', label: 'Loans and applications', labelBn: 'ঋণ ও আবেদন' },
]

/** How many events to show before "Show all". */
const FIRST_EVENTS = 12

export function Timeline({ events }: { events: TimelineEvent[] }) {
  const t = useT()
  const lang = useLang()
  const [stream, setStream] = useState<Stream | 'all'>('all')
  const [showAll, setShowAll] = useState(false)

  // The API lists events oldest first; the timeline reads newest first.
  const matching = events.filter((e) => stream === 'all' || e.stream === stream).slice().reverse()
  const shown = showAll ? matching : matching.slice(0, FIRST_EVENTS)

  return (
    <Section
      id="timeline"
      title={t('Unified timeline', 'একসাথে সময়রেখা')}
      answer={t('Every purchase, parcel, payment and loan in one line, newest first.', 'সব কেনাকাটা, পার্সেল, পেমেন্ট আর ঋণ এক সারিতে, নতুনটা আগে।')}
    >
      <div role="group" aria-label={t('Show stream', 'কোন ধারা দেখাবে')} className="flex flex-wrap gap-2">
        {STREAM_FILTERS.map((f) => (
          <FilterChip key={f.value} on={stream === f.value} onClick={() => setStream(f.value)}>
            {t(f.label, f.labelBn)}
          </FilterChip>
        ))}
      </div>
      {matching.length === 0 ? (
        <p className="m-0 border-t border-line pt-3 text-sm text-body">
          {events.length === 0 ? t('No events to show.', 'দেখানোর মতো কোনো ঘটনা নেই।') : t('No events in this stream.', 'এই ধারায় কোনো ঘটনা নেই।')}
        </p>
      ) : (
        <ol className="relative m-0 flex list-none flex-col p-0">
          {shown.map((e, i) => {
            const meta = e.kind === 'application' ? APPLICATION_META : STREAM_META[e.stream]
            return (
              <li
                key={`${e.date}-${i}`}
                className="grid grid-cols-[88px_16px_minmax(0,1fr)] items-start gap-x-3 gap-y-1 border-t border-line py-3 @lg:grid-cols-[104px_16px_150px_minmax(0,1fr)_auto]"
              >
                <span className="flex flex-col">
                  <span className="text-xs text-muted-2">{t('Date', 'তারিখ')}</span>
                  <span className="text-sm text-ink tabular">{fmtDate(e.date)}</span>
                </span>
                <span aria-hidden="true" className="mt-2 block size-3 rounded-full border-2 border-white shadow-[0_0_0_1px_#DCE7EB]" style={{ background: STREAM_COLOR[e.stream] }} />
                <span className={cn('hidden self-start justify-self-start rounded-md border px-2 py-0.5 text-xs font-medium @lg:inline-flex', meta.chip)}>
                  {t(meta.tag, meta.tagBn)}
                </span>
                <span className="col-start-3 flex flex-col gap-0.5 @lg:col-start-auto">
                  <span className="text-[15px] font-medium text-ink">{lang === 'bn' && e.label_bn ? e.label_bn : e.label}</span>
                  <span className="text-xs text-muted-2 @lg:hidden">{t(meta.tag, meta.tagBn)}</span>
                </span>
                {e.amount_bdt != null && (
                  <span className="col-start-3 flex flex-col @lg:col-start-auto @lg:items-end">
                    <span className="text-xs text-muted-2">{t('Amount', 'পরিমাণ')}</span>
                    <span className="text-[15px] font-semibold text-ink tabular">{taka(e.amount_bdt)}</span>
                  </span>
                )}
              </li>
            )
          })}
        </ol>
      )}
      {matching.length > FIRST_EVENTS && (
        <button
          type="button"
          onClick={() => setShowAll((v) => !v)}
          className="min-h-10 cursor-pointer self-start rounded-[10px] border border-lens bg-card px-4 font-sans text-sm font-semibold text-lens-dark hover:bg-mint-2"
        >
          {showAll ? t('Show fewer', 'কম দেখান') : t(`Show all ${count(matching.length)} events`, `সব ${count(matching.length)}টি ঘটনা দেখান`)}
        </button>
      )}
    </Section>
  )
}

/**
 * Loans and the application, said plainly (GET /merchants/{id}/loans): an issued loan with
 * its limit, or the application with the amount requested. No balance is worked out here:
 * the repayment events are on the timeline, and an application never takes a repayment.
 */
export function LoansPanel({ loans }: { loans: MerchantLoan[] }) {
  const t = useT()
  const rows = [...loans].sort((a, b) => b.issued_at.localeCompare(a.issued_at))
  return (
    <Section
      id="loans"
      title={t('Loans and application', 'ঋণ ও আবেদন')}
      answer={t(
        'Issued loans from the lender’s records, and this shop’s application if it has one. Repayments are on the timeline below.',
        'ঋণদাতার রেকর্ডের দেওয়া ঋণ, আর থাকলে এই দোকানের আবেদন। পরিশোধ নিচের সময়রেখায়।',
      )}
    >
      <ul className="m-0 flex list-none flex-col p-0">
        {rows.map((loan) => (
          <li key={loan.loan_id} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1.5 border-t border-line py-3 first:border-t-0">
            <span className="flex flex-col gap-1">
              <StatusTag status={LOAN_KIND[loan.kind]} />
              <span className="text-[13px] text-muted-2">
                {loan.kind === 'application' ? t(`Applied ${fmtDate(loan.issued_at)}`, `আবেদন ${fmtDate(loan.issued_at)}`) : t(`Issued ${fmtDate(loan.issued_at)}`, `দেওয়া হয়েছে ${fmtDate(loan.issued_at)}`)}
              </span>
            </span>
            <span className="flex flex-col items-end gap-0.5 text-right">
              <span className="text-[15px] font-semibold text-ink tabular">
                {loan.kind === 'application' ? taka(loan.requested_amount_bdt) : taka(loan.limit_bdt)}
              </span>
              <span className="text-[12.5px] text-muted-2">
                {loan.kind === 'application'
                  ? t('requested, not issued', 'চাওয়া, দেওয়া হয়নি')
                  : loan.has_outcome
                    ? t('limit · outcome known', 'সীমা · ফলাফল জানা')
                    : t('limit · outcome not known yet', 'সীমা · ফলাফল এখনও জানা নেই')}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </Section>
  )
}
