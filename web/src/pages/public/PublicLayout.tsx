/**
 * The public site's frame: a compact sticky header (mark, three section links, language,
 * "Explore the demo") and a footer with only what is true about the project.
 */
import { Menu, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link, NavLink } from 'react-router'

import { LanguageSwitch } from '@/app/AppShell'
import { Wordmark } from '@/components/Brand'
import { useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'

const SECTIONS = [
  { href: '/', en: 'Product', bn: 'প্রোডাক্ট' },
  { href: '/how-it-works', en: 'How it works', bn: 'কীভাবে কাজ করে' },
  { href: '/sources', en: 'Data sources', bn: 'ডেটার উৎস' },
  { href: '/trust', en: 'Trust and governance', bn: 'আস্থা ও শাসন' },
]

export function PublicLayout({ children }: { children: ReactNode }) {
  const t = useT()
  const [open, setOpen] = useState(false)
  return (
    <div className="min-h-screen bg-paper font-sans text-ink">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-white focus:px-3 focus:py-2">
        {t('Skip to content', 'মূল লেখায় যান')}
      </a>
      <header className="sticky top-0 z-30 border-b border-line/70 bg-paper/95 backdrop-blur-sm print:hidden">
        <div className="mx-auto flex h-16 max-w-[1200px] items-center justify-between gap-4 px-4 sm:px-6">
          <Link to="/" className="no-underline" aria-label={t('CredLens home', 'CredLens হোম')}>
            <Wordmark size="sm" />
          </Link>
          <nav aria-label={t('Sections', 'অংশ')} className="hidden items-center gap-7 md:flex">
            {SECTIONS.map((s) => (
              <NavLink
                key={s.href}
                to={s.href}
                end
                className={({ isActive }) =>
                  cn('relative py-1 text-[15px] font-medium no-underline transition-colors after:absolute after:inset-x-0 after:-bottom-0.5 after:h-0.5 after:rounded-full after:transition-transform after:duration-200', isActive ? 'text-ink after:scale-x-100 after:bg-lens' : 'text-ink-2 after:scale-x-0 after:bg-lens hover:text-lens-dark hover:after:scale-x-100')
                }
              >
                {t(s.en, s.bn)}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <div className="hidden sm:block">
              <LanguageSwitch />
            </div>
            <Link
              to="/register"
              className="hidden min-h-10 items-center rounded-[10px] border border-button-line bg-white px-4 text-sm font-semibold text-lens-dark no-underline hover:bg-open-hover lg:inline-flex"
            >
              {t('Register', 'নিবন্ধন')}
            </Link>
            <Link
              to="/login"
              className="hidden min-h-10 items-center rounded-[10px] bg-lens-dark px-4 text-sm font-semibold text-white no-underline hover:bg-lens-hover hover:text-white sm:inline-flex"
            >
              {t('Sign in', 'সাইন ইন')}
            </Link>
            <button
              type="button"
              className="flex size-11 cursor-pointer items-center justify-center rounded-[10px] border border-control-line bg-white text-ink md:hidden"
              aria-expanded={open}
              aria-controls="public-menu"
              aria-label={open ? t('Close the menu', 'মেনু বন্ধ করুন') : t('Open the menu', 'মেনু খুলুন')}
              onClick={() => setOpen(!open)}
            >
              {open ? <X size={20} aria-hidden="true" /> : <Menu size={20} aria-hidden="true" />}
            </button>
          </div>
        </div>
        <div id="public-menu" className={cn('border-t border-line bg-paper px-4 pb-5 md:hidden', open ? 'block' : 'hidden')}>
          <nav aria-label={t('Sections', 'অংশ')} className="flex flex-col py-2">
            {SECTIONS.map((s) => (
              <Link key={s.href} to={s.href} onClick={() => setOpen(false)} className="flex min-h-12 items-center border-b border-line text-base font-medium text-ink no-underline">
                {t(s.en, s.bn)}
              </Link>
            ))}
          </nav>
          <div className="flex flex-wrap items-center justify-between gap-3 pt-3">
            <LanguageSwitch />
            <Link to="/register" className="inline-flex min-h-11 items-center rounded-[10px] border border-button-line bg-white px-4 text-sm font-semibold text-lens-dark no-underline">
              {t('Register', 'নিবন্ধন')}
            </Link>
            <Link to="/login" className="inline-flex min-h-11 items-center rounded-[10px] bg-lens-dark px-4 text-sm font-semibold text-white no-underline hover:text-white">
              {t('Sign in', 'সাইন ইন')}
            </Link>
          </div>
        </div>
      </header>
      <main id="main">{children}</main>
      <footer className="border-t border-deep-line bg-deep text-[#c9d2ea] print:hidden">
        <div className="mx-auto grid max-w-[1200px] gap-10 px-4 py-14 sm:px-6 md:grid-cols-[1.4fr_1fr_1fr]">
          <div className="flex flex-col gap-3">
            <Wordmark size="sm" tone="light" />
            <p className="m-0 max-w-[420px] text-sm leading-6">
              {t(
                'Business evidence intelligence for responsible credit assessment. Built by Team 4Bytes; first presented at the 2026 Data, AI & Policy APAC Hackathon (Financial Health Frontiers).',
                'দায়িত্বশীল ঋণ মূল্যায়নের জন্য ব্যবসায়িক প্রমাণ-বুদ্ধিমত্তা। টিম 4Bytes-এর তৈরি; প্রথম উপস্থাপন ২০২৬ ডেটা, এআই অ্যান্ড পলিসি এপ্যাক হ্যাকাথনে (ফাইন্যান্সিয়াল হেলথ ফ্রন্টিয়ার্স)।',
              )}
            </p>
          </div>
          <div className="flex flex-col gap-2 text-sm">
            <span className="font-semibold text-white">{t('Product', 'প্রোডাক্ট')}</span>
            {SECTIONS.map((s) => (
              <Link key={s.href} to={s.href} className="text-[#c9d2ea] no-underline hover:text-white">
                {t(s.en, s.bn)}
              </Link>
            ))}
            <Link to="/register" className="text-[#c9d2ea] no-underline hover:text-white">
              {t('Register your company', 'আপনার প্রতিষ্ঠান নিবন্ধন করুন')}
            </Link>
          </div>
          <div className="flex flex-col gap-2 text-sm leading-6">
            <span className="font-semibold text-white">{t('This deployment', 'এই ইনস্টলেশন')}</span>
            <span>{t('A sandbox with synthetic data: no real customer appears.', 'সিনথেটিক ডেটার স্যান্ডবক্স: কোনো আসল গ্রাহক নেই।')}</span>
            <span>{t('Decision support only: a person decides, never the software.', 'শুধু সিদ্ধান্তে সহায়তা: সিদ্ধান্ত নেন একজন মানুষ, সফটওয়্যার নয়।')}</span>
            <div className="pt-2">
              <LanguageSwitch />
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
