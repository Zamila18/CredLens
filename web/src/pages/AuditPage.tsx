/**
 * Audit log (Audit.dc.html), admin only: who viewed or changed what, and when.
 * GET /audit?limit=200|500|1000, newest first. Opening this view is itself audited,
 * so it is asked fresh every time (and the newest row is often this very view).
 */
import { useMemo, useState } from 'react'
import { Link } from 'react-router'

import type { AuditEntry } from '@/api/types'
import { useApi } from '@/api/useApi'
import { Chip } from '@/components/BandChip'
import { ErrorCallout } from '@/components/ErrorCallout'
import { FilterSelect } from '@/components/Filters'
import { Card, Page, PageHeader } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { count, fmtDateTime } from '@/lib/format'

type Look = { verb: string; glyph: string; tile: string; target?: string }

/** A plain sentence and a glyph tile for each action the API writes. */
function describe(action: string): Look {
  switch (action) {
    case 'view_profile':
      return { verb: 'opened the profile of', glyph: 'V', tile: 'bg-peri-chip text-peri-text' }
    case 'view_score':
      return { verb: 'read the score of', glyph: 'S', tile: 'bg-peri-chip text-peri-text' }
    case 'view_consent':
      return { verb: 'read the consent of', glyph: 'C', tile: 'bg-neutral-chip text-neutral-text' }
    case 'record_decision':
      return { verb: 'recorded a decision on', glyph: 'D', tile: 'bg-strong-chip text-lens-dark' }
    case 'record_questionnaire':
      return { verb: 'saved questionnaire answers for', glyph: 'Q', tile: 'bg-strong-chip text-lens-dark' }
    case 'view_audit_log':
      return { verb: 'opened', glyph: 'A', tile: 'bg-neutral-chip text-neutral-text', target: 'the audit log' }
  }
  if (action.startsWith('check_import_')) {
    return { verb: 'checked a file for', glyph: 'I', tile: 'bg-amber-chip text-amber-text', target: action.slice('check_import_'.length) }
  }
  if (action.startsWith('import_')) {
    return { verb: 'imported a file into', glyph: 'I', tile: 'bg-amber-chip text-amber-text', target: action.slice('import_'.length) }
  }
  return { verb: action.replace(/_/g, ' '), glyph: '·', tile: 'bg-neutral-chip text-neutral-text' }
}

const LIMITS = ['200', '500', '1000']

export function AuditPage() {
  const [limit, setLimit] = useState('200')
  const [actor, setActor] = useState('all')
  const [action, setAction] = useState('all')
  const audit = useApi<AuditEntry[]>('/audit', { limit }, { noCache: true })

  const rows = useMemo(() => audit.data ?? [], [audit.data])
  const actors = useMemo(() => [...new Set(rows.map((r) => r.actor))].sort(), [rows])
  const actions = useMemo(() => [...new Set(rows.map((r) => r.action))].sort(), [rows])
  const visible = rows.filter((r) => (actor === 'all' || r.actor === actor) && (action === 'all' || r.action === action))

  return (
    <Page>
      <PageHeader
        title="Audit log"
        description="Who viewed or changed what, and when. A profile read and a score read are each written before anything is shown. Newest first."
        aside={<span className="font-mono text-xs text-muted-2">admin only · this view is itself audited</span>}
      />

      {audit.error ? (
        <ErrorCallout error={audit.error} />
      ) : (
        <Card className="overflow-hidden">
          <div className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-3.5">
            <FilterSelect
              label="Actor"
              value={actor}
              onChange={setActor}
              options={[{ value: 'all', label: 'Everyone' }, ...actors.map((a) => ({ value: a, label: a }))]}
            />
            <FilterSelect
              label="Action"
              value={action}
              onChange={setAction}
              options={[{ value: 'all', label: 'All' }, ...actions.map((a) => ({ value: a, label: a }))]}
            />
            <div className="flex items-center gap-2 sm:ml-auto">
              <FilterSelect label="Rows" value={limit} onChange={setLimit} options={LIMITS.map((l) => ({ value: l, label: l }))} />
              <Button variant="outline" size="sm" onClick={audit.reload}>
                Refresh
              </Button>
            </div>
          </div>
          {audit.loading && <div className="px-5 py-10 text-center text-sm text-muted">Loading the audit log…</div>}
          {audit.data && visible.length === 0 && (
            <div className="px-5 py-10 text-center text-sm text-muted">No entries match these filters.</div>
          )}
          <ol className="m-0 list-none p-0">
            {visible.map((r) => {
              const look = describe(r.action)
              const target = look.target ?? r.merchant_id
              return (
                <li
                  key={r.id}
                  className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3.5 gap-y-1 border-t border-line-soft px-5 py-4 sm:grid-cols-[150px_28px_minmax(0,1fr)_auto]"
                >
                  <span className="col-span-2 font-mono text-[13px] text-ink-3 tabular sm:col-span-1">{fmtDateTime(r.timestamp, true)}</span>
                  <span
                    aria-hidden="true"
                    className={`hidden size-7 items-center justify-center rounded-lg font-mono text-xs font-semibold sm:inline-flex ${look.tile}`}
                  >
                    {look.glyph}
                  </span>
                  <span className="flex min-w-0 flex-col gap-0.5">
                    <span className="text-sm">
                      <span className="font-mono font-semibold">{r.actor}</span> {look.verb}{' '}
                      {target &&
                        (r.merchant_id && !look.target ? (
                          <Link to={`/merchants/${encodeURIComponent(r.merchant_id)}`} className="font-mono font-semibold no-underline">
                            {target}
                          </Link>
                        ) : (
                          <span className="font-mono font-semibold">{target}</span>
                        ))}
                    </span>
                    <span className="font-mono text-xs text-muted-2">
                      {r.action} · role {r.role} · #{r.id}
                    </span>
                  </span>
                  <Chip>{r.role}</Chip>
                </li>
              )
            })}
          </ol>
          {audit.data && (
            <div className="border-t border-line px-5 py-3.5 text-[13px] text-muted">
              Showing {count(visible.length)} of the newest {count(rows.length)} entries.
            </div>
          )}
        </Card>
      )}
    </Page>
  )
}
