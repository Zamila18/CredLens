/**
 * Model card (approved design: 06-model-card-desktop.png): what the model is for, how it was
 * tested and where it falls short. One tab per data source; each tab calls
 * GET /model/card?mode=<mode>. The first tab shown is the mode the API is running.
 *
 * Every value comes from the card. A value a source does not report is not shown.
 * The card's own sentences are shown in Bangla when the card has a Bangla version
 * (`<key>_bn`, `limitations_bn`), else in English.
 */
import { useSearchParams } from 'react-router'

import type { DataMode, Health, ModelCard } from '@/api/types'
import { useApi } from '@/api/useApi'
import { ErrorCallout } from '@/components/ErrorCallout'
import { Card, Page, PageHeader, Section } from '@/components/Page'
import { MODE_TEXT, pick, useLang, useT } from '@/lib/i18n'
import { MODE_ORDER } from '@/lib/modes'
import { cn } from '@/lib/utils'
import { auc, num, signed } from './metrics'
import { Accordion, CalibrationSection, CategoriesSection, DeliverySection, GroupsSection, PurposeSection, RankingSection } from './ModelCardParts'

/** The card's limitations in the page's language (Bangla when the card has them). */
function limitationsIn(card: ModelCard, lang: 'en' | 'bn'): string[] {
  const bn = card.limitations_bn
  return lang === 'bn' && bn && bn.length ? bn : card.limitations
}

/** One row of "Other public data sources": validation and later-test AUC from that card. */
function OtherSource({ mode, onOpen }: { mode: DataMode; onOpen: (mode: DataMode) => void }) {
  const t = useT()
  const lang = useLang()
  const card = useApi<ModelCard>('/model/card', { mode })
  const m = card.data?.metrics
  const val = m ? num(m, 'roc_auc') : undefined
  const test = m ? num(m, 'test_roc_auc') : undefined
  const reversed = test !== undefined && test < 0.5
  return (
    <tr className="border-t border-line">
      <td className="py-2">
        <button type="button" onClick={() => onOpen(mode)} className="cursor-pointer border-0 bg-transparent p-0 font-sans text-sm font-semibold text-lens-dark underline-offset-2 hover:underline">
          {pick(MODE_TEXT[mode], lang)}
        </button>
      </td>
      <td className="py-2 text-right tabular">{val !== undefined ? auc(val) : '—'}</td>
      <td className="py-2 text-right tabular">{test !== undefined ? auc(test) : '—'}</td>
      <td className="py-2 text-right tabular">{val !== undefined && test !== undefined ? signed(test - val) : '—'}</td>
      <td className={cn('py-2 pl-4', reversed ? 'font-semibold text-amber-text' : 'text-body')}>
        {card.error
          ? t('card not available', 'কার্ড নেই')
          : reversed
            ? t('Later ranking is reversed; this model must not be used.', 'পরের পরীক্ষায় ক্রম উল্টে গেছে; এই মডেল ব্যবহার করা যাবে না।')
            : val === undefined
              ? t('no results written', 'ফলাফল লেখা হয়নি')
              : t('public data, not ShopUp data', 'পাবলিক ডেটা, ShopUp-এর ডেটা নয়')}
      </td>
    </tr>
  )
}

function KeepInMind({ card, current, onOpen }: { card: ModelCard; current: DataMode; onOpen: (mode: DataMode) => void }) {
  const t = useT()
  const lang = useLang()
  const items = limitationsIn(card, lang)
  const others = MODE_ORDER.filter((k) => k !== current && k !== 'synthetic_bd')
  return (
    <Section
      id="keep-in-mind"
      title={t('What should officers keep in mind?', 'কর্মকর্তাদের কী মনে রাখা উচিত?')}
      answer={t('These results describe a prototype, not established real-world performance.', 'এই ফলাফল একটি প্রোটোটাইপের, বাস্তবে প্রমাণিত কার্যকারিতার নয়।')}
    >
      {items.length > 0 && (
        <ul className="m-0 grid gap-x-8 gap-y-2 rounded-[12px] border border-line bg-ground py-4 pr-4 pl-9 text-sm leading-[21px] text-ink-2 md:grid-cols-2">
          {items.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      )}
      {others.length > 0 && (
        <Accordion title={t('Other public data sources', 'অন্যান্য পাবলিক ডেটার উৎস')} aside={t('Validation and later-test ranking (AUC)', 'যাচাই ও পরের পরীক্ষার ক্রম (AUC)')}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] border-collapse text-sm">
              <thead>
                <tr className="text-left text-[13px] text-ink-2">
                  <th scope="col" className="py-1.5 font-semibold">{t('Source', 'উৎস')}</th>
                  <th scope="col" className="py-1.5 text-right font-semibold">{t('Validation', 'যাচাই')}</th>
                  <th scope="col" className="py-1.5 text-right font-semibold">{t('Later test', 'পরের পরীক্ষা')}</th>
                  <th scope="col" className="py-1.5 text-right font-semibold">{t('Change', 'পরিবর্তন')}</th>
                  <th scope="col" className="py-1.5 pl-4 font-semibold">{t('Note', 'মন্তব্য')}</th>
                </tr>
              </thead>
              <tbody>
                {others.map((k) => (
                  <OtherSource key={k} mode={k} onOpen={onOpen} />
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 mb-0 text-body">
            {t('Open a source for its full card. Real-world effectiveness cannot be inferred from these numbers.', 'পুরো কার্ড দেখতে উৎসটি খুলুন। এই সংখ্যা থেকে বাস্তবের কার্যকারিতা বোঝা যায় না।')}
          </p>
        </Accordion>
      )}
    </Section>
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
  const open = (k: DataMode) => {
    setParams(k === running ? {} : { mode: k }, { replace: true })
    window.scrollTo({ top: 0 })
  }

  const hasNumbers = card.data && num(card.data.metrics, 'roc_auc') !== undefined

  return (
    <Page>
      <PageHeader
        title={t('Model card', 'মডেল কার্ড')}
        description={t(
          'What the model is for, how it was tested and where it falls short. One card per data source, produced by the same code.',
          'মডেলটি কীসের জন্য, কীভাবে পরীক্ষা করা হয়েছে, আর কোথায় এর ঘাটতি। প্রতিটি ডেটার উৎসের জন্য একটি কার্ড, একই কোড থেকে তৈরি।',
        )}
      />

      <div role="tablist" aria-label={t('Data source', 'ডেটার উৎস')} className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
        {MODE_ORDER.map((k) => {
          const on = k === mode
          return (
            <button
              key={k}
              type="button"
              role="tab"
              aria-selected={on}
              onClick={() => open(k)}
              className={cn(
                'flex min-h-14 cursor-pointer flex-col items-center justify-center gap-0.5 rounded-[12px] border px-3 py-2 text-center font-sans',
                on ? 'border-mint-line bg-mint text-lens-dark' : 'border-card-line bg-card text-ink hover:bg-night-2',
              )}
            >
              <span className="text-[15px] font-semibold">
                {pick(MODE_TEXT[k], lang)}
                {k === running && t(' (running)', ' (চলছে)')}
              </span>
              <small className="font-mono text-xs text-body">{k}</small>
            </button>
          )
        })}
      </div>

      {card.error ? (
        <ErrorCallout error={card.error} />
      ) : !card.data || !mode ? (
        <Card className="p-5 text-sm text-body">{t('Loading the model card…', 'মডেল কার্ড আসছে…')}</Card>
      ) : (
        <>
          <PurposeSection card={card.data} firstLimitation={limitationsIn(card.data, lang)[0]} />
          {hasNumbers ? (
            <>
              <RankingSection m={card.data.metrics} />
              <CategoriesSection m={card.data.metrics} />
              <CalibrationSection m={card.data.metrics} />
              <DeliverySection card={card.data} />
              <GroupsSection card={card.data} />
            </>
          ) : (
            <Card className="p-5 text-[15px] text-body">
              {t('No results have been written for this source yet, so there are no numbers to show.', 'এই উৎসের ফলাফল এখনও লেখা হয়নি, তাই দেখানোর মতো কোনো সংখ্যা নেই।')}
            </Card>
          )}
          <KeepInMind card={card.data} current={mode} onOpen={open} />
        </>
      )}
    </Page>
  )
}
