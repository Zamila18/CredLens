/**
 * Review queue (Main.dc.html). GET /merchants returns the whole queue (about 4,200
 * rows, no paging in the API), so filtering, search and paging happen here in the
 * browser. The API's order is kept: pending first, oldest first.
 *
 * Filters live in the address (?status=pending&band=Review&page=2), so the browser's
 * Back button from a merchant returns to the same view.
 */
import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router'

import type { Band, Health, QueueItem } from '@/api/types'
import { useApi } from '@/api/useApi'
import { scoreNumberClass } from '@/components/band'
import { BandChip, Chip } from '@/components/BandChip'
import { CoverageBar } from '@/components/CoverageBar'
import { ErrorCallout } from '@/components/ErrorCallout'
import { FilterChip, FilterSelect, Pager } from '@/components/Filters'
import { ChevronRight, LockIcon, SearchIcon } from '@/components/icons'
import { Card, Page, PageHeader } from '@/components/Page'
import { Segmented } from '@/components/Segmented'
import { StatTile } from '@/components/StatTile'
import { count, fmtDate } from '@/lib/format'
import { BAND_TEXT, pick, useLang, useT, valueText } from '@/lib/i18n'
import { hasQueue } from '@/lib/modes'
import { cn } from '@/lib/utils'

const PAGE_SIZE = 50

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

function ReadinessCell({ row }: { row: QueueItem }) {
  const t = useT()
  // A score is shown only together with its coverage and band.
  if (!row.consent_valid || row.score == null || row.coverage == null || !row.band) {
    return (
      <div className="flex items-center gap-2.5 text-neutral-text">
        <LockIcon />
        <div className="flex flex-col">
          <span className="text-[13px] font-semibold">
            {row.consent_valid ? t('No score', 'কোনো স্কোর নেই') : t('Consent needed', 'অনুমতি দরকার')}
          </span>
          <span className="text-xs">
            {row.consent_valid
              ? t('Open the merchant to see why', 'কারণ দেখতে মার্চেন্ট খুলুন')
              : t('No score until the merchant consents', 'অনুমতি না দেওয়া পর্যন্ত কোনো স্কোর নেই')}
          </span>
        </div>
      </div>
    )
  }
  return (
    <div className="flex items-center gap-3.5">
      <span className={cn('min-w-11 font-mono text-[28px] font-semibold tabular', scoreNumberClass(row.band, row.low_score_warning))}>
        {row.score}
      </span>
      <div className="flex flex-col gap-1.5">
        <BandChip band={row.band} lowScoreWarning={row.low_score_warning} className="self-start" />
        <CoverageBar coverage={row.coverage} band={row.band} />
      </div>
    </div>
  )
}

function NoQueue() {
  const t = useT()
  return (
    <Page>
      <PageHeader title={t('Review queue', 'পর্যালোচনার তালিকা')} />
      <Card className="flex max-w-[720px] flex-col gap-2 p-5 text-sm text-ink-3">
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
        aside={
          <label className="flex min-h-11 min-w-[260px] items-center gap-2 rounded-[10px] border border-control-line bg-card px-3">
            <SearchIcon />
            <span className="sr-only">{t('Search merchant ID', 'মার্চেন্ট আইডি খুঁজুন')}</span>
            <input
              type="search"
              placeholder={t('Search merchant ID', 'মার্চেন্ট আইডি খুঁজুন')}
              value={search}
              onChange={(e) => setParam('q', e.target.value, '')}
              className="flex-1 border-0 bg-transparent font-sans text-sm text-ink outline-none"
            />
          </label>
        }
      />

      <section aria-label={t('Queue summary', 'তালিকার সারাংশ')} className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-3">
        <StatTile label={t('Pending', 'অপেক্ষমাণ')} value={tileValue(counts.pending)} />
        <StatTile label={pick(BAND_TEXT['Needs more info'], lang)} value={tileValue(counts.nmi)} valueClassName="text-peri-text" />
        <StatTile label={t('Consent missing · no score', 'অনুমতি নেই · কোনো স্কোর নেই')} value={tileValue(counts.noConsent)} />
        <StatTile label={t('Decided', 'সিদ্ধান্ত হয়েছে')} value={tileValue(counts.decided)} />
      </section>

      <section aria-label={t('Filters', 'ফিল্টার')} className="flex flex-wrap items-center gap-x-5 gap-y-3">
        <Segmented<StatusFilter>
          label={t('Status', 'অবস্থা')}
          value={status}
          onChange={(v) => setParam('status', v)}
          options={[
            { value: 'all', label: t('All', 'সব') },
            { value: 'pending', label: t('Pending', 'অপেক্ষমাণ') },
            { value: 'decided', label: t('Decided', 'সিদ্ধান্ত হয়েছে') },
          ]}
        />
        <div role="group" aria-label={t('Band', 'ব্যান্ড')} className="flex flex-wrap items-center gap-2">
          <span className="text-[13px] text-muted">{t('Band', 'ব্যান্ড')}</span>
          {BAND_FILTERS.map((b) => (
            <FilterChip key={b.value} on={band === b.value} onClick={() => setParam('band', b.value)}>
              {t(b.label, b.labelBn)}
            </FilterChip>
          ))}
        </div>
        <div className="flex flex-wrap gap-2 lg:ml-auto">
          <FilterSelect
            label={t('Town tier', 'শহরের ধরন')}
            value={tier}
            onChange={(v) => setParam('tier', v)}
            options={[{ value: 'all', label: t('All', 'সব') }, ...tiers.map((x) => ({ value: x, label: valueText(x, lang) }))]}
          />
          <FilterSelect
            label={t('Shop type', 'দোকানের ধরন')}
            value={shop}
            onChange={(v) => setParam('shop', v)}
            options={[{ value: 'all', label: t('All', 'সব') }, ...shops.map((s) => ({ value: s, label: valueText(s, lang) }))]}
          />
        </div>
      </section>

      {queue.error ? (
        <ErrorCallout error={queue.error} />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[880px] border-collapse text-sm">
              <thead>
                <tr className="text-left text-xs tracking-[.04em] text-muted uppercase">
                  <th scope="col" className="px-5 py-3.5 font-semibold">{t('Merchant', 'মার্চেন্ট')}</th>
                  <th scope="col" className="px-3 py-3.5 font-semibold">{t('Readiness', 'প্রস্তুতি')}</th>
                  <th scope="col" className="px-3 py-3.5 font-semibold">{t('Shop', 'দোকান')}</th>
                  <th scope="col" className="px-3 py-3.5 font-semibold">{t('Onboarded', 'যুক্ত হয়েছে')}</th>
                  <th scope="col" className="px-3 py-3.5 font-semibold">{t('Waiting since', 'অপেক্ষা শুরু')}</th>
                  <th scope="col" className="px-3 py-3.5 font-semibold">{t('Status', 'অবস্থা')}</th>
                  <th scope="col" className="px-5 py-3.5">
                    <span className="sr-only">{t('Open', 'খুলুন')}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {visible.map((r) => (
                  <tr key={r.merchant_id} className="border-t border-line hover:bg-row-hover">
                    <td className="px-5 py-4 align-middle">
                      <div className="font-mono text-sm font-semibold">{r.merchant_id}</div>
                      <div className="text-[13px] text-muted">
                        {[r.district, r.town_tier && valueText(r.town_tier, lang)].filter(Boolean).join(' · ') || '—'}
                      </div>
                    </td>
                    <td className="p-3 align-middle">
                      <ReadinessCell row={r} />
                    </td>
                    <td className="p-3 align-middle text-ink-2">{valueText(r.shop_type, lang)}</td>
                    <td className="p-3 align-middle font-mono text-[13px] text-ink-2 tabular">{fmtDate(r.onboarded_at)}</td>
                    <td className="p-3 align-middle font-mono text-[13px] text-ink-2 tabular">{fmtDate(r.pending_since)}</td>
                    <td className="p-3 align-middle">
                      <Chip tone={r.status === 'pending' ? 'neutral' : 'strong'}>
                        {r.status === 'pending' ? t('Pending', 'অপেক্ষমাণ') : t('Decided', 'সিদ্ধান্ত হয়েছে')}
                      </Chip>
                    </td>
                    <td className="px-5 py-3 text-right align-middle">
                      <Link
                        to={`/merchants/${encodeURIComponent(r.merchant_id)}`}
                        aria-label={`${t('Open', 'খুলুন')} ${r.merchant_id}`}
                        className="inline-flex min-h-5 items-center gap-1.5 rounded-lg border border-button-line px-3.5 py-2.5 text-[13px] font-semibold text-lens no-underline hover:bg-open-hover hover:text-lens-hover"
                      >
                        {t('Open', 'খুলুন')} <ChevronRight />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {queue.loading && <div className="px-5 py-10 text-center text-sm text-muted">{t('Loading the queue…', 'তালিকা আসছে…')}</div>}
          {queue.data && filtered.length === 0 && (
            <div className="px-5 py-10 text-center text-sm text-muted">
              {t('No merchants match these filters.', 'এই ফিল্টারে কোনো মার্চেন্ট মেলেনি।')}
            </div>
          )}
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t border-line px-5 py-3.5 text-[13px] text-muted">
            <span>
              {filtered.length > 0
                ? t(
                    `Showing ${count(first + 1)}–${count(first + visible.length)} of ${count(filtered.length)} merchants`,
                    `${count(filtered.length)} জন মার্চেন্টের মধ্যে ${count(first + 1)}–${count(first + visible.length)} দেখানো হচ্ছে`,
                  )
                : t(`Showing 0 of ${count(rows.length)} merchants`, `${count(rows.length)} জন মার্চেন্টের মধ্যে 0 দেখানো হচ্ছে`)}
              {filtered.length !== rows.length &&
                filtered.length > 0 &&
                t(` (${count(rows.length)} in the queue)`, ` (তালিকায় ${count(rows.length)})`)}
            </span>
            <Pager page={page} pages={pages} onPage={(p) => setParam('page', String(p), '1')} />
            <span>
              {t(
                'A thin file shows as Needs more info, never as a low band.',
                'কম তথ্যের ফাইল "আরও তথ্য প্রয়োজন" দেখায়, কখনও নিচু ব্যান্ড নয়।',
              )}
            </span>
          </div>
        </Card>
      )}
    </Page>
  )
}
