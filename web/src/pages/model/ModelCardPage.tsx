/**
 * Model card (ModelCard.dc.html): what the model is for, how it was tested and where it
 * falls short. One tab per data source; each tab calls GET /model/card?mode=<mode>.
 * The first tab shown is the mode the API is running.
 *
 * Every value comes from the card. A value a source does not report is not shown.
 * The card's own sentences are shown in Bangla when the card has a Bangla version
 * (`<key>_bn`, `limitations_bn`), else in English.
 */
import { useSearchParams } from 'react-router'

import type { DataMode, Health, ModelCard } from '@/api/types'
import { useApi } from '@/api/useApi'
import { ErrorCallout } from '@/components/ErrorCallout'
import { WarnIcon } from '@/components/icons'
import { Card, Eyebrow, Page, PageHeader } from '@/components/Page'
import { count } from '@/lib/format'
import { MODE_TEXT, pick, useLang, useT } from '@/lib/i18n'
import { MODE_ORDER } from '@/lib/modes'
import { cn } from '@/lib/utils'
import { num, textIn } from './metrics'
import { AblationCard, AucCard, BandsCard, CalibrationCard, GroupsCard, SmallMetrics, TestPeriodCard } from './ModelCardParts'

/** The card's limitations in the page's language (Bangla when the card has them). */
function limitationsIn(card: ModelCard, lang: 'en' | 'bn'): string[] {
  const bn = card.limitations_bn
  return lang === 'bn' && bn && bn.length ? bn : card.limitations
}

function Facts({ card }: { card: ModelCard }) {
  const t = useT()
  const lang = useLang()
  const m = card.metrics
  const train = num(m, 'train_loans')
  const val = num(m, 'validation_loans')
  const test = num(m, 'test_loans')
  const sizes = [train, val, test].some((v) => v !== undefined)
    ? [train, val, test].map((v) => (v === undefined ? '—' : count(v))).join(' / ')
    : undefined
  const modelLabel = t('Model in use', 'ব্যবহৃত মডেল')
  const rows: [string, string | undefined, boolean?][] = [
    [modelLabel, textIn(m, 'model', lang)],
    [t('Split', 'ভাগ'), textIn(m, 'split', lang)],
    [t('Loans train / validation / test', 'ঋণ: প্রশিক্ষণ / যাচাই / পরীক্ষা'), sizes, true],
    [t('Outcome', 'ফলাফল'), textIn(m, 'label', lang)],
    [t('Data terms', 'ডেটার শর্ত'), textIn(m, 'terms', lang)],
    [t('Version', 'সংস্করণ'), card.model_version, true],
  ]
  return (
    <dl className="m-0 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1.5 text-[13px] md:max-w-[440px]">
      {rows
        .filter(([, v]) => v)
        .map(([k, v, mono]) => (
          <div key={k} className="contents">
            <dt className="text-muted">{k}</dt>
            <dd className={cn('m-0', mono && 'font-mono break-all tabular', k === modelLabel && 'font-semibold')}>{v}</dd>
          </div>
        ))}
    </dl>
  )
}

function Overview({ card }: { card: ModelCard }) {
  const t = useT()
  const lang = useLang()
  const m = card.metrics
  const inputs = textIn(m, 'inputs', lang)?.split(' | ').filter(Boolean) ?? []
  const firstLimitation = limitationsIn(card, lang)[0]
  const shows = textIn(m, 'what_this_shows', lang)
  const notShows = textIn(m, 'what_this_does_not_show', lang)
  return (
    <Card className="flex flex-col gap-5 p-6">
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div className="flex max-w-[640px] flex-col gap-1.5">
          <Eyebrow>{t('What this source tells us', 'এই উৎস আমাদের কী বলে')}</Eyebrow>
          <h2 className="m-0 text-xl leading-7 font-semibold tracking-[-0.01em]">
            {textIn(m, 'data_source', lang) ?? pick(MODE_TEXT[card.data_mode], lang)}
          </h2>
          {textIn(m, 'banner', lang) && <span className="font-mono text-xs text-muted-2">{textIn(m, 'banner', lang)}</span>}
          <p className="m-0 text-sm text-ink-3">{(lang === 'bn' ? textIn(m, 'intended_use', lang) : undefined) ?? card.intended_use}</p>
        </div>
        <Facts card={card} />
      </div>
      {firstLimitation && (
        <div className="flex items-start gap-3 rounded-panel bg-amber-chip px-4 py-3.5 text-amber-deep">
          <WarnIcon />
          <span className="text-sm leading-5 font-medium">
            <span className="font-semibold">{t('Read this first: ', 'আগে এটি পড়ুন: ')}</span>
            {firstLimitation}
          </span>
        </div>
      )}
      {(shows || notShows) && (
        <div className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-4">
          {shows && (
            <div className="flex flex-col gap-1.5 rounded-panel bg-strong-panel p-4">
              <span className="text-[13px] font-semibold text-lens-dark">{t('Shows', 'যা দেখায়')}</span>
              <span className="text-sm leading-[21px]">{shows}</span>
            </div>
          )}
          {notShows && (
            <div className="flex flex-col gap-1.5 rounded-panel bg-peri-panel p-4">
              <span className="text-[13px] font-semibold text-peri-head">{t('Does not show', 'যা দেখায় না')}</span>
              <span className="text-sm leading-[21px]">{notShows}</span>
            </div>
          )}
        </div>
      )}
      {inputs.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer font-semibold">
            {t('Inputs in words', 'ইনপুটগুলো কথায়')} ({inputs.length})
          </summary>
          <ul className="mt-2 mb-0 flex flex-col gap-1 pl-5 text-ink-2">
            {inputs.map((input) => (
              <li key={input}>{input}</li>
            ))}
          </ul>
        </details>
      )}
    </Card>
  )
}

function Limitations({ items }: { items: string[] }) {
  const t = useT()
  if (items.length === 0) return null
  return (
    <Card className="flex flex-col gap-3 p-5">
      <h2 className="m-0 text-lg font-semibold">{t('Limitations, in plain words', 'সীমাবদ্ধতা, সহজ কথায়')}</h2>
      <ul className="m-0 flex flex-col gap-2 pl-5 text-sm leading-[21px] text-ink-2">
        {items.map((l) => (
          <li key={l}>{l}</li>
        ))}
      </ul>
    </Card>
  )
}

export function ModelCardPage() {
  const t = useT()
  const lang = useLang()
  const health = useApi<Health>('/health')
  const [params, setParams] = useSearchParams()
  const running = health.data?.data_mode
  const mode = (params.get('mode') as DataMode | null) ?? running
  const card = useApi<ModelCard>(mode ? '/model/card' : null, { mode })

  const hasNumbers = card.data && num(card.data.metrics, 'roc_auc') !== undefined

  return (
    <Page>
      <PageHeader
        title={t('Model card', 'মডেল কার্ড')}
        description={t(
          'What the model is for, how it was tested and where it falls short. One card per data source, produced by the same code. Decision support for credit officers: the officer decides and records why.',
          'মডেলটি কীসের জন্য, কীভাবে পরীক্ষা করা হয়েছে, আর কোথায় এর ঘাটতি। প্রতিটি ডেটার উৎসের জন্য একটি কার্ড, একই কোড থেকে তৈরি। ঋণ কর্মকর্তাদের সিদ্ধান্তে সহায়তা: সিদ্ধান্ত নেন কর্মকর্তা, আর কারণ লিখে রাখেন।',
        )}
      />

      <div role="tablist" aria-label={t('Data source', 'ডেটার উৎস')} className="flex flex-wrap gap-2">
        {MODE_ORDER.map((k) => {
          const on = k === mode
          return (
            <button
              key={k}
              type="button"
              role="tab"
              aria-selected={on}
              onClick={() => setParams(k === running ? {} : { mode: k }, { replace: true })}
              className={cn(
                'flex min-h-11 cursor-pointer flex-col items-start gap-0.5 rounded-panel border px-4 py-2.5 text-left font-sans text-sm',
                on ? 'border-ink bg-ink text-white' : 'border-control-line bg-card text-ink-2 hover:border-[#9FAAA3]',
              )}
            >
              <span className="font-semibold">{pick(MODE_TEXT[k], lang)}</span>
              <small className="font-mono text-[11px] opacity-75">
                {k}
                {k === running && t(' · running', ' · চলছে')}
              </small>
            </button>
          )
        })}
      </div>

      {card.error ? (
        <ErrorCallout error={card.error} />
      ) : !card.data ? (
        <Card className="p-5 text-sm text-muted">{t('Loading the model card…', 'মডেল কার্ড আসছে…')}</Card>
      ) : (
        <>
          <Overview card={card.data} />
          {hasNumbers ? (
            <>
              <section aria-label={t('Headline metrics', 'মূল পরিমাপ')} className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-4">
                <AucCard m={card.data.metrics} />
                <SmallMetrics m={card.data.metrics} />
              </section>
              <section className="grid grid-cols-[repeat(auto-fit,minmax(min(360px,100%),1fr))] gap-4">
                <BandsCard m={card.data.metrics} />
                <TestPeriodCard m={card.data.metrics} />
              </section>
              <CalibrationCard m={card.data.metrics} />
              <AblationCard card={card.data} />
              <GroupsCard card={card.data} />
            </>
          ) : (
            <Card className="p-5 text-sm text-ink-3">
              {t(
                'No results have been written for this source yet, so there are no numbers to show.',
                'এই উৎসের ফলাফল এখনও লেখা হয়নি, তাই দেখানোর মতো কোনো সংখ্যা নেই।',
              )}
            </Card>
          )}
          <Limitations items={limitationsIn(card.data, lang)} />
        </>
      )}
    </Page>
  )
}
