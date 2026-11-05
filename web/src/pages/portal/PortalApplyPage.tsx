/**
 * The merchant applies for a loan (GET and POST /portal/application). The application reaches
 * the lender's Credit Officers like any other. The merchant sees only a plain status, never the
 * score or the officers' notes.
 */
import { HandCoins } from 'lucide-react'
import { useState } from 'react'

import { api, ApiError } from '@/api/client'
import type { ApplicationStatus } from '@/api/types'
import { useApi } from '@/api/useApi'
import { ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { Field, MoneyInput, Select, TextArea } from '@/components/form'
import { Page, PageHeader } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { fmtDate, taka } from '@/lib/format'
import { useT } from '@/lib/i18n'

const PURPOSES: Record<string, [string, string]> = {
  inventory_restock: ['Restock the shop', 'দোকানের মাল তোলা'],
  seasonal_stock: ['Stock for a season or festival', 'মৌসুম বা উৎসবের মাল'],
  shop_equipment: ['Shop equipment', 'দোকানের সরঞ্জাম'],
  other: ['Something else', 'অন্য কিছু'],
}

export function PortalApplyPage() {
  const t = useT()
  const status = useApi<ApplicationStatus>('/portal/application', undefined, { noCache: true })
  const [amount, setAmount] = useState('')
  const [purpose, setPurpose] = useState('inventory_restock')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const s = status.data

  const send = async () => {
    setBusy(true)
    setError(null)
    try {
      await api('/portal/application', { method: 'POST', json: { requested_amount_bdt: Number(amount), purpose, purpose_note: note || null } })
      status.reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Page>
      <PageHeader
        title={t('Apply for a loan', 'ঋণের জন্য আবেদন')}
        description={t('Tell your lender how much you would like and why. A person at your lender will look at your records and decide.', 'আপনি কত টাকা চান ও কেন তা ঋণদাতাকে জানান। ঋণদাতার একজন কর্মী আপনার হিসাব দেখে সিদ্ধান্ত নেবেন।')}
      />
      {status.error ? (
        <ErrorCallout error={status.error} />
      ) : !s ? (
        <LoadingState title={t('Loading…', 'আসছে…')} />
      ) : s.has_application ? (
        <section className="flex flex-col gap-3 rounded-card border border-card-line bg-card p-6">
          <h2 className="m-0 text-[20px] font-semibold text-ink">{t('Your application', 'আপনার আবেদন')}</h2>
          <p className="m-0 text-[28px] font-semibold text-ink">{s.requested_amount_bdt == null ? '' : taka(s.requested_amount_bdt)}</p>
          <p className="m-0 text-[15px] text-body">
            {s.purpose && PURPOSES[s.purpose] ? t(...PURPOSES[s.purpose]) : s.purpose}
            {s.applied_on ? ` · ${t('applied on', 'আবেদনের তারিখ')} ${fmtDate(s.applied_on)}` : ''}
          </p>
          <p className="m-0 rounded-[10px] bg-strong-chip p-4 text-[16px] font-semibold text-lens-dark">{s.status_text}</p>
        </section>
      ) : !s.can_apply ? (
        <p className="m-0 rounded-card border border-card-line bg-card p-6 text-[16px] text-body">{s.cannot_apply_reason}</p>
      ) : (
        <form
          className="flex flex-col gap-5 rounded-card border border-card-line bg-card p-6"
          onSubmit={(e) => {
            e.preventDefault()
            void send()
          }}
        >
          <Field label={t('How much would you like? (BDT)', 'আপনি কত টাকা চান? (টাকা)')} required hint={t(`Up to ${taka(s.max_requested_bdt)}`, `সর্বোচ্চ ${taka(s.max_requested_bdt)}`)}>
            <MoneyInput value={amount} onChange={(e) => setAmount(e.target.value)} />
          </Field>
          <Field label={t('What is it for?', 'কীসের জন্য?')} required>
            <Select value={purpose} onChange={(e) => setPurpose(e.target.value)} options={s.purposes.map((p) => ({ value: p, label: PURPOSES[p] ? t(...PURPOSES[p]) : p }))} />
          </Field>
          <Field label={t('Anything you want to add', 'আর কিছু বলার থাকলে')}>
            <TextArea value={note} maxLength={300} onChange={(e) => setNote(e.target.value)} rows={3} />
          </Field>
          {error && <p role="alert" className="m-0 rounded-[10px] bg-error-panel px-4 py-3 text-[14.5px] text-error">{error}</p>}
          <div>
            <Button size="lg" type="submit" disabled={busy || !Number(amount)}>
              <HandCoins size={20} aria-hidden="true" />
              {busy ? t('Sending…', 'পাঠানো হচ্ছে…') : t('Send my application', 'আবেদন পাঠান')}
            </Button>
          </div>
          <p className="m-0 text-[13.5px] text-muted-2">{t('Sending an application does not mean the loan is approved. Your lender decides.', 'আবেদন পাঠালেই ঋণ অনুমোদিত হয় না। ঋণদাতা সিদ্ধান্ত নেন।')}</p>
        </form>
      )}
    </Page>
  )
}
