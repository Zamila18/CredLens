/**
 * Applications: every working-capital request, newest first, with its assessment, review
 * status and the latest decision (GET /applications). An application is a request: it is
 * never shown as an issued loan, and the amount is what was asked for, not a limit.
 */
import { useMemo, useState } from 'react'
import { Link } from 'react-router'

import type { ApplicationRow } from '@/api/types'
import { useApi } from '@/api/useApi'
import { ActionChip } from '@/components/ActionChip'
import { EmptyState, ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { FilterSegments, SearchBox } from '@/components/Filters'
import { Page, PageHeader } from '@/components/Page'
import { StatusTag } from '@/components/StatusTag'
import { count, fmtDate, taka } from '@/lib/format'
import { PURPOSE_WORDS, wordsFor } from '@/lib/fieldWords'
import { useLang, useT } from '@/lib/i18n'
import { ASSESSMENT_STATUS, READINESS } from '@/lib/statuses'

type Status = 'waiting' | 'decided' | 'all'
type Ready = 'any' | ApplicationRow['readiness']

function Decision({ row }: { row: ApplicationRow }) {
  const t = useT()
  if (!row.decision) return <span className="text-[13px] font-medium text-amber-text">{t('Waiting for a decision', 'সিদ্ধান্তের অপেক্ষায়')}</span>
  return (
    <span className="flex flex-col items-start gap-1">
      <ActionChip action={row.decision} />
      <span className="text-[12px] text-muted-2">{fmtDate(row.decided_at)}</span>
    </span>
  )
}

export function ApplicationsPage() {
  const t = useT()
  const lang = useLang()
  const list = useApi<ApplicationRow[]>('/applications', undefined, { noCache: true })
  const [status, setStatus] = useState<Status>('waiting')
  const [ready, setReady] = useState<Ready>('any')
  const [q, setQ] = useState('')

  const rows = useMemo(() => {
    const words = q.trim().toLowerCase()
    return (list.data ?? []).filter(
      (r) =>
        (status === 'all' || (status === 'waiting' ? !r.decision : Boolean(r.decision))) &&
        (ready === 'any' || r.readiness === ready) &&
        (!words || [r.merchant_id, r.shop_name, r.area, r.district].some((v) => v?.toLowerCase().includes(words))),
    )
  }, [list.data, status, ready, q])

  const all = list.data ?? []
  return (
    <Page>
      <PageHeader
        title={t('Applications', 'আবেদন')}
        description={t(
          'Working-capital requests from shops added in the app. A request is not a loan: nothing here has been approved or issued.',
          'অ্যাপে যোগ করা দোকানের কার্যকরী মূলধনের অনুরোধ। অনুরোধ মানে ঋণ নয়: এখানে কিছুই অনুমোদিত বা প্রদত্ত নয়।',
        )}
      />

      <div className="flex flex-col gap-4 rounded-card border border-card-line bg-card p-4">
        <div className="flex flex-wrap items-end gap-4">
          <FilterSegments<Status>
            label={t('Decision', 'সিদ্ধান্ত')}
            value={status}
            onChange={setStatus}
            options={[
              { value: 'waiting', label: t(`Waiting (${all.filter((r) => !r.decision).length})`, `অপেক্ষায় (${all.filter((r) => !r.decision).length})`) },
              { value: 'decided', label: t('Decided', 'সিদ্ধান্ত হয়েছে') },
              { value: 'all', label: t('All', 'সব') },
            ]}
          />
          <FilterSegments<Ready>
            label={t('Review status', 'পর্যালোচনার অবস্থা')}
            value={ready}
            onChange={setReady}
            options={[
              { value: 'any', label: t('Any', 'যেকোনো') },
              { value: 'not_updated', label: t('Not updated', 'হালনাগাদ হয়নি') },
              { value: 'more_info_needed', label: t('More info', 'আরও তথ্য') },
              { value: 'check_needed', label: t('Check needed', 'যাচাই বাকি') },
              { value: 'ready', label: t('Ready', 'প্রস্তুত') },
            ]}
          />
        </div>
        <SearchBox value={q} onChange={setQ} placeholder={t('Search by shop name, area or CredLens id', 'দোকানের নাম, এলাকা বা CredLens আইডি দিয়ে খুঁজুন')} className="max-w-[460px]" />
      </div>

      {list.error ? (
        <ErrorCallout error={list.error} />
      ) : !list.data ? (
        <LoadingState title={t('Loading the applications…', 'আবেদন আসছে…')} />
      ) : rows.length === 0 ? (
        <EmptyState
          title={all.length ? t('No application matches these filters', 'এই ফিল্টারে কোনো আবেদন নেই') : t('No applications yet', 'এখনও কোনো আবেদন নেই')}
          text={all.length ? t('Change a filter or clear the search.', 'ফিল্টার বদলান বা খোঁজ মুছুন।') : t('Applications are created in Field work, one per shop.', 'আবেদন তৈরি হয় মাঠের কাজে, প্রতি দোকানে একটি।')}
        />
      ) : (
        <>
          <p className="m-0 text-sm text-body">{t(`${count(rows.length)} of ${count(all.length)} applications`, `${count(all.length)}টির মধ্যে ${count(rows.length)}টি আবেদন`)}</p>
          {/* Desktop table */}
          <div className="hidden overflow-hidden rounded-card border border-card-line bg-card lg:block">
            <table className="w-full border-collapse text-left text-sm">
              <thead className="bg-ground text-[12.5px] text-muted-2">
                <tr>
                  <th className="px-4 py-2.5 font-medium">{t('Shop', 'দোকান')}</th>
                  <th className="px-4 py-2.5 text-right font-medium">{t('Requested', 'চাওয়া')}</th>
                  <th className="px-4 py-2.5 font-medium">{t('Applied', 'আবেদন')}</th>
                  <th className="px-4 py-2.5 font-medium">{t('Assessment', 'মূল্যায়ন')}</th>
                  <th className="px-4 py-2.5 font-medium">{t('Review status', 'পর্যালোচনার অবস্থা')}</th>
                  <th className="px-4 py-2.5 font-medium">{t('Decision', 'সিদ্ধান্ত')}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.application_id} className="border-t border-line align-top hover:bg-row-hover">
                    <td className="px-4 py-3">
                      <Link to={`/app/merchants/${encodeURIComponent(r.merchant_id)}`} className="font-semibold no-underline">
                        {r.shop_name ?? r.merchant_id}
                      </Link>
                      <div className="text-[12.5px] text-muted-2">
                        <span className="font-mono">{r.merchant_id}</span>
                        {[r.area, r.district].filter(Boolean).length > 0 && ` · ${[r.area, r.district].filter(Boolean).join(', ')}`}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="font-semibold text-ink tabular">{taka(r.requested_amount_bdt)}</div>
                      <div className="text-[12.5px] text-muted-2">{wordsFor(PURPOSE_WORDS, r.purpose, lang)}</div>
                    </td>
                    <td className="px-4 py-3 text-ink-2 tabular">{fmtDate(r.business_date)}</td>
                    <td className="px-4 py-3">
                      <StatusTag status={ASSESSMENT_STATUS[r.assessment] ?? ASSESSMENT_STATUS.not_scored} />
                    </td>
                    <td className="px-4 py-3">
                      <StatusTag status={READINESS[r.readiness]} />
                      {r.open_checks > 0 && <div className="pt-1 text-[12px] text-muted-2">{t(`${r.open_checks} open`, `${r.open_checks}টি বাকি`)}</div>}
                    </td>
                    <td className="px-4 py-3">
                      <Decision row={r} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Phone and tablet cards */}
          <ul className="m-0 flex list-none flex-col gap-3 p-0 lg:hidden">
            {rows.map((r) => (
              <li key={r.application_id}>
                <Link to={`/app/merchants/${encodeURIComponent(r.merchant_id)}`} className="flex flex-col gap-2 rounded-card border border-card-line bg-card p-4 no-underline">
                  <span className="flex items-start justify-between gap-3">
                    <span className="flex min-w-0 flex-col">
                      <span className="truncate text-[16px] font-semibold text-ink">{r.shop_name ?? r.merchant_id}</span>
                      <span className="font-mono text-[12.5px] text-muted-2">{r.merchant_id}</span>
                    </span>
                    <span className="text-[16px] font-semibold text-ink tabular">{taka(r.requested_amount_bdt)}</span>
                  </span>
                  <span className="flex flex-wrap gap-2">
                    <StatusTag status={READINESS[r.readiness]} />
                    <StatusTag status={ASSESSMENT_STATUS[r.assessment] ?? ASSESSMENT_STATUS.not_scored} />
                  </span>
                  <span className="flex items-center justify-between gap-2 text-[13px] text-body">
                    <span>{t(`Applied ${fmtDate(r.business_date)}`, `আবেদন ${fmtDate(r.business_date)}`)}</span>
                    <Decision row={r} />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </Page>
  )
}
