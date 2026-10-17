/** Page layout pieces shared by every screen: the padded column, its header, cards. */
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

/** The content column, max 1240px wide, aligned with the banner above it. */
export function Page({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  return (
    <div className={cn('box-border flex w-full flex-col gap-6 px-4 pt-6 pb-14 sm:px-8', wide ? 'max-w-[1240px]' : 'max-w-[1240px]')}>
      {children}
    </div>
  )
}

/** Page title (DM Sans, 32px bold), one plain sentence under it, an optional right-hand slot. */
export function PageHeader({ title, description, aside }: { title: ReactNode; description?: ReactNode; aside?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div className="flex flex-col gap-1.5">
        <h1 className="m-0 text-[28px] leading-9 font-bold tracking-[-0.02em] sm:text-[32px] sm:leading-10">{title}</h1>
        {description && <p className="m-0 max-w-[820px] text-base text-body">{description}</p>}
      </div>
      {aside}
    </header>
  )
}

/** A white card: 14px radius, hairline border. */
export function Card({ children, className, id }: { children: ReactNode; className?: string; id?: string }) {
  return (
    <section id={id} className={cn('rounded-card border border-card-line bg-card', className)}>
      {children}
    </section>
  )
}

/** A section card with a title that says what it answers, and an optional plain answer. */
export function Section({
  title,
  answer,
  aside,
  children,
  className,
  id,
}: {
  title: ReactNode
  answer?: ReactNode
  aside?: ReactNode
  children?: ReactNode
  className?: string
  id?: string
}) {
  return (
    <Card id={id} className={cn('flex flex-col gap-4 p-5 sm:p-6', className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <h2 className="m-0 text-[20px] leading-7 font-semibold sm:text-[22px]">{title}</h2>
          {answer && <p className="m-0 max-w-[860px] text-[15px] text-body">{answer}</p>}
        </div>
        {aside}
      </div>
      {children}
    </Card>
  )
}

/** Small label above a value (13px). */
export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cn('text-[13px] font-medium text-muted-2', className)}>{children}</span>
}

/** The mint strip of headline counts (queue, consent): label, then a big number. */
export function SummaryStrip({ items, label }: { items: { label: string; value: string; muted?: boolean; help?: string }[]; label: string }) {
  return (
    <section
      aria-label={label}
      className="mint-wash grid grid-cols-2 gap-y-4 rounded-card border border-mint-line px-2 py-4 md:grid-cols-4 md:divide-x md:divide-mint-line"
    >
      {items.map((item) => (
        <div key={item.label} className="flex flex-col gap-0.5 px-4">
          <span className="text-sm text-body">{item.label}</span>
          <span className={cn('font-display text-[28px] leading-9 font-bold tabular', item.muted ? 'text-[#5F6B80]' : 'text-ink')}>{item.value}</span>
          {item.help && <span className="text-xs text-muted-2">{item.help}</span>}
        </div>
      ))}
    </section>
  )
}
