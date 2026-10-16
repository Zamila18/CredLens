/**
 * Filter controls from the mockups: round filter chips (`.fchip`) and small labelled
 * dropdowns. Used by the queue, the decision log and the audit log.
 */
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'
import { useT } from '@/lib/i18n'

/** A round chip that is either on (dark) or off (white). */
export function FilterChip({ on, onClick, children }: { on: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={cn(
        'min-h-9 cursor-pointer rounded-full border px-3 py-2 font-sans text-[13px]',
        on ? 'border-ink bg-ink text-white' : 'border-control-line bg-card text-ink-2 hover:border-[#9FAAA3]',
      )}
    >
      {children}
    </button>
  )
}

type SelectOption = { value: string; label: string }

/** "Town tier [All ▾]": a label and a native dropdown, styled like the mockup. */
export function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  options: SelectOption[]
}) {
  return (
    <label className="flex items-center gap-1.5 text-[13px] text-muted">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-h-9 cursor-pointer rounded-lg border border-control-line bg-card px-2.5 py-2 font-sans text-[13px] text-ink"
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

/** Previous / next buttons with "Page 2 of 84" between them. */
export function Pager({ page, pages, onPage }: { page: number; pages: number; onPage: (page: number) => void }) {
  const t = useT()
  if (pages <= 1) return null
  const btn =
    'min-h-9 cursor-pointer rounded-lg border border-button-line bg-card px-3 font-sans text-[13px] font-semibold text-lens hover:bg-open-hover disabled:cursor-not-allowed disabled:text-disabled disabled:hover:bg-card'
  return (
    <nav aria-label={t('Pages', 'পাতা')} className="flex items-center gap-2">
      <button type="button" className={btn} disabled={page <= 1} onClick={() => onPage(page - 1)}>
        ‹ {t('Previous', 'আগের')}
      </button>
      <span className="font-mono text-xs text-muted tabular">
        {t(`Page ${page} of ${pages}`, `পাতা ${page} / ${pages}`)}
      </span>
      <button type="button" className={btn} disabled={page >= pages} onClick={() => onPage(page + 1)}>
        {t('Next', 'পরের')} ›
      </button>
    </nav>
  )
}
