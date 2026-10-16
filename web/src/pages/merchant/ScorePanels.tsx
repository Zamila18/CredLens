/**
 * Right column of the merchant page (Merchant.dc.html): score card, reasons, the
 * financial habits panel and "Why might this be wrong?". Every number comes from
 * GET /merchants/{id}/score or the profile.
 */
import type { ReactNode } from 'react'

import type { Lang } from '@/app/session-context'
import type { Band, MerchantProfile, Reason, Score } from '@/api/types'
import { Chip } from '@/components/BandChip'
import { LensDial } from '@/components/LensDial'
import { Card, Eyebrow } from '@/components/Page'
import { ReasonCard } from '@/components/ReasonCard'
import { fmtDate, pct } from '@/lib/format'
import { useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'

/** What each band asks of the officer. Describes; never says lend or do not lend. */
const BAND_MEANING: Record<Band, { en: string; bn: string }> = {
  Strong: {
    en: 'Strong: a high score with enough evidence behind it. Proceed with normal checks.',
    bn: 'শক্তিশালী: যথেষ্ট প্রমাণসহ উঁচু স্কোর। স্বাভাবিক যাচাই করে এগোন।',
  },
  Review: {
    en: 'Review: the score is under the Strong line. Read every reason before deciding.',
    bn: 'পর্যালোচনা: স্কোর শক্তিশালী সীমার নিচে। সিদ্ধান্তের আগে প্রতিটি কারণ পড়ুন।',
  },
  'Needs more info': {
    en: 'Needs more info: too little evidence to rely on the number. The ask is more evidence, not a lower band.',
    bn: 'আরও তথ্য প্রয়োজন: সংখ্যার ওপর ভরসা করার মতো প্রমাণ কম। দরকার আরও প্রমাণ, নিচু ব্যান্ড নয়।',
  },
}

function Mono({ children }: { children: ReactNode }) {
  return <span className="font-mono font-semibold tabular">{children}</span>
}

/** `outcome` is the model card's label, e.g. "Repaid in time: the loan was paid in full no more than 30 days after its due date". */
export function ScoreCard({ score, lang, outcome }: { score: Score; lang: Lang; outcome?: string }) {
  const t = useT()
  const summary = lang === 'bn' ? (score.summary_bn ?? score.summary_en) : score.summary_en
  const summaryIsBn = lang === 'bn' && Boolean(score.summary_bn)
  return (
    <Card className="flex flex-col">
      {summary && (
        <div className="flex flex-col gap-1.5 border-b border-line-soft px-5 pt-5 pb-4">
          <Eyebrow>{t('Summary', 'সারসংক্ষেপ')}</Eyebrow>
          <p className={cn('m-0 text-[15px]', summaryIsBn ? 'font-bn leading-[26px]' : 'leading-[23px]')}>{summary}</p>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-5 p-5">
        <LensDial score={score.score} coverage={score.coverage} band={score.band} lowScoreWarning={score.low_score_warning} />
        <div className="flex flex-[1_1_200px] flex-col gap-3">
          <h2 className="m-0">
            <Eyebrow>{t('Readiness score', 'প্রস্তুতির স্কোর')}</Eyebrow>
          </h2>
          <p className="m-0 text-[15px] leading-[22px]">
            {t('Calibrated probability of repaying in time:', 'সময়মতো পরিশোধের ক্যালিব্রেটেড সম্ভাবনা:')}{' '}
            <Mono>{score.probability.toFixed(2)}</Mono>, {t('shown as', 'দেখানো হয়')} <Mono>{score.score}</Mono>
            {t('.', ' হিসেবে।')}
          </p>
          {outcome && <p className="m-0 text-[13px] text-muted-2">{outcome}.</p>}
          <p className="m-0 text-sm leading-[21px] text-ink-3">
            <span className="font-semibold">
              {t('Coverage', 'কভারেজ')} {pct(score.coverage)}
            </span>{' '}
            {t(
              'is how much of the expected evidence exists. It is not the score. The outer ring fills with it.',
              'মানে প্রত্যাশিত প্রমাণের কতটা আছে। এটি স্কোর নয়। বাইরের বৃত্ত এটা দিয়ে ভরে।',
            )}
          </p>
          <p className="m-0 text-[13px] text-muted-2">{t(BAND_MEANING[score.band].en, BAND_MEANING[score.band].bn)}</p>
          {score.low_score_warning && (
            <p className="m-0 text-[13px] font-medium text-rust">
              {t('Low score: read every reason before deciding.', 'কম স্কোর: সিদ্ধান্তের আগে প্রতিটি কারণ পড়ুন।')}
            </p>
          )}
        </div>
      </div>
    </Card>
  )
}

/** "1.2" for the equation line; the sign is written separately. */
function abs1(n: number) {
  return Math.abs(n).toFixed(1)
}

function sum(reasons: Reason[]) {
  return reasons.reduce((total, r) => total + r.contribution, 0)
}

export function WhyThisScore({ score, lang }: { score: Score; lang: Lang }) {
  const t = useT()
  const helps = score.reasons_positive
  const holds = score.reasons_negative
  const maxAbs = Math.max(0, ...[...helps, ...holds].map((r) => Math.abs(r.contribution)))
  const helpsTotal = sum(helps)
  const holdsTotal = sum(holds)
  const other = score.other_contribution

  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="m-0 text-lg font-semibold">{t('Why this score', 'কেন এই স্কোর')}</h2>
        <span className="text-xs text-muted-2">{t('Observations, not causes', 'পর্যবেক্ষণ, কারণ নয়')}</span>
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-4">
        <div className="flex flex-col gap-2.5">
          <span className="text-[13px] font-semibold text-lens-dark">{t('Helps', 'সাহায্য করে')}</span>
          {helps.length === 0 && (
            <span className="text-[13px] text-muted">{t('Nothing stands out for this merchant.', 'এই মার্চেন্টের ক্ষেত্রে আলাদা কিছু চোখে পড়ে না।')}</span>
          )}
          {helps.map((r, i) => (
            <ReasonCard key={i} reason={r} lang={lang} maxAbs={maxAbs} />
          ))}
        </div>
        <div className="flex flex-col gap-2.5">
          <span className="text-[13px] font-semibold text-amber-text">{t('Holds back', 'পিছিয়ে দেয়')}</span>
          {holds.length === 0 && (
            <span className="text-[13px] text-muted">{t('Nothing stands out for this merchant.', 'এই মার্চেন্টের ক্ষেত্রে আলাদা কিছু চোখে পড়ে না।')}</span>
          )}
          {holds.map((r, i) => (
            <ReasonCard key={i} reason={r} lang={lang} maxAbs={maxAbs} />
          ))}
        </div>
      </div>
      {/* baseline + helps + holds back + everything else = score */}
      <div
        className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5 rounded-[10px] bg-ground px-3.5 py-3 font-mono text-[13px] text-ink-2 tabular"
        aria-label={t(
          `Average merchant ${abs1(score.baseline_score)}, plus ${abs1(helpsTotal)} from what helps, minus ${abs1(holdsTotal)} from what holds back, ${other < 0 ? 'minus' : 'plus'} ${abs1(other)} from everything else, gives ${score.score}`,
          `গড় মার্চেন্ট ${abs1(score.baseline_score)}, সাহায্যকারী থেকে যোগ ${abs1(helpsTotal)}, পিছিয়ে দেওয়া থেকে বিয়োগ ${abs1(holdsTotal)}, বাকি সব থেকে ${other < 0 ? 'বিয়োগ' : 'যোগ'} ${abs1(other)}, মোট ${score.score}`,
        )}
      >
        <span>
          {score.baseline_score.toFixed(1)} {t('average merchant', 'গড় মার্চেন্ট')}
        </span>
        <span aria-hidden="true">+</span>
        <span className="text-lens-dark">
          {abs1(helpsTotal)} {t('helps', 'সাহায্য')}
        </span>
        <span aria-hidden="true">−</span>
        <span className="text-amber-text">
          {abs1(holdsTotal)} {t('holds back', 'পিছিয়ে দেয়')}
        </span>
        <span aria-hidden="true">{other < 0 ? '−' : '+'}</span>
        <span>
          {abs1(other)} {t('everything else', 'বাকি সব')}
        </span>
        <span aria-hidden="true">=</span>
        <span className="font-semibold">{score.score}</span>
      </div>
    </Card>
  )
}

const HABITS: { key: 'spend' | 'save' | 'borrow' | 'plan'; label: string; labelBn: string }[] = [
  { key: 'spend', label: 'Spend', labelBn: 'খরচ' },
  { key: 'save', label: 'Save', labelBn: 'সঞ্চয়' },
  { key: 'borrow', label: 'Borrow', labelBn: 'ধার' },
  { key: 'plan', label: 'Plan', labelBn: 'পরিকল্পনা' },
]

/**
 * Financial habits (the questionnaire). Shown beside the score, never inside it:
 * saving new answers does not change the score. `action` is the officer's
 * "Record new answers" button; `children` is the form when it is open.
 */
export function HabitsPanel({
  questionnaire: q,
  action,
  children,
}: {
  questionnaire: MerchantProfile['questionnaire']
  action?: ReactNode
  children?: ReactNode
}) {
  const t = useT()
  return (
    <Card className="flex flex-col gap-3.5 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="m-0 text-lg font-semibold">{t('Financial habits', 'আর্থিক অভ্যাস')}</h2>
        <Chip tone="peri" className="px-2.5 py-1">
          {t('Directional · not part of the score', 'ইঙ্গিতমাত্র · স্কোরের অংশ নয়')}
        </Chip>
      </div>
      {q ? (
        <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-x-5 gap-y-3">
          {HABITS.map((h) => (
            <div key={h.key} className="flex flex-col gap-1.5">
              <div className="flex justify-between text-[13px]">
                <span>{t(h.label, h.labelBn)}</span>
                <span className="font-mono font-semibold tabular">{q[h.key].toFixed(1)} / 5</span>
              </div>
              <div className="h-2 overflow-hidden rounded bg-line-soft" aria-hidden="true">
                <span className="block h-2 bg-slate" style={{ width: `${(q[h.key] / 5) * 100}%` }} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="m-0 text-sm text-ink-3">{t('No answers recorded yet for this merchant.', 'এই মার্চেন্টের কোনো উত্তর এখনও রাখা হয়নি।')}</p>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2.5 text-[13px] text-muted">
        <span>
          {q
            ? t(
                `Stress ${q.stress} / 5 (5 = a lot) · Confidence ${q.confidence} / 5 · answered ${fmtDate(q.answered_at)}`,
                `চাপ ${q.stress} / 5 (5 = অনেক) · আত্মবিশ্বাস ${q.confidence} / 5 · উত্তর ${fmtDate(q.answered_at)}`,
              )
            : t('The ten questions are optional and never change the score.', 'দশটি প্রশ্ন ঐচ্ছিক, এবং কখনও স্কোর বদলায় না।')}
        </span>
        {action}
      </div>
      {children}
    </Card>
  )
}

export function WhyMightThisBeWrong() {
  const t = useT()
  return (
    <section aria-labelledby="ww" className="flex flex-col gap-2.5 rounded-card bg-peri-panel px-5 py-[18px]">
      <h2 id="ww" className="m-0 text-base font-semibold text-peri-head">
        {t('Why might this be wrong?', 'এটি কেন ভুল হতে পারে?')}
      </h2>
      <ul className="m-0 flex flex-col gap-1.5 pl-[18px] text-sm leading-5 text-peri-body">
        <li>{t('Returns can come from riders or addresses, not the shop.', 'ফেরত রাইডার বা ঠিকানার কারণেও হতে পারে, দোকানের কারণে নয়।')}</li>
        <li>
          {t(
            'The model learned from synthetic data. It says nothing yet about real merchants.',
            'মডেলটি সিনথেটিক ডেটা থেকে শিখেছে। আসল মার্চেন্টদের সম্পর্কে এটি এখনও কিছু বলে না।',
          )}
        </li>
        <li>{t('Labels exist only for merchants who got credit before.', 'ফলাফল শুধু তাদেরই জানা, যারা আগে ঋণ পেয়েছেন।')}</li>
        <li>{t('A reason describes the data. It does not prove a cause.', 'একটি কারণ ডেটার বর্ণনা দেয়। এটি কোনো কারণ প্রমাণ করে না।')}</li>
      </ul>
    </section>
  )
}

/** Shown in place of the score card when the API answers consent_required. */
export function NoConsentScore() {
  const t = useT()
  return (
    <Card className="flex flex-wrap items-center gap-5 p-5">
      <LensDial noConsent />
      <div className="flex flex-[1_1_200px] flex-col gap-3">
        <h2 className="m-0">
          <Eyebrow>{t('Readiness score', 'প্রস্তুতির স্কোর')}</Eyebrow>
        </h2>
        <p className="m-0 text-[15px] leading-[22px]">
          {t(
            'Scoring is blocked until the merchant grants consent. There is no score, no decision and no questionnaire.',
            'মার্চেন্ট অনুমতি না দেওয়া পর্যন্ত স্কোর বন্ধ। কোনো স্কোর, সিদ্ধান্ত বা প্রশ্নাবলি নেই।',
          )}
        </p>
      </div>
    </Card>
  )
}
