/**
 * Merchant page sections (approved design: 03-merchant-desktop.png): readiness overview,
 * "Why this score", financial habits, "Why might this be wrong?" and the no-consent state.
 * Every number comes from GET /merchants/{id}/score or the profile; nothing is made up.
 */
import type { LucideIcon } from 'lucide-react'
import { BadgeInfo, CalendarCheck, ChartNoAxesColumn, Database, FileText, Lock, Package, Users } from 'lucide-react'
import type { ReactNode } from 'react'

import type { Lang } from '@/app/session-context'
import type { Band, MerchantProfile, Reason, Score } from '@/api/types'
import { BandChip, Chip } from '@/components/BandChip'
import { CoverageBar } from '@/components/CoverageBar'
import { Section } from '@/components/Page'
import { ScoreRing } from '@/components/ScoreRing'
import { fmtDate, pct } from '@/lib/format'
import { useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'

/** What each band asks of the officer. Describes; never says lend or do not lend. */
const BAND_MEANING: Record<Band, { en: string; bn: string; titleEn: string; titleBn: string }> = {
  Strong: {
    titleEn: 'Strong:',
    titleBn: 'শক্তিশালী:',
    en: 'a high score with enough evidence behind it. Proceed with normal checks.',
    bn: 'যথেষ্ট প্রমাণসহ উঁচু স্কোর। স্বাভাবিক যাচাই করে এগোন।',
  },
  Review: {
    titleEn: 'Review:',
    titleBn: 'পর্যালোচনা:',
    en: 'the score is under the Strong line. Read every reason before deciding.',
    bn: 'স্কোর শক্তিশালী সীমার নিচে। সিদ্ধান্তের আগে প্রতিটি কারণ পড়ুন।',
  },
  'Needs more info': {
    titleEn: 'Needs more info:',
    titleBn: 'আরও তথ্য প্রয়োজন:',
    en: 'too little evidence to rely on the number. The ask is more evidence, not a lower band.',
    bn: 'সংখ্যার ওপর ভরসা করার মতো প্রমাণ কম। দরকার আরও প্রমাণ, নিচু ব্যান্ড নয়।',
  },
}

function InfoTile({ icon: Icon, children }: { icon: LucideIcon; children: ReactNode }) {
  return (
    <li className="flex gap-3 rounded-[12px] border border-line bg-white/80 p-3.5 text-sm leading-5 text-body">
      <Icon size={20} strokeWidth={1.7} className="mt-0.5 shrink-0 text-lens-dark" aria-hidden="true" />
      <span>{children}</span>
    </li>
  )
}

/** Readiness overview: the plain summary first, then the ring, band, coverage and four meanings. */
export function ReadinessOverview({ score, lang, outcome }: { score: Score; lang: Lang; outcome?: string }) {
  const t = useT()
  const summary = lang === 'bn' ? (score.summary_bn ?? score.summary_en) : score.summary_en
  const meaning = BAND_MEANING[score.band]
  return (
    <Section id="overview" title={t('Readiness overview', 'প্রস্তুতির সারসংক্ষেপ')} className="mint-wash border-mint-line">
      {summary && <p className="m-0 max-w-[900px] text-base leading-[26px] text-ink-2">{summary}</p>}
      <div className="flex flex-wrap items-center gap-x-10 gap-y-6 rounded-[12px] border border-line bg-white/80 p-5">
        <div className="flex items-center gap-5">
          <ScoreRing score={score.score} band={score.band} coverage={score.coverage} size={124} />
          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium text-ink-2">{t('Readiness score', 'প্রস্তুতির স্কোর')}</span>
            <BandChip band={score.band} lowScoreWarning={score.low_score_warning} size="md" className="self-start text-sm" />
          </div>
        </div>
        <div className="flex min-w-[220px] flex-1 flex-col gap-2 border-line sm:border-l sm:pl-10">
          <span className="text-sm font-medium text-ink-2">{t('Coverage', 'কভারেজ')}</span>
          <span className="font-display text-[30px] leading-9 font-bold text-ink tabular">{pct(score.coverage)}</span>
          <CoverageBar coverage={score.coverage} band={score.band} wide label={false} />
        </div>
      </div>
      {score.low_score_warning && score.band !== 'Needs more info' && (
        <p role="note" className="m-0 rounded-[10px] border border-amber-chip bg-amber-panel px-4 py-2.5 text-sm font-medium text-amber-deep">
          {t('Low score: read every reason before deciding.', 'কম স্কোর: সিদ্ধান্তের আগে প্রতিটি কারণ পড়ুন।')}
        </p>
      )}
      <ul className="m-0 grid list-none gap-3 p-0 sm:grid-cols-2 xl:grid-cols-4">
        <InfoTile icon={BadgeInfo}>
          {t('Calibrated probability of repaying in time:', 'সময়মতো পরিশোধের ক্যালিব্রেটেড সম্ভাবনা:')}{' '}
          <b className="font-semibold text-ink tabular">{score.probability.toFixed(2)}</b>
          {t(`, shown as ${score.score}.`, `, দেখানো হয় ${score.score} হিসেবে।`)}
        </InfoTile>
        <InfoTile icon={CalendarCheck}>{outcome ? `${outcome}.` : t('Repaid in time is the outcome the score predicts.', 'স্কোর সময়মতো পরিশোধের সম্ভাবনা বোঝায়।')}</InfoTile>
        <InfoTile icon={FileText}>
          <b className="font-semibold text-ink">
            {t('Coverage', 'কভারেজ')} {pct(score.coverage)}
          </b>{' '}
          {t('is how much of the expected evidence exists. It is not the score.', 'মানে প্রত্যাশিত প্রমাণের কতটা আছে। এটি স্কোর নয়।')}
        </InfoTile>
        <InfoTile icon={ChartNoAxesColumn}>
          <b className="font-semibold text-ink">{t(meaning.titleEn, meaning.titleBn)}</b> {t(meaning.en, meaning.bn)}
        </InfoTile>
      </ul>
    </Section>
  )
}

/** "1.2" for the equation line; the sign is written separately. */
function abs1(n: number) {
  return Math.abs(n).toFixed(1)
}

function sum(reasons: Reason[]) {
  return reasons.reduce((total, r) => total + r.contribution, 0)
}

/** A whole-number axis that holds every contribution and zero. */
function axis(values: number[]): { low: number; high: number } {
  const low = Math.min(0, Math.floor(Math.min(...values)))
  const high = Math.max(0, Math.ceil(Math.max(...values)))
  return { low: low === high ? -1 : low, high: high === low ? 1 : high }
}

/** One reason: dot, sentence and detail, the points, and a bar drawn to scale around zero. */
function ReasonRow({ reason, lang, low, high }: { reason: Reason; lang: Lang; low: number; high: number }) {
  const helps = reason.contribution >= 0
  const sentence = lang === 'bn' ? reason.sentence_bn : reason.sentence_en
  const span = high - low
  const zero = ((0 - low) / span) * 100
  const width = (Math.abs(reason.contribution) / span) * 100
  const left = helps ? zero : zero - width
  return (
    <li className="grid grid-cols-[14px_minmax(0,1fr)_64px] items-start gap-x-3 gap-y-2 border-t border-line py-3 md:grid-cols-[14px_minmax(0,1fr)_64px_minmax(180px,0.8fr)]">
      <span className={cn('mt-1.5 size-3 rounded-full', helps ? 'bg-band-strong' : 'bg-band-review')} aria-hidden="true" />
      <span className="flex flex-col gap-0.5">
        <span className="text-[15px] leading-[22px] text-ink">{sentence}</span>
        {reason.detail && <span className="text-[13px] text-muted-2">{reason.detail}</span>}
      </span>
      <span className={cn('pt-0.5 text-right text-[15px] font-semibold tabular', helps ? 'text-lens-dark' : 'text-amber-text')}>
        {helps ? '+' : '−'}
        {Math.abs(reason.contribution).toFixed(2)}
      </span>
      <span className="relative col-span-3 h-6 md:col-span-1" aria-hidden="true">
        <span className="absolute inset-y-0 w-px bg-control-line" style={{ left: `${zero}%` }} />
        <span
          className={cn('absolute top-1 h-4 rounded-[4px]', helps ? 'bg-band-strong/70' : 'bg-band-review/70')}
          style={{ left: `${left}%`, width: `${Math.max(width, 0.8)}%` }}
        />
      </span>
    </li>
  )
}

export function WhyThisScore({ score, lang }: { score: Score; lang: Lang }) {
  const t = useT()
  const helps = score.reasons_positive
  const holds = score.reasons_negative
  const reasons = [...helps, ...holds]
  const { low, high } = axis(reasons.map((r) => r.contribution))
  const zero = ((0 - low) / (high - low)) * 100
  const helpsTotal = sum(helps)
  const holdsTotal = sum(holds)
  const other = score.other_contribution

  return (
    <Section
      id="reasons"
      title={t('Why this score', 'কেন এই স্কোর')}
      answer={t(
        'Observations, not causes. Green raised the score, amber held it back; each bar is drawn to scale.',
        'পর্যবেক্ষণ, কারণ নয়। সবুজ স্কোর বাড়িয়েছে, হলুদ পিছিয়ে দিয়েছে; প্রতিটি দাগ মাপমতো আঁকা।',
      )}
    >
      {reasons.length === 0 ? (
        <p className="m-0 text-sm text-body">{t('Nothing stands out for this merchant.', 'এই মার্চেন্টের ক্ষেত্রে আলাদা কিছু চোখে পড়ে না।')}</p>
      ) : (
        <div className="flex flex-col">
          <div className="hidden grid-cols-[14px_minmax(0,1fr)_64px_minmax(180px,0.8fr)] gap-x-3 pb-1 text-xs text-muted-2 md:grid">
            <span />
            <span />
            <span />
            <span className="relative h-4">
              <span className="absolute left-0">{low}</span>
              <span className="absolute -translate-x-1/2" style={{ left: `${zero}%` }}>
                0
              </span>
              <span className="absolute right-0">+{high}</span>
            </span>
          </div>
          <ul className="m-0 list-none p-0">
            {[...helps, ...holds].map((r, i) => (
              <ReasonRow key={`${r.code}-${i}`} reason={r} lang={lang} low={low} high={high} />
            ))}
          </ul>
          <span className="pt-1 text-right text-xs text-muted-2">{t('Contribution (points)', 'অবদান (পয়েন্ট)')}</span>
        </div>
      )}
      {/* baseline + helps + holds back + everything else = score */}
      <div
        className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1.5 rounded-[12px] bg-ground px-4 py-3 text-[15px] text-ink-2 tabular"
        aria-label={t(
          `Average merchant ${abs1(score.baseline_score)}, plus ${abs1(helpsTotal)} from what helps, minus ${abs1(holdsTotal)} from what holds back, ${other < 0 ? 'minus' : 'plus'} ${abs1(other)} from everything else, gives ${score.score}`,
          `গড় মার্চেন্ট ${abs1(score.baseline_score)}, সাহায্যকারী থেকে যোগ ${abs1(helpsTotal)}, পিছিয়ে দেওয়া থেকে বিয়োগ ${abs1(holdsTotal)}, বাকি সব থেকে ${other < 0 ? 'বিয়োগ' : 'যোগ'} ${abs1(other)}, মোট ${score.score}`,
        )}
      >
        <span>
          <b className="font-semibold text-ink">{score.baseline_score.toFixed(1)}</b> {t('average merchant', 'গড় মার্চেন্ট')}
        </span>
        <span className="text-lens-dark">
          + {abs1(helpsTotal)} {t('helps', 'সাহায্য')}
        </span>
        <span className="text-amber-text">
          − {abs1(holdsTotal)} {t('holds back', 'পিছিয়ে দেয়')}
        </span>
        <span>
          {other < 0 ? '−' : '+'} {abs1(other)} {t('everything else', 'বাকি সব')}
        </span>
        <span aria-hidden="true">=</span>
        <span className="font-display text-xl font-bold text-ink">{score.score}</span>
      </div>
    </Section>
  )
}

const HABITS: { key: 'spend' | 'save' | 'borrow' | 'plan'; label: string; labelBn: string }[] = [
  { key: 'spend', label: 'Spend', labelBn: 'খরচ' },
  { key: 'save', label: 'Save', labelBn: 'সঞ্চয়' },
  { key: 'borrow', label: 'Borrow', labelBn: 'ধার' },
  { key: 'plan', label: 'Plan', labelBn: 'পরিকল্পনা' },
]

/** Five dots for a 1-to-5 answer (stress, confidence). */
function Dots({ value, color }: { value: number; color: string }) {
  return (
    <span className="flex gap-1" aria-hidden="true">
      {[1, 2, 3, 4, 5].map((n) => (
        <span key={n} className="h-2.5 w-5 rounded-full" style={{ background: n <= value ? color : '#E2EAED' }} />
      ))}
    </span>
  )
}

/**
 * Financial habits (the questionnaire). Shown beside the score, never inside it:
 * saving new answers does not change the score. `action` is the officer's
 * "Record new answers" button; `children` is the form when it is open.
 * Only this merchant's own answers are shown: never another merchant's as a preview.
 */
export function HabitsPanel({
  merchantId,
  questionnaire: q,
  action,
  children,
}: {
  merchantId: string
  questionnaire: MerchantProfile['questionnaire']
  action?: ReactNode
  children?: ReactNode
}) {
  const t = useT()
  return (
    <Section
      id="habits"
      title={t('Financial habits', 'আর্থিক অভ্যাস')}
      answer={t(
        'The merchant’s own answers to ten short questions. Directional only: they never change the score.',
        'দশটি ছোট প্রশ্নে মার্চেন্টের নিজের উত্তর। শুধু ইঙ্গিত: এগুলো কখনও স্কোর বদলায় না।',
      )}
      aside={
        <Chip tone="strong" className="px-3 py-1 text-[13px]">
          {t('Directional · not part of the score', 'ইঙ্গিতমাত্র · স্কোরের অংশ নয়')}
        </Chip>
      }
    >
      {q ? (
        <div className="flex flex-col gap-4 rounded-[12px] border border-line p-4 sm:p-5">
          <span className="self-end text-[13px] text-muted-2">
            {t(`Answered ${fmtDate(q.answered_at)}`, `উত্তর দিয়েছেন ${fmtDate(q.answered_at)}`)}
          </span>
          <ul className="m-0 flex list-none flex-col gap-3 p-0">
            {HABITS.map((h) => (
              <li key={h.key} className="grid grid-cols-[72px_minmax(0,1fr)_112px] items-center gap-3">
                <span className="text-[15px] font-medium text-ink">{t(h.label, h.labelBn)}</span>
                <span className="h-3 overflow-hidden rounded-full bg-track" aria-hidden="true">
                  <span className="block h-3 rounded-full bg-band-strong/60" style={{ width: `${(q[h.key] / 5) * 100}%` }} />
                </span>
                <span className="text-right text-sm font-semibold text-ink tabular">
                  {q[h.key].toFixed(1)} / 5 ({Math.round((q[h.key] / 5) * 100)}%)
                </span>
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap gap-x-10 gap-y-3 border-t border-line pt-4 text-[15px] text-ink">
            <span className="flex flex-wrap items-center gap-3">
              <b className="font-semibold">{t(`Stress ${q.stress} / 5`, `চাপ ${q.stress} / 5`)}</b>
              <Dots value={q.stress} color="#D9A441" />
              <span className="text-[13px] text-muted-2">{t('5 = a lot (higher is not better)', '5 = অনেক (বেশি মানে ভালো নয়)')}</span>
            </span>
            <span className="flex items-center gap-3">
              <b className="font-semibold">{t(`Confidence ${q.confidence} / 5`, `আত্মবিশ্বাস ${q.confidence} / 5`)}</b>
              <Dots value={q.confidence} color="#16845B" />
            </span>
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-3 rounded-[12px] border border-line bg-mint-2 p-4">
          <ChartNoAxesColumn size={28} className="shrink-0 text-lens-dark" aria-hidden="true" />
          <span className="text-[15px] font-medium text-ink">
            {t(`No answers recorded yet for ${merchantId}.`, `${merchantId}-এর কোনো উত্তর এখনও রাখা হয়নি।`)}
          </span>
        </div>
      )}
      <div className="flex flex-col items-center gap-2 text-center text-[13px] text-body">
        {action}
        <span>{t('Saving replaces the earlier answers. The score does not change.', 'রাখলে আগের উত্তর বদলে যায়। স্কোর বদলায় না।')}</span>
      </div>
      {children}
    </Section>
  )
}

function Caveat({ icon: Icon, children }: { icon: LucideIcon; children: string }) {
  return (
    <li className="flex gap-3 rounded-[12px] border border-amber-chip bg-white/70 p-3.5 text-sm leading-5 text-ink-2">
      <Icon size={22} strokeWidth={1.6} className="shrink-0 text-amber" aria-hidden="true" />
      <span>{children}</span>
    </li>
  )
}

export function WhyMightThisBeWrong() {
  const t = useT()
  return (
    <Section id="limits" title={t('Why might this be wrong?', 'এটি কেন ভুল হতে পারে?')} className="border-amber-chip bg-amber-panel">
      <ul className="m-0 grid list-none gap-3 p-0 sm:grid-cols-2 xl:grid-cols-4">
        <Caveat icon={Package}>{t('Returns can come from riders or addresses, not the shop.', 'ফেরত রাইডার বা ঠিকানার কারণেও হতে পারে, দোকানের কারণে নয়।')}</Caveat>
        <Caveat icon={Database}>
          {t(
            'The model learned from synthetic data. It says nothing yet about real merchants.',
            'মডেলটি সিনথেটিক ডেটা থেকে শিখেছে। আসল মার্চেন্টদের সম্পর্কে এটি এখনও কিছু বলে না।',
          )}
        </Caveat>
        <Caveat icon={Users}>{t('Labels exist only for merchants who got credit before.', 'ফলাফল শুধু তাদেরই জানা, যারা আগে ঋণ পেয়েছেন।')}</Caveat>
        <Caveat icon={FileText}>{t('A reason describes the data. It does not prove a cause.', 'একটি কারণ ডেটার বর্ণনা দেয়। এটি কোনো কারণ প্রমাণ করে না।')}</Caveat>
      </ul>
    </Section>
  )
}

/** Shown in place of the score when the API answers consent_required: no score, nothing faked. */
export function NoConsentScore() {
  const t = useT()
  return (
    <Section id="overview" title={t('Readiness overview', 'প্রস্তুতির সারসংক্ষেপ')}>
      <div className="flex flex-col items-center gap-2 rounded-[12px] border border-line bg-ground px-5 py-8 text-center">
        <span className="flex size-14 items-center justify-center rounded-full bg-neutral-chip text-ink-2">
          <Lock size={24} aria-hidden="true" />
        </span>
        <span className="font-display text-xl font-bold text-ink">{t('Consent needed', 'অনুমতি দরকার')}</span>
        <p className="m-0 max-w-[560px] text-[15px] text-body">
          {t(
            'Scoring is blocked until the merchant grants consent. There is no score, no evidence, no decision and no questionnaire.',
            'মার্চেন্ট অনুমতি না দেওয়া পর্যন্ত স্কোর বন্ধ। কোনো স্কোর, প্রমাণ, সিদ্ধান্ত বা প্রশ্নাবলি নেই।',
          )}
        </p>
      </div>
    </Section>
  )
}
