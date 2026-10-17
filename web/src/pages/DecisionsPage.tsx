/**
 * Decision log (approved design: 04-decision-log-desktop.png): every human decision, with
 * the score, band and coverage that were on screen and the model that made it. GET /decisions.
 * Nothing can be edited or deleted. Asked fresh on every visit, so decisions recorded
 * elsewhere show up. Times are stored in UTC and shown in Bangladesh time (UTC+06:00).
 * Every number on this page is counted from the real decisions; none is a sample.
 */
import { Lock } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router'

import type { Decision, OfficerAction } from '@/api/types'
import { useApi } from '@/api/useApi'
import { ActionChip } from '@/components/ActionChip'
import { BandChip } from '@/components/BandChip'
import { ErrorCallout } from '@/components/ErrorCallout'
import { FilterSelect, Pager, SearchBox } from '@/components/Filters'
import { Card, Page, PageHeader } from '@/components/Page'
import { ScoreRing } from '@/components/ScoreRing'
import { ACTION_SHORT, isOverride } from '@/lib/actions'
import { count, fmtBdTime, pct } from '@/lib/format'
import { ACTION_TEXT, pick, useLang, useT } from '@/lib/i18n'

const PAGE_SIZE = 25

/** A question card: the question, a plain answer, a visual, and what the number means. */
function QuestionCard({ question, answer, children }: { question: string; answer: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3 rounded-card border border-card-line bg-card p-5">
      <h2 className="m-0 text-[17px] leading-6 font-semibold">{question}</h2>
      <p className="m-0 text-[15px] text-body">{answer}</p>
      <div className="mt-auto">{children}</div>
    </section>
  )
}

/** A small ring for a share (e.g. 80% of suggestions kept). */
function ShareRing({ share }: { share: number }) {
  const size = 88
  const stroke = 10
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} aria-hidden="true">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#E6EEF0" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="#16845B"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${(c * share).toFixed(1)} ${c.toFixed(1)}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center font-display text-lg font-bold text-ink">{Math.round(share * 100)}%</span>
    </div>
  )
}

/** The score as it was on screen: ring, band and coverage (only the number for decisions before Oct 17). */
function ShownScore({ d }: { d: Decision }) {
  const t = useT()
  if (!d.band_shown || d.coverage_shown == null) {
    return (
      <span className="flex flex-col">
        <span className="text-lg font-bold text-ink tabular">{d.score_shown}/100</span>
        <span className="text-xs text-muted-2">{t('band not saved (older decision)', 'ব্যান্ড রাখা হয়নি (পুরোনো সিদ্ধান্ত)')}</span>
      </span>
    )
  }
  return (
    <span className="flex items-center gap-3">
      <ScoreRing score={d.score_shown} band={d.band_shown} coverage={d.coverage_shown} size={60} />
      <span className="flex flex-col items-start gap-1">
        <BandChip band={d.band_shown} lowScoreWarning={d.band_shown !== 'Needs more info' && d.score_shown < 70} />
        <span className="text-[13px] text-body tabular">
          {pct(d.coverage_shown)} {t('coverage', 'কভারেজ')}
        </span>
      </span>
    </span>
  )
}

export function DecisionsPage() {
  const t = useT()
  const lang = useLang()
  const decisions = useApi<Decision[]>('/decisions', undefined, { noCache: true })
  const [merchant, setMerchant] = useState('')
  const [action, setAction] = useState<OfficerAction | 'all'>('all')
  const [page, setPage] = useState(1)

  const all = useMemo(() => [...(decisions.data ?? [])].sort((a, b) => b.decided_at.localeCompare(a.decided_at)), [decisions.data])

  const stats = useMemo(() => {
    const accepts = all.filter((d) => d.officer_action === 'accept').length
    const overrides = all.filter((d) => isOverride(d.officer_action))
    return {
      accepts,
      overrides: overrides.length,
      overridesWithReason: overrides.filter((d) => (d.reason_text ?? '').trim() !== '').length,
      moreInfo: all.filter((d) => d.officer_action === 'needs_more_info').length,
      models: [...new Set(all.map((d) => d.model_version))],
    }
  }, [all])

  const filtered = useMemo(() => {
    const needle = merchant.trim().toLowerCase()
    return all.filter((d) => (action === 'all' || d.officer_action === action) && (!needle || d.merchant_id.toLowerCase().includes(needle)))
  }, [all, merchant, action])

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const current = Math.min(page, pages)
  const visible = filtered.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE)
  const loaded = decisions.data !== undefined
  const kept = stats.accepts + stats.overrides

  return (
    <Page>
      <PageHeader
        title={
          <span className="flex flex-wrap items-center gap-3">
            {t('Decision log', 'সিদ্ধান্তের খাতা')}
            <span className="inline-flex items-center gap-1.5 rounded-full border border-control-line bg-white px-3 py-1 font-sans text-sm font-medium text-ink-2">
              <Lock size={15} aria-hidden="true" /> {t('Append-only', 'শুধু যোগ করা যায়')}
            </span>
          </span>
        }
        description={t(
          'Every human decision, with the score that was on screen and the model that made it. Nothing here can be edited or deleted.',
          'মানুষের নেওয়া প্রতিটি সিদ্ধান্ত, তখন পর্দায় যে স্কোর ছিল এবং যে মডেল তা দিয়েছিল সেসহ। এখানে কিছুই বদলানো বা মোছা যায় না।',
        )}
      />

      <div className="grid gap-4 md:grid-cols-3">
        <QuestionCard
          question={t('Do officers keep the suggested band?', 'কর্মকর্তারা কি প্রস্তাবিত ব্যান্ড রাখেন?')}
          answer={
            !loaded
              ? '…'
              : kept === 0
                ? t('No accepts or overrides recorded yet.', 'এখনও কোনো মেনে নেওয়া বা পরিবর্তন রাখা হয়নি।')
                : t(
                    `Officers kept ${count(stats.accepts)} of ${count(kept)} suggestions they accepted or overrode.`,
                    `মেনে নেওয়া বা পরিবর্তন করা ${count(kept)}টি পরামর্শের ${count(stats.accepts)}টি কর্মকর্তারা রেখেছেন।`,
                  )
          }
        >
          {loaded && kept > 0 && (
            <div className="flex items-center gap-4">
              <ShareRing share={stats.accepts / kept} />
              <span className="flex flex-col">
                <span className="font-display text-2xl font-bold text-ink">{t(`${count(stats.accepts)} of ${count(kept)}`, `${count(kept)}-এর মধ্যে ${count(stats.accepts)}`)}</span>
                <span className="text-[13px] text-body">{t('Requests for more information are left out.', '"আরও তথ্য" চাওয়া এখানে ধরা হয়নি।')}</span>
              </span>
            </div>
          )}
        </QuestionCard>
        <QuestionCard
          question={t('Do overrides explain why?', 'পরিবর্তনে কি কারণ লেখা থাকে?')}
          answer={
            !loaded
              ? '…'
              : stats.overrides === 0
                ? t('No overrides recorded yet.', 'এখনও কোনো পরিবর্তন রাখা হয়নি।')
                : t(
                    `${count(stats.overridesWithReason)} of ${count(stats.overrides)} overrides include a written reason.`,
                    `${count(stats.overrides)}টি পরিবর্তনের ${count(stats.overridesWithReason)}টিতে লিখিত কারণ আছে।`,
                  )
          }
        >
          {loaded && stats.overrides > 0 && (
            <div className="flex flex-col gap-2">
              <div className="h-3 overflow-hidden rounded-full bg-track" aria-hidden="true">
                <span className="block h-3 rounded-full bg-band-strong" style={{ width: `${(stats.overridesWithReason / stats.overrides) * 100}%` }} />
              </div>
              <span className="font-display text-2xl font-bold text-ink">{t(`${count(stats.overridesWithReason)} of ${count(stats.overrides)}`, `${count(stats.overrides)}-এর মধ্যে ${count(stats.overridesWithReason)}`)}</span>
              <span className="text-[13px] text-body">{t('The API refuses an override without a reason.', 'কারণ ছাড়া পরিবর্তন API নেয় না।')}</span>
            </div>
          )}
        </QuestionCard>
        <QuestionCard
          question={t('Who needs more evidence?', 'কার আরও প্রমাণ দরকার?')}
          answer={
            !loaded
              ? '…'
              : t(`Officers asked for more information on ${count(stats.moreInfo)} ${stats.moreInfo === 1 ? 'decision' : 'decisions'}.`, `${count(stats.moreInfo)}টি সিদ্ধান্তে কর্মকর্তারা আরও তথ্য চেয়েছেন।`)
          }
        >
          {loaded && (
            <div className="flex flex-col">
              <span className="font-display text-[32px] leading-10 font-bold text-ink">{count(stats.moreInfo)}</span>
              <span className="text-[13px] text-body">{t(stats.moreInfo === 1 ? 'request to collect more evidence' : 'requests to collect more evidence', 'আরও প্রমাণ জোগাড়ের অনুরোধ')}</span>
            </div>
          )}
        </QuestionCard>
      </div>

      {decisions.error ? (
        <ErrorCallout error={decisions.error} />
      ) : (
        <Card className="flex flex-col gap-4 p-4 sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex flex-col gap-1">
              <h2 className="m-0 text-[22px] leading-7 font-semibold">{t('What did each officer decide?', 'প্রত্যেক কর্মকর্তা কী সিদ্ধান্ত নিয়েছেন?')}</h2>
              <p className="m-0 text-[15px] text-body">
                {t('Each row keeps the decision, its reason and the score shown at that moment.', 'প্রতিটি সারিতে সিদ্ধান্ত, তার কারণ আর সেই মুহূর্তে দেখানো স্কোর থাকে।')}
              </p>
            </div>
            <div className="flex flex-wrap items-end gap-3">
              <SearchBox
                className="w-[280px] max-w-full"
                value={merchant}
                onChange={(v) => {
                  setMerchant(v)
                  setPage(1)
                }}
                placeholder={t('Search merchant ID (e.g. M000031)', 'মার্চেন্ট আইডি খুঁজুন (যেমন M000031)')}
              />
              <FilterSelect
                label={t('Action', 'পদক্ষেপ')}
                value={action}
                onChange={(v) => {
                  setAction(v as OfficerAction | 'all')
                  setPage(1)
                }}
                options={[
                  { value: 'all', label: t('All', 'সব') },
                  ...(Object.keys(ACTION_SHORT) as OfficerAction[]).map((a) => ({ value: a, label: pick(ACTION_TEXT[a].label, lang) })),
                ]}
              />
            </div>
          </div>
          <div className="flex flex-wrap justify-between gap-2 text-[13px] text-body">
            <span>{t('Score: readiness out of 100. Coverage: how much expected evidence was available.', 'স্কোর: ১০০-এর মধ্যে প্রস্তুতি। কভারেজ: প্রত্যাশিত প্রমাণের কতটা ছিল।')}</span>
            <span>{t('Times shown in Bangladesh time (UTC+06:00)', 'সময় বাংলাদেশ সময়ে (UTC+06:00)')}</span>
          </div>
          <div className="overflow-x-auto rounded-[12px] border border-line" role="region" aria-label={t('Decisions', 'সিদ্ধান্ত')} tabIndex={0}>
            <table className="w-full min-w-[960px] border-collapse text-[15px]">
              <thead className="bg-ground">
                <tr className="text-left text-sm text-ink-2">
                  <th scope="col" className="px-4 py-3 font-semibold">{t('When', 'কখন')}</th>
                  <th scope="col" className="px-4 py-3 font-semibold">{t('Merchant', 'মার্চেন্ট')}</th>
                  <th scope="col" className="px-4 py-3 font-semibold">{t('Score at the time of the decision', 'সিদ্ধান্তের সময়ের স্কোর')}</th>
                  <th scope="col" className="px-4 py-3 font-semibold">{t('Action', 'পদক্ষেপ')}</th>
                  <th scope="col" className="px-4 py-3 font-semibold">{t('Why', 'কেন')}</th>
                  <th scope="col" className="px-4 py-3 font-semibold">{t('Officer', 'কর্মকর্তা')}</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((d) => (
                  <tr key={d.decision_id} className="border-t border-line align-top">
                    <td className="px-4 py-4 whitespace-nowrap text-ink-2 tabular">{fmtBdTime(d.decided_at)}</td>
                    <td className="px-4 py-4 font-semibold">
                      <Link to={`/merchants/${encodeURIComponent(d.merchant_id)}`} className="no-underline">
                        {d.merchant_id}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <ShownScore d={d} />
                    </td>
                    <td className="px-4 py-4">
                      <ActionChip action={d.officer_action} />
                    </td>
                    <td className="max-w-[340px] px-4 py-4 leading-[22px] text-ink">
                      {d.reason_text ??
                        (d.officer_action === 'accept' ? t('No note. Accepting needs none.', 'কোনো নোট নেই। মেনে নিতে নোট লাগে না।') : t('No note.', 'কোনো নোট নেই।'))}
                    </td>
                    <td className="px-4 py-4 text-ink-2">{d.officer_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {decisions.loading && <div className="px-5 py-10 text-center text-sm text-body">{t('Loading decisions…', 'সিদ্ধান্ত আসছে…')}</div>}
            {loaded && all.length === 0 && (
              <div className="px-5 py-10 text-center text-[15px] text-body">
                {t('No decisions recorded yet. Officers record them on a merchant’s page.', 'এখনও কোনো সিদ্ধান্ত রাখা হয়নি। কর্মকর্তারা মার্চেন্টের পাতায় সিদ্ধান্ত রাখেন।')}
              </div>
            )}
            {loaded && all.length > 0 && filtered.length === 0 && (
              <div className="px-5 py-10 text-center text-[15px] text-body">{t('No decisions match these filters.', 'এই ফিল্টারে কোনো সিদ্ধান্ত মেলেনি।')}</div>
            )}
          </div>
          {loaded && all.length > 0 && (
            <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-body">
              <span>{t(`${count(filtered.length)} of ${count(all.length)} decisions`, `${count(all.length)}টি সিদ্ধান্তের মধ্যে ${count(filtered.length)}টি`)}</span>
              <Pager page={current} pages={pages} onPage={setPage} />
            </div>
          )}
        </Card>
      )}

      {stats.models.length > 0 && (
        <Card className="flex flex-col gap-1 px-5 py-4">
          <span className="text-[15px] text-ink">
            {t(stats.models.length === 1 ? 'Model for these records:' : 'Models for these records:', 'এই রেকর্ডগুলোর মডেল:')}{' '}
            <span className="font-mono text-sm">{stats.models.join(', ')}</span>
          </span>
          <span className="text-[13px] text-body">{t('The model version identifies how the displayed scores were produced.', 'মডেল সংস্করণ বলে দেখানো স্কোর কীভাবে তৈরি হয়েছিল।')}</span>
        </Card>
      )}
      <Card className="flex flex-col gap-1 px-5 py-4">
        <span className="text-[15px] text-ink">
          {t('Decisions are', 'সিদ্ধান্ত')} <b className="font-semibold">{t('append-only', 'শুধু যোগ করা যায়')}</b>
          {t('. To change course, record a new decision.', '। মত বদলালে নতুন সিদ্ধান্ত রাখুন।')}
        </span>
        <span className="text-[13px] text-body">{t('New decisions are recorded on a merchant’s page.', 'নতুন সিদ্ধান্ত মার্চেন্টের পাতায় রাখা হয়।')}</span>
      </Card>
    </Page>
  )
}
