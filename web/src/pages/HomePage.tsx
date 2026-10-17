/**
 * Home (approved design: 01-home-desktop.png, 01-home-bangla.png).
 *
 * Hero with the shop illustration and one real merchant's score card, two buttons into
 * the work, today's counts, how it works, the four promises, the data sources and a footer.
 *
 * Every number is live: the counts and the hero card come from GET /merchants (the review
 * queue, one audited read shared with the sidebar badge). The hero shows M000031 when it is
 * in the queue with a score, else the first Strong merchant; no score is ever made up.
 * A public data mode has no queue: the counts say so instead of showing zeros.
 */
import type { LucideIcon } from 'lucide-react'
import { ChartNoAxesColumn, Database, FileText, ScrollText, ShieldCheck, UserRound } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type { DataMode, Health, QueueItem } from '@/api/types'
import { useApi } from '@/api/useApi'
import heroLarge from '@/assets/hero-shop-1400.webp'
import heroSmall from '@/assets/hero-shop-800.webp'
import { BandChip } from '@/components/BandChip'
import { CoverageBar } from '@/components/CoverageBar'
import { count } from '@/lib/format'
import { useLang, useT } from '@/lib/i18n'
import { MODE_ORDER, hasQueue } from '@/lib/modes'
import { cn } from '@/lib/utils'

const HERO_MERCHANT = 'M000031'

/** The data sources strip: name, and what kind of data it is. */
const SOURCES: Record<DataMode, { en: string; bn: string; noteEn?: string; noteBn?: string }> = {
  synthetic_bd: { en: 'Synthetic, Bangladesh-shaped', bn: 'সিনথেটিক, বাংলাদেশের আদলে', noteEn: '(demo)', noteBn: '(ডেমো)' },
  taiwan_cc: { en: 'Taiwan credit cards', bn: 'তাইওয়ানের ক্রেডিট কার্ড' },
  india_ltfs: { en: 'India vehicle loans', bn: 'ভারতের গাড়ির ঋণ' },
  homecredit: { en: 'Home Credit', bn: 'হোম ক্রেডিট', noteEn: '(country not stated)', noteBn: '(দেশ উল্লেখ নেই)' },
  kiva_asia: { en: 'Kiva Asia', bn: 'কিভা এশিয়া' },
}

function SectionTitle({ children }: { children: string }) {
  return <h2 className="m-0 text-[22px] leading-7 font-semibold">{children}</h2>
}

function Tile({ label, value, help, muted }: { label: string; value: string; help: string; muted?: boolean }) {
  return (
    <div className="flex flex-col gap-1 rounded-card border border-card-line bg-card px-5 py-4">
      <span className="text-[15px] text-body">{label}</span>
      <span className={cn('font-display text-[40px] leading-[48px] font-bold tabular', muted ? 'text-[#5F6B80]' : 'text-ink')}>{value}</span>
      <span className="text-[13px] leading-[18px] text-muted-2">{help}</span>
    </div>
  )
}

function Step({ n, icon: Icon, title, text }: { n: string; icon: LucideIcon; title: string; text: string }) {
  return (
    <li className="flex gap-4 rounded-card border border-card-line bg-card p-5">
      <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-mint font-mono text-sm font-semibold text-lens-dark">{n}</span>
      <div className="flex flex-col gap-1.5">
        <Icon size={26} strokeWidth={1.6} className="text-lens-dark" aria-hidden="true" />
        <span className="font-display text-[17px] font-semibold text-ink">{title}</span>
        <span className="text-[15px] text-body">{text}</span>
      </div>
    </li>
  )
}

function Promise({ icon: Icon, children }: { icon: LucideIcon; children: ReactNode }) {
  return (
    <li className="flex items-center gap-4 rounded-[12px] border border-card-line bg-white px-5 py-4 text-[15px] text-ink-2">
      <Icon size={24} strokeWidth={1.6} className="shrink-0 text-lens-dark" aria-hidden="true" />
      <span>{children}</span>
    </li>
  )
}

/** The white score card that sits on the illustration. */
function HeroCard({ item }: { item: QueueItem }) {
  const t = useT()
  if (item.score == null || item.coverage == null) return null
  return (
    <Link
      to={`/merchants/${item.merchant_id}`}
      className="flex w-full flex-col gap-1 rounded-[14px] border border-card-line bg-white/95 p-3.5 sm:w-[200px] text-ink no-underline shadow-[0_8px_24px_rgba(17,27,66,.12)] hover:text-ink"
      aria-label={t(`Open merchant ${item.merchant_id}`, `মার্চেন্ট ${item.merchant_id} খুলুন`)}
    >
      <span className="font-mono text-sm font-semibold">{item.merchant_id}</span>
      <span className="text-[13px] text-body">{t('Readiness score', 'প্রস্তুতির স্কোর')}</span>
      <span className="flex items-center gap-3">
        <span className="font-display text-[36px] leading-[40px] font-bold tabular">{item.score}</span>
        <BandChip band={item.band ?? null} lowScoreWarning={item.low_score_warning} size="md" />
      </span>
      <CoverageBar coverage={item.coverage} band={item.band ?? null} wide />
    </Link>
  )
}

export function HomePage() {
  const t = useT()
  const lang = useLang()
  const health = useApi<Health>('/health')
  const mode = health.data?.data_mode
  const withQueue = hasQueue(mode)
  const queue = useApi<QueueItem[]>(withQueue ? '/merchants' : null)

  const items = queue.data ?? []
  const pending = items.filter((m) => m.status === 'pending')
  const hero =
    items.find((m) => m.merchant_id === HERO_MERCHANT && m.score != null) ??
    items.find((m) => m.band === 'Strong' && m.score != null)
  const loading = '…'
  const number = (n: number) => (queue.data ? count(n) : loading)

  return (
    <div className="box-border flex w-full max-w-[1240px] flex-col gap-9 px-4 pt-4 pb-10 sm:px-8">
      {/* Hero */}
      <section className="mint-wash grid overflow-hidden rounded-[16px] border border-card-line lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="flex flex-col justify-center gap-3 p-5 sm:px-8 sm:py-6">
          <span className="font-display text-lg font-bold text-ink">CredLens</span>
          <h1 className="m-0 text-[28px] leading-[34px] font-bold tracking-[-0.02em] sm:text-[34px] sm:leading-[40px]">
            {t('See a small shop’s readiness, with reasons.', 'ছোট দোকানের প্রস্তুতি দেখুন, কারণসহ।')}
          </h1>
          <p className="m-0 max-w-[500px] text-[15px] leading-[23px] text-body">
            {t(
              'Mokam purchases, REDX deliveries and Baki repayments, joined so your officers can decide with confidence.',
              'Mokam-এর কেনাকাটা, REDX-এর ডেলিভারি আর বাকির পরিশোধ একসাথে, যাতে আপনার কর্মকর্তারা আত্মবিশ্বাসের সাথে সিদ্ধান্ত নিতে পারেন।',
            )}
          </p>
          <div className="mt-1 flex flex-wrap gap-3">
            {withQueue && (
              <Link
                to="/queue"
                className="inline-flex min-h-11 items-center rounded-[10px] bg-lens-dark px-5 text-[15px] font-semibold text-white no-underline hover:bg-lens-hover hover:text-white"
              >
                {t('Open the review queue', 'পর্যালোচনার তালিকা খুলুন')}
              </Link>
            )}
            <Link
              to="/model"
              className="inline-flex min-h-11 items-center rounded-[10px] border border-lens-dark bg-white px-5 text-[15px] font-semibold text-lens-dark no-underline hover:bg-mint-2"
            >
              {t('See how the model was tested', 'মডেল কীভাবে পরীক্ষা হয়েছে দেখুন')}
            </Link>
          </div>
          <p className="m-0 text-[13px] text-body">
            {t('The score suggests. You decide, and the record keeps why.', 'স্কোর পরামর্শ দেয়। সিদ্ধান্ত আপনার, আর খাতায় থাকে কেন।')}
          </p>
        </div>
        <div className="relative flex flex-col">
        <div className="hero-art relative aspect-[1586/992] overflow-hidden lg:absolute lg:inset-0 lg:aspect-auto">
          <div className="hero-art-layer">
            <img
              src={heroLarge}
              srcSet={`${heroSmall} 800w, ${heroLarge} 1400w`}
              sizes="(min-width: 1024px) 50vw, 100vw"
              alt={t(
                'A painted illustration of a small grocery shop with a striped awning.',
                'ডোরাকাটা ছাউনির একটি ছোট মুদি দোকানের আঁকা ছবি।',
              )}
              width={1400}
              height={876}
            />
            {/* The shop's name on the board, as real text (the illustration's board is blank). */}
            <span
              lang="bn"
              aria-hidden="true"
              className="hero-art-sign font-bn font-semibold whitespace-nowrap text-white [text-shadow:0_1px_2px_rgba(0,0,0,.3)]"
            >
              মুদি দোকান
            </span>
          </div>
        </div>
          {/* On a phone the card sits under the picture; from tablet width up, on it. */}
          {hero && (
            <div className="p-4 sm:absolute sm:right-4 sm:bottom-4 sm:p-0">
              <HeroCard item={hero} />
            </div>
          )}
        </div>
      </section>

      {/* Today */}
      <section className="flex flex-col gap-4" aria-labelledby="today">
        <h2 id="today" className="m-0 text-[22px] leading-7 font-semibold">
          {t('Today', 'আজ')}
        </h2>
        {withQueue || !mode ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Tile
              label={t('Pending merchants', 'অপেক্ষমাণ মার্চেন্ট')}
              value={number(pending.length)}
              help={t('A loan is waiting for an officer’s decision.', 'একটি ঋণ কর্মকর্তার সিদ্ধান্তের অপেক্ষায়।')}
            />
            <Tile
              label={t('Needs more info', 'আরও তথ্য প্রয়োজন')}
              value={number(pending.filter((m) => m.band === 'Needs more info').length)}
              help={t('Too little evidence to lean on the score.', 'স্কোরের ওপর ভরসা করার মতো প্রমাণ কম।')}
              muted
            />
            <Tile
              label={t('Consent missing, no score', 'অনুমতি নেই, স্কোর নেই')}
              value={number(pending.filter((m) => !m.consent_valid).length)}
              help={t('No valid consent: nothing is scored or shown.', 'বৈধ অনুমতি নেই: কিছুই স্কোর বা দেখানো হয় না।')}
            />
            <Tile
              label={t('Decided', 'সিদ্ধান্ত হয়েছে')}
              value={number(items.filter((m) => m.status === 'decided').length)}
              help={t('An officer has recorded a decision.', 'কর্মকর্তা সিদ্ধান্ত লিখে রেখেছেন।')}
            />
          </div>
        ) : (
          <p className="m-0 rounded-card border border-card-line bg-card px-5 py-4 text-[15px] text-body">
            {t(
              'This public data source has no review queue: every outcome is already known. Its model card shows what it supports.',
              'এই পাবলিক ডেটার কোনো পর্যালোচনার তালিকা নেই: সব ফলাফল আগেই জানা। এর মডেল কার্ডে দেখুন এটি কী দেখাতে পারে।',
            )}
          </p>
        )}
        {queue.error && (
          <p className="m-0 text-sm text-body">
            {t('The counts could not be loaded: ', 'সংখ্যাগুলো আনা যায়নি: ')}
            {queue.error.message}
          </p>
        )}
      </section>

      {/* How it works */}
      <section className="flex flex-col gap-4">
        <SectionTitle>{t('How it works', 'কীভাবে কাজ করে')}</SectionTitle>
        <ol className="m-0 grid list-none gap-4 p-0 md:grid-cols-3">
          <Step
            n="01"
            icon={Database}
            title={t('Join the records', 'রেকর্ডগুলো একসাথে')}
            text={t('Purchases, deliveries and repayments, in one view.', 'কেনাকাটা, ডেলিভারি আর পরিশোধ, এক জায়গায়।')}
          />
          <Step
            n="02"
            icon={FileText}
            title={t('A readiness score', 'প্রস্তুতির স্কোর')}
            text={t('With its reasons and a separate coverage figure.', 'কারণসহ, আর আলাদা করে কভারেজ।')}
          />
          <Step
            n="03"
            icon={UserRound}
            title={t('The officer decides', 'সিদ্ধান্ত কর্মকর্তার')}
            text={t('And the record keeps why.', 'আর খাতায় থাকে কেন।')}
          />
        </ol>
      </section>

      {/* Promises */}
      <section className="flex flex-col gap-4 rounded-[16px] border border-card-line bg-card p-5 sm:p-6">
        <SectionTitle>{t('Built around an officer’s judgment', 'কর্মকর্তার বিচারকে ঘিরে তৈরি')}</SectionTitle>
        <ul className="m-0 grid list-none gap-3 p-0 md:grid-cols-2">
          <Promise icon={ShieldCheck}>
            <b className="font-semibold text-ink">{t('Decision support only:', 'শুধু সিদ্ধান্তে সহায়তা:')}</b>{' '}
            {t('an officer decides.', 'সিদ্ধান্ত নেন একজন কর্মকর্তা।')}
          </Promise>
          <Promise icon={FileText}>
            <b className="font-semibold text-ink">{t('Consent first:', 'আগে অনুমতি:')}</b>{' '}
            {t('no consent, no score.', 'অনুমতি নেই তো স্কোরও নেই।')}
          </Promise>
          <Promise icon={ScrollText}>{t('Every view and decision is audited.', 'প্রতিটি দেখা আর সিদ্ধান্ত অডিটে লেখা থাকে।')}</Promise>
          <Promise icon={ChartNoAxesColumn}>
            {t('Thin files get ‘Needs more info’, never a low score.', 'কম তথ্যের ফাইল পায় ‘আরও তথ্য প্রয়োজন’, কখনো কম স্কোর নয়।')}
          </Promise>
        </ul>
      </section>

      {/* Data sources */}
      <section className="flex flex-col gap-4">
        <SectionTitle>{t('Data sources', 'ডেটার উৎস')}</SectionTitle>
        <ul className="m-0 grid list-none gap-3 p-0 sm:grid-cols-2 lg:grid-cols-5">
          {MODE_ORDER.map((m) => {
            const source = SOURCES[m]
            const current = m === mode
            return (
              <li
                key={m}
                className={cn(
                  'flex flex-col gap-1.5 rounded-[12px] border px-4 py-3',
                  current ? 'border-mint-line bg-mint' : 'border-card-line bg-white',
                )}
                aria-current={current ? 'true' : undefined}
              >
                <span className="flex items-start gap-2 text-[15px] font-semibold text-ink">
                  <Database size={18} strokeWidth={1.7} className="mt-0.5 shrink-0" aria-hidden="true" />
                  <span>
                    {lang === 'bn' ? source.bn : source.en}
                    {source.noteEn && (
                      <span className="block text-[13px] font-normal text-muted-2">{lang === 'bn' ? source.noteBn : source.noteEn}</span>
                    )}
                  </span>
                </span>
                <span className="text-[13px] text-muted-2">
                  {m === 'synthetic_bd'
                    ? t('made-up merchants, no real people', 'বানানো মার্চেন্ট, কোনো আসল মানুষ নয়')
                    : t('public data, not ShopUp data', 'পাবলিক ডেটা, ShopUp-এর ডেটা নয়')}
                </span>
                {current && <span className="text-xs font-semibold text-lens-dark">{t('In use now', 'এখন চালু')}</span>}
              </li>
            )
          })}
        </ul>
      </section>

      <footer className="flex flex-wrap justify-between gap-2 border-t border-line pt-5 text-[13px] text-muted-2">
        <span>Team 4Bytes · 2026 Data, AI &amp; Policy APAC Hackathon</span>
        <span>{t('Prototype on synthetic and public data. Decision support only.', 'সিনথেটিক ও পাবলিক ডেটায় তৈরি প্রোটোটাইপ। শুধু সিদ্ধান্তে সহায়তা।')}</span>
      </footer>
    </div>
  )
}
