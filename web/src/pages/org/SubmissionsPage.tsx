/**
 * The Credit Officer's view of what comes in each day (GET /submissions): every shop's daily
 * sheet, who sent it, the totals, and what is still a draft. Open a sheet to read its rows, then
 * accept it or return it to the FSR with a reason. Nothing here changes a score by itself.
 */
import { useState } from 'react'
import { Link } from 'react-router'

import { api } from '@/api/client'
import type { DailyDayOut, SubmissionOut } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSession } from '@/app/session-context'
import { useSubmit } from '@/api/useSubmit'
import { EmptyState, ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { Page, PageHeader } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { fmtDate, fmtBdTime, taka } from '@/lib/format'
import { useT } from '@/lib/i18n'

const STATUSES = ['', 'submitted', 'returned', 'accepted', 'draft']

export function SubmissionsPage() {
  const t = useT()
  const { role } = useSession()
  const [status, setStatus] = useState('submitted')
  const list = useApi<SubmissionOut[]>('/submissions', { status: status || undefined }, { noCache: true })
  const [openKey, setOpenKey] = useState<string | null>(null)
  const [reason, setReason] = useState('')
  const act = useSubmit<DailyDayOut>()

  const day = useApi<DailyDayOut>(
    openKey ? `/merchants/${encodeURIComponent(openKey.split('|')[0])}/daily/${openKey.split('|')[1]}` : null,
    undefined,
    { noCache: true },
  )
  const move = async (s: SubmissionOut, what: 'accept' | 'return') => {
    const done = await act.submit(() =>
      api<DailyDayOut>(`/merchants/${encodeURIComponent(s.merchant_id)}/daily/${s.business_date}/${what}`, {
        method: 'POST',
        json: what === 'return' ? { reason } : {},
      }),
    )
    if (done) {
      setReason('')
      setOpenKey(null)
      list.reload()
    }
  }

  return (
    <Page>
      <PageHeader
        title={t('Daily submissions', 'দৈনিক জমা')}
        description={t(
          'What the field representatives send each day. Accept a sheet, or return it with a reason if something looks wrong.',
          'মাঠ প্রতিনিধিরা প্রতিদিন যা পাঠান। শীট গ্রহণ করুন, কিছু ভুল মনে হলে কারণসহ ফেরত দিন।',
        )}
      />
      <label className="flex items-center gap-2 text-[14px] text-body">
        {t('Show', 'দেখান')}
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="min-h-10 rounded-[10px] border border-control-line bg-white px-2.5 text-[14px] text-ink">
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s || t('All', 'সব')}
            </option>
          ))}
        </select>
      </label>
      {act.error && <ErrorCallout error={act.error} />}
      {list.error ? (
        <ErrorCallout error={list.error} />
      ) : !list.data ? (
        <LoadingState title={t('Loading…', 'আসছে…')} />
      ) : list.data.length === 0 ? (
        <EmptyState title={t('Nothing here', 'এখানে কিছু নেই')} text={t('Sheets appear when a representative sends them.', 'প্রতিনিধি পাঠালে শীট এখানে আসবে।')} />
      ) : (
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {list.data.map((s) => {
            const key = `${s.merchant_id}|${s.business_date}`
            const opened = openKey === key
            return (
              <li key={s.sheet_id} className="rounded-card border border-card-line bg-card p-4 text-[14px] text-body">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span>
                    <Link to={`/app/merchants/${encodeURIComponent(s.merchant_id)}`} className="font-semibold text-ink">
                      {s.shop_name ?? s.merchant_id}
                    </Link>
                    <span className="ml-2 text-muted-2">{fmtDate(s.business_date)} · {s.fsr_name}</span>
                  </span>
                  <span className="rounded-md bg-neutral-chip px-2 py-0.5 text-[13px] font-semibold text-neutral-text">{s.status}</span>
                </div>
                <div className="mt-1 flex flex-wrap gap-x-4 text-[13.5px]">
                  {Object.entries(s.totals).map(([k, v]) => (
                    <span key={k}>
                      {k}: {taka(v)}
                    </span>
                  ))}
                  {s.drafts > 0 && <span className="text-amber-text">{t(`${s.drafts} draft rows`, `${s.drafts}টি খসড়া সারি`)}</span>}
                  {s.submitted_at && <span className="text-muted-2">{fmtBdTime(s.submitted_at)}</span>}
                </div>
                {s.returned_reason && <p className="m-0 mt-1 text-amber-text">{s.returned_reason}</p>}
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <Button size="sm" variant="ghost" onClick={() => setOpenKey(opened ? null : key)}>
                    {opened ? t('Hide rows', 'সারি লুকান') : t('Read rows', 'সারি দেখুন')}
                  </Button>
                  {role === 'credit_officer' && s.status === 'submitted' && (
                    <>
                      <Button size="sm" disabled={act.pending} onClick={() => void move(s, 'accept')}>
                        {t('Accept', 'গ্রহণ')}
                      </Button>
                      <input
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        placeholder={t('Reason to return', 'ফেরতের কারণ')}
                        aria-label={t('Reason to return', 'ফেরতের কারণ')}
                        className="min-h-9 min-w-0 flex-1 rounded-[10px] border border-control-line px-2.5 text-[14px] text-ink"
                      />
                      <Button size="sm" variant="outline" disabled={act.pending || reason.trim().length < 3} onClick={() => void move(s, 'return')}>
                        {t('Return', 'ফেরত')}
                      </Button>
                    </>
                  )}
                </div>
                {opened && (
                  <div className="mt-3 overflow-x-auto">
                    {!day.data ? (
                      <LoadingState title={t('Loading rows…', 'সারি আসছে…')} />
                    ) : (
                      <table className="w-full border-collapse text-[13px]">
                        <thead>
                          <tr className="text-left text-muted-2">
                            {['Kind', 'Date', 'Item', 'Party', 'Amount', 'Status'].map((h) => (
                              <th key={h} className="border-b border-line px-2 py-1">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {day.data.entries.map((e) => (
                            <tr key={e.entry_id} className={e.status === 'superseded' ? 'text-muted-2 line-through' : ''}>
                              <td className="border-b border-line px-2 py-1">{e.entry_type}</td>
                              <td className="border-b border-line px-2 py-1">{e.txn_date}</td>
                              <td className="border-b border-line px-2 py-1">{e.category ?? e.description}</td>
                              <td className="border-b border-line px-2 py-1">{e.counterparty}</td>
                              <td className="border-b border-line px-2 py-1">{e.amount_bdt != null ? taka(e.amount_bdt) : ''}</td>
                              <td className="border-b border-line px-2 py-1">{e.status}{e.amend_reason ? ` (${e.amend_reason})` : ''}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </Page>
  )
}
