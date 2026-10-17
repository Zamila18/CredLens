/**
 * Merchant page sections (approved design: 03-merchant-desktop.png): readiness overview,
 * "Why this score", financial habits, "Why might this be wrong?" and the no-consent state.
 * Every number comes from GET /merchants/{id}/score or the profile; nothing is made up.
 */
import type { LucideIcon } from 'lucide-react'
import { ArrowDown, BadgeInfo, CalendarCheck, ChartNoAxesColumn, Check, Database, FileText, Lock, Minus, Package, Users, X } from 'lucide-react'
import type { ReactNode } from 'react'

import type { Lang } from '@/app/session-context'
import type { Band, InputPoints, MerchantProfile, Reason, Score } from '@/api/types'
import { BandChip, Chip } from '@/components/BandChip'
import { CoverageBar } from '@/components/CoverageBar'
import { Section } from '@/components/Page'
import { ScoreRing } from '@/components/ScoreRing'
import { fmtDate, pct } from '@/lib/format'
import { useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { coverageItemText, groupText, inputName } from './scoreWords'

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
      {(score.inputs?.length > 0 || score.coverage_items?.length > 0) && (
        <div className="grid gap-4 lg:grid-cols-2">
          {score.inputs?.length > 0 && <ScoreBySource score={score} lang={lang} />}
          {score.coverage_items?.length > 0 && <CoverageChecklist score={score} lang={lang} />}
        </div>
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

function signed2(n: number) {
  return `${n >= 0 ? '+' : '−'}${Math.abs(n).toFixed(2)}`
}

/** A whole-number axis that holds every contribution and zero. */
function axis(values: number[]): { low: number; high: number } {
  const low = Math.min(0, Math.floor(Math.min(0, ...values)))
  const high = Math.max(0, Math.ceil(Math.max(0, ...values)))
  return { low: low === high ? -1 : low, high: high === low ? 1 : high }
}

/** The inputs of a card. Older API answers have only the top reasons: use those. */
function inputsOf(score: Score): InputPoints[] {
  if (score.inputs?.length) return score.inputs
  return [...score.reasons_positive, ...score.reasons_negative].map((r: Reason) => ({
    code: r.code,
    group: '',
    label: r.code,
    has_data: true,
    points: r.contribution,
    sentence_en: r.sentence_en,
    sentence_bn: r.sentence_bn,
    detail: r.detail ?? null,
  }))
}

/** "Where the score came from": the average merchant, then the points of each data source. */
function ScoreBySource({ score, lang }: { score: Score; lang: Lang }) {
  const t = useT()
  const order = ['purchases', 'payments', 'deliveries']
  const groups = order
    .map((g) => {
      const items = score.inputs.filter((i) => i.group === g)
      return { group: g, points: items.reduce((s, i) => s + i.points, 0), anyData: items.some((i) => i.has_data) }
    })
    .filter((g) => score.inputs.some((i) => i.group === g.group))
  return (
    <div className="flex flex-col gap-3 rounded-[12px] border border-line bg-white/80 p-4">
      <span className="text-[15px] font-semibold text-ink">{t('Where the score came from', 'স্কোর কোথা থেকে এলো')}</span>
      <ol className="m-0 flex list-none flex-col gap-1.5 p-0 text-sm text-ink-2">
        <li className="flex items-center justify-between gap-3">
          <span>{t('Average merchant', 'গড় মার্চেন্ট')}</span>
          <span className="font-semibold text-ink tabular">{score.baseline_score.toFixed(1)}</span>
        </li>
        {groups.map((g) => (
          <li key={g.group} className="flex items-center justify-between gap-3 border-t border-line pt-1.5">
            <span className="flex items-center gap-2">
              {g.anyData ? (
                <span className={cn('size-2.5 rounded-full', g.points >= 0 ? 'bg-band-strong' : 'bg-band-review')} aria-hidden="true" />
              ) : (
                <Minus size={12} className="text-muted-2" aria-hidden="true" />
              )}
              {groupText(g.group, lang)}
            </span>
            <span className={cn('tabular', !g.anyData ? 'text-muted-2' : g.points >= 0 ? 'font-semibold text-lens-dark' : 'font-semibold text-amber-text')}>
              {g.anyData ? `${g.points >= 0 ? '+' : '−'}${abs1(g.points)}` : t('no data · 0', 'তথ্য নেই · 0')}
            </span>
          </li>
        ))}
        <li className="flex items-center justify-between gap-3 border-t border-control-line pt-1.5">
          <span className="font-semibold text-ink">{t('Score', 'স্কোর')}</span>
          <span className="font-display text-lg font-bold text-ink tabular">{score.score}</span>
        </li>
      </ol>
      <a href="#reasons" className="inline-flex items-center gap-1 self-start text-sm font-semibold no-underline">
        {t('See every input below', 'নিচে প্রতিটি ইনপুট দেখুন')} <ArrowDown size={14} aria-hidden="true" />
      </a>
    </div>
  )
}

/** "Why coverage is 35%": the checklist, each item with its weight, ✓ or ✗. */
function CoverageChecklist({ score, lang }: { score: Score; lang: Lang }) {
  const t = useT()
  const missing = score.coverage_items.filter((x) => !x.present)
  return (
    <div className="flex flex-col gap-3 rounded-[12px] border border-line bg-white/80 p-4">
      <span className="text-[15px] font-semibold text-ink">
        {t(`Why coverage is ${pct(score.coverage)}`, `কভারেজ কেন ${pct(score.coverage)}`)}
      </span>
      <ul className="m-0 flex list-none flex-col gap-1.5 p-0 text-sm">
        {score.coverage_items.map((x) => (
          <li key={x.item} className="flex items-center justify-between gap-3">
            <span className={cn('flex items-center gap-2', x.present ? 'text-ink-2' : 'text-muted-2')}>
              {x.present ? (
                <Check size={16} strokeWidth={2.5} className="shrink-0 text-band-strong" aria-label={t('present', 'আছে')} />
              ) : (
                <X size={16} strokeWidth={2.5} className="shrink-0 text-muted-2" aria-label={t('missing', 'নেই')} />
              )}
              {coverageItemText(x.item, lang)}
            </span>
            <span className={cn('tabular', x.present ? 'font-semibold text-ink' : 'text-muted-2 line-through')}>{Math.round(x.weight * 100)}%</span>
          </li>
        ))}
      </ul>
      <span className="text-[13px] text-body">
        {missing.length === 0
          ? t('Every item is present.', 'সব কিছুই আছে।')
          : t(
              `To raise coverage, collect: ${missing.map((x) => { const s = coverageItemText(x.item, 'en'); return s.charAt(0).toLowerCase() + s.slice(1) }).join('; ')}. Coverage never changes the score.`,
              `কভারেজ বাড়াতে সংগ্রহ করুন: ${missing.map((x) => coverageItemText(x.item, 'bn')).join('; ')}। কভারেজ স্কোর বদলায় না।`,
            )}
      </span>
    </div>
  )
}

/** One input: dot, sentence (or its name) and detail, the points, and a bar drawn to scale around zero. */
function InputRow({ input, lang, low, high }: { input: InputPoints; lang: Lang; low: number; high: number }) {
  const t = useT()
  const helps = input.points >= 0
  const sentence = (lang === 'bn' ? input.sentence_bn : input.sentence_en) ?? inputName(input.code, input.label, lang)
  const span = high - low
  const zero = ((0 - low) / span) * 100
  const width = (Math.abs(input.points) / span) * 100
  const left = helps ? zero : zero - width
  return (
    <li className="grid grid-cols-[14px_minmax(0,1fr)_64px] items-start gap-x-3 gap-y-2 border-t border-line py-3 md:grid-cols-[14px_minmax(0,1fr)_64px_minmax(180px,0.8fr)]">
      <span className={cn('mt-1.5 size-3 rounded-full', input.points === 0 ? 'bg-[#B4C3C8]' : helps ? 'bg-band-strong' : 'bg-band-review')} aria-hidden="true" />
      <span className="flex flex-col gap-0.5">
        <span className="text-[15px] leading-[22px] text-ink">{sentence}</span>
        <span className="text-[13px] text-muted-2">
          {input.group && `${groupText(input.group, lang)} · `}
          {input.detail ?? t('no notable effect', 'উল্লেখযোগ্য প্রভাব নেই')}
        </span>
      </span>
      <span className={cn('pt-0.5 text-right text-[15px] font-semibold tabular', input.points === 0 ? 'text-muted-2' : helps ? 'text-lens-dark' : 'text-amber-text')}>
        {signed2(input.points)}
      </span>
      <span className="relative col-span-3 h-6 md:col-span-1" aria-hidden="true">
        <span className="absolute inset-y-0 w-px bg-control-line" style={{ left: `${zero}%` }} />
        {input.points !== 0 && (
          <span
            className={cn('absolute top-1 h-4 rounded-[4px]', helps ? 'bg-band-strong/70' : 'bg-band-review/70')}
            style={{ left: `${left}%`, width: `${Math.max(width, 0.8)}%` }}
          />
        )}
      </span>
    </li>
  )
}

export function WhyThisScore({ score, lang }: { score: Score; lang: Lang }) {
  const t = useT()
  const inputs = inputsOf(score)
  const withData = inputs.filter((i) => i.has_data).sort((a, b) => b.points - a.points)
  const noData = inputs.filter((i) => !i.has_data)
  const { low, high } = axis(withData.map((i) => i.points))
  const zero = ((0 - low) / (high - low)) * 100
  const helps = withData.filter((i) => i.points > 0).reduce((s, i) => s + i.points, 0)
  const holds = withData.filter((i) => i.points < 0).reduce((s, i) => s + i.points, 0)
  // Each input's points are rounded to 2 decimals and the score to a whole number;
  // whatever the rounding leaves is shown, so the line always adds up.
  const listed = score.inputs?.length ? 0 : score.other_contribution
  const rounding = score.score - score.baseline_score - helps - holds - listed

  return (
    <Section
      id="reasons"
      title={t('Why this score', 'কেন এই স্কোর')}
      answer={t(
        'Every input the model uses, from this merchant’s own records. Observations, not causes. Green raised the score, amber held it back; each bar is drawn to scale.',
        'মডেল যত ইনপুট ব্যবহার করে, সব, এই মার্চেন্টের নিজের রেকর্ড থেকে। পর্যবেক্ষণ, কারণ নয়। সবুজ স্কোর বাড়িয়েছে, হলুদ পিছিয়ে দিয়েছে; প্রতিটি দাগ মাপমতো আঁকা।',
      )}
    >
      {withData.length === 0 ? (
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
            {withData.map((input) => (
              <InputRow key={input.code} input={input} lang={lang} low={low} high={high} />
            ))}
          </ul>
          <span className="pt-1 text-right text-xs text-muted-2">{t('Contribution (points)', 'অবদান (পয়েন্ট)')}</span>
        </div>
      )}

      {noData.length > 0 && (
        <div className="flex flex-col gap-2 rounded-[12px] border border-line bg-ground p-4">
          <span className="text-[15px] font-semibold text-ink">
            {t('No data, so 0 points', 'তথ্য নেই, তাই 0 পয়েন্ট')}
          </span>
          <span className="text-[13px] text-body">
            {t('Missing data never lowers a score; it lowers coverage instead.', 'তথ্য না থাকলে স্কোর কমে না; কমে কভারেজ।')}
          </span>
          <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
            {noData.map((i) => (
              <li key={i.code} className="rounded-full border border-line bg-white px-3 py-1 text-[13px] text-ink-2">
                {inputName(i.code, i.label, lang)}
                {i.group && <span className="text-muted-2"> · {groupText(i.group, lang)}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* baseline + helps + holds back (+ rounding) = score */}
      <div
        className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1.5 rounded-[12px] bg-ground px-4 py-3 text-[15px] text-ink-2 tabular"
        aria-label={t(
          `Average merchant ${abs1(score.baseline_score)}, plus ${abs1(helps)} from what helps, minus ${abs1(holds)} from what holds back, gives ${score.score}`,
          `গড় মার্চেন্ট ${abs1(score.baseline_score)}, সাহায্যকারী থেকে যোগ ${abs1(helps)}, পিছিয়ে দেওয়া থেকে বিয়োগ ${abs1(holds)}, মোট ${score.score}`,
        )}
      >
        <span>
          <b className="font-semibold text-ink">{score.baseline_score.toFixed(1)}</b> {t('average merchant', 'গড় মার্চেন্ট')}
        </span>
        <span className="text-lens-dark">
          + {abs1(helps)} {t('helps', 'সাহায্য')}
        </span>
        <span className="text-amber-text">
          − {abs1(holds)} {t('holds back', 'পিছিয়ে দেয়')}
        </span>
        {listed !== 0 && (
          <span>
            {listed < 0 ? '−' : '+'} {abs1(listed)} {t('everything else', 'বাকি সব')}
          </span>
        )}
        {Math.abs(rounding) >= 0.05 && (
          <span className="text-muted-2">
            {rounding < 0 ? '−' : '+'} {abs1(rounding)} {t('rounding', 'পূর্ণসংখ্যা করা')}
          </span>
        )}
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
