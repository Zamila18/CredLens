/**
 * How it works: the eight stages from a business's own records to an audited decision.
 * Each stage can be opened to see what it does and exactly what exists in this build
 * (catalog.ts). Two real screens from the product close the page.
 */
import { ArrowRight } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

import dashboard from '@/assets/showcase/dashboard.jpg'
import imported from '@/assets/showcase/import.jpg'
import { Reveal } from '@/components/Motion'
import { useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { AVAILABILITY, STAGES } from './catalog'
import { PublicLayout } from './PublicLayout'

export function HowItWorksPage() {
  const t = useT()
  const [open, setOpen] = useState(0)
  const stage = STAGES[open]
  return (
    <PublicLayout>
      <section className="mx-auto flex max-w-[1200px] flex-col gap-4 px-4 pt-14 pb-10 sm:px-6">
        <span className="text-[13px] font-semibold tracking-[0.08em] text-lens-dark uppercase">{t('How it works', 'কীভাবে কাজ করে')}</span>
        <h1 className="route-enter m-0 max-w-[820px] font-display text-[38px] leading-[44px] font-bold tracking-[-0.025em] text-ink sm:text-[50px] sm:leading-[56px]">
          {t('From a shop’s own records to a decision someone can explain.', 'দোকানের নিজের রেকর্ড থেকে এমন সিদ্ধান্ত, যা ব্যাখ্যা করা যায়।')}
        </h1>
        <p className="m-0 max-w-[680px] text-[18px] leading-[30px] text-ink-3">
          {t('Eight stages, each with a clear job. Select a stage to see what it does and what exists today.', 'আটটি ধাপ, প্রতিটির নির্দিষ্ট কাজ। একটি ধাপ বেছে নিয়ে দেখুন এটি কী করে আর আজ কী আছে।')}
        </p>
      </section>

      <section className="mx-auto max-w-[1200px] px-4 pb-16 sm:px-6">
        <ol className="m-0 grid list-none grid-cols-2 gap-2 p-0 sm:grid-cols-4 lg:grid-cols-8" role="tablist" aria-label={t('Stages', 'ধাপ')}>
          {STAGES.map((s, i) => (
            <li key={s.en} className="relative">
              <button
                type="button"
                role="tab"
                aria-selected={open === i}
                aria-controls="stage-panel"
                onClick={() => setOpen(i)}
                className={cn(
                  'lift flex h-full w-full cursor-pointer flex-col items-start gap-2 rounded-[14px] border p-3 text-left font-sans',
                  open === i ? 'border-lens bg-deep text-white' : 'border-line bg-white text-ink hover:border-lens',
                )}
              >
                <span className={cn('font-mono text-[12px]', open === i ? 'text-[#7fd1b9]' : 'text-muted-2')}>0{i + 1}</span>
                <span className="text-[14px] leading-5 font-semibold">{t(s.en, s.bn)}</span>
                <span className={cn('size-1.5 rounded-full', s.status === 'planned' ? 'bg-muted-2' : s.status === 'partial' ? 'bg-amber' : 'bg-band-strong')} aria-hidden="true" />
              </button>
            </li>
          ))}
        </ol>
        <div id="stage-panel" role="tabpanel" key={open} className="route-enter mt-4 grid gap-6 rounded-[18px] border border-line bg-white p-6 sm:p-8 lg:grid-cols-[1.2fr_1fr]">
          <div className="flex flex-col gap-3">
            <span className="font-mono text-sm text-muted-2">{t(`Stage ${open + 1} of ${STAGES.length}`, `ধাপ ${open + 1} / ${STAGES.length}`)}</span>
            <h2 className="m-0 font-display text-[28px] leading-9 font-bold text-ink">{t(stage.en, stage.bn)}</h2>
            <p className="m-0 text-[17px] leading-7 text-ink-3">{t(stage.textEn, stage.textBn)}</p>
          </div>
          <div className="flex flex-col gap-3 rounded-[14px] bg-paper p-5">
            <span className="text-[13px] font-semibold tracking-[0.06em] text-muted-2 uppercase">{t('In this build', 'এই সংস্করণে')}</span>
            <span className={cn('self-start rounded-full border px-2.5 py-0.5 text-[12px] font-semibold', AVAILABILITY[stage.status].tone)}>{t(AVAILABILITY[stage.status].en, AVAILABILITY[stage.status].bn)}</span>
            <p className="m-0 text-[15px] leading-6 text-ink-2">{t(stage.todayEn, stage.todayBn)}</p>
          </div>
        </div>
      </section>

      <section className="border-t border-line bg-white">
        <div className="mx-auto grid max-w-[1200px] gap-10 px-4 py-16 sm:px-6 lg:grid-cols-2">
          {[
            { src: dashboard, en: 'The officer starts from what needs a decision', bn: 'যেটিতে সিদ্ধান্ত দরকার, কর্মকর্তা সেখান থেকে শুরু করেন' },
            { src: imported, en: 'Every import is accounted for, row by row', bn: 'প্রতিটি আমদানির হিসাব, সারি ধরে' },
          ].map((shot, i) => (
            <Reveal key={shot.en} delay={i * 80} className="flex flex-col gap-3">
              <div className="overflow-hidden rounded-[14px] border border-card-line bg-deep shadow-[0_18px_40px_-24px_rgba(11,21,51,0.45)]">
                <img src={shot.src} alt={t(`${shot.en}: screenshot with synthetic data`, `${shot.bn}: সিনথেটিক ডেটাসহ স্ক্রিনশট`)} loading="lazy" className="block w-full bg-white" />
              </div>
              <span className="text-[16px] font-semibold text-ink">{t(shot.en, shot.bn)}</span>
            </Reveal>
          ))}
        </div>
        <div className="mx-auto max-w-[1200px] px-4 pb-16 sm:px-6">
          <Link to="/register" className="lift inline-flex min-h-12 items-center gap-2 rounded-[12px] bg-lens-dark px-6 font-semibold text-white no-underline hover:text-white">
            {t('Register your company', 'আপনার প্রতিষ্ঠান নিবন্ধন করুন')}
            <ArrowRight size={18} aria-hidden="true" />
          </Link>
        </div>
      </section>
    </PublicLayout>
  )
}
