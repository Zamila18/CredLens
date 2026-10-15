/**
 * Model card (ModelCard.dc.html): what the model is for, how it was tested and where it
 * falls short. One tab per data source; each tab calls GET /model/card?mode=<mode>.
 * The first tab shown is the mode the API is running.
 *
 * Every value comes from the card. A value a source does not report is not shown:
 * the calibration plot, the "lowest 20 scored" figure and the coverage-group AUCs of
 * the mockup are not in the API, so those blocks are left out.
 */
import { useSearchParams } from 'react-router'

import type { DataMode, Health, ModelCard } from '@/api/types'
import { useApi } from '@/api/useApi'
import { ErrorCallout } from '@/components/ErrorCallout'
import { WarnIcon } from '@/components/icons'
import { Card, Eyebrow, Page, PageHeader } from '@/components/Page'
import { count } from '@/lib/format'
import { MODE_LABELS, MODE_ORDER } from '@/lib/modes'
import { cn } from '@/lib/utils'
import { num, text } from './metrics'
import { AblationCard, AucCard, BandsCard, GroupsCard, SmallMetrics, TestPeriodCard } from './ModelCardParts'

function Facts({ card }: { card: ModelCard }) {
  const m = card.metrics
  const train = num(m, 'train_loans')
  const val = num(m, 'validation_loans')
  const test = num(m, 'test_loans')
  const sizes = [train, val, test].some((v) => v !== undefined)
    ? [train, val, test].map((v) => (v === undefined ? '—' : count(v))).join(' / ')
    : undefined
  const rows: [string, string | undefined, boolean?][] = [
    ['Model in use', text(m, 'model')],
    ['Split', text(m, 'split')],
    ['Loans train / validation / test', sizes, true],
    ['Outcome', text(m, 'label')],
    ['Data terms', text(m, 'terms')],
    ['Version', card.model_version, true],
  ]
  return (
    <dl className="m-0 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1.5 text-[13px] md:max-w-[440px]">
      {rows
        .filter(([, v]) => v)
        .map(([k, v, mono]) => (
          <div key={k} className="contents">
            <dt className="text-muted">{k}</dt>
            <dd className={cn('m-0', mono && 'font-mono break-all tabular', k === 'Model in use' && 'font-semibold')}>{v}</dd>
          </div>
        ))}
    </dl>
  )
}

function Overview({ card }: { card: ModelCard }) {
  const m = card.metrics
  const inputs = text(m, 'inputs')?.split(' | ').filter(Boolean) ?? []
  const firstLimitation = card.limitations[0]
  return (
    <Card className="flex flex-col gap-5 p-6">
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div className="flex max-w-[640px] flex-col gap-1.5">
          <Eyebrow>What this source tells us</Eyebrow>
          <h2 className="m-0 text-xl leading-7 font-semibold tracking-[-0.01em]">{text(m, 'data_source') ?? MODE_LABELS[card.data_mode]}</h2>
          {text(m, 'banner') && <span className="font-mono text-xs text-muted-2">{text(m, 'banner')}</span>}
          <p className="m-0 text-sm text-ink-3">{card.intended_use}</p>
        </div>
        <Facts card={card} />
      </div>
      {firstLimitation && (
        <div className="flex items-start gap-3 rounded-panel bg-amber-chip px-4 py-3.5 text-amber-deep">
          <WarnIcon />
          <span className="text-sm leading-5 font-medium">
            <span className="font-semibold">Read this first: </span>
            {firstLimitation}
          </span>
        </div>
      )}
      {(text(m, 'what_this_shows') || text(m, 'what_this_does_not_show')) && (
        <div className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-4">
          {text(m, 'what_this_shows') && (
            <div className="flex flex-col gap-1.5 rounded-panel bg-strong-panel p-4">
              <span className="text-[13px] font-semibold text-lens-dark">Shows</span>
              <span className="text-sm leading-[21px]">{text(m, 'what_this_shows')}</span>
            </div>
          )}
          {text(m, 'what_this_does_not_show') && (
            <div className="flex flex-col gap-1.5 rounded-panel bg-peri-panel p-4">
              <span className="text-[13px] font-semibold text-peri-head">Does not show</span>
              <span className="text-sm leading-[21px]">{text(m, 'what_this_does_not_show')}</span>
            </div>
          )}
        </div>
      )}
      {inputs.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer font-semibold">Inputs in words ({inputs.length})</summary>
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
  if (items.length === 0) return null
  return (
    <Card className="flex flex-col gap-3 p-5">
      <h2 className="m-0 text-lg font-semibold">Limitations, in plain words</h2>
      <ul className="m-0 flex flex-col gap-2 pl-5 text-sm leading-[21px] text-ink-2">
        {items.map((l) => (
          <li key={l}>{l}</li>
        ))}
      </ul>
    </Card>
  )
}

export function ModelCardPage() {
  const health = useApi<Health>('/health')
  const [params, setParams] = useSearchParams()
  const running = health.data?.data_mode
  const mode = (params.get('mode') as DataMode | null) ?? running
  const card = useApi<ModelCard>(mode ? '/model/card' : null, { mode })

  const hasNumbers = card.data && num(card.data.metrics, 'roc_auc') !== undefined

  return (
    <Page>
      <PageHeader
        title="Model card"
        description="What the model is for, how it was tested and where it falls short. One card per data source, produced by the same code. Decision support for credit officers: the officer decides and records why."
      />

      <div role="tablist" aria-label="Data source" className="flex flex-wrap gap-2">
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
              <span className="font-semibold">{MODE_LABELS[k]}</span>
              <small className="font-mono text-[11px] opacity-75">
                {k}
                {k === running && ' · running'}
              </small>
            </button>
          )
        })}
      </div>

      {card.error ? (
        <ErrorCallout error={card.error} />
      ) : !card.data ? (
        <Card className="p-5 text-sm text-muted">Loading the model card…</Card>
      ) : (
        <>
          <Overview card={card.data} />
          {hasNumbers ? (
            <>
              <section aria-label="Headline metrics" className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-4">
                <AucCard m={card.data.metrics} />
                <SmallMetrics m={card.data.metrics} />
              </section>
              <section className="grid grid-cols-[repeat(auto-fit,minmax(min(360px,100%),1fr))] gap-4">
                <BandsCard m={card.data.metrics} />
                <TestPeriodCard m={card.data.metrics} />
              </section>
              <AblationCard card={card.data} />
              <GroupsCard card={card.data} />
            </>
          ) : (
            <Card className="p-5 text-sm text-ink-3">
              No results have been written for this source yet, so there are no numbers to show.
            </Card>
          )}
          <Limitations items={card.data.limitations} />
        </>
      )}
    </Page>
  )
}
