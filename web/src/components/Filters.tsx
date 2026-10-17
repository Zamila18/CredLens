/**
 * Filter controls (approved design: 02-review-queue-desktop.png): mint filter chips,
 * labelled dropdowns, a search box and the pager. Used by the queue, the decision log,
 * the consent list and the audit log. Filters sit in one row above the content; there is
 * no filter sidebar.
 */
import { ChevronLeft, ChevronRight, Search } from 'lucide-react'
import type { ReactNode } from 'react'

import { useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'

/** A round chip: mint when on, soft grey when off. */
export function FilterChip({ on, onClick, children }: { on: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={cn(
        'min-h-9 cursor-pointer rounded-full border px-4 py-1.5 font-sans text-sm',
        on ? 'border-mint-line bg-mint font-semibold text-lens-dark' : 'border-transparent bg-neutral-chip text-ink-2 hover:bg-seg',
      )}
    >
      {children}
    </button>
  )
}

type SelectOption = { value: string; label: string }

/** A small label above a native dropdown. */
export function FilterSelect({
  label,
  value,
  onChange,
  options,
  className,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  options: SelectOption[]
  className?: string
}) {
  return (
    <label className={cn('flex min-w-[150px] flex-col gap-1 text-[13px] font-medium text-ink-2', className)}>
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-h-11 cursor-pointer rounded-[10px] border border-control-line bg-card px-3 font-sans text-sm text-ink"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  )
}

/** The status-style segmented filter with a label above it ("Status: All | Pending | Decided"). */
export function FilterSegments<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string
  value: T
  onChange: (value: T) => void
  options: { value: T; label: string }[]
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[13px] font-medium text-ink-2">{label}</span>
      <div role="group" aria-label={label} className="inline-flex gap-0.5 rounded-[10px] border border-control-line bg-card p-[3px]">
        {options.map((o) => (
          <button
            key={o.value}
            type="button"
            aria-pressed={o.value === value}
            onClick={() => onChange(o.value)}
            className={cn(
              'min-h-9 cursor-pointer rounded-lg border-0 px-4 font-sans text-sm',
              o.value === value ? 'bg-mint font-semibold text-lens-dark' : 'bg-transparent text-ink-2 hover:bg-night-2',
            )}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  )
}

/** A search box with a magnifier. */
export function SearchBox({ value, onChange, placeholder, className }: { value: string; onChange: (value: string) => void; placeholder: string; className?: string }) {
  return (
    <label className={cn('flex min-h-11 items-center gap-2 rounded-[10px] border border-control-line bg-card px-3', className)}>
      <Search size={18} className="shrink-0 text-muted-2" aria-hidden="true" />
      <span className="sr-only">{placeholder}</span>
      <input
        type="search"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-w-0 flex-1 border-0 bg-transparent font-sans text-sm text-ink outline-none placeholder:text-muted-2"
      />
    </label>
  )
}

/** ‹  Page 2 of 84  › */
export function Pager({ page, pages, onPage }: { page: number; pages: number; onPage: (page: number) => void }) {
  const t = useT()
  if (pages <= 1) return null
  const btn =
    'flex size-10 cursor-pointer items-center justify-center rounded-[10px] border border-control-line bg-card text-ink hover:bg-night-2 disabled:cursor-not-allowed disabled:text-disabled disabled:hover:bg-card'
  return (
    <nav aria-label={t('Pages', 'পাতা')} className="flex items-center gap-3">
      <button type="button" className={btn} disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label={t('Previous page', 'আগের পাতা')}>
        <ChevronLeft size={18} aria-hidden="true" />
      </button>
      <span className="text-sm text-ink-2 tabular">{t(`Page ${page} of ${pages}`, `পাতা ${page} / ${pages}`)}</span>
      <button type="button" className={btn} disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label={t('Next page', 'পরের পাতা')}>
        <ChevronRight size={18} aria-hidden="true" />
      </button>
    </nav>
  )
}
