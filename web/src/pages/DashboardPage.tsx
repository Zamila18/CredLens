/**
 * The company overview: what needs attention now. Every number is counted from the company's own
 * records; a company with nothing yet sees the next steps instead of figures.
 *
 * Calls GET /overview (counts, the evidence of the shops added in the app, data quality and
 * recent activity, all counted from the database), and for officers and viewers
 * GET /applications, for administrators GET /import-batches. Every tile links to the list its
 * number comes from, and every chart writes its numbers out. Nothing is estimated.
 */
import { FileSpreadsheet, KeyRound, MapPinned, UserRoundCog } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type { ApplicationRow, EmployeeOut, ImportBatchOut, Overview } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSession } from '@/app/session-context'
import { ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { Page, PageHeader } from '@/components/Page'
import { StatusTag } from '@/components/StatusTag'
import { ActivityList, MetricTile, Panel } from '@/components/Workspace'
import { fmtBdTime, fmtDate, taka } from '@/lib/format'
import { useT } from '@/lib/i18n'
import { READINESS } from '@/lib/statuses'

/** Most urgent first: an assessment that could not be updated, then missing evidence, then checks. */
const URGENCY: Record<ApplicationRow['readiness'], number> = { not_updated: 0, more_info_needed: 1, check_needed: 2, ready: 3 }

function QuickAction({ to, icon, title, text }: { to: string; icon: ReactNode; title: string; text: string }) {
  return (
    <Link to={to} className="flex min-w-0 items-center gap-3 rounded-panel border border-card-line bg-card p-4 no-underline transition-colors hover:border-lens hover:bg-mint-2">
      <span className="flex size-10 shrink-0 items-center justify-center rounded-[10px] bg-deep text-white">{icon}</span>
      <span className="flex min-w-0 flex-col">
        <span className="text-[15px] font-semibold text-ink">{title}</span>
        <span className="text-[13px] text-body">{text}</span>
      </span>
    </Link>
  )
}

function WaitingApplications({ rows }: { rows: ApplicationRow[] }) {
  const t = useT()
  const waiting = rows.filter((r) => !r.decision).sort((a, b) => URGENCY[a.readiness] - URGENCY[b.readiness] || b.entered_at.localeCompare(a.entered_at))
  if (!waiting.length) return <p className="m-0 text-sm text-body">{t('No application is waiting for a decision.', 'কোনো আবেদন সিদ্ধান্তের অপেক্ষায় নেই।')}</p>
  return (
    <ul className="m-0 flex list-none flex-col p-0">
      {waiting.slice(0, 6).map((r) => (
        <li key={r.application_id} className="border-t border-line first:border-t-0">
          <Link to={`/app/merchants/${encodeURIComponent(r.merchant_id)}`} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1.5 py-3 no-underline hover:bg-row-hover sm:px-1">
            <span className="flex min-w-0 flex-col">
              <span className="truncate text-[15px] font-semibold text-ink">{r.shop_name ?? r.merchant_id}</span>
              <span className="text-[13px] text-muted-2">
                {r.merchant_id} · {t(`applied ${fmtDate(r.business_date)}`, `আবেদন ${fmtDate(r.business_date)}`)}
              </span>
            </span>
            <span className="flex flex-wrap items-center gap-2">
              <span className="text-[15px] font-semibold text-ink tabular">{taka(r.requested_amount_bdt)}</span>
              <StatusTag status={READINESS[r.readiness]} />
            </span>
          </Link>
        </li>
      ))}
    </ul>
  )
}

function RecentImports({ rows }: { rows: ImportBatchOut[] }) {
  const t = useT()
  if (!rows.length) return <p className="m-0 text-sm text-body">{t('No spreadsheet has been imported yet.', 'এখনও কোনো স্প্রেডশিট আমদানি হয়নি।')}</p>
  return (
    <ul className="m-0 flex list-none flex-col p-0">
      {rows.slice(0, 5).map((b) => (
        <li key={b.batch_id} className="border-t border-line first:border-t-0">
          <Link to={`/app/imports/${encodeURIComponent(b.batch_id)}`} className="flex flex-wrap items-center justify-between gap-2 py-3 no-underline hover:bg-row-hover sm:px-1">
            <span className="flex min-w-0 items-center gap-2.5">
              <FileSpreadsheet size={18} aria-hidden="true" className="shrink-0 text-lens-dark" />
              <span className="flex min-w-0 flex-col">
                <span className="truncate text-[14.5px] font-medium text-ink">{b.file_name}</span>
                <span className="text-[12.5px] text-muted-2">
                  {b.shop_name ?? b.merchant_id} · {fmtBdTime(b.uploaded_at)}
                </span>
              </span>
            </span>
            <span className="text-[13px] text-body tabular">
              {t(`${b.rows_added} added · ${b.rows_skipped} skipped · ${b.rows_rejected} not read`, `${b.rows_added} যোগ · ${b.rows_skipped} বাদ · ${b.rows_rejected} পড়া যায়নি`)}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  )
}

export function DashboardPage() {
  const t = useT()
  const { role, isOwner } = useSession()
  const officer = role === 'credit_officer'
  const overview = useApi<Overview>('/overview', undefined, { noCache: true })
  const applications = useApi<ApplicationRow[]>('/applications', undefined, { noCache: true })
  const imports = useApi<ImportBatchOut[]>(officer ? '/import-batches' : null, undefined, { noCache: true })
  const people = useApi<EmployeeOut[]>(officer ? '/org/employees' : null, undefined, { noCache: true })
  const o = overview.data

  if (overview.error) return <Page><ErrorCallout error={overview.error} /></Page>
  if (!o) return <Page><LoadingState title={t('Loading the overview…', 'সারসংক্ষেপ আসছে…')} /></Page>

  const fsrs = (people.data ?? []).filter((p) => p.role === 'fsr' && p.status === 'active')
  const empty = o.merchants_total === 0 && o.applications_total === 0
  const waiting = (applications.data ?? []).filter((r) => !r.decision).length

  return (
    <Page>
      <PageHeader
        title={t('Overview', 'সারসংক্ষেপ')}
        description={t('What is happening in your company: merchants, field work, applications and decisions.', 'আপনার প্রতিষ্ঠানে কী চলছে: মার্চেন্ট, মাঠের কাজ, আবেদন ও সিদ্ধান্ত।')}
      />
      {empty ? (
        <Panel title={t('Get started', 'শুরু করুন')}>
          <p className="m-0 text-[15px] text-body">
            {t('Your company has no merchants yet. These three steps get the field team working; nothing on this page is made up.', 'আপনার প্রতিষ্ঠানে এখনও কোনো মার্চেন্ট নেই। এই তিন ধাপে মাঠকর্মীরা কাজ শুরু করতে পারবেন; এই পাতায় কিছুই বানানো নয়।')}
          </p>
          <div className="grid gap-3 sm:grid-cols-3">
            {isOwner && <QuickAction to="/app/invitations" icon={<KeyRound size={19} aria-hidden="true" />} title={t('1. Invite your FSRs', '১. FSR-দের আমন্ত্রণ করুন')} text={t('Make an invitation code and share it', 'একটি আমন্ত্রণ কোড বানিয়ে দিন')} />}
            <QuickAction to="/app/registrations/new" icon={<MapPinned size={19} aria-hidden="true" />} title={t('2. Add the first merchant', '২. প্রথম মার্চেন্ট যোগ করুন')} text={t('Register a shop with a signed consent form', 'সই করা সম্মতিপত্রসহ দোকান নিবন্ধন')} />
            <QuickAction to="/app/assignments" icon={<UserRoundCog size={19} aria-hidden="true" />} title={t('3. Assign it to an FSR', '৩. FSR-কে দিন')} text={t('The FSR then records daily business', 'FSR প্রতিদিনের ব্যবসা রাখবেন')} />
          </div>
        </Panel>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <MetricTile label={t('Merchants', 'মার্চেন্ট')} value={o.merchants_total} hint={t(`${o.shops_created_in_app} registered in the app`, `${o.shops_created_in_app}টি অ্যাপে নিবন্ধিত`)} to="/app/merchants" />
            <MetricTile label={t('Applications', 'আবেদন')} value={o.applications_total} hint={t(`${waiting} waiting for a decision`, `${waiting}টি সিদ্ধান্তের অপেক্ষায়`)} to="/app/applications" tone={waiting ? 'attention' : 'neutral'} />
            <MetricTile label={t('Assessments to redo', 'আবার করার মূল্যায়ন')} value={o.assessments_not_updated} to="/app/applications" tone={o.assessments_not_updated ? 'attention' : 'neutral'} />
            <MetricTile label={t('Decisions recorded', 'রাখা সিদ্ধান্ত')} value={o.decisions_total} to="/app/decisions" />
          </div>
          {officer && (
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <MetricTile label={t('Active FSRs', 'সক্রিয় FSR')} value={fsrs.length} to="/app/team" />
              <MetricTile label={t('FSRs with no shop', 'দোকান ছাড়া FSR')} value={fsrs.filter((p) => p.assigned_shops === 0).length} to="/app/assignments" />
              <MetricTile label={t('Spreadsheet imports', 'স্প্রেডশিট আমদানি')} value={o.import_batches} to="/app/imports" />
              <MetricTile label={t('Issued loans on record', 'রেকর্ডে দেওয়া ঋণ')} value={o.issued_loans} hint={t('Applications are not counted', 'আবেদন গোনা হয়নি')} />
            </div>
          )}
          <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
            <Panel title={t('Applications waiting', 'অপেক্ষমাণ আবেদন')} action={{ to: '/app/applications', label: t('All applications', 'সব আবেদন') }}>
              {applications.error ? <ErrorCallout error={applications.error} /> : applications.data ? <WaitingApplications rows={applications.data} /> : <LoadingState title={t('Loading…', 'আসছে…')} />}
            </Panel>
            <div className="flex min-w-0 flex-col gap-5">
              <Panel title={t('Recent activity', 'সাম্প্রতিক কার্যক্রম')}>
                <ActivityList items={o.recent} />
              </Panel>
              {officer && imports.data && (
                <Panel title={t('Recent spreadsheet imports', 'সাম্প্রতিক স্প্রেডশিট আমদানি')} action={{ to: '/app/imports', label: t('All imports', 'সব আমদানি') }}>
                  <RecentImports rows={imports.data} />
                </Panel>
              )}
            </div>
          </div>
        </>
      )}
    </Page>
  )
}
