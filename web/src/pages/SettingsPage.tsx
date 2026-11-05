/**
 * Settings: who is signed in, the language, and the password (POST /auth/password). A merchant
 * has no password (they sign in with their Merchant ID), so that part is hidden for them.
 */
import { useState } from 'react'
import { Link } from 'react-router'

import { api, ApiError } from '@/api/client'
import { useSession } from '@/app/session-context'
import { LanguageSwitch } from '@/app/AppShell'
import { ROLE_NAMES } from '@/app/navigation'
import { Field, TextInput } from '@/components/form'
import { Page, PageHeader } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { pick, useT } from '@/lib/i18n'

export function SettingsPage() {
  const t = useT()
  const { me, role, lang, isOwner } = useSession()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [again, setAgain] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ tone: 'ok' | 'bad'; text: string } | null>(null)

  const change = async () => {
    setMessage(null)
    if (next !== again) {
      setMessage({ tone: 'bad', text: t('The two new passwords are not the same.', 'নতুন পাসওয়ার্ড দুটি একই নয়।') })
      return
    }
    setBusy(true)
    try {
      await api('/auth/password', { method: 'POST', json: { current, new: next } })
      setMessage({ tone: 'ok', text: t('Your password was changed.', 'আপনার পাসওয়ার্ড বদলানো হয়েছে।') })
      setCurrent('')
      setNext('')
      setAgain('')
    } catch (err) {
      setMessage({ tone: 'bad', text: err instanceof ApiError ? err.message : String(err) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Page>
      <PageHeader title={t('Settings', 'সেটিংস')} description={t('Your account and your language.', 'আপনার অ্যাকাউন্ট ও ভাষা।')} />
      <section className="flex flex-col gap-3 rounded-card border border-card-line bg-card p-5">
        <h2 className="m-0 text-[18px] font-semibold">{t('Your account', 'আপনার অ্যাকাউন্ট')}</h2>
        <dl className="m-0 grid gap-3 sm:grid-cols-2">
          {[
            [t('Name', 'নাম'), me?.display_name ?? '—'],
            [t('Role', 'ভূমিকা'), pick(ROLE_NAMES[role], lang)],
            [t('Company', 'প্রতিষ্ঠান'), me?.organization_name ?? '—'],
          ].map(([label, value]) => (
            <div key={String(label)} className="rounded-[10px] border border-line px-3 py-2.5">
              <dt className="text-[13px] text-muted-2">{label}</dt>
              <dd className="m-0 text-[16px] font-semibold text-ink">{value}</dd>
            </div>
          ))}
        </dl>
      </section>
      <section className="flex flex-col gap-3 rounded-card border border-card-line bg-card p-5">
        <h2 className="m-0 text-[18px] font-semibold">{t('Language', 'ভাষা')}</h2>
        <div>
          <LanguageSwitch />
        </div>
      </section>
      {isOwner && (
        <section className="flex flex-col gap-2 rounded-card border border-card-line bg-card p-5">
          <h2 className="m-0 text-[18px] font-semibold">{t('Loan range rule (owner only)', 'ঋণের পরিসীমার নিয়ম (শুধু মালিক)')}</h2>
          <p className="m-0 text-[15px] text-body">
            {t(
              'The rule behind each suggested loan range. Your officers do not need to open it.',
              'প্রতিটি প্রস্তাবিত ঋণ-পরিসীমার পেছনের নিয়ম। আপনার কর্মকর্তাদের এটি খুলতে হয় না।',
            )}
          </p>
          <div>
            <Link to="/app/range-policy" className="font-semibold">
              {t('Open the range rule', 'পরিসীমার নিয়ম খুলুন')}
            </Link>
          </div>
        </section>
      )}
      {role !== 'merchant' && (
        <form
          className="flex max-w-[520px] flex-col gap-4 rounded-card border border-card-line bg-card p-5"
          onSubmit={(e) => {
            e.preventDefault()
            void change()
          }}
        >
          <h2 className="m-0 text-[18px] font-semibold">{t('Change your password', 'পাসওয়ার্ড বদলান')}</h2>
          <Field label={t('Current password', 'বর্তমান পাসওয়ার্ড')} required>
            <TextInput type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
          </Field>
          <Field label={t('New password', 'নতুন পাসওয়ার্ড')} required hint={t('At least 12 characters with upper and lower case letters, a digit and a symbol.', 'কমপক্ষে ১২ অক্ষর: বড় ও ছোট হাতের অক্ষর, একটি সংখ্যা ও একটি চিহ্ন।')}>
            <TextInput type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
          </Field>
          <Field label={t('New password again', 'নতুন পাসওয়ার্ড আবার')} required>
            <TextInput type="password" autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} />
          </Field>
          {message && <p role="status" className={`m-0 rounded-[10px] px-4 py-3 text-[14.5px] ${message.tone === 'ok' ? 'bg-strong-chip text-lens-dark' : 'bg-error-panel text-error'}`}>{message.text}</p>}
          <div>
            <Button type="submit" size="lg" disabled={busy || !current || !next || !again}>
              {t('Change password', 'পাসওয়ার্ড বদলান')}
            </Button>
          </div>
        </form>
      )}
    </Page>
  )
}
