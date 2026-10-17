/**
 * Consent administration (approved design: 07-consent-desktop.png): a table of merchants with
 * their consent status, and the record opened inline under its row (no side drawer).
 *
 * The table and the two counts come from GET /merchants (consent valid or not, per merchant
 * in the review queue). "View record" opens one merchant's records with
 * GET /merchants/{id}/consent; that read is audited, so a record is fetched only when asked
 * for. Statuses are worked out for the last day in the data, not the computer's clock.
 * There is no revoke button on purpose (docs/API_NOTES.md, "Consent").
 */
import { ChevronDown, ChevronRight, ExternalLink, Lock } from 'lucide-react'
import { Fragment, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import type { ConsentView, Health, QueueItem } from '@/api/types'
import { useApi } from '@/api/useApi'
import { Chip } from '@/components/BandChip'
import { ErrorCallout } from '@/components/ErrorCallout'
import { FilterSegments, Pager, SearchBox } from '@/components/Filters'
import { Card, Page, Section } from '@/components/Page'
import { categoriesOf, humanize } from '@/lib/consent'
import { count, fmtDate } from '@/lib/format'
import { PURPOSE_TEXT, categoryWord, pick, useLang, useT } from '@/lib/i18n'
import { hasQueue } from '@/lib/modes'
import { cn } from '@/lib/utils'
import { CategoryChip } from './merchant/ConsentPanel'

const PAGE_SIZE = 10

type Filter = 'all' | 'valid' | 'none'

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5 px-4 first:pl-0 max-md:px-0">
      <dt className="text-[13px] font-medium text-ink">{label}</dt>
      <dd className="m-0 text-[15px] text-ink-2 tabular">{value}</dd>
    </div>
  )
}

/** One merchant's consent records, loaded when the row is opened (an audited read). */
function ConsentRecord({ merchantId }: { merchantId: string }) {
  const t = useT()
  const lang = useLang()
  const consent = useApi<ConsentView>(`/merchants/${encodeURIComponent(merchantId)}/consent`, undefined, { noCache: true })
  if (consent.error) return <ErrorCallout error={consent.error} />
  if (!consent.data) return <span className="text-sm text-body">{t('Loading the record…', 'রেকর্ড আসছে…')}</span>
  const c = consent.data
  const latest = c.records[c.records.length - 1]
  return (
    <div className="flex flex-col gap-4 rounded-[12px] border border-line border-l-4 border-l-band-strong bg-white p-4 sm:p-5">
      <div className="flex flex-col gap-0.5">
        <h3 className="m-0 text-lg font-semibold">
          {t('Consent record', 'অনুমতির রেকর্ড')} · {merchantId}
        </h3>
        <p className="m-0 text-[15px] text-body">
          {c.valid && latest
            ? t(`This permission covers the readiness assessment until ${fmtDate(latest.expires_at)}.`, `এই অনুমতি ${fmtDate(latest.expires_at)} পর্যন্ত প্রস্তুতি যাচাইয়ে প্রযোজ্য।`)
            : t('No valid permission: no score, no decision and no questionnaire.', 'বৈধ অনুমতি নেই: কোনো স্কোর, সিদ্ধান্ত বা প্রশ্নাবলি নেই।')}
        </p>
      </div>
      {c.records.length === 0 ? (
        <span className="text-[15px] text-body">{t('No consent records exist for this merchant.', 'এই মার্চেন্টের কোনো অনুমতির রেকর্ড নেই।')}</span>
      ) : (
        c.records.map((r, i) => (
          <div key={r.consent_id ?? i} className="flex flex-col gap-3 border-t border-line pt-3 first:border-t-0 first:pt-0">
            <dl className="m-0 grid grid-cols-2 gap-y-3 md:grid-cols-5 md:divide-x md:divide-line">
              <Field label={t('Record', 'রেকর্ড')} value={r.consent_id ?? '—'} />
              <Field label={t('Purpose', 'উদ্দেশ্য')} value={r.purpose && PURPOSE_TEXT[r.purpose] ? pick(PURPOSE_TEXT[r.purpose], lang) : humanize(r.purpose)} />
              <Field label={t('Granted', 'দেওয়া হয়েছে')} value={fmtDate(r.granted_at)} />
              <Field label={t('Expires', 'মেয়াদ শেষ')} value={fmtDate(r.expires_at)} />
              <Field label={t('Revoked', 'তুলে নেওয়া')} value={r.revoked_at ? fmtDate(r.revoked_at) : t('Not revoked', 'তুলে নেওয়া হয়নি')} />
            </dl>
            <div className="flex flex-col gap-1.5">
              <span className="text-[13px] font-medium text-ink">{t('Scope', 'পরিধি')}</span>
              <div className="flex flex-wrap gap-2">
                {categoriesOf(r.data_categories).map((cat) => (
                  <CategoryChip key={cat}>{categoryWord(cat, lang)}</CategoryChip>
                ))}
              </div>
            </div>
          </div>
        ))
      )}
      <span className="text-[13px] text-body">
        {t(`Checked for ${fmtDate(c.as_of)}, the last day in the data.`, `যাচাইয়ের তারিখ ${fmtDate(c.as_of)}, ডেটার শেষ দিন।`)}
      </span>
    </div>
  )
}

function Principle({ title, children }: { title: string; children: string }) {
  return (
    <li className="flex gap-3 rounded-[12px] border border-line p-4">
      <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-mint text-lens-dark" aria-hidden="true">
        <Lock size={18} />
      </span>
      <span className="flex flex-col gap-0.5">
        <span className="text-[15px] font-semibold text-ink">{title}</span>
        <span className="text-sm text-body">{children}</span>
      </span>
    </li>
  )
}

export function ConsentPage() {
  const t = useT()
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
    return rows.filter((r) => (filter === 'all' || (filter === 'valid') === r.consent_valid) && (!needle || r.merchant_id.toLowerCase().includes(needle)))
  }, [rows, filter, search])
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const page = Math.min(Math.max(1, requestedPage), pages)
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  return (
    <Page>
      <header className="mint-wash flex flex-wrap items-center justify-between gap-4 rounded-card border border-mint-line p-5 sm:p-6">
        <div className="flex max-w-[680px] flex-col gap-1.5">
          <h1 className="m-0 text-[32px] leading-10 font-bold tracking-[-0.02em]">{t('Consent', 'অনুমতি')}</h1>
          <p className="m-0 text-base text-body">
            {t(
              'What each merchant allowed, for which purpose, and until when. Without a valid consent there is no score, no decision and no questionnaire.',
              'প্রতিটি মার্চেন্ট কী অনুমতি দিয়েছেন, কোন উদ্দেশ্যে, কতদিন পর্যন্ত। বৈধ অনুমতি ছাড়া কোনো স্কোর, সিদ্ধান্ত বা প্রশ্নাবলি নেই।',
            )}
          </p>
        </div>
        <Link
          to="/demo/consent"
          className="inline-flex min-h-12 items-center gap-2 rounded-[10px] border border-mint-line bg-mint px-5 text-[15px] font-semibold text-lens-dark no-underline hover:bg-mint-2 hover:text-lens-dark"
        >
          <ExternalLink size={18} aria-hidden="true" /> {t('See what the merchant sees', 'মার্চেন্ট কী দেখেন দেখুন')}
        </Link>
      </header>

      <Section
        title={t('What can the data be used for?', 'ডেটা কী কাজে ব্যবহার করা যায়?')}
        answer={t('Only the data needed for credit readiness is used, with the merchant’s permission.', 'মার্চেন্টের অনুমতি নিয়ে শুধু ঋণের প্রস্তুতি যাচাইয়ে দরকারি ডেটা ব্যবহার হয়।')}
      >
        <ul className="m-0 grid list-none gap-3 p-0 md:grid-cols-3">
          <Principle title={t('Purpose', 'উদ্দেশ্য')}>{t('Credit readiness assessment, and nothing else.', 'শুধু ঋণের প্রস্তুতি যাচাই, আর কিছু নয়।')}</Principle>
          <Principle title={t('Minimum data', 'ন্যূনতম ডেটা')}>{t('Only the fields the features need are kept and shown.', 'শুধু যে তথ্য দরকার, সেটুকুই রাখা ও দেখানো হয়।')}</Principle>
          <Principle title={t('Questionnaire', 'প্রশ্নাবলি')}>{t('Needs its own scope in the consent.', 'অনুমতিতে আলাদাভাবে থাকতে হয়।')}</Principle>
        </ul>
      </Section>

      {health.data && !showQueue ? (
        <Card className="p-5 text-[15px] text-body">
          {t(
            'Public data modes hold no merchant consents: their records are public datasets, not merchants of a lender.',
            'পাবলিক ডেটায় মার্চেন্টের অনুমতি নেই: সেগুলো পাবলিক ডেটাসেট, কোনো ঋণদাতার মার্চেন্ট নয়।',
          )}
        </Card>
      ) : queue.error ? (
        <ErrorCallout error={queue.error} />
      ) : (
        <>
          <Section
            title={t('Who has given permission?', 'কে অনুমতি দিয়েছেন?')}
            answer={
              queue.data
                ? t(`${count(valid)} merchants have valid consent; ${count(rows.length - valid)} cannot be scored.`, `${count(valid)} জন মার্চেন্টের বৈধ অনুমতি আছে; ${count(rows.length - valid)} জনকে স্কোর করা যায় না।`)
                : '…'
            }
          >
            <div className="grid gap-4 md:grid-cols-2">
              <div className="flex flex-col gap-1 rounded-[12px] border border-mint-line bg-mint-2 p-4">
                <span className="text-[15px] text-ink-2">{t('Valid consent', 'বৈধ অনুমতি')}</span>
                <span className="font-display text-[36px] leading-[44px] font-bold text-ink tabular">{queue.data ? count(valid) : '—'}</span>
                <span className="text-sm text-body">{t('These merchants have permission for scoring.', 'এই মার্চেন্টদের স্কোর করার অনুমতি আছে।')}</span>
              </div>
              <div className="flex flex-col gap-1 rounded-[12px] border border-line bg-ground p-4">
                <span className="text-[15px] text-ink-2">{t('No valid consent · scoring blocked', 'বৈধ অনুমতি নেই · স্কোর বন্ধ')}</span>
                <span className="font-display text-[36px] leading-[44px] font-bold text-ink tabular">{queue.data ? count(rows.length - valid) : '—'}</span>
                <span className="text-sm text-body">{t('No score, decision or questionnaire until permission is valid.', 'অনুমতি বৈধ না হওয়া পর্যন্ত কোনো স্কোর, সিদ্ধান্ত বা প্রশ্নাবলি নেই।')}</span>
              </div>
            </div>
          </Section>

          <Section
            title={t('What is each merchant’s consent status?', 'প্রত্যেক মার্চেন্টের অনুমতির অবস্থা কী?')}
            answer={t('Open a record to see what was allowed and when it expires.', 'কী অনুমতি দেওয়া হয়েছে আর কবে মেয়াদ শেষ, দেখতে একটি রেকর্ড খুলুন।')}
          >
            <div className="flex flex-wrap items-end justify-between gap-3">
              <FilterSegments<Filter>
                label={t('Status', 'অবস্থা')}
                value={filter}
                onChange={(v) => setParam('consent', v, 'all')}
                options={[
                  { value: 'all', label: t('All', 'সব') },
                  { value: 'valid', label: t('Valid', 'বৈধ') },
                  { value: 'none', label: t('No valid consent', 'বৈধ অনুমতি নেই') },
                ]}
              />
              <SearchBox className="w-[320px] max-w-full" value={search} onChange={(v) => setParam('q', v, '')} placeholder={t('Search merchant ID', 'মার্চেন্ট আইডি খুঁজুন')} />
            </div>
            <div className="overflow-x-auto rounded-[12px] border border-line" role="region" aria-label={t('Merchants and their consent', 'মার্চেন্ট ও তাদের অনুমতি')} tabIndex={0}>
              <table className="w-full min-w-[640px] border-collapse text-[15px]">
                <thead className="bg-ground">
                  <tr className="text-left text-sm text-ink-2">
                    <th scope="col" className="px-4 py-3 font-semibold">{t('Merchant', 'মার্চেন্ট')}</th>
                    <th scope="col" className="px-4 py-3 font-semibold">{t('Status', 'অবস্থা')}</th>
                    <th scope="col" className="px-4 py-3 font-semibold">{t('Effect', 'প্রভাব')}</th>
                    <th scope="col" className="px-4 py-3 font-semibold">{t('Action', 'পদক্ষেপ')}</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((r) => {
                    const isOpen = open === r.merchant_id
                    return (
                      <Fragment key={r.merchant_id}>
                        <tr className={cn('border-t border-line', isOpen && 'bg-mint-2')}>
                          <td className="px-4 py-3">
                            <Link to={`/merchants/${encodeURIComponent(r.merchant_id)}`} className="font-medium text-ink no-underline hover:text-lens-dark">
                              {r.merchant_id}
                            </Link>
                          </td>
                          <td className="px-4 py-3">
                            {r.consent_valid ? (
                              <Chip tone="strong" className="px-3 py-1 text-[13px]">
                                {t('Valid', 'বৈধ')}
                              </Chip>
                            ) : (
                              <Chip tone="peri" className="px-3 py-1 text-[13px]">
                                {t('No valid consent', 'বৈধ অনুমতি নেই')}
                              </Chip>
                            )}
                          </td>
                          <td className="px-4 py-3 text-body">{r.consent_valid ? t('Scoring allowed', 'স্কোর করা যায়') : t('Scoring blocked', 'স্কোর বন্ধ')}</td>
                          <td className="px-4 py-3">
                            <button
                              type="button"
                              aria-expanded={isOpen}
                              onClick={() => setOpen(isOpen ? null : r.merchant_id)}
                              className="inline-flex min-h-10 cursor-pointer items-center gap-1.5 border-0 bg-transparent px-0 font-sans text-[15px] font-semibold text-lens-dark hover:underline"
                            >
                              {isOpen ? t('Hide record', 'রেকর্ড লুকান') : t('View record', 'রেকর্ড দেখুন')}
                              {isOpen ? <ChevronDown size={16} aria-hidden="true" /> : <ChevronRight size={16} aria-hidden="true" />}
                            </button>
                          </td>
                        </tr>
                        {isOpen && (
                          <tr className="bg-mint-2">
                            <td colSpan={4} className="px-4 pt-0 pb-4">
                              <ConsentRecord merchantId={r.merchant_id} />
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    )
                  })}
                </tbody>
              </table>
              {queue.loading && <div className="px-5 py-10 text-center text-sm text-body">{t('Loading merchants…', 'মার্চেন্টের তালিকা আসছে…')}</div>}
              {queue.data && filtered.length === 0 && <div className="px-5 py-10 text-center text-[15px] text-body">{t('No merchants match these filters.', 'এই ফিল্টারে কোনো মার্চেন্ট মেলেনি।')}</div>}
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-body">
              <span>
                {t(`${count(filtered.length)} of ${count(rows.length)} merchants in the review queue`, `পর্যালোচনার তালিকার ${count(rows.length)} জন মার্চেন্টের মধ্যে ${count(filtered.length)} জন`)}
              </span>
              <Pager page={page} pages={pages} onPage={(p) => setParam('page', String(p), '1')} />
            </div>
          </Section>
        </>
      )}

      <Section title={t('What happens when a record is opened?', 'রেকর্ড খুললে কী হয়?')} answer={t('Opening a record writes an audit entry.', 'রেকর্ড খুললে অডিটে লেখা হয়।')}>
        <p className="m-0 text-[15px] text-body">
          {t(
            'Consent design follows platform consent in Bangladesh. India’s Account Aggregator, Singapore’s SGFinDex and Open Finance PH are design references, not integrations.',
            'অনুমতির নকশা বাংলাদেশে প্ল্যাটফর্মের অনুমতির মতো। ভারতের Account Aggregator, সিঙ্গাপুরের SGFinDex ও Open Finance PH নকশার উদাহরণ, সংযোগ নয়।',
          )}
        </p>
        <p className="m-0 text-[15px] text-body">{t('There is no revoke button here on purpose.', 'এখানে অনুমতি তুলে নেওয়ার বোতাম ইচ্ছা করেই নেই।')}</p>
      </Section>
    </Page>
  )
}
