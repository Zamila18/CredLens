/**
 * Company profile: the registration details (GET /org/profile). The owner can edit a few
 * details, including what the company calls its Field Sales Representatives.
 */
import { useState } from 'react'

import { api } from '@/api/client'
import type { OrganizationProfileOut } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSubmit } from '@/api/useSubmit'
import { useSession } from '@/app/session-context'
import { ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { Field, FormActions, TextInput } from '@/components/form'
import { Notice } from '@/components/Notice'
import { Page, PageHeader } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { fmtDate } from '@/lib/format'
import { useT } from '@/lib/i18n'

export function CompanyPage() {
  const t = useT()
  const { isOwner } = useSession()
  const profile = useApi<OrganizationProfileOut>('/org/profile', undefined, { noCache: true })
  const [contact, setContact] = useState<string | null>(null)
  const save = useSubmit<OrganizationProfileOut>()

  if (profile.error) return <Page><ErrorCallout error={profile.error} /></Page>
  if (!profile.data) return <Page><LoadingState title={t('Loading…', 'আসছে…')} /></Page>
  const p = profile.data
  const rows: [string, string, string | null][] = [
    ['Legal name', 'আইনি নাম', p.legal_name],
    ['Trading name', 'ব্র্যান্ড নাম', p.trading_name],
    ['Registration number', 'নিবন্ধন নম্বর', p.registration_number],
    ['Organisation type', 'প্রতিষ্ঠানের ধরন', p.org_type],
    ['Sector', 'খাত', p.sector],
    ['Official email', 'অফিসিয়াল ইমেইল', p.official_email],
    ['Contact number', 'যোগাযোগ নম্বর', p.contact_number],
    ['Address', 'ঠিকানা', [p.address, p.city, p.division, p.country].filter(Boolean).join(', ')],
    ['Website', 'ওয়েবসাইট', p.website],
    ['Registered', 'নিবন্ধিত', fmtDate(p.created_at)],
  ]

  return (
    <Page>
      <PageHeader title={t('Company profile', 'প্রতিষ্ঠানের তথ্য')} description={t('The details your company registered with.', 'আপনার প্রতিষ্ঠান যে তথ্য দিয়ে নিবন্ধন করেছে।')} />
      <dl className="m-0 grid gap-x-6 gap-y-3 rounded-card border border-card-line bg-card p-5 sm:grid-cols-2">
        {rows.map(([en, bn, value]) => (
          <div key={en} className="flex min-w-0 flex-col gap-0.5">
            <dt className="text-[13px] text-muted-2">{t(en, bn)}</dt>
            <dd className="m-0 break-words text-[15px] font-semibold text-ink">{value || '—'}</dd>
          </div>
        ))}
      </dl>
      {isOwner ? (
        <section className="flex flex-col gap-4 rounded-card border border-card-line bg-card p-5">
          <h2 className="m-0 text-[18px] font-semibold">{t('What you can change', 'যা বদলাতে পারেন')}</h2>
          <Field label={t('Contact number', 'যোগাযোগ নম্বর')}>
            <TextInput value={contact ?? p.contact_number ?? ''} onChange={(e) => setContact(e.target.value)} />
          </Field>
          {save.error && <ErrorCallout error={save.error} />}
          {save.result && <Notice tone="success" title={t('Saved', 'সংরক্ষিত')}>{''}</Notice>}
          <FormActions>
            <Button
              disabled={save.pending}
              onClick={() =>
                void save
                  .submit(() => api<OrganizationProfileOut>('/org/profile', { method: 'PATCH', json: { contact_number: contact ?? p.contact_number } }))
                  .then(() => profile.reload())
              }
            >
              {t('Save', 'সংরক্ষণ')}
            </Button>
          </FormActions>
        </section>
      ) : null}
    </Page>
  )
}
