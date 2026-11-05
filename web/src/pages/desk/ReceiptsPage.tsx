/**
 * The Records Desk home: add receipts to a shop and work through what the reader found.
 *
 * Upload one or many photos, scans or PDFs for a shop (POST /merchants/{id}/receipts); each is
 * read in the background and opens as a table beside the picture. A receipt with no picture
 * (handwritten, lost) can be typed in. The queue below shows what still needs checking first.
 */
import { FilePlus2, Upload } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router'

import { api, ApiError } from '@/api/client'
import type { ReceiptOut, ReceiptRow } from '@/api/types'
import { useApi } from '@/api/useApi'
import { EmptyState, ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { Field, Select } from '@/components/form'
import { Page, PageHeader } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { taka, fmtDate } from '@/lib/format'
import { pick, useLang, useT } from '@/lib/i18n'
import { KIND_WORDS, STATUS_WORDS, TONES } from './words'

type ShopPick = { merchant_id: string; shop_name: string | null; area: string | null; owner_name: string | null; receipts_to_check: number }
const TABS = ['extracted', 'checked', 'published', 'rejected'] as const

export function ReceiptsPage() {
  const t = useT()
  const lang = useLang()
  const navigate = useNavigate()
  const shops = useApi<ShopPick[]>('/receipt-shops', undefined, { noCache: true })
  const [tab, setTab] = useState<(typeof TABS)[number] | 'all'>('extracted')
  const queue = useApi<ReceiptRow[]>('/receipts', { status: tab === 'all' ? undefined : tab }, { noCache: true })
  const [shop, setShop] = useState('')
  const [kind, setKind] = useState('purchase')
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const input = useRef<HTMLInputElement>(null)

  // while something is being read, ask again every few seconds
  const reading = (queue.data ?? []).some((r) => r.reading === 'queued' || r.reading === 'running')
  useEffect(() => {
    if (!reading) return
    const id = window.setInterval(() => queue.reload(), 3000)
    return () => window.clearInterval(id)
  }, [reading, queue])

  const upload = async (files: FileList | null) => {
    if (!files || files.length === 0 || !shop) return
    setBusy(true)
    setError(null)
    const names: string[] = []
    let lastId = ''
    for (const file of Array.from(files)) {
      try {
        const made = await api<ReceiptOut>(`/merchants/${encodeURIComponent(shop)}/receipts`, {
          method: 'POST',
          query: { kind, name: file.name },
          body: { content: file, contentType: 'application/octet-stream' },
        })
        lastId = made.receipt_id
        names.push(`✓ ${file.name}`)
      } catch (err) {
        names.push(`✗ ${file.name}: ${err instanceof ApiError ? err.message : String(err)}`)
      }
      setProgress([...names])
    }
    setBusy(false)
    if (input.current) input.current.value = ''
    queue.reload()
    if (files.length === 1 && lastId) navigate(`/app/receipts/${lastId}`)
  }

  const typed = async () => {
    if (!shop) return
    setError(null)
    try {
      const made = await api<ReceiptOut>(`/merchants/${encodeURIComponent(shop)}/receipts/typed`, { method: 'POST', json: { kind } })
      navigate(`/app/receipts/${made.receipt_id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err))
    }
  }

  return (
    <Page>
      <PageHeader
        title={t('Receipts', 'রসিদ')}
        description={t(
          'Upload a shop’s receipts. The reader fills a table; you compare it with the picture, fix anything wrong, and publish.',
          'দোকানের রসিদ আপলোড করুন। রিডার একটি টেবিল ভরে দেয়; আপনি ছবির সাথে মিলিয়ে ভুল ঠিক করে প্রকাশ করুন।',
        )}
      />
      <section className="flex flex-col gap-4 rounded-card border border-card-line bg-card p-5">
        <h2 className="m-0 text-[18px] font-semibold">{t('Add receipts', 'রসিদ যোগ করুন')}</h2>
        {shops.error ? (
          <ErrorCallout error={shops.error} />
        ) : shops.data && shops.data.length === 0 ? (
          <p className="m-0 text-[15px] text-body">{t('No shop is ready yet. A shop appears here once its consent form has been checked.', 'এখনও কোনো দোকান প্রস্তুত নয়। সম্মতিপত্র যাচাই হলে দোকান এখানে আসবে।')}</p>
        ) : (
          <>
            <div className="grid gap-4 md:grid-cols-2">
              <Field label={t('Shop', 'দোকান')} required>
                <Select
                  value={shop}
                  onChange={(e) => setShop(e.target.value)}
                  placeholder={t('Choose a shop', 'দোকান বাছুন')}
                  options={(shops.data ?? []).map((s) => ({ value: s.merchant_id, label: `${s.shop_name ?? s.merchant_id}${s.area ? ` · ${s.area}` : ''}` }))}
                />
              </Field>
              <Field label={t('What are these?', 'এগুলো কী?')} required>
                <Select value={kind} onChange={(e) => setKind(e.target.value)} options={Object.entries(KIND_WORDS).map(([value, w]) => ({ value, label: pick(w, lang) }))} />
              </Field>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <input ref={input} type="file" multiple accept="image/png,image/jpeg,application/pdf" className="sr-only" id="receipt-files" onChange={(e) => void upload(e.target.files)} />
              <Button size="lg" disabled={!shop || busy} onClick={() => input.current?.click()}>
                <Upload size={20} aria-hidden="true" />
                {busy ? t('Uploading…', 'আপলোড হচ্ছে…') : t('Choose photos or PDFs', 'ছবি বা PDF বাছুন')}
              </Button>
              <Button size="lg" variant="outline" disabled={!shop || busy} onClick={() => void typed()}>
                <FilePlus2 size={20} aria-hidden="true" />
                {t('Type a receipt instead', 'নিজে টাইপ করুন')}
              </Button>
            </div>
            {!shop && <p className="m-0 text-[13.5px] text-muted-2">{t('Choose the shop first.', 'আগে দোকান বাছুন।')}</p>}
          </>
        )}
        {error && <p className="m-0 text-[14px] text-error">{error}</p>}
        {progress.length > 0 && (
          <ul className="m-0 list-none p-0 text-[14px] text-body">
            {progress.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        )}
      </section>

      <div role="tablist" className="flex flex-wrap gap-2">
        {[...TABS, 'all' as const].map((id) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`min-h-11 cursor-pointer rounded-[11px] border px-4 font-sans text-[14.5px] font-semibold transition-all duration-200 hover:-translate-y-px motion-reduce:transition-none ${tab === id ? 'border-lens-dark bg-lens-dark text-white' : 'border-control-line bg-white text-ink-2 hover:border-lens'}`}
          >
            {id === 'all' ? t('All', 'সব') : pick(STATUS_WORDS[id], lang)}
          </button>
        ))}
      </div>

      {queue.error ? (
        <ErrorCallout error={queue.error} />
      ) : !queue.data ? (
        <LoadingState title={t('Loading receipts…', 'রসিদ আসছে…')} />
      ) : queue.data.length === 0 ? (
        <EmptyState title={t('Nothing here', 'এখানে কিছু নেই')} text={t('Receipts you upload will appear in this list.', 'আপনার আপলোড করা রসিদ এই তালিকায় আসবে।')} />
      ) : (
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {queue.data.map((r) => {
            const status = STATUS_WORDS[r.status]
            return (
              <li key={r.receipt_id}>
                <Link to={`/app/receipts/${r.receipt_id}`} className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-card-line bg-card p-4 text-ink no-underline transition-all duration-200 hover:-translate-y-0.5 hover:border-lens hover:shadow-md motion-reduce:transition-none motion-reduce:hover:translate-y-0">
                  <span className="flex min-w-0 flex-col">
                    <span className="text-[16px] font-semibold">{r.shop_name ?? r.merchant_id}</span>
                    <span className="text-[13.5px] text-muted-2">
                      {pick(KIND_WORDS[r.kind], lang)}
                      {r.supplier ? ` · ${r.supplier}` : ''}
                      {r.receipt_date ? ` · ${fmtDate(r.receipt_date)}` : ''}
                    </span>
                  </span>
                  <span className="flex flex-wrap items-center gap-2 text-[13.5px]">
                    {(r.reading === 'queued' || r.reading === 'running') && <span className="text-muted-2">{t('Reading…', 'পড়া হচ্ছে…')}</span>}
                    {r.reading === 'failed' && <span className="font-semibold text-error">{t('Could not be read', 'পড়া যায়নি')}</span>}
                    {r.lines > 0 && <span className="text-body">{t(`${r.lines} lines · ${taka(r.lines_total)}`, `${r.lines}টি লাইন · ${taka(r.lines_total)}`)}</span>}
                    {r.cells_to_check > 0 && r.status !== 'published' && (
                      <span className="rounded-md bg-amber-chip px-2 py-0.5 font-semibold text-amber-text">{t(`${r.cells_to_check} to check`, `${r.cells_to_check}টি দেখার`)}</span>
                    )}
                    <span className={`rounded-md px-2 py-0.5 font-semibold ${TONES[status.tone]}`}>{pick(status, lang)}</span>
                  </span>
                </Link>
              </li>
            )
          })}
        </ul>
      )}
    </Page>
  )
}
