/**
 * A short message in the flow of a page: what happened, or what to know before acting.
 *
 * Tones: info (neutral facts), success (an action the API confirmed), warning (something
 * needs attention, e.g. an assessment that is not current), error (an action failed).
 * Every tone has an icon and words; colour is never the only signal. Success and info are
 * announced politely to screen readers; warnings and errors at once.
 */
import type { LucideIcon } from 'lucide-react'
import { CircleAlert, CircleCheck, Info, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

export type NoticeTone = 'info' | 'success' | 'warning' | 'error'

const LOOK: Record<NoticeTone, { icon: LucideIcon; box: string; iconColor: string }> = {
  info: { icon: Info, box: 'border-[#CFE0F2] bg-info-panel', iconColor: 'text-info' },
  success: { icon: CircleCheck, box: 'border-mint-line bg-strong-panel', iconColor: 'text-band-strong' },
  warning: { icon: TriangleAlert, box: 'border-amber-chip bg-amber-panel', iconColor: 'text-amber-text' },
  error: { icon: CircleAlert, box: 'border-[#F3D0D0] bg-error-panel', iconColor: 'text-error' },
}

export function Notice({
  tone = 'info',
  title,
  children,
  action,
  className,
}: {
  tone?: NoticeTone
  title: ReactNode
  children?: ReactNode
  action?: ReactNode
  className?: string
}) {
  const look = LOOK[tone]
  const Icon = look.icon
  return (
    <div
      role={tone === 'error' || tone === 'warning' ? 'alert' : 'status'}
      className={cn('flex gap-3 rounded-panel border px-4 py-3', look.box, className)}
    >
      <Icon size={20} strokeWidth={1.9} className={cn('mt-0.5 shrink-0', look.iconColor)} aria-hidden="true" />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="text-[15px] font-semibold text-ink">{title}</span>
        {children && <div className="text-sm leading-[21px] text-ink-3">{children}</div>}
        {action && <div className="pt-1">{action}</div>}
      </div>
    </div>
  )
}
