/**
 * Mistakes merchants reported on their receipts (GET /merchant-reports): the line, what the
 * merchant says it should be, their note and their photo of their own copy. The Records Officer
 * answers each one: accept (the amount is corrected) or reject (the line stays as it was), with a
 * note the merchant will read. While a report is open the line stays out of the score.
 */
import { FileSearch } from 'lucide-react'
import { useState } from 'react'

import { api, apiBlob, ApiError } from '@/api/client'
import type { ReportOut } from '@/api/types'
import { useApi } from '@/api/useApi'
import { EmptyState, ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { Page, PageHeader } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { fmtBdTime, taka } from '@/lib/format'
import { pick, useLang, useT } from '@/lib/i18n'
import { KIND_WORDS } from './words'

export function ReportsPage() {
  const t = useT()
  const lang = useLang()
  const [filter, setFilter] = useState<'open' | 'all'>('open')
  const list = useApi<ReportOut[]>('/merchant-reports', { status: filter }, { noCache: true })
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [amounts, setAmounts] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const answer = async (r: ReportOut, accept: boolean) => {
    setBusy(true)
    setError(null)
    try {
      await api<ReportOut>(`/merchant-reports/${encodeURIComponent(r.flag_id)}/resolve`, {
        method: 'POST',
        json: { accept, amount_bdt: accept ? Number(amounts[r.flag_id] ?? r.claimed_amount_bdt ?? 0) || null : null, note: notes[r.flag_id] ?? '' },
      })
      list.reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const openProof = async (r: ReportOut) => {
    try {
      const blob = await apiBlob(`/merchant-reports/${encodeURIComponent(r.flag_id)}/proof`)
      window.open(URL.createObjectURL(blob), '_blank', 'noopener')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err))
    }
  }

  return (
    <Page>
      <PageHeader
        title={t('Merchant reports', 'ব্যবসায়ীর অভিযোগ')}
        description={t(
          'A merchant says a line on a published receipt is wrong. Look at their proof, then accept or reject. The line stays out of the score until you answer.',
          'ব্যবসায়ী বলছেন প্রকাশিত রসিদের একটি লাইন ভুল। তাঁর প্রমাণ দেখুন, তারপর গ্রহণ বা বাতিল করুন। উত্তর না দেওয়া পর্যন্ত লাইনটি স্কোর থেকে বাদ থাকে।',
        )}
      />
      <div className="flex gap-2">
        {(['open', 'all'] as const).map((id) => (
          <button key={id} onClick={() => setFilter(id)} className={`min-h-11 cursor-pointer rounded-[11px] border px-4 font-sans text-[14.5px] font-semibold transition-all hover:-translate-y-px ${filter === id ? 'border-lens-dark bg-lens-dark text-white' : 'border-control-line bg-white text-ink-2 hover:border-lens'}`}>
            {id === 'open' ? t('Waiting for an answer', 'উত্তরের অপেক্ষায়') : t('All reports', 'সব অভিযোগ')}
          </button>
        ))}
      </div>
      {error && <p role="alert" className="m-0 rounded-[10px] bg-error-panel px-4 py-3 text-[14.5px] text-error">{error}</p>}
      {list.error ? (
        <ErrorCallout error={list.error} />
      ) : !list.data ? (
        <LoadingState title={t('Loading…', 'আসছে…')} />
      ) : list.data.length === 0 ? (
        <EmptyState title={t('No reports', 'কোনো অভিযোগ নেই')} text={t('Nothing is waiting for you.', 'আপনার জন্য কিছু অপেক্ষা করছে না।')} />
      ) : (
        <ul className="m-0 flex list-none flex-col gap-4 p-0">
          {list.data.map((r) => (
            <li key={r.flag_id} className="flex flex-col gap-3 rounded-card border border-card-line bg-card p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-[17px] font-semibold text-ink">{r.shop_name ?? r.merchant_id}</span>
                <span className="text-[13px] text-muted-2">{fmtBdTime(r.raised_at)}</span>
              </div>
              <p className="m-0 text-[14.5px] text-body">
                {pick(KIND_WORDS[r.receipt_kind], lang)}
                {r.supplier ? ` · ${r.supplier}` : ''} · {t('line', 'লাইন')} {r.line_no}
                {r.item ? ` · ${r.item}` : ''}
              </p>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-[10px] bg-ground p-3">
                  <div className="text-[13px] text-muted-2">{t('We recorded', 'আমরা লিখেছি')}</div>
                  <div className="text-[20px] font-semibold text-ink">{r.recorded_amount_bdt == null ? '—' : taka(r.recorded_amount_bdt)}</div>
                </div>
                <div className="rounded-[10px] bg-amber-panel p-3">
                  <div className="text-[13px] text-amber-text">{t('The merchant says', 'ব্যবসায়ী বলছেন')}</div>
                  <div className="text-[20px] font-semibold text-amber-text">{r.claimed_amount_bdt == null ? '—' : taka(r.claimed_amount_bdt)}</div>
                </div>
              </div>
              <p className="m-0 rounded-[10px] border border-line p-3 text-[15px] text-ink">“{r.note}”</p>
              {r.has_proof && (
                <div>
                  <Button variant="outline" onClick={() => void openProof(r)}>
                    <FileSearch size={19} aria-hidden="true" />
                    {t('Look at the merchant’s photo', 'ব্যবসায়ীর ছবি দেখুন')}
                  </Button>
                </div>
              )}
              {r.status === 'open' ? (
                <div className="flex flex-col gap-3 border-t border-line pt-3">
                  <div className="grid gap-3 sm:grid-cols-[180px_minmax(0,1fr)]">
                    <label className="flex flex-col gap-1 text-[13.5px] font-semibold">
                      {t('Correct amount (if accepted)', 'সঠিক টাকা (গ্রহণ করলে)')}
                      <input className="min-h-11 rounded-[9px] border border-control-line px-2.5 font-sans text-[15px] font-normal" inputMode="decimal" value={amounts[r.flag_id] ?? (r.claimed_amount_bdt ?? '')} onChange={(e) => setAmounts({ ...amounts, [r.flag_id]: e.target.value })} />
                    </label>
                    <label className="flex flex-col gap-1 text-[13.5px] font-semibold">
                      {t('Your answer (the merchant reads this)', 'আপনার উত্তর (ব্যবসায়ী পড়বেন)')}
                      <input className="min-h-11 rounded-[9px] border border-control-line px-2.5 font-sans text-[15px] font-normal" value={notes[r.flag_id] ?? ''} onChange={(e) => setNotes({ ...notes, [r.flag_id]: e.target.value })} />
                    </label>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <Button size="lg" disabled={busy || (notes[r.flag_id] ?? '').trim().length < 3} onClick={() => void answer(r, true)}>
                      {t('Accept and correct the amount', 'গ্রহণ করে টাকা ঠিক করুন')}
                    </Button>
                    <Button size="lg" variant="outline" disabled={busy || (notes[r.flag_id] ?? '').trim().length < 3} onClick={() => void answer(r, false)}>
                      {t('Reject: keep the line as it was', 'বাতিল: লাইন যেমন ছিল থাকুক')}
                    </Button>
                  </div>
                </div>
              ) : (
                <p className="m-0 border-t border-line pt-3 text-[14.5px] text-body">
                  <strong>{r.status === 'accepted' ? t('Accepted', 'গৃহীত') : t('Rejected', 'বাতিল')}</strong> · {r.resolution_note}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </Page>
  )
}
