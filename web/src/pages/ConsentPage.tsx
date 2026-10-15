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
import { hasQueue } from '@/lib/modes'
import { CategoryChip } from './merchant/ConsentPanel'

const PAGE_SIZE = 50

type Filter = 'all' | 'valid' | 'none'

function effectOf(consent: ConsentView): string {
  if (!consent.valid) return 'Scoring blocked: no score, no decision, no questionnaire'
  return consent.data_categories.includes('questionnaire')
    ? 'Score, decision and questionnaire'
    : 'Score and decision; no questionnaire'
}

/** One merchant's consent records, loaded when the row is opened. */
function ConsentRecord({ merchantId }: { merchantId: string }) {
  const consent = useApi<ConsentView>(`/merchants/${encodeURIComponent(merchantId)}/consent`, undefined, { noCache: true })
  if (consent.error) return <ErrorCallout error={consent.error} />
  if (!consent.data) return <span className="text-[13px] text-muted">Loading the record…</span>
  const c = consent.data
  return (
    <div className="flex flex-col gap-2.5">
      <span className="text-[13px] text-ink-2">
        {effectOf(c)} · checked for <span className="font-mono tabular">{fmtDate(c.as_of)}</span>
      </span>
      {c.records.length === 0 ? (
        <span className="text-[13px] text-muted">No consent records exist for this merchant.</span>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-[13px]">
            <thead>
              <tr className="text-left text-xs text-muted">
                <th scope="col" className="py-1.5 font-semibold">Record</th>
                <th scope="col" className="py-1.5 font-semibold">Data allowed</th>
                <th scope="col" className="py-1.5 font-semibold">Granted</th>
                <th scope="col" className="py-1.5 font-semibold">Expires</th>
                <th scope="col" className="py-1.5 font-semibold">Status</th>
              </tr>
            </thead>
            <tbody>
              {c.records.map((r, i) => (
                <tr key={r.consent_id ?? i} className="border-t border-line-soft align-top">
                  <td className="py-2 pr-2">
                    <div className="font-mono">{r.consent_id ?? '—'}</div>
                    <div className="text-xs text-muted-2">{humanize(r.purpose)}</div>
                  </td>
                  <td className="py-2 pr-2">
                    <div className="flex flex-wrap gap-1">
                      {categoriesOf(r.data_categories).map((cat) => (
                        <CategoryChip key={cat}>{cat}</CategoryChip>
                      ))}
                    </div>
                  </td>
                  <td className="py-2 pr-2 font-mono tabular">{fmtDate(r.granted_at)}</td>
                  <td className="py-2 pr-2 font-mono tabular">{fmtDate(r.expires_at)}</td>
                  <td className="py-2">
                    {r.revoked_at ? (
                      <Chip className="shadow-[inset_0_0_0_1.5px_#9AA39E]">Revoked {fmtDate(r.revoked_at)}</Chip>
                    ) : (
                      <span className="text-muted">Not revoked</span>
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
        title="Consent"
        description="What each merchant allowed, for which purpose, and until when. Without a valid consent there is no score, no decision and no questionnaire."
        aside={
          <Link
            to="/demo/consent"
            className="inline-flex items-center gap-2 rounded-[10px] border border-button-line bg-card px-4 py-3 text-sm font-semibold no-underline hover:bg-open-hover"
          >
            See what the merchant sees <ChevronRight />
          </Link>
        }
      />

      <section className="grid grid-cols-[repeat(auto-fit,minmax(min(240px,100%),1fr))] gap-3">
        <div className="flex flex-col gap-1 rounded-[14px] bg-strong-panel px-[18px] py-4">
          <span className="text-[13px] font-semibold text-lens-dark">Purpose</span>
          <span className="text-sm">Credit readiness assessment, and nothing else</span>
        </div>
        <div className="flex flex-col gap-1 rounded-[14px] border border-card-line bg-card px-[18px] py-4">
          <span className="text-[13px] font-semibold">Minimum data</span>
          <span className="text-sm">Only the fields the features need are kept and shown</span>
        </div>
        <div className="flex flex-col gap-1 rounded-[14px] border border-card-line bg-card px-[18px] py-4">
          <span className="text-[13px] font-semibold">Questionnaire</span>
          <span className="text-sm">Needs its own scope in the consent</span>
        </div>
      </section>

      {health.data && !showQueue ? (
        <Card className="p-5 text-sm text-ink-3">
          Public data modes hold no merchant consents: their records are public datasets, not merchants of a lender.
        </Card>
      ) : queue.error ? (
        <ErrorCallout error={queue.error} />
      ) : (
        <>
          <section aria-label="Consent summary" className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-3">
            <StatTile label="Valid consent" value={queue.data ? count(valid) : '—'} />
            <StatTile label="No valid consent · scoring blocked" value={queue.data ? count(rows.length - valid) : '—'} />
          </section>

          <section aria-label="Filters" className="flex flex-wrap items-center gap-3">
            <div role="group" aria-label="Consent" className="flex flex-wrap gap-2">
              {(
                [
                  ['all', 'All'],
                  ['valid', 'Valid'],
                  ['none', 'No valid consent'],
                ] as [Filter, string][]
              ).map(([v, label]) => (
                <FilterChip key={v} on={filter === v} onClick={() => setParam('consent', v, 'all')}>
                  {label}
                </FilterChip>
              ))}
            </div>
            <label className="flex min-h-11 min-w-[240px] items-center gap-2 rounded-[10px] border border-control-line bg-card px-3 sm:ml-auto">
              <SearchIcon />
              <span className="sr-only">Search merchant ID</span>
              <input
                type="search"
                placeholder="Search merchant ID"
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
                    <th scope="col" className="px-5 py-3.5 font-semibold">Merchant</th>
                    <th scope="col" className="px-3 py-3.5 font-semibold">Status</th>
                    <th scope="col" className="px-3 py-3.5 font-semibold">Effect</th>
                    <th scope="col" className="px-5 py-3.5">
                      <span className="sr-only">Record</span>
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
                            <div className="text-[13px] text-muted">{[r.district, r.town_tier].filter(Boolean).join(' · ')}</div>
                          </td>
                          <td className="px-3 py-3.5">
                            {r.consent_valid ? (
                              <Chip tone="strong">Valid</Chip>
                            ) : (
                              <Chip className="shadow-[inset_0_0_0_1.5px_#9AA39E]">No valid consent</Chip>
                            )}
                          </td>
                          <td className="px-3 py-3.5 text-[13px] text-muted">
                            {r.consent_valid ? 'Scoring allowed' : 'Scoring blocked'}
                          </td>
                          <td className="px-5 py-3.5 text-right">
                            <button
                              type="button"
                              aria-expanded={isOpen}
                              onClick={() => setOpen(isOpen ? null : r.merchant_id)}
                              className="min-h-10 cursor-pointer rounded-lg border border-button-line bg-card px-3.5 font-sans text-[13px] font-semibold text-lens hover:bg-open-hover"
                            >
                              {isOpen ? 'Hide record' : 'View record'}
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
            {queue.loading && <div className="px-5 py-10 text-center text-sm text-muted">Loading merchants…</div>}
            {queue.data && filtered.length === 0 && (
              <div className="px-5 py-10 text-center text-sm text-muted">No merchants match these filters.</div>
            )}
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-3.5 text-[13px] text-muted">
              <span>
                {count(filtered.length)} of {count(rows.length)} merchants in the review queue
              </span>
              <Pager page={page} pages={pages} onPage={(p) => setParam('page', String(p), '1')} />
            </div>
          </Card>
        </>
      )}

      <p className="m-0 text-[13px] text-muted">
        Consent design follows platform consent in Bangladesh. India’s Account Aggregator, Singapore’s SGFinDex and
        Open Finance PH are design references, not integrations. Opening a record writes an audit entry. There is no
        revoke button here on purpose.
      </p>
    </Page>
  )
}
