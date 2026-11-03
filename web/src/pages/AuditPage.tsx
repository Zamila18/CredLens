/**
 * Audit log (approved design: 09-audit-log-desktop.png), admin only: who viewed or changed
 * what, and when. GET /audit?limit=200|500|1000, newest first. Opening this view is itself
 * audited, so it is asked fresh every time (and the newest row is often this very view).
 * Times are stored in UTC and shown in Bangladesh time (UTC+06:00).
 */
import type { LucideIcon } from 'lucide-react'
import { Ban, ClipboardList, Eye, FileCheck2, FilePen, FileText, Info, NotebookPen, RefreshCw, ScrollText, Send, Upload, UserRound } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router'

import type { AuditEntry, Role } from '@/api/types'
import { useApi } from '@/api/useApi'
import { ErrorCallout } from '@/components/ErrorCallout'
import { FilterSelect } from '@/components/Filters'
import { Notice } from '@/components/Notice'
import { Card, Page, PageHeader } from '@/components/Page'
import { count, fmtBdTime } from '@/lib/format'
import { ROLE_TEXT, pick, useLang, useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'

/**
 * How an entry reads. English: "officer-1 opened the profile of M000031". Bangla puts the
 * verb after the target ("officer-1 M000031-এর প্রোফাইল খুলেছেন").
 */
type Look = { en: string; bnAfter: string; icon: LucideIcon; tile: string; target?: string; targetBn?: string }

const TILE = {
  read: 'bg-info-panel text-info',
  write: 'bg-mint text-lens-dark',
  file: 'bg-mint-2 text-lens-dark',
  answers: 'bg-peri-panel text-peri-text',
  refused: 'bg-amber-panel text-amber-text',
  plain: 'bg-ground text-ink-2',
}

/** A plain sentence and an icon tile for each action the API writes. */
function describe(action: string): Look {
  switch (action) {
    case 'view_profile':
      return { en: 'opened the profile of', bnAfter: '-এর প্রোফাইল খুলেছেন', icon: UserRound, tile: TILE.plain }
    case 'view_score':
      return { en: 'read the score of', bnAfter: '-এর স্কোর দেখেছেন', icon: Eye, tile: TILE.read }
    case 'view_consent':
      return { en: 'read the consent of', bnAfter: '-এর অনুমতি দেখেছেন', icon: FileCheck2, tile: TILE.read }
    case 'view_consents':
      return { en: 'opened', bnAfter: ' খুলেছেন', icon: FileCheck2, tile: TILE.read, target: 'the consent list', targetBn: 'অনুমতির তালিকা' }
    case 'view_queue':
      return { en: 'opened', bnAfter: ' খুলেছেন', icon: ClipboardList, tile: TILE.read, target: 'the review queue', targetBn: 'পর্যালোচনার তালিকা' }
    case 'record_decision':
      return { en: 'recorded a decision on', bnAfter: '-এর ব্যাপারে সিদ্ধান্ত রেখেছেন', icon: NotebookPen, tile: TILE.write }
    case 'record_questionnaire':
      return { en: 'saved questionnaire answers for', bnAfter: '-এর প্রশ্নাবলির উত্তর রেখেছেন', icon: FilePen, tile: TILE.answers }
    case 'request_consent':
      return { en: 'asked for the consent of', bnAfter: '-এর কাছে অনুমতি চেয়েছেন', icon: Send, tile: TILE.write }
    case 'view_audit_log':
      return { en: 'opened', bnAfter: ' খুলেছেন', icon: ScrollText, tile: TILE.plain, target: 'the audit log', targetBn: 'অডিট লগ' }
    case 'refused_score':
      return { en: 'was refused the score of (no valid consent)', bnAfter: '-এর স্কোর পাননি (বৈধ অনুমতি নেই)', icon: Ban, tile: TILE.refused }
    case 'refused_decision':
      return { en: 'was refused a decision on (no consent, or no loan waiting)', bnAfter: '-এর সিদ্ধান্ত রাখা যায়নি (অনুমতি নেই, বা ঋণ অপেক্ষায় নেই)', icon: Ban, tile: TILE.refused }
    case 'refused_questionnaire':
      return { en: 'was refused the questionnaire of', bnAfter: '-এর প্রশ্নাবলি রাখা যায়নি', icon: Ban, tile: TILE.refused }
    case 'import_bundle':
      return { en: 'imported', bnAfter: ' আমদানি করেছেন', icon: Upload, tile: TILE.file, target: 'a bundle of files', targetBn: 'একগুচ্ছ ফাইল' }
    case 'check_import_bundle':
      return { en: 'checked', bnAfter: ' যাচাই করেছেন', icon: FileText, tile: TILE.file, target: 'a bundle of files', targetBn: 'একগুচ্ছ ফাইল' }
    case 'refused_import_bundle':
      return { en: 'was refused an import of', bnAfter: ' আমদানি করতে পারেননি', icon: Ban, tile: TILE.refused, target: 'a bundle of files', targetBn: 'একগুচ্ছ ফাইল' }
  }
  if (action.startsWith('refused_import_')) {
    const table = action.slice('refused_import_'.length)
    return { en: 'was refused an import into', bnAfter: ' টেবিলে আমদানি করতে পারেননি', icon: Ban, tile: TILE.refused, target: table }
  }
  if (action.startsWith('check_import_')) {
    const table = action.slice('check_import_'.length)
    return { en: 'checked a file for', bnAfter: ' টেবিলের একটি ফাইল যাচাই করেছেন', icon: FileText, tile: TILE.file, target: table }
  }
  if (action.startsWith('import_')) {
    const table = action.slice('import_'.length)
    return { en: 'imported a file into', bnAfter: ' টেবিলে একটি ফাইল আমদানি করেছেন', icon: Upload, tile: TILE.file, target: table }
  }
  return { en: action.replace(/_/g, ' '), bnAfter: ` (${action})`, icon: Info, tile: TILE.plain }
}

const ROLE_CHIP: Record<string, string> = {
  admin: 'bg-info-panel text-info',
  officer: 'bg-amber-panel text-amber-text',
  viewer: 'bg-ground text-ink-2',
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
        title={
          <span className="flex flex-wrap items-center gap-3">
            {t('Audit log', 'অডিট লগ')}
            <span className="rounded-full bg-mint px-3 py-1 font-sans text-sm font-medium text-lens-dark">
              {t('Admin only · this view is itself audited', 'শুধু অ্যাডমিন · এই দেখাটাও অডিটে লেখা হয়')}
            </span>
          </span>
        }
        description={t(
          'Who viewed or changed what, and when. A profile read and a score read are each written before anything is shown. Newest first.',
          'কে কী দেখেছেন বা বদলেছেন, এবং কখন। প্রোফাইল বা স্কোর দেখানোর আগেই তা লেখা হয়। নতুনটি আগে।',
        )}
      />

      {audit.error ? (
        <ErrorCallout error={audit.error} />
      ) : (
        <Card className="flex flex-col gap-4 p-4 sm:p-5">
          <div className="flex flex-col gap-1">
            <h2 className="m-0 text-[18px] leading-7 font-semibold">{t('Who accessed or changed a record?', 'কে রেকর্ড দেখেছেন বা বদলেছেন?')}</h2>
            <p className="m-0 text-[14.5px] text-body">
              {t('Each entry identifies the person, action and time, so the work can be traced.', 'প্রতিটি এন্ট্রিতে ব্যক্তি, কাজ আর সময় থাকে, তাই কাজের হিসাব মেলানো যায়।')}
            </p>
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <FilterSelect
              className="flex-1"
              label={t('Actor', 'কে')}
              value={actor}
              onChange={setActor}
              options={[{ value: 'all', label: t('Everyone', 'সবাই') }, ...actors.map((a) => ({ value: a, label: a }))]}
            />
            <FilterSelect
              className="flex-1"
              label={t('Action', 'কাজ')}
              value={action}
              onChange={setAction}
              options={[{ value: 'all', label: t('All', 'সব') }, ...actions.map((a) => ({ value: a, label: a }))]}
            />
            <FilterSelect className="flex-1" label={t('Rows', 'সারি')} value={limit} onChange={setLimit} options={LIMITS.map((l) => ({ value: l, label: l }))} />
            <button
              type="button"
              onClick={audit.reload}
              className="inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-[10px] border border-mint-line bg-mint px-5 font-sans text-[15px] font-semibold text-lens-dark hover:bg-mint-2"
            >
              <RefreshCw size={17} aria-hidden="true" /> {t('Refresh', 'আবার আনুন')}
            </button>
          </div>
          <div className="flex flex-wrap justify-between gap-2 text-[13px] text-body">
            <span>{t('Times shown in Bangladesh time (UTC+06:00).', 'সময় বাংলাদেশ সময়ে (UTC+06:00)।')}</span>
            <span>{t(`Up to ${limit} audit entries are shown.`, `সর্বোচ্চ ${limit}টি এন্ট্রি দেখানো হয়।`)}</span>
          </div>

          <div className="overflow-x-auto rounded-[12px] border border-line" role="region" aria-label={t('Audit entries', 'অডিট এন্ট্রি')} tabIndex={0}>
            <table className="w-full min-w-[760px] border-collapse text-[14.5px]">
              <thead className="bg-ground">
                <tr className="text-left text-sm text-ink-2">
                  <th scope="col" className="px-4 py-3 font-semibold">{t('Time (Bangladesh time)', 'সময় (বাংলাদেশ)')}</th>
                  <th scope="col" className="px-4 py-3 font-semibold">{t('Event', 'ঘটনা')}</th>
                  <th scope="col" className="px-4 py-3 font-semibold">{t('Details', 'বিস্তারিত')}</th>
                  <th scope="col" className="px-4 py-3 font-semibold">{t('Role', 'ভূমিকা')}</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((r) => {
                  const look = describe(r.action)
                  const Icon = look.icon
                  const target = (lang === 'bn' ? (look.targetBn ?? look.target) : look.target) ?? r.merchant_id
                  const role = pick(ROLE_TEXT[r.role as Role] ?? { en: r.role, bn: r.role }, lang)
                  const targetNode =
                    target &&
                    (r.merchant_id && !look.target ? (
                      <Link to={`/app/merchants/${encodeURIComponent(r.merchant_id)}`} className="font-medium no-underline">
                        {target}
                      </Link>
                    ) : (
                      <span>{target}</span>
                    ))
                  return (
                    <tr key={r.id} className="border-t border-line">
                      <td className="px-4 py-3 whitespace-nowrap text-ink-2 tabular">{fmtBdTime(r.timestamp)}</td>
                      <td className="min-w-[300px] px-4 py-3">
                        <span className="flex items-center gap-3">
                          <span className={cn('flex size-8 shrink-0 items-center justify-center rounded-[10px]', look.tile)} aria-hidden="true">
                            <Icon size={16} />
                          </span>
                          <span className="text-ink">
                            {r.actor} {lang === 'bn' ? <>{targetNode}{look.bnAfter}</> : <>{look.en} {targetNode}</>}
                          </span>
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="rounded-[8px] bg-ground px-2.5 py-1 font-mono text-[13px] whitespace-nowrap text-ink-2">
                          {r.action} · #{r.id}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={cn('rounded-full px-3 py-1 text-[13px] font-semibold', ROLE_CHIP[r.role] ?? ROLE_CHIP.viewer)}>{role}</span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {audit.loading && <div className="px-5 py-10 text-center text-sm text-body">{t('Loading the audit log…', 'অডিট লগ আসছে…')}</div>}
            {audit.data && visible.length === 0 && <div className="px-5 py-10 text-center text-[15px] text-body">{t('No entries match these filters.', 'এই ফিল্টারে কোনো এন্ট্রি মেলেনি।')}</div>}
          </div>
          {audit.data && (
            <span className="text-sm text-body">
              {t(`Showing ${count(visible.length)} of the newest ${count(rows.length)} entries.`, `নতুন ${count(rows.length)}টি এন্ট্রির মধ্যে ${count(visible.length)}টি দেখানো হচ্ছে।`)}
            </span>
          )}
        </Card>
      )}

      <Notice tone="info" title={t('Why are reads recorded?', 'দেখাও কেন লেখা হয়?')}>
        {t(
          'Opening a merchant profile, reading a score and opening this log all leave an audit record. A refused attempt is recorded too.',
          'মার্চেন্টের প্রোফাইল খোলা, স্কোর দেখা আর এই লগ খোলা, সবই অডিটে লেখা থাকে। আটকে যাওয়া চেষ্টাও লেখা হয়।',
        )}
      </Notice>
    </Page>
  )
}
