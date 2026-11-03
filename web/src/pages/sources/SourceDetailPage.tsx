/**
 * One connection: Overview (status, settings, test, revoke), Mapping and preview (discover
 * the source's fields, map them, see what a sync would do to every row, sync), Merchant
 * matching (link or reject each source merchant; never automatic) and History (every test,
 * discovery and sync, failed ones included). Calls the /sources/{id} endpoints.
 */
import { CheckCircle2, CircleAlert, RefreshCw, Unplug } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'

import { api } from '@/api/client'
import type { MatchOut, SourceDetail, SourceFields, SourceLinkOut, SourcePreview, SourceRunOut } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSubmit } from '@/api/useSubmit'
import { useSession } from '@/app/session-context'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { FilterSegments } from '@/components/Filters'
import { Field, Select, TextInput } from '@/components/form'
import { Notice } from '@/components/Notice'
import { Page, PageHeader } from '@/components/Page'
import { StatusTag } from '@/components/StatusTag'
import { Button } from '@/components/ui/button'
import { count, fmtBdTime, fmtDate, taka } from '@/lib/format'
import { pick, useLang, useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { CONNECTION_STATUS, ERROR_WORDS, FIELD_LABEL, OUTCOME, REASON } from './words'

type Tab = 'overview' | 'mapping' | 'matching' | 'history'

function RunLine({ run }: { run: SourceRunOut }) {
  const t = useT()
  const lang = useLang()
  const ok = run.status === 'ok'
  return (
    <li className="grid gap-1 border-t border-line py-3 first:border-t-0 sm:grid-cols-[150px_100px_minmax(0,1fr)] sm:items-start sm:gap-4">
      <span className="text-[13px] text-muted-2 tabular">{fmtBdTime(run.started_at)}</span>
      <span className="flex items-center gap-1.5 text-[14px] font-semibold text-ink">
        {ok ? <CheckCircle2 size={16} aria-hidden="true" className="text-band-strong" /> : <CircleAlert size={16} aria-hidden="true" className="text-amber" />}
        {run.kind}
      </span>
      <span className="text-[14px] text-body">
        {ok
          ? run.kind === 'sync'
            ? t(
                `${count(run.rows_added)} saved · ${count(run.rows_skipped)} already saved · ${count(run.rows_flagged)} possible duplicates · ${count(run.rows_rejected)} refused · ${count(run.rows_unmatched)} waiting for a match`,
                `${count(run.rows_added)} রাখা · ${count(run.rows_skipped)} আগেই রাখা · ${count(run.rows_flagged)} সম্ভাব্য দ্বৈত · ${count(run.rows_rejected)} বাতিল · ${count(run.rows_unmatched)} মেলানোর অপেক্ষায়`,
              )
            : t('Worked.', 'কাজ করেছে।')
          : `${pick(ERROR_WORDS[run.error_code ?? ''] ?? { en: run.error_message ?? 'Failed.', bn: run.error_message ?? 'ব্যর্থ।' }, lang)} ${t('Nothing from this run was saved.', 'এই চালানো থেকে কিছু রাখা হয়নি।')}`}
        <span className="block text-[12.5px] text-muted-2">{run.actor}</span>
      </span>
    </li>
  )
}

export function SourceDetailPage() {
  const t = useT()
  const lang = useLang()
  const { role } = useSession()
  const { connectionId = '' } = useParams()
  const id = encodeURIComponent(connectionId)
  const detail = useApi<SourceDetail>(`/sources/${id}`, undefined, { noCache: true })
  const links = useApi<SourceLinkOut[]>(`/sources/${id}/matches`, undefined, { noCache: true })
  const [params] = useSearchParams()
  const [tab, setTab] = useState<Tab>(params.get('tab') === 'matching' ? 'matching' : 'overview')
  const [withdraw, setWithdraw] = useState<SourceLinkOut | null>(null)
  const [mapping, setMapping] = useState<Record<string, string | null>>({})
  const [confirmSync, setConfirmSync] = useState(false)
  const [confirmRevoke, setConfirmRevoke] = useState(false)
  const [chosen, setChosen] = useState<Record<string, string>>({})
  const test = useSubmit<SourceRunOut>()
  const discover = useSubmit<SourceFields>()
  const preview = useSubmit<SourcePreview>()
  const sync = useSubmit<SourceRunOut>()
  const match = useSubmit<MatchOut>()
  const revoke = useSubmit<unknown>()
  const staff = ['officer', 'admin', 'org_admin'].includes(role)

  if (detail.error) return <Page><ErrorCallout error={detail.error} /></Page>
  if (!detail.data) return <Page><LoadingState title={t('Loading the connection…', 'সংযোগ আসছে…')} /></Page>
  const d = detail.data
  const revoked = d.status === 'revoked'

  const runDiscover = async () => {
    const fields = await discover.submit(() => api<SourceFields>(`/sources/${id}/discover`, { method: 'POST' }))
    if (fields) setMapping(fields.suggested)
    detail.reload()
  }
  const runPreview = () => preview.submit(() => api<SourcePreview>(`/sources/${id}/preview`, { method: 'POST', json: { mapping } }))
  const runSync = async () => {
    await sync.submit(() => api<SourceRunOut>(`/sources/${id}/sync`, { method: 'POST', json: { mapping } }))
    setConfirmSync(false)
    detail.reload()
    void runPreview()
  }
  const decide = async (externalRef: string, decision: 'confirmed' | 'rejected') => {
    const saved = await match.submit(() =>
      api<MatchOut>(`/sources/${id}/matches`, { method: 'POST', json: { external_ref: externalRef, merchant_id: decision === 'confirmed' ? chosen[externalRef] : null, decision } }),
    )
    if (saved) {
      detail.reload()
      links.reload()
      if (preview.result) void runPreview()
    }
    return saved
  }

  const fields = discover.result
  const rows = preview.result

  return (
    <Page>
      <nav aria-label={t('Breadcrumb', 'পথ')} className="flex items-center gap-2 text-sm text-body">
        <Link to="/app/sources" className="font-medium no-underline">{t('Data sources', 'ডেটার উৎস')}</Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">{d.display_name}</span>
      </nav>
      <PageHeader
        title={d.display_name}
        description={`${d.connector_name} · ${t(`added ${fmtDate(d.created_at)} by ${d.created_by}`, `যোগ ${fmtDate(d.created_at)}, ${d.created_by}`)}`}
        aside={<StatusTag status={CONNECTION_STATUS[d.status]} className="text-[13px]" />}
      />
      {d.status === 'error' && d.last_error && (
        <Notice tone="warning" title={t('The last run failed', 'শেষ চালানো ব্যর্থ')}>
          {d.last_error} {t('Nothing from it was saved. Fix the cause, then test or sync again.', 'তা থেকে কিছু রাখা হয়নি। কারণ ঠিক করে আবার পরীক্ষা বা সিঙ্ক করুন।')}
        </Notice>
      )}

      <FilterSegments<Tab>
        label={t('View', 'দৃশ্য')}
        value={tab}
        onChange={setTab}
        options={[
          { value: 'overview', label: t('Overview', 'সারসংক্ষেপ') },
          { value: 'mapping', label: t('Mapping and preview', 'ম্যাপিং ও প্রিভিউ') },
          { value: 'matching', label: t('Merchant matching', 'মার্চেন্ট মেলানো') },
          { value: 'history', label: t(`History (${d.runs.length})`, `ইতিহাস (${d.runs.length})`) },
        ]}
      />

      {tab === 'overview' && (
        <section className="route-enter grid gap-5 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
          <div className="flex flex-col gap-1 rounded-card border border-card-line bg-card p-5">
            <h2 className="m-0 pb-2 text-[17px] font-semibold">{t('Configuration', 'কনফিগারেশন')}</h2>
            <dl className="m-0">
              {Object.entries(d.settings).map(([k, v]) => (
                <div key={k} className="grid grid-cols-[180px_minmax(0,1fr)] gap-3 border-t border-line py-2.5 first:border-t-0">
                  <dt className="text-sm text-muted-2">{k.replaceAll('_', ' ')}</dt>
                  <dd className="m-0 text-[15px] text-ink">{v.replaceAll('_', ' ')}</dd>
                </div>
              ))}
              <div className="grid grid-cols-[180px_minmax(0,1fr)] gap-3 border-t border-line py-2.5">
                <dt className="text-sm text-muted-2">{t('Credential', 'ক্রেডেনশিয়াল')}</dt>
                <dd className="m-0 text-[15px] text-ink">{d.secret_ref_set ? t('Reference set (the value is never shown)', 'রেফারেন্স সেট (মান কখনো দেখানো হয় না)') : t('None', 'নেই')}</dd>
              </div>
              <div className="grid grid-cols-[180px_minmax(0,1fr)] gap-3 border-t border-line py-2.5">
                <dt className="text-sm text-muted-2">{t('Linked merchants', 'যুক্ত মার্চেন্ট')}</dt>
                <dd className="m-0 text-[15px] text-ink tabular">{count(d.linked_merchants)}</dd>
              </div>
            </dl>
          </div>
          <div className="flex flex-col gap-3 rounded-card border border-card-line bg-card p-5">
            <h2 className="m-0 text-[17px] font-semibold">{t('Health', 'অবস্থা')}</h2>
            <span className="text-[14px] text-body">
              {d.last_tested_at ? t(`Last successful test ${fmtBdTime(d.last_tested_at)}.`, `শেষ সফল পরীক্ষা ${fmtBdTime(d.last_tested_at)}।`) : t('Not tested yet.', 'এখনও পরীক্ষা হয়নি।')}
            </span>
            {test.result && (
              <span className={cn('text-[14px] font-semibold', test.result.status === 'ok' ? 'text-lens-dark' : 'text-amber-text')}>
                {test.result.status === 'ok' ? t('The connection works.', 'সংযোগ কাজ করছে।') : pick(ERROR_WORDS[test.result.error_code ?? ''] ?? { en: test.result.error_message ?? '', bn: test.result.error_message ?? '' }, lang)}
              </span>
            )}
            {test.error && <ErrorCallout error={test.error} />}
            {role === 'credit_officer' && !revoked && (
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" disabled={test.pending} onClick={() => { void test.submit(() => api<SourceRunOut>(`/sources/${id}/test`, { method: 'POST' })).then(() => detail.reload()) }}>
                  <RefreshCw size={16} aria-hidden="true" />
                  {test.pending ? t('Testing…', 'পরীক্ষা হচ্ছে…') : t('Test the connection', 'সংযোগ পরীক্ষা করুন')}
                </Button>
                <Button variant="outline" onClick={() => setConfirmRevoke(true)}>
                  <Unplug size={16} aria-hidden="true" />
                  {t('Revoke', 'প্রত্যাহার')}
                </Button>
              </div>
            )}
            {revoked && <span className="text-[14px] text-body">{t(`Revoked ${fmtBdTime(d.revoked_at)}. It can no longer be tested or synced; records it saved keep their origin.`, `প্রত্যাহার ${fmtBdTime(d.revoked_at)}। আর পরীক্ষা বা সিঙ্ক করা যায় না; রাখা রেকর্ডের উৎস থেকে যায়।`)}</span>}
          </div>
        </section>
      )}

      {tab === 'mapping' && (
        <section className="route-enter flex flex-col gap-4">
          {!staff || revoked ? (
            <Notice tone="info" title={revoked ? t('This connection is revoked', 'এই সংযোগ প্রত্যাহার করা') : t('Read-only role', 'শুধু দেখার ভূমিকা')}>
              {revoked ? t('Add a new connection to read the source again.', 'আবার পড়তে নতুন সংযোগ যোগ করুন।') : t('Officers and administrators map and sync sources.', 'কর্মকর্তা ও অ্যাডমিন উৎস ম্যাপ ও সিঙ্ক করেন।')}
            </Notice>
          ) : (
            <>
              <div className="flex flex-col gap-4 rounded-card border border-card-line bg-card p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <span className="flex flex-col">
                    <span className="text-[16px] font-semibold text-ink">{t('1 · Map the source’s fields', '১ · উৎসের ফিল্ড মেলান')}</span>
                    <span className="text-[13.5px] text-body">{t('Read the field names from the source; suggestions are filled in for you to check.', 'উৎস থেকে ফিল্ডের নাম পড়ুন; যাচাইয়ের জন্য প্রস্তাব বসানো থাকবে।')}</span>
                  </span>
                  <Button variant="outline" disabled={discover.pending} onClick={() => void runDiscover()}>
                    {discover.pending ? t('Reading…', 'পড়া হচ্ছে…') : fields ? t('Read again', 'আবার পড়ুন') : t('Read the fields', 'ফিল্ড পড়ুন')}
                  </Button>
                </div>
                {discover.error && <ErrorCallout error={discover.error} />}
                {fields && (
                  <div className="grid gap-4 sm:grid-cols-2">
                    {fields.canonical.map((f) => (
                      <Field key={f} label={pick(FIELD_LABEL[f] ?? { en: f, bn: f }, lang)} required={fields.required.includes(f)}>
                        <Select
                          value={mapping[f] ?? ''}
                          onChange={(e) => setMapping({ ...mapping, [f]: e.target.value || null })}
                          options={[{ value: '', label: t('Not sent by this source', 'এই উৎস পাঠায় না') }, ...fields.fields.map((x) => ({ value: x, label: x }))]}
                        />
                      </Field>
                    ))}
                  </div>
                )}
              </div>
              {fields && (
                <div className="flex flex-col gap-4 rounded-card border border-card-line bg-card p-5">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <span className="flex flex-col">
                      <span className="text-[16px] font-semibold text-ink">{t('2 · Preview every row', '২ · প্রতিটি সারি দেখুন')}</span>
                      <span className="text-[13.5px] text-body">{t('Nothing is saved until you sync.', 'সিঙ্ক না করা পর্যন্ত কিছু রাখা হয় না।')}</span>
                    </span>
                    <div className="flex flex-wrap gap-2">
                      <Button variant="outline" disabled={preview.pending} onClick={() => void runPreview()}>{preview.pending ? t('Checking…', 'দেখা হচ্ছে…') : t('Preview', 'প্রিভিউ')}</Button>
                      <Button disabled={!rows || rows.counts.add === 0 || sync.pending} onClick={() => setConfirmSync(true)}>
                        {t(`Sync ${count(rows?.counts.add ?? 0)} records`, `${count(rows?.counts.add ?? 0)}টি রেকর্ড সিঙ্ক করুন`)}
                      </Button>
                    </div>
                  </div>
                  {preview.error && <ErrorCallout error={preview.error} />}
                  {sync.result && (
                    <Notice tone={sync.result.status === 'ok' ? 'success' : 'warning'} title={sync.result.status === 'ok' ? t(`${count(sync.result.rows_added)} records saved`, `${count(sync.result.rows_added)}টি রেকর্ড রাখা হয়েছে`) : t('The sync failed', 'সিঙ্ক ব্যর্থ')}>
                      {sync.result.status === 'ok'
                        ? t('Each saved record keeps this source, the source’s own reference and a fingerprint of the row as received.', 'প্রতিটি রাখা রেকর্ডে এই উৎস, উৎসের নিজস্ব রেফারেন্স ও পাওয়া সারির ছাপ থাকে।')
                        : `${pick(ERROR_WORDS[sync.result.error_code ?? ''] ?? { en: sync.result.error_message ?? '', bn: sync.result.error_message ?? '' }, lang)} ${t('Nothing was saved.', 'কিছু রাখা হয়নি।')}`}
                    </Notice>
                  )}
                  {rows && (
                    <>
                      <dl className="m-0 grid grid-cols-2 gap-2 sm:grid-cols-5">
                        {(['add', 'skip', 'flag', 'reject', 'unmatched'] as const).map((k) => (
                          <div key={k} className="rounded-[10px] border border-line bg-ground px-3 py-2">
                            <dt className="text-[12px] text-muted-2">{pick(OUTCOME[k], lang)}</dt>
                            <dd className="m-0 font-display text-xl font-bold tabular text-ink">{count(rows.counts[k])}</dd>
                          </div>
                        ))}
                      </dl>
                      <div className="overflow-x-auto rounded-[12px] border border-line">
                        <table className="w-full min-w-[640px] border-collapse text-left text-[13.5px]">
                          <thead className="bg-ground text-[12px] text-muted-2">
                            <tr>
                              <th className="px-3 py-2 font-medium">{t('Reference', 'রেফারেন্স')}</th>
                              <th className="px-3 py-2 font-medium">{t('Record', 'রেকর্ড')}</th>
                              <th className="px-3 py-2 text-right font-medium">{t('Amount', 'অঙ্ক')}</th>
                              <th className="px-3 py-2 font-medium">{t('Outcome', 'ফলাফল')}</th>
                            </tr>
                          </thead>
                          <tbody>
                            {rows.rows.map((r) => (
                              <tr key={r.index} className="border-t border-line align-top">
                                <td className="px-3 py-2 font-mono text-[12.5px]">{r.source_reference ?? '—'}<div className="font-sans text-muted-2">{r.external_ref}</div></td>
                                <td className="px-3 py-2">{r.kind ?? '—'} · {r.business_date ? fmtDate(r.business_date) : '—'}{r.delivery_status && <span className="text-body"> · {r.delivery_status}</span>}</td>
                                <td className="px-3 py-2 text-right tabular">{r.amount != null ? taka(r.amount) : '—'}</td>
                                <td className="px-3 py-2">
                                  <StatusTag status={OUTCOME[r.outcome]} />
                                  <div className="pt-1 text-[12.5px] text-body">{pick(REASON[r.code] ?? { en: r.code, bn: r.code }, lang)}</div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      {rows.unmatched.length > 0 && (
                        <button type="button" onClick={() => setTab('matching')} className="self-start cursor-pointer border-0 bg-transparent p-0 font-sans text-[14px] font-semibold text-lens-dark underline">
                          {t(`${rows.unmatched.length} source merchants need a match`, `${rows.unmatched.length}টি উৎস-মার্চেন্ট মেলানো দরকার`)}
                        </button>
                      )}
                    </>
                  )}
                </div>
              )}
            </>
          )}
        </section>
      )}

      {tab === 'matching' && (
        <section className="route-enter flex flex-col gap-3">
          <Notice tone="info" title={t('A person decides every match', 'প্রতিটি মিল মানুষ ঠিক করেন')}>
            {t('A suggestion means the name and district look alike, not that it is the same shop. Records are saved only for confirmed matches; a decision can be changed later and the history is kept.', 'প্রস্তাব মানে নাম ও জেলা মিল দেখায়, একই দোকান নয়। শুধু নিশ্চিত মিলের রেকর্ড রাখা হয়; সিদ্ধান্ত পরে বদলানো যায় আর ইতিহাস থাকে।')}
          </Notice>
          {!rows ? (
            <p className="m-0 text-[15px] text-body">{t('Preview the source first (Mapping and preview) to see which merchants need a match.', 'কোন মার্চেন্ট মেলাতে হবে দেখতে আগে উৎস প্রিভিউ করুন (ম্যাপিং ও প্রিভিউ)।')}</p>
          ) : rows.unmatched.length === 0 ? (
            <p className="m-0 text-[15px] text-body">{t('Every source merchant in this read is matched.', 'এই পাঠের প্রতিটি উৎস-মার্চেন্ট মেলানো।')}</p>
          ) : (
            <ul className="m-0 flex list-none flex-col gap-3 p-0">
              {rows.unmatched.map((u) => (
                <li key={u.external_ref} className="grid gap-4 rounded-card border border-card-line bg-card p-4 sm:p-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
                  <div className="flex flex-col gap-1">
                    <span className="text-[12px] font-semibold tracking-[0.06em] text-muted-2 uppercase">{t('In the source', 'উৎসে')}</span>
                    <span className="text-[16px] font-semibold text-ink">{u.merchant_name ?? u.external_ref}</span>
                    <span className="text-[13.5px] text-body"><span className="font-mono">{u.external_ref}</span>{u.district && ` · ${u.district}`} · {t(`${u.rows} rows waiting`, `${u.rows}টি সারি অপেক্ষায়`)}</span>
                    {u.decision === 'rejected' && <span className="text-[13px] font-semibold text-amber-text">{t('A match was rejected earlier.', 'আগে একটি মিল বাতিল করা হয়েছিল।')}</span>}
                  </div>
                  {staff ? (
                    <div className="flex flex-col gap-3">
                      <Field label={t('CredLens merchant', 'CredLens মার্চেন্ট')} hint={u.candidates.length ? t('Suggested by name and district.', 'নাম ও জেলা দেখে প্রস্তাবিত।') : t('No look-alike shop found. Type a CredLens id if you know it.', 'মিল দেখায় এমন দোকান নেই। জানা থাকলে CredLens আইডি লিখুন।')}>
                        {u.candidates.length ? (
                          <Select value={chosen[u.external_ref] ?? ''} onChange={(e) => setChosen({ ...chosen, [u.external_ref]: e.target.value })} placeholder={t('Choose a merchant', 'একটি মার্চেন্ট বেছে নিন')} options={u.candidates.map((c) => ({ value: c.merchant_id, label: `${c.shop_name ?? c.merchant_id} · ${c.merchant_id}${c.area ? ` · ${c.area}` : ''}` }))} />
                        ) : (
                          <TextInput value={chosen[u.external_ref] ?? ''} onChange={(e) => setChosen({ ...chosen, [u.external_ref]: e.target.value.trim().toUpperCase() })} placeholder="CL-M-000001" />
                        )}
                      </Field>
                      <div className="flex flex-wrap gap-2">
                        <Button size="sm" disabled={!chosen[u.external_ref] || match.pending} onClick={() => void decide(u.external_ref, 'confirmed')}>{t('Confirm this match', 'এই মিল নিশ্চিত করুন')}</Button>
                        <Button size="sm" variant="outline" disabled={match.pending} onClick={() => void decide(u.external_ref, 'rejected')}>{t('Not the same shop', 'একই দোকান নয়')}</Button>
                      </div>
                    </div>
                  ) : (
                    <span className="text-[14px] text-body">{t('Officers and administrators decide matches.', 'কর্মকর্তা ও অ্যাডমিন মিল ঠিক করেন।')}</span>
                  )}
                </li>
              ))}
            </ul>
          )}
          {match.error && <ErrorCallout error={match.error} />}
          <h2 className="m-0 mt-3 text-[18px] font-semibold">{t('Match decisions', 'মিলের সিদ্ধান্ত')}</h2>
          {links.error ? (
            <ErrorCallout error={links.error} />
          ) : !links.data ? (
            <LoadingState title={t('Loading decisions…', 'সিদ্ধান্ত আসছে…')} />
          ) : links.data.length === 0 ? (
            <p className="m-0 text-[15px] text-body">{t('No match has been decided yet.', 'এখনও কোনো মিল ঠিক হয়নি।')}</p>
          ) : (
            <ul className="m-0 flex list-none flex-col overflow-hidden rounded-card border border-card-line bg-card p-0">
              {links.data.map((l) => (
                <li key={l.id} className={cn('grid gap-2 border-t border-line px-4 py-3 first:border-t-0 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)_auto] sm:items-center', !l.current && 'bg-ground/60')}>
                  <span className="flex flex-col">
                    <span className="font-mono text-[14px] text-ink">{l.external_ref}</span>
                    <span className="text-[12.5px] text-muted-2">{fmtBdTime(l.decided_at)} · {l.decided_by}</span>
                  </span>
                  <span className="text-[14px] text-body">
                    {l.decision === 'confirmed' ? (
                      <>
                        {t('Linked to ', 'যুক্ত: ')}
                        <Link to={`/app/merchants/${encodeURIComponent(l.merchant_id ?? '')}`} className="font-semibold no-underline">{l.shop_name ?? l.merchant_id}</Link>
                        <span className="text-muted-2"> · {l.merchant_id}</span>
                        {l.records_saved > 0 && <span className="block text-[13px] text-muted-2">{t(`${count(l.records_saved)} records saved from this source`, `এই উৎস থেকে ${count(l.records_saved)}টি রেকর্ড রাখা`)}</span>}
                      </>
                    ) : (
                      t('Not the same shop (rejected)', 'একই দোকান নয় (বাতিল)')
                    )}
                    {!l.current && <span className="block text-[12.5px] font-semibold text-muted-2">{t('Replaced by a later decision', 'পরের সিদ্ধান্তে বদলানো')}</span>}
                  </span>
                  {staff && !revoked && l.current && l.decision === 'confirmed' ? (
                    <Button size="sm" variant="outline" onClick={() => setWithdraw(l)}>{t('Withdraw link', 'সংযোগ তুলে নিন')}</Button>
                  ) : (
                    <span aria-hidden="true" />
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {tab === 'history' && (
        <section className="route-enter rounded-card border border-card-line bg-card px-4 py-1 sm:px-5">
          {d.runs.length === 0 ? <p className="py-3 text-[15px] text-body">{t('Nothing has run yet.', 'এখনও কিছু চালানো হয়নি।')}</p> : <ol className="m-0 list-none p-0">{d.runs.map((r) => <RunLine key={r.run_id} run={r} />)}</ol>}
        </section>
      )}

      <ConfirmDialog
        open={confirmSync}
        onOpenChange={setConfirmSync}
        title={t(`Save ${count(rows?.counts.add ?? 0)} records from this source?`, `এই উৎস থেকে ${count(rows?.counts.add ?? 0)}টি রেকর্ড রাখবেন?`)}
        confirmLabel={t('Sync', 'সিঙ্ক')}
        onConfirm={() => void runSync()}
        pending={sync.pending}
      >
        {t('The source is read again and every row is checked again before saving. Rows of unmatched merchants are not saved.', 'রাখার আগে উৎস আবার পড়া ও প্রতিটি সারি আবার যাচাই হয়। না-মেলা মার্চেন্টের সারি রাখা হয় না।')}
      </ConfirmDialog>
      <ConfirmDialog
        open={withdraw !== null}
        onOpenChange={(open) => !open && setWithdraw(null)}
        title={t('Withdraw this match?', 'এই মিল তুলে নেবেন?')}
        confirmLabel={t('Withdraw link', 'সংযোগ তুলে নিন')}
        onConfirm={() => { if (withdraw) void decide(withdraw.external_ref, 'rejected').then(() => setWithdraw(null)) }}
        pending={match.pending}
      >
        {t(
          `${withdraw?.external_ref ?? ''} will no longer be linked to ${withdraw?.shop_name ?? withdraw?.merchant_id ?? ''}, and later syncs save nothing for it. Records already saved are not deleted: they appear under Data quality for a person to review.`,
          `${withdraw?.external_ref ?? ''} আর ${withdraw?.shop_name ?? withdraw?.merchant_id ?? ''}-এর সাথে যুক্ত থাকবে না, পরের সিঙ্কে এর কিছু রাখা হবে না। আগে রাখা রেকর্ড মোছা হয় না: সেগুলো ডেটার মানে পর্যালোচনার জন্য দেখায়।`,
        )}
      </ConfirmDialog>
      <ConfirmDialog
        open={confirmRevoke}
        onOpenChange={setConfirmRevoke}
        title={t('Revoke this connection?', 'এই সংযোগ প্রত্যাহার করবেন?')}
        confirmLabel={t('Revoke', 'প্রত্যাহার')}
        onConfirm={() => { void revoke.submit(() => api(`/sources/${id}/revoke`, { method: 'POST' })).then(() => { setConfirmRevoke(false); detail.reload() }) }}
        pending={revoke.pending}
      >
        {t('It can no longer be tested, read or synced, and its credential reference is cleared. Records it saved stay, with their origin.', 'এটি আর পরীক্ষা, পড়া বা সিঙ্ক করা যাবে না, আর ক্রেডেনশিয়ালের রেফারেন্স মুছে যাবে। রাখা রেকর্ড উৎসসহ থেকে যায়।')}
      </ConfirmDialog>
    </Page>
  )
}
