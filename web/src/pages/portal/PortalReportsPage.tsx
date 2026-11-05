/**
 * The merchant's reports: every mistake they reported, what they said, and the lender's answer.
 * (GET /portal/reports)
 */
import type { PortalReport } from '@/api/types'
import { useApi } from '@/api/useApi'
import { EmptyState, ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { Page, PageHeader } from '@/components/Page'
import { fmtBdTime, taka } from '@/lib/format'
import { useT } from '@/lib/i18n'

export function PortalReportsPage() {
  const t = useT()
  const list = useApi<PortalReport[]>('/portal/reports', undefined, { noCache: true })
  const words = {
    open: { en: 'Waiting for an answer', bn: 'উত্তরের অপেক্ষায়', cls: 'bg-amber-chip text-amber-text' },
    accepted: { en: 'Accepted: corrected', bn: 'গৃহীত: ঠিক করা হয়েছে', cls: 'bg-strong-chip text-lens-dark' },
    rejected: { en: 'Checked: kept as recorded', bn: 'যাচাই: আগের মতোই', cls: 'bg-neutral-chip text-neutral-text' },
  } as const
  return (
    <Page>
      <PageHeader title={t('My reports', 'আমার অভিযোগ')} description={t('The mistakes you reported and the answers you received.', 'আপনি যেসব ভুল জানিয়েছেন এবং যে উত্তর পেয়েছেন।')} />
      {list.error ? (
        <ErrorCallout error={list.error} />
      ) : !list.data ? (
        <LoadingState title={t('Loading…', 'আসছে…')} />
      ) : list.data.length === 0 ? (
        <EmptyState title={t('No reports', 'কোনো অভিযোগ নেই')} text={t('If a number on My records is wrong, use “Wrong?” beside it.', 'আমার হিসাবে কোনো সংখ্যা ভুল হলে পাশের “ভুল?” চাপুন।')} />
      ) : (
        <ul className="m-0 flex list-none flex-col gap-4 p-0">
          {list.data.map((r) => {
            const w = words[r.status as keyof typeof words] ?? words.open
            return (
              <li key={r.flag_id} className="flex flex-col gap-2 rounded-card border border-card-line bg-card p-5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-[16px] font-semibold text-ink">{r.item ?? t('A line', 'একটি লাইন')}{r.supplier ? ` · ${r.supplier}` : ''}</span>
                  <span className={`rounded-md px-2.5 py-1 text-[13.5px] font-semibold ${w.cls}`}>{t(w.en, w.bn)}</span>
                </div>
                <p className="m-0 text-[14.5px] text-body">
                  {t('Recorded', 'লেখা আছে')}: {r.recorded_amount_bdt == null ? '—' : taka(r.recorded_amount_bdt)} · {t('You said', 'আপনি বলেছেন')}: {r.claimed_amount_bdt == null ? '—' : taka(r.claimed_amount_bdt)}
                </p>
                <p className="m-0 text-[15px] text-ink">“{r.note}”</p>
                <p className="m-0 text-[13px] text-muted-2">{fmtBdTime(r.raised_at)}</p>
                {r.answer && <p className="m-0 rounded-[10px] bg-ground p-3 text-[15px] text-ink"><strong>{t('Answer', 'উত্তর')}:</strong> {r.answer}</p>}
              </li>
            )
          })}
        </ul>
      )}
    </Page>
  )
}
