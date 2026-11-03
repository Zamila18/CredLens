/**
 * Spreadsheet imports: every .xlsx purchase import with its exact counts
 * (GET /import-batches), and one import with the purchases it saved and how each is known
 * (GET /import-batches/{id}). The workbook itself is never stored, only its fingerprint, so
 * rows that were skipped or could not be read are counted, not listed.
 */
import { FileSpreadsheet } from 'lucide-react'
import { Link, useParams } from 'react-router'

import type { ImportBatchDetail, ImportBatchOut } from '@/api/types'
import { useApi } from '@/api/useApi'
import { EmptyState, ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { Page, PageHeader } from '@/components/Page'
import { StatusTag } from '@/components/StatusTag'
import { count, fmtBdTime, fmtDate, taka } from '@/lib/format'
import { useT } from '@/lib/i18n'
import { RECORD_STATUS } from '@/lib/statuses'

function Counts({ b }: { b: ImportBatchOut }) {
  const t = useT()
  const items: [string, number, string][] = [
    [t('Added', 'যোগ হয়েছে'), b.rows_added, 'text-lens-dark'],
    [t('Already saved, skipped', 'আগেই ছিল, বাদ'), b.rows_skipped, 'text-ink-2'],
    [t('Possible duplicates left out', 'সম্ভাব্য দ্বৈত, বাদ'), b.rows_flagged, 'text-amber-text'],
    [t('Could not be read', 'পড়া যায়নি'), b.rows_rejected, 'text-peri-text'],
  ]
  return (
    <dl className="m-0 grid grid-cols-2 gap-2 sm:grid-cols-4">
      {items.map(([label, value, tone]) => (
        <div key={label} className="rounded-[10px] border border-line bg-ground px-3 py-2">
          <dt className="text-[12px] text-muted-2">{label}</dt>
          <dd className={`m-0 font-display text-xl font-bold tabular ${tone}`}>{count(value)}</dd>
        </div>
      ))}
    </dl>
  )
}

export function ImportsPage() {
  const t = useT()
  const batches = useApi<ImportBatchOut[]>('/import-batches', undefined, { noCache: true })
  return (
    <Page>
      <PageHeader
        title={t('Spreadsheet imports', 'স্প্রেডশিট আমদানি')}
        description={t(
          'Every Excel purchase import and exactly what happened to its rows. Imported records are marked “from a spreadsheet, not verified”.',
          'প্রতিটি এক্সেল কেনাকাটা আমদানি, আর এর সারিগুলোর ঠিক কী হলো। আমদানি করা রেকর্ডে লেখা থাকে “স্প্রেডশিট থেকে, যাচাই হয়নি”।',
        )}
      />
      {batches.error ? (
        <ErrorCallout error={batches.error} />
      ) : !batches.data ? (
        <LoadingState title={t('Loading imports…', 'আমদানি আসছে…')} />
      ) : batches.data.length === 0 ? (
        <EmptyState title={t('No imports yet', 'এখনও কোনো আমদানি নেই')} text={t('Import a purchase sheet from a shop’s Business records page in Field work.', 'মাঠের কাজে দোকানের ব্যবসার রেকর্ড পাতা থেকে কেনাকাটার শিট আমদানি করুন।')} />
      ) : (
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {batches.data.map((b) => (
            <li key={b.batch_id} className="flex flex-col gap-3 rounded-card border border-card-line bg-card p-4 sm:p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <Link to={`/app/imports/${encodeURIComponent(b.batch_id)}`} className="flex min-w-0 items-center gap-3 no-underline">
                  <FileSpreadsheet size={22} aria-hidden="true" className="shrink-0 text-lens-dark" />
                  <span className="flex min-w-0 flex-col">
                    <span className="truncate text-[16px] font-semibold">{b.file_name}</span>
                    <span className="text-[13px] text-muted-2">
                      {t(`Sheet “${b.sheet_name ?? '—'}”`, `শিট “${b.sheet_name ?? '—'}”`)} · {fmtBdTime(b.uploaded_at)} {t('BD time', 'বাংলাদেশ সময়')} · {b.actor}
                    </span>
                  </span>
                </Link>
                {b.merchant_id && (
                  <Link to={`/app/merchants/${encodeURIComponent(b.merchant_id)}`} className="text-sm font-medium no-underline">
                    {b.shop_name ?? b.merchant_id}
                  </Link>
                )}
              </div>
              <Counts b={b} />
            </li>
          ))}
        </ul>
      )}
    </Page>
  )
}

export function ImportBatchPage() {
  const t = useT()
  const { batchId = '' } = useParams()
  const batch = useApi<ImportBatchDetail>(`/import-batches/${encodeURIComponent(batchId)}`, undefined, { noCache: true })
  return (
    <Page>
      <nav aria-label={t('Breadcrumb', 'পথ')} className="flex items-center gap-2 text-sm text-body">
        <Link to="/app/imports" className="font-medium no-underline">
          {t('Spreadsheet imports', 'স্প্রেডশিট আমদানি')}
        </Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">{batch.data?.file_name ?? t('Import', 'আমদানি')}</span>
      </nav>
      {batch.error ? (
        <ErrorCallout error={batch.error} />
      ) : !batch.data ? (
        <LoadingState title={t('Loading the import…', 'আমদানি আসছে…')} />
      ) : (
        <>
          <PageHeader
            title={batch.data.file_name}
            description={t(
              `Sheet “${batch.data.sheet_name ?? '—'}”, imported ${fmtBdTime(batch.data.uploaded_at)} (Bangladesh time) by ${batch.data.actor}.`,
              `শিট “${batch.data.sheet_name ?? '—'}”, আমদানি ${fmtBdTime(batch.data.uploaded_at)} (বাংলাদেশ সময়), ${batch.data.actor}।`,
            )}
          />
          <section className="flex flex-col gap-4 rounded-card border border-card-line bg-card p-4 sm:p-5">
            <Counts b={batch.data} />
            <dl className="m-0 grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-muted-2">{t('Shop', 'দোকান')}</dt>
                <dd className="m-0">
                  {batch.data.merchant_id ? (
                    <Link to={`/app/merchants/${encodeURIComponent(batch.data.merchant_id)}`} className="font-medium no-underline">
                      {batch.data.shop_name ?? batch.data.merchant_id} · <span className="font-mono">{batch.data.merchant_id}</span>
                    </Link>
                  ) : (
                    '—'
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-muted-2">{t('File fingerprint (SHA-256)', 'ফাইলের ছাপ (SHA-256)')}</dt>
                <dd className="m-0 font-mono text-[12.5px] break-all text-ink-2">{batch.data.file_sha256}</dd>
              </div>
            </dl>
            <p className="m-0 text-[13px] text-body">
              {t(
                'The file is not kept, so skipped and unreadable rows are counted here but not listed. Importing the same file again adds nothing.',
                'ফাইলটি রাখা হয় না, তাই বাদ পড়া ও পড়া-না-যাওয়া সারি এখানে গোনা হয়, তালিকা হয় না। একই ফাইল আবার আমদানি করলে কিছু যোগ হয় না।',
              )}
            </p>
          </section>
          <section className="flex flex-col gap-3 rounded-card border border-card-line bg-card p-4 sm:p-5" aria-labelledby="saved">
            <h2 id="saved" className="m-0 text-[17px] font-semibold">
              {t(`Purchases saved by this import (${count(batch.data.records.length)})`, `এই আমদানিতে রাখা কেনাকাটা (${count(batch.data.records.length)})`)}
            </h2>
            {batch.data.records.length === 0 ? (
              <p className="m-0 text-sm text-body">{t('This import saved no purchases.', 'এই আমদানিতে কোনো কেনাকাটা রাখা হয়নি।')}</p>
            ) : (
              <ul className="m-0 flex list-none flex-col p-0">
                {batch.data.records.map((r, i) => (
                  <li key={i} className="flex flex-col gap-1 border-t border-line py-2.5 first:border-t-0">
                    <span className="flex flex-wrap items-baseline justify-between gap-2">
                      <span className="text-[15px] text-ink">
                        <span className="tabular">{fmtDate(r.business_date)}</span>
                        {r.detail && <span className="text-body"> · {r.detail}</span>}
                      </span>
                      <span className="text-[15px] font-semibold tabular">{taka(r.amount_bdt)}</span>
                    </span>
                    <span className="flex flex-wrap items-center gap-2 text-[12.5px] text-muted-2">
                      <StatusTag status={r.status ? RECORD_STATUS[r.status] : undefined} />
                      {t(`saved ${fmtBdTime(r.entered_at)} · simulated business date`, `সংরক্ষিত ${fmtBdTime(r.entered_at)} · সিমুলেটেড ব্যবসার তারিখ`)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </Page>
  )
}
