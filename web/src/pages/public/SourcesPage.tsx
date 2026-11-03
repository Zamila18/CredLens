/**
 * Data sources: every kind of source CredLens is designed to take, grouped by what works
 * today and what is planned. Names of companies are examples of a category only; no
 * partnership or connection is implied, and the page says so.
 */
import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router'

import { Reveal } from '@/components/Motion'
import { useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { AVAILABILITY, SOURCES } from './catalog'
import { PublicLayout } from './PublicLayout'

export function SourcesPage() {
  const t = useT()
  const working = SOURCES.filter((s) => s.status !== 'planned')
  const planned = SOURCES.filter((s) => s.status === 'planned')
  return (
    <PublicLayout>
      <section className="mx-auto flex max-w-[1200px] flex-col gap-4 px-4 pt-14 pb-10 sm:px-6">
        <span className="text-[13px] font-semibold tracking-[0.08em] text-lens-dark uppercase">{t('Data sources', 'ডেটার উৎস')}</span>
        <h1 className="route-enter m-0 max-w-[820px] font-display text-[38px] leading-[44px] font-bold tracking-[-0.025em] text-ink sm:text-[50px] sm:leading-[56px]">
          {t('Bring evidence from wherever the business keeps it.', 'ব্যবসা যেখানে প্রমাণ রাখে, সেখান থেকেই আনুন।')}
        </h1>
        <p className="m-0 max-w-[700px] text-[18px] leading-[30px] text-ink-3">
          {t(
            'CredLens works with no integration at all: field teams and files are enough. Connected systems add more evidence when an organisation is authorised to share it. Every source keeps its own label on every record.',
            'CredLens কোনো সংযোগ ছাড়াই কাজ করে: মাঠকর্মী ও ফাইলই যথেষ্ট। কোনো প্রতিষ্ঠান অনুমোদিত হলে সংযুক্ত সিস্টেম আরও প্রমাণ যোগ করে। প্রতিটি রেকর্ডে তার উৎসের নাম থাকে।',
          )}
        </p>
      </section>

      {[
        { title: t('Working today', 'আজ চালু'), items: working },
        { title: t('Planned connectors', 'পরিকল্পিত সংযোগ'), items: planned },
      ].map((group) => (
        <section key={group.title} className="mx-auto max-w-[1200px] px-4 pb-14 sm:px-6">
          <h2 className="m-0 mb-5 text-[22px] font-semibold text-ink">{group.title}</h2>
          <ul className="m-0 grid list-none gap-4 p-0 sm:grid-cols-2 lg:grid-cols-3">
            {group.items.map((s, i) => (
              <Reveal as="li" key={s.en} delay={(i % 3) * 60} className="flex flex-col gap-3 rounded-[16px] border border-line bg-white p-5">
                <span className="flex items-center justify-between gap-3">
                  <span className={cn('flex size-11 items-center justify-center rounded-[12px]', s.status === 'planned' ? 'bg-neutral-chip text-ink-2' : 'bg-mint text-lens-dark')}>
                    <s.icon size={20} aria-hidden="true" />
                  </span>
                  <span className={cn('rounded-full border px-2.5 py-0.5 text-[12px] font-semibold', AVAILABILITY[s.status].tone)}>{t(AVAILABILITY[s.status].en, AVAILABILITY[s.status].bn)}</span>
                </span>
                <span className="text-[17px] font-semibold text-ink">{t(s.en, s.bn)}</span>
                <span className="text-[15px] leading-6 text-ink-3">{t(s.textEn, s.textBn)}</span>
                {s.examplesEn && <span className="text-[13px] text-muted-2">{t(s.examplesEn, s.examplesBn ?? s.examplesEn)}</span>}
              </Reveal>
            ))}
          </ul>
        </section>
      ))}

      <section className="bg-deep text-white">
        <div className="mx-auto grid max-w-[1200px] gap-8 px-4 py-16 sm:px-6 lg:grid-cols-2">
          <div className="flex flex-col gap-3">
            <h2 className="m-0 font-display text-[28px] leading-9 font-bold text-white">{t('What a connector must do before it is called connected', 'সংযুক্ত বলার আগে একটি সংযোগকে যা করতে হবে')}</h2>
            <p className="m-0 text-[16px] leading-7 text-[#c9d2ea]">
              {t(
                'Company names on this page are examples of a category. CredLens has no partnership with them and no live connection to any external platform yet.',
                'এই পাতার কোম্পানির নাম শুধু একটি ধরনের উদাহরণ। তাদের সাথে CredLens-এর কোনো অংশীদারিত্ব নেই, আর এখনও কোনো বাইরের প্ল্যাটফর্মের সাথে সরাসরি সংযোগ নেই।',
              )}
            </p>
          </div>
          <ol className="m-0 grid list-none gap-2 p-0 sm:grid-cols-2">
            {[
              t('Authorised access agreed with the organisation', 'প্রতিষ্ঠানের সাথে অনুমোদিত প্রবেশাধিকার'),
              t('Connection tested', 'সংযোগ পরীক্ষিত'),
              t('Fields discovered and mapped', 'ফিল্ড খুঁজে মেলানো'),
              t('Merchants matched, with people confirming', 'মার্চেন্ট মেলানো, মানুষ নিশ্চিত করেন'),
              t('Preview and validation before saving', 'রাখার আগে দেখে নেওয়া ও যাচাই'),
              t('Origin and audit on every record', 'প্রতিটি রেকর্ডে উৎস ও অডিট'),
              t('Sync history and reconciliation', 'সিঙ্কের ইতিহাস ও মিলিয়ে দেখা'),
              t('Access that can be revoked', 'প্রবেশাধিকার প্রত্যাহারযোগ্য'),
            ].map((step, i) => (
              <li key={step} className="flex gap-3 rounded-[12px] border border-deep-line px-4 py-3 text-[15px] text-[#e3e8f6]">
                <span className="font-mono text-[#7fd1b9]">{String(i + 1).padStart(2, '0')}</span>
                {step}
              </li>
            ))}
          </ol>
        </div>
        <div className="mx-auto max-w-[1200px] px-4 pb-16 sm:px-6">
          <Link to="/register" className="lift inline-flex min-h-12 items-center gap-2 rounded-[12px] bg-[#1fb58f] px-6 font-semibold text-deep no-underline hover:text-deep">
            {t('Register your company', 'আপনার প্রতিষ্ঠান নিবন্ধন করুন')}
            <ArrowRight size={18} aria-hidden="true" />
          </Link>
        </div>
      </section>
    </PublicLayout>
  )
}
