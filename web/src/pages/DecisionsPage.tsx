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

const PAGE_SIZE = 50

export function DecisionsPage() {
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
        title="Decision log"
        description="Every human decision, with the score that was on screen and the model that made it. Nothing here can be edited or deleted."
        aside={
          <span className="inline-flex items-center gap-2 rounded-[10px] bg-banner px-3 py-2 text-[13px] font-semibold text-ink-2">
            <LockIcon size={16} color="#2E3934" /> Append-only
          </span>
        }
      />

      <section aria-label="Summary" className="grid grid-cols-[repeat(auto-fit,minmax(min(220px,100%),1fr))] gap-3">
        <StatTile
          label="Officer agreed with the band"
          value={loaded && agreedTotal > 0 ? `${count(stats.accepts)} of ${count(agreedTotal)}` : '—'}
          caption="accepts against overrides; needs-more-info left out"
        />
        <StatTile
          label="Overrides with a written reason"
          value={loaded && stats.overrides > 0 ? `${count(stats.overridesWithReason)} of ${count(stats.overrides)}` : '—'}
          caption="the API refuses an override without one"
        />
        <StatTile
          label="Asked for more information"
          value={loaded ? count(stats.moreInfo) : '—'}
          caption="evidence requested before deciding"
        />
      </section>

      {decisions.error ? (
        <ErrorCallout error={decisions.error} />
      ) : (
        <Card className="overflow-hidden">
          <div className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-3.5">
            <label className="flex items-center gap-2 text-[13px] text-muted">
              Merchant
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
              label="Action"
              value={action}
              onChange={(v) => {
                setAction(v as OfficerAction | 'all')
                setPage(1)
              }}
              options={[
                { value: 'all', label: 'All' },
                ...(Object.keys(ACTION_SHORT) as OfficerAction[]).map((a) => ({ value: a, label: ACTION_SHORT[a] })),
              ]}
            />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] border-collapse text-sm">
              <thead>
                <tr className="text-left text-xs tracking-[.04em] text-muted uppercase">
                  <th scope="col" className="px-5 py-3.5 font-semibold">When</th>
                  <th scope="col" className="px-3 py-3.5 font-semibold">Merchant</th>
                  <th scope="col" className="px-3 py-3.5 font-semibold">Score shown</th>
                  <th scope="col" className="px-3 py-3.5 font-semibold">Action</th>
                  <th scope="col" className="px-3 py-3.5 font-semibold">Why</th>
                  <th scope="col" className="px-5 py-3.5 font-semibold">Officer · model</th>
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
                      {d.reason_text ?? (d.officer_action === 'accept' ? 'No note. Accepting needs none.' : 'No note.')}
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
          {decisions.loading && <div className="px-5 py-10 text-center text-sm text-muted">Loading decisions…</div>}
          {loaded && all.length === 0 && (
            <div className="px-5 py-10 text-center text-sm text-muted">
              No decisions recorded yet. Officers record them on a merchant’s page.
            </div>
          )}
          {loaded && all.length > 0 && filtered.length === 0 && (
            <div className="px-5 py-10 text-center text-sm text-muted">No decisions match these filters.</div>
          )}
          {loaded && all.length > 0 && (
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-3.5 text-[13px] text-muted">
              <span>
                {count(filtered.length)} of {count(all.length)} decisions
              </span>
              <Pager page={current} pages={pages} onPage={setPage} />
            </div>
          )}
        </Card>
      )}
    </Page>
  )
}
