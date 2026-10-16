/**
 * Portfolio (Portfolio.dc.html): how the book splits across bands, how each band
 * actually repaid, and how officers use the score.
 *
 * Sources: GET /model/card (bands and repayment on the validation loans, group results),
 * GET /merchants (today's queue by band), GET /decisions (officer use, decisions per day).
 * Every band segment carries a written label, so colour is never the only cue.
 */
import { useMemo } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import type { Decision, Health, ModelCard, QueueItem } from '@/api/types'
import { useApi } from '@/api/useApi'
import { ErrorCallout } from '@/components/ErrorCallout'
import { Card, Page, PageHeader } from '@/components/Page'
import { isOverride } from '@/lib/actions'
import { count, fmtDate, pct } from '@/lib/format'
import { BAND_TEXT, MODE_TEXT, pick, useLang, useT } from '@/lib/i18n'
import { hasQueue } from '@/lib/modes'
import { cn } from '@/lib/utils'
import { num, text } from './model/metrics'
import { GroupsCard } from './model/ModelCardParts'

type Segment = { label: string; short: string; share: number; className: string }

/** A 100% stacked bar with a 2px gap between segments and the label written inside. */
function StackedBar({ segments, height = 40, ariaLabel }: { segments: Segment[]; height?: number; ariaLabel: string }) {
  return (
    <div role="img" aria-label={ariaLabel} className="flex gap-0.5 overflow-hidden rounded-[10px]" style={{ height }}>
      {segments
        .filter((s) => s.share > 0)
        .map((s) => (
          <div
            key={s.label}
            title={`${s.label} ${pct(s.share)}`}
            className={cn('flex min-w-0 items-center overflow-hidden px-3 text-sm font-semibold whitespace-nowrap', s.className)}
            style={{ width: `${s.share * 100}%` }}
          >
            {/* Narrow segments use the short name so the label still fits. */}
            {s.share >= 0.2 ? `${s.label} ${pct(s.share)}` : `${s.short} ${pct(s.share)}`}
          </div>
        ))}
    </div>
  )
}

const SEG = {
  strong: 'bg-lens text-white',
  review: 'bg-marigold text-[#3F2502]',
  nmi: 'bg-[repeating-linear-gradient(90deg,#5A6894_0_6px,#7E8BB4_6px_9px)] text-white',
  none: 'bg-neutral-chip text-neutral-text',
}

function BandsSection({ card, queue, showQueue }: { card: ModelCard; queue?: QueueItem[]; showQueue: boolean }) {
  const t = useT()
  const lang = useLang()
  const strongName = pick(BAND_TEXT.Strong, lang)
  const reviewName = pick(BAND_TEXT.Review, lang)
  const nmiName = pick(BAND_TEXT['Needs more info'], lang)
  const m = card.metrics
  const strong = num(m, 'band_strong_share')
  const review = num(m, 'band_review_share')
  const nmi = num(m, 'band_needs_more_info_share')
  const loans = num(m, 'validation_loans')

  const queueSegments = useMemo(() => {
    if (!queue || queue.length === 0) return null
    const share = (pred: (r: QueueItem) => boolean) => queue.filter(pred).length / queue.length
    return [
      { label: strongName, short: strongName, share: share((r) => r.band === 'Strong'), className: SEG.strong },
      { label: reviewName, short: t('Rev.', 'পর্য.'), share: share((r) => r.band === 'Review'), className: SEG.review },
      { label: nmiName, short: t('NMI', 'আরও তথ্য'), share: share((r) => r.band === 'Needs more info'), className: SEG.nmi },
      { label: t('No consent', 'অনুমতি নেই'), short: t('None', 'নেই'), share: share((r) => !r.consent_valid), className: SEG.none },
    ]
  }, [queue, t, strongName, reviewName, nmiName])

  if (strong === undefined || review === undefined || nmi === undefined) {
    return <Card className="p-5 text-sm text-ink-3">{t('This source does not report band shares.', 'এই উৎস ব্যান্ডের ভাগ জানায় না।')}</Card>
  }

  const tiles = [
    {
      name: strongName,
      repaid: num(m, 'band_strong_share_repaid'),
      panel: 'bg-strong-panel',
      head: 'text-lens-dark',
      note: t('repaid in time', 'সময়মতো পরিশোধ'),
    },
    {
      name: reviewName,
      repaid: num(m, 'band_review_share_repaid'),
      panel: 'bg-amber-panel',
      head: 'text-amber-text',
      note: t('repaid: the band that needs an officer’s eye', 'পরিশোধ: যে ব্যান্ডে কর্মকর্তার নজর দরকার'),
    },
    {
      name: nmiName,
      repaid: num(m, 'band_needs_more_info_share_repaid'),
      panel: 'bg-peri-panel',
      head: 'text-peri-text',
      note: t('repaid: thin files are not bad files', 'পরিশোধ: কম তথ্য মানে খারাপ ফাইল নয়'),
    },
  ]

  return (
    <Card className="flex flex-col gap-5 p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="m-0 text-lg font-semibold">{t('Bands and what happened next', 'ব্যান্ড, এবং পরে যা ঘটেছে')}</h2>
        <span className="font-mono text-xs text-muted">
          {loans !== undefined && t(`${count(loans)} validation loans · `, `${count(loans)}টি যাচাইয়ের ঋণ · `)}
          {pick(MODE_TEXT[card.data_mode], lang)}
        </span>
      </div>
      {(() => {
        const label = (lang === 'bn' ? text(m, 'label_bn') : undefined) ?? text(m, 'label')
        return label && <span className="-mt-3 text-[13px] text-muted">{label}{lang === 'bn' ? '।' : '.'}</span>
      })()}
      <StackedBar
        ariaLabel={t(
          `Validation loans: Strong ${pct(strong)}, Review ${pct(review)}, Needs more info ${pct(nmi)}`,
          `যাচাইয়ের ঋণ: ${strongName} ${pct(strong)}, ${reviewName} ${pct(review)}, ${nmiName} ${pct(nmi)}`,
        )}
        segments={[
          { label: strongName, short: strongName, share: strong, className: SEG.strong },
          { label: reviewName, short: t('Rev.', 'পর্য.'), share: review, className: SEG.review },
          { label: nmiName, short: t('NMI', 'আরও তথ্য'), share: nmi, className: SEG.nmi },
        ]}
      />
      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(240px,100%),1fr))] gap-4">
        {tiles.map((tile) => (
          <div key={tile.name} className={cn('flex flex-col gap-1.5 rounded-panel p-4', tile.panel)}>
            <span className={cn('text-[13px] font-semibold', tile.head)}>{tile.name}</span>
            <span className="font-mono text-[30px] font-semibold tabular">{pct(tile.repaid, 1)}</span>
            <span className="text-[13px] text-ink-3">{tile.note}</span>
          </div>
        ))}
      </div>
      {showQueue && queueSegments && queue && (
        <div className="flex flex-col gap-2 border-t border-line-soft pt-4">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <span className="text-sm font-semibold">{t('Review queue today', 'আজকের পর্যালোচনার তালিকা')}</span>
            <span className="font-mono text-xs text-muted">
              {t(`${count(queue.length)} merchants · outcomes not known yet`, `${count(queue.length)} জন মার্চেন্ট · ফলাফল এখনও জানা নেই`)}
            </span>
          </div>
          <StackedBar
            height={28}
            ariaLabel={queueSegments.map((s) => `${s.label} ${pct(s.share)}`).join(', ')}
            segments={queueSegments}
          />
        </div>
      )}
    </Card>
  )
}

function OfficerUse({ decisions }: { decisions: Decision[] }) {
  const t = useT()
  const accepts = decisions.filter((d) => d.officer_action === 'accept').length
  const overrides = decisions.filter((d) => isOverride(d.officer_action)).length
  const moreInfo = decisions.filter((d) => d.officer_action === 'needs_more_info').length
  const rate = decisions.length ? overrides / decisions.length : undefined

  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="m-0 text-lg font-semibold">{t('How officers use the score', 'কর্মকর্তারা স্কোর কীভাবে ব্যবহার করেন')}</h2>
        <span className="font-mono text-xs text-muted">
          {t(`${count(decisions.length)} decisions recorded`, `${count(decisions.length)}টি সিদ্ধান্ত রাখা হয়েছে`)}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-3">
        {[
          [accepts, t('accepted', 'মেনে নেওয়া')],
          [overrides, t('overridden, with a reason', 'কারণসহ পরিবর্তন')],
          [moreInfo, t('asked for more info', 'আরও তথ্য চাওয়া')],
        ].map(([n, label]) => (
          <div key={label} className="flex flex-col gap-1">
            <span className="font-mono text-[28px] font-semibold tabular">{count(n as number)}</span>
            <span className="text-[13px] text-ink-3">{label}</span>
          </div>
        ))}
      </div>
      <div className="flex flex-col gap-1.5">
        <div className="flex justify-between text-sm">
          <span>{t('Override rate', 'পরিবর্তনের হার')}</span>
          <span className="font-mono font-semibold tabular">{rate === undefined ? '—' : pct(rate)}</span>
        </div>
        <div className="h-2.5 overflow-hidden rounded-[5px] bg-line-soft" aria-hidden="true">
          <span className="block h-2.5 rounded-[5px] bg-amber" style={{ width: `${(rate ?? 0) * 100}%` }} />
        </div>
        <span className="text-[13px] text-muted">
          {t(
            'A rate near zero can mean rubber-stamping; a rate near half means the score is not helping. Both are worth a conversation.',
            'হার শূন্যের কাছে হলে হয়তো না দেখেই মেনে নেওয়া হচ্ছে; অর্ধেকের কাছে হলে স্কোর কাজে আসছে না। দুটোই আলোচনার বিষয়।',
          )}
        </span>
      </div>
    </Card>
  )
}

type DayCount = { day: string; label: string; decisions: number }

function DayTooltip({ active, payload }: { active?: boolean; payload?: { payload: DayCount }[] }) {
  const t = useT()
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="rounded-lg border border-card-line bg-card px-3 py-2 text-[13px] shadow-[0_2px_8px_rgba(19,32,28,.12)]">
      <div className="text-muted">{fmtDate(d.day)}</div>
      <div className="font-mono font-semibold tabular">
        {d.decisions} {t(d.decisions === 1 ? 'decision' : 'decisions', 'টি সিদ্ধান্ত')}
      </div>
    </div>
  )
}

function DecisionsOverTime({ decisions }: { decisions: Decision[] }) {
  const t = useT()
  const days = useMemo<DayCount[]>(() => {
    const byDay = new Map<string, number>()
    for (const d of decisions) {
      const day = d.decided_at.slice(0, 10)
      byDay.set(day, (byDay.get(day) ?? 0) + 1)
    }
    return [...byDay.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([day, n]) => ({ day, label: fmtDate(day).split(' ').slice(0, 2).join(' '), decisions: n }))
  }, [decisions])

  return (
    <Card className="flex flex-col gap-4 p-5">
      <h2 className="m-0 text-lg font-semibold">{t('Decisions over time', 'সময়ের সাথে সিদ্ধান্ত')}</h2>
      {days.length === 0 ? (
        <p className="m-0 text-sm text-ink-3">
          {t(
            'No decisions recorded yet. Officers record them on a merchant’s page.',
            'এখনও কোনো সিদ্ধান্ত রাখা হয়নি। কর্মকর্তারা মার্চেন্টের পাতায় সিদ্ধান্ত রাখেন।',
          )}
        </p>
      ) : (
        <>
          <div
            className="h-[180px]"
            role="img"
            aria-label={days.map((d) => `${fmtDate(d.day)}: ${d.decisions}`).join('. ')}
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={days} margin={{ top: 8, right: 4, bottom: 0, left: -24 }}>
                <CartesianGrid vertical={false} stroke="#EEF0EA" />
                <XAxis dataKey="label" tickLine={false} axisLine={{ stroke: '#C3C9C0' }} tick={{ fontFamily: 'IBM Plex Mono', fontSize: 12, fill: '#4C5853' }} />
                <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fontFamily: 'IBM Plex Mono', fontSize: 12, fill: '#4C5853' }} />
                <Tooltip content={<DayTooltip />} cursor={{ fill: '#F2F8F5' }} />
                <Bar dataKey="decisions" fill="#0E5A4A" radius={[4, 4, 0, 0]} maxBarSize={44} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <span className="text-[13px] text-muted">
            {t('Decisions recorded per day. Hover a bar for the count.', 'প্রতিদিন রাখা সিদ্ধান্ত। সংখ্যা দেখতে বারের ওপর মাউস রাখুন।')}
          </span>
        </>
      )}
    </Card>
  )
}

export function PortfolioPage() {
  const t = useT()
  const health = useApi<Health>('/health')
  const showQueue = hasQueue(health.data?.data_mode)
  const card = useApi<ModelCard>(health.data ? '/model/card' : null)
  const queue = useApi<QueueItem[]>(showQueue ? '/merchants' : null)
  const decisions = useApi<Decision[]>(showQueue ? '/decisions' : null, undefined, { noCache: true })

  return (
    <Page>
      <PageHeader
        title={t('Portfolio', 'পোর্টফোলিও')}
        description={t(
          'How the book splits across bands, how each band actually repaid, and how officers use the score.',
          'ঋণগুলো কোন ব্যান্ডে কতটা, প্রতিটি ব্যান্ড আসলে কতটা পরিশোধ করেছে, আর কর্মকর্তারা স্কোর কীভাবে ব্যবহার করেন।',
        )}
      />

      {card.error ? (
        <ErrorCallout error={card.error} />
      ) : card.data ? (
        <BandsSection card={card.data} queue={queue.data} showQueue={showQueue} />
      ) : (
        <Card className="p-5 text-sm text-muted">{t('Loading…', 'আসছে…')}</Card>
      )}

      {showQueue && (
        <section className="grid grid-cols-[repeat(auto-fit,minmax(min(340px,100%),1fr))] gap-4">
          {decisions.error ? (
            <ErrorCallout error={decisions.error} />
          ) : decisions.data ? (
            <>
              <OfficerUse decisions={decisions.data} />
              <DecisionsOverTime decisions={decisions.data} />
            </>
          ) : (
            <Card className="p-5 text-sm text-muted">{t('Loading decisions…', 'সিদ্ধান্ত আসছে…')}</Card>
          )}
        </section>
      )}

      {card.data && <GroupsCard card={card.data} />}
    </Page>
  )
}
