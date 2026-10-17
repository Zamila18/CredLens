/**
 * "Ask for consent" (Oct 17): on the page of a merchant without a valid consent.
 *
 * An officer can record a request; the merchant gets it in their own app (in production).
 * A request never grants consent and scores nothing: only the merchant can grant consent,
 * and the consent system's record then reaches CredLens like any other record.
 * Admin and viewer see the earlier requests but cannot ask. POST /merchants/{id}/consent-request.
 */
import { Send } from 'lucide-react'
import { useState } from 'react'

import { ApiError, api } from '@/api/client'
import type { ConsentRequest, ConsentView } from '@/api/types'
import { useSession } from '@/app/session-context'
import { ErrorCallout } from '@/components/ErrorCallout'
import { Section } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { fmtBdTime } from '@/lib/format'
import { useT } from '@/lib/i18n'

export function ConsentRequestPanel({ merchantId, consent, onRequested }: { merchantId: string; consent?: ConsentView; onRequested: () => void }) {
  const t = useT()
  const { role, user } = useSession()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [sent, setSent] = useState<ConsentRequest | null>(null)
  const requests = consent?.consent_requests ?? []

  async function ask() {
    setBusy(true)
    setError(null)
    try {
      const result = await api<ConsentRequest>(`/merchants/${encodeURIComponent(merchantId)}/consent-request`, { method: 'POST' })
      setSent(result)
      onRequested()
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, 'network', String(err)))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Section
      id="ask-consent"
      title={t('Ask for consent', 'অনুমতি চান')}
      answer={t(
        'The merchant can still give permission at any time, in their own app. You can send them a request; only they can grant it.',
        'মার্চেন্ট যেকোনো সময় নিজের অ্যাপে অনুমতি দিতে পারেন। আপনি অনুরোধ পাঠাতে পারেন; অনুমতি দিতে পারেন শুধু তিনিই।',
      )}
    >
      {sent ? (
        <p role="status" className="m-0 rounded-[12px] border border-mint-line bg-mint-2 px-4 py-3 text-[15px] text-ink">
          <b className="font-semibold text-lens-dark">{t('Request recorded.', 'অনুরোধ রাখা হয়েছে।')}</b>{' '}
          {t(
            'In production the merchant gets it in their own app. Nothing is scored until they grant consent.',
            'বাস্তবে মার্চেন্ট এটি নিজের অ্যাপে পান। তিনি অনুমতি না দেওয়া পর্যন্ত কিছুই স্কোর হয় না।',
          )}
        </p>
      ) : role === 'officer' ? (
        <div className="flex flex-wrap items-center gap-3">
          <Button size="lg" disabled={busy} onClick={ask}>
            <Send size={17} aria-hidden="true" />
            {busy ? t('Sending…', 'পাঠানো হচ্ছে…') : t('Ask for consent', 'অনুমতি চান')}
          </Button>
          <span className="text-[13px] text-body">{t('Recorded in the audit log. It does not grant consent.', 'অডিট লগে লেখা থাকে। এটি অনুমতি দেয় না।')}</span>
        </div>
      ) : (
        <p className="m-0 text-[15px] text-body">
          {t('Only officers send consent requests. You are using the demo role', 'শুধু কর্মকর্তারা অনুমতির অনুরোধ পাঠান। আপনি ডেমো ভূমিকায় আছেন')}{' '}
          <span className="font-mono font-semibold text-ink">{user}</span>.
        </p>
      )}
      {error && <ErrorCallout error={error} />}
      {requests.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-semibold text-ink">{t('Earlier requests', 'আগের অনুরোধ')}</span>
          <ul className="m-0 flex list-none flex-col gap-1 p-0 text-sm text-body">
            {requests.map((r) => (
              <li key={r.requested_at + r.requested_by}>
                {fmtBdTime(r.requested_at)} {t('(Bangladesh time) · by', '(বাংলাদেশ সময়) ·')} <span className="font-medium text-ink">{r.requested_by}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Section>
  )
}
