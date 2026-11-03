/**
 * Pieces shared by the workspace lists and the dashboard: a metric tile that links to where
 * the number comes from, a titled panel, and the recent-activity list. Every number they
 * show is passed in from an API answer; nothing here computes or invents one.
 */
import type { LucideIcon } from 'lucide-react'
import { ArrowRight, FileSpreadsheet, NotebookPen, PenLine } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type { ActivityItem } from '@/api/types'
import { count, fmtBdTime, fmtDate } from '@/lib/format'
import { ACTION_TEXT, pick, useLang, useT, type Pair } from '@/lib/i18n'
import { cn } from '@/lib/utils'

export function MetricTile({
  label,
  value,
  hint,
  to,
  tone = 'neutral',
}: {
  label: string
  value: number | null | undefined
  hint?: string
  to?: string
  tone?: 'neutral' | 'attention'
}) {
  const body = (
    <>
      <span className="text-[13px] font-medium text-muted-2">{label}</span>
      <span className={cn('font-display text-[30px] leading-9 font-bold tabular', tone === 'attention' && value ? 'text-amber-text' : 'text-ink')}>
        {value == null ? '—' : count(value)}
      </span>
      {hint && <span className="text-[13px] leading-[18px] text-body">{hint}</span>}
    </>
  )
  const box = 'flex min-w-0 flex-col gap-1 rounded-panel border border-card-line bg-card p-4'
  return to ? (
    <Link to={to} className={cn(box, 'no-underline transition-colors hover:border-lens hover:bg-mint-2')}>
      {body}
    </Link>
  ) : (
    <div className={box}>{body}</div>
  )
}

export function Panel({
  title,
  action,
  children,
  className,
}: {
  title: string
  action?: { to: string; label: string }
  children: ReactNode
  className?: string
}) {
  return (
    <section className={cn('flex min-w-0 flex-col gap-3 rounded-card border border-card-line bg-card p-4 sm:p-5', className)}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="m-0 text-[17px] font-semibold text-ink">{title}</h2>
        {action && (
          <Link to={action.to} className="inline-flex items-center gap-1 text-sm font-semibold no-underline">
            {action.label}
            <ArrowRight size={15} aria-hidden="true" />
          </Link>
        )}
      </div>
      {children}
    </section>
  )
}

const RECORD_WORDS: Record<string, Pair> = {
  merchant: { en: 'Shop added', bn: 'দোকান যোগ হয়েছে' },
  purchase: { en: 'Purchase recorded', bn: 'কেনাকাটা রাখা হয়েছে' },
  delivery: { en: 'Delivery recorded', bn: 'ডেলিভারি রাখা হয়েছে' },
  payment: { en: 'Repayment recorded', bn: 'পরিশোধ রাখা হয়েছে' },
  visit: { en: 'Field visit recorded', bn: 'মাঠ পরিদর্শন রাখা হয়েছে' },
  application: { en: 'Application created', bn: 'আবেদন তৈরি হয়েছে' },
}

function activityIcon(item: ActivityItem): LucideIcon {
  if (item.kind === 'decision') return NotebookPen
  return item.entry_method === 'imported_spreadsheet' ? FileSpreadsheet : PenLine
}

/** Recent records and decisions, newest first, with real time and (for records) business date. */
export function ActivityList({ items }: { items: ActivityItem[] }) {
  const t = useT()
  const lang = useLang()
  if (!items.length) return <p className="m-0 text-sm text-body">{t('Nothing has been recorded yet.', 'এখনও কিছু রাখা হয়নি।')}</p>
  return (
    <ol className="m-0 flex list-none flex-col p-0">
      {items.map((item, i) => {
        const Icon = activityIcon(item)
        const what =
          item.kind === 'decision'
            ? `${t('Decision', 'সিদ্ধান্ত')}: ${item.officer_action ? pick(ACTION_TEXT[item.officer_action].short, lang) : ''}`
            : pick(RECORD_WORDS[item.record_type ?? ''] ?? { en: 'Record saved', bn: 'রেকর্ড রাখা হয়েছে' }, lang)
        return (
          <li key={`${item.at}-${i}`} className="flex gap-3 border-t border-line py-2.5 first:border-t-0 first:pt-0">
            <span className={cn('mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full', item.kind === 'decision' ? 'bg-amber-panel text-amber-text' : 'bg-mint text-lens-dark')}>
              <Icon size={15} aria-hidden="true" />
            </span>
            <span className="flex min-w-0 flex-1 flex-col gap-0.5">
              <span className="text-[14.5px] text-ink">
                <span className="font-medium">{what}</span>
                {item.entry_method === 'imported_spreadsheet' && <span className="text-body"> · {t('from a spreadsheet', 'স্প্রেডশিট থেকে')}</span>}
              </span>
              <Link to={`/app/merchants/${encodeURIComponent(item.merchant_id)}`} className="truncate text-[13px] no-underline">
                {item.shop_name ? `${item.shop_name} · ${item.merchant_id}` : item.merchant_id}
              </Link>
              <span className="text-[12px] text-muted-2">
                {fmtBdTime(item.at)} {t('(BD time)', '(বাংলাদেশ সময়)')}
                {item.actor && ` · ${item.actor}`}
                {item.business_date && ` · ${t('business date', 'ব্যবসার তারিখ')} ${fmtDate(item.business_date)}`}
              </span>
            </span>
          </li>
        )
      })}
    </ol>
  )
}
