/**
 * The officer workspace pieces that come from GET /merchants/{id}/review: the summary at the
 * top (application, assessment, review status), the review status with its checks, credit
 * range guidance, and every evidence group with how each record entered CredLens.
 *
 * The rules live in the API (src/api/review.py); this file only words them. The review
 * status is about the evidence, never about the score's level, and never means approval.
 */
import { CircleCheck, CircleDashed, CircleX, Info, Scale } from 'lucide-react'
import type { ReactNode } from 'react'

import type { EvidenceGroup, EvidenceRequest, ReadinessCheck, ReviewRecord, ReviewStatus, Score } from '@/api/types'
import { useSession } from '@/app/session-context'
import { BandChip } from '@/components/BandChip'
import { SourceBar, SourceLegend } from '@/components/EvidenceViz'
import { Card, Section } from '@/components/Page'
import { StatusTag } from '@/components/StatusTag'
import { DELIVERY_STATUS_WORDS, OUTCOME_WORDS, PURPOSE_WORDS, wordsFor } from '@/lib/fieldWords'
import { count, fmtBdTime, fmtDate, taka } from '@/lib/format'
import { pick, useLang, useT, type Pair } from '@/lib/i18n'
import { ASSESSMENT_STATUS, GENERATED_RECORD, LOAN_KIND, READINESS, RECORD_STATUS } from '@/lib/statuses'
import { cn } from '@/lib/utils'

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <dt className="text-[13px] text-muted-2">{label}</dt>
      <dd className="m-0 flex min-w-0 flex-wrap items-center gap-2 text-[17px] font-semibold text-ink">{children}</dd>
    </div>
  )
}

/** The top summary: what is being asked for, how fresh the assessment is, where the review stands. */
export function ReviewSummary({ review, score }: { review: ReviewStatus; score?: Score }) {
  const t = useT()
  const { mode } = useSession()
  const lang = useLang()
  const app = review.application
  const assessment = review.assessment === 'consent_required' ? undefined : ASSESSMENT_STATUS[review.assessment]
  return (
    <Card id="summary" className="flex flex-col gap-4 p-5 sm:p-6">
      <h2 className="sr-only">{t('Summary', 'সারসংক্ষেপ')}</h2>
      <dl className="m-0 grid grid-cols-1 gap-4 min-[480px]:grid-cols-2 lg:grid-cols-4">
        <Fact label={t('Requested', 'চাওয়া হয়েছে')}>
          {app ? (
            <span className="flex flex-col">
              <span className="tabular">{taka(app.requested_amount_bdt)}</span>
              <span className="text-[13px] font-normal text-peri-text" title={pick(LOAN_KIND.application.help, lang)}>
                {t('Application · not an issued loan', 'আবেদন · দেওয়া ঋণ নয়')}
              </span>
            </span>
          ) : (
            <span className="text-[15px] font-normal text-body">{t('No application in CredLens', 'CredLens-এ কোনো আবেদন নেই')}</span>
          )}
        </Fact>
        <Fact label={t('Purpose', 'উদ্দেশ্য')}>
          {app ? (
            <span className="text-[15px]">
              {wordsFor(PURPOSE_WORDS, app.purpose, lang)}
              <span className="block text-[13px] font-normal text-muted-2">{t(`Applied ${fmtDate(app.business_date)}`, `আবেদন ${fmtDate(app.business_date)}`)}</span>
            </span>
          ) : mode === 'account' ? (
            <span className="text-[15px] font-normal text-body">{t('No application yet', 'এখনও আবেদন নেই')}</span>
          ) : (
            <span className="text-[15px] font-normal text-body">{t('The loan under review is the shop’s application', 'পর্যালোচনার ঋণটি দোকানের আবেদন')}</span>
          )}
        </Fact>
        <Fact label={t('Model result', 'মডেলের ফল')}>
          {score && review.assessment === 'current' ? (
            <>
              <span className="tabular">{t(`Score ${score.score}`, `স্কোর ${score.score}`)}</span>
              <BandChip band={score.band} lowScoreWarning={score.low_score_warning} />
            </>
          ) : assessment ? (
            <StatusTag status={assessment} />
          ) : (
            <span className="text-[15px] font-normal text-body">{t('No score without consent', 'অনুমতি ছাড়া স্কোর নেই')}</span>
          )}
        </Fact>
        <Fact label={t('Review status', 'পর্যালোচনার অবস্থা')}>
          <StatusTag status={READINESS[review.readiness]} className="text-[13px]" />
        </Fact>
      </dl>
      <p className="m-0 border-t border-line pt-3 text-[13px] text-body">
        {app && review.assessment === 'current' && assessment && <>{pick(assessment.help, lang)} </>}
        {t('The model suggests; the decision is yours and is recorded separately.', 'মডেল পরামর্শ দেয়; সিদ্ধান্ত আপনার, আর তা আলাদাভাবে রাখা হয়।')}
      </p>
    </Card>
  )
}

/** Each check in words, passed or not. */
function checkWords(check: ReadinessCheck, assessment: ReviewStatus['assessment']): Pair {
  switch (check.code) {
    case 'consent':
      return check.passed
        ? { en: 'Consent is valid.', bn: 'অনুমতি বৈধ।' }
        : { en: 'No valid consent. Record it before anything else.', bn: 'বৈধ অনুমতি নেই। আগে এটি নিন।' }
    case 'assessment':
      if (check.passed) return { en: 'The assessment is up to date.', bn: 'মূল্যায়ন হালনাগাদ।' }
      if (assessment === 'not_updated')
        return { en: 'The latest records are saved, but the score could not be redone.', bn: 'সর্বশেষ রেকর্ড সংরক্ষিত, কিন্তু স্কোর আবার করা যায়নি।' }
      if (assessment === 'consent_required') return { en: 'No assessment without consent.', bn: 'অনুমতি ছাড়া মূল্যায়ন নেই।' }
      return { en: 'Not assessed yet: there is no application or loan to assess.', bn: 'এখনও মূল্যায়ন হয়নি: মূল্যায়নের মতো কোনো আবেদন বা ঋণ নেই।' }
    case 'history':
      return check.passed
        ? { en: 'There is enough history behind the score.', bn: 'স্কোরের পেছনে যথেষ্ট ইতিহাস আছে।' }
        : { en: 'Too little history: coverage is under the line, so the band is Needs more info.', bn: 'ইতিহাস কম: কভারেজ সীমার নিচে, তাই ব্যান্ড "আরও তথ্য প্রয়োজন"।' }
    case 'field_visit':
      return check.passed
        ? { en: 'A field visit is recorded.', bn: 'মাঠ পরিদর্শন রাখা আছে।' }
        : { en: 'No field visit is recorded for this application.', bn: 'এই আবেদনের জন্য কোনো মাঠ পরিদর্শন রাখা হয়নি।' }
    case 'deliveries':
      return check.passed
        ? { en: 'Delivery records are present.', bn: 'ডেলিভারির রেকর্ড আছে।' }
        : { en: 'No delivery records. They are optional: this never blocks review or lowers the score.', bn: 'ডেলিভারির রেকর্ড নেই। এগুলো ঐচ্ছিক: এতে পর্যালোচনা আটকায় না, স্কোরও কমে না।' }
  }
}

const NEXT_ACTION: Record<ReviewStatus['readiness'], Pair> = {
  ready: { en: 'Read the reasons and the records, then record your decision.', bn: 'কারণ ও রেকর্ড পড়ুন, তারপর সিদ্ধান্ত রাখুন।' },
  check_needed: { en: 'Look at the open check, then decide. You can also ask for more information.', bn: 'বাকি যাচাইটি দেখুন, তারপর সিদ্ধান্ত নিন। চাইলে আরও তথ্যও চাইতে পারেন।' },
  more_info_needed: { en: 'Ask for the missing evidence before relying on the score.', bn: 'স্কোরের ওপর ভরসার আগে যে প্রমাণ নেই তা চেয়ে নিন।' },
  not_updated: { en: 'Do not decide on an old score. Check the records or ask an administrator.', bn: 'পুরনো স্কোরে সিদ্ধান্ত নেবেন না। রেকর্ড দেখুন বা অ্যাডমিনকে জানান।' },
}

function CheckIcon({ check }: { check: ReadinessCheck }) {
  const t = useT()
  if (check.passed) return <CircleCheck size={18} className="mt-0.5 shrink-0 text-band-strong" aria-label={t('passed', 'ঠিক আছে')} />
  if (check.kind === 'info') return <Info size={18} className="mt-0.5 shrink-0 text-muted-2" aria-label={t('for information', 'তথ্যের জন্য')} />
  if (check.kind === 'check') return <CircleDashed size={18} className="mt-0.5 shrink-0 text-amber" aria-label={t('to check', 'দেখতে হবে')} />
  return <CircleX size={18} className="mt-0.5 shrink-0 text-error" aria-label={t('missing', 'নেই')} />
}

export function ReadinessPanel({ review, className }: { review: ReviewStatus; className?: string }) {
  const t = useT()
  const lang = useLang()
  return (
    <Section
      id="readiness"
      className={className}
      title={t('Review status', 'পর্যালোচনার অবস্থা')}
      aside={<StatusTag status={READINESS[review.readiness]} className="text-[13px]" />}
    >
      <p className="m-0 rounded-[10px] border border-mint-line bg-strong-panel px-4 py-3 text-[15px] font-semibold text-lens-dark">
        {pick(NEXT_ACTION[review.readiness], lang)}
      </p>
      <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
        {review.checks.map((check) => (
          <li key={check.code} className={cn('flex gap-2.5 text-[15px] leading-[22px]', check.passed || check.kind === 'info' ? 'text-ink-2' : 'text-ink')}>
            <CheckIcon check={check} />
            <span>{pick(checkWords(check, review.assessment), lang)}</span>
          </li>
        ))}
      </ul>
      <p className="m-0 text-[13px] text-muted-2">
        {t(
          'These checks look at the evidence only, never at how high the score is. A status is not an approval.',
          'এই যাচাই শুধু প্রমাণ দেখে, স্কোর কত উঁচু তা নয়। কোনো অবস্থা অনুমোদন নয়।',
        )}
      </p>
    </Section>
  )
}

export function RangePanel({ review, className }: { review: ReviewStatus; className?: string }) {
  const t = useT()
  const r = review.range
  const unavailable: Record<string, [string, string]> = {
    no_application: ['Range guidance unavailable: there is no application.', 'পরিসীমার নির্দেশনা নেই: কোনো আবেদন নেই।'],
    assessment_not_current: [
      'Range guidance unavailable: the assessment is not up to date.',
      'পরিসীমার নির্দেশনা নেই: মূল্যায়ন হালনাগাদ নয়।',
    ],
    needs_more_info: [
      'Range guidance unavailable: the band is "Needs more info". Collect more records first.',
      'পরিসীমার নির্দেশনা নেই: ব্যান্ড "আরও তথ্য প্রয়োজন"। আগে আরও রেকর্ড নিন।',
    ],
    not_enough_verified: [
      'Not enough verified information for a range yet.',
      'পরিসীমার জন্য যথেষ্ট যাচাইকৃত তথ্য এখনও নেই।',
    ],
    policy_not_configured: [
      'No range policy is approved for your company yet. Your owner Credit Officer sets one on the Range policy page.',
      'আপনার প্রতিষ্ঠানের কোনো পরিসীমা-নীতি এখনও অনুমোদিত নয়। মালিক ক্রেডিট অফিসার “পরিসীমা-নীতি” পাতায় তা ঠিক করেন।',
    ],
  }
  return (
    <Section id="range" className={className} title={t('Credit range guidance', 'ঋণের পরিসীমার নির্দেশনা')}>
      <div className="flex gap-3 rounded-[12px] border border-line bg-ground p-4">
        <Scale size={22} strokeWidth={1.7} className="shrink-0 text-ink-2" aria-hidden="true" />
        {r.available && r.low_bdt != null && r.high_bdt != null ? (
          <div className="flex min-w-0 flex-col gap-2">
            <span className="text-[13px] text-muted-2">{t('Suggested range to consider', 'বিবেচনার জন্য প্রস্তাবিত পরিসীমা')}</span>
            <span className="text-[24px] font-semibold text-ink tabular-nums">
              {taka(r.low_bdt)} – {taka(r.high_bdt)}
            </span>
            <span className="text-sm text-body">
              {t(
                `How: average monthly wholesale purchases over the last ${r.window_days} days (${taka(r.monthly_purchases_bdt)}) × ${r.multiples?.[0]}–${r.multiples?.[1]} for the band "${r.band}", rounded down${r.capped ? `, capped at the requested ${taka(r.requested_bdt)}` : ''}.`,
                `হিসাব: গত ${r.window_days} দিনের গড় মাসিক পাইকারি কেনাকাটা (${taka(r.monthly_purchases_bdt)}) × ${r.multiples?.[0]}–${r.multiples?.[1]}, ব্যান্ড "${r.band}", নিচের দিকে রাউন্ড করা${r.capped ? `, চাওয়া ${taka(r.requested_bdt)}-এর বেশি নয়` : ''}।`,
              )}
            </span>
            <span className="text-sm text-body">
              {t(
                `Policy ${r.policy_version}. Decision support only: a person decides the amount.`,
                `নীতি ${r.policy_version}। শুধু সিদ্ধান্তে সহায়তা: অঙ্ক একজন মানুষ ঠিক করেন।`,
              )}
            </span>
          </div>
        ) : (
          <div className="flex flex-col gap-1.5">
            <span className="text-[15px] font-semibold text-ink">
              {t(...(unavailable[r.reason ?? 'policy_not_configured'] ?? unavailable.policy_not_configured))}
            </span>
            {r.missing && r.missing.length > 0 && (
              <ul className="m-0 pl-5 text-sm text-body">
                {r.missing.map((m) => (
                  <li key={m}>{t(`Still needed: ${m}`, `এখনও দরকার: ${m}`)}</li>
                ))}
              </ul>
            )}
            <span className="text-sm text-body">
              {t(
                'A range is a separate lending policy, not the score turned into money. Decide the amount under your own lending rules.',
                'পরিসীমা আলাদা একটি ঋণনীতি, স্কোরকে টাকায় বদলানো নয়। নিজের ঋণনীতি মেনে অঙ্ক ঠিক করুন।',
              )}
            </span>
          </div>
        )}
      </div>
    </Section>
  )
}

function askWords(ask: EvidenceRequest, lang: 'en' | 'bn'): string {
  const day = ask.business_date ? fmtDate(ask.business_date) : ''
  const amount = ask.amount_bdt != null ? taka(ask.amount_bdt) : ''
  const words: Record<EvidenceRequest['code'], Pair> = {
    add_purchase_records: { en: 'Ask for the shop’s purchase memos and record them: there are none yet.', bn: 'দোকানের কেনাকাটার মেমো চেয়ে নিয়ে রাখুন: এখনও একটিও নেই।' },
    confirm_not_same_shop: { en: `Check this is not the same shop as ${ask.other_merchant_id}: the name and district match.`, bn: `দেখুন এটি ${ask.other_merchant_id}-এর সাথে একই দোকান নয়: নাম ও জেলা মেলে।` },
    confirm_possible_duplicate: { en: `Ask whether the two purchases of ${amount} on ${day} are different papers.`, bn: `${day}-এর ${amount}-এর দুটি কেনাকাটা আলাদা কাগজ কি না জিজ্ঞেস করুন।` },
    clarify_part_payment: { en: `Ask what is still owed on the repayment due ${day}: ${amount} was not paid.`, bn: `${day}-এ দেয় পরিশোধে এখনও কত বাকি জিজ্ঞেস করুন: ${amount} দেওয়া হয়নি।` },
    show_memo_for_large_purchase: { en: `Ask to see the memo for the ${amount} purchase on ${day}.`, bn: `${day}-এর ${amount}-এর কেনাকাটার মেমো দেখতে চান।` },
  }
  return pick(words[ask.code], lang)
}

/** The smallest evidence worth asking for (fixed rules in the API). Never a promise. */
export function EvidenceRequestsPanel({ review, className }: { review: ReviewStatus; className?: string }) {
  const t = useT()
  const lang = useLang()
  const asks = review.evidence_requests ?? []
  return (
    <Section id="asks" className={className} title={t('Evidence to ask for', 'যে প্রমাণ চাইতে হবে')}>
      {asks.length === 0 ? (
        <p className="m-0 text-[15px] text-body">{t('Nothing to ask the merchant for right now.', 'এখন মার্চেন্টের কাছে কিছু চাওয়ার নেই।')}</p>
      ) : (
        <>
          <ol className="m-0 flex list-decimal flex-col gap-2 pl-5 text-[15px] leading-[22px] text-ink">
            {asks.map((ask, i) => (
              <li key={i}>{askWords(ask, lang)}</li>
            ))}
          </ol>
          <p className="m-0 text-[13px] text-muted-2">
            {t(
              'Ask only for these. More papers do not promise a better score or credit.',
              'শুধু এগুলোই চান। বেশি কাগজ মানেই ভালো স্কোর বা ঋণ নয়।',
            )}
          </p>
        </>
      )}
    </Section>
  )
}

const GROUP_TITLE: Record<EvidenceGroup['group'], Pair> = {
  purchases: { en: 'Stock purchases', bn: 'মাল কেনা' },
  repayments: { en: 'Repayments of earlier loans', bn: 'আগের ঋণের পরিশোধ' },
  deliveries: { en: 'Parcel deliveries (optional)', bn: 'পার্সেল ডেলিভারি (ঐচ্ছিক)' },
  visits: { en: 'Field visits', bn: 'মাঠ পরিদর্শন' },
}

const PAID_WORDS: Record<string, Pair> = {
  paid: { en: 'Paid', bn: 'পরিশোধিত' },
  unpaid: { en: 'Not paid', bn: 'পরিশোধ হয়নি' },
}

function recordDetail(record: ReviewRecord, lang: 'en' | 'bn'): string | null {
  if (!record.detail) return null
  switch (record.record_type) {
    case 'purchase':
      return record.detail.replaceAll('_', ' ')
    case 'payment':
      return pick(PAID_WORDS[record.detail] ?? { en: record.detail, bn: record.detail }, lang)
    case 'delivery':
      return wordsFor(DELIVERY_STATUS_WORDS, record.detail, lang)
    case 'visit':
      return wordsFor(OUTCOME_WORDS, record.detail, lang)
  }
}

function RecordRow({ record }: { record: ReviewRecord }) {
  const t = useT()
  const lang = useLang()
  const detail = recordDetail(record, lang)
  const status = record.status ? RECORD_STATUS[record.status] : GENERATED_RECORD
  return (
    <li className="flex flex-col gap-1 border-t border-line py-2.5 first:border-t-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <span className="text-[15px] text-ink">
          <span className="tabular">{fmtDate(record.business_date)}</span>
          {detail && <span className="text-body"> · {detail}</span>}
        </span>
        {record.amount_bdt != null && <span className="text-[15px] font-semibold text-ink tabular">{taka(record.amount_bdt)}</span>}
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-2">
        <StatusTag status={status} />
        {record.entered_at && (
          <span>
            {t(`Entered ${fmtBdTime(record.entered_at)} (BD time) by ${record.entered_by ?? 'unknown'}`, `রাখা হয়েছে ${fmtBdTime(record.entered_at)} (বাংলাদেশ সময়), ${record.entered_by ?? 'অজানা'}`)}
            {record.simulated && t(' · simulated business date', ' · সিমুলেটেড ব্যবসার তারিখ')}
          </span>
        )}
      </div>
    </li>
  )
}

/** Every evidence group, with how each record entered CredLens. */
export function RecordsPanel({ review, className }: { review: ReviewStatus; className?: string }) {
  const t = useT()
  const lang = useLang()
  const totalBySource: Record<string, number> = {}
  for (const g of review.evidence) for (const [s, n] of Object.entries(g.by_source ?? {})) totalBySource[s] = (totalBySource[s] ?? 0) + n
  return (
    <Section
      id="records"
      className={className}
      title={t('Records and where they came from', 'রেকর্ড ও তাদের উৎস')}
      answer={t(
        'The latest records in each group, how each entered CredLens and what is known about it. Typed-in records are not verified. None of these sources is a live connection.',
        'প্রতিটি দলের সর্বশেষ রেকর্ড, প্রতিটি কীভাবে CredLens-এ এলো এবং এ সম্পর্কে কী জানা আছে। হাতে লেখা রেকর্ড যাচাই করা নয়। কোনো উৎসই সরাসরি সংযোগ নয়।',
      )}
    >
      <SourceLegend counts={totalBySource} />
      <div className="grid gap-4 @3xl:grid-cols-2">
        {review.evidence.map((group) => (
          <div key={group.group} id={`records-${group.group}`} className="flex min-w-0 scroll-mt-4 flex-col gap-2 rounded-[12px] border border-line p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 className="m-0 text-base font-semibold text-ink">{pick(GROUP_TITLE[group.group], lang)}</h3>
              <span className="text-[13px] text-muted-2">
                {t(`${count(group.total)} in total`, `মোট ${count(group.total)}টি`)}
                {group.total > 0 && t(` · ${count(group.with_entry_record)} with an entry record`, ` · ${count(group.with_entry_record)}টির এন্ট্রি রেকর্ড আছে`)}
              </span>
            </div>
            {group.total > 0 && <SourceBar counts={group.by_source ?? {}} label={pick(GROUP_TITLE[group.group], lang)} />}
            {group.latest.length === 0 ? (
              <p className="m-0 text-sm text-body">
                {group.group === 'deliveries'
                  ? t('No delivery records. This never lowers the score.', 'ডেলিভারির রেকর্ড নেই। এতে স্কোর কমে না।')
                  : t('No records in this group.', 'এই দলে কোনো রেকর্ড নেই।')}
              </p>
            ) : (
              <ul className="m-0 list-none p-0">
                {group.latest.map((record, i) => (
                  <RecordRow key={`${record.business_date}-${i}`} record={record} />
                ))}
              </ul>
            )}
            {group.total > group.latest.length && (
              <span className="text-[13px] text-muted-2">
                {t(`Showing the latest ${count(group.latest.length)}. The timeline below has every event.`, `সর্বশেষ ${count(group.latest.length)}টি দেখানো হচ্ছে। নিচের সময়রেখায় সব আছে।`)}
              </span>
            )}
          </div>
        ))}
      </div>
    </Section>
  )
}
