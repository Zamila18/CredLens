/**
 * One receipt, checked by a Records Officer: the picture on one side, what the reader found as
 * an editable table on the other.
 *
 * Cells the reader was unsure of, and cells whose numbers do not agree (quantity times rate not
 * equal to the amount, lines not adding up to the stated total, an impossible date) are
 * highlighted with a plain-words reason. Nothing reaches the credit officers or the score until
 * the receipt is published (POST /receipts/{id}/publish); a published receipt is also what the
 * merchant sees on their own portal.
 */
import { ArrowLeft, CheckCircle2, Plus, Save, Trash2, TriangleAlert } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router'

import { api, apiBlob, ApiError } from '@/api/client'
import type { ReceiptLineOut, ReceiptOut } from '@/api/types'
import { useApi } from '@/api/useApi'
import { ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { Page, PageHeader } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { taka } from '@/lib/format'
import { pick, useLang, useT } from '@/lib/i18n'
import { KIND_WORDS, OUTCOME_WORDS, STATUS_WORDS, TONES } from './words'

type Row = Record<string, string> & { line_id: string }
type Col = { key: string; en: string; bn: string; type?: 'text' | 'number' | 'date' | 'outcome'; w: string }

const COLUMNS: Record<string, Col[]> = {
  purchase: [
    { key: 'item', en: 'Item', bn: 'পণ্য', w: 'minmax(150px,2fr)' },
    { key: 'quantity', en: 'Qty', bn: 'পরিমাণ', type: 'number', w: '90px' },
    { key: 'unit', en: 'Unit', bn: 'একক', w: '80px' },
    { key: 'unit_price', en: 'Rate', bn: 'দর', type: 'number', w: '110px' },
    { key: 'amount_bdt', en: 'Amount (BDT)', bn: 'টাকা', type: 'number', w: '130px' },
  ],
  delivery: [
    { key: 'line_date', en: 'Date', bn: 'তারিখ', type: 'date', w: '150px' },
    { key: 'outcome', en: 'Result', bn: 'ফলাফল', type: 'outcome', w: '150px' },
    { key: 'amount_bdt', en: 'Cash on delivery (BDT)', bn: 'ক্যাশ অন ডেলিভারি', type: 'number', w: '170px' },
    { key: 'reference', en: 'Parcel number', bn: 'পার্সেল নম্বর', w: 'minmax(140px,1fr)' },
  ],
  repayment: [
    { key: 'line_date', en: 'Paid on', bn: 'শোধের তারিখ', type: 'date', w: '150px' },
    { key: 'due_date', en: 'Was due', bn: 'মেয়াদ ছিল', type: 'date', w: '150px' },
    { key: 'reference', en: 'Loan number', bn: 'ঋণ নম্বর', w: 'minmax(130px,1fr)' },
    { key: 'unit_price', en: 'Amount due', bn: 'দেয় টাকা', type: 'number', w: '130px' },
    { key: 'amount_bdt', en: 'Amount paid', bn: 'শোধ করা', type: 'number', w: '130px' },
  ],
}

const toRow = (line: ReceiptLineOut, keys: string[]): Row => {
  const row: Row = { line_id: line.line_id }
  for (const k of keys) {
    const v = (line as unknown as Record<string, unknown>)[k]
    row[k] = v === null || v === undefined ? '' : String(v)
  }
  return row
}

type Message = { tone: 'ok' | 'bad'; text: string } | null

export function ReceiptReviewPage() {
  const t = useT()
  const { receiptId = '' } = useParams()
  const view = useApi<ReceiptOut>(`/receipts/${encodeURIComponent(receiptId)}`, undefined, { noCache: true })
  const [message, setMessage] = useState<Message>(null)
  const data = view.data

  // a receipt being read: ask again until it is done
  const reading = data?.reading === 'queued' || data?.reading === 'running'
  useEffect(() => {
    if (!reading) return
    const id = window.setInterval(() => view.reload(), 2500)
    return () => window.clearInterval(id)
  }, [reading, view])

  if (view.error) return <Page><ErrorCallout error={view.error} /></Page>
  if (!data) return <Page><LoadingState title={t('Opening the receipt…', 'রসিদ খোলা হচ্ছে…')} /></Page>
  // the form starts afresh from every new answer of the server
  return <Editor key={JSON.stringify(data)} data={data} receiptId={receiptId} reload={view.reload} message={message} setMessage={setMessage} />
}

function Editor({ data, receiptId, reload, message, setMessage }: { data: ReceiptOut; receiptId: string; reload: () => void; message: Message; setMessage: (m: Message) => void }) {
  const t = useT()
  const lang = useLang()
  const cols = COLUMNS[data.kind]
  const keys = useMemo(() => cols.map((c) => c.key), [cols])

  const [header, setHeader] = useState({
    supplier: data.supplier ?? '',
    receipt_date: data.receipt_date ?? '',
    memo_no: data.memo_no ?? '',
    stated_total: data.stated_total == null ? '' : String(data.stated_total),
  })
  const [rows, setRows] = useState<Row[]>(() => data.lines.map((l) => toRow(l, keys)))
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [ack, setAck] = useState(false)
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')
  const [picture, setPicture] = useState<{ url: string; type: string } | null>(null)

  // the picture, as stored (every view is recorded)
  useEffect(() => {
    if (!data.has_document) return
    let url = ''
    let alive = true
    apiBlob(`/receipts/${encodeURIComponent(receiptId)}/document`).then(
      (blob) => {
        if (!alive) return
        url = URL.createObjectURL(blob)
        setPicture({ url, type: blob.type })
      },
      () => undefined,
    )
    return () => {
      alive = false
      if (url) URL.revokeObjectURL(url)
    }
  }, [data.has_document, receiptId])

  const closed = data.status === 'published' || data.status === 'rejected'
  const flagsByLine = useMemo(() => {
    const map: Record<string, Record<string, string>> = {}
    for (const l of data.lines) {
      map[l.line_id] = {}
      for (const f of l.flags) map[l.line_id][f.cell] = f.text
    }
    return map
  }, [data])
  const conf = (id: string, key: string) => data.lines.find((l) => l.line_id === id)?.confidence[key]

  const sum = rows.reduce((a, r) => a + (Number(r.amount_bdt) || 0), 0)
  const stated = header.stated_total === '' ? null : Number(header.stated_total)

  const edit = (index: number, key: string, value: string) => {
    setRows(rows.map((r, i) => (i === index ? { ...r, [key]: value } : r)))
    setDirty(true)
  }
  const editHeader = (key: keyof typeof header, value: string) => {
    setHeader({ ...header, [key]: value })
    setDirty(true)
  }
  const addRow = () => {
    const blank: Row = { line_id: '' }
    for (const k of keys) blank[k] = ''
    setRows([...rows, blank])
    setDirty(true)
  }
  const remove = (index: number) => {
    setRows(rows.filter((_, i) => i !== index))
    setDirty(true)
  }

  const payload = () => ({
    header: { supplier: header.supplier, receipt_date: header.receipt_date || null, memo_no: header.memo_no, stated_total: header.stated_total === '' ? null : header.stated_total },
    lines: rows.map((r) => {
      const line: Record<string, string | null> = {}
      if (r.line_id) line.line_id = r.line_id
      for (const k of keys) line[k] = r[k] === '' ? null : r[k]
      return line
    }),
  })

  const fail = (err: unknown) => setMessage({ tone: 'bad', text: err instanceof ApiError ? err.message : String(err) })

  const save = async (): Promise<boolean> => {
    setBusy(true)
    setMessage(null)
    try {
      await api<ReceiptOut>(`/receipts/${encodeURIComponent(receiptId)}`, { method: 'PUT', json: payload() })
      reload()
      setMessage({ tone: 'ok', text: t('Saved. The checks ran again on your numbers.', 'সংরক্ষিত। আপনার সংখ্যায় আবার যাচাই চলেছে।') })
      return true
    } catch (err) {
      fail(err)
      return false
    } finally {
      setBusy(false)
    }
  }

  const publish = async () => {
    if (dirty && !(await save())) return
    setBusy(true)
    try {
      await api<ReceiptOut>(`/receipts/${encodeURIComponent(receiptId)}/publish`, { method: 'POST', json: { acknowledged: ack } })
      reload()
      setMessage({ tone: 'ok', text: t('Published. The credit officers and the merchant can see it now.', 'প্রকাশিত। ক্রেডিট অফিসার ও ব্যবসায়ী এখন দেখতে পারবেন।') })
    } catch (err) {
      fail(err)
      reload()
    } finally {
      setBusy(false)
    }
  }

  const reject = async () => {
    setBusy(true)
    try {
      await api<ReceiptOut>(`/receipts/${encodeURIComponent(receiptId)}/reject`, { method: 'POST', json: { reason } })
      setRejecting(false)
      reload()
    } catch (err) {
      fail(err)
    } finally {
      setBusy(false)
    }
  }

  const status = STATUS_WORDS[data.status]
  const toCheck = data.cells_to_check

  const input = 'min-h-11 w-full min-w-0 rounded-[9px] border bg-white px-2.5 font-sans text-[15px] text-ink disabled:bg-ground disabled:text-muted-2 transition-colors'

  return (
    <Page>
      <Link to="/app/receipts" className="inline-flex min-h-11 items-center gap-1.5 self-start text-[14.5px] font-semibold text-lens-dark no-underline transition-transform hover:-translate-x-0.5">
        <ArrowLeft size={17} aria-hidden="true" />
        {t('All receipts', 'সব রসিদ')}
      </Link>
      <PageHeader
        title={`${data.shop_name ?? data.merchant_id} · ${pick(KIND_WORDS[data.kind], lang)}`}
        description={
          closed
            ? data.status === 'published'
              ? t('This receipt is published. The merchant sees it on their own page.', 'এই রসিদ প্রকাশিত। ব্যবসায়ী তাঁর নিজের পাতায় দেখতে পান।')
              : `${t('Rejected', 'বাতিল')}: ${data.reject_reason ?? ''}`
            : t('Compare each row with the picture. Highlighted cells need a look.', 'প্রতিটি সারি ছবির সাথে মেলান। রঙিন ঘরগুলো দেখুন।')
        }
      />
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-md px-2.5 py-1 text-[13.5px] font-semibold ${TONES[status.tone]}`}>{pick(status, lang)}</span>
        {data.method === 'typed' && <span className="text-[13.5px] text-muted-2">{t('Typed in, no picture', 'টাইপ করা, ছবি নেই')}</span>}
        {data.merchant_confirmed_at && <span className="inline-flex items-center gap-1 text-[13.5px] font-semibold text-lens-dark"><CheckCircle2 size={16} aria-hidden="true" />{t('The merchant says it looks right', 'ব্যবসায়ী বলেছেন ঠিক আছে')}</span>}
      </div>

      {(data.reading === 'queued' || data.reading === 'running') && <p role="status" className="m-0 rounded-[10px] bg-info-panel px-4 py-3 text-[14.5px] text-[#245C93]">{t('Reading the picture… this takes up to a minute. You can type the lines yourself meanwhile.', 'ছবি পড়া হচ্ছে… এক মিনিটের মতো লাগে। চাইলে ততক্ষণে নিজে লাইন টাইপ করুন।')}</p>}
      {data.reading === 'failed' && <p role="alert" className="m-0 rounded-[10px] bg-amber-panel px-4 py-3 text-[14.5px] text-amber-text">{t('The picture could not be read. Type the lines in beside it.', 'ছবিটি পড়া যায়নি। পাশে নিজে লাইনগুলো টাইপ করুন।')}</p>}
      {message && <p role="status" className={`m-0 rounded-[10px] px-4 py-3 text-[14.5px] ${message.tone === 'ok' ? 'bg-strong-chip text-lens-dark' : 'bg-error-panel text-error'}`}>{message.text}</p>}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        {data.has_document && (
          <section className="flex max-h-[80vh] flex-col gap-2 overflow-auto rounded-card border border-card-line bg-card p-3 xl:sticky xl:top-20 xl:self-start" aria-label={t('The receipt picture', 'রসিদের ছবি')}>
            {!picture ? (
              <p className="m-0 p-6 text-center text-muted-2">{t('Loading the picture…', 'ছবি আসছে…')}</p>
            ) : picture.type === 'application/pdf' ? (
              <iframe title={t('Receipt PDF', 'রসিদের PDF')} src={picture.url} className="h-[70vh] w-full border-0" />
            ) : (
              <img src={picture.url} alt={t('The uploaded receipt', 'আপলোড করা রসিদ')} className="h-auto w-full rounded-[8px]" />
            )}
          </section>
        )}

        <section className={`flex flex-col gap-5 ${data.has_document ? '' : 'xl:col-span-2'}`}>
          <div className="grid gap-3 rounded-card border border-card-line bg-card p-4 sm:grid-cols-2">
            {([
              ['supplier', t('Supplier', 'সরবরাহকারী'), 'text'],
              ['receipt_date', t('Receipt date', 'রসিদের তারিখ'), 'date'],
              ['memo_no', t('Memo number', 'মেমো নম্বর'), 'text'],
              ['stated_total', t('Total on the receipt', 'রসিদের মোট'), 'number'],
            ] as const).map(([key, label, type]) => (
              <label key={key} className={`flex flex-col gap-1 text-[13.5px] font-semibold text-ink ${data.kind !== 'purchase' && (key === 'supplier' || key === 'memo_no' || key === 'stated_total') ? 'hidden' : ''}`}>
                {label}
                <input className={`${input} border-control-line font-normal`} type={type === 'number' ? 'text' : type} inputMode={type === 'number' ? 'decimal' : undefined} disabled={closed} value={header[key]} onChange={(e) => editHeader(key, e.target.value)} />
              </label>
            ))}
          </div>

          <div className="overflow-x-auto rounded-card border border-card-line bg-card">
            <div className="min-w-[640px]">
              <div className="grid items-end gap-2 border-b border-line bg-ground px-3 py-2.5 text-[13px] font-semibold text-muted-2" style={{ gridTemplateColumns: `34px ${cols.map((c) => c.w).join(' ')} 48px` }}>
                <span>#</span>
                {cols.map((c) => (
                  <span key={c.key}>{t(c.en, c.bn)}</span>
                ))}
                <span />
              </div>
              {rows.length === 0 && <p className="m-0 p-5 text-[15px] text-body">{t('No lines yet. Add a line, or wait for the reader.', 'এখনও কোনো লাইন নেই। লাইন যোগ করুন, বা রিডারের জন্য অপেক্ষা করুন।')}</p>}
              {rows.map((row, i) => (
                <div key={row.line_id || `new-${i}`} className="grid items-start gap-2 border-b border-line px-3 py-2 last:border-b-0" style={{ gridTemplateColumns: `34px ${cols.map((c) => c.w).join(' ')} 48px` }}>
                  <span className="pt-3 text-[13.5px] text-muted-2">{i + 1}</span>
                  {cols.map((c) => {
                    const flag = flagsByLine[row.line_id]?.[c.key]
                    const sure = conf(row.line_id, c.key)
                    const unsure = sure !== undefined && sure < 0.6
                    const cls = flag ? 'border-amber bg-amber-panel' : unsure ? 'border-amber-chip bg-[#fffaf0]' : 'border-control-line'
                    return (
                      <label key={c.key} className="flex min-w-0 flex-col gap-1">
                        {c.type === 'outcome' ? (
                          <select aria-label={t(c.en, c.bn)} disabled={closed} className={`${input} ${cls}`} value={row[c.key]} onChange={(e) => edit(i, c.key, e.target.value)}>
                            <option value="">—</option>
                            {Object.entries(OUTCOME_WORDS).map(([v, w]) => (
                              <option key={v} value={v}>{pick(w, lang)}</option>
                            ))}
                          </select>
                        ) : (
                          <input aria-label={t(c.en, c.bn)} aria-invalid={flag ? true : undefined} title={flag} disabled={closed} className={`${input} ${cls}`} type={c.type === 'date' ? 'date' : 'text'} inputMode={c.type === 'number' ? 'decimal' : undefined} value={row[c.key]} onChange={(e) => edit(i, c.key, e.target.value)} />
                        )}
                        {flag && <span className="flex items-start gap-1 text-[12.5px] leading-snug text-amber-text"><TriangleAlert size={14} aria-hidden="true" className="mt-0.5 shrink-0" />{flag}</span>}
                      </label>
                    )
                  })}
                  <button type="button" disabled={closed} onClick={() => remove(i)} aria-label={t('Remove this line', 'এই লাইন সরান')} className="mt-1 flex size-11 cursor-pointer items-center justify-center rounded-[10px] border-0 bg-transparent text-muted-2 transition-colors hover:bg-error-panel hover:text-error disabled:invisible">
                    <Trash2 size={18} aria-hidden="true" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {data.kind === 'purchase' && (
            <p className={`m-0 rounded-[10px] px-4 py-3 text-[15px] font-semibold ${stated != null && Math.abs(sum - stated) > 1 ? 'bg-amber-panel text-amber-text' : 'bg-strong-chip text-lens-dark'}`}>
              {stated == null
                ? t(`The lines add up to ${taka(sum)}.`, `লাইনগুলোর যোগফল ${taka(sum)}।`)
                : Math.abs(sum - stated) > 1
                  ? t(`The lines add up to ${taka(sum)} but the receipt says ${taka(stated)}: one amount may be wrong.`, `লাইনগুলোর যোগফল ${taka(sum)}, কিন্তু রসিদে ${taka(stated)}: কোনো একটি টাকা ভুল হতে পারে।`)
                  : t(`The lines add up to ${taka(sum)}, the same as the receipt.`, `লাইনগুলোর যোগফল ${taka(sum)}, রসিদের সাথে মিলেছে।`)}
            </p>
          )}
          {data.notes.filter((n) => n.startsWith('!') || n.length > 0).map((n) => (
            <p key={n} className="m-0 flex items-start gap-2 text-[14px] text-amber-text"><TriangleAlert size={16} aria-hidden="true" className="mt-0.5 shrink-0" />{n.replace(/^!/, '')}</p>
          ))}

          {!closed && (
            <div className="flex flex-col gap-4 rounded-card border border-card-line bg-card p-4">
              <div className="flex flex-wrap items-center gap-3">
                <Button variant="outline" size="lg" onClick={addRow}>
                  <Plus size={19} aria-hidden="true" />
                  {t('Add a line', 'লাইন যোগ করুন')}
                </Button>
                <Button variant="outline" size="lg" disabled={busy || !dirty} onClick={() => void save()}>
                  <Save size={19} aria-hidden="true" />
                  {t('Save corrections', 'সংশোধন সংরক্ষণ')}
                </Button>
              </div>
              {toCheck > 0 && (
                <label className="flex items-start gap-3 rounded-[10px] bg-amber-panel p-3 text-[14.5px] text-amber-text">
                  <input type="checkbox" className="mt-1 size-5" checked={ack} onChange={(e) => setAck(e.target.checked)} />
                  <span>{t(`${toCheck} line(s) have highlighted cells. I compared them with the paper receipt and they are right.`, `${toCheck}টি লাইনে রঙিন ঘর আছে। আমি কাগজের রসিদের সাথে মিলিয়ে দেখেছি, ঠিক আছে।`)}</span>
                </label>
              )}
              <div className="flex flex-wrap items-center gap-3">
                <Button size="lg" disabled={busy || rows.length === 0 || (toCheck > 0 && !ack)} onClick={() => void publish()}>
                  <CheckCircle2 size={20} aria-hidden="true" />
                  {t('Publish this receipt', 'রসিদ প্রকাশ করুন')}
                </Button>
                <Button size="lg" variant="ghost" onClick={() => setRejecting(!rejecting)}>
                  {t('Reject', 'বাতিল করুন')}
                </Button>
              </div>
              <p className="m-0 text-[13px] text-muted-2">{t('Publishing makes these lines visible to the credit officers and the score, and shows them to the merchant to confirm.', 'প্রকাশ করলে লাইনগুলো ক্রেডিট অফিসার ও স্কোরে যায় এবং ব্যবসায়ীকে নিশ্চিত করতে দেখানো হয়।')}</p>
              {rejecting && (
                <div className="flex flex-wrap items-end gap-3">
                  <label className="flex min-w-[260px] flex-1 flex-col gap-1 text-[13.5px] font-semibold">
                    {t('Why is this receipt rejected?', 'কেন বাতিল করছেন?')}
                    <input className={`${input} border-control-line font-normal`} value={reason} onChange={(e) => setReason(e.target.value)} />
                  </label>
                  <Button disabled={busy || reason.trim().length < 3} onClick={() => void reject()}>{t('Confirm reject', 'বাতিল নিশ্চিত করুন')}</Button>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </Page>
  )
}
