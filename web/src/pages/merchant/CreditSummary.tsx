/**
 * The first thing a Credit Officer reads about a shop, in plain words: the credit score out of
 * 100, the suggested loan range, what looks good and what to watch, and what it rests on. The
 * technical panels live further down the page.
 *
 * It shows the latest stored assessment (GET /merchants/{id}/assessments); "Update" stores a new
 * one from the records as they are now. The range comes from the company's own approved range
 * rule and the shop's checked purchases only. A shop with too few checked receipts shows no
 * score at all (a number there would be a guess). A person decides.
 */
import { Check, RefreshCw, TriangleAlert } from 'lucide-react'
import { useEffect, useState } from 'react'

import { api } from '@/api/client'
import type { AssessmentOut } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSubmit } from '@/api/useSubmit'
import { ErrorCallout } from '@/components/ErrorCallout'
import { Section } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { fmtBdTime, taka } from '@/lib/format'
import { useLang, useT } from '@/lib/i18n'

type Plain = {
  outlook?: 'strong' | 'moderate' | 'not_enough'
  range_line?: { en: string; bn: string }
  basis?: {
    receipts: number
    receipts_confirmed: number
    purchase_records: number
    months_with_purchases: number
    window_days: number | null
    monthly_purchases_bdt: number | null
    lines_disputed: number
    repayments_on_file: number
  }
  improve?: { en: string[]; bn: string[] }
}

const OUTLOOK = {
  strong: { en: 'Looks reliable', bn: 'ভরসাযোগ্য মনে হচ্ছে', cls: 'bg-strong-chip text-lens-dark' },
  moderate: { en: 'Needs a closer look', bn: 'আরও খুঁটিয়ে দেখুন', cls: 'bg-amber-chip text-amber-text' },
  not_enough: { en: 'Not enough receipts yet', bn: 'এখনও যথেষ্ট রসিদ নেই', cls: 'bg-neutral-chip text-neutral-text' },
} as const

/** One reason as a sentence in the officer's language (older rows may hold plain text). */
function sentenceOf(reason: unknown, lang: 'en' | 'bn'): string {
  if (reason && typeof reason === 'object') {
    const value = (reason as Record<string, unknown>)[lang === 'bn' ? 'sentence_bn' : 'sentence_en']
    return typeof value === 'string' ? value.trim() : ''
  }
  return typeof reason === 'string' ? reason.trim() : ''
}

/** The score as a ring filled to its percentage (85 out of 100 is 85% round). Empty when there is no score. */
function ScoreRing({ score, tone, label }: { score: number | null; tone: 'strong' | 'moderate' | 'none'; label: string }) {
  const size = 96
  const stroke = 10
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const [shown, setShown] = useState(0)
  useEffect(() => {
    const frame = requestAnimationFrame(() => setShown(score ?? 0))
    return () => cancelAnimationFrame(frame)
  }, [score])
  const colour = tone === 'strong' ? 'text-lens' : tone === 'moderate' ? 'text-amber-text' : 'text-muted-2'
  return (
    <span role="img" aria-label={label} className="relative inline-flex shrink-0">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" strokeWidth={stroke} className="stroke-current text-card-line" />
        {score != null && (
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={circumference * (1 - shown / 100)}
            className={`stroke-current ${colour} motion-safe:transition-[stroke-dashoffset] motion-safe:duration-700 motion-safe:ease-out`}
          />
        )}
      </svg>
      <span className="absolute inset-0 flex items-center justify-center font-display text-[22px] font-bold tabular-nums text-ink">
        {score != null ? `${score}%` : '—'}
      </span>
    </span>
  )
}

function Reasons({ title, lines, tone }: { title: string; lines: string[]; tone: 'good' | 'watch' }) {
  if (!lines.length) return null
  const Icon = tone === 'good' ? Check : TriangleAlert
  return (
    <div className={`flex flex-col gap-2.5 rounded-[14px] border p-4 ${tone === 'good' ? 'border-mint-line bg-mint-2' : 'border-amber-line bg-amber-panel'}`}>
      <h3 className={`m-0 text-[16px] font-semibold ${tone === 'good' ? 'text-lens-dark' : 'text-amber-text'}`}>{title}</h3>
      <ul className="m-0 flex list-none flex-col gap-2 p-0">
        {lines.map((line) => (
          <li key={line} className="flex items-start gap-2 text-[15.5px] leading-[23px] text-ink">
            <Icon size={18} aria-hidden="true" className={`mt-[3px] shrink-0 ${tone === 'good' ? 'text-lens-dark' : 'text-amber-text'}`} />
            <span>{line}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function CreditSummary({
  merchantId,
  canRun,
  nothingToScore = false,
  className,
}: {
  merchantId: string
  canRun: boolean
  /** The shop has no application and no loan yet: there is nothing to assess. */
  nothingToScore?: boolean
  className?: string
}) {
  const t = useT()
  const lang = useLang()
  const base = `/merchants/${encodeURIComponent(merchantId)}/assessments`
  const list = useApi<AssessmentOut[]>(base, undefined, { noCache: true })
  const run = useSubmit<AssessmentOut>()
  const current = list.data?.[0]
  const plain = (current?.plain ?? {}) as Plain
  const b = plain.basis

  const update = async () => {
    const done = await run.submit(() => api<AssessmentOut>(base, { method: 'POST' }))
    if (done) list.reload()
  }

  const outlook = OUTLOOK[plain.outlook ?? 'not_enough']
  const scored = current != null && current.band !== 'Needs more info'
  const asked = current && typeof current.range_inputs?.requested_bdt === 'number' ? (current.range_inputs.requested_bdt as number) : null
  // How late earlier instalments were paid, straight from the records (not from the model).
  const delay = (current?.input_snapshot as Record<string, number | null> | undefined)?.avg_pay_delay_days
  const good = (current?.reasons_positive ?? []).map((r) => sentenceOf(r, lang)).filter(Boolean).slice(0, 3)
  const watch = (current?.reasons_negative ?? []).map((r) => sentenceOf(r, lang)).filter(Boolean).slice(0, 3)
  const improve = ((lang === 'bn' ? plain.improve?.bn : plain.improve?.en) ?? []).slice(0, 3)

  return (
    <Section
      className={className}
      title={t('Credit summary', 'ঋণের সারসংক্ষেপ')}
      answer={t('The score, the loan range and the reasons, in one place. You decide.', 'স্কোর, ঋণের পরিসীমা ও কারণ এক জায়গায়। সিদ্ধান্ত আপনার।')}
    >
      <div className="flex flex-col gap-5">
        {list.error && <ErrorCallout error={list.error} />}
        {run.error && <ErrorCallout error={run.error} />}
        {nothingToScore && !current && (
          <p className="m-0 text-[15.5px] text-body">
            {t('This shop has not applied for a loan yet, so there is nothing to score.', 'এই দোকান এখনও ঋণের জন্য আবেদন করেনি, তাই স্কোর করার কিছু নেই।')}
          </p>
        )}
        {!nothingToScore && !current && list.data && (
          <p className="m-0 text-[15.5px] text-body">{t('No summary has been made for this shop yet.', 'এই দোকানের জন্য এখনও কোনো সারসংক্ষেপ তৈরি হয়নি।')}</p>
        )}
        {current && (
          <>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="flex flex-col gap-2 rounded-[14px] border border-card-line bg-ground p-5">
                <span className="text-[14px] text-muted-2">{t('Credit score', 'ক্রেডিট স্কোর')}</span>
                <div className="flex items-center gap-4">
                  <ScoreRing
                    score={scored ? current.score : null}
                    tone={!scored ? 'none' : plain.outlook === 'moderate' ? 'moderate' : 'strong'}
                    label={scored ? t(`Score ${current.score} out of 100`, `স্কোর ১০০-র মধ্যে ${current.score}`) : t('No score yet', 'এখনও স্কোর নেই')}
                  />
                  {scored ? (
                    <span className="flex items-baseline gap-2">
                      <span className="font-display text-[56px] leading-[60px] font-bold tabular-nums text-ink">{current.score}</span>
                      <span className="text-[18px] whitespace-nowrap text-muted-2">{t('out of 100', '১০০-র মধ্যে')}</span>
                    </span>
                  ) : (
                    <span className="font-display text-[26px] leading-[32px] font-bold text-ink">{t('No score yet', 'এখনও স্কোর নেই')}</span>
                  )}
                </div>
                <span className={`self-start rounded-lg px-3 py-1.5 text-[17px] font-semibold ${outlook.cls}`}>{t(outlook.en, outlook.bn)}</span>
                <span className="text-[15px] leading-[22px] text-body">
                  {scored
                    ? t(
                        'A confidence score from this shop’s checked records: the higher it is, the more the records support repayment.',
                        'দোকানের যাচাই করা রেকর্ড থেকে পাওয়া আস্থার স্কোর: যত বেশি, রেকর্ড তত বেশি পরিশোধের পক্ষে।',
                      )
                    : t('Too few checked receipts to score fairly: a number now would be a guess.', 'যথেষ্ট যাচাই করা রসিদ নেই, তাই এখন স্কোর দিলে তা আন্দাজ হতো।')}
                </span>
              </div>
              <div className="flex flex-col gap-2 rounded-[14px] border border-card-line bg-ground p-5">
                <span className="text-[14px] text-muted-2">{t('Suggested loan range', 'প্রস্তাবিত ঋণের পরিসীমা')}</span>
                {current.range_available && current.range_min_bdt != null && current.range_max_bdt != null ? (
                  <span className="font-display text-[34px] leading-[42px] font-bold tabular-nums text-ink">
                    {taka(current.range_min_bdt)} – {taka(current.range_max_bdt)}
                  </span>
                ) : (
                  <span className="font-display text-[34px] leading-[42px] font-bold text-ink">{t('Not yet', 'এখনও নয়')}</span>
                )}
                {asked != null && (
                  <span className="text-[15px] text-body">
                    {t('The shop asked for', 'দোকান চেয়েছে')} <strong className="text-ink">{taka(asked)}</strong>
                  </span>
                )}
                {!current.range_available && plain.range_line && (
                  <span className="text-[15px] leading-[22px] text-body">{lang === 'bn' ? plain.range_line.bn : plain.range_line.en}</span>
                )}
              </div>
            </div>

            {scored && (good.length > 0 || watch.length > 0) && (
              <div className="grid gap-4 md:grid-cols-2">
                <Reasons title={t('What looks good', 'যা ভালো দেখাচ্ছে')} lines={good} tone="good" />
                <Reasons title={t('What to watch', 'যা খেয়াল রাখবেন')} lines={watch} tone="watch" />
              </div>
            )}

            {b && b.receipts > 0 && (
              <p className="m-0 text-[15px] leading-[23px] text-body">
                {t(
                  `Based on ${b.receipts} checked receipts over ${b.months_with_purchases} months; ${b.receipts_confirmed} of them confirmed by the shop owner.`,
                  `${b.months_with_purchases} মাসের ${b.receipts}টি যাচাই করা রসিদের ভিত্তিতে; এর মধ্যে ${b.receipts_confirmed}টি দোকানের মালিক নিশ্চিত করেছেন।`,
                )}
                {b.monthly_purchases_bdt != null && (
                  <>
                    {' '}
                    {t(`The shop buys about ${taka(b.monthly_purchases_bdt)} of stock a month.`, `দোকান মাসে প্রায় ${taka(b.monthly_purchases_bdt)} টাকার মাল কেনে।`)}
                  </>
                )}
                {typeof delay === 'number' && (
                  <>
                    {' '}
                    {delay < 1
                      ? t('On earlier loans, instalments were paid on the due date on average.', 'আগের ঋণে কিস্তি গড়ে নির্ধারিত দিনেই শোধ হয়েছে।')
                      : t(
                          `On earlier loans, instalments were paid about ${Math.round(delay)} ${Math.round(delay) === 1 ? 'day' : 'days'} after the due date on average.`,
                          `আগের ঋণে কিস্তি গড়ে নির্ধারিত দিনের প্রায় ${Math.round(delay)} দিন পরে শোধ হয়েছে।`,
                        )}
                  </>
                )}
                {b.lines_disputed > 0 && (
                  <>
                    {' '}
                    {t(
                      `${b.lines_disputed} line(s) the owner reported are left out until answered.`,
                      `মালিকের জানানো ${b.lines_disputed}টি লাইন উত্তর না আসা পর্যন্ত বাদ আছে।`,
                    )}
                  </>
                )}
              </p>
            )}

            {improve.length > 0 && (
              <div className="flex flex-col gap-1.5">
                <h3 className="m-0 text-[15px] font-semibold text-ink">{t('To be surer', 'আরও নিশ্চিত হতে')}</h3>
                <ul className="m-0 flex list-disc flex-col gap-1 pl-5 text-[15px] leading-[22px] text-body">
                  {improve.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              </div>
            )}

            {current.range_reasoning.length > 0 && (
              <details className="text-[14.5px] text-body">
                <summary className="cursor-pointer font-semibold text-lens-dark">{t('How was the range worked out?', 'পরিসীমা কীভাবে হিসাব হলো?')}</summary>
                <ol className="m-0 mt-2 flex list-decimal flex-col gap-1 pl-5">
                  {current.range_reasoning.map((step) => (
                    <li key={step}>{step}</li>
                  ))}
                </ol>
              </details>
            )}
          </>
        )}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
          <span className="text-[13px] leading-[19px] text-muted-2">
            {current ? `${t('Made', 'তৈরি')} ${fmtBdTime(current.assessed_at)}. ` : ''}
            {t(
              'The score comes from practice data and has not yet been checked on real repayments. It helps you decide; it never approves or declines a loan.',
              'স্কোরটি অনুশীলনের ডেটা থেকে এসেছে, যা এখনও আসল পরিশোধে যাচাই হয়নি। এটি সিদ্ধান্তে সাহায্য করে; কখনও ঋণ অনুমোদন বা প্রত্যাখ্যান করে না।',
            )}
          </span>
          {canRun && !nothingToScore && (
            <Button variant="outline" disabled={run.pending} onClick={() => void update()}>
              <RefreshCw size={18} aria-hidden="true" className={run.pending ? 'animate-spin' : ''} />
              {run.pending ? t('Updating…', 'হালনাগাদ হচ্ছে…') : current ? t('Update the summary', 'সারসংক্ষেপ হালনাগাদ') : t('Make the summary', 'সারসংক্ষেপ তৈরি করুন')}
            </Button>
          )}
        </div>
      </div>
    </Section>
  )
}
