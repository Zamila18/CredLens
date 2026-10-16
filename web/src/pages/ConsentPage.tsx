/**
 * Consent (Consent.dc.html). There is no "all consents" endpoint, so the table comes
 * from GET /merchants (consent valid or not, per merchant in the review queue), and
 * "View record" opens one merchant's records with GET /merchants/{id}/consent.
 * That read is audited, so records are fetched only when asked for, one at a time.
 * There is no revoke button on purpose (docs/API_NOTES.md, "Consent").
 */
import { Fragment, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import type { ConsentView, Health, QueueItem } from '@/api/types'
import { useApi } from '@/api/useApi'
import { Chip } from '@/components/BandChip'
import { ErrorCallout } from '@/components/ErrorCallout'
import { FilterChip, Pager } from '@/components/Filters'
import { ChevronRight, SearchIcon } from '@/components/icons'
import { Card, Page, PageHeader } from '@/components/Page'
import { StatTile } from '@/components/StatTile'
import { categoriesOf, humanize } from '@/lib/consent'
import { count, fmtDate } from '@/lib/format'
import { PURPOSE_TEXT, categoryWord, pick, useLang, useT, valueText, type T } from '@/lib/i18n'
import { hasQueue } from '@/lib/modes'
import { CategoryChip } from './merchant/ConsentPanel'

const PAGE_SIZE = 50

type Filter = 'all' | 'valid' | 'none'

function effectOf(consent: ConsentView, t: T): string {
  if (!consent.valid) {
    return t('Scoring blocked: no score, no decision, no questionnaire', 'স্কোর বন্ধ: কোনো স্কোর, সিদ্ধান্ত বা প্রশ্নাবলি নেই')
  }
  return consent.data_categories.includes('questionnaire')
    ? t('Score, decision and questionnaire', 'স্কোর, সিদ্ধান্ত ও প্রশ্নাবলি')
    : t('Score and decision; no questionnaire', 'স্কোর ও সিদ্ধান্ত; প্রশ্নাবলি নয়')
}

/** One merchant's consent records, loaded when the row is opened. */
function ConsentRecord({ merchantId }: { merchantId: string }) {
  const t = useT()
  const lang = useLang()
  const consent = useApi<ConsentView>(`/merchants/${encodeURIComponent(merchantId)}/consent`, undefined, { noCache: true })
  if (consent.error) return <ErrorCallout error={consent.error} />
  if (!consent.data) return <span className="text-[13px] text-muted">{t('Loading the record…', 'রেকর্ড আসছে…')}</span>
  const c = consent.data
  return (
    <div className="flex flex-col gap-2.5">
      <span className="text-[13px] text-ink-2">
        {effectOf(c, t)} · {t('checked for', 'যাচাইয়ের তারিখ')} <span className="font-mono tabular">{fmtDate(c.as_of)}</span>
      </span>
      {c.records.length === 0 ? (
        <span className="text-[13px] text-muted">{t('No consent records exist for this merchant.', 'এই মার্চেন্টের কোনো অনুমতির রেকর্ড নেই।')}</span>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-[13px]">
            <thead>
              <tr className="text-left text-xs text-muted">
                <th scope="col" className="py-1.5 font-semibold">{t('Record', 'রেকর্ড')}</th>
                <th scope="col" className="py-1.5 font-semibold">{t('Data allowed', 'যে ডেটার অনুমতি আছে')}</th>
                <th scope="col" className="py-1.5 font-semibold">{t('Granted', 'দেওয়া হয়েছে')}</th>
                <th scope="col" className="py-1.5 font-semibold">{t('Expires', 'মেয়াদ শেষ')}</th>
                <th scope="col" className="py-1.5 font-semibold">{t('Status', 'অবস্থা')}</th>
              </tr>
            </thead>
            <tbody>
              {c.records.map((r, i) => (
                <tr key={r.consent_id ?? i} className="border-t border-line-soft align-top">
                  <td className="py-2 pr-2">
                    <div className="font-mono">{r.consent_id ?? '—'}</div>
                    <div className="text-xs text-muted-2">
                      {r.purpose && PURPOSE_TEXT[r.purpose] ? pick(PURPOSE_TEXT[r.purpose], lang) : humanize(r.purpose)}
                    </div>
                  </td>
                  <td className="py-2 pr-2">
                    <div className="flex flex-wrap gap-1">
                      {categoriesOf(r.data_categories).map((cat) => (
                        <CategoryChip key={cat}>{categoryWord(cat, lang)}</CategoryChip>
                      ))}
                    </div>
                  </td>
                  <td className="py-2 pr-2 font-mono tabular">{fmtDate(r.granted_at)}</td>
                  <td className="py-2 pr-2 font-mono tabular">{fmtDate(r.expires_at)}</td>
                  <td className="py-2">
                    {r.revoked_at ? (
                      <Chip className="shadow-[inset_0_0_0_1.5px_#9AA39E]">
                        {t(`Revoked ${fmtDate(r.revoked_at)}`, `তুলে নেওয়া হয়েছে ${fmtDate(r.revoked_at)}`)}
                      </Chip>
                    ) : (
                      <span className="text-muted">{t('Not revoked', 'তুলে নেওয়া হয়নি')}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export function ConsentPage() {
  const t = useT()
  const lang = useLang()
  const health = useApi<Health>('/health')
  const showQueue = hasQueue(health.data?.data_mode)
  const queue = useApi<QueueItem[]>(showQueue ? '/merchants' : null)
  const [params, setParams] = useSearchParams()
  const [open, setOpen] = useState<string | null>(null)

  const filter = (params.get('consent') ?? 'all') as Filter
  const search = params.get('q') ?? ''
  const requestedPage = Number(params.get('page') ?? '1') || 1

  const setParam = (key: string, value: string, defaultValue: string) =>
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

  const rows = useMemo(() => queue.data ?? [], [queue.data])
  const valid = rows.filter((r) => r.consent_valid).length
  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return rows.filter(
      (r) =>
        (filter === 'all' || (filter === 'valid') === r.consent_valid) &&
        (!needle || r.merchant_id.toLowerCase().includes(needle)),
    )
  }, [rows, filter, search])
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const page = Math.min(Math.max(1, requestedPage), pages)
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  return (
    <Page>
      <PageHeader
        title={t('Consent', 'অনুমতি')}
        description={t(
          'What each merchant allowed, for which purpose, and until when. Without a valid consent there is no score, no decision and no questionnaire.',
          'প্রতিটি মার্চেন্ট কী অনুমতি দিয়েছেন, কোন উদ্দেশ্যে, কতদিন পর্যন্ত। বৈধ অনুমতি ছাড়া কোনো স্কোর, সিদ্ধান্ত বা প্রশ্নাবলি নেই।',
        )}
        aside={
          <Link
            to="/demo/consent"
            className="inline-flex items-center gap-2 rounded-[10px] border border-button-line bg-card px-4 py-3 text-sm font-semibold no-underline hover:bg-open-hover"
          >
            {t('See what the merchant sees', 'মার্চেন্ট কী দেখেন দেখুন')} <ChevronRight />
          </Link>
        }
      />

      <section className="grid grid-cols-[repeat(auto-fit,minmax(min(240px,100%),1fr))] gap-3">
        <div className="flex flex-col gap-1 rounded-[14px] bg-strong-panel px-[18px] py-4">
          <span className="text-[13px] font-semibold text-lens-dark">{t('Purpose', 'উদ্দেশ্য')}</span>
          <span className="text-sm">{t('Credit readiness assessment, and nothing else', 'শুধু ঋণের প্রস্তুতি যাচাই, আর কিছু নয়')}</span>
        </div>
        <div className="flex flex-col gap-1 rounded-[14px] border border-card-line bg-card px-[18px] py-4">
          <span className="text-[13px] font-semibold">{t('Minimum data', 'ন্যূনতম ডেটা')}</span>
          <span className="text-sm">{t('Only the fields the features need are kept and shown', 'শুধু যে তথ্য দরকার, সেটুকুই রাখা ও দেখানো হয়')}</span>
        </div>
        <div className="flex flex-col gap-1 rounded-[14px] border border-card-line bg-card px-[18px] py-4">
          <span className="text-[13px] font-semibold">{t('Questionnaire', 'প্রশ্নাবলি')}</span>
          <span className="text-sm">{t('Needs its own scope in the consent', 'অনুমতিতে আলাদাভাবে থাকতে হয়')}</span>
        </div>
      </section>

      {health.data && !showQueue ? (
        <Card className="p-5 text-sm text-ink-3">
          {t(
            'Public data modes hold no merchant consents: their records are public datasets, not merchants of a lender.',
            'পাবলিক ডেটায় মার্চেন্টের অনুমতি নেই: সেগুলো পাবলিক ডেটাসেট, কোনো ঋণদাতার মার্চেন্ট নয়।',
          )}
        </Card>
      ) : queue.error ? (
        <ErrorCallout error={queue.error} />
      ) : (
        <>
          <section aria-label={t('Consent summary', 'অনুমতির সারাংশ')} className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-3">
            <StatTile label={t('Valid consent', 'বৈধ অনুমতি')} value={queue.data ? count(valid) : '—'} />
            <StatTile
              label={t('No valid consent · scoring blocked', 'বৈধ অনুমতি নেই · স্কোর বন্ধ')}
              value={queue.data ? count(rows.length - valid) : '—'}
            />
          </section>

          <section aria-label={t('Filters', 'ফিল্টার')} className="flex flex-wrap items-center gap-3">
            <div role="group" aria-label={t('Consent', 'অনুমতি')} className="flex flex-wrap gap-2">
              {(
                [
                  ['all', t('All', 'সব')],
                  ['valid', t('Valid', 'বৈধ')],
                  ['none', t('No valid consent', 'বৈধ অনুমতি নেই')],
                ] as [Filter, string][]
              ).map(([v, label]) => (
                <FilterChip key={v} on={filter === v} onClick={() => setParam('consent', v, 'all')}>
                  {label}
                </FilterChip>
              ))}
            </div>
            <label className="flex min-h-11 min-w-[240px] items-center gap-2 rounded-[10px] border border-control-line bg-card px-3 sm:ml-auto">
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
          </section>

          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] border-collapse text-sm">
                <thead>
                  <tr className="text-left text-xs tracking-[.04em] text-muted uppercase">
                    <th scope="col" className="px-5 py-3.5 font-semibold">{t('Merchant', 'মার্চেন্ট')}</th>
                    <th scope="col" className="px-3 py-3.5 font-semibold">{t('Status', 'অবস্থা')}</th>
                    <th scope="col" className="px-3 py-3.5 font-semibold">{t('Effect', 'প্রভাব')}</th>
                    <th scope="col" className="px-5 py-3.5">
                      <span className="sr-only">{t('Record', 'রেকর্ড')}</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((r) => {
                    const isOpen = open === r.merchant_id
                    return (
                      <Fragment key={r.merchant_id}>
                        <tr className="border-t border-line">
                          <td className="px-5 py-3.5">
                            <Link to={`/merchants/${encodeURIComponent(r.merchant_id)}`} className="font-mono font-semibold no-underline">
                              {r.merchant_id}
                            </Link>
                            <div className="text-[13px] text-muted">
                              {[r.district, r.town_tier && valueText(r.town_tier, lang)].filter(Boolean).join(' · ')}
                            </div>
                          </td>
                          <td className="px-3 py-3.5">
                            {r.consent_valid ? (
                              <Chip tone="strong">{t('Valid', 'বৈধ')}</Chip>
                            ) : (
                              <Chip className="shadow-[inset_0_0_0_1.5px_#9AA39E]">{t('No valid consent', 'বৈধ অনুমতি নেই')}</Chip>
                            )}
                          </td>
                          <td className="px-3 py-3.5 text-[13px] text-muted">
                            {r.consent_valid ? t('Scoring allowed', 'স্কোর করা যায়') : t('Scoring blocked', 'স্কোর বন্ধ')}
                          </td>
                          <td className="px-5 py-3.5 text-right">
                            <button
                              type="button"
                              aria-expanded={isOpen}
                              onClick={() => setOpen(isOpen ? null : r.merchant_id)}
                              className="min-h-10 cursor-pointer rounded-lg border border-button-line bg-card px-3.5 font-sans text-[13px] font-semibold text-lens hover:bg-open-hover"
                            >
                              {isOpen ? t('Hide record', 'রেকর্ড লুকান') : t('View record', 'রেকর্ড দেখুন')}
                            </button>
                          </td>
                        </tr>
                        {isOpen && (
                          <tr className="bg-row-hover">
                            <td colSpan={4} className="px-5 pt-1 pb-4">
                              <ConsentRecord merchantId={r.merchant_id} />
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    )
                  })}
                </tbody>
              </table>
            </div>
            {queue.loading && <div className="px-5 py-10 text-center text-sm text-muted">{t('Loading merchants…', 'মার্চেন্টের তালিকা আসছে…')}</div>}
            {queue.data && filtered.length === 0 && (
              <div className="px-5 py-10 text-center text-sm text-muted">
                {t('No merchants match these filters.', 'এই ফিল্টারে কোনো মার্চেন্ট মেলেনি।')}
              </div>
            )}
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-3.5 text-[13px] text-muted">
              <span>
                {t(
                  `${count(filtered.length)} of ${count(rows.length)} merchants in the review queue`,
                  `পর্যালোচনার তালিকার ${count(rows.length)} জন মার্চেন্টের মধ্যে ${count(filtered.length)} জন`,
                )}
              </span>
              <Pager page={page} pages={pages} onPage={(p) => setParam('page', String(p), '1')} />
            </div>
          </Card>
        </>
      )}

      <p className="m-0 text-[13px] text-muted">
        {t(
          'Consent design follows platform consent in Bangladesh. India’s Account Aggregator, Singapore’s SGFinDex and Open Finance PH are design references, not integrations. Opening a record writes an audit entry. There is no revoke button here on purpose.',
          'অনুমতির নকশা বাংলাদেশে প্ল্যাটফর্মের অনুমতির মতো। ভারতের Account Aggregator, সিঙ্গাপুরের SGFinDex ও Open Finance PH নকশার উদাহরণ, সংযোগ নয়। রেকর্ড খুললে অডিটে লেখা হয়। এখানে অনুমতি তুলে নেওয়ার বোতাম ইচ্ছা করেই নেই।',
        )}
      </p>
    </Page>
  )
}
