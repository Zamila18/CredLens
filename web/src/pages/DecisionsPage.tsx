/**
 * Decision log (approved design: 04-decision-log-desktop.png): every human decision, with
 * the score, band and coverage that were on screen and the model that made it. GET /decisions.
 * Nothing can be edited or deleted. Asked fresh on every visit, so decisions recorded
 * elsewhere show up. Times are stored in UTC and shown in Bangladesh time (UTC+06:00).
 * Every number on this page is counted from the real decisions; none is a sample.
 */
import { Lock } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router'

import type { Decision, OfficerAction } from '@/api/types'
import { useApi } from '@/api/useApi'
import { ActionChip } from '@/components/ActionChip'
import { BandChip } from '@/components/BandChip'
import { ErrorCallout } from '@/components/ErrorCallout'
import { FilterSelect, Pager, SearchBox } from '@/components/Filters'
import { Notice } from '@/components/Notice'
import { Card, Page, PageHeader } from '@/components/Page'
import { ScoreRing } from '@/components/ScoreRing'
import { MetricTile } from '@/components/Workspace'
import { ACTION_SHORT, isOverride } from '@/lib/actions'
import { count, fmtBdTime, pct } from '@/lib/format'
import { ACTION_TEXT, pick, useLang, useT } from '@/lib/i18n'

const PAGE_SIZE = 25

/** The score as it was on screen: ring, band and coverage (only the number for decisions before Oct 17). */
function ShownScore({ d }: { d: Decision }) {
  const t = useT()
  if (!d.band_shown || d.coverage_shown == null) {
    return (
      <span className="flex flex-col">
        <span className="text-lg font-bold text-ink tabular">{d.score_shown}/100</span>
        <span className="text-xs text-muted-2">{t('band not saved (older decision)', 'ব্যান্ড রাখা হয়নি (পুরোনো সিদ্ধান্ত)')}</span>
      </span>
    )
  }
  return (
    <span className="flex items-center gap-3">
      <ScoreRing score={d.score_shown} band={d.band_shown} coverage={d.coverage_shown} size={60} />
      <span className="flex flex-col items-start gap-1">
        <BandChip band={d.band_shown} lowScoreWarning={d.band_shown !== 'Needs more info' && d.score_shown < 70} />
        <span className="text-[13px] text-body tabular">
          {pct(d.coverage_shown)} {t('coverage', 'কভারেজ')}
        </span>
      </span>
    </span>
  )
}

export function DecisionsPage() {
  const t = useT()
  const lang = useLang()
  const decisions = useApi<Decision[]>('/decisions', undefined, { noCache: true })
  const [merchant, setMerchant] = useState('')
  const [action, setAction] = useState<OfficerAction | 'all'>('all')
  const [page, setPage] = useState(1)

  const all = useMemo(() => [...(decisions.data ?? [])].sort((a, b) => b.decided_at.localeCompare(a.decided_at)), [decisions.data])

  const stats = useMemo(() => {
    const accepts = all.filter((d) => d.officer_action === 'accept').length
    const overrides = all.filter((d) => isOverride(d.officer_action))
    return {
      accepts,
      overrides: overrides.length,
      overridesWithReason: overrides.filter((d) => (d.reason_text ?? '').trim() !== '').length,
      moreInfo: all.filter((d) => d.officer_action === 'needs_more_info').length,
      models: [...new Set(all.map((d) => d.model_version))],
    }
  }, [all])

  const filtered = useMemo(() => {
    const needle = merchant.trim().toLowerCase()
    return all.filter((d) => (action === 'all' || d.officer_action === action) && (!needle || d.merchant_id.toLowerCase().includes(needle)))
  }, [all, merchant, action])

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const current = Math.min(page, pages)
  const visible = filtered.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE)
  const loaded = decisions.data !== undefined
  const kept = stats.accepts + stats.overrides

  return (
    <Page>
      <PageHeader
        title={
          <span className="flex flex-wrap items-center gap-3">
            {t('Decision log', 'সিদ্ধান্তের খাতা')}
            <span className="inline-flex items-center gap-1.5 rounded-full border border-control-line bg-white px-3 py-1 font-sans text-sm font-medium text-ink-2">
              <Lock size={15} aria-hidden="true" /> {t('Append-only', 'শুধু যোগ করা যায়')}
            </span>
          </span>
        }
        description={t(
          'Every human decision, with the score that was on screen and the model that made it. Nothing here can be edited or deleted.',
          'মানুষের নেওয়া প্রতিটি সিদ্ধান্ত, তখন পর্দায় যে স্কোর ছিল এবং যে মডেল তা দিয়েছিল সেসহ। এখানে কিছুই বদলানো বা মোছা যায় না।',
        )}
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricTile label={t('Decisions recorded', 'রাখা সিদ্ধান্ত')} value={loaded ? all.length : null} hint={t('Every one kept, none edited', 'সবগুলো রাখা, কোনোটি বদলানো নয়')} />
        <MetricTile
          label={t('Suggested band kept', 'প্রস্তাবিত ব্যান্ড রাখা')}
          value={loaded ? stats.accepts : null}
          hint={kept ? t(`of ${count(kept)} accepted or overridden`, `মেনে নেওয়া বা বদলানো ${count(kept)}টির মধ্যে`) : t('No accepts or overrides yet', 'এখনও মেনে নেওয়া বা বদলানো নেই')}
        />
        <MetricTile
          label={t('Overrides with a reason', 'কারণসহ পরিবর্তন')}
          value={loaded ? stats.overridesWithReason : null}
          hint={stats.overrides ? t(`of ${count(stats.overrides)} · the API refuses one without`, `${count(stats.overrides)}টির মধ্যে · কারণ ছাড়া API নেয় না`) : t('No overrides yet', 'এখনও কোনো পরিবর্তন নেই')}
        />
        <MetricTile label={t('Asked for more information', 'আরও তথ্য চাওয়া')} value={loaded ? stats.moreInfo : null} hint={t('Requests to collect more evidence', 'আরও প্রমাণ জোগাড়ের অনুরোধ')} />
      </div>

      {decisions.error ? (
        <ErrorCallout error={decisions.error} />
      ) : (
        <Card className="flex flex-col gap-4 p-4 sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex flex-col gap-1">
              <h2 className="m-0 text-[18px] leading-7 font-semibold">{t('What did each officer decide?', 'প্রত্যেক কর্মকর্তা কী সিদ্ধান্ত নিয়েছেন?')}</h2>
              <p className="m-0 text-[14.5px] text-body">
                {t('Each row keeps the decision, its reason and the score shown at that moment.', 'প্রতিটি সারিতে সিদ্ধান্ত, তার কারণ আর সেই মুহূর্তে দেখানো স্কোর থাকে।')}
              </p>
            </div>
            <div className="flex flex-wrap items-end gap-3">
              <SearchBox
                className="w-[280px] max-w-full"
                value={merchant}
                onChange={(v) => {
                  setMerchant(v)
                  setPage(1)
                }}
                placeholder={t('Search merchant ID (e.g. M000031)', 'মার্চেন্ট আইডি খুঁজুন (যেমন M000031)')}
              />
              <FilterSelect
                label={t('Action', 'পদক্ষেপ')}
                value={action}
                onChange={(v) => {
                  setAction(v as OfficerAction | 'all')
                  setPage(1)
                }}
                options={[
                  { value: 'all', label: t('All', 'সব') },
                  ...(Object.keys(ACTION_SHORT) as OfficerAction[]).map((a) => ({ value: a, label: pick(ACTION_TEXT[a].label, lang) })),
                ]}
              />
            </div>
          </div>
          <div className="flex flex-wrap justify-between gap-2 text-[13px] text-body">
            <span>{t('Score: readiness out of 100. Coverage: how much expected evidence was available.', 'স্কোর: ১০০-এর মধ্যে প্রস্তুতি। কভারেজ: প্রত্যাশিত প্রমাণের কতটা ছিল।')}</span>
            <span>{t('Times shown in Bangladesh time (UTC+06:00)', 'সময় বাংলাদেশ সময়ে (UTC+06:00)')}</span>
          </div>
          <div className="overflow-x-auto rounded-[12px] border border-line" role="region" aria-label={t('Decisions', 'সিদ্ধান্ত')} tabIndex={0}>
            <table className="w-full min-w-[760px] border-collapse text-[14.5px]">
              <thead className="bg-ground">
                <tr className="text-left text-sm text-ink-2">
                  <th scope="col" className="px-4 py-3 font-semibold">{t('When and who', 'কখন ও কে')}</th>
                  <th scope="col" className="px-4 py-3 font-semibold">{t('Merchant', 'মার্চেন্ট')}</th>
                  <th scope="col" className="px-4 py-3 font-semibold">{t('Score shown', 'দেখানো স্কোর')}</th>
                  <th scope="col" className="px-4 py-3 font-semibold">{t('Action', 'পদক্ষেপ')}</th>
                  <th scope="col" className="px-4 py-3 font-semibold">{t('Why', 'কেন')}</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((d) => (
                  <tr key={d.decision_id} className="border-t border-line align-top">
                    <td className="px-4 py-4 text-ink-2">
                      <span className="block whitespace-nowrap tabular">{fmtBdTime(d.decided_at)}</span>
                      <span className="text-[13px] text-muted-2">{d.officer_id}</span>
                    </td>
                    <td className="px-4 py-4 font-semibold whitespace-nowrap">
                      <Link to={`/app/merchants/${encodeURIComponent(d.merchant_id)}`} className="no-underline">
                        {d.merchant_id}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <ShownScore d={d} />
                    </td>
                    <td className="px-4 py-4">
                      <ActionChip action={d.officer_action} />
                    </td>
                    <td className="min-w-[200px] px-4 py-4 leading-[22px] text-ink">
                      {d.reason_text ??
                        (d.officer_action === 'accept' ? t('No note. Accepting needs none.', 'কোনো নোট নেই। মেনে নিতে নোট লাগে না।') : t('No note.', 'কোনো নোট নেই।'))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {decisions.loading && <div className="px-5 py-10 text-center text-sm text-body">{t('Loading decisions…', 'সিদ্ধান্ত আসছে…')}</div>}
            {loaded && all.length === 0 && (
              <div className="px-5 py-10 text-center text-[15px] text-body">
                {t('No decisions recorded yet. Officers record them on a merchant’s page.', 'এখনও কোনো সিদ্ধান্ত রাখা হয়নি। কর্মকর্তারা মার্চেন্টের পাতায় সিদ্ধান্ত রাখেন।')}
              </div>
            )}
            {loaded && all.length > 0 && filtered.length === 0 && (
              <div className="px-5 py-10 text-center text-[15px] text-body">{t('No decisions match these filters.', 'এই ফিল্টারে কোনো সিদ্ধান্ত মেলেনি।')}</div>
            )}
          </div>
          {loaded && all.length > 0 && (
            <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-body">
              <span>{t(`${count(filtered.length)} of ${count(all.length)} ${all.length === 1 ? 'decision' : 'decisions'}`, `${count(all.length)}টি সিদ্ধান্তের মধ্যে ${count(filtered.length)}টি`)}</span>
              <Pager page={current} pages={pages} onPage={setPage} />
            </div>
          )}
        </Card>
      )}

      <Notice tone="info" title={t('Decisions are append-only', 'সিদ্ধান্ত শুধু যোগ করা যায়')}>
        {t('To change course, record a new decision on the merchant’s page.', 'মত বদলালে মার্চেন্টের পাতায় নতুন সিদ্ধান্ত রাখুন।')}
        {stats.models.length > 0 && (
          <span className="mt-1 block text-[13px]">
            {t(stats.models.length === 1 ? 'Model behind these scores: ' : 'Models behind these scores: ', 'এই স্কোরগুলোর মডেল: ')}
            <span className="font-mono">{stats.models.join(', ')}</span>
          </span>
        )}
      </Notice>
    </Page>
  )
}
