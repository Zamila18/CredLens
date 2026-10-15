/**
 * Data import (Import.dc.html), admin only. POST /admin/import/{table}?dry_run=...
 * with the CSV file itself as the body (Content-Type: text/csv).
 *
 * Imported rows are checked and stored, but they never reach a score: training reads
 * the generated files, not the database. The page says so (DESIGN_SPEC section 5;
 * the mockup's info strip was wrong).
 */
import { useRef, useState, type DragEvent } from 'react'

import { ApiError, api } from '@/api/client'
import type { Health, ImportReport } from '@/api/types'
import { useApi } from '@/api/useApi'
import { ErrorCallout } from '@/components/ErrorCallout'
import { Card, Page, PageHeader } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { count } from '@/lib/format'
import { hasQueue } from '@/lib/modes'
import { cn } from '@/lib/utils'

/** Contract order: every id points at something already loaded (docs/API_NOTES.md). */
const TABLES = ['merchants', 'loans', 'purchases', 'deliveries', 'payments', 'questionnaire', 'consents']

function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function Report({ report }: { report: ImportReport }) {
  return (
    <Card className="flex flex-col gap-3.5 p-[18px]">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="m-0 text-base font-semibold">3 · What the check found</h2>
        <span className="font-mono text-xs text-muted-2">
          {report.table} · {report.dry_run ? 'check only' : 'check and load'}
        </span>
      </div>

      {report.file_error && (
        <div className="rounded-panel bg-amber-panel px-4 py-3 text-sm leading-5 text-amber-deep">
          <span className="font-semibold">The whole file was refused. </span>
          {report.file_error}
        </div>
      )}

      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(150px,100%),1fr))] gap-3">
        <div className="flex flex-col gap-0.5 rounded-panel bg-ground p-3.5">
          <span className="text-[13px] font-semibold">Rows received</span>
          <span className="font-mono text-[26px] font-semibold tabular">{count(report.rows_received)}</span>
        </div>
        <div className="flex flex-col gap-0.5 rounded-panel bg-strong-panel p-3.5">
          <span className="text-[13px] font-semibold text-lens-dark">Rows accepted</span>
          <span className="font-mono text-[26px] font-semibold tabular">{count(report.rows_accepted)}</span>
        </div>
        <div className="flex flex-col gap-0.5 rounded-panel bg-amber-panel p-3.5">
          <span className="text-[13px] font-semibold text-amber-text">Rows rejected</span>
          <span className="font-mono text-[26px] font-semibold tabular">{count(report.rows_rejected)}</span>
        </div>
        <div className="flex flex-col gap-0.5 rounded-panel bg-ground p-3.5">
          <span className="text-[13px] font-semibold">Loaded</span>
          <span className="pt-1.5 text-[15px] font-semibold">
            {report.loaded ? 'Yes: accepted rows only' : report.dry_run ? 'Nothing: check only' : 'Nothing'}
          </span>
        </div>
      </div>

      {report.rejections.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] border-collapse text-[13px]">
            <thead>
              <tr className="text-left text-xs text-muted">
                <th scope="col" className="py-1.5 font-semibold">Line</th>
                <th scope="col" className="py-1.5 font-semibold">Record</th>
                <th scope="col" className="py-1.5 font-semibold">Rejected because</th>
              </tr>
            </thead>
            <tbody>
              {report.rejections.map((r) => (
                <tr key={r.line} className="border-t border-line-soft align-top">
                  <td className="py-2 pr-3 font-mono tabular">{r.line}</td>
                  <td className="py-2 pr-3 font-mono">{r.record_id ?? '—'}</td>
                  <td className="py-2">
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
      )}
      {report.rejections_truncated && (
        <span className="text-[13px] text-amber-text">
          More rows were rejected than are listed here. Fix the ones shown and check the file again.
        </span>
      )}

      <p className="m-0 text-sm text-ink-2">{report.note}</p>
      <span className="text-[13px] text-muted">
        Every import writes an audit entry. Imported rows never change a score in this prototype.
      </span>
    </Card>
  )
}

export function ImportPage() {
  const health = useApi<Health>('/health')
  const [table, setTable] = useState('merchants')
  const [file, setFile] = useState<File | null>(null)
  const [dryRun, setDryRun] = useState(true)
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [report, setReport] = useState<ImportReport | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const input = useRef<HTMLInputElement>(null)

  function choose(next: File | null) {
    setFile(next)
    setReport(null)
    setError(null)
  }

  function onDrop(e: DragEvent<HTMLLabelElement>) {
    e.preventDefault()
    setDragging(false)
    choose(e.dataTransfer.files[0] ?? null)
  }

  async function run() {
    if (!file) return
    setBusy(true)
    setReport(null)
    setError(null)
    try {
      const result = await api<ImportReport>(`/admin/import/${encodeURIComponent(table)}`, {
        method: 'POST',
        query: { dry_run: dryRun },
        body: { content: file, contentType: 'text/csv' },
      })
      setReport(result)
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, 'network', String(err)))
    } finally {
      setBusy(false)
    }
  }

  const publicMode = health.data && !hasQueue(health.data.data_mode)

  return (
    <Page>
      <PageHeader
        title="Data import"
        description="Upload a CSV exported from the lender’s systems. Each file is checked against the data contract before anything loads. Nobody types purchase or delivery records here."
        aside={<span className="font-mono text-xs text-muted-2">admin only · synthetic or fixture files only</span>}
      />

      <div className="rounded-panel bg-peri-panel px-4 py-3.5 text-sm leading-5 text-peri-head">
        In production the source systems feed CredLens on a schedule. In this prototype an imported file is checked
        and its accepted rows are stored, but they never reach a score: training reads the generated data files, not
        the database. Scoring from the database is a pilot step.
      </div>

      {publicMode && (
        <ErrorCallout
          error={{ status: 409, code: 'import_not_available', message: '' }}
          className="max-w-[720px]"
        />
      )}

      <div className="flex flex-wrap items-start gap-6">
        <Card className="flex flex-[1_1_280px] flex-col gap-2.5 p-[18px]">
          <h2 className="m-0 text-base font-semibold">1 · Pick a table</h2>
          <span className="text-[13px] text-muted">Import in this order, so every id points at something already loaded.</span>
          <div role="radiogroup" aria-label="Table" className="flex flex-col gap-1.5">
            {TABLES.map((name, i) => {
              const on = name === table
              return (
                <button
                  key={name}
                  type="button"
                  role="radio"
                  aria-checked={on}
                  onClick={() => {
                    setTable(name)
                    setReport(null)
                    setError(null)
                  }}
                  className={cn(
                    'flex min-h-11 w-full cursor-pointer items-center gap-3 rounded-[10px] border-[1.5px] px-3 py-2.5 text-left font-sans text-ink',
                    on ? 'border-lens bg-strong-selected' : 'border-card-line bg-card hover:border-[#9FAAA3]',
                  )}
                >
                  <span
                    className={cn(
                      'inline-flex size-6 items-center justify-center rounded-[7px] font-mono text-xs font-semibold',
                      on ? 'bg-lens text-white' : 'bg-seg',
                    )}
                  >
                    {i + 1}
                  </span>
                  <span className="font-mono text-sm font-medium">{name}</span>
                </button>
              )
            })}
          </div>
        </Card>

        <div className="flex min-w-0 flex-[999_1_460px] flex-col gap-4">
          <Card className="flex flex-col gap-3.5 p-[18px]">
            <h2 className="m-0 text-base font-semibold">2 · Choose the file</h2>
            <label
              onDragOver={(e) => {
                e.preventDefault()
                setDragging(true)
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              className={cn(
                'relative flex cursor-pointer flex-col items-center justify-center gap-2 rounded-[14px] border-2 border-dashed px-4 py-8 text-center',
                dragging ? 'border-lens bg-strong-panel' : 'border-disabled bg-row-hover',
              )}
            >
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#2D4F45" strokeWidth="1.6" aria-hidden="true">
                <path d="M12 15V4" />
                <path d="M7.5 8.5 12 4l4.5 4.5" />
                <path d="M4 15v4h16v-4" />
              </svg>
              {file ? (
                <span className="text-[15px] font-semibold">
                  <span className="font-mono">{file.name}</span> · {fileSize(file.size)}
                </span>
              ) : (
                <span className="text-[15px] font-semibold">
                  Drop <span className="font-mono">{table}.csv</span> here, or browse
                </span>
              )}
              <span className="text-[13px] text-muted">CSV only · up to 10 MB · exact column names from the contract</span>
              <input
                ref={input}
                type="file"
                accept=".csv,text/csv"
                onChange={(e) => choose(e.target.files?.[0] ?? null)}
                className="absolute size-px opacity-0"
              />
            </label>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <label className="flex cursor-pointer items-center gap-2.5 text-sm">
                <input
                  type="checkbox"
                  checked={dryRun}
                  onChange={() => {
                    setDryRun((v) => !v)
                    setReport(null)
                  }}
                  className="size-5 accent-lens"
                />
                Check only, do not load
              </label>
              <Button size="lg" disabled={!file || busy} onClick={run}>
                {busy ? 'Checking…' : dryRun ? 'Check file' : 'Check and load'}
              </Button>
            </div>
            {!dryRun && (
              <span className="text-[13px] text-amber-text">
                Accepted rows will be written to the database. An import never overwrites a row and cannot be undone
                from this page.
              </span>
            )}
          </Card>

          {error && <ErrorCallout error={error} />}
          {report && <Report report={report} />}
        </div>
      </div>
    </Page>
  )
}
