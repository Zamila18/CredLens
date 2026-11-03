/** The frame of the sign-in screens: the mark, the language switch and one centred card. */
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { LanguageSwitch } from '@/app/AppShell'
import { Wordmark } from '@/components/Brand'

export function AuthFrame({ title, lead, children, wide = false }: { title: string; lead: string; children: ReactNode; wide?: boolean }) {
  return (
    <div className="flex min-h-screen flex-col bg-ground font-sans text-ink">
      <header className="mx-auto flex w-full max-w-[1100px] items-center justify-between gap-3 px-4 py-5 sm:px-6">
        <Link to="/" className="no-underline" aria-label="CredLens">
          <Wordmark size="sm" />
        </Link>
        <LanguageSwitch tone="compact" />
      </header>
      <main className="flex flex-1 items-start justify-center px-4 pt-6 pb-16 sm:pt-14">
        <section className={`flex w-full ${wide ? "max-w-[640px]" : "max-w-[440px]"} flex-col gap-5 rounded-card border border-card-line bg-card p-6 shadow-[0_10px_30px_-18px_rgba(17,27,66,0.25)] sm:p-8`}>
          <div className="flex flex-col gap-1.5">
            <h1 className="m-0 font-display text-[26px] leading-8 font-bold tracking-[-0.01em]">{title}</h1>
            <p className="m-0 text-[15px] leading-[22px] text-body">{lead}</p>
          </div>
          {children}
        </section>
      </main>
    </div>
  )
}
