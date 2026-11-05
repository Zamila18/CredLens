/**
 * Invitation codes (owner only): make a code for Field Sales Representatives or another Credit
 * Officer, copy it, share it, revoke or regenerate it, and see who joined with it.
 * The full code is shown once, when it is made; afterwards only its last four characters.
 */
import { Copy, RefreshCw, Ban } from 'lucide-react'
import { useState } from 'react'

import { api } from '@/api/client'
import type { InvitationCreatedOut, InvitationOut } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSubmit } from '@/api/useSubmit'
import { EmptyState, ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { Field, FormActions, Select, TextInput } from '@/components/form'
import { Notice } from '@/components/Notice'
import { Page, PageHeader } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { fmtDate } from '@/lib/format'
import { useT } from '@/lib/i18n'

const STATE_WORDS: Record<string, [string, string]> = {
  active: ['Active', 'সক্রিয়'],
  revoked: ['Revoked', 'বাতিল'],
  expired: ['Expired', 'মেয়াদোত্তীর্ণ'],
  used_up: ['All places used', 'সব স্থান পূর্ণ'],
}

export function InvitationsPage() {
  const t = useT()
  const list = useApi<InvitationOut[]>('/org/invitations', undefined, { noCache: true })
  const [role, setRole] = useState('records_officer')
  const [days, setDays] = useState('14')
  const [maxUses, setMaxUses] = useState('5')
  const [label, setLabel] = useState('')
  const [fresh, setFresh] = useState<InvitationCreatedOut | null>(null)
  const [copied, setCopied] = useState(false)
  const create = useSubmit<InvitationCreatedOut>()
  const act = useSubmit<unknown>()

  const make = async () => {
    const made = await create.submit(() =>
      api<InvitationCreatedOut>('/org/invitations', {
        method: 'POST',
        json: { role, days: Number(days), max_uses: Number(maxUses), label: label || null },
      }),
    )
    if (made) {
      setFresh(made)
      setCopied(false)
      list.reload()
    }
  }
  const copy = (text: string) => {
    void navigator.clipboard?.writeText(text).then(() => setCopied(true))
  }
  const run = (path: string) =>
    void act.submit(() => api<InvitationCreatedOut | InvitationOut>(path, { method: 'POST' })).then((r) => {
      if (r && 'code' in (r as object)) {
        setFresh(r as InvitationCreatedOut)
        setCopied(false)
      }
      list.reload()
    })

  return (
    <Page>
      <PageHeader
        title={t('Invitation codes', 'আমন্ত্রণ কোড')}
        description={t(
          'Give colleagues a code so they can register under your company. The code decides the company and the role; it shows the person belongs to your CredLens company, not a legal check of anyone.',
          'সহকর্মীদের একটি কোড দিন যাতে তাঁরা আপনার প্রতিষ্ঠানের অধীনে নিবন্ধন করতে পারেন। কোড ঠিক করে প্রতিষ্ঠান ও ভূমিকা; এটি আপনার CredLens প্রতিষ্ঠানের সাথে সম্পর্ক দেখায়, কারও আইনি যাচাই নয়।',
        )}
      />
      {fresh && (
        <Notice tone="success" title={t('New code. Copy it now: it is shown only once.', 'নতুন কোড। এখনই কপি করুন: এটি একবারই দেখানো হয়।')}>
          <span className="flex flex-wrap items-center gap-3">
            <span className="rounded-[10px] border border-mint-line bg-white px-3 py-1.5 font-mono text-[20px] font-semibold tracking-[0.08em] text-ink">{fresh.code}</span>
            <Button size="sm" variant="outline" onClick={() => copy(fresh.code)}>
              <Copy size={15} aria-hidden="true" />
              {copied ? t('Copied', 'কপি হয়েছে') : t('Copy', 'কপি')}
            </Button>
          </span>
        </Notice>
      )}
      <section className="flex flex-col gap-4 rounded-card border border-card-line bg-card p-4 sm:p-5">
        <h2 className="m-0 text-[18px] font-semibold">{t('Make a code', 'কোড বানান')}</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t('For', 'কার জন্য')} required>
            <Select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              options={[
                { value: 'records_officer', label: t('Records Desk officers', 'রেকর্ড ডেস্কের সদস্য') },
                { value: 'credit_officer', label: t('Another Credit Officer', 'আরেকজন ক্রেডিট অফিসার') },
              ]}
            />
          </Field>
          <Field label={t('Valid for (days)', 'মেয়াদ (দিন)')} required>
            <TextInput inputMode="numeric" value={days} onChange={(e) => setDays(e.target.value)} />
          </Field>
          <Field label={t('How many people may use it', 'কতজন ব্যবহার করতে পারবেন')} required>
            <TextInput inputMode="numeric" value={maxUses} onChange={(e) => setMaxUses(e.target.value)} />
          </Field>
          <Field label={t('Note for yourself (optional)', 'নিজের জন্য নোট (ঐচ্ছিক)')}>
            <TextInput value={label} onChange={(e) => setLabel(e.target.value)} maxLength={80} />
          </Field>
        </div>
        {create.error && <ErrorCallout error={create.error} />}
        <FormActions>
          <Button onClick={() => void make()} disabled={create.pending}>
            {t('Make the code', 'কোড বানান')}
          </Button>
        </FormActions>
      </section>
      <section className="flex flex-col gap-3">
        <h2 className="m-0 text-[18px] font-semibold">{t('Codes and who joined', 'কোড ও কারা যোগ দিয়েছেন')}</h2>
        {list.error ? (
          <ErrorCallout error={list.error} />
        ) : !list.data ? (
          <LoadingState title={t('Loading…', 'আসছে…')} />
        ) : list.data.length === 0 ? (
          <EmptyState title={t('No code yet', 'এখনও কোনো কোড নেই')} text={t('Make the first code above and share it with the people who should join.', 'ওপরে প্রথম কোডটি বানিয়ে যাঁদের যোগ দেওয়ার কথা তাঁদের দিন।')} />
        ) : (
          <ul className="m-0 flex list-none flex-col gap-3 p-0">
            {list.data.map((inv) => (
              <li key={inv.invitation_id} className="flex flex-col gap-2 rounded-card border border-card-line bg-card p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="flex flex-col">
                    <span className="font-semibold text-ink">
                      {inv.role === 'records_officer' ? t('Records Desk officer', 'রেকর্ড ডেস্কের সদস্য') : t('Credit Officer', 'ক্রেডিট অফিসার')} · …{inv.code_hint}
                      {inv.label ? ` · ${inv.label}` : ''}
                    </span>
                    <span className="text-[13px] text-muted-2">
                      {t(STATE_WORDS[inv.state][0], STATE_WORDS[inv.state][1])} · {inv.use_count}/{inv.max_uses} {t('used', 'ব্যবহৃত')} · {t('until', 'পর্যন্ত')} {fmtDate(inv.expires_at)}
                    </span>
                  </span>
                  <span className="flex gap-2">
                    {inv.state === 'active' && (
                      <Button size="sm" variant="ghost" disabled={act.pending} onClick={() => run(`/org/invitations/${inv.invitation_id}/revoke`)}>
                        <Ban size={15} aria-hidden="true" />
                        {t('Revoke', 'বাতিল')}
                      </Button>
                    )}
                    <Button size="sm" variant="outline" disabled={act.pending} onClick={() => run(`/org/invitations/${inv.invitation_id}/regenerate`)}>
                      <RefreshCw size={15} aria-hidden="true" />
                      {t('Regenerate', 'নতুন কোড')}
                    </Button>
                  </span>
                </div>
                {inv.uses.length > 0 && (
                  <ul className="m-0 flex list-none flex-col gap-1 p-0 text-[13.5px] text-body">
                    {inv.uses.map((u) => (
                      <li key={u.user_id}>
                        {u.display_name}
                        {u.employee_id ? ` (ID ${u.employee_id})` : ''} · {fmtDate(u.used_at)}
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        )}
        {act.error && <ErrorCallout error={act.error} />}
      </section>
    </Page>
  )
}
