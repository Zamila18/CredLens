/**
 * The FSR's home: the shops assigned to them, today's state of each daily sheet, and what needs
 * attention (sheets returned for correction, unsent drafts). GET /fsr/overview.
 */
import { Link } from 'react-router'

import type { FsrOverviewOut } from '@/api/types'
import { useApi } from '@/api/useApi'
import { EmptyState, ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { Page, PageHeader } from '@/components/Page'
import { fmtDate } from '@/lib/format'
import { useT } from '@/lib/i18n'

const STATE = {
  draft: ['Draft saved', 'খসড়া সংরক্ষিত', 'bg-amber-chip text-amber-text'],
  submitted: ['Sent', 'পাঠানো হয়েছে', 'bg-strong-chip text-lens-dark'],
  accepted: ['Accepted', 'গৃহীত', 'bg-strong-chip text-lens-dark'],
  returned: ['Returned to you', 'আপনার কাছে ফেরত', 'bg-peri-chip text-peri-text'],
} as const

export function MyShopsPage() {
  const t = useT()
  const view = useApi<FsrOverviewOut>('/fsr/overview', undefined, { noCache: true })
  const data = view.data
  return (
    <Page>
      <PageHeader
        title={t('My shops', 'আমার দোকান')}
        description={t(
          'Record each shop’s purchases, deliveries and repayments every day, then send the sheet to the Credit Officer.',
          'প্রতিদিন প্রতিটি দোকানের ক্রয়, ডেলিভারি ও পরিশোধ লিখুন, তারপর শীটটি ক্রেডিট অফিসারকে পাঠান।',
        )}
      />
      {view.error ? (
        <ErrorCallout error={view.error} />
      ) : !data ? (
        <LoadingState title={t('Loading your shops…', 'আপনার দোকান আসছে…')} />
      ) : (
        <>
          <dl className="m-0 grid grid-cols-2 gap-3 md:grid-cols-4">
            {[
              [t('Shops', 'দোকান'), data.shops.length],
              [t('Sent today', 'আজ পাঠানো'), data.submitted_today],
              [t('Unsent drafts', 'না-পাঠানো খসড়া'), data.pending_drafts],
              [t('Returned to fix', 'ঠিক করতে ফেরত'), data.returned],
            ].map(([label, value]) => (
              <div key={String(label)} className="rounded-card border border-card-line bg-card px-4 py-3">
                <dt className="text-[13px] text-muted-2">{label}</dt>
                <dd className="m-0 text-[24px] font-semibold text-ink">{value}</dd>
              </div>
            ))}
          </dl>
          <p className="m-0 text-[13.5px] text-body">
            {[data.employee_id, data.territory].filter(Boolean).join(' · ')} · {fmtDate(data.today)}
          </p>
          {data.shops.length === 0 ? (
            <EmptyState
              title={t('No shops assigned yet', 'এখনও কোনো দোকান বরাদ্দ হয়নি')}
              text={t('Your Credit Officer assigns shops to you. They will appear here.', 'ক্রেডিট অফিসার আপনাকে দোকান বরাদ্দ দেবেন। এখানে দেখা যাবে।')}
            />
          ) : (
            <ul className="m-0 grid list-none gap-3 p-0 md:grid-cols-2 xl:grid-cols-3">
              {data.shops.map((s) => {
                const st = s.today_status ? STATE[s.today_status as keyof typeof STATE] : undefined
                return (
                  <li key={s.merchant_id} className="rounded-card border border-card-line bg-card p-4">
                    <Link to={`/app/shops/${encodeURIComponent(s.merchant_id)}/daily`} className="block text-ink no-underline">
                      <span className="block text-[16px] font-semibold">{s.shop_name ?? s.merchant_id}</span>
                      <span className="block text-[13px] text-muted-2">{[s.area, s.district].filter(Boolean).join(', ')}</span>
                      <span className="mt-3 flex flex-wrap items-center gap-2 text-[13px]">
                        <span className={`rounded-md px-2 py-0.5 font-semibold ${st ? st[2] : 'bg-neutral-chip text-neutral-text'}`}>
                          {st ? t(st[0], st[1]) : t('Nothing recorded today', 'আজ কিছু লেখা হয়নি')}
                        </span>
                        {s.last_submitted && <span className="text-muted-2">{t(`last sent ${fmtDate(s.last_submitted)}`, `সর্বশেষ ${fmtDate(s.last_submitted)}`)}</span>}
                      </span>
                      <span className="mt-3 inline-block text-[14px] font-semibold text-lens-dark">{t('Open today’s sheet →', 'আজকের শীট খুলুন →')}</span>
                    </Link>
                  </li>
                )
              })}
            </ul>
          )}
        </>
      )}
    </Page>
  )
}
