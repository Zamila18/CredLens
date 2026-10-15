/** StatTile: white card with a small label, a big mono number and an optional caption. */
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

type Props = {
  label: string
  value: ReactNode
  caption?: string
  /** Extra classes for the number, e.g. "text-peri-text" for Needs more info. */
  valueClassName?: string
}

export function StatTile({ label, value, caption, valueClassName }: Props) {
  return (
    <div className="flex flex-col gap-1 rounded-[14px] border border-card-line bg-card px-[18px] py-4">
      <span className="text-[13px] text-muted">{label}</span>
      <span className={cn('font-mono text-[28px] font-semibold tabular', valueClassName)}>{value}</span>
      {caption && <span className="text-xs text-muted-2">{caption}</span>}
    </div>
  )
}
