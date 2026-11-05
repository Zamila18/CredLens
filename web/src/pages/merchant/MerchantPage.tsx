/**
 * Merchant detail: the credit officer's workspace (implementation pack, Phase 6).
 * Identity and the review summary on top; then, on desktop, an evidence and explanation
 * column (score overview, evidence, records with provenance, why this score, timeline,
 * habits, limits, consent) beside an assessment and action column (review status, range
 * guidance, your decision, decision history). On a phone: summary, assessment, evidence,
 * explanation, action.
 *
 * Calls: GET /merchants/{id} (profile), GET /merchants/{id}/score, GET /merchants/{id}/review,
 * GET /merchants/{id}/consent,
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

import type { ConsentView, Decision, Health, MerchantLoan, MerchantProfile, ModelCard, ReviewStatus, Score } from '@/api/types'
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
import { DecisionForm, DecisionHistory, NoPendingLoanNote, ReadOnlyDecisionNote } from './DecisionPanels'
import { EvidenceCards, LoansPanel, Timeline } from './Evidence'
import { AssessmentPanel } from './AssessmentPanel'
import { CreditSummary } from './CreditSummary'
import { MerchantIdCard } from './MerchantIdCard'
import { QuestionnaireForm } from './QuestionnaireForm'
import { EvidenceRequestsPanel, RangePanel, ReadinessPanel, RecordsPanel, ReviewSummary } from './Review'
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

function Header({ profile, consent, status }: { profile: MerchantProfile; consent?: ConsentView; status: 'waiting' | 'decided' | null }) {
  const { lang } = useSession()
  const t = useT()
  const until = consent?.valid ? validUntil(consent) : null
  const consentValid = consent ? consent.valid : profile.consent_valid
  const place = [profile.area, profile.district, profile.town_tier && valueText(profile.town_tier, lang)].filter(Boolean).join(' · ')

  return (
    <header className="mint-wash flex flex-col gap-5 rounded-card border border-mint-line p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <h1 className="m-0 text-[30px] leading-9 font-bold tracking-[-0.02em] break-words sm:text-[34px] sm:leading-10">{profile.shop_name ?? profile.merchant_id}</h1>
          <span className="flex flex-wrap items-center gap-2 text-sm text-body">
            <span className="rounded bg-white/80 px-1.5 py-0.5 font-mono text-[13px] text-ink-2">{profile.merchant_id}</span>
            {profile.area ? <span>{[profile.area, profile.district].filter(Boolean).join(', ')}</span> : null}
          </span>
        </div>
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
          {status === 'waiting' && (
            <Chip tone="amber" className="px-3 py-1.5 text-[13px]">
              {t('Waiting for a decision', 'সিদ্ধান্তের অপেক্ষায়')}
            </Chip>
          )}
          {status === 'decided' && (
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
  // Who may record a credit decision (the server checks the same: src/api/routes_decisions.py).
  const isOfficer = role === 'credit_officer'

  // Public data modes have no merchant pages (and Home Credit rows may never be shown):
  // in those modes the page does not ask for any merchant data at all.
  const health = useApi<Health>('/health')
  const rowsAllowed = hasQueue(health.data?.data_mode)
  const ask = (path: string) => (rowsAllowed ? path : null)

  const profile = useApi<MerchantProfile>(ask(`/merchants/${id}`), undefined, { noCache: true })
  const score = useApi<Score>(ask(`/merchants/${id}/score`), undefined, { noCache: true })
  const consent = useApi<ConsentView>(ask(`/merchants/${id}/consent`), undefined, { noCache: true })
  const review = useApi<ReviewStatus>(ask(`/merchants/${id}/review`), undefined, { noCache: true })
  // The shop's own loans and application say whether something waits for a decision
  // (no need to load the whole review queue for one merchant).
  const loans = useApi<MerchantLoan[]>(ask(`/merchants/${id}/loans`), undefined, { noCache: true })
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
      <Link to="/app/merchants" className="font-medium no-underline">
        {t('Merchants', 'মার্চেন্ট')}
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
          <Link to="/app/model" className="font-semibold">
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
  // A loan (or the application) is waiting when one has no outcome yet.
  const loanWaiting = loans.data ? loans.data.some((l) => !l.has_outcome) : true
  const decided = (decisions.data?.length ?? 0) > 0
  const status: 'waiting' | 'decided' | null = loans.data ? (decided ? 'decided' : loanWaiting ? 'waiting' : null) : null
  // A shop with no loan and no application has nothing to assess yet.
  const notAssessed = score.error?.code === 'unknown_merchant'

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

  // Desktop (xl): an evidence and explanation column, and an assessment and action column.
  // Below xl the two columns melt into one (`contents`) and `order-*` stacks the sections as
  // summary, assessment, evidence, explanation, action. The numbers rise inside each column,
  // so the desktop order is the source order.
  const scoreReady = !noConsent && !score.error && score.data
  return (
    <Page>
      {breadcrumb}
      <Header profile={profile.data} consent={consent.data} status={status} />

      {noConsent ? <NoConsentScore /> : <CreditSummary merchantId={merchantId} canRun={isOfficer} nothingToScore={notAssessed} />}

      {/* The decision sits right under the summary. None without a score, and none when no loan is waiting. */}
      {scoreReady && (!isOfficer ? <ReadOnlyDecisionNote /> : loanWaiting ? <DecisionForm merchantId={merchantId} onRecorded={decisions.reload} /> : <NoPendingLoanNote />)}

      <div className="grid gap-6 xl:grid-cols-2 xl:items-start">
        <DecisionHistory decisions={decisions.data} error={decisions.error} />
        {isOfficer && <MerchantIdCard merchantId={merchantId} />}
      </div>

      <details className="group rounded-card border border-card-line bg-card">
        <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-3 rounded-card px-5 py-3 text-[16px] font-semibold text-ink transition-colors hover:bg-ground">
          {t('Receipts, loans and consent', 'রসিদ, ঋণ ও অনুমতি')}
          <span className="text-[13.5px] font-normal text-muted-2 group-open:hidden">{t('Show', 'দেখুন')}</span>
          <span className="hidden text-[13.5px] font-normal text-muted-2 group-open:inline">{t('Hide', 'লুকান')}</span>
        </summary>
        <div className="flex min-w-0 flex-col gap-6 border-t border-line p-5">
          {!noConsent && review.data && <RecordsPanel review={review.data} className="min-w-0" />}
          {!noConsent && loans.data && loans.data.length > 0 && <LoansPanel loans={loans.data} />}
          {consent.error ? (
            <ErrorCallout error={consent.error} />
          ) : consent.data ? (
            <ConsentPanel consent={consent.data} />
          ) : (
            <Loading what={t('Loading the consent record…', 'অনুমতির রেকর্ড আসছে…')} />
          )}
        </div>
      </details>

      <details className="group rounded-card border border-card-line bg-card">
        <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-3 rounded-card px-5 py-3 text-[16px] font-semibold text-ink transition-colors hover:bg-ground">
          {t('Technical details for analysts', 'বিশ্লেষকদের জন্য কারিগরি তথ্য')}
          <span className="text-[13.5px] font-normal text-muted-2 group-open:hidden">{t('Show', 'দেখুন')}</span>
          <span className="hidden text-[13.5px] font-normal text-muted-2 group-open:inline">{t('Hide', 'লুকান')}</span>
        </summary>
        <div className="flex flex-col gap-6 border-t border-line p-5">
          {review.data ? <ReviewSummary review={review.data} score={score.data} /> : review.error ? <ErrorCallout error={review.error} /> : null}
          {review.data && <ReadinessPanel review={review.data} />}
          {review.data && !noConsent && <EvidenceRequestsPanel review={review.data} />}
          {review.data && <RangePanel review={review.data} />}
          {!noConsent && <AssessmentPanel merchantId={merchantId} canRun={false} />}
          {scoreReady && (
            <>
              <ReadinessOverview score={score.data!} lang={lang} outcome={outcome} />
              <WhyThisScore score={score.data!} lang={lang} />
              <EvidenceCards profile={profile.data} />
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
          {notAssessed && <p className="m-0 text-[15px] text-body">{t('This shop has no application and no loan yet, so there is nothing to assess.', 'এই দোকানের এখনও কোনো আবেদন বা ঋণ নেই, তাই মূল্যায়নের কিছু নেই।')}</p>}
          {score.error && score.error.code !== 'consent_required' && score.error.code !== 'unknown_merchant' && <ErrorCallout error={score.error} />}
        </div>
      </details>
    </Page>
  )
}
