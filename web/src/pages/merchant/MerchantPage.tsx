/**
 * Merchant detail (approved design: 03-merchant-desktop.png). One scrolling column of
 * full-width sections, in this order: identity → readiness overview → evidence → why this
 * score → unified timeline → financial habits → why might this be wrong → consent →
 * your decision → decisions on this merchant.
 *
 * Calls: GET /merchants/{id} (profile), GET /merchants/{id}/score, GET /merchants/{id}/consent,
 * GET /decisions?merchant_id=; officers also POST a decision and questionnaire answers.
 * Profile and score reads are audited by the API, so they are asked fresh on every visit.
 * "Pending since" and whether a loan is waiting come from the queue (GET /merchants).
 *
 * Without consent the API refuses the score (consent_required): the page then shows the
 * locked state, with no evidence, no reasons, no habits and no decision form.
 */
import { CircleCheck, Lock } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'

import type { ConsentView, Decision, Health, MerchantProfile, ModelCard, QueueItem, Score } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSession } from '@/app/session-context'
import { Chip } from '@/components/BandChip'
import { ErrorCallout } from '@/components/ErrorCallout'
import { Card, Page } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { fmtDate } from '@/lib/format'
import { listInWords, useT, valueText } from '@/lib/i18n'
import { hasQueue } from '@/lib/modes'
import { text } from '../model/metrics'
import { ConsentPanel } from './ConsentPanel'
import { ConsentRequestPanel } from './ConsentRequestPanel'
import { DecisionForm, DecisionHistory, NoPendingLoanNote, ReadOnlyDecisionNote } from './DecisionPanels'
import { EvidenceCards, Timeline } from './Evidence'
import { QuestionnaireForm } from './QuestionnaireForm'
import { HabitsPanel, NoConsentScore, ReadinessOverview, WhyMightThisBeWrong, WhyThisScore } from './ScorePanels'

/** The latest expiry among the records that are not revoked. */
function validUntil(consent: ConsentView | undefined): string | null {
  const dates = (consent?.records ?? [])
    .filter((r) => !r.revoked_at && r.expires_at)
    .map((r) => r.expires_at as string)
    .sort()
  return dates.length ? dates[dates.length - 1] : null
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5 px-4 first:pl-0 max-sm:px-0">
      <dt className="text-[13px] text-muted-2">{label}</dt>
      <dd className="m-0 text-[17px] font-semibold text-ink">{value}</dd>
    </div>
  )
}

function Header({ profile, consent, queueRow }: { profile: MerchantProfile; consent?: ConsentView; queueRow?: QueueItem }) {
  const { lang } = useSession()
  const t = useT()
  const until = consent?.valid ? validUntil(consent) : null
  const consentValid = consent ? consent.valid : profile.consent_valid
  const place = [profile.district, profile.town_tier && valueText(profile.town_tier, lang)].filter(Boolean).join(' · ')

  return (
    <header className="mint-wash flex flex-col gap-5 rounded-card border border-mint-line p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h1 className="m-0 text-[32px] leading-10 font-bold tracking-[-0.02em] sm:text-[36px]">{profile.merchant_id}</h1>
        <div className="flex flex-wrap gap-2">
          {consentValid ? (
            <Chip tone="strong" className="px-3 py-1.5 text-[13px]">
              <CircleCheck size={15} aria-hidden="true" />
              {until ? t(`Consent valid until ${fmtDate(until)}`, `অনুমতি বৈধ ${fmtDate(until)} পর্যন্ত`) : t('Consent valid', 'অনুমতি বৈধ')}
            </Chip>
          ) : (
            <Chip className="px-3 py-1.5 text-[13px]">
              <Lock size={14} aria-hidden="true" />
              {t('No valid consent', 'বৈধ অনুমতি নেই')}
            </Chip>
          )}
          {queueRow?.status === 'pending' && (
            <Chip tone="amber" className="px-3 py-1.5 text-[13px]">
              {t(`Pending since ${fmtDate(queueRow.pending_since)}`, `${fmtDate(queueRow.pending_since)} থেকে অপেক্ষমাণ`)}
            </Chip>
          )}
          {queueRow?.status === 'decided' && (
            <Chip tone="strong" className="px-3 py-1.5 text-[13px]">
              {t('Decided', 'সিদ্ধান্ত হয়েছে')}
            </Chip>
          )}
        </div>
      </div>
      <dl className="m-0 grid grid-cols-2 gap-y-4 sm:grid-cols-4 sm:divide-x sm:divide-mint-line">
        <Fact label={t('Shop type', 'দোকানের ধরন')} value={valueText(profile.shop_type, lang)} />
        <Fact label={t('Location', 'এলাকা')} value={place || '—'} />
        <Fact
          label={t('Trade licence', 'ট্রেড লাইসেন্স')}
          value={profile.has_trade_license == null ? '—' : profile.has_trade_license ? t('yes', 'আছে') : t('no', 'নেই')}
        />
        <Fact label={t('Onboarded', 'যুক্ত হয়েছে')} value={fmtDate(profile.onboarded_at)} />
      </dl>
      {consent && consent.data_categories.length > 0 && (
        <p className="m-0 flex items-center gap-2 rounded-[10px] border border-mint-line bg-white/80 px-4 py-2.5 text-sm text-ink-2">
          <CircleCheck size={16} className="shrink-0 text-lens-dark" aria-hidden="true" />
          {t(`Consent covers ${listInWords(consent.data_categories, lang)}.`, `অনুমতিতে আছে: ${listInWords(consent.data_categories, lang)}।`)}
        </p>
      )}
    </header>
  )
}

function Loading({ what }: { what: string }) {
  return <Card className="p-5 text-sm text-body">{what}</Card>
}

/** One merchant's page. The key makes React start fresh for every merchant (no answers carried over). */
export function MerchantPage() {
  const { merchantId = '' } = useParams()
  return <MerchantView key={merchantId} merchantId={merchantId} />
}

function MerchantView({ merchantId }: { merchantId: string }) {
  const { lang, role } = useSession()
  const t = useT()
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
  const outcome = card.data ? ((lang === 'bn' ? text(card.data.metrics, 'label_bn') : undefined) ?? text(card.data.metrics, 'label')) : undefined

  // Questionnaire answers saved on this visit replace the ones in the profile.
  const [savedAnswers, setSavedAnswers] = useState<MerchantProfile['questionnaire'] | undefined>(undefined)
  const [answering, setAnswering] = useState(false)
  const [justSaved, setJustSaved] = useState(false)

  const breadcrumb = (
    <nav aria-label={t('Breadcrumb', 'পথ')} className="flex items-center gap-2 text-sm text-body">
      <Link to="/queue" className="font-medium no-underline">
        {t('Review queue', 'পর্যালোচনার তালিকা')}
      </Link>
      <span aria-hidden="true">/</span>
      <span className="font-mono" aria-current="page">
        {merchantId}
      </span>
    </nav>
  )

  if (health.data && !rowsAllowed) {
    return (
      <Page>
        {breadcrumb}
        <Card className="flex max-w-[720px] flex-col gap-2 p-5 text-[15px] text-body">
          <span className="font-semibold text-ink">{t('No merchant pages for public data', 'পাবলিক ডেটায় মার্চেন্টের পাতা নেই')}</span>
          <span>
            {t(
              'This data source shows its model card and totals only. Individual rows are not shown.',
              'এই ডেটার উৎস শুধু তার মডেল কার্ড ও মোট হিসাব দেখায়। আলাদা সারি দেখানো হয় না।',
            )}
          </span>
          <Link to="/model" className="font-semibold">
            {t('Open the model card', 'মডেল কার্ড খুলুন')}
          </Link>
        </Card>
      </Page>
    )
  }
  if (profile.error) {
    return (
      <Page>
        {breadcrumb}
        <ErrorCallout error={profile.error} className="max-w-[720px]" />
      </Page>
    )
  }
  if (!profile.data) {
    return (
      <Page>
        {breadcrumb}
        <Loading what={t('Loading the merchant…', 'মার্চেন্টের তথ্য আসছে…')} />
      </Page>
    )
  }

  const noConsent = score.error?.code === 'consent_required' || !profile.data.consent_valid
  const questionnaire = savedAnswers !== undefined ? savedAnswers : profile.data.questionnaire
  const coversQuestionnaire = !consent.data || consent.data.data_categories.includes('questionnaire')
  // A loan is waiting when the merchant is in the review queue (its latest loan has no outcome).
  const loanWaiting = queue.data ? Boolean(queueRow) : true

  let habitsAction = null
  if (justSaved && !answering) {
    habitsAction = <span className="font-medium text-lens-dark">{t('Saved. The score did not change.', 'রাখা হয়েছে। স্কোর বদলায়নি।')}</span>
  } else if (isOfficer && !answering && coversQuestionnaire) {
    habitsAction = (
      <Button
        variant="outline"
        onClick={() => {
          setAnswering(true)
          setJustSaved(false)
        }}
      >
        {t('Record new answers', 'নতুন উত্তর লিখুন')}
      </Button>
    )
  } else if (isOfficer && !coversQuestionnaire) {
    habitsAction = <span>{t('Consent does not cover the questionnaire.', 'অনুমতিতে প্রশ্নাবলি নেই।')}</span>
  }

  return (
    <Page>
      {breadcrumb}
      <Header profile={profile.data} consent={consent.data} queueRow={queueRow} />

      {noConsent ? (
        <>
          <NoConsentScore />
          <ConsentRequestPanel merchantId={merchantId} consent={consent.data} onRequested={consent.reload} />
          {score.error && score.error.code !== 'consent_required' && <ErrorCallout error={score.error} />}
        </>
      ) : score.error ? (
        <ErrorCallout error={score.error} />
      ) : !score.data ? (
        <Loading what={t('Loading the score…', 'স্কোর আসছে…')} />
      ) : (
        <>
          <ReadinessOverview score={score.data} lang={lang} outcome={outcome} />
          <EvidenceCards profile={profile.data} />
          <WhyThisScore score={score.data} lang={lang} />
          <Timeline events={profile.data.timeline ?? []} />
          <HabitsPanel merchantId={merchantId} questionnaire={questionnaire} action={habitsAction}>
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
        <Loading what={t('Loading the consent record…', 'অনুমতির রেকর্ড আসছে…')} />
      )}

      {/* No decision without a score, and none when no loan is waiting. */}
      {score.data && !noConsent && (!isOfficer ? <ReadOnlyDecisionNote /> : loanWaiting ? <DecisionForm merchantId={merchantId} score={score.data} onRecorded={decisions.reload} /> : <NoPendingLoanNote />)}
      <DecisionHistory decisions={decisions.data} error={decisions.error} />
    </Page>
  )
}
