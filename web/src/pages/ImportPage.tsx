/**
 * Data import (approved design: 10-data-import-desktop.png, with the top production-feed
 * callout removed as asked), admin only.
 *
 * Two ways in:
 * - One table: POST /admin/import/{table}?dry_run=... with the CSV itself as the body.
 * - The whole lender file: POST /admin/import-bundle?dry_run=... with a .zip of the
 *   contract CSVs, checked in contract order in one transaction (the live demo uses this).
 * Accepted rows of NEW merchants are scored by the saved model after a load (nothing is
 * retrained), so they appear in the review queue. An import may never change the history
 * or consent of a merchant already in the data (409 import_not_allowed).
 */
import { CircleAlert, CircleCheck, Database, FileArchive, FileText, Info, Search, UploadCloud } from 'lucide-react'
import { useRef, useState, type DragEvent, type ReactNode } from 'react'
import { Link } from 'react-router'

import { ApiError, api } from '@/api/client'
import type { BundleReport, Health, ImportReport, QueueItem } from '@/api/types'
import { invalidate, useApi } from '@/api/useApi'
import { BandChip } from '@/components/BandChip'
import { ErrorCallout } from '@/components/ErrorCallout'
import { Card, Page, PageHeader } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { count } from '@/lib/format'
import { useT } from '@/lib/i18n'
import { hasQueue } from '@/lib/modes'
import { cn } from '@/lib/utils'

/** Contract order: every id points at something already loaded (docs/API_NOTES.md). */
const TABLES = ['merchants', 'loans', 'purchases', 'deliveries', 'payments', 'questionnaire', 'consents']
const BUNDLE = 'bundle'

function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function Step({ n, title, sub, children }: { n: number; title: string; sub: string; children: ReactNode }) {
  return (
    <Card className="flex flex-col gap-4 p-4 sm:p-5">
      <div className="flex items-start gap-4">
        <span className="flex size-11 shrink-0 items-center justify-center rounded-full border border-[#CFE0F2] bg-info-panel font-display text-xl font-bold text-info">{n}</span>
        <div className="flex flex-col gap-0.5">
          <h2 className="m-0 text-[22px] leading-7 font-semibold">{title}</h2>
          <p className="m-0 text-[15px] text-body">{sub}</p>
        </div>
      </div>
      {children}
    </Card>
  )
}

function Tile({ icon, tone, label, value, help }: { icon: ReactNode; tone: string; label: string; value: ReactNode; help: string }) {
  return (
    <div className={cn('flex items-start gap-3 rounded-[12px] border p-4', tone)}>
      <span className="mt-0.5 shrink-0" aria-hidden="true">
        {icon}
      </span>
      <span className="flex flex-col gap-0.5">
        <span className="text-sm font-semibold text-ink">{label}</span>
        <span className="font-display text-[26px] leading-8 font-bold text-ink tabular">{value}</span>
        <span className="text-[13px] text-body">{help}</span>
      </span>
    </div>
  )
}

function Rejections({ report }: { report: ImportReport }) {
  const t = useT()
  if (report.rejections.length === 0) return null
  return (
    <>
      <div className="overflow-x-auto rounded-[12px] border border-line">
        <table className="w-full min-w-[520px] border-collapse text-sm">
          <thead className="bg-ground">
            <tr className="text-left text-[13px] text-ink-2">
              <th scope="col" className="px-4 py-2.5 font-semibold">{t('Line', 'লাইন')}</th>
              <th scope="col" className="px-4 py-2.5 font-semibold">{t('Record', 'রেকর্ড')}</th>
              <th scope="col" className="px-4 py-2.5 font-semibold">{t('Rejected because', 'নেওয়া হয়নি কারণ')}</th>
            </tr>
          </thead>
          <tbody>
            {report.rejections.map((r) => (
              <tr key={r.line} className="border-t border-line align-top">
                <td className="px-4 py-2.5 tabular">{r.line}</td>
                <td className="px-4 py-2.5 font-mono">{r.record_id ?? '—'}</td>
                <td className="px-4 py-2.5">
                  <ul className="m-0 list-none p-0">
                    {r.reasons.map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {report.rejections_truncated && (
        <span className="text-[13px] text-amber-text">
          {t('More rows were rejected than are listed here. Fix the ones shown and check the file again.', 'এখানে দেখানোর চেয়ে বেশি সারি নেওয়া হয়নি। দেখানোগুলো ঠিক করে ফাইলটি আবার যাচাই করুন।')}
        </span>
      )}
    </>
  )
}

/** One table's report: four tiles and the rejected rows. */
function TableReport({ report }: { report: ImportReport }) {
  const t = useT()
  return (
    <div className="flex flex-col gap-4">
      {report.file_error && (
        <p className="m-0 rounded-[12px] border border-amber-chip bg-amber-panel px-4 py-3 text-sm leading-5 text-amber-deep">
          <b className="font-semibold">{t('The whole file was refused. ', 'পুরো ফাইলটি নেওয়া হয়নি। ')}</b>
          {report.file_error}
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Tile
          icon={<FileText size={30} className="text-info" />}
          tone="border-[#CFE0F2] bg-info-panel"
          label={t('Rows received', 'যত সারি এসেছে')}
          value={count(report.rows_received)}
          help={t('Rows read from the file.', 'ফাইল থেকে পড়া সারি।')}
        />
        <Tile
          icon={<CircleCheck size={30} className="text-band-strong" />}
          tone="border-mint-line bg-mint-2"
          label={t('Rows accepted', 'যত সারি নেওয়া হয়েছে')}
          value={count(report.rows_accepted)}
          help={t('Rows that passed the checks.', 'যে সারি যাচাই পেরিয়েছে।')}
        />
        <Tile
          icon={<CircleAlert size={30} className="text-error" />}
          tone="border-[#F3D0D0] bg-error-panel"
          label={t('Rows rejected', 'যত সারি নেওয়া হয়নি')}
          value={<span className={report.rows_rejected > 0 ? 'text-error' : ''}>{count(report.rows_rejected)}</span>}
          help={t('Rows that could not be accepted.', 'যে সারি নেওয়া যায়নি।')}
        />
        <Tile
          icon={<Database size={30} className="text-ink-2" />}
          tone="border-line bg-ground"
          label={t('Loaded', 'লোড হয়েছে')}
          value={
            <span className="text-lg">
              {report.loaded ? t('Yes: accepted rows', 'হ্যাঁ: নেওয়া সারি') : report.dry_run ? t('Nothing: check only', 'কিছুই না: শুধু যাচাই') : t('Nothing', 'কিছুই না')}
            </span>
          }
          help={report.loaded ? t('Stored in the database.', 'ডেটাবেসে রাখা হয়েছে।') : t('No rows were stored.', 'কোনো সারি রাখা হয়নি।')}
        />
      </div>
      <Rejections report={report} />
    </div>
  )
}

/** Before the first check: the four boxes, empty, so the page shows what will appear. */
function WaitingTiles({ busy }: { busy: boolean }) {
  const t = useT()
  const dash = busy ? '…' : '—'
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label={t('No file checked yet', 'এখনও কোনো ফাইল যাচাই হয়নি')}>
      <Tile icon={<FileText size={30} className="text-info" />} tone="border-[#CFE0F2] bg-info-panel" label={t('Rows received', 'যত সারি এসেছে')} value={dash} help={t('Rows read from the file.', 'ফাইল থেকে পড়া সারি।')} />
      <Tile icon={<CircleCheck size={30} className="text-band-strong" />} tone="border-mint-line bg-mint-2" label={t('Rows accepted', 'যত সারি নেওয়া হয়েছে')} value={dash} help={t('Rows that pass the checks.', 'যে সারি যাচাই পেরোয়।')} />
      <Tile icon={<CircleAlert size={30} className="text-error" />} tone="border-[#F3D0D0] bg-error-panel" label={t('Rows rejected', 'যত সারি নেওয়া হয়নি')} value={dash} help={t('Each one is listed with its reason.', 'প্রতিটির কারণসহ তালিকা দেখানো হবে।')} />
      <Tile icon={<Database size={30} className="text-ink-2" />} tone="border-line bg-ground" label={t('Loaded', 'লোড হয়েছে')} value={dash} help={t('Nothing loads until you untick “Check only”.', '“শুধু যাচাই” না তুললে কিছুই লোড হয় না।')} />
    </div>
  )
}

/** The bundle's report: one row per file, the rejected rows, and the new merchants. */
function BundleResult({ report }: { report: BundleReport }) {
  const t = useT()
  const queue = useApi<QueueItem[]>(report.new_merchants.length ? '/merchants' : null)
  const rows = queue.data?.filter((r) => report.new_merchants.includes(r.merchant_id)) ?? []
  const totals = report.tables.reduce((s, r) => ({ received: s.received + r.rows_received, accepted: s.accepted + r.rows_accepted, rejected: s.rejected + r.rows_rejected }), {
    received: 0,
    accepted: 0,
    rejected: 0,
  })
  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Tile icon={<FileText size={30} className="text-info" />} tone="border-[#CFE0F2] bg-info-panel" label={t('Rows received', 'যত সারি এসেছে')} value={count(totals.received)} help={t(`In ${report.tables.length} files.`, `${report.tables.length}টি ফাইলে।`)} />
        <Tile icon={<CircleCheck size={30} className="text-band-strong" />} tone="border-mint-line bg-mint-2" label={t('Rows accepted', 'যত সারি নেওয়া হয়েছে')} value={count(totals.accepted)} help={t('Rows that passed the checks.', 'যে সারি যাচাই পেরিয়েছে।')} />
        <Tile
          icon={<CircleAlert size={30} className="text-error" />}
          tone="border-[#F3D0D0] bg-error-panel"
          label={t('Rows rejected', 'যত সারি নেওয়া হয়নি')}
          value={<span className={totals.rejected > 0 ? 'text-error' : ''}>{count(totals.rejected)}</span>}
          help={t('Listed by file below.', 'নিচে ফাইল অনুযায়ী দেখানো।')}
        />
        <Tile
          icon={<Database size={30} className="text-ink-2" />}
          tone="border-line bg-ground"
          label={t('Loaded', 'লোড হয়েছে')}
          value={<span className="text-lg">{report.loaded ? t('Yes: accepted rows', 'হ্যাঁ: নেওয়া সারি') : report.dry_run ? t('Nothing: check only', 'কিছুই না: শুধু যাচাই') : t('Nothing', 'কিছুই না')}</span>}
          help={report.loaded ? t('All files in one go.', 'সব ফাইল একসাথে।') : t('No rows were stored.', 'কোনো সারি রাখা হয়নি।')}
        />
      </div>

      <div className="overflow-x-auto rounded-[12px] border border-line">
        <table className="w-full min-w-[560px] border-collapse text-[15px]">
          <thead className="bg-ground">
            <tr className="text-left text-sm text-ink-2">
              <th scope="col" className="px-4 py-2.5 font-semibold">{t('File', 'ফাইল')}</th>
              <th scope="col" className="px-4 py-2.5 text-right font-semibold">{t('Received', 'এসেছে')}</th>
              <th scope="col" className="px-4 py-2.5 text-right font-semibold">{t('Accepted', 'নেওয়া হয়েছে')}</th>
              <th scope="col" className="px-4 py-2.5 text-right font-semibold">{t('Rejected', 'নেওয়া হয়নি')}</th>
              <th scope="col" className="px-4 py-2.5 font-semibold">{t('Note', 'মন্তব্য')}</th>
            </tr>
          </thead>
          <tbody>
            {report.tables.map((r) => (
              <tr key={r.table} className="border-t border-line">
                <td className="px-4 py-2.5 font-mono text-sm">{r.table}.csv</td>
                <td className="px-4 py-2.5 text-right tabular">{count(r.rows_received)}</td>
                <td className="px-4 py-2.5 text-right tabular">{count(r.rows_accepted)}</td>
                <td className={cn('px-4 py-2.5 text-right tabular', r.rows_rejected > 0 && 'font-semibold text-error')}>{count(r.rows_rejected)}</td>
                <td className="px-4 py-2.5 text-sm text-body">{r.file_error ?? r.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {report.tables
        .filter((r) => r.rejections.length > 0)
        .map((r) => (
          <div key={r.table} className="flex flex-col gap-2">
            <h3 className="m-0 text-base font-semibold">
              {t('Rejected rows in', 'যে সারি নেওয়া হয়নি:')} <span className="font-mono">{r.table}.csv</span>
            </h3>
            <Rejections report={r} />
          </div>
        ))}

      {report.loaded && (
        <div className="flex flex-col gap-3 rounded-[12px] border border-mint-line bg-mint-2 p-4">
          <h3 className="m-0 text-lg font-semibold">
            {t(`New merchants now in the review queue: ${report.new_merchants.length}`, `নতুন মার্চেন্ট এখন পর্যালোচনার তালিকায়: ${report.new_merchants.length}`)}
          </h3>
          {report.new_merchants.length === 0 ? (
            <p className="m-0 text-[15px] text-body">{t('None of the new merchants has a loan waiting, so none is in the queue.', 'নতুন কোনো মার্চেন্টের ঋণ অপেক্ষায় নেই, তাই তালিকায় কেউ নেই।')}</p>
          ) : (
            <ul className="m-0 grid list-none gap-2 p-0 sm:grid-cols-2">
              {[...report.new_merchants].sort().map((id) => {
                const row = rows.find((r) => r.merchant_id === id)
                return (
                  <li key={id} className="flex flex-wrap items-center justify-between gap-2 rounded-[10px] border border-line bg-white px-3 py-2">
                    <Link to={`/merchants/${encodeURIComponent(id)}`} className="font-semibold no-underline">
                      {id}
                    </Link>
                    {row ? (
                      row.score != null && row.band ? (
                        <span className="flex items-center gap-2 text-sm text-body tabular">
                          <b className="text-ink">{row.score}</b>/100
                          <BandChip band={row.band} lowScoreWarning={row.low_score_warning} />
                          {row.coverage != null && `${Math.round(row.coverage * 100)}% ${t('coverage', 'কভারেজ')}`}
                        </span>
                      ) : (
                        <span className="text-sm text-body">{t('Consent needed: no score', 'অনুমতি দরকার: স্কোর নেই')}</span>
                      )
                    ) : (
                      <span className="text-sm text-body">{queue.loading ? '…' : t('Open the merchant', 'মার্চেন্ট খুলুন')}</span>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

export function ImportPage() {
  const t = useT()
  const health = useApi<Health>('/health')
  const [table, setTable] = useState<string>(BUNDLE)
  const [file, setFile] = useState<File | null>(null)
  const [dryRun, setDryRun] = useState(true)
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [report, setReport] = useState<ImportReport | null>(null)
  const [bundle, setBundle] = useState<BundleReport | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const input = useRef<HTMLInputElement>(null)
  const isBundle = table === BUNDLE
  const expected = isBundle ? 'credlens_demo_bundle.zip' : `${table}.csv`

  function clear() {
    setReport(null)
    setBundle(null)
    setError(null)
  }

  function choose(next: File | null) {
    setFile(next)
    clear()
  }

  function onDrop(e: DragEvent<HTMLLabelElement>) {
    e.preventDefault()
    setDragging(false)
    choose(e.dataTransfer.files[0] ?? null)
  }

  async function run() {
    if (!file) return
    setBusy(true)
    clear()
    try {
      if (isBundle) {
        const result = await api<BundleReport>('/admin/import-bundle', {
          method: 'POST',
          query: { dry_run: dryRun },
          body: { content: file, contentType: 'application/zip' },
        })
        setBundle(result)
        if (result.loaded) invalidate('/merchants')
      } else {
        const result = await api<ImportReport>(`/admin/import/${encodeURIComponent(table)}`, {
          method: 'POST',
          query: { dry_run: dryRun },
          body: { content: file, contentType: 'text/csv' },
        })
        setReport(result)
        if (result.loaded) invalidate('/merchants')
      }
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, 'network', String(err)))
    } finally {
      setBusy(false)
    }
  }

  const publicMode = health.data && !hasQueue(health.data.data_mode)
  const wrongKind = file && (isBundle ? !file.name.toLowerCase().endsWith('.zip') : !file.name.toLowerCase().endsWith('.csv'))
  const answer = bundle
    ? bundle.note
    : report
      ? report.note
      : t('Choose a file and press the button: the result appears here.', 'ফাইল বেছে বোতাম চাপুন: ফলাফল এখানে দেখা যাবে।')

  return (
    <Page>
      <PageHeader
        title={
          <span className="flex flex-wrap items-center gap-3">
            {t('Data import', 'ডেটা আমদানি')}
            <span className="rounded-full bg-info-panel px-3 py-1 font-sans text-sm font-medium text-info">
              {t('Admin only · synthetic or fixture files only', 'শুধু অ্যাডমিন · শুধু সিনথেটিক বা নমুনা ফাইল')}
            </span>
          </span>
        }
        description={t(
          'Upload a file exported from the lender’s systems. Each file is checked against the data contract before anything loads. Nobody types purchase or delivery records here.',
          'ঋণদাতার সিস্টেম থেকে নেওয়া ফাইল দিন। কিছু লোড হওয়ার আগে প্রতিটি ফাইল ডেটা চুক্তির সাথে মিলিয়ে দেখা হয়। এখানে কেউ কেনাকাটা বা ডেলিভারির রেকর্ড হাতে লেখে না।',
        )}
      />

      {publicMode && <ErrorCallout error={{ status: 409, code: 'import_not_available', message: '' }} className="max-w-[720px]" />}

      <Step
        n={1}
        title={t('Pick a table', 'একটি টেবিল বেছে নিন')}
        sub={t(
          'All seven files in one zip, or one table at a time in this order, so every id points at something already loaded.',
          'সাতটি ফাইল একটি জিপে, অথবা এই ক্রমে একটি একটি টেবিল, যাতে প্রতিটি আইডি আগে থেকে লোড হওয়া কিছুকে নির্দেশ করে।',
        )}
      >
        <div role="radiogroup" aria-label={t('What to upload', 'কী আপলোড করবেন')} className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-8">
          {[BUNDLE, ...TABLES].map((name, i) => {
            const on = name === table
            return (
              <button
                key={name}
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => {
                  setTable(name)
                  setFile(null)
                  clear()
                }}
                className={cn(
                  'flex min-h-12 cursor-pointer items-center justify-center gap-2 rounded-[12px] border px-2 py-2 font-sans text-[15px] text-ink',
                  on ? 'border-band-strong bg-mint font-semibold shadow-[inset_0_0_0_1px_#16845B]' : 'border-card-line bg-card hover:bg-night-2',
                )}
              >
                <span className={cn('flex size-7 items-center justify-center rounded-full text-[13px] font-semibold', on ? 'bg-band-strong text-white' : 'bg-neutral-chip text-ink-2')}>
                  {name === BUNDLE ? <FileArchive size={15} aria-hidden="true" /> : i}
                </span>
                {name === BUNDLE ? t('All tables (zip)', 'সব টেবিল (জিপ)') : name}
              </button>
            )
          })}
        </div>
      </Step>

      <Step
        n={2}
        title={t('Choose the file', 'ফাইল বেছে নিন')}
        sub={
          isBundle
            ? t('A .zip of the contract CSVs (merchants.csv, loans.csv, …). They are checked together, in order.', 'চুক্তির CSV ফাইলগুলোর একটি .zip (merchants.csv, loans.csv, …)। সব একসাথে, ক্রমমতো যাচাই হয়।')
            : t('The file is checked against the table’s required columns.', 'ফাইলটি টেবিলের দরকারি কলামের সাথে মিলিয়ে দেখা হয়।')
        }
      >
        <label
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={cn(
            'relative flex cursor-pointer flex-col items-center justify-center gap-1.5 rounded-[12px] border-2 border-dashed px-4 py-8 text-center',
            dragging ? 'border-info bg-info-panel' : 'border-[#B9D0E8] bg-[#F7FAFD]',
          )}
        >
          <UploadCloud size={36} className="text-info" aria-hidden="true" />
          <span className="text-[17px] font-semibold text-ink">
            {t('Drop', 'এখানে ছাড়ুন:')} <span className="font-mono">{expected}</span> {t('here, or', 'অথবা')}{' '}
            <span className="text-info underline">{t('browse', 'খুঁজে নিন')}</span>.
          </span>
          <span className="text-sm text-body">
            {isBundle ? t('ZIP only · up to 10 MB · CSV files named after the contract tables', 'শুধু ZIP · সর্বোচ্চ 10 MB · চুক্তির টেবিলের নামে CSV') : t('CSV only · up to 10 MB · exact column names from the contract', 'শুধু CSV · সর্বোচ্চ 10 MB · চুক্তির হুবহু কলামের নাম')}
          </span>
          <input
            ref={input}
            type="file"
            accept={isBundle ? '.zip,application/zip' : '.csv,text/csv'}
            onChange={(e) => choose(e.target.files?.[0] ?? null)}
            className="absolute size-px opacity-0"
          />
        </label>
        {file && (
          <div className="flex items-center gap-3 rounded-[12px] border border-line px-4 py-3">
            {isBundle ? <FileArchive size={24} className="text-ink-2" aria-hidden="true" /> : <FileText size={24} className="text-ink-2" aria-hidden="true" />}
            <span className="flex flex-1 flex-col">
              <span className="font-mono text-sm font-semibold text-ink">{file.name}</span>
              <span className="text-[13px] text-body">
                {fileSize(file.size)} · {wrongKind ? t('this does not look like the right kind of file', 'ফাইলের ধরন ঠিক মনে হচ্ছে না') : t('Ready', 'প্রস্তুত')}
              </span>
            </span>
            {wrongKind ? <CircleAlert size={22} className="text-band-review" aria-hidden="true" /> : <CircleCheck size={22} className="text-band-strong" aria-hidden="true" />}
          </div>
        )}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <label className="flex cursor-pointer items-center gap-3 text-[15px] text-ink">
            <input
              type="checkbox"
              checked={dryRun}
              onChange={() => {
                setDryRun((v) => !v)
                clear()
              }}
              className="size-6 accent-[#2F6FB0]"
            />
            {t('Check only, do not load.', 'শুধু যাচাই, লোড নয়।')}
          </label>
          <Button size="lg" disabled={!file || busy || Boolean(publicMode)} onClick={run}>
            <Search size={17} aria-hidden="true" />
            {busy ? t('Checking…', 'যাচাই হচ্ছে…') : dryRun ? t('Check file', 'ফাইল যাচাই') : t('Check and load', 'যাচাই ও লোড')}
          </Button>
        </div>
        {!dryRun && (
          <span className="text-sm text-amber-text">
            {t(
              'Accepted rows will be written to the database. An import never overwrites a row and cannot be undone from this page.',
              'নেওয়া সারি ডেটাবেসে লেখা হবে। আমদানি কখনও কোনো সারির ওপর লেখে না, আর এই পাতা থেকে ফেরানো যায় না।',
            )}
          </span>
        )}
      </Step>

      <Step n={3} title={t('What the check found', 'যাচাইয়ে যা পাওয়া গেল')} sub={answer}>
        {error && <ErrorCallout error={error} />}
        {report && <TableReport report={report} />}
        {bundle && <BundleResult report={bundle} />}
        {!report && !bundle && !error && <WaitingTiles busy={busy} />}
        <span className="text-sm text-body">{t('Every import and every check writes an audit entry.', 'প্রতিটি আমদানি ও যাচাই অডিটে লেখা হয়।')}</span>
        <div className="flex items-start gap-3 rounded-[12px] border border-mint-line bg-mint-2 p-4">
          <Info size={24} className="mt-0.5 shrink-0 text-band-strong" aria-hidden="true" />
          <span className="flex flex-col gap-0.5">
            <span className="text-[15px] font-semibold text-ink">{t('What happens to the score?', 'স্কোরের কী হয়?')}</span>
            <span className="text-sm text-body">
              {t(
                'New merchants with a loan waiting and a valid consent are scored by the same saved model, with the same rules; nothing is retrained. An import can never change the history or consent of a merchant already in the data.',
                'নতুন মার্চেন্টের ঋণ অপেক্ষায় আর বৈধ অনুমতি থাকলে একই সংরক্ষিত মডেল, একই নিয়মে স্কোর দেয়; মডেল আবার শেখানো হয় না। ডেটায় আগে থেকে থাকা মার্চেন্টের ইতিহাস বা অনুমতি আমদানি দিয়ে কখনও বদলানো যায় না।',
              )}
            </span>
          </span>
        </div>
      </Step>
    </Page>
  )
}
