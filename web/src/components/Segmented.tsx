/**
 * Segmented control: a row of buttons where one is on (the mockups' `.seg`).
 * `tone="dark"` is the sidebar version (Demo role).
 */
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

type Option<T extends string> = { value: T; label: ReactNode }

type Props<T extends string> = {
  options: Option<T>[]
  value: T
  onChange: (value: T) => void
  label: string
  tone?: 'light' | 'dark'
  className?: string
}

export function Segmented<T extends string>({ options, value, onChange, label, tone = 'light', className }: Props<T>) {
  const dark = tone === 'dark'
  return (
    <div
      role="group"
      aria-label={label}
      className={cn('inline-flex gap-0.5 p-[3px]', dark ? 'flex w-full rounded-[10px] bg-night-2' : 'rounded-[10px] bg-seg', className)}
    >
      {options.map((o) => {
        const on = o.value === value
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={on}
            onClick={() => onChange(o.value)}
            className={cn(
              'min-h-9 cursor-pointer rounded-lg border-0 font-sans',
              dark
                ? cn('flex-1 px-1 py-2 text-xs font-semibold', on ? 'bg-night-hi text-night' : 'bg-transparent text-night-text hover:text-white')
                : cn('px-3.5 py-2 text-[13px] font-medium', on ? 'bg-card text-ink shadow-[0_1px_2px_rgba(19,32,28,.12)]' : 'bg-transparent text-[#45514C] hover:text-ink'),
            )}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}
