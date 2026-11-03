/**
 * Add a connection (POST /sources): pick a source that can be connected now, name the
 * connection and fill in its settings. A credential is never typed here: the form asks for
 * the NAME of the environment variable that holds it. Administrators only.
 */
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'

import { api } from '@/api/client'
import type { ConnectorInfo, SourceConnectionOut } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSubmit } from '@/api/useSubmit'
import { ErrorCallout, LoadingState } from '@/components/ErrorCallout'
import { Field, FormActions, Select, TextInput } from '@/components/form'
import { Notice } from '@/components/Notice'
import { Page, PageHeader } from '@/components/Page'
import { Button } from '@/components/ui/button'
import { useLang, useT } from '@/lib/i18n'

export function NewSourcePage() {
  const t = useT()
  const lang = useLang()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const catalog = useApi<ConnectorInfo[]>('/sources/catalog')
  const available = (catalog.data ?? []).filter((c) => c.availability === 'available')
  const [key, setKey] = useState(params.get('connector') ?? '')
  const [name, setName] = useState('')
  const [values, setValues] = useState<Record<string, string>>({})
  const [touched, setTouched] = useState(false)
  const save = useSubmit<SourceConnectionOut>()

  if (catalog.error) return <Page><ErrorCallout error={catalog.error} /></Page>
  if (!catalog.data) return <Page><LoadingState title={t('Loading…', 'আসছে…')} /></Page>

  const spec = available.find((c) => c.key === key) ?? available[0]
  const missing = spec ? spec.settings.filter((s) => s.required && !values[s.key]) : []
  const problems = { name: name.trim().length < 2 ? t('Give the connection a name.', 'সংযোগের একটি নাম দিন।') : null }

  const submit = async () => {
    setTouched(true)
    if (!spec || problems.name || missing.length) return
    const settings = Object.fromEntries(spec.settings.filter((s) => s.kind !== 'secret_ref' && values[s.key]).map((s) => [s.key, values[s.key]]))
    const secretField = spec.settings.find((s) => s.kind === 'secret_ref')
    const created = await save.submit(() =>
      api<SourceConnectionOut>('/sources', {
        method: 'POST',
        json: { connector_key: spec.key, display_name: name.trim(), settings, secret_ref: secretField ? values[secretField.key] || null : null },
      }),
    )
    if (created) navigate(`/app/sources/${encodeURIComponent(created.connection_id)}`)
  }

  return (
    <Page>
      <nav aria-label={t('Breadcrumb', 'পথ')} className="flex items-center gap-2 text-sm text-body">
        <Link to="/app/sources" className="font-medium no-underline">{t('Data sources', 'ডেটার উৎস')}</Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">{t('Add a connection', 'সংযোগ যোগ করুন')}</span>
      </nav>
      <PageHeader title={t('Add a connection', 'সংযোগ যোগ করুন')} description={t('Only sources that can be connected in this build are offered. Planned sources need authorised access first.', 'শুধু এই সংস্করণে সংযুক্ত করা যায় এমন উৎস দেখানো হয়। পরিকল্পিত উৎসে আগে অনুমোদিত প্রবেশাধিকার দরকার।')} />
      {!spec ? (
        <Notice tone="info" title={t('Nothing to connect yet', 'এখনও সংযোগের কিছু নেই')}>
          {t('No source can be connected in this organisation’s environment.', 'এই প্রতিষ্ঠানের পরিবেশে কোনো উৎস সংযুক্ত করা যায় না।')}
        </Notice>
      ) : (
        <form noValidate className="flex max-w-[640px] flex-col gap-5 rounded-card border border-card-line bg-card p-5 sm:p-6" onSubmit={(e) => { e.preventDefault(); void submit() }}>
          <Field label={t('Source', 'উৎস')} required hint={lang === 'bn' ? spec.description_bn : spec.description}>
            <Select value={spec.key} onChange={(e) => { setKey(e.target.value); setValues({}) }} options={available.map((c) => ({ value: c.key, label: lang === 'bn' ? c.name_bn : c.name }))} />
          </Field>
          {spec.sandbox_only && (
            <Notice tone="info" title={t('Sandbox only', 'শুধু স্যান্ডবক্স')}>
              {t('This feed sends synthetic rows for made-up shops. It is not a provider, and its records are marked synthetic.', 'এই ফিড বানানো দোকানের সিনথেটিক সারি পাঠায়। এটি কোনো প্রোভাইডার নয়, আর এর রেকর্ড সিনথেটিক হিসেবে চিহ্নিত।')}
            </Notice>
          )}
          <Field label={t('Connection name', 'সংযোগের নাম')} required error={touched ? problems.name : null} hint={t('How your team will recognise this connection.', 'আপনার দল এই সংযোগ কীভাবে চিনবে।')}>
            <TextInput value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
          </Field>
          {spec.settings.map((s) => (
            <Field key={s.key} label={lang === 'bn' ? s.label_bn : s.label} required={s.required} hint={lang === 'bn' ? s.help_bn : s.help} error={touched && s.required && !values[s.key] ? t('Choose a value.', 'একটি মান বেছে নিন।') : null}>
              {s.kind === 'choice' ? (
                <Select value={values[s.key] ?? ''} onChange={(e) => setValues({ ...values, [s.key]: e.target.value })} placeholder={t('Choose one', 'একটি বেছে নিন')} options={s.choices.map((c) => ({ value: c, label: c.replaceAll('_', ' ') }))} />
              ) : (
                <TextInput value={values[s.key] ?? ''} onChange={(e) => setValues({ ...values, [s.key]: e.target.value.toUpperCase() })} placeholder={s.kind === 'secret_ref' ? 'CREDLENS_SOURCE_KEY' : undefined} autoComplete="off" spellCheck={false} />
              )}
            </Field>
          ))}
          {save.error && <ErrorCallout error={save.error} />}
          <FormActions>
            <Button type="submit" size="lg" disabled={save.pending}>{save.pending ? t('Adding…', 'যোগ হচ্ছে…') : t('Add connection', 'সংযোগ যোগ করুন')}</Button>
            <Link to="/app/sources" className="font-semibold no-underline">{t('Cancel', 'বাতিল')}</Link>
          </FormActions>
        </form>
      )}
    </Page>
  )
}
