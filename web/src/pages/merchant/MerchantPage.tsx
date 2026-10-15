/**
 * Merchant detail (Merchant.dc.html), read-only part.
 *
 * Calls: GET /merchants/{id} (profile), GET /merchants/{id}/score, GET /merchants/{id}/consent.
 * Profile and score reads are audited by the API, so they are asked fresh on every visit.
 * "Pending since" comes from the queue (GET /merchants), which the sidebar already loads.
 *
 * Without consent the API refuses the score (consent_required): the right column then
 * shows the no-consent dial and the callout, with no decision form and no questionnaire.
 */
import { Link, useParams } from 'react-router'

import type { ConsentView, MerchantProfile, QueueItem, Score } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSession, type Lang } from '@/app/session-context'
import { Chip } from '@/components/BandChip'
import { ErrorCallout } from '@/components/ErrorCallout'
import { CheckIcon } from '@/components/icons'
import { Card, Eyebrow, Page } from '@/components/Page'
import { Segmented } from '@/components/Segmented'
import { humanize } from '@/lib/consent'
import { fmtDate } from '@/lib/format'
import { ConsentPanel } from './ConsentPanel'
import { EvidenceCards, Timeline } from './Evidence'
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

export function MerchantPage() {
  const { merchantId = '' } = useParams()
  const { lang } = useSession()
  const id = encodeURIComponent(merchantId)

  const profile = useApi<MerchantProfile>(`/merchants/${id}`, undefined, { noCache: true })
  const score = useApi<Score>(`/merchants/${id}/score`, undefined, { noCache: true })
  const consent = useApi<ConsentView>(`/merchants/${id}/consent`, undefined, { noCache: true })
  const queue = useApi<QueueItem[]>('/merchants')
  const queueRow = queue.data?.find((r) => r.merchant_id === merchantId)

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
              <ScoreCard score={score.data} lang={lang} />
              <WhyThisScore score={score.data} lang={lang} />
              <HabitsPanel profile={profile.data} />
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
        </div>
      </div>
    </Page>
  )
}
