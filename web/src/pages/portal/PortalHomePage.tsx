/**
 * The merchant's own page: what the lender has recorded about their shop, as clear tables.
 *
 * Each published receipt is shown with its lines. The merchant can say "Looks right" for a whole
 * receipt, or report one line as wrong with the correct amount and a photo of their own copy.
 * A reported line is marked and waits for the lender's answer. A merchant sees only their own
 * shop and never a score.
 */
import { CheckCircle2, Flag, Printer } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

import { api, ApiError } from '@/api/client'
import type { PortalLine, PortalMe, PortalReceipt } from '@/api/types'
import { useApi } from '@/api/useApi'
import { EmptyState, ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { Page, PageHeader } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { fmtDate, taka } from '@/lib/format'
import { pick, useLang, useT } from '@/lib/i18n'
import { KIND_WORDS, OUTCOME_WORDS } from '../desk/words'

const STATE = {
  checked: { en: 'Checked', bn: 'যাচাই করা', cls: 'bg-strong-chip text-lens-dark' },
  reported: { en: 'You reported this', bn: 'আপনি জানিয়েছেন', cls: 'bg-amber-chip text-amber-text' },
  corrected: { en: 'Corrected', bn: 'ঠিক করা হয়েছে', cls: 'bg-info-panel text-[#245C93]' },
  kept: { en: 'Kept as recorded', bn: 'আগের মতোই', cls: 'bg-neutral-chip text-neutral-text' },
} as const

function ReportForm({ line, onDone }: { line: PortalLine; onDone: () => void }) {
  const t = useT()
  const [note, setNote] = useState('')
  const [amount, setAmount] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const send = async () => {
    setBusy(true)
    setError(null)
    try {
      let proof: string | null = null
      if (file) {
        const up = await api<{ document_id: string }>('/portal/proof', { method: 'POST', query: { name: file.name }, body: { content: file, contentType: 'application/octet-stream' } })
        proof = up.document_id
      }
      await api(`/portal/lines/${encodeURIComponent(line.line_id)}/report`, {
        method: 'POST',
        json: { note, claimed_amount_bdt: amount === '' ? null : Number(amount), proof_document_id: proof },
      })
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }
  const box = 'min-h-12 w-full rounded-[10px] border border-control-line px-3 font-sans text-[15px]'
  return (
    <div className="flex flex-col gap-3 rounded-[12px] border border-amber-chip bg-amber-panel p-4">
      <label className="flex flex-col gap-1 text-[14px] font-semibold text-ink">
        {t('What is wrong?', 'কী ভুল?')}
        <input className={box} value={note} onChange={(e) => setNote(e.target.value)} placeholder={t('For example: my copy says a different amount', 'যেমন: আমার কপিতে অন্য টাকা লেখা')} />
      </label>
      <label className="flex flex-col gap-1 text-[14px] font-semibold text-ink">
        {t('What should the amount be? (BDT)', 'সঠিক টাকা কত? (টাকা)')}
        <input className={box} inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
      </label>
      <label className="flex flex-col gap-1 text-[14px] font-semibold text-ink">
        {t('A photo of your own copy (recommended)', 'আপনার নিজের কপির ছবি (ভালো হয়)')}
        <input type="file" accept="image/png,image/jpeg,application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </label>
      {error && <p role="alert" className="m-0 text-[14px] text-error">{error}</p>}
      <div>
        <Button size="lg" disabled={busy || note.trim().length < 5} onClick={() => void send()}>
          <Flag size={19} aria-hidden="true" />
          {busy ? t('Sending…', 'পাঠানো হচ্ছে…') : t('Send the report', 'অভিযোগ পাঠান')}
        </Button>
      </div>
    </div>
  )
}

export function PortalHomePage() {
  const t = useT()
  const lang = useLang()
  const me = useApi<PortalMe>('/portal/me', undefined, { noCache: true })
  const records = useApi<PortalReceipt[]>('/portal/records', undefined, { noCache: true })
  const [open, setOpen] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const confirm = async (id: string) => {
    try {
      await api(`/portal/receipts/${encodeURIComponent(id)}/confirm`, { method: 'POST' })
      records.reload()
      me.reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err))
    }
  }

  return (
    <Page>
      <PageHeader
        title={me.data?.shop_name ? `${t('Hello', 'নমস্কার')}, ${me.data.shop_name}` : t('My records', 'আমার হিসাব')}
        description={t(
          'This is what your lender has written down about your shop. If a number does not match your own copy, report it and we will check.',
          'আপনার ঋণদাতা আপনার দোকান সম্পর্কে যা লিখে রেখেছে তা এখানে। কোনো সংখ্যা আপনার কপির সাথে না মিললে জানান, আমরা যাচাই করব।',
        )}
      />
      {me.data && (
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-card border border-card-line bg-card p-4">
            <div className="text-[13.5px] text-muted-2">{t('Receipts checked', 'যাচাই করা রসিদ')}</div>
            <div className="text-[28px] font-semibold text-ink">{me.data.receipts_published}</div>
          </div>
          <div className="rounded-card border border-card-line bg-card p-4">
            <div className="text-[13.5px] text-muted-2">{t('Your reports waiting', 'আপনার অপেক্ষমাণ অভিযোগ')}</div>
            <div className="text-[28px] font-semibold text-ink">{me.data.reports_open}</div>
          </div>
          <Link to="/app/portal/apply" className="flex flex-col justify-center rounded-card border border-lens bg-strong-chip p-4 text-lens-dark no-underline transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md motion-reduce:transition-none">
            <span className="text-[17px] font-semibold">{me.data.has_application ? t('See your loan application', 'আপনার ঋণের আবেদন দেখুন') : t('Apply for a loan', 'ঋণের জন্য আবেদন করুন')} →</span>
          </Link>
        </div>
      )}
      {error && <p role="alert" className="m-0 rounded-[10px] bg-error-panel px-4 py-3 text-[14.5px] text-error">{error}</p>}
      {records.error ? (
        <ErrorCallout error={records.error} />
      ) : !records.data ? (
        <LoadingState title={t('Loading your records…', 'আপনার হিসাব আসছে…')} />
      ) : records.data.length === 0 ? (
        <EmptyState title={t('Nothing here yet', 'এখনও কিছু নেই')} text={t('Your lender’s Records Desk is checking your receipts. They will appear here once they are checked.', 'ঋণদাতার রেকর্ড ডেস্ক আপনার রসিদ যাচাই করছে। যাচাই হলে এখানে দেখা যাবে।')} />
      ) : (
        <ul className="m-0 flex list-none flex-col gap-5 p-0">
          {records.data.map((r) => (
            <li key={r.receipt_id} className="flex flex-col gap-3 rounded-card border border-card-line bg-card p-4 sm:p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex flex-col">
                  <span className="text-[17px] font-semibold text-ink">
                    {pick(KIND_WORDS[r.kind], lang)}
                    {r.supplier ? ` · ${r.supplier}` : ''}
                  </span>
                  <span className="text-[13.5px] text-muted-2">
                    {r.receipt_date ? fmtDate(r.receipt_date) : ''}
                    {r.memo_no ? ` · ${t('memo', 'মেমো')} ${r.memo_no}` : ''}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {r.confirmed ? (
                    <span className="inline-flex items-center gap-1.5 text-[14px] font-semibold text-lens-dark"><CheckCircle2 size={18} aria-hidden="true" />{t('You said it looks right', 'আপনি বলেছেন ঠিক আছে')}</span>
                  ) : (
                    <Button variant="outline" onClick={() => void confirm(r.receipt_id)}>
                      <CheckCircle2 size={19} aria-hidden="true" />
                      {t('This looks right', 'ঠিক আছে')}
                    </Button>
                  )}
                  <Button variant="ghost" onClick={() => window.print()} aria-label={t('Print', 'ছাপুন')}>
                    <Printer size={19} aria-hidden="true" />
                  </Button>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[520px] border-collapse text-[15px]">
                  <thead>
                    <tr className="text-left text-[13px] text-muted-2">
                      {r.kind === 'purchase' ? (
                        <>
                          <th className="border-b border-line px-2 py-2">{t('Item', 'পণ্য')}</th>
                          <th className="border-b border-line px-2 py-2 text-right">{t('Qty', 'পরিমাণ')}</th>
                          <th className="border-b border-line px-2 py-2 text-right">{t('Rate', 'দর')}</th>
                          <th className="border-b border-line px-2 py-2 text-right">{t('Amount', 'টাকা')}</th>
                        </>
                      ) : (
                        <>
                          <th className="border-b border-line px-2 py-2">{t('Date', 'তারিখ')}</th>
                          <th className="border-b border-line px-2 py-2">{r.kind === 'delivery' ? t('Result', 'ফলাফল') : t('Loan', 'ঋণ')}</th>
                          <th className="border-b border-line px-2 py-2 text-right">{t('Amount', 'টাকা')}</th>
                        </>
                      )}
                      <th className="border-b border-line px-2 py-2">{t('State', 'অবস্থা')}</th>
                      <th className="border-b border-line px-2 py-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {r.lines.map((ln) => {
                      const state = STATE[ln.shown_state as keyof typeof STATE] ?? STATE.checked
                      return (
                        <tr key={ln.line_id} className="align-top">
                          {r.kind === 'purchase' ? (
                            <>
                              <td className="border-b border-line px-2 py-3">{ln.item}</td>
                              <td className="border-b border-line px-2 py-3 text-right">{ln.quantity}{ln.unit ? ` ${ln.unit}` : ''}</td>
                              <td className="border-b border-line px-2 py-3 text-right">{ln.unit_price == null ? '' : taka(ln.unit_price)}</td>
                            </>
                          ) : (
                            <>
                              <td className="border-b border-line px-2 py-3">{ln.line_date ? fmtDate(ln.line_date) : ''}</td>
                              <td className="border-b border-line px-2 py-3">{ln.outcome ? pick(OUTCOME_WORDS[ln.outcome] ?? { en: ln.outcome, bn: ln.outcome }, lang) : ln.reference}</td>
                            </>
                          )}
                          <td className="border-b border-line px-2 py-3 text-right font-semibold">{ln.amount_bdt == null ? '' : taka(ln.amount_bdt)}</td>
                          <td className="border-b border-line px-2 py-3">
                            <span className={`rounded-md px-2 py-0.5 text-[13px] font-semibold ${state.cls}`}>{pick(state, lang)}</span>
                            {ln.answer && <div className="mt-1 text-[13px] text-muted-2">{ln.answer}</div>}
                          </td>
                          <td className="border-b border-line px-2 py-2 text-right">
                            {ln.shown_state !== 'reported' && (
                              <Button size="sm" variant="ghost" onClick={() => setOpen(open === ln.line_id ? null : ln.line_id)}>
                                {t('Wrong?', 'ভুল?')}
                              </Button>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                  <tfoot>
                    <tr>
                      <td colSpan={r.kind === 'purchase' ? 3 : 2} className="px-2 py-3 text-right text-[14px] text-muted-2">{t('Lines add up to', 'লাইনগুলোর যোগফল')}</td>
                      <td className="px-2 py-3 text-right text-[16px] font-semibold">{taka(r.lines_total)}</td>
                      <td colSpan={2} />
                    </tr>
                  </tfoot>
                </table>
              </div>
              {r.lines.filter((ln) => ln.line_id === open).map((ln) => (
                <ReportForm key={ln.line_id} line={ln} onDone={() => { setOpen(null); records.reload(); me.reload() }} />
              ))}
            </li>
          ))}
        </ul>
      )}
    </Page>
  )
}
