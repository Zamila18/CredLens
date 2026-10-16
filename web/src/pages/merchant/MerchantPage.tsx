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
import { fmtDate } from '@/lib/format'
import { listInWords, useT, valueText } from '@/lib/i18n'
import { hasQueue } from '@/lib/modes'
import { text } from '../model/metrics'
import { ConsentPanel } from './ConsentPanel'
import { DecisionForm, DecisionHistory, ReadOnlyDecisionNote } from './DecisionPanels'
import { EvidenceCards, Timeline } from './Evidence'
import { QuestionnaireForm } from './QuestionnaireForm'
import { HabitsPanel, NoConsentScore, ScoreCard, WhyMightThisBeWrong, WhyThisScore } from './ScorePanels'

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
  const t = useT()
  const until = consent?.valid ? validUntil(consent) : null
  const consentValid = consent ? consent.valid : profile.consent_valid
  const place = [profile.district, profile.town_tier && valueText(profile.town_tier, lang)].filter(Boolean).join(' · ')

  return (
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div className="flex flex-col gap-2.5">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="m-0 font-mono text-[30px] leading-9 font-semibold tracking-[-0.02em]">{profile.merchant_id}</h1>
          {consentValid ? (
            <Chip tone="strong" className="px-2.5 py-1">
              <CheckIcon />{' '}
              {until
                ? t(`Consent valid until ${fmtDate(until)}`, `অনুমতি বৈধ ${fmtDate(until)} পর্যন্ত`)
                : t('Consent valid', 'অনুমতি বৈধ')}
            </Chip>
          ) : (
            <Chip className="px-2.5 py-1">{t('No valid consent', 'বৈধ অনুমতি নেই')}</Chip>
          )}
          {queueRow?.status === 'pending' && queueRow.pending_since && (
            <Chip className="px-2.5 py-1">
              {t(`Pending since ${fmtDate(queueRow.pending_since)}`, `${fmtDate(queueRow.pending_since)} থেকে অপেক্ষমাণ`)}
            </Chip>
          )}
          {queueRow?.status === 'decided' && (
            <Chip tone="strong" className="px-2.5 py-1">
              {t('Decided', 'সিদ্ধান্ত হয়েছে')}
            </Chip>
          )}
        </div>
        <div className="flex flex-wrap gap-x-[18px] gap-y-1.5 text-sm text-ink-3">
          {profile.shop_type && <span>{valueText(profile.shop_type, lang)}</span>}
          {place && <span>{place}</span>}
          {profile.has_trade_license != null && (
            <span>
              {t('Trade licence', 'ট্রেড লাইসেন্স')}: {profile.has_trade_license ? t('yes', 'আছে') : t('no', 'নেই')}
            </span>
          )}
          <span>{t(`Onboarded ${fmtDate(profile.onboarded_at)}`, `যুক্ত হয়েছে ${fmtDate(profile.onboarded_at)}`)}</span>
        </div>
        {consent && consent.data_categories.length > 0 && (
          <div className="text-[13px] text-muted-2">
            {t(
              `Consent covers ${listInWords(consent.data_categories, lang)}.`,
              `অনুমতিতে আছে: ${listInWords(consent.data_categories, lang)}।`,
            )}
          </div>
        )}
      </div>
      <div className="flex flex-col items-end gap-1.5">
        <Eyebrow>
          Language · <span className="font-bn normal-case">ভাষা</span>
        </Eyebrow>
        <Segmented<Lang>
          label="Language / ভাষা"
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
  return <Card className="p-5 text-sm text-muted">{what}</Card>
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
  // In Bangla the card's `label_bn` is used when the card has one (part 4 adds it).
  const outcome = card.data
    ? ((lang === 'bn' ? text(card.data.metrics, 'label_bn') : undefined) ?? text(card.data.metrics, 'label'))
    : undefined

  // Questionnaire answers saved on this visit replace the ones in the profile.
  const [savedAnswers, setSavedAnswers] = useState<MerchantProfile['questionnaire'] | undefined>(undefined)
  const [answering, setAnswering] = useState(false)
  const [justSaved, setJustSaved] = useState(false)

  const breadcrumb = (
    <nav aria-label={t('Breadcrumb', 'পথ')} className="flex items-center gap-2 text-[13px] text-muted">
      <Link to="/" className="font-medium no-underline">
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
      <Page wide>
        {breadcrumb}
        <Card className="flex max-w-[720px] flex-col gap-2 p-5 text-sm text-ink-3">
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
        <Loading what={t('Loading the merchant…', 'মার্চেন্টের তথ্য আসছে…')} />
      </Page>
    )
  }

  const noConsent = score.error?.code === 'consent_required'
  const questionnaire = savedAnswers !== undefined ? savedAnswers : profile.data.questionnaire
  const coversQuestionnaire = !consent.data || consent.data.data_categories.includes('questionnaire')

  let habitsAction = null
  if (justSaved && !answering) {
    habitsAction = (
      <span className="font-medium text-lens-dark">{t('Saved. The score did not change.', 'রাখা হয়েছে। স্কোর বদলায়নি।')}</span>
    )
  } else if (isOfficer && !answering && coversQuestionnaire) {
    habitsAction = (
      <Button variant="outline" size="sm" onClick={() => { setAnswering(true); setJustSaved(false) }}>
        {t('Record new answers', 'নতুন উত্তর লিখুন')}
      </Button>
    )
  } else if (isOfficer && !coversQuestionnaire) {
    habitsAction = <span>{t('Consent does not cover the questionnaire.', 'অনুমতিতে প্রশ্নাবলি নেই।')}</span>
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
            <Loading what={t('Loading the score…', 'স্কোর আসছে…')} />
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
            <Loading what={t('Loading the consent record…', 'অনুমতির রেকর্ড আসছে…')} />
          )}
          {/* No decision without a score: no form when consent is missing or the score failed. */}
          {score.data && (isOfficer ? <DecisionForm merchantId={merchantId} score={score.data} onRecorded={decisions.reload} /> : <ReadOnlyDecisionNote />)}
          <DecisionHistory decisions={decisions.data} error={decisions.error} />
        </div>
      </div>
    </Page>
  )
}
