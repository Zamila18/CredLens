/** Page layout pieces shared by every screen: the padded column and its header. */
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

/** The content column: 28–32px padding, max 1240px wide (1320 on the merchant page). */
export function Page({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  return (
    <div className={cn('box-border flex w-full flex-col gap-6 px-4 pt-7 pb-14 sm:px-8', wide ? 'max-w-[1320px]' : 'max-w-[1240px]')}>
      {children}
    </div>
  )
}

/** Page title (30/36 semibold), a sentence under it, and an optional right-hand slot. */
export function PageHeader({ title, description, aside }: { title: ReactNode; description?: ReactNode; aside?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div className="flex flex-col gap-1.5">
        <h1 className="m-0 text-[30px] leading-9 font-semibold tracking-[-0.01em]">{title}</h1>
        {description && <p className="m-0 max-w-[720px] text-[15px] text-muted">{description}</p>}
      </div>
      {aside}
    </header>
  )
}

/** A white card: 16px radius, hairline border. */
export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={cn('rounded-card border border-card-line bg-card', className)}>{children}</section>
}

/** Small uppercase label above a section (12px, .06em tracking). */
export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cn('text-xs font-semibold tracking-[.06em] text-muted uppercase', className)}>{children}</span>
}
