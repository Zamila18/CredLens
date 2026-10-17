/**
 * Review queue (approved design: 02-review-queue-desktop.png): a two-by-two card grid on
 * desktop, one card per row on a phone. GET /merchants returns the whole queue (about
 * 4,200 rows, no paging in the API), so filtering, search and paging happen here in the
 * browser. The API's order is kept: pending first, oldest first.
 *
 * Filters live in the address (?status=pending&band=Review&page=2), so the browser's
 * Back button from a merchant returns to the same view, and other pages can link to a
 * filtered queue (the portfolio's "View in queue").
 */
import { Lock } from 'lucide-react'
import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router'

import type { Band, Health, QueueItem } from '@/api/types'
import { useApi } from '@/api/useApi'
import { BandChip, Chip } from '@/components/BandChip'
import { CoverageBar } from '@/components/CoverageBar'
import { EmptyState, ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { FilterChip, FilterSegments, FilterSelect, Pager, SearchBox } from '@/components/Filters'
import { Card, Page, PageHeader, SummaryStrip } from '@/components/Page'
import { ScoreRing } from '@/components/ScoreRing'
import { count, fmtDate } from '@/lib/format'
import { BAND_TEXT, pick, useLang, useT, valueText } from '@/lib/i18n'
import { hasQueue } from '@/lib/modes'

const PAGE_SIZE = 20

type StatusFilter = 'all' | 'pending' | 'decided'
type BandFilter = 'all' | Band | 'none'

const BAND_FILTERS: { value: BandFilter; label: string; labelBn: string }[] = [
  { value: 'all', label: 'All', labelBn: 'সব' },
  { value: 'Strong', label: BAND_TEXT.Strong.en, labelBn: BAND_TEXT.Strong.bn },
  { value: 'Review', label: BAND_TEXT.Review.en, labelBn: BAND_TEXT.Review.bn },
  { value: 'Needs more info', label: BAND_TEXT['Needs more info'].en, labelBn: BAND_TEXT['Needs more info'].bn },
  { value: 'none', label: 'No consent', labelBn: 'অনুমতি নেই' },
]

/** Tiers in their natural order; any other value the data holds goes after them. */
const TIER_ORDER = ['metro', 'city', 'small_town']

function distinct(rows: QueueItem[], pick: (r: QueueItem) => string | null | undefined): string[] {
  return [...new Set(rows.map(pick).filter((v): v is string => Boolean(v)))]
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5 px-3 first:pl-0">
      <dt className="text-[13px] text-muted-2">{label}</dt>
      <dd className="m-0 truncate text-[15px] text-ink tabular">{value}</dd>
    </div>
  )
}

/** One merchant: id and place, status, the score with band and coverage (or the lock), facts, Open. */
function MerchantCard({ row }: { row: QueueItem }) {
  const t = useT()
  const lang = useLang()
  const scored = row.consent_valid && row.score != null && row.coverage != null && row.band ? row : null
  return (
    <li className="flex flex-col gap-4 rounded-card border border-card-line bg-card p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col">
          <span className="font-display text-[22px] leading-7 font-bold text-ink">{row.merchant_id}</span>
          <span className="text-sm text-body">
            {[row.district, row.town_tier && valueText(row.town_tier, lang)].filter(Boolean).join(' · ') || '—'}
          </span>
        </div>
        <Chip tone={row.status === 'pending' ? 'amber' : 'strong'} className="px-3 py-1 text-[13px]">
          {row.status === 'pending' ? t('Pending', 'অপেক্ষমাণ') : t('Decided', 'সিদ্ধান্ত হয়েছে')}
        </Chip>
      </div>

      <div className="flex min-h-[132px] items-center rounded-[12px] border border-line px-4 py-3">
        {scored && scored.band && scored.score != null && scored.coverage != null ? (
          <div className="flex w-full flex-wrap items-center gap-x-5 gap-y-3">
            <ScoreRing score={scored.score} band={scored.band} coverage={scored.coverage} size={96} />
            <div className="flex min-w-[150px] flex-1 flex-col gap-2">
              <BandChip band={scored.band} lowScoreWarning={scored.low_score_warning} size="md" className="self-start" />
              <div className="flex flex-col gap-1">
                <span className="flex items-baseline justify-between gap-2">
                  <span className="text-[13px] text-muted-2">{t('Coverage', 'কভারেজ')}</span>
                  <span className="text-lg font-bold text-ink tabular">{Math.round(scored.coverage * 100)}%</span>
                </span>
                <CoverageBar coverage={scored.coverage} band={scored.band} wide label={false} />
              </div>
              {scored.low_score_warning && scored.band !== 'Needs more info' && (
                <span className="text-[13px] text-body">
                  {t('Low score: read every reason before deciding.', 'কম স্কোর: সিদ্ধান্তের আগে প্রতিটি কারণ পড়ুন।')}
                </span>
              )}
              {scored.band === 'Needs more info' && (
                <span className="text-[13px] text-body">
                  {t('Too little evidence to rely on the number.', 'সংখ্যার ওপর ভরসা করার মতো প্রমাণ কম।')}
                </span>
              )}
            </div>
          </div>
        ) : (
          <div className="flex w-full flex-col items-center gap-1.5 text-center">
            <span className="flex size-12 items-center justify-center rounded-full bg-neutral-chip text-ink-2">
              <Lock size={20} aria-hidden="true" />
            </span>
            <span className="font-semibold text-ink">
              {row.consent_valid ? t('No score', 'কোনো স্কোর নেই') : t('Consent needed', 'অনুমতি দরকার')}
            </span>
            <span className="text-[13px] text-body">
              {row.consent_valid
                ? t('Open the merchant to see why.', 'কারণ দেখতে মার্চেন্ট খুলুন।')
                : t('No score until the merchant consents.', 'মার্চেন্ট অনুমতি না দেওয়া পর্যন্ত কোনো স্কোর নেই।')}
            </span>
          </div>
        )}
      </div>

      <dl className="m-0 grid grid-cols-3 divide-x divide-line">
        <Fact label={t('Shop', 'দোকান')} value={valueText(row.shop_type, lang)} />
        <Fact label={t('Onboarded', 'যুক্ত হয়েছে')} value={fmtDate(row.onboarded_at)} />
        <Fact label={t('Waiting since', 'অপেক্ষা শুরু')} value={fmtDate(row.pending_since)} />
      </dl>

      <Link
        to={`/merchants/${encodeURIComponent(row.merchant_id)}`}
        aria-label={`${t('Open', 'খুলুন')} ${row.merchant_id}`}
        className="mt-auto flex min-h-11 items-center justify-center rounded-[10px] border-[1.5px] border-lens bg-white text-[15px] font-semibold text-lens-dark no-underline hover:bg-mint-2 hover:text-lens-dark"
      >
        {t('Open', 'খুলুন')}
      </Link>
    </li>
  )
}

function NoQueue() {
  const t = useT()
  return (
    <Page>
      <PageHeader title={t('Review queue', 'পর্যালোচনার তালিকা')} />
      <Card className="flex max-w-[720px] flex-col gap-2 p-5 text-[15px] text-body">
        <span className="font-semibold text-ink">{t('No review queue for public data', 'পাবলিক ডেটায় পর্যালোচনার তালিকা নেই')}</span>
        <span>
          {t(
            'In a public data mode every outcome is already known, so there are no merchants to review. This source shows its model card and totals only.',
            'পাবলিক ডেটায় প্রতিটি ফলাফল আগে থেকেই জানা, তাই পর্যালোচনার মতো কোনো মার্চেন্ট নেই। এই উৎস শুধু তার মডেল কার্ড ও মোট হিসাব দেখায়।',
          )}
        </span>
        <Link to="/model" className="font-semibold">
          {t('Open the model card', 'মডেল কার্ড খুলুন')}
        </Link>
      </Card>
    </Page>
  )
}

export function QueuePage() {
  const t = useT()
  const lang = useLang()
  const health = useApi<Health>('/health')
  const showQueue = hasQueue(health.data?.data_mode)
  const queue = useApi<QueueItem[]>(showQueue ? '/merchants' : null)
  const [params, setParams] = useSearchParams()

  const status = (params.get('status') ?? 'all') as StatusFilter
  const band = (params.get('band') ?? 'all') as BandFilter
  const tier = params.get('tier') ?? 'all'
  const shop = params.get('shop') ?? 'all'
  const search = params.get('q') ?? ''
  const requestedPage = Number(params.get('page') ?? '1') || 1

  /** Change one filter; any filter change goes back to page 1. */
  const setParam = (key: string, value: string, defaultValue = 'all') => {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        if (value === defaultValue) next.delete(key)
        else next.set(key, value)
        if (key !== 'page') next.delete('page')
        return next
      },
      { replace: key === 'q' },
    )
  }

  const rows = useMemo(() => queue.data ?? [], [queue.data])

  const counts = useMemo(
    () => ({
      pending: rows.filter((r) => r.status === 'pending').length,
      decided: rows.filter((r) => r.status === 'decided').length,
      nmi: rows.filter((r) => r.band === 'Needs more info').length,
      noConsent: rows.filter((r) => !r.consent_valid).length,
    }),
    [rows],
  )

  const tiers = useMemo(() => {
    const found = distinct(rows, (r) => r.town_tier)
    return [...TIER_ORDER.filter((t) => found.includes(t)), ...found.filter((t) => !TIER_ORDER.includes(t)).sort()]
  }, [rows])
  const shops = useMemo(() => distinct(rows, (r) => r.shop_type).sort(), [rows])

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return rows.filter((r) => {
      if (status !== 'all' && r.status !== status) return false
      if (band === 'none' && r.consent_valid) return false
      if (band !== 'all' && band !== 'none' && r.band !== band) return false
      if (tier !== 'all' && r.town_tier !== tier) return false
      if (shop !== 'all' && r.shop_type !== shop) return false
      if (needle && !r.merchant_id.toLowerCase().includes(needle)) return false
      return true
    })
  }, [rows, status, band, tier, shop, search])

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const page = Math.min(Math.max(1, requestedPage), pages)
  const first = (page - 1) * PAGE_SIZE
  const visible = filtered.slice(first, first + PAGE_SIZE)

  if (health.data && !showQueue) return <NoQueue />

  const tileValue = (n: number) => (queue.data ? count(n) : '—')

  return (
    <Page>
      <PageHeader
        title={t('Review queue', 'পর্যালোচনার তালিকা')}
        description={t(
          'Pending merchants first, oldest first. Every score travels with its coverage and band. Open a merchant to read why.',
          'অপেক্ষমাণ মার্চেন্ট আগে, সবচেয়ে পুরোনো আগে। প্রতিটি স্কোরের সাথে তার কভারেজ ও ব্যান্ড থাকে। কারণ পড়তে মার্চেন্ট খুলুন।',
        )}
      />

      <SummaryStrip
        label={t('Queue summary', 'তালিকার সারাংশ')}
        items={[
          { label: t('Pending', 'অপেক্ষমাণ'), value: tileValue(counts.pending) },
          { label: pick(BAND_TEXT['Needs more info'], lang), value: tileValue(counts.nmi), muted: true },
          { label: t('Consent missing · no score', 'অনুমতি নেই · কোনো স্কোর নেই'), value: tileValue(counts.noConsent) },
          { label: t('Decided', 'সিদ্ধান্ত হয়েছে'), value: tileValue(counts.decided) },
        ]}
      />

      <Card className="flex flex-col gap-4 p-4 sm:p-5">
        <div className="flex flex-wrap items-end gap-4">
          <SearchBox
            className="min-w-[220px] flex-[2_1_260px]"
            value={search}
            onChange={(v) => setParam('q', v, '')}
            placeholder={t('Search merchant ID', 'মার্চেন্ট আইডি খুঁজুন')}
          />
          <FilterSegments<StatusFilter>
            label={t('Status', 'অবস্থা')}
            value={status}
            onChange={(v) => setParam('status', v)}
            options={[
              { value: 'all', label: t('All', 'সব') },
              { value: 'pending', label: t('Pending', 'অপেক্ষমাণ') },
              { value: 'decided', label: t('Decided', 'সিদ্ধান্ত হয়েছে') },
            ]}
          />
          <FilterSelect
            className="flex-1"
            label={t('Town tier', 'শহরের ধরন')}
            value={tier}
            onChange={(v) => setParam('tier', v)}
            options={[{ value: 'all', label: t('All', 'সব') }, ...tiers.map((x) => ({ value: x, label: valueText(x, lang) }))]}
          />
          <FilterSelect
            className="flex-1"
            label={t('Shop type', 'দোকানের ধরন')}
            value={shop}
            onChange={(v) => setParam('shop', v)}
            options={[{ value: 'all', label: t('All', 'সব') }, ...shops.map((s) => ({ value: s, label: valueText(s, lang) }))]}
          />
        </div>
        <div role="group" aria-label={t('Band', 'ব্যান্ড')} className="flex flex-wrap items-center gap-2 border-t border-line pt-4">
          <span className="mr-2 text-sm font-medium text-ink-2">{t('Band', 'ব্যান্ড')}</span>
          {BAND_FILTERS.map((b) => (
            <FilterChip key={b.value} on={band === b.value} onClick={() => setParam('band', b.value)}>
              {t(b.label, b.labelBn)}
            </FilterChip>
          ))}
        </div>
      </Card>

      {queue.error ? (
        <ErrorCallout error={queue.error} />
      ) : (
        <>
          {queue.loading && <LoadingState title={t('Loading the queue…', 'তালিকা আসছে…')} text={t('The queue is being fetched.', 'তালিকা আনা হচ্ছে।')} />}
          {queue.data && filtered.length === 0 && (
            <EmptyState title={t('No merchants match these filters.', 'এই ফিল্টারে কোনো মার্চেন্ট মেলেনি।')} text={t('Change or clear a filter to see more.', 'আরও দেখতে একটি ফিল্টার বদলান বা মুছুন।')} />
          )}
          <ul className="m-0 grid list-none gap-5 p-0 lg:grid-cols-2">
            {visible.map((r) => (
              <MerchantCard key={r.merchant_id} row={r} />
            ))}
          </ul>
          <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 text-sm text-body">
            <span>
              {filtered.length > 0
                ? t(
                    `Showing ${count(first + 1)}–${count(first + visible.length)} of ${count(filtered.length)} merchants`,
                    `${count(filtered.length)} জন মার্চেন্টের মধ্যে ${count(first + 1)}–${count(first + visible.length)} দেখানো হচ্ছে`,
                  )
                : t(`Showing 0 of ${count(rows.length)} merchants`, `${count(rows.length)} জন মার্চেন্টের মধ্যে 0 দেখানো হচ্ছে`)}
              {filtered.length !== rows.length && filtered.length > 0 && t(` (${count(rows.length)} in the queue)`, ` (তালিকায় ${count(rows.length)})`)}
            </span>
            <Pager page={page} pages={pages} onPage={(p) => setParam('page', String(p), '1')} />
            <span>{t('A thin file shows as Needs more info, never as a low band.', 'কম তথ্যের ফাইল "আরও তথ্য প্রয়োজন" দেখায়, কখনও নিচু ব্যান্ড নয়।')}</span>
          </div>
        </>
      )}
    </Page>
  )
}
