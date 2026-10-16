/**
 * Decision log (Decisions.dc.html): every human decision, with the score that was on
 * screen and the model that made it. GET /decisions. Nothing can be edited or deleted.
 * Asked fresh on every visit, so decisions recorded elsewhere show up.
 */
import { useMemo, useState } from 'react'
import { Link } from 'react-router'

import type { Decision, OfficerAction } from '@/api/types'
import { useApi } from '@/api/useApi'
import { ActionChip } from '@/components/ActionChip'
import { ErrorCallout } from '@/components/ErrorCallout'
import { FilterSelect, Pager } from '@/components/Filters'
import { LockIcon } from '@/components/icons'
import { Card, Page, PageHeader } from '@/components/Page'
import { StatTile } from '@/components/StatTile'
import { ACTION_SHORT, isOverride } from '@/lib/actions'
import { count, fmtDateTime } from '@/lib/format'
import { ACTION_TEXT, pick, useLang, useT } from '@/lib/i18n'

const PAGE_SIZE = 50

export function DecisionsPage() {
  const t = useT()
  const lang = useLang()
  const decisions = useApi<Decision[]>('/decisions', undefined, { noCache: true })
  const [merchant, setMerchant] = useState('')
  const [action, setAction] = useState<OfficerAction | 'all'>('all')
  const [page, setPage] = useState(1)

  const all = useMemo(
    () => [...(decisions.data ?? [])].sort((a, b) => b.decided_at.localeCompare(a.decided_at)),
    [decisions.data],
  )

  const stats = useMemo(() => {
    const accepts = all.filter((d) => d.officer_action === 'accept').length
    const overrides = all.filter((d) => isOverride(d.officer_action))
    return {
      accepts,
      overrides: overrides.length,
      overridesWithReason: overrides.filter((d) => (d.reason_text ?? '').trim() !== '').length,
      moreInfo: all.filter((d) => d.officer_action === 'needs_more_info').length,
    }
  }, [all])

  const filtered = useMemo(() => {
    const needle = merchant.trim().toLowerCase()
    return all.filter(
      (d) => (action === 'all' || d.officer_action === action) && (!needle || d.merchant_id.toLowerCase().includes(needle)),
    )
  }, [all, merchant, action])

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const current = Math.min(page, pages)
  const visible = filtered.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE)
  const loaded = decisions.data !== undefined
  const agreedTotal = stats.accepts + stats.overrides

  return (
    <Page>
      <PageHeader
        title={t('Decision log', 'সিদ্ধান্তের খাতা')}
        description={t(
          'Every human decision, with the score that was on screen and the model that made it. Nothing here can be edited or deleted.',
          'মানুষের নেওয়া প্রতিটি সিদ্ধান্ত, তখন পর্দায় যে স্কোর ছিল এবং যে মডেল তা দিয়েছিল সেসহ। এখানে কিছুই বদলানো বা মোছা যায় না।',
        )}
        aside={
          <span className="inline-flex items-center gap-2 rounded-[10px] bg-banner px-3 py-2 text-[13px] font-semibold text-ink-2">
            <LockIcon size={16} color="#2E3934" /> {t('Append-only', 'শুধু যোগ করা যায়')}
          </span>
        }
      />

      <section aria-label={t('Summary', 'সারাংশ')} className="grid grid-cols-[repeat(auto-fit,minmax(min(220px,100%),1fr))] gap-3">
        <StatTile
          label={t('Officer agreed with the band', 'কর্মকর্তা ব্যান্ডের সাথে একমত')}
          value={loaded && agreedTotal > 0 ? t(`${count(stats.accepts)} of ${count(agreedTotal)}`, `${count(agreedTotal)}-এর মধ্যে ${count(stats.accepts)}`) : '—'}
          caption={t('accepts against overrides; needs-more-info left out', 'মেনে নেওয়া বনাম পরিবর্তন; "আরও তথ্য" বাদ')}
        />
        <StatTile
          label={t('Overrides with a written reason', 'লিখিত কারণসহ পরিবর্তন')}
          value={
            loaded && stats.overrides > 0
              ? t(`${count(stats.overridesWithReason)} of ${count(stats.overrides)}`, `${count(stats.overrides)}-এর মধ্যে ${count(stats.overridesWithReason)}`)
              : '—'
          }
          caption={t('the API refuses an override without one', 'কারণ ছাড়া পরিবর্তন API নেয় না')}
        />
        <StatTile
          label={t('Asked for more information', 'আরও তথ্য চাওয়া হয়েছে')}
          value={loaded ? count(stats.moreInfo) : '—'}
          caption={t('evidence requested before deciding', 'সিদ্ধান্তের আগে প্রমাণ চাওয়া হয়েছে')}
        />
      </section>

      {decisions.error ? (
        <ErrorCallout error={decisions.error} />
      ) : (
        <Card className="overflow-hidden">
          <div className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-3.5">
            <label className="flex items-center gap-2 text-[13px] text-muted">
              {t('Merchant', 'মার্চেন্ট')}
              <input
                type="search"
                value={merchant}
                onChange={(e) => {
                  setMerchant(e.target.value)
                  setPage(1)
                }}
                placeholder="M0…"
                className="min-h-9 w-36 rounded-lg border border-control-line bg-card px-2.5 font-mono text-[13px] text-ink"
              />
            </label>
            <FilterSelect
              label={t('Action', 'পদক্ষেপ')}
              value={action}
              onChange={(v) => {
                setAction(v as OfficerAction | 'all')
                setPage(1)
              }}
              options={[
                { value: 'all', label: t('All', 'সব') },
                ...(Object.keys(ACTION_SHORT) as OfficerAction[]).map((a) => ({ value: a, label: pick(ACTION_TEXT[a].short, lang) })),
              ]}
            />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] border-collapse text-sm">
              <thead>
                <tr className="text-left text-xs tracking-[.04em] text-muted uppercase">
                  <th scope="col" className="px-5 py-3.5 font-semibold">{t('When', 'কখন')}</th>
                  <th scope="col" className="px-3 py-3.5 font-semibold">{t('Merchant', 'মার্চেন্ট')}</th>
                  <th scope="col" className="px-3 py-3.5 font-semibold">{t('Score shown', 'দেখানো স্কোর')}</th>
                  <th scope="col" className="px-3 py-3.5 font-semibold">{t('Action', 'পদক্ষেপ')}</th>
                  <th scope="col" className="px-3 py-3.5 font-semibold">{t('Why', 'কেন')}</th>
                  <th scope="col" className="px-5 py-3.5 font-semibold">{t('Officer · model', 'কর্মকর্তা · মডেল')}</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((d) => (
                  <tr key={d.decision_id} className="border-t border-line align-top">
                    <td className="px-5 py-4 font-mono text-[13px] whitespace-nowrap tabular">{fmtDateTime(d.decided_at)}</td>
                    <td className="px-3 py-4 font-mono font-semibold">
                      <Link to={`/merchants/${encodeURIComponent(d.merchant_id)}`} className="no-underline">
                        {d.merchant_id}
                      </Link>
                    </td>
                    <td className="px-3 py-4 font-mono text-lg font-semibold tabular">{d.score_shown}</td>
                    <td className="px-3 py-4">
                      <ActionChip action={d.officer_action} />
                    </td>
                    <td className="max-w-[380px] px-3 py-4 leading-5">
                      {d.reason_text ??
                        (d.officer_action === 'accept'
                          ? t('No note. Accepting needs none.', 'কোনো নোট নেই। মেনে নিতে নোট লাগে না।')
                          : t('No note.', 'কোনো নোট নেই।'))}
                    </td>
                    <td className="px-5 py-4 font-mono text-xs whitespace-nowrap text-ink-3">
                      {d.officer_id}
                      <br />
                      {d.model_version}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {decisions.loading && <div className="px-5 py-10 text-center text-sm text-muted">{t('Loading decisions…', 'সিদ্ধান্ত আসছে…')}</div>}
          {loaded && all.length === 0 && (
            <div className="px-5 py-10 text-center text-sm text-muted">
              {t(
                'No decisions recorded yet. Officers record them on a merchant’s page.',
                'এখনও কোনো সিদ্ধান্ত রাখা হয়নি। কর্মকর্তারা মার্চেন্টের পাতায় সিদ্ধান্ত রাখেন।',
              )}
            </div>
          )}
          {loaded && all.length > 0 && filtered.length === 0 && (
            <div className="px-5 py-10 text-center text-sm text-muted">
              {t('No decisions match these filters.', 'এই ফিল্টারে কোনো সিদ্ধান্ত মেলেনি।')}
            </div>
          )}
          {loaded && all.length > 0 && (
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-3.5 text-[13px] text-muted">
              <span>
                {t(
                  `${count(filtered.length)} of ${count(all.length)} decisions`,
                  `${count(all.length)}টি সিদ্ধান্তের মধ্যে ${count(filtered.length)}টি`,
                )}
              </span>
              <Pager page={current} pages={pages} onPage={setPage} />
            </div>
          )}
        </Card>
      )}
    </Page>
  )
}
