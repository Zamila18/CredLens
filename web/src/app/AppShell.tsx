/**
 * The frame around every workspace page.
 *
 * Only for someone signed in (session cookie). Nobody signed in is sent to /login. While the server is asked who is there, a short wait is shown.
 *
 * Desktop (1024px and up): a fixed navy sidebar, and a slim top bar with the context: the
 * company and its environment, the role and the language.
 * Phone and tablet: the top bar keeps the menu button, the mark and the language switch; a
 * tab bar at the bottom holds the four places the current role uses most, and the menu
 * opens the full sidebar as a drawer.
 */
import { Menu, MoreHorizontal, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, Navigate, Outlet, useLocation } from 'react-router'

import { Wordmark } from '@/components/Brand'
import { pick, useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { HOME, PHONE_TABS, ROLE_NAMES, isActive } from './navigation'
import { useSession, type Lang } from './session-context'
import { NotificationBell } from './NotificationBell'
import { Sidebar } from './Sidebar'

/** English / বাংলা: the language of the whole product, kept across pages and reloads. */
export function LanguageSwitch({ tone = 'light' }: { tone?: 'light' | 'compact' }) {
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
            'cursor-pointer rounded-[9px] border-0 font-semibold',
            tone === 'compact' ? 'min-h-9 px-3 text-[13px]' : 'min-h-9 px-4 text-sm',
            lang === o.value ? 'bg-lens-dark text-white' : 'bg-transparent text-ink-2 hover:bg-night-2',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

/** The one-line context every page carries: whose company, and that the tool supports a
 * person's decision. The model's training provenance is shown where a score is, not here. */
function ContextLine({ compact = false }: { compact?: boolean }) {
  const t = useT()
  const { me } = useSession()
  const env = me?.environment
  const envWords = env ? { benchmark: t('Benchmark', 'বেঞ্চমার্ক'), pilot: t('Pilot', 'পাইলট'), production: t('Production', 'প্রোডাকশন') }[env] : null
  return (
    <div className={cn('flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px]', compact ? 'text-muted-2' : 'text-ink-2')} role="note">
      <span className="font-semibold text-ink">{me?.organization_name ?? t('CredLens platform', 'CredLens প্ল্যাটফর্ম')}</span>
      {envWords && (
        <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-chip bg-amber-panel px-2.5 py-0.5 font-semibold text-amber-text">
          <span className="size-1.5 rounded-full bg-amber" aria-hidden="true" />
          {envWords}
        </span>
      )}
      <span className="text-muted-2">{t('Decision support only.', 'শুধু সিদ্ধান্তে সহায়তা।')}</span>
    </div>
  )
}

function PhoneTabs({ onMenu }: { onMenu: () => void }) {
  const { role } = useSession()
  const { pathname } = useLocation()
  const t = useT()
  return (
    <nav
      aria-label={t('Main places', 'প্রধান জায়গা')}
      className="fixed inset-x-0 bottom-0 z-30 grid border-t border-line bg-white pb-[env(safe-area-inset-bottom)] lg:hidden print:hidden"
      style={{ gridTemplateColumns: `repeat(${PHONE_TABS[role].length + 1}, minmax(0, 1fr))` }}
    >
      {PHONE_TABS[role].map((item) => {
        const active = isActive(item, pathname)
        return (
          <Link
            key={item.to}
            to={item.to}
            aria-current={active ? 'page' : undefined}
            className={cn('flex min-h-14 flex-col items-center justify-center gap-0.5 px-1 text-[11px] leading-tight no-underline', active ? 'font-semibold text-lens-dark' : 'text-muted-2')}
          >
            <item.icon size={20} strokeWidth={active ? 2.2 : 1.8} aria-hidden="true" />
            <span className="max-w-full truncate">{t(item.label, item.labelBn)}</span>
          </Link>
        )
      })}
      <button type="button" onClick={onMenu} className="flex min-h-14 cursor-pointer flex-col items-center justify-center gap-0.5 border-0 bg-transparent text-[11px] text-muted-2">
        <MoreHorizontal size={20} aria-hidden="true" />
        {t('More', 'আরও')}
      </button>
    </nav>
  )
}

export function AppShell() {
  const t = useT()
  const { pathname } = useLocation()
  const { user, me, lang, mode, role } = useSession()
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

  if (mode === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ground font-sans text-body" role="status">
        {t('Checking who is signed in…', 'কে সাইন ইন করেছেন দেখা হচ্ছে…')}
      </div>
    )
  }
  if (mode === 'signed_out') {
    return <Navigate to={`/login?next=${encodeURIComponent(pathname)}`} replace />
  }
  // An address one's role does not use: go to the role's own start page (the API refuses
  // anything out of scope anyway).
  if ((pathname === '/app' || pathname === '/app/') && HOME[role] !== '/app') {
    return <Navigate to={HOME[role]} replace />
  }

  return (
    <div className="min-h-screen bg-ground font-sans text-ink">
      {/* Desktop sidebar */}
      <div className="fixed inset-y-0 left-0 hidden w-[256px] lg:block print:hidden">
        <Sidebar />
      </div>

      {/* Phone and tablet drawer */}
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label={t('Menu', 'মেনু')}>
          <button type="button" className="absolute inset-0 cursor-default border-0 bg-ink/40" aria-label={t('Close the menu', 'মেনু বন্ধ করুন')} onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-[min(300px,86vw)] shadow-xl">
            <Sidebar />
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="absolute top-4 right-3 flex size-11 cursor-pointer items-center justify-center rounded-[10px] border-0 bg-transparent text-white hover:bg-deep-2"
              aria-label={t('Close the menu', 'মেনু বন্ধ করুন')}
            >
              <X size={22} aria-hidden="true" />
            </button>
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-col pb-20 lg:pb-0 lg:pl-[256px] print:pb-0 print:pl-0">
        <header className="sticky top-0 z-20 border-b border-line bg-white/95 backdrop-blur-sm print:static print:border-0">
          <div className="box-border flex min-h-14 w-full max-w-[1280px] items-center justify-between gap-3 px-4 sm:px-8">
            <div className="flex items-center gap-2 lg:hidden print:hidden">
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
              <Link to={HOME[role]} className="no-underline" aria-label={t('CredLens home', 'CredLens হোম')}>
                <Wordmark size="sm" />
              </Link>
            </div>
            <div className="hidden lg:block print:block">
              <ContextLine />
            </div>
            <div className="flex items-center gap-3 print:hidden">
              <span className="hidden items-center gap-2 rounded-full border border-line px-3 py-1 text-[13px] font-medium text-ink-2 md:inline-flex">
                <span className="size-2 rounded-full bg-lens" aria-hidden="true" />
                {me?.display_name ?? user} · {pick(ROLE_NAMES[role], lang)}
              </span>
              <NotificationBell />
              <LanguageSwitch tone="compact" />
            </div>
          </div>
          <div className="border-t border-line-soft px-4 py-1.5 sm:px-8 lg:hidden print:hidden">
            <ContextLine compact />
          </div>
        </header>
        <main key={pathname} className="route-enter min-w-0">
          <Outlet />
        </main>
      </div>
      <PhoneTabs onMenu={() => setOpen(true)} />
    </div>
  )
}
