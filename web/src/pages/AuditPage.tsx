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
import { ROLE_TEXT, pick, useLang, useT } from '@/lib/i18n'
import type { Role } from '@/api/types'

/**
 * How an entry reads. English: "officer-1 opened the profile of M000031". Bangla puts
 * the verb after the target ("officer-1 M000031-এর প্রোফাইল খুলেছেন"), so it has the
 * words before and after the target.
 */
type Look = {
  verb: string
  bnBefore: string
  bnAfter: string
  glyph: string
  tile: string
  target?: string
  targetBn?: string
}

/** A plain sentence and a glyph tile for each action the API writes. */
function describe(action: string): Look {
  switch (action) {
    case 'view_profile':
      return { verb: 'opened the profile of', bnBefore: '', bnAfter: '-এর প্রোফাইল খুলেছেন', glyph: 'V', tile: 'bg-peri-chip text-peri-text' }
    case 'view_score':
      return { verb: 'read the score of', bnBefore: '', bnAfter: '-এর স্কোর দেখেছেন', glyph: 'S', tile: 'bg-peri-chip text-peri-text' }
    case 'view_consent':
      return { verb: 'read the consent of', bnBefore: '', bnAfter: '-এর অনুমতি দেখেছেন', glyph: 'C', tile: 'bg-neutral-chip text-neutral-text' }
    case 'record_decision':
      return { verb: 'recorded a decision on', bnBefore: '', bnAfter: '-এর ব্যাপারে সিদ্ধান্ত রেখেছেন', glyph: 'D', tile: 'bg-strong-chip text-lens-dark' }
    case 'record_questionnaire':
      return { verb: 'saved questionnaire answers for', bnBefore: '', bnAfter: '-এর প্রশ্নাবলির উত্তর রেখেছেন', glyph: 'Q', tile: 'bg-strong-chip text-lens-dark' }
    case 'view_audit_log':
      return {
        verb: 'opened',
        bnBefore: '',
        bnAfter: ' খুলেছেন',
        glyph: 'A',
        tile: 'bg-neutral-chip text-neutral-text',
        target: 'the audit log',
        targetBn: 'অডিট লগ',
      }
  }
  if (action.startsWith('check_import_')) {
    const table = action.slice('check_import_'.length)
    return { verb: 'checked a file for', bnBefore: '', bnAfter: ' টেবিলের একটি ফাইল যাচাই করেছেন', glyph: 'I', tile: 'bg-amber-chip text-amber-text', target: table }
  }
  if (action.startsWith('import_')) {
    const table = action.slice('import_'.length)
    return { verb: 'imported a file into', bnBefore: '', bnAfter: ' টেবিলে একটি ফাইল আমদানি করেছেন', glyph: 'I', tile: 'bg-amber-chip text-amber-text', target: table }
  }
  return { verb: action.replace(/_/g, ' '), bnBefore: action.replace(/_/g, ' '), bnAfter: '', glyph: '·', tile: 'bg-neutral-chip text-neutral-text' }
}

const LIMITS = ['200', '500', '1000']

export function AuditPage() {
  const t = useT()
  const lang = useLang()
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
        title={t('Audit log', 'অডিট লগ')}
        description={t(
          'Who viewed or changed what, and when. A profile read and a score read are each written before anything is shown. Newest first.',
          'কে কী দেখেছেন বা বদলেছেন, এবং কখন। প্রোফাইল বা স্কোর দেখানোর আগেই তা লেখা হয়। নতুনটি আগে।',
        )}
        aside={
          <span className="font-mono text-xs text-muted-2">
            {t('admin only · this view is itself audited', 'শুধু অ্যাডমিন · এই দেখাটাও অডিটে লেখা হয়')}
          </span>
        }
      />

      {audit.error ? (
        <ErrorCallout error={audit.error} />
      ) : (
        <Card className="overflow-hidden">
          <div className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-3.5">
            <FilterSelect
              label={t('Actor', 'কে')}
              value={actor}
              onChange={setActor}
              options={[{ value: 'all', label: t('Everyone', 'সবাই') }, ...actors.map((a) => ({ value: a, label: a }))]}
            />
            <FilterSelect
              label={t('Action', 'কাজ')}
              value={action}
              onChange={setAction}
              options={[{ value: 'all', label: t('All', 'সব') }, ...actions.map((a) => ({ value: a, label: a }))]}
            />
            <div className="flex items-center gap-2 sm:ml-auto">
              <FilterSelect label={t('Rows', 'সারি')} value={limit} onChange={setLimit} options={LIMITS.map((l) => ({ value: l, label: l }))} />
              <Button variant="outline" size="sm" onClick={audit.reload}>
                {t('Refresh', 'আবার আনুন')}
              </Button>
            </div>
          </div>
          {audit.loading && <div className="px-5 py-10 text-center text-sm text-muted">{t('Loading the audit log…', 'অডিট লগ আসছে…')}</div>}
          {audit.data && visible.length === 0 && (
            <div className="px-5 py-10 text-center text-sm text-muted">
              {t('No entries match these filters.', 'এই ফিল্টারে কোনো এন্ট্রি মেলেনি।')}
            </div>
          )}
          <ol className="m-0 list-none p-0">
            {visible.map((r) => {
              const look = describe(r.action)
              const target = (lang === 'bn' ? (look.targetBn ?? look.target) : look.target) ?? r.merchant_id
              const role = pick(ROLE_TEXT[r.role as Role] ?? { en: r.role, bn: r.role }, lang)
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
                      <span className="font-mono font-semibold">{r.actor}</span> {lang === 'bn' ? look.bnBefore : look.verb}{' '}
                      {target &&
                        (r.merchant_id && !look.target ? (
                          <Link to={`/merchants/${encodeURIComponent(r.merchant_id)}`} className="font-mono font-semibold no-underline">
                            {target}
                          </Link>
                        ) : (
                          <span className={lang === 'bn' && look.targetBn ? 'font-semibold' : 'font-mono font-semibold'}>{target}</span>
                        ))}
                      {lang === 'bn' && look.bnAfter}
                    </span>
                    <span className="font-mono text-xs text-muted-2">
                      {r.action} · {t('role', 'ভূমিকা')} {r.role} · #{r.id}
                    </span>
                  </span>
                  <Chip>{role}</Chip>
                </li>
              )
            })}
          </ol>
          {audit.data && (
            <div className="border-t border-line px-5 py-3.5 text-[13px] text-muted">
              {t(
                `Showing ${count(visible.length)} of the newest ${count(rows.length)} entries.`,
                `নতুন ${count(rows.length)}টি এন্ট্রির মধ্যে ${count(visible.length)}টি দেখানো হচ্ছে।`,
              )}
            </div>
          )}
        </Card>
      )}
    </Page>
  )
}
