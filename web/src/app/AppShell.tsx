/**
 * The frame around every page (approved design: 01-home-desktop.png).
 *
 * Desktop: a fixed white sidebar on the left; on the right a top bar with the
 * English / বাংলা switch, the source banner, then the page.
 * Phone and tablet (under 1024px): the sidebar becomes a drawer opened from the menu
 * button; the language switch, the banner and the page keep their order.
 */
import { Menu, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router'

import { useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { Banner } from './Banner'
import { useSession, type Lang } from './session-context'
import { Sidebar } from './Sidebar'

/** English / বাংলা: the language of the whole dashboard, kept across pages and reloads. */
export function LanguageSwitch() {
  const { lang, setLang } = useSession()
  const options: { value: Lang; label: string }[] = [
    { value: 'en', label: 'English' },
    { value: 'bn', label: 'বাংলা' },
  ]
  return (
    <div role="group" aria-label="Language / ভাষা" className="inline-flex gap-0.5 rounded-xl border border-control-line bg-white p-[3px]">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          lang={o.value}
          aria-pressed={lang === o.value}
          onClick={() => setLang(o.value)}
          className={cn(
            'min-h-9 cursor-pointer rounded-[9px] border-0 px-4 text-sm font-semibold',
            lang === o.value ? 'bg-lens-dark text-white' : 'bg-transparent text-ink-2 hover:bg-night-2',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function AppShell() {
  const t = useT()
  const { pathname } = useLocation()
  // The drawer remembers the page it was opened on, so going to another page closes it.
  const [openOn, setOpenOn] = useState<string | null>(null)
  const open = openOn === pathname
  const setOpen = (next: boolean) => setOpenOn(next ? pathname : null)
  const menuButton = useRef<HTMLButtonElement>(null)

  // Escape closes the drawer and gives focus back to the menu button.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpenOn(null)
        menuButton.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  return (
    <div className="min-h-screen bg-ground font-sans text-ink">
      {/* Desktop sidebar */}
      <div className="fixed inset-y-0 left-0 hidden w-[264px] border-r border-line lg:block">
        <Sidebar />
      </div>

      {/* Phone drawer */}
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label={t('Menu', 'মেনু')}>
          <button
            type="button"
            className="absolute inset-0 cursor-default border-0 bg-ink/30"
            aria-label={t('Close the menu', 'মেনু বন্ধ করুন')}
            onClick={() => setOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 w-[min(300px,86vw)] shadow-xl">
            <Sidebar />
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="absolute top-4 right-3 flex size-11 cursor-pointer items-center justify-center rounded-[10px] border-0 bg-transparent text-ink-2 hover:bg-night-2"
              aria-label={t('Close the menu', 'মেনু বন্ধ করুন')}
            >
              <X size={22} aria-hidden="true" />
            </button>
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-col lg:pl-[264px]">
        <div className="box-border flex w-full max-w-[1240px] flex-col gap-3 px-4 pt-4 sm:px-8 sm:pt-5">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 lg:hidden">
              <button
                ref={menuButton}
                type="button"
                onClick={() => setOpen(true)}
                aria-expanded={open}
                className="flex size-11 cursor-pointer items-center justify-center rounded-[10px] border border-control-line bg-white text-ink"
                aria-label={t('Open the menu', 'মেনু খুলুন')}
              >
                <Menu size={22} aria-hidden="true" />
              </button>
              <Link to="/" className="font-display text-xl font-bold text-ink no-underline">
                CredLens
              </Link>
            </div>
            <div className="ml-auto">
              <LanguageSwitch />
            </div>
          </div>
          <Banner />
        </div>
        <main className="min-w-0">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
