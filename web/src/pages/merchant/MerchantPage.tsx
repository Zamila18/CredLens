/**
 * Merchant detail (Merchant.dc.html).
 *
 * Calls: GET /merchants/{id} (profile), GET /merchants/{id}/score, GET /merchants/{id}/consent,
 * GET /decisions?merchant_id=; officers also POST a decision and questionnaire answers.
 * Profile and score reads are audited by the API, so they are asked fresh on every visit.
 * "Pending since" comes from the queue (GET /merchants), which the sidebar already loads.
 *
 * Without consent the API refuses the score (consent_required): the right column then
 * shows the no-consent dial and the callout, with no decision form and no questionnaire.
 */
import { useState } from 'react'
import { Link, useParams } from 'react-router'

import type { ConsentView, Decision, Health, MerchantProfile, ModelCard, QueueItem, Score } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSession, type Lang } from '@/app/session-context'
import { Chip } from '@/components/BandChip'
import { ErrorCallout } from '@/components/ErrorCallout'
import { CheckIcon } from '@/components/icons'
import { Card, Eyebrow, Page } from '@/components/Page'
import { Segmented } from '@/components/Segmented'
import { Button } from '@/components/ui/button'
import { humanize } from '@/lib/consent'
import { fmtDate } from '@/lib/format'
import { hasQueue } from '@/lib/modes'
import { text } from '../model/metrics'
import { ConsentPanel } from './ConsentPanel'
import { DecisionForm, DecisionHistory, ReadOnlyDecisionNote } from './DecisionPanels'
import { EvidenceCards, Timeline } from './Evidence'
import { QuestionnaireForm } from './QuestionnaireForm'
import { HabitsPanel, NoConsentScore, ScoreCard, WhyMightThisBeWrong, WhyThisScore } from './ScorePanels'

/** ["purchases", "payments", "questionnaire"] -> "purchases, payments and the questionnaire". */
function listInWords(items: string[]): string {
  const words = items.map((c) => (c === 'questionnaire' ? 'the questionnaire' : c))
  if (words.length <= 1) return words.join('')
  return `${words.slice(0, -1).join(', ')} and ${words[words.length - 1]}`
}

/** The latest expiry among the records that are not revoked. */
function validUntil(consent: ConsentView | undefined): string | null {
  const dates = (consent?.records ?? [])
    .filter((r) => !r.revoked_at && r.expires_at)
    .map((r) => r.expires_at as string)
    .sort()
  return dates.length ? dates[dates.length - 1] : null
}

function Header({ profile, consent, queueRow }: { profile: MerchantProfile; consent?: ConsentView; queueRow?: QueueItem }) {
  const { lang, setLang } = useSession()
  const until = consent?.valid ? validUntil(consent) : null
  const consentValid = consent ? consent.valid : profile.consent_valid
  const place = [profile.district, profile.town_tier].filter(Boolean).join(' · ')

  return (
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div className="flex flex-col gap-2.5">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="m-0 font-mono text-[30px] leading-9 font-semibold tracking-[-0.02em]">{profile.merchant_id}</h1>
          {consentValid ? (
            <Chip tone="strong" className="px-2.5 py-1">
              <CheckIcon /> {until ? `Consent valid until ${fmtDate(until)}` : 'Consent valid'}
            </Chip>
          ) : (
            <Chip className="px-2.5 py-1">No valid consent</Chip>
          )}
          {queueRow?.status === 'pending' && queueRow.pending_since && (
            <Chip className="px-2.5 py-1">Pending since {fmtDate(queueRow.pending_since)}</Chip>
          )}
          {queueRow?.status === 'decided' && (
            <Chip tone="strong" className="px-2.5 py-1">
              Decided
            </Chip>
          )}
        </div>
        <div className="flex flex-wrap gap-x-[18px] gap-y-1.5 text-sm text-ink-3">
          {profile.shop_type && <span>{humanize(profile.shop_type)}</span>}
          {place && <span>{place}</span>}
          {profile.has_trade_license != null && <span>Trade licence: {profile.has_trade_license ? 'yes' : 'no'}</span>}
          <span>Onboarded {fmtDate(profile.onboarded_at)}</span>
        </div>
        {consent && consent.data_categories.length > 0 && (
          <div className="text-[13px] text-muted-2">Consent covers {listInWords(consent.data_categories)}.</div>
        )}
      </div>
      <div className="flex flex-col items-end gap-1.5">
        <Eyebrow>Reason language</Eyebrow>
        <Segmented<Lang>
          label="Reason language"
          value={lang}
          onChange={setLang}
          options={[
            { value: 'en', label: 'English' },
            { value: 'bn', label: <span className="font-bn">বাংলা</span> },
          ]}
        />
      </div>
    </header>
  )
}

function Loading({ what }: { what: string }) {
  return <Card className="p-5 text-sm text-muted">Loading {what}…</Card>
}

/** One merchant's page. The key makes React start fresh for every merchant (no answers carried over). */
export function MerchantPage() {
  const { merchantId = '' } = useParams()
  return <MerchantView key={merchantId} merchantId={merchantId} />
}

function MerchantView({ merchantId }: { merchantId: string }) {
  const { lang, role } = useSession()
  const id = encodeURIComponent(merchantId)
  const isOfficer = role === 'officer'

  // Public data modes have no merchant pages (and Home Credit rows may never be shown):
  // in those modes the page does not ask for any merchant data at all.
  const health = useApi<Health>('/health')
  const rowsAllowed = hasQueue(health.data?.data_mode)
  const ask = (path: string) => (rowsAllowed ? path : null)

  const profile = useApi<MerchantProfile>(ask(`/merchants/${id}`), undefined, { noCache: true })
  const score = useApi<Score>(ask(`/merchants/${id}/score`), undefined, { noCache: true })
  const consent = useApi<ConsentView>(ask(`/merchants/${id}/consent`), undefined, { noCache: true })
  const queue = useApi<QueueItem[]>(ask('/merchants'))
  const queueRow = queue.data?.find((r) => r.merchant_id === merchantId)
  const decisions = useApi<Decision[]>(ask('/decisions'), { merchant_id: merchantId })
  // The outcome the score predicts, in the model card's own words (the 30-day rule lives in config).
  const card = useApi<ModelCard>('/model/card')
  const outcome = card.data ? text(card.data.metrics, 'label') : undefined

  // Questionnaire answers saved on this visit replace the ones in the profile.
  const [savedAnswers, setSavedAnswers] = useState<MerchantProfile['questionnaire'] | undefined>(undefined)
  const [answering, setAnswering] = useState(false)
  const [justSaved, setJustSaved] = useState(false)

  const breadcrumb = (
    <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-[13px] text-muted">
      <Link to="/" className="font-medium no-underline">
        Review queue
      </Link>
      <span aria-hidden="true">/</span>
      <span className="font-mono" aria-current="page">
        {merchantId}
      </span>
    </nav>
  )

  if (health.data && !rowsAllowed) {
    return (
      <Page wide>
        {breadcrumb}
        <Card className="flex max-w-[720px] flex-col gap-2 p-5 text-sm text-ink-3">
          <span className="font-semibold text-ink">No merchant pages for public data</span>
          <span>This data source shows its model card and totals only. Individual rows are not shown.</span>
          <Link to="/model" className="font-semibold">
            Open the model card
          </Link>
        </Card>
      </Page>
    )
  }
  if (profile.error) {
    return (
      <Page wide>
        {breadcrumb}
        <ErrorCallout error={profile.error} className="max-w-[720px]" />
      </Page>
    )
  }
  if (!profile.data) {
    return (
      <Page wide>
        {breadcrumb}
        <Loading what="the merchant" />
      </Page>
    )
  }

  const noConsent = score.error?.code === 'consent_required'
  const questionnaire = savedAnswers !== undefined ? savedAnswers : profile.data.questionnaire
  const coversQuestionnaire = !consent.data || consent.data.data_categories.includes('questionnaire')

  let habitsAction = null
  if (justSaved && !answering) {
    habitsAction = <span className="font-medium text-lens-dark">Saved. The score did not change.</span>
  } else if (isOfficer && !answering && coversQuestionnaire) {
    habitsAction = (
      <Button variant="outline" size="sm" onClick={() => { setAnswering(true); setJustSaved(false) }}>
        Record new answers
      </Button>
    )
  } else if (isOfficer && !coversQuestionnaire) {
    habitsAction = <span>Consent does not cover the questionnaire.</span>
  }

  return (
    <Page wide>
      {breadcrumb}
      <Header profile={profile.data} consent={consent.data} queueRow={queueRow} />

      <div className="flex flex-wrap items-start gap-6">
        {/* Left: evidence */}
        <div className="flex min-w-0 flex-[1_1_520px] flex-col gap-5">
          <EvidenceCards profile={profile.data} />
          <Timeline events={profile.data.timeline ?? []} />
        </div>

        {/* Right: score, reasons, habits, consent */}
        <div className="flex min-w-0 flex-[1_1_460px] flex-col gap-5">
          {noConsent && score.error ? (
            <>
              <NoConsentScore />
              <ErrorCallout error={score.error} />
            </>
          ) : score.error ? (
            <ErrorCallout error={score.error} />
          ) : !score.data ? (
            <Loading what="the score" />
          ) : (
            <>
              <ScoreCard score={score.data} lang={lang} outcome={outcome} />
              <WhyThisScore score={score.data} lang={lang} />
              <HabitsPanel questionnaire={questionnaire} action={habitsAction}>
                {answering && (
                  <QuestionnaireForm
                    merchantId={merchantId}
                    lang={lang}
                    onCancel={() => setAnswering(false)}
                    onSaved={(summary) => {
                      setSavedAnswers(summary)
                      setAnswering(false)
                      setJustSaved(true)
                    }}
                  />
                )}
              </HabitsPanel>
              <WhyMightThisBeWrong />
            </>
          )}
          {consent.error ? (
            <ErrorCallout error={consent.error} />
          ) : consent.data ? (
            <ConsentPanel consent={consent.data} />
          ) : (
            <Loading what="the consent record" />
          )}
          {/* No decision without a score: no form when consent is missing or the score failed. */}
          {score.data && (isOfficer ? <DecisionForm merchantId={merchantId} score={score.data} onRecorded={decisions.reload} /> : <ReadOnlyDecisionNote />)}
          <DecisionHistory decisions={decisions.data} error={decisions.error} />
        </div>
      </div>
    </Page>
  )
}
