/**
 * Portfolio (approved design: 05-portfolio-desktop.png): the manager's view of the whole book,
 * as "Portfolio in one minute" and five plain questions. Each question has a plain answer,
 * a picture of the numbers, and what they mean.
 *
 * Every number is real:
 * - GET /model/card: how each band repaid on the validation loans, and the group audit.
 * - GET /merchants: today's queue by band (pending merchants; outcomes not known yet).
 * - GET /decisions: how officers use the score, and decisions per day (Bangladesh time).
 * A public data mode has no queue and no decisions: questions 2 to 4 say so.
 */
import { ArrowRight, PieChart } from 'lucide-react'
import { useMemo, type ReactNode } from 'react'
import { Link } from 'react-router'

import type { Band, Decision, Health, ModelCard, QueueItem } from '@/api/types'
import { useApi } from '@/api/useApi'
import { ErrorCallout } from '@/components/ErrorCallout'
import { Card, Page, PageHeader } from '@/components/Page'
import { isOverride } from '@/lib/actions'
import { bdDay, count, fmtDate, pct } from '@/lib/format'
import { BAND_TEXT, MODE_TEXT, pick, useLang, useT, valueText } from '@/lib/i18n'
import { hasQueue } from '@/lib/modes'
import { cn } from '@/lib/utils'
import { num, textIn } from './model/metrics'

type Tone = 'strong' | 'review' | 'nmi' | 'none'

const TONE: Record<Tone, { panel: string; dot: string; head: string; bar: string }> = {
  strong: { panel: 'border-mint-line bg-mint-2', dot: 'bg-band-strong', head: 'text-lens-dark', bar: 'bg-band-strong' },
  review: { panel: 'border-amber-chip bg-amber-panel', dot: 'bg-band-review', head: 'text-amber-text', bar: 'bg-band-review' },
  nmi: { panel: 'border-peri-chip bg-peri-panel', dot: 'bg-band-nmi', head: 'text-peri-text', bar: 'bg-band-nmi' },
  none: { panel: 'border-line bg-ground', dot: 'bg-[#B4C3C8]', head: 'text-ink-2', bar: 'bg-[#B4C3C8]' },
}

/** One numbered question: the question, its plain answer, then the picture. */
function Question({ n, title, answer, children }: { n: number; title: string; answer: ReactNode; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-4 rounded-card border border-card-line bg-card p-5 sm:p-6" aria-labelledby={`q${n}`}>
      <div className="flex flex-col gap-1">
        <h2 id={`q${n}`} className="m-0 text-[22px] leading-7 font-semibold">
          <span className="text-lens-dark">{n}.</span> {title}
        </h2>
        <p className="m-0 text-base text-body">{answer}</p>
      </div>
      {children}
    </section>
  )
}

function BandHead({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span className={cn('flex items-center gap-2 text-[15px] font-semibold', TONE[tone].head)}>
      <span className={cn('size-3.5 rounded-full', TONE[tone].dot)} aria-hidden="true" />
      {children}
    </span>
  )
}

function Unavailable({ children }: { children: string }) {
  return <p className="m-0 rounded-[12px] border border-line bg-ground px-4 py-3 text-[15px] text-body">{children}</p>
}

/** 1. Do the bands mean anything? */
function BandsQuestion({ card }: { card: ModelCard }) {
  const t = useT()
  const lang = useLang()
  const m = card.metrics
  const rows: { band: Band; tone: Tone; share?: number; repaid?: number }[] = [
    { band: 'Strong', tone: 'strong', share: num(m, 'band_strong_share'), repaid: num(m, 'band_strong_share_repaid') },
    { band: 'Review', tone: 'review', share: num(m, 'band_review_share'), repaid: num(m, 'band_review_share_repaid') },
    { band: 'Needs more info', tone: 'nmi', share: num(m, 'band_needs_more_info_share'), repaid: num(m, 'band_needs_more_info_share_repaid') },
  ]
  const loans = num(m, 'validation_loans')
  const known = rows.every((r) => r.repaid !== undefined && r.share !== undefined)
  const in100 = (x?: number) => (x === undefined ? '—' : String(Math.round(x * 100)))
  const label = textIn(m, 'label', lang)

  return (
    <Question
      n={1}
      title={t('Do the bands mean anything?', 'ব্যান্ডগুলোর কি কোনো মানে আছে?')}
      answer={
        known
          ? t(
              `Of past loans the model called Strong, ${in100(rows[0].repaid)} in 100 were repaid; Review ${in100(rows[1].repaid)} in 100; Needs more info ${in100(rows[2].repaid)} in 100.`,
              `মডেল যেগুলোকে শক্তিশালী বলেছিল, সেসব পুরোনো ঋণের ১০০টিতে ${in100(rows[0].repaid)}টি পরিশোধ হয়েছে; পর্যালোচনা ১০০-তে ${in100(rows[1].repaid)}; আরও তথ্য প্রয়োজন ১০০-তে ${in100(rows[2].repaid)}।`,
            )
          : t('This source does not report how each band repaid.', 'এই উৎস জানায় না প্রতিটি ব্যান্ড কতটা পরিশোধ করেছে।')
      }
    >
      {known && (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            {rows.map((r) => (
              <div key={r.band} className={cn('flex flex-col gap-3 rounded-[12px] border p-4', TONE[r.tone].panel)}>
                <BandHead tone={r.tone}>{pick(BAND_TEXT[r.band], lang)}</BandHead>
                <span className="flex items-baseline gap-2">
                  <span className="font-display text-[32px] leading-10 font-bold text-ink tabular">{pct(r.repaid, 1)}</span>
                  <span className="text-[15px] text-body">{t('repaid', 'পরিশোধ')}</span>
                </span>
                <div className="h-2.5 overflow-hidden rounded-full bg-white" aria-hidden="true">
                  <span className={cn('block h-2.5 rounded-full', TONE[r.tone].bar)} style={{ width: pct(r.repaid, 1) }} />
                </div>
                <span className="text-sm text-body">
                  {t(`About ${in100(r.repaid)} of every 100 loans were repaid.`, `প্রতি ১০০টি ঋণের প্রায় ${in100(r.repaid)}টি পরিশোধ হয়েছে।`)}
                </span>
                <span className="flex items-center gap-3 border-t border-black/5 pt-3">
                  <span className="text-xl font-bold text-ink tabular">{pct(r.share)}</span>
                  <span className="text-[13px] leading-[18px] text-body">{t('Share of past loans in this category', 'পুরোনো ঋণের মধ্যে এই ধরনের ভাগ')}</span>
                </span>
                {r.band === 'Needs more info' && (
                  <span className="rounded-[10px] bg-white/70 px-3 py-2 text-[13px] leading-[18px] text-peri-body">
                    {t(
                      'Thin files are not bad files: these merchants repaid almost as often. They need more evidence, not a lower score.',
                      'কম তথ্য মানে খারাপ ফাইল নয়: এই মার্চেন্টরাও প্রায় সমান হারে পরিশোধ করেছেন। দরকার আরও প্রমাণ, কম স্কোর নয়।',
                    )}
                  </span>
                )}
              </div>
            ))}
          </div>
          <span className="text-[13px] text-body">
            {loans !== undefined &&
              t(
                `Measured on ${count(loans)} past loans the model had not trained on (${pick(MODE_TEXT[card.data_mode], lang)}).`,
                `মডেল যেগুলো থেকে শেখেনি এমন ${count(loans)}টি পুরোনো ঋণে মাপা (${pick(MODE_TEXT[card.data_mode], lang)})।`,
              )}{' '}
            {label && `${label}${lang === 'bn' ? '।' : '.'}`}
          </span>
        </>
      )}
    </Question>
  )
}

/** 2. How much work is waiting today? */
function WaitingQuestion({ queue }: { queue?: QueueItem[] }) {
  const t = useT()
  const lang = useLang()
  const pending = useMemo(() => (queue ?? []).filter((r) => r.status === 'pending'), [queue])
  const tiles: { tone: Tone; name: string; n: number; link: string }[] = [
    { tone: 'strong', name: pick(BAND_TEXT.Strong, lang), n: pending.filter((r) => r.band === 'Strong').length, link: 'Strong' },
    { tone: 'review', name: pick(BAND_TEXT.Review, lang), n: pending.filter((r) => r.band === 'Review').length, link: 'Review' },
    { tone: 'nmi', name: pick(BAND_TEXT['Needs more info'], lang), n: pending.filter((r) => r.band === 'Needs more info').length, link: 'Needs more info' },
    { tone: 'none', name: t('No consent (no score)', 'অনুমতি নেই (স্কোর নেই)'), n: pending.filter((r) => !r.consent_valid).length, link: 'none' },
  ]
  return (
    <Question
      n={2}
      title={t('How much work is waiting today?', 'আজ কত কাজ অপেক্ষায়?')}
      answer={
        queue
          ? t(`${count(pending.length)} ${pending.length === 1 ? 'merchant is' : 'merchants are'} waiting for a decision. Their outcomes are not known yet.`, `${count(pending.length)} জন মার্চেন্ট সিদ্ধান্তের অপেক্ষায়। তাদের ফলাফল এখনও জানা নেই।`)
          : '…'
      }
    >
      {queue && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {tiles.map((tile) => (
            <div key={tile.link} className={cn('flex flex-col gap-2 rounded-[12px] border p-4', TONE[tile.tone].panel)}>
              <BandHead tone={tile.tone}>{tile.name}</BandHead>
              <span className="font-display text-[32px] leading-10 font-bold text-ink tabular">{count(tile.n)}</span>
              <span className="text-sm text-body">{t('merchants in this category are waiting for a decision.', 'জন মার্চেন্ট এই ধরনে সিদ্ধান্তের অপেক্ষায়।')}</span>
              <Link
                to={`/queue?status=pending&band=${encodeURIComponent(tile.link)}`}
                className="mt-auto inline-flex items-center gap-1 text-[15px] font-semibold no-underline"
              >
                {t('View in queue', 'তালিকায় দেখুন')} <ArrowRight size={16} aria-hidden="true" />
              </Link>
            </div>
          ))}
        </div>
      )}
    </Question>
  )
}

/** 3. How do officers use the score? */
function OfficersQuestion({ decisions }: { decisions: Decision[] }) {
  const t = useT()
  const accepts = decisions.filter((d) => d.officer_action === 'accept').length
  const overrides = decisions.filter((d) => isOverride(d.officer_action))
  const explained = overrides.filter((d) => (d.reason_text ?? '').trim() !== '').length
  const moreInfo = decisions.filter((d) => d.officer_action === 'needs_more_info').length
  const base = accepts + overrides.length
  const rate = base ? overrides.length / base : undefined

  return (
    <Question
      n={3}
      title={t('How do officers use the score?', 'কর্মকর্তারা স্কোর কীভাবে ব্যবহার করেন?')}
      answer={
        decisions.length === 0
          ? t('No decisions recorded yet. Officers record them on a merchant’s page.', 'এখনও কোনো সিদ্ধান্ত রাখা হয়নি। কর্মকর্তারা মার্চেন্টের পাতায় সিদ্ধান্ত রাখেন।')
          : t(
              `Officers accepted ${count(accepts)} ${accepts === 1 ? 'suggestion' : 'suggestions'}, overrode ${count(overrides.length)} (${count(explained)} with a written reason) and asked for more information on ${count(moreInfo)}.`,
              `কর্মকর্তারা ${count(accepts)}টি পরামর্শ মেনেছেন, ${count(overrides.length)}টি বদলেছেন (${count(explained)}টিতে লিখিত কারণ), আর ${count(moreInfo)}টিতে আরও তথ্য চেয়েছেন।`,
            )
      }
    >
      {decisions.length > 0 && (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            {[
              { tone: 'strong' as Tone, name: t('Accepted', 'মেনে নেওয়া'), n: accepts, note: t('suggestions kept', 'পরামর্শ রাখা হয়েছে') },
              { tone: 'review' as Tone, name: t('Overridden, with a reason', 'কারণসহ পরিবর্তন'), n: overrides.length, note: t('decisions changed with reasons', 'কারণসহ বদলানো সিদ্ধান্ত') },
              { tone: 'nmi' as Tone, name: t('Asked for more info', 'আরও তথ্য চাওয়া'), n: moreInfo, note: t('requests for evidence', 'প্রমাণের অনুরোধ') },
            ].map((tile) => (
              <div key={tile.name} className={cn('flex flex-col gap-1.5 rounded-[12px] border p-4', TONE[tile.tone].panel)}>
                <BandHead tone={tile.tone}>{tile.name}</BandHead>
                <span className="font-display text-[32px] leading-10 font-bold text-ink tabular">{count(tile.n)}</span>
                <span className="text-sm text-body">{tile.note}</span>
              </div>
            ))}
          </div>
          <div className="grid gap-4 rounded-[12px] border border-line p-4 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] md:divide-x md:divide-line">
            <div className="flex flex-col gap-2">
              <span className="text-[15px] font-semibold text-ink">{t('Override rate', 'পরিবর্তনের হার')}</span>
              <div className="flex items-center gap-4">
                <span className="font-display text-[32px] leading-10 font-bold text-ink tabular">{rate === undefined ? '—' : pct(rate)}</span>
                <div className="h-3 flex-1 overflow-hidden rounded-full bg-track" aria-hidden="true">
                  <span className="block h-3 rounded-full bg-band-strong" style={{ width: `${(rate ?? 0) * 100}%` }} />
                </div>
                <span className="text-sm text-body tabular">{t(`${count(overrides.length)} of ${count(base)}`, `${count(base)}-এর মধ্যে ${count(overrides.length)}`)}</span>
              </div>
              <span className="text-[13px] text-body">
                {t(
                  `${count(overrides.length)} of ${count(base)} accepts and overrides were changed. Requests for information are excluded from this rate.`,
                  `${count(base)}টি মেনে নেওয়া ও পরিবর্তনের মধ্যে ${count(overrides.length)}টি বদলানো। তথ্যের অনুরোধ এই হারে ধরা হয়নি।`,
                )}
              </span>
            </div>
            <p className="m-0 text-sm leading-[21px] text-body md:pl-5">
              {t(
                'If officers almost never override, they may be accepting the score without reading it. If they override about half the time, the score is not helping. Both are worth a conversation.',
                'কর্মকর্তারা প্রায় কখনো না বদলালে হয়তো না পড়েই স্কোর মেনে নিচ্ছেন। প্রায় অর্ধেক সময় বদলালে স্কোর কাজে আসছে না। দুটোই আলোচনার বিষয়।',
              )}
            </p>
          </div>
        </>
      )}
    </Question>
  )
}

/** 4. When were decisions made? A bar per day (Bangladesh time), drawn to scale. */
function DaysQuestion({ decisions }: { decisions: Decision[] }) {
  const t = useT()
  const days = useMemo(() => {
    const byDay = new Map<string, number>()
    for (const d of decisions) {
      const day = bdDay(d.decided_at)
      byDay.set(day, (byDay.get(day) ?? 0) + 1)
    }
    return [...byDay.entries()].sort(([a], [b]) => a.localeCompare(b)).slice(-14)
  }, [decisions])
  const top = Math.max(1, ...days.map(([, n]) => n))
  const busiest = days.reduce<[string, number] | null>((best, d) => (!best || d[1] > best[1] ? d : best), null)

  return (
    <Question
      n={4}
      title={t('When were decisions made?', 'সিদ্ধান্তগুলো কবে নেওয়া হয়েছে?')}
      answer={
        busiest
          ? t(`Most decisions were made on ${fmtDate(busiest[0])}.`, `সবচেয়ে বেশি সিদ্ধান্ত হয়েছে ${fmtDate(busiest[0])} তারিখে।`)
          : t('No decisions recorded yet.', 'এখনও কোনো সিদ্ধান্ত রাখা হয়নি।')
      }
    >
      {days.length > 0 && (
        <div className="flex gap-3">
          <span className="flex w-5 items-center justify-center text-xs text-body [writing-mode:vertical-rl] rotate-180">
            {t('Number of decisions', 'সিদ্ধান্তের সংখ্যা')}
          </span>
          <div className="flex flex-1 flex-col gap-2">
            <ol className="m-0 flex h-[200px] list-none items-end gap-3 border-b border-control-line p-0" aria-label={t('Decisions per day', 'দিনপ্রতি সিদ্ধান্ত')}>
              {days.map(([day, n]) => (
                <li key={day} className="flex h-full flex-1 flex-col items-center justify-end gap-1">
                  <span className="text-sm font-semibold text-ink tabular">{n}</span>
                  <span className="w-full max-w-[72px] rounded-t-[6px] bg-band-strong/35" style={{ height: `${(n / top) * 85}%` }} aria-hidden="true" />
                  <span className="sr-only">{`${fmtDate(day)}: ${n}`}</span>
                </li>
              ))}
            </ol>
            <div className="flex gap-3" aria-hidden="true">
              {days.map(([day]) => (
                <span key={day} className="flex-1 text-center text-xs text-body tabular">
                  {fmtDate(day)}
                </span>
              ))}
            </div>
            <span className="text-center text-xs text-body">{t('Date (Bangladesh time)', 'তারিখ (বাংলাদেশ সময়)')}</span>
          </div>
        </div>
      )}
    </Question>
  )
}

const GROUP_COLUMN: Record<string, { en: string; bn: string }> = {
  town_tier: { en: 'Town tier', bn: 'শহরের ধরন' },
  shop_type: { en: 'Shop type', bn: 'দোকানের ধরন' },
  has_trade_license: { en: 'Trade licence', bn: 'ট্রেড লাইসেন্স' },
}

type GroupRow = { column: string; group: unknown; loans?: number; share_repaid?: number; mean_score?: number; ranking?: string; calibration?: string }

/** 5. Does the model work differently for some groups? (the measured group audit) */
function GroupsQuestion({ card }: { card: ModelCard }) {
  const t = useT()
  const lang = useLang()
  const rows = (card.group_results ?? []) as GroupRow[]
  const findings = textIn(card.metrics, 'group_findings', lang)
  // The audit's own words (src/model/fairness.py): the worse of the ranking and calibration checks.
  const result = (r: GroupRow): { en: string; bn: string; tone: string } => {
    const both = [r.ranking, r.calibration]
    if (both.includes('flagged')) return { en: 'Gap flagged', bn: 'ফারাক চিহ্নিত', tone: 'bg-amber-chip text-amber-text' }
    if (both.some((v) => v?.startsWith('gap'))) return { en: 'Gap within the ranges', bn: 'সীমার মধ্যে ফারাক', tone: 'bg-neutral-chip text-ink-2' }
    if (both.some((v) => v?.startsWith('too few'))) return { en: 'Too few loans to measure', bn: 'মাপার মতো ঋণ কম', tone: 'bg-neutral-chip text-ink-2' }
    return { en: 'No gap', bn: 'ফারাক নেই', tone: 'bg-mint text-lens-dark' }
  }
  const groupName = (r: GroupRow) => {
    const column = GROUP_COLUMN[r.column] ? pick(GROUP_COLUMN[r.column], lang) : r.column
    const value = valueText(String(r.group), lang)
    return `${column} · ${value}`
  }
  return (
    <Question
      n={5}
      title={t('Does the model work differently for some groups?', 'মডেল কি কোনো দলের জন্য আলাদাভাবে কাজ করে?')}
      answer={findings ?? t('This source has no group audit.', 'এই উৎসের কোনো দলভিত্তিক যাচাই নেই।')}
    >
      {rows.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-[12px] border border-line" role="region" aria-label={t('Group results', 'দলভিত্তিক ফলাফল')} tabIndex={0}>
            <table className="w-full min-w-[640px] border-collapse text-[15px]">
              <thead className="bg-ground">
                <tr className="text-left text-sm text-ink-2">
                  <th scope="col" className="px-4 py-3 font-semibold">{t('Group', 'দল')}</th>
                  <th scope="col" className="px-4 py-3 text-right font-semibold">{t('Loans', 'ঋণ')}</th>
                  <th scope="col" className="px-4 py-3 text-right font-semibold">{t('Repaid', 'পরিশোধ')}</th>
                  <th scope="col" className="px-4 py-3 text-right font-semibold">{t('Average score', 'গড় স্কোর')}</th>
                  <th scope="col" className="px-4 py-3 text-center font-semibold">{t('Result', 'ফলাফল')}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={`${r.column}-${String(r.group)}-${i}`} className="border-t border-line">
                    <td className="px-4 py-2.5 text-ink">{groupName(r)}</td>
                    <td className="px-4 py-2.5 text-right tabular">{count(r.loans)}</td>
                    <td className="px-4 py-2.5 text-right tabular">{pct(r.share_repaid, 1)}</td>
                    <td className="px-4 py-2.5 text-right tabular">{r.mean_score == null ? '—' : r.mean_score.toFixed(1)}</td>
                    <td className="px-4 py-2.5 text-center">
                      <span className={cn('inline-flex rounded-full px-2.5 py-0.5 text-[13px] font-semibold whitespace-nowrap', result(r).tone)}>
                        {t(result(r).en, result(r).bn)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <span className="text-[13px] text-body">
            {t(
              'Groups overlap; do not add loan counts. These columns are used only to check the model, never to score anyone. We report gaps; we do not claim fairness.',
              'দলগুলো একটির সাথে আরেকটি মেশে; ঋণের সংখ্যা যোগ করবেন না। এই কলামগুলো শুধু মডেল যাচাইয়ে ব্যবহার হয়, কাউকে স্কোর দিতে নয়। আমরা ফারাক জানাই; ন্যায্যতার দাবি করি না।',
            )}
          </span>
        </>
      )}
    </Question>
  )
}

export function PortfolioPage() {
  const t = useT()
  const health = useApi<Health>('/health')
  const showQueue = hasQueue(health.data?.data_mode)
  const card = useApi<ModelCard>(health.data ? '/model/card' : null)
  const queue = useApi<QueueItem[]>(showQueue ? '/merchants' : null)
  const decisions = useApi<Decision[]>(showQueue ? '/decisions' : null, undefined, { noCache: true })

  const m = card.data?.metrics
  const strongRepaid = m ? num(m, 'band_strong_share_repaid') : undefined
  const waiting = queue.data?.filter((r) => r.status === 'pending').length
  const d = decisions.data ?? []
  const accepts = d.filter((x) => x.officer_action === 'accept').length
  const overrides = d.filter((x) => isOverride(x.officer_action)).length
  const moreInfo = d.filter((x) => x.officer_action === 'needs_more_info').length

  return (
    <Page>
      <PageHeader title={t('Portfolio', 'পোর্টফোলিও')} description={t('The manager’s view of the whole book.', 'পুরো ঋণ-খাতার ব্যবস্থাপকের দৃষ্টি।')} />

      <Card className="flex items-start gap-5 p-5 sm:p-6">
        <span className="flex size-16 shrink-0 items-center justify-center rounded-full bg-mint text-lens-dark" aria-hidden="true">
          <PieChart size={30} strokeWidth={1.8} />
        </span>
        <div className="flex flex-col gap-1">
          <h2 className="m-0 text-[20px] font-semibold">{t('Portfolio in one minute', 'এক মিনিটে পোর্টফোলিও')}</h2>
          <ul className="m-0 flex list-none flex-col gap-0.5 p-0 text-base text-ink-2">
            {strongRepaid !== undefined && (
              <li>{t(`About ${Math.round(strongRepaid * 100)} in 100 Strong loans were repaid.`, `শক্তিশালী ঋণের প্রতি ১০০টিতে প্রায় ${Math.round(strongRepaid * 100)}টি পরিশোধ হয়েছে।`)}</li>
            )}
            {showQueue && waiting !== undefined && (
              <li>{t(`${count(waiting)} merchants are waiting for a decision.`, `${count(waiting)} জন মার্চেন্ট সিদ্ধান্তের অপেক্ষায়।`)}</li>
            )}
            {showQueue && decisions.data && (
              <li>
                {d.length === 0
                  ? t('No decisions recorded yet.', 'এখনও কোনো সিদ্ধান্ত রাখা হয়নি।')
                  : t(
                      `Officers accepted ${count(accepts)} ${accepts === 1 ? 'suggestion' : 'suggestions'}, overrode ${count(overrides)} and requested more information on ${count(moreInfo)}.`,
                      `কর্মকর্তারা ${count(accepts)}টি পরামর্শ মেনেছেন, ${count(overrides)}টি বদলেছেন এবং ${count(moreInfo)}টিতে আরও তথ্য চেয়েছেন।`,
                    )}
              </li>
            )}
          </ul>
        </div>
      </Card>

      {card.error ? <ErrorCallout error={card.error} /> : card.data ? <BandsQuestion card={card.data} /> : <Card className="p-5 text-sm text-body">{t('Loading…', 'আসছে…')}</Card>}

      {showQueue ? (
        <>
          {queue.error ? <ErrorCallout error={queue.error} /> : <WaitingQuestion queue={queue.data} />}
          {decisions.error ? (
            <ErrorCallout error={decisions.error} />
          ) : decisions.data ? (
            <>
              <OfficersQuestion decisions={decisions.data} />
              <DaysQuestion decisions={decisions.data} />
            </>
          ) : (
            <Card className="p-5 text-sm text-body">{t('Loading decisions…', 'সিদ্ধান্ত আসছে…')}</Card>
          )}
        </>
      ) : (
        health.data && (
          <Unavailable>
            {t(
              'Questions 2 to 4 need a review queue and officers’ decisions. This public data source has neither: every outcome is already known.',
              '২ থেকে ৪ নম্বর প্রশ্নের জন্য পর্যালোচনার তালিকা আর কর্মকর্তার সিদ্ধান্ত লাগে। এই পাবলিক ডেটায় দুটোর কোনোটিই নেই: সব ফলাফল আগেই জানা।',
            )}
          </Unavailable>
        )
      )}

      {card.data && <GroupsQuestion card={card.data} />}
    </Page>
  )
}
