/**
 * One shop's daily sheet: a spreadsheet-style grid for the FSR (GET/PUT /merchants/{id}/daily/{date}).
 *
 * Draft rows are editable and saved on their own a moment after each change; nothing a draft
 * says reaches an assessment. "Send to the Credit Officer" freezes the rows. A sent row is only
 * ever corrected as an amendment with a reason. Figures can also be pasted from Excel or Google
 * Sheets, or read from a file or a photo (the import panel), and always arrive as drafts.
 * On a phone each row is a card.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router'

import { api, ApiError } from '@/api/client'
import type { DailyDayOut, DailyEntryOut, EntryTypeOut, ImportTableOut } from '@/api/types'
import { useApi } from '@/api/useApi'
import { ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { Page, PageHeader } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { taka } from '@/lib/format'
import { useT } from '@/lib/i18n'

type Row = {
  key: string
  entry_id?: string
  entry_type: string
  status: 'draft' | 'submitted' | 'superseded'
  source?: string
  extraction_confidence?: number | null
  [field: string]: string | number | null | undefined
}

const COLS: { f: string; en: string; bn: string; w: string; type?: string }[] = [
  { f: 'txn_date', en: 'Date', bn: 'তারিখ', w: '124px', type: 'date' },
  { f: 'category', en: 'Item / kind', bn: 'পণ্য / ধরন', w: '130px' },
  { f: 'description', en: 'Details', bn: 'বিবরণ', w: '150px' },
  { f: 'quantity', en: 'Qty', bn: 'পরিমাণ', w: '72px' },
  { f: 'unit', en: 'Unit', bn: 'একক', w: '72px' },
  { f: 'unit_price', en: 'Rate', bn: 'দর', w: '90px' },
  { f: 'amount_bdt', en: 'Amount (BDT)', bn: 'টাকা', w: '110px' },
  { f: 'counterparty', en: 'Supplier / party', bn: 'পক্ষ', w: '140px' },
  { f: 'payment_method', en: 'Method', bn: 'পদ্ধতি', w: '100px' },
  { f: 'payment_status', en: 'Status', bn: 'অবস্থা', w: '100px' },
  { f: 'due_date', en: 'Due / delivered', bn: 'মেয়াদ', w: '124px', type: 'date' },
  { f: 'note', en: 'Note', bn: 'মন্তব্য', w: '130px' },
]
const TEXT_FIELDS = COLS.map((c) => c.f)
const todayIso = () => new Date().toLocaleDateString('en-CA')

let counter = 0
const newKey = () => `r${Date.now()}-${counter++}`

function fromEntry(e: DailyEntryOut): Row {
  const row: Row = { key: e.entry_id, entry_id: e.entry_id, entry_type: e.entry_type, status: e.status, source: e.source, extraction_confidence: e.extraction_confidence }
  for (const f of TEXT_FIELDS) {
    const v = (e as unknown as Record<string, unknown>)[f]
    row[f] = v === null || v === undefined ? '' : String(v)
  }
  return row
}

const blank = (type: string, date: string): Row => ({ key: newKey(), entry_type: type, status: 'draft', txn_date: date })

const amountOf = (r: Row) => {
  const a = Number(r.amount_bdt)
  if (r.amount_bdt !== '' && r.amount_bdt != null && !Number.isNaN(a)) return a
  const q = Number(r.quantity)
  const p = Number(r.unit_price)
  return q && p ? q * p : 0
}

export function DailySheetPage() {
  const t = useT()
  const { merchantId = '' } = useParams()
  const [date, setDate] = useState(todayIso())
  const types = useApi<EntryTypeOut[]>('/daily/entry-types')
  const day = useApi<DailyDayOut>(`/merchants/${encodeURIComponent(merchantId)}/daily/${date}`, undefined, { noCache: true })
  const [rows, setRows] = useState<Row[]>([])
  const [errors, setErrors] = useState<Record<string, Record<string, string>>>({})
  const [saved, setSaved] = useState<'idle' | 'dirty' | 'saving' | 'saved'>('idle')
  const [message, setMessage] = useState<{ tone: 'ok' | 'bad'; text: string } | null>(null)
  const [amend, setAmend] = useState<{ row: Row; reason: string; amount: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const version = useRef(0)
  const grid = useRef<HTMLDivElement>(null)

  const kinds = useMemo(() => Object.fromEntries((types.data ?? []).map((k) => [k.key, k])), [types.data])
  const base = `/merchants/${encodeURIComponent(merchantId)}/daily/${date}`

  // load the rows of the chosen day
  useEffect(() => {
    if (!day.data) return
    const entries = day.data.entries.filter((e) => e.status !== 'superseded').map(fromEntry)
    setRows(entries.length ? entries : [blank('purchase', date)])
    setErrors(day.data.errors ?? {})
    setSaved('idle')
    version.current += 1
  }, [day.data, date])

  const sheet = day.data?.sheet ?? null
  const locked = sheet?.status === 'accepted'
  const drafts = rows.filter((r) => r.status === 'draft')

  const toIn = (r: Row) => {
    const out: Record<string, unknown> = { entry_type: r.entry_type }
    if (r.entry_id) out.entry_id = r.entry_id
    for (const f of TEXT_FIELDS) if (r[f] !== '' && r[f] != null) out[f] = r[f]
    if (r.source) out.source = r.source
    if (r.extraction_confidence != null) out.extraction_confidence = r.extraction_confidence
    return out
  }

  const save = useCallback(async (): Promise<boolean> => {
    const sent = version.current
    setSaved('saving')
    try {
      const res = await api<DailyDayOut>(base, {
        method: 'PUT',
        json: { rows: rows.filter((r) => r.status === 'draft').map(toIn), delete_missing: true },
      })
      setErrors(res.errors ?? {})
      if (sent === version.current) {
        const entries = res.entries.filter((e) => e.status !== 'superseded').map(fromEntry)
        setRows(entries.length ? entries : [blank('purchase', date)])
      }
      setSaved('saved')
      return true
    } catch (err) {
      setSaved('dirty')
      setMessage({ tone: 'bad', text: err instanceof ApiError ? err.message : String(err) })
      return false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [base, rows, date])

  // save drafts a moment after the last change
  useEffect(() => {
    if (saved !== 'dirty') return
    const id = window.setTimeout(() => void save(), 1500)
    return () => window.clearTimeout(id)
  }, [saved, rows, save])

  const change = (next: Row[]) => {
    version.current += 1
    setRows(next)
    setSaved('dirty')
  }
  const edit = (key: string, f: string, v: string) => change(rows.map((r) => (r.key === key ? { ...r, [f]: v } : r)))
  const addRow = (type?: string) => change([...rows, blank(type ?? rows[rows.length - 1]?.entry_type ?? 'purchase', date)])
  const dup = (r: Row) => change([...rows, { ...r, key: newKey(), entry_id: undefined, status: 'draft', source: undefined }])
  const del = (key: string) => change(rows.filter((r) => r.key !== key))

  const focus = (r: number, c: number) => grid.current?.querySelector<HTMLElement>(`[data-r="${r}"][data-c="${c}"]:not(:disabled)`)?.focus()
  const onKey = (e: React.KeyboardEvent, r: number, c: number) => {
    if (e.key === 'ArrowDown' || e.key === 'Enter') {
      e.preventDefault()
      focus(r + 1, c)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      focus(r - 1, c)
    }
  }
  // pasting a block from a spreadsheet fills cells to the right and rows below
  const onPaste = (e: React.ClipboardEvent, rowIndex: number, col: number) => {
    const text = e.clipboardData.getData('text')
    if (!/[\t\n]/.test(text.trim())) return
    e.preventDefault()
    const lines = text.replace(/\r/g, '').split('\n').filter((l) => l.trim() !== '')
    const next = [...rows]
    lines.forEach((line, i) => {
      const at = rowIndex + i
      const row = next[at]?.status === 'draft' ? { ...next[at] } : blank(rows[rowIndex]?.entry_type ?? 'purchase', date)
      line.split('\t').forEach((cell, j) => {
        const f = COLS[col + j]?.f
        if (f) row[f] = cell.trim()
      })
      if (next[at]?.status === 'draft') next[at] = row
      else next.splice(at, 0, row)
    })
    change(next)
  }

  const send = async () => {
    setBusy(true)
    setMessage(null)
    if (saved !== 'saved' && saved !== 'idle' && !(await save())) {
      setBusy(false)
      return
    }
    try {
      await api(`${base}/submit`, { method: 'POST' })
      setMessage({ tone: 'ok', text: t('Sent to the Credit Officer.', 'ক্রেডিট অফিসারকে পাঠানো হয়েছে।') })
      day.reload()
    } catch (err) {
      setMessage({ tone: 'bad', text: err instanceof ApiError ? err.message : String(err) })
      await save()
    }
    setBusy(false)
  }

  const doAmend = async () => {
    if (!amend?.row.entry_id) return
    setBusy(true)
    try {
      await api(`/merchants/${encodeURIComponent(merchantId)}/daily/entries/${encodeURIComponent(amend.row.entry_id)}/amend`, {
        method: 'POST',
        json: { reason: amend.reason, ...(amend.amount !== '' ? { amount_bdt: amend.amount } : {}) },
      })
      setAmend(null)
      day.reload()
    } catch (err) {
      setMessage({ tone: 'bad', text: err instanceof ApiError ? err.message : String(err) })
    }
    setBusy(false)
  }

  const totals = useMemo(() => {
    const sums: Record<string, number> = {}
    for (const r of rows) if (r.status !== 'superseded') sums[r.entry_type] = (sums[r.entry_type] ?? 0) + amountOf(r)
    return sums
  }, [rows])

  const cols = COLS.map((c) => c.w).join(' ')

  return (
    <Page>
      <PageHeader
        title={t('Daily sheet', 'দৈনিক শীট')}
        description={t(
          'Type or paste the day’s figures. Drafts are saved for you and counted only after you send the sheet.',
          'দিনের হিসাব লিখুন বা পেস্ট করুন। খসড়া নিজে থেকে সংরক্ষিত হয়; শীট পাঠালে তবেই হিসাবে ধরা হয়।',
        )}
      />
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-[14px] text-body">
          {t('Date', 'তারিখ')}
          <input type="date" value={date} max={todayIso()} onChange={(e) => e.target.value && setDate(e.target.value)} className="min-h-10 rounded-[10px] border border-control-line bg-white px-2.5 text-[14px] text-ink" />
        </label>
        {sheet && <span className="rounded-md bg-neutral-chip px-2 py-0.5 text-[13px] font-semibold text-neutral-text">{t(`Sheet: ${sheet.status}`, `শীট: ${sheet.status}`)}</span>}
        <span aria-live="polite" className="text-[13px] text-muted-2">
          {saved === 'saving' ? t('Saving…', 'সংরক্ষণ হচ্ছে…') : saved === 'dirty' ? t('Unsaved changes', 'অসংরক্ষিত পরিবর্তন') : saved === 'saved' ? t('Draft saved', 'খসড়া সংরক্ষিত') : ''}
        </span>
      </div>
      {sheet?.status === 'returned' && sheet.returned_reason && (
        <p className="m-0 rounded-[10px] border border-amber-chip bg-amber-panel px-4 py-3 text-[14px] text-amber-text">
          {t('Returned for correction: ', 'সংশোধনের জন্য ফেরত: ')}{sheet.returned_reason}
        </p>
      )}
      {message && (
        <p role="status" className={`m-0 rounded-[10px] px-4 py-3 text-[14px] ${message.tone === 'ok' ? 'bg-strong-chip text-lens-dark' : 'bg-amber-panel text-amber-text'}`}>
          {message.text}
        </p>
      )}
      {day.error ? (
        <ErrorCallout error={day.error} />
      ) : !day.data || !types.data ? (
        <LoadingState title={t('Loading the sheet…', 'শীট আসছে…')} />
      ) : (
        <>
          <div ref={grid} className="overflow-x-auto rounded-card border border-card-line bg-card" role="grid" aria-label={t('Daily records', 'দৈনিক হিসাব')}>
            <div className="hidden min-w-max gap-2 border-b border-line bg-ground px-3 py-2 text-[12.5px] font-semibold text-muted-2 md:grid md:[grid-template-columns:var(--cols)]" style={{ ['--cols' as string]: `150px ${cols} 84px` }} role="row">
              <span>{t('Kind', 'ধরন')}</span>
              {COLS.map((c) => (
                <span key={c.f}>{t(c.en, c.bn)}</span>
              ))}
              <span />
            </div>
            {rows.map((r, ri) => {
              const kind = kinds[r.entry_type]
              const allowed = new Set(kind?.fields ?? TEXT_FIELDS)
              const readOnly = r.status !== 'draft' || locked
              const bad = errors[r.entry_id ?? `new-${drafts.indexOf(r)}`] ?? {}
              return (
                <div key={r.key} role="row" className="grid gap-2 border-b border-line px-3 py-3 last:border-b-0 md:min-w-max md:items-start md:py-1.5 md:[grid-template-columns:var(--cols)]" style={{ ['--cols' as string]: `150px ${cols} 84px` }}>
                  <select
                    aria-label={t('Kind of row', 'সারির ধরন')}
                    disabled={readOnly}
                    value={r.entry_type}
                    onChange={(e) => edit(r.key, 'entry_type', e.target.value)}
                    className="min-h-10 rounded-[10px] border border-control-line bg-white px-2 text-[14px] text-ink disabled:bg-ground"
                  >
                    {(types.data ?? []).map((k) => (
                      <option key={k.key} value={k.key}>
                        {t(k.en, k.bn)}
                      </option>
                    ))}
                  </select>
                  {COLS.map((c, ci) => {
                    const on = allowed.has(c.f)
                    return (
                      <label key={c.f} className={`${on ? 'flex' : 'hidden md:flex'} min-w-0 flex-col gap-0.5`}>
                        <span className="text-[12px] text-muted-2 md:hidden">{t(c.en, c.bn)}</span>
                        <input
                          data-r={ri}
                          data-c={ci}
                          type={c.type === 'date' ? 'date' : 'text'}
                          inputMode={['quantity', 'unit_price', 'amount_bdt'].includes(c.f) ? 'decimal' : undefined}
                          disabled={readOnly || !on}
                          aria-invalid={bad[c.f] ? true : undefined}
                          aria-label={t(c.en, c.bn)}
                          title={bad[c.f]}
                          value={String(r[c.f] ?? '')}
                          onChange={(e) => edit(r.key, c.f, e.target.value)}
                          onKeyDown={(e) => onKey(e, ri, ci)}
                          onPaste={(e) => onPaste(e, ri, ci)}
                          className={`min-h-10 w-full min-w-0 rounded-[8px] border px-2 text-[14px] text-ink disabled:bg-ground disabled:text-muted-2 ${bad[c.f] ? 'border-[#c63535] bg-[#fdf1f1]' : 'border-control-line bg-white'}`}
                        />
                        {bad[c.f] && <span className="text-[12px] text-[#c63535] md:sr-only">{bad[c.f]}</span>}
                      </label>
                    )
                  })}
                  <span className="flex items-center gap-1 md:justify-end">
                    {r.status === 'draft' && !locked ? (
                      <>
                        <Button size="sm" variant="ghost" onClick={() => dup(r)} aria-label={t('Duplicate row', 'সারি নকল করুন')}>
                          ⧉
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => del(r.key)} aria-label={t('Delete row', 'সারি মুছুন')}>
                          ✕
                        </Button>
                      </>
                    ) : r.status === 'submitted' && !locked ? (
                      <Button size="sm" variant="ghost" onClick={() => setAmend({ row: r, reason: '', amount: '' })}>
                        {t('Correct', 'সংশোধন')}
                      </Button>
                    ) : null}
                    {r.extraction_confidence != null && r.extraction_confidence < 0.6 && (
                      <span title={t('Read by a machine with low confidence: check it', 'যন্ত্র কম নিশ্চিত হয়ে পড়েছে: মিলিয়ে দেখুন')} className="text-[12px] text-amber-text">
                        ?
                      </span>
                    )}
                  </span>
                </div>
              )
            })}
            <div className="flex flex-wrap gap-x-5 gap-y-1 bg-ground px-3 py-2 text-[13.5px] font-semibold text-ink">
              {Object.entries(totals).map(([k, v]) => (
                <span key={k}>
                  {kinds[k] ? t(kinds[k].en, kinds[k].bn) : k}: {taka(v)}
                </span>
              ))}
            </div>
          </div>
          {amend && (
            <div className="grid gap-2 rounded-card border border-card-line bg-card p-4 md:grid-cols-[1fr_160px_auto] md:items-end">
              <label className="flex flex-col gap-1 text-[13px] text-body">
                {t('Why is this being corrected?', 'কেন সংশোধন করছেন?')}
                <input value={amend.reason} onChange={(e) => setAmend({ ...amend, reason: e.target.value })} className="min-h-10 rounded-[10px] border border-control-line px-2.5 text-[14px] text-ink" />
              </label>
              <label className="flex flex-col gap-1 text-[13px] text-body">
                {t('Correct amount (BDT)', 'সঠিক টাকা')}
                <input value={amend.amount} inputMode="decimal" onChange={(e) => setAmend({ ...amend, amount: e.target.value })} className="min-h-10 rounded-[10px] border border-control-line px-2.5 text-[14px] text-ink" />
              </label>
              <span className="flex gap-2">
                <Button size="sm" disabled={busy || amend.reason.trim().length < 3} onClick={() => void doAmend()}>
                  {t('Save correction', 'সংশোধন সংরক্ষণ')}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setAmend(null)}>
                  {t('Cancel', 'বাতিল')}
                </Button>
              </span>
            </div>
          )}
          {!locked && (
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" onClick={() => addRow()}>
                {t('Add a row', 'সারি যোগ করুন')}
              </Button>
              <Button disabled={busy || drafts.length === 0} onClick={() => void send()}>
                {t('Send to the Credit Officer', 'ক্রেডিট অফিসারকে পাঠান')}
              </Button>
              <span className="text-[13px] text-muted-2">{t('Tip: copy cells from Excel or Google Sheets and paste into the first cell.', 'টিপ: Excel বা Google Sheets থেকে কপি করে প্রথম ঘরে পেস্ট করুন।')}</span>
            </div>
          )}
          {!locked && <ImportPanel merchantId={merchantId} types={types.data} date={date} onLoad={(loaded) => change([...rows.filter((r) => r.status !== 'draft' || TEXT_FIELDS.some((f) => r[f])), ...loaded])} />}
        </>
      )}
    </Page>
  )
}

/** Upload a CSV, Excel, Word or PDF file or a photo; map its columns; load the rows as drafts. */
function ImportPanel({ merchantId, types, date, onLoad }: { merchantId: string; types: EntryTypeOut[]; date: string; onLoad: (rows: Row[]) => void }) {
  const t = useT()
  const [open, setOpen] = useState(false)
  const [kind, setKind] = useState('purchase')
  const [job, setJob] = useState<ImportTableOut | null>(null)
  const [mapping, setMapping] = useState<Record<string, number>>({})
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const base = `/merchants/${encodeURIComponent(merchantId)}/daily-import`
  const fields = types.find((k) => k.key === kind)?.fields ?? []

  const accept = (res: ImportTableOut) => {
    setJob(res)
    if (res.status === 'done') setMapping(res.suggested_mapping ?? {})
  }
  const upload = async (file: File | undefined) => {
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      accept(await api<ImportTableOut>(base, { method: 'POST', query: { name: file.name, entry_type: kind }, body: { content: file, contentType: 'application/octet-stream' } }))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err))
    }
    setBusy(false)
  }
  // a photo or scan is read in the background: ask again until it is done
  useEffect(() => {
    if (!job || (job.status !== 'queued' && job.status !== 'running')) return
    const id = window.setTimeout(() => {
      api<ImportTableOut>(`${base}/${encodeURIComponent(job.job_id)}`, { query: { entry_type: kind } }).then(accept, (err) => setError(String(err)))
    }, 2500)
    return () => window.clearTimeout(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job])

  const load = () => {
    if (!job) return
    const loaded = job.rows.map((cells, i): Row => {
      const row: Row = { key: newKey(), entry_type: kind, status: 'draft', source: 'import', extraction_confidence: job.confidences[i] ?? null, txn_date: date }
      for (const f of fields) {
        const col = mapping[f]
        if (col !== undefined && col >= 0 && cells[col] !== undefined) row[f] = cells[col]
      }
      return row
    })
    onLoad(loaded)
    setJob(null)
    setOpen(false)
  }

  return (
    <section className="rounded-card border border-card-line bg-card p-4">
      <button type="button" className="cursor-pointer border-0 bg-transparent p-0 text-[15px] font-semibold text-ink" aria-expanded={open} onClick={() => setOpen(!open)}>
        {t('Import figures from a file or photo', 'ফাইল বা ছবি থেকে হিসাব আমদানি')} {open ? '▴' : '▾'}
      </button>
      {open && (
        <div className="mt-3 flex flex-col gap-3">
          <p className="m-0 text-[13.5px] text-body">
            {t('CSV, Excel, Word and PDF files are read exactly. A photo or scanned register is read by a machine and often needs correcting: check every row. Rows arrive as drafts.', 'CSV, Excel, Word ও PDF হুবহু পড়া হয়। ছবি বা স্ক্যান করা খাতা যন্ত্র পড়ে এবং প্রায়ই ভুল থাকে: প্রতিটি সারি মিলিয়ে নিন। সারিগুলো খসড়া হিসেবে আসে।')}
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <select value={kind} onChange={(e) => { setKind(e.target.value); setJob(null) }} className="min-h-10 rounded-[10px] border border-control-line bg-white px-2 text-[14px]" aria-label={t('Kind of figures', 'হিসাবের ধরন')}>
              {types.map((k) => (
                <option key={k.key} value={k.key}>
                  {t(k.en, k.bn)}
                </option>
              ))}
            </select>
            <input type="file" accept=".csv,.xlsx,.docx,.pdf,image/png,image/jpeg" disabled={busy} onChange={(e) => void upload(e.target.files?.[0])} aria-label={t('Choose a file', 'ফাইল বাছুন')} />
          </div>
          {error && <p className="m-0 text-[14px] text-[#c63535]">{error}</p>}
          {job && (job.status === 'queued' || job.status === 'running') && <p className="m-0 text-[14px] text-body">{t('Reading the file… this can take a minute.', 'ফাইল পড়া হচ্ছে… এক মিনিট লাগতে পারে।')}</p>}
          {job?.status === 'failed' && <p className="m-0 text-[14px] text-[#c63535]">{job.error ?? t('The file could not be read.', 'ফাইলটি পড়া যায়নি।')}</p>}
          {job?.status === 'done' && (
            <>
              {job.notes.map((n) => (
                <p key={n} className="m-0 text-[13px] text-amber-text">{n}</p>
              ))}
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {fields.map((f) => (
                  <label key={f} className="flex flex-col gap-1 text-[13px] text-body">
                    {COLS.find((c) => c.f === f) ? t(COLS.find((c) => c.f === f)!.en, COLS.find((c) => c.f === f)!.bn) : f}
                    <select value={mapping[f] ?? -1} onChange={(e) => setMapping({ ...mapping, [f]: Number(e.target.value) })} className="min-h-10 rounded-[10px] border border-control-line bg-white px-2 text-[14px]">
                      <option value={-1}>—</option>
                      {job.headers.map((h, i) => (
                        <option key={i} value={i}>{h || t(`Column ${i + 1}`, `কলাম ${i + 1}`)}</option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-[13px]">
                  <thead>
                    <tr>{job.headers.map((h, i) => <th key={i} className="border-b border-line px-2 py-1 text-left">{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {job.rows.slice(0, 8).map((r, i) => (
                      <tr key={i} className={job.confidences[i] != null && job.confidences[i] < 0.6 ? 'bg-amber-panel' : ''}>
                        {r.map((c, j) => <td key={j} className="border-b border-line px-2 py-1">{c}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex items-center gap-3">
                <Button onClick={load} disabled={job.rows.length === 0}>
                  {t(`Load ${job.rows.length} rows as drafts`, `${job.rows.length}টি সারি খসড়া হিসেবে নিন`)}
                </Button>
                <span className="text-[13px] text-muted-2">{t('You can still edit every cell before sending.', 'পাঠানোর আগে প্রতিটি ঘর সম্পাদনা করা যাবে।')}</span>
              </div>
            </>
          )}
        </div>
      )}
    </section>
  )
}
